from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from django.core.exceptions import ObjectDoesNotExist

from smashbotspain.models import Player, Arena, Region, Tier, ArenaPlayer, Message, Guild
from smashbotspain.serializers import PlayerSerializer, ArenaSerializer, TierSerializer, ArenaPlayerSerializer, MessageSerializer, GuildSerializer

# Create your views here.
class PlayerViewSet(viewsets.ModelViewSet):
    """
    This viewset automatically provides `list`, `create`, `retrieve`,
    `update` and `destroy` actions.    
    """
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer
    
    def create(self, request):       
        region_roles = Region.objects.filter()
        
        serializer = PlayerSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def matchmaking(self, request, pk):
        """
        Matches the player. Requires to have created an arena through POST /arenas/.
        """
        player = self.get_object()
        guild_id = request.data['guild']

        min_tier = Tier.objects.get(id=request.data['min_tier'])
        max_tier = Tier.objects.get(id=request.data['max_tier'])

        arenas = player.search(min_tier, max_tier, guild_id)

        if arenas: # Join existing arena
            arena = arenas.first()
            arena.add_player(player, "CONFIRMATION")
            arena.set_status("CONFIRMATION")
            arena.save()

            old_arena = Arena.objects.filter(guild=guild_id, created_by=player, status="SEARCHING").first()                
            old_arena.set_status("WAITING")

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
                arena_player.status = "PLAYING"
                arena_player.save()

                guest_arena = Arena.objects.filter(created_by=player).first()
                messages = guest_arena.message_set.all()
                
                for message in messages:
                    message.arena = arena
                    message.save()
                
                guest_arena.delete()

                response = {
                    'messages' : [{'id': message.id, 'channel': message.tier.channel_id} for message in arena.message_set.all()]
                }
            else:
                response = {}
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
                other_arena = Arena.objects.filter(created_by=other_player).first()
                other_arena.set_status("SEARCHING")
                searching_arena = other_arena
                arena.delete()
            else:
                arena_player.delete()
                other_arena = Arena.objects.filter(created_by=player).first()
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
                    'min_tier': searching_arena.min_tier.id,
                    'max_tier': searching_arena.max_tier.id,
                    'tiers': [{'id': tier.id, 'channel': tier.channel_id} for tier in tiers]
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

        channel = request.data['channel']
        arena = Arena.objects.filter(channel_id=channel).first()

        if arena is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        arena.add_player(player, status="INVITED")
        return Response(status=status.HTTP_200_OK)




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
            confirmation_list.append([{'id' : player.id, 'tier': player.tier.name, 'status': player.status()} for player in arena.players.all()])
        
        # PLAYING        
        playing_arenas = Arena.objects.filter(status="PLAYING")
        playing_list = response['playing']
        for arena in playing_arenas:
            playing_list.append([{'id' : player.id, 'tier': player.tier.name, 'status': player.status()} for player in arena.players.all()])
        
        return Response(response, status=status.HTTP_200_OK)        

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

        # Check author in arena
        if arena:
            is_in_arena = arena.arenaplayer_set.filter(status="PLAYING", player__id=author).exists()

        if not arena or arena.status != "PLAYING" or not is_in_arena:
            return Response({'not_playing': "NOT_PLAYING"}, status=status.HTTP_400_BAD_REQUEST)

        # Get players
        players = []
        for arena_player in arena.arenaplayer_set.filter(status="PLAYING").all():
            players.append(arena_player.player.id)

        is_closed = len(players) <= 2
        
        if not is_closed:            
            players.remove(author)            
            
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

        # Get GGs players
        ggs_players = []
        for arena_player in arena.arenaplayer_set.filter(status="GGS").all():
            ggs_players.append(arena_player.player.id)

        # Get messages
        messages = []
        for message in arena.message_set.all():
            messages.append({'id': message.id, 'channel': message.tier.channel_id})
            if is_closed:
                message.delete()
        return Response({'closed': is_closed, 'messages': messages, 'players': players, 'ggs_players': ggs_players}, status=status.HTTP_200_OK)
    
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
        
        # Arena params
        guild = arena.guild        
        host = arena.created_by
        min_tier = arena.min_tier
        max_tier = arena.max_tier
        
        hosts = arena.players.all()
        hosts = [host.id for host in hosts if host.status() == "PLAYING"]
        
        # Search and parse
        arenas = host.search(min_tier, max_tier, guild).all()        
        players = [arena.created_by for arena in arenas if arena.created_by.status() != "INVITED"]
        players.sort(key=lambda player: player.tier.weight, reverse=True)
        players = [{'id': player.id, 'tier': player.tier.name} for player in players]

        return Response({'players': players, 'hosts': hosts}, status=status.HTTP_200_OK)    

    def create(self, request):
        guild_id = request.data['guild']
        roles = request.data['roles']
        force_tier = request.data.get('force_tier', False)
        
        # Get player tier
        tier_roles = Tier.objects.filter(pk__in=roles)
        
        if not tier_roles:
            return Response({"cant_join":"NO_TIER"}, status=status.HTTP_400_BAD_REQUEST)
        
        player_tier = max(tier_roles, key=lambda role : role.weight)

        # Get or create player
        player_id = request.data['created_by']
        player_name = request.data['player_name']
        try:
            player = Player.objects.get(pk=player_id)
        except Player.DoesNotExist as e:                        
            player_data = {
                'id' : player_id,
                'name' : player_name,
                'tier' : player_tier.id
            }
            player_serializer = PlayerSerializer(data=player_data)
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
        data['min_tier'] = min_tier.id
        data['max_tier'] = max_tier.id
        
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
            old_serializer = ArenaSerializer(old_arena, data={'min_tier' : min_tier.id, 'max_tier' : max_tier.id}, partial=True)
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
            response_data['added_tiers'] = [{'id': tier.id, 'channel': tier.channel_id} for tier in added_tiers]
            response_data['removed_tiers'] = [{'id': tier.id, 'channel': tier.channel_id} for tier in removed_tiers]

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
                response_data["added_tiers"] = [{'id': tier.id, 'channel': tier.channel_id} for tier in tiers]
                response_data["removed_tiers"] = []
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(response_data, status=status.HTTP_201_CREATED)