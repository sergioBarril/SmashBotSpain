from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from django.core.exceptions import ObjectDoesNotExist

from smashbotspain.models import Player, Arena, Region, RegionRole, Tier, ArenaPlayer, Message, Guild, Character, CharacterRole, Main
from smashbotspain.serializers import (PlayerSerializer, ArenaSerializer, TierSerializer, ArenaPlayerSerializer, MessageSerializer, GuildSerializer,
                                        MainSerializer, RegionSerializer, RegionRoleSerializer, CharacterSerializer, CharacterRoleSerializer)

from smashbotspain.aux_methods.roles import normalize_character
from smashbotspain.aux_methods.text import key_format

from smashbotspain.params.roles import SMASH_CHARACTERS, SPANISH_REGIONS

# Create your views here.
class PlayerViewSet(viewsets.ModelViewSet):
    """
    This viewset automatically provides `list`, `create`, `retrieve`,
    `update` and `destroy` actions.    
    """
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer
    
    def create(self, request):        
        serializer = PlayerSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def profile(self, request, pk):
        player = self.get_object()
        guild = Guild.objects.get(id=request.data['guild'])
        
        response = {}        
        
        # REGIONS
        region_roles = player.region_roles.filter(guild=guild)
        response['regions'] = [{'name': region_role.region.name , 'emoji': region_role.region.emoji } for region_role in region_roles]

        # CHARACTERS
        mains = player.main_set.filter(character_role__guild=guild, status="MAIN")
        seconds = player.main_set.filter(character_role__guild=guild, status="SECOND")
        pockets = player.main_set.filter(character_role__guild=guild, status="POCKET")

        response['mains'] = [{'name': role.character_role.character.name, 'emoji' : role.character_role.character.emoji} for role in mains]
        response['seconds'] = [{'name': role.character_role.character.name, 'emoji' : role.character_role.character.emoji} for role in seconds]
        response['pockets'] = [{'name': role.character_role.character.name, 'emoji' : role.character_role.character.emoji} for role in pockets]

        # TIER
        tier = player.tiers.filter(guild=guild).first()
        response['tier'] = tier.discord_id if tier else None

        return Response(response, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def roles(self, request, pk):
        """
        Updates the role of the player. Can be of many types:
            - character (main or second)
            - region            
        """
        player = self.get_object()
        role_type = request.data['role_type']
        param = request.data['param']
        
        guild_id = request.data['guild']        
        guild = Guild.objects.get(id=guild_id)
        ROLE_MESSAGE_TIME = guild.role_message_time

        action = None
        role = None
        
        
        # GET ROLE
        if role_type == "region":
            region = Region.objects.filter(name__unaccent__iexact=key_format(param)).first()
            if region:
                role = RegionRole.objects.filter(guild=guild, region=region).first()
        elif role_type in ("main", "second", "pocket"):
            normalized = normalize_character(param)
            if normalized:
                character = Character.objects.filter(name=normalized).first()
            else:
                character = Character.objects.filter(name__unaccent__iexact=key_format(param)).first()
            if character:
                role = CharacterRole.objects.filter(guild=guild, character=character).first()
        elif role_type == 'tier':
            role = Tier.objects.filter(name__icontains=param, guild=guild).first()
        else:
            return Response({'bad_type': "BAD_ROLE_TYPE", 'role_message_time': ROLE_MESSAGE_TIME}, status=status.HTTP_400_BAD_REQUEST)
        
        if role is None:
            return Response({'role_message_time': ROLE_MESSAGE_TIME}, status=status.HTTP_404_NOT_FOUND)
        
        # ADD OR REMOVE ROLE
        if role_type == "region": # REGIONS
            if role.player_set.filter(id=player.id).exists():
                action = "REMOVE"
                role.player_set.remove(player)
            else:
                action = "ADD"
                role.player_set.add(player)
        elif role_type in ("main", "second", "pocket"): # CHARACTER MAINS
            if main := Main.objects.filter(player=player, character_role=role, status=role_type.upper()):
                action = "REMOVE"
                main.first().delete()
            else:
                if main := Main.objects.filter(player=player, character_role=role):
                    action = "SWAP"
                else:
                    action = "ADD"
                
                new_main = {
                    'status': role_type.upper(),
                    'player': player.id,
                    'character_role': role.id,
                }
                
                serializer = MainSerializer(data=new_main, context={'guild': guild})
                if serializer.is_valid():
                    serializer.save()
                else:
                    mains = serializer.context.get('mains')
                    if mains:
                        errors = {
                            'mains': serializer.context['mains']               
                        }
                    else:
                        errors = serializer.errors
                    
                    errors['role_message_time'] = ROLE_MESSAGE_TIME                    
                    return Response(errors, status=status.HTTP_400_BAD_REQUEST)                

                if action == "SWAP":
                    main.first().delete()        
        elif role_type == 'tier':  # TIER PINGS
            player_tier = player.tiers.filter(guild=guild).first()
            error = False
            if player_tier is None:
                error = "NO_TIER"
            if player_tier == role:
                error = 'SAME_TIER'                
            elif player_tier < role:
                error = 'HIGHER_TIER'            
            
            if error:                
                return Response({'tier_error': error, 'discord_id': role.discord_id, 'name': role.name, 'player_tier': player_tier.name,
                    'role_message_time': ROLE_MESSAGE_TIME},
                    status=status.HTTP_400_BAD_REQUEST)
        
        # ROLE NAME:
        if role_type in ('main', 'second', 'pocket'):
            name = role.character.name
            emoji = role.character.emoji
        elif role_type == "region":
            name = role.region.name
            emoji = role.region.emoji
        else:
            name = role.name
            emoji = ""            
        return Response({'name': name, 'discord_id': role.discord_id, 'emoji': emoji, 'action': action, 'role_message_time': ROLE_MESSAGE_TIME},
            status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path="roles")
    def get_roles(self, request):
        """
        Returns a list with all the roles of the chosen type, and every player
        that has it.        
        """
        guild = Guild.objects.get(id=request.data['guild'])
        role_type = request.data['role_type']        
        
        response = [] 
        role_list = None

        # CHARACTER TYPE FIX
        if role_type in ("mains", "seconds", "pockets"):
            role_type = role_type[:-1].upper()
        
        CHARACTER_STATUS = ("MAIN", "SECOND", "POCKET")
        
        # GET ROLE LIST
        if role_type == "tiers":
            role_list = guild.tier_set.order_by('-weight').all()
        elif role_type == "regions":
            role_list = guild.regionrole_set.all()
        elif role_type in CHARACTER_STATUS:
            role_list = guild.characterrole_set.all()
        
        
        # GET MEMBERS
        for role in role_list:
            if role_type in CHARACTER_STATUS:
                role_members = Player.objects.filter(main__in=role.main_set.filter(status=role_type)).all()
            else:
                role_members = role.player_set.all()
            
            if role_type == "regions":
                role_detail = {'name' : role.region.name}
            elif role_type in CHARACTER_STATUS:
                role_detail = {'name' : role.character.name}
            else:
                role_detail = {'name': role.name}
            
            role_detail['players'] = [player.id for player in role_members]
            response.append(role_detail)
        
        # SORT RESPONSE
        if role_type != "tiers":
            response.sort(key=lambda role : len(role['players']), reverse=True)

        return Response({'roles': response}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def matchmaking(self, request, pk):
        """
        Matches the player. Requires to have created an arena through POST /arenas/.
        """
        player = self.get_object()
        guild_id = request.data['guild']

        min_tier = Tier.objects.get(discord_id=request.data['min_tier'])
        max_tier = Tier.objects.get(discord_id=request.data['max_tier'])

        arenas = player.search(min_tier, max_tier, guild_id)

        if arenas: # Join existing arena
            arena = arenas.first()
            arena.add_player(player, "CONFIRMATION")
            arena.set_status("CONFIRMATION")
            arena.save()

            old_arena = Arena.objects.filter(guild=guild_id, created_by=player, status="SEARCHING").first()                
            old_arena.set_status("WAITING")

            # REMOVE INVITATIONS
            for ap in ArenaPlayer.objects.filter(player__id__in=(player_id, arena.created_by.id), status="INVITED").all():
                ap.delete()

            return Response({
                "match_found" : True,
                "player_one" : arena.created_by.id,
                "player_two" : player_id
            }, status=status.HTTP_200_OK)
        else:
            return Response({'no_match', True}, status=status.HTTP_404_NOT_FOUND)    
    
    @action(detail=True, methods=['patch'])
    def confirmation(self, request, pk):
        player = self.get_object()
        accepted = request.data['accepted']
        is_timeout = request.data.get('timeout', False)

        
        is_invited = request.data.get('invited', False)
        if is_invited:
            channel = request.data.get('channel')
            arena = Arena.objects.filter(channel_id=channel).first()
            arena_player = ArenaPlayer.objects.filter(status="INVITED", player=player, arena=arena).first()
            
            if arena_player is None:
                return Response(status=status.HTTP_404_NOT_FOUND)
            
            if accepted:
                ggs_player = ArenaPlayer.objects.filter(status="GGS", player=player, arena=arena).first()
                
                if ggs_player is not None:
                    arena_player, ggs_player = ggs_player, arena_player
                    ggs_player.delete()

                arena_player.status = "PLAYING"
                arena_player.save()

                guest_arena = Arena.objects.filter(created_by=player, status="SEARCHING").first()
                messages = guest_arena.message_set.all()
                
                for message in messages:
                    message.arena = arena
                    message.save()
                
                guest_arena.delete()

                players = arena.get_players()

                response = {
                    'players' : players,
                    'messages' : [{'id': message.id, 'channel': message.tier.channel_id} for message in arena.message_set.all()]
                }
            else:                
                response = {}
                arena.rejected_players.add(player)
                arena_player.delete()
            return Response(response, status=status.HTTP_200_OK)
        
        arena_player = ArenaPlayer.objects.filter(status__in=["CONFIRMATION", "ACCEPTED"], player=player).first()
        
        if arena_player is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        arena = arena_player.arena

        players = arena.players.all()
        other_player = arena.players.exclude(id=player.id).get()        
        
        # Rejected
        if not accepted:
            searching_arena = None
            other_accepted = other_player.status() == "ACCEPTED"
            
            if player == arena.created_by:
                other_arena = Arena.objects.filter(created_by=other_player, status="WAITING").first()
                other_arena.set_status("SEARCHING")
                searching_arena = other_arena
                arena.delete()
            else:
                arena_player.delete()
                other_arena = Arena.objects.filter(created_by=player, status="WAITING").first()
                arena.set_status("SEARCHING")
                searching_arena = arena                
                other_arena.delete()            
                        
            if is_timeout and not other_accepted:
                searching_arena.delete()
                searching_arena = None
            elif not is_timeout:
                searching_arena.rejected_players.add(player)
                searching_arena.save()

            response_body = {
                'player_accepted': False,
                'timeout': is_timeout,
                'player_id' : player.id,
            }             

            if searching_arena is None:
                response_body['arena_id'] = None
            else:
                tiers = searching_arena.get_tiers()
                
                response_body.update({
                    'arena_id' : searching_arena.id,
                    'searching_player': searching_arena.created_by.id,
                    'min_tier': searching_arena.min_tier.discord_id,
                    'max_tier': searching_arena.max_tier.discord_id,
                    'tiers': [{'id': tier.discord_id, 'channel': tier.channel_id} for tier in tiers]
                })            
            return Response(response_body, status=status.HTTP_200_OK)
        
        serializer = ArenaPlayerSerializer(arena_player, data={'status' : 'ACCEPTED'}, partial=True)
        if serializer.is_valid():
            serializer.save()
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if the other players have already accepted        
        unconfirmed_players = ArenaPlayer.objects.filter(arena=arena, status="CONFIRMATION")
        all_accepted = not unconfirmed_players.exists()
                        
        # Build response and cleanup
        response = {
            'player_accepted' : True,
            'player_id' : player.id,
            'arena_id' : arena.id,
            'all_accepted' : all_accepted,            
        }

        if all_accepted:
            # ArenaPlayer status -> PLAYING
            arena_players = arena.arenaplayer_set.all()
            for arena_player in arena_players:
                arena_player.set_status("PLAYING")            
            arena.set_status("PLAYING")

            #  Delete "search" arenas
            obsolete_arenas = Arena.objects.filter(created_by__in=players, status__in=("WAITING", "SEARCHING"))
            for arena in obsolete_arenas:
                arena.delete()                    
        else:
            response['waiting_for'] = unconfirmed_players.first().player.id

        return Response(response, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def invite(self, request, pk):
        player = self.get_object()

        if player.status() != "WAITING":
            return Response({'cant_invite': 'not_searching'}, status=status.HTTP_400_BAD_REQUEST)

        channel = request.data['channel']
        arena = Arena.objects.filter(channel_id=channel).first()

        if arena is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        arena.add_player(player, status="INVITED")
        return Response(status=status.HTTP_200_OK)

class RegionViewSet(viewsets.ModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer

    @action(methods=['post'], detail=False, url_path="import")
    def import_regions(self, request):        
        roles = request.data['roles']

        # Get Guild and Roles
        guild_id = request.data['guild']
        guild = Guild.objects.get(id=guild_id)

        # Create (or update) the Smash Regions
        region_count = 0
        for region in SPANISH_REGIONS:
            reg, created = Region.objects.update_or_create(
                name=region['name'], defaults= {
                    'emoji': region['emoji']
            })
            if created:
                region_count += 1        
        
        # Create (or update) the Region roles
        role_count = 0
        region_names = Region.objects.values_list('name', flat=True).all()
        region_roles = [role for role in roles if role['name'] in region_names]
                
        for role in region_roles:            
            reg = Region.objects.get(name=role['name'])
            region_role, created = RegionRole.objects.update_or_create(region=reg, guild=guild,
                                defaults={
                                    'region': reg,
                                    'guild': guild,
                                    'discord_id': role['id'],
                                })
            if created:
                role_count += 1

        return Response({'count': region_count, 'role_count': role_count}, status=status.HTTP_200_OK)

class CharacterViewSet(viewsets.ModelViewSet):
    queryset = CharacterRole.objects.all()
    serializer_class = CharacterRoleSerializer

    @action(methods=['post'], detail=False, url_path="import")
    def import_characters(self, request):        
        roles = request.data['roles']

        # Get Guild and Roles
        guild_id = request.data['guild']
        guild = Guild.objects.get(id=guild_id)
        

        # Create Smash Characters
        char_count = 0
        for character in SMASH_CHARACTERS:
            char, created = Character.objects.update_or_create(
                name=character['name'], defaults= {
                    'emoji': character['emoji']
            })
            if created:
                char_count += 1
                
        # Create (or update) the Character roles
        role_count = 0
        char_names = Character.objects.values_list('name', flat=True).all()
        char_roles = [role for role in roles if role['name'] in char_names]        
        
        for role in char_roles:
            character = Character.objects.get(name=role['name'])
            char_role, created = CharacterRole.objects.update_or_create(character=character, guild=guild,
                                defaults={
                                    'character' : character,
                                    'discord_id': role['id'],
                                    'guild': guild
                                })
            if created:
                role_count += 1

        return Response({'count': char_count, 'role_count': role_count}, status=status.HTTP_200_OK)




class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer

    def create(self, request):        
        data = request.data.get('messages', None)            
        is_bulk = data is not None        
        
        if not is_bulk:
            data = request.data
                
        serializer = MessageSerializer(data=data, many=is_bulk)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def destroy(self, request, pk):
        # Single destroy
        message = self.get_object()
        serializer = MessageSerializer(message)
        serializer.data
        message.delete()
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(methods=['post'], detail=False)
    def bulk_delete(self, request):
        # Bulk destroy
        messages = request.data.get('messages', None)
        if messages is None:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(messages, many=True)
        self.perform_destroy(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

class TierViewSet(viewsets.ModelViewSet):
    queryset = Tier.objects.all()
    serializer_class = TierSerializer

class GuildViewSet(viewsets.ModelViewSet):
    queryset = Guild.objects.all()
    serializer_class = GuildSerializer
    
    @action(detail=True)
    def list_message(self, request, pk):
        guild = self.get_object()
        
        searching_arenas = Arena.objects.filter(status="SEARCHING")
        tiers = Tier.objects.order_by('-weight').all()
        
        response = {
            'tiers' : [],
            'confirmation' : [],
            'playing': [],
            'list_channel': guild.list_channel,
            'list_message': guild.list_message
        }
        
        # TIERS        
        tier_lists = response['tiers']
        for tier in tiers:
            tier_lists.append({'name' : tier.name, 'players': [arena.created_by.id for arena in searching_arenas
                                                                if tier.between(arena.min_tier, arena.max_tier)]})
        # CONFIRMATION
        confirmation_arenas = Arena.objects.filter(status="CONFIRMATION")
        confirmation_list = response['confirmation']
        for arena in confirmation_arenas:
            confirmation_list.append([{'id' : player.id, 'tier': player.tier(guild).name, 'status': player.status()} for player in arena.players.all()])
        
        # PLAYING        
        playing_arenas = Arena.objects.filter(status="PLAYING")
        playing_list = response['playing']
        for arena in playing_arenas:
            playing_list.append([{'id' : ap.player.id, 'tier': ap.player.tier(guild).name, 'status': ap.status} 
                for ap in arena.arenaplayer_set.filter(status="PLAYING").all()])
        
        return Response(response, status=status.HTTP_200_OK)        


    @action(detail=True, methods=['get'])
    def role(self, request, pk):
        """
        Returns the Discord_id of a role, given a text
        """        
        guild = self.get_object()
        
        param = request.data['param']

        # Get Tiers
        if role := Tier.objects.filter(guild=guild, name__iexact=param):
            role = role.first()
            role_name = role.name
        elif role := RegionRole.objects.filter(guild=guild, region__name__unaccent__iexact=key_format(param)):
            role = role.first()
            role_name = role.region.name
        elif normalized := normalize_character(param):
            role = CharacterRole.objects.filter(guild=guild, character__name=normalized).first()
            role_name = role.character.name
        elif role := CharacterRole.objects.filter(guild=guild, character__name__unaccent__iexact=key_format(param)):
            role = role.first()
            role_name = role.character.name
        else:
            role = None
        
        if role is None:
            return Response({'error' : 'NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)        
        return Response({'discord_id': role.discord_id, 'name': role_name}, status=status.HTTP_200_OK)

class ArenaViewSet(viewsets.ModelViewSet):
    queryset = Arena.objects.all()
    serializer_class = ArenaSerializer

    @action(detail=False)
    def playing(self, request):
        playing_arenas = Arena.objects.filter(status="PLAYING")

        page = self.paginate_queryset(playing_arenas)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(playing_arenas, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def ggs(self, request):                
        channel_id = request.data['channel_id']
        arena = Arena.objects.filter(channel_id=channel_id).first()
        author = request.data['author']
        guild_id = request.data['guild']

        # Get GGs time
        guild = Guild.objects.get(id=guild_id)        

        # Check author in arena
        if arena:
            is_in_arena = arena.arenaplayer_set.filter(status="PLAYING", player__id=author).exists()

        if not arena or arena.status != "PLAYING" or not is_in_arena:
            return Response({'not_playing': "NOT_PLAYING"}, status=status.HTTP_400_BAD_REQUEST)

        # Min players?        
        is_closed = arena.arenaplayer_set.filter(status="PLAYING").count() <= 2        
        
        if not is_closed:
            arena_player = arena.arenaplayer_set.filter(player__id=author, status="PLAYING").first()
            if arena_player is None:
                return Response({'not_playing': "NOT_PLAYING"}, status=status.HTTP_400_BAD_REQUEST)
            
            arena_player.status = "GGS"
            arena_player.save()
        else:
            arena.set_status("CLOSED")
        
            # Remove channel_id
            arena.channel_id = None
            arena.save()

        # Get players
        players = arena.get_players()

        # Get messages
        messages = []
        for message in arena.message_set.all():
            messages.append({'id': message.id, 'channel': message.tier.channel_id})
            if is_closed:
                message.delete()
        return Response({'closed': is_closed, 'messages': messages, 'players': players, 'ggs_time': guild.ggs_time}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def cancel(self, request):
        player_id = request.data['player']

        player = Player.objects.get(id=player_id)
        player_status = player.status()
        searching_arenas = Arena.objects.filter(status="SEARCHING", created_by=player_id).all()

        #  CAN'T CANCEL
        if not player_status or (player_status in ArenaPlayer.CAN_JOIN_STATUS and not searching_arenas):
            return Response({'not_searching': "NOT_SEARCHING"}, status=status.HTTP_400_BAD_REQUEST)
        elif not searching_arenas:
            return Response({'not_searching' : player_status}, status=status.HTTP_400_BAD_REQUEST)

        #  CANCEL
        for arena in searching_arenas:
            arena.set_status("CANCELLED")
        
        # REMOVE INVITATIONS
        for ap in ArenaPlayer.objects.filter(player=player, status="INVITED").all():
            ap.delete()

        messages = []
        for message in arena.message_set.all():
            messages.append({'id': message.id, 'channel': message.tier.channel_id})
            message.delete()
        
        return Response({'messages': messages}, status=status.HTTP_200_OK)
    
    @action(detail=False)
    def invite_list(self, request):
        # Get arena
        channel = request.data.get('channel', None)
        if channel is None:
            return Response(status=status.HTTP_400_BAD_REQUEST)        
        
        arena = Arena.objects.filter(channel_id=channel).first()        
        if arena is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        # Search params
        guild = arena.guild        
        host = arena.created_by
        min_tier = arena.min_tier
        max_tier = arena.max_tier
        
        hosts = arena.players.all()
        hosts = [host.id for host in hosts if host.status() == "PLAYING"]
        
        # Search players, and parse
        arenas = host.search(min_tier, max_tier, guild, invite=True).all()        
        players = [arena.created_by for arena in arenas if arena.created_by.status() != "INVITED"]
        players.sort(key=lambda player: player.tier(guild).weight, reverse=True)
        players = [{'id': player.id, 'tier': player.tier(guild).name} for player in players]

        return Response({'players': players, 'hosts': hosts}, status=status.HTTP_200_OK)    

    def create(self, request):
        guild_id = request.data['guild']
        roles = request.data['roles']
        force_tier = request.data.get('force_tier', False)
        
        # Get player tier
        tier_roles = Tier.objects.filter(discord_id__in=roles)
        
        if not tier_roles:
            return Response({"cant_join":"NO_TIER"}, status=status.HTTP_400_BAD_REQUEST)
        
        player_tier = max(tier_roles, key=lambda role : role.weight)

        # Get or create player
        player_id = request.data['created_by']        
        try:
            player = Player.objects.get(pk=player_id)
        except Player.DoesNotExist as e:                        
            player_data = {
                'id' : player_id                
            }
            player_serializer = PlayerSerializer(data=player_data, context={'tier' : player_tier.discord_id})
            if player_serializer.is_valid():
                player = player_serializer.save()
            else:
                return Response(player_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if can search
        player_status = player.status()
                
        if player_status in ArenaPlayer.CANT_JOIN_STATUS:            
            return Response({"cant_join" : player_status}, status=status.HTTP_409_CONFLICT)

        # Get tier range
        min_tier = Tier.objects.filter(channel_id=request.data['min_tier']).first()
        max_tier = min_tier if force_tier else player_tier
        
        data = request.data.copy()
        data['min_tier'] = min_tier.discord_id
        data['max_tier'] = max_tier.discord_id
        
        # Update search
        old_arena = None
        try:
            old_arena = Arena.objects.filter(created_by=player, status="SEARCHING").get()

            # Get added and removed tiers
            old_tiers = Tier.objects.filter(weight__gte=old_arena.min_tier.weight, weight__lte=old_arena.max_tier.weight)
            new_tiers = Tier.objects.filter(weight__gte=min_tier.weight, weight__lte=max_tier.weight)
            
            added_tiers = [tier for tier in new_tiers if tier not in old_tiers]
            removed_tiers = [tier for tier in old_tiers if tier not in new_tiers]

            if not (added_tiers or removed_tiers):
                return Response({"cant_join" : "ALREADY_SEARCHING"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Partial update
            old_serializer = ArenaSerializer(old_arena, data={'min_tier' : min_tier.discord_id, 'max_tier' : max_tier.discord_id}, partial=True)
            if old_serializer.is_valid():
                old_serializer.save()
            else:
                return Response({"cant_join" : "BAD_TIERS", 
                    "wanted_tier" : min_tier.name,
                    "player_tier" : max_tier.name},
                status=status.HTTP_400_BAD_REQUEST)

        except Arena.DoesNotExist:
            pass
        
        arenas = player.search(min_tier, max_tier, guild_id)        

        if arenas: # Join existing arena
            arena = arenas.first()
            arena.add_player(player, "CONFIRMATION")
            arena.set_status("CONFIRMATION")
            arena.save()

            # Update your arena or make a new one anyway
            if not old_arena:
                serializer = ArenaSerializer(data=data)
                if serializer.is_valid():
                    old_arena = serializer.save()
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)                
                
            old_arena.set_status("WAITING")

            # REMOVE INVITATIONS
            for ap in ArenaPlayer.objects.filter(player__id__in=(player_id, arena.created_by.id), status="INVITED").all():
                ap.delete()

            # Messages
            arena_messages = Message.objects.filter(arena=arena).all()
            old_arena_messages = Message.objects.filter(arena=old_arena).all()

            messages = list(arena_messages) + list(old_arena_messages)
            
            
            return Response({
                "match_found" : True,
                "player_one" : arena.created_by.id,
                "player_two" : player_id,
                "messages" : [{'id': message.id, 'channel': message.tier.channel_id} for message in messages]
            }, status=status.HTTP_201_CREATED)
        
        if old_arena: # No match available, just updated search
            response_data = old_serializer.data.copy()
            response_data['added_tiers'] = [{'id': tier.discord_id, 'channel': tier.channel_id} for tier in added_tiers]
            response_data['removed_tiers'] = [{'id': tier.discord_id, 'channel': tier.channel_id} for tier in removed_tiers]

            # Remove messages from tiers
            removed_messages = []
            for tier in removed_tiers:
                tier_messages = Message.objects.filter(tier=tier, arena=old_arena).all()
                for message in tier_messages:
                    removed_messages.append({'id': message.id, 'channel': tier.channel_id})
                    message.delete()
            response_data['removed_messages'] = removed_messages

            return Response(response_data, status=status.HTTP_200_OK)
        else: # Create new arena
            serializer = ArenaSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                response_data = serializer.data.copy()
                response_data["match_found"] = False
                
                tiers = Tier.objects.filter(weight__gte=min_tier.weight, weight__lte=max_tier.weight)
                response_data["added_tiers"] = [{'id': tier.discord_id, 'channel': tier.channel_id} for tier in tiers]
                response_data["removed_tiers"] = []
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(response_data, status=status.HTTP_201_CREATED)