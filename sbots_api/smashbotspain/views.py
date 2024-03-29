from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count

from smashbotspain.models import Player, Arena, Rating, Region, Tier, ArenaPlayer, Message, Guild, Character, Main, GameSet, Game, GamePlayer, Stage
from smashbotspain.serializers import (GameSerializer, GameSetSerializer, PlayerSerializer, ArenaSerializer, RatingSerializer, TierSerializer, ArenaPlayerSerializer, MessageSerializer, GuildSerializer,
                                        MainSerializer, RegionSerializer, CharacterSerializer, StageSerializer)

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
    lookup_field = "discord_id"
    
    def create(self, request):
        """
        Create a player, and imports their roles to characters
        """
        player_id = request.data['player']
        guild = Guild.objects.get(discord_id=request.data['guild'])
        roles = request.data.get('roles', [])

        characters = Character.objects.filter(guild=guild)
        regions = Region.objects.filter(guild=guild)
        tiers = Tier.objects.filter(guild=guild)
        
        # Create Player
        player, created = Player.objects.get_or_create(discord_id=player_id, defaults={
            'discord_id': player_id
        })        

        tier_roles = []        
        mains_count = 0        
        
        for role_id in roles:
            # Tier
            if tier := tiers.filter(discord_id=role_id).first():
                tier_roles.append(tier)
            # Characters
            elif character := characters.filter(discord_id=role_id).first():
                if created:
                    pocket, created = Main.objects.update_or_create(player=player, character=character, defaults={
                        'player': player,
                        'character': character,
                        'status': "MAIN" if mains_count < 2 else "SECOND"
                    })

                    mains_count += 1
            # Region
            elif region := regions.filter(discord_id=role_id).first():
                player.regions.add(region)
        
        # Remove previous tier
        if not created:
            previous_tier = player.tier(guild)
            if previous_tier:
                player.tiers.remove(previous_tier)

        # Add only the highest tier role
        if tier_roles:
            tier_roles.sort(key=lambda tier : tier.weight, reverse=True)
            player.tiers.add(tier_roles[0])
        
        # Add MMR
        tier = player.tier(guild=guild)

        if created and tier:
            player_mmr = Rating(player=player, guild=guild, score=player.tier(guild=guild).threshold)
            player_mmr.save()
        
        return Response({'tier': tier.discord_id if tier else None}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def profile(self, request, discord_id):
        player = self.get_object()
        guild = Guild.objects.get(discord_id=request.data['guild'])
        roles = request.data.get('roles', [])
        
        response = {}        
        
        # REGIONS
        regions = player.regions.filter(guild=guild)
        response['regions'] = [role.discord_id for role in regions]

        # CHARACTERS
        mains = player.main_set.filter(character__guild=guild, status="MAIN")
        seconds = player.main_set.filter(character__guild=guild, status="SECOND")
        pockets = player.main_set.filter(character__guild=guild, status="POCKET")

        response['mains'] = [role.character.discord_id for role in mains]
        response['seconds'] = [role.character.discord_id for role in seconds]
        response['pockets'] = [role.character.discord_id for role in pockets]

        # TIER
        tier = player.tier(guild=guild)        

        if not tier:
            tier_roles = []
            for role_id in roles:
            # Tier
                if tier := Tier.objects.filter(discord_id=role_id).first():
                    tier_roles.append(tier)
            
            if tier_roles:
                tier_roles.sort(key=lambda tier : tier.weight, reverse=True)
                player.set_tier(tier=tier_roles[0], guild=guild)
                tier = player.tier(guild=guild)
        
        response['tier'] = tier.discord_id if tier else None

        # RATING
        rating = Rating.objects.filter(guild=guild, player=player).first()
        if rating:
            response['score'] = rating.score
            if rating.promotion_wins is None:
                response['promotion'] = None
            else:
                response['promotion'] = {
                    'wins' : rating.promotion_wins,
                    'losses': rating.promotion_losses
                }            

        return Response(response, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def roles(self, request, discord_id):
        """
        Updates the role of the player. Can be of many types:
            - character (main or second)
            - region
        """
        player = self.get_object()
        role_type = request.data['role_type']
        
        role_id = request.data['role_id']        
        
        guild_id = request.data['guild']        
        guild = Guild.objects.get(discord_id=guild_id)
        ROLE_MESSAGE_TIME = guild.role_message_time

        action = None
        role = None
        
        # GET ROLE
        if role_type == "region":                        
            role = Region.objects.filter(guild=guild, discord_id=role_id).first()
        elif role_type in ("main", "second", "pocket"):            
            role = Character.objects.filter(guild=guild, discord_id=role_id).first()            
        elif role_type == 'tier':
            role = Tier.objects.filter(guild=guild, discord_id=role_id).first()
        else:
            return Response({'bad_type': "BAD_ROLE_TYPE", 'role_message_time': ROLE_MESSAGE_TIME}, status=status.HTTP_400_BAD_REQUEST)
        
        if role is None:
            return Response({'role_message_time': ROLE_MESSAGE_TIME}, status=status.HTTP_404_NOT_FOUND)
        
        # ADD OR REMOVE ROLE
        #  REGIONS
        if role_type == "region":
            if role.player_set.filter(discord_id=player.discord_id).exists():
                action = "REMOVE"
                role.player_set.remove(player)
            else:
                action = "ADD"
                role.player_set.add(player)
        
        # CHARACTER MAINS
        elif role_type in ("main", "second", "pocket"):
            if main := Main.objects.filter(player=player, character=role, status=role_type.upper()):
                action = "REMOVE"
                main.first().delete()
            else:
                if main := Main.objects.filter(player=player, character=role):
                    action = "SWAP"
                else:
                    action = "ADD"

                # NEW MAIN CREATION
                new_main = {
                    'status': role_type.upper(),
                    'player': player.discord_id,
                    'character': role.discord_id,
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
        
        # TIER PINGS
        elif role_type == 'tier':
            player_tier = player.tiers.filter(guild=guild).first()
            error = False
            if player_tier is None:
                error = "NO_TIER"
            if player_tier == role:
                error = 'SAME_TIER'
            elif player_tier < role:
                error = 'HIGHER_TIER'
            
            if error:                
                return Response({'tier_error': error, 'discord_id': role.discord_id, 'player_tier': player_tier.discord_id,
                    'role_message_time': ROLE_MESSAGE_TIME},
                    status=status.HTTP_400_BAD_REQUEST)
        
        return Response({'discord_id': role.discord_id, 'action': action, 'role_message_time': ROLE_MESSAGE_TIME},
            status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path="roles")
    def get_roles(self, request):
        """
        Returns a list with all the roles of the chosen type, and every player
        that has it.        
        """
        guild = Guild.objects.get(discord_id=request.data['guild'])
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
            role_list = guild.region_set.all()
        elif role_type in CHARACTER_STATUS:
            role_list = guild.character_set.all()
        
        
        # GET MEMBERS
        for role in role_list:
            if role_type in CHARACTER_STATUS:
                role_members = Player.objects.filter(main__in=role.main_set.filter(status=role_type)).all()
            else:
                role_members = role.player_set.all()
            
            role_detail = {'id': role.discord_id}
            
            role_detail['players'] = [player.discord_id for player in role_members]
            response.append(role_detail)
        
        # SORT RESPONSE
        if role_type != "tiers":
            response.sort(key=lambda role : len(role['players']), reverse=True)

        return Response({'roles': response}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def ranked_matchmaking(self, request, discord_id):
        """
        Matches. Ranked only
        """
        player = self.get_object()

        guild_id = request.data['guild']
        guild = Guild.objects.get(discord_id=guild_id)

        # Check ranked tier:
        rating = player.get_rating(guild)
        tier = player.tier(guild)
        
        if not tier or not rating:
            return Response({"cant_join" : "NO_TIER"}, status=status.HTTP_400_BAD_REQUEST)
        
        # If in promotion
        if rating.promotion_wins is not None: 
            tier = tier.next(guild)


        arenas = player.search_ranked(guild=guild, tier=tier)
        if arenas: # Join existing arena
            arena = arenas.first()
            arena.add_player(player, "CONFIRMATION")
            arena.set_status("CONFIRMATION")
            arena.save()

            arena.created_by.confirmation(arena)
            player.confirmation(arena)

            # Messages
            arena_messages = Message.objects.filter(arena=arena).all()
            
            return Response({
                "match_found" : True,
                "player_one" : arena.created_by.discord_id,
                "player_two" : player.discord_id,
                "messages" : [{'id': message.id, 'channel': message.channel_id} for message in arena_messages]
            }, status=status.HTTP_200_OK)
        else:
            ranked_arena = Arena.objects.filter(created_by=player, mode="RANKED").first()            
            
            messages = ranked_arena.get_messages() if ranked_arena else []
            return Response({'no_match': True, 'messages': messages}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['get'])
    def rematch(self, request, discord_id):
        """
        Allows a player that has just finished a ranked set to do another one.
        """
        player = self.get_object()

        # Get finished game_set to get arena
        game_set = GameSet.objects.filter(players=player).exclude(winner__isnull=True).exclude(arena__isnull=True).first()

        if not game_set:
            return Response(status=status.HTTP_404_NOT_FOUND)        
        arena = game_set.arena

        other_player = game_set.players.exclude(discord_id=discord_id).first()                

        if not player.can_rematch(other_player):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        serializer = GameSetSerializer(data={
                    'guild': arena.guild.id,
                    'players': [player.id for player in game_set.players.all()],
                    'arena': arena.id
        })

        # Remove arena from last set
        game_set.arena = None
        game_set.save()
        
        if serializer.is_valid():
            new_set = serializer.save()
            new_set.add_game()
        
        return Response({
            'player1': player.discord_id,
            'player2': other_player.discord_id
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def matchmaking(self, request, discord_id):
        """
        Matches the player. Requires to have created an arena through POST /arenas/.
        """
        player = self.get_object()
        guild_id = request.data['guild']
        guild = Guild.objects.get(discord_id=guild_id)

        old_arena = Arena.objects.filter(guild=guild, created_by=player, mode='FRIENDLIES', status="SEARCHING").first()
        
        if old_arena is None:
            return Response(status=status.HTTP_409_CONFLICT)
        
        min_tier = Tier.objects.get(discord_id=request.data['min_tier'])
        max_tier = Tier.objects.get(discord_id=request.data['max_tier'])        

        arenas = player.search(min_tier, max_tier, guild)

        if arenas: # Join existing arena
            arena = arenas.first()
            arena.add_player(player, "CONFIRMATION")
            arena.set_status("CONFIRMATION")
            arena.save()

            old_arena = Arena.objects.filter(guild=guild, created_by=player, mode='FRIENDLIES', status="SEARCHING").first()
            old_arena.set_status("WAITING")

            # REMOVE INVITATIONS
            for ap in ArenaPlayer.objects.filter(player__discord_id__in=(player.discord_id, arena.created_by.discord_id), status="INVITED").all():
                ap.delete()

            return Response({
                "match_found" : True,
                "player_one" : arena.created_by.discord_id,
                "player_two" : player.discord_id
            }, status=status.HTTP_200_OK)
        else:            
            return Response({'no_match', True}, status=status.HTTP_404_NOT_FOUND)    
    
    @action(detail=True, methods=['patch'])
    def confirmation(self, request, discord_id):        
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
                
                # Remove the AP born with the invitation, just change the status to the old one
                if ggs_player is not None:
                    arena_player, ggs_player = ggs_player, arena_player
                    ggs_player.delete()

                arena_player.status = "PLAYING"
                arena_player.save()

                guest_arenas = Arena.objects.filter(created_by=player, status="SEARCHING").all()
                
                # Fetch the messages of all other arenas
                messages = []
                for guest_arena in guest_arenas:
                    messages += list(guest_arena.message_set.all())
                
                for message in messages:
                    message.arena = arena
                    message.save()
                
                for guest_arena in guest_arenas:
                    guest_arena.delete()

                players = arena.get_players()

                response = {
                    'players' : players,
                    'messages' : [{'id': message.id, 'channel': message.channel_id} for message in arena.message_set.all()]
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
        is_ranked = arena.mode == 'RANKED'

        players = arena.players.all()
        other_player = arena.players.exclude(discord_id=player.discord_id).get()        
        
        # Rejected
        if not accepted:
            messages = []
            searching_arenas = []
            other_accepted = other_player.status() == "ACCEPTED"
            
            if player == arena.created_by:
                other_arenas = Arena.objects.filter(created_by__in=players, status="WAITING").exclude(id=arena.id)
                for other_arena in other_arenas:
                    other_arena.set_status("SEARCHING")
                    searching_arenas.append(other_arena)
                messages = arena.get_messages()
                arena.delete()
            else:
                arena_player.delete()
                
                rejected_arena = Arena.objects.filter(created_by=player, status="WAITING", mode=arena.mode).first()
                if rejected_arena is None:
                    return Response(status=status.HTTP_404_NOT_FOUND)
                messages = rejected_arena.get_messages()
                rejected_arena.delete()
                
                other_arenas = Arena.objects.filter(created_by__in=list(players), status__in=("WAITING", "CONFIRMATION")).all()
                for arena_to_search in other_arenas:
                    arena_to_search.set_status("SEARCHING")
                    searching_arenas.append(arena_to_search)

            # TIMEOUT
            if is_timeout:                
                if not other_accepted:  # No one responded                    
                    for searching_arena in searching_arenas:
                        messages += searching_arena.get_messages()
                        searching_arena.delete()
                    searching_arenas = []
                else: # Only current player timed out
                    player_arenas = Arena.objects.filter(created_by=player).all()
                    for searching_arena in player_arenas:
                        messages += searching_arena.get_messages()
                        searching_arena.delete()
                    searching_arenas = list(Arena.objects.filter(created_by=other_player).all())
            else:
                for searching_arena in searching_arenas:
                    if not is_ranked and searching_arena.mode != 'RANKED' and searching_arena.created_by == other_player:
                        searching_arena.rejected_players.add(player)
                        searching_arena.save()


            surviving_ranked_message = {}
            
            # Get and delete ranked message of the player who accepted:
            # (it will be then resent)
            if not (is_timeout and not other_accepted):
                surviving_ranked_arena = Arena.objects.filter(created_by=other_player, mode="RANKED").first()
                if surviving_ranked_arena:
                    message = Message.objects.filter(arena=surviving_ranked_arena, mode="RANKED").first()
                    if message:
                        surviving_ranked_message = {
                            'id': message.id,
                            'arena': message.arena.id,
                            'tier': message.arena.created_by.tier(message.arena.guild).discord_id,
                            'channel_id': message.channel_id,
                            'mode': message.mode,
                            'player_id' : message.arena.created_by.discord_id
                        }
                        message.delete()

                
            response_body = {
                'player_accepted': False,
                'timeout': is_timeout,
                'player_id' : player.discord_id,
                'arenas': [],
                'messages' : messages,
                'ranked_message': surviving_ranked_message
            }

            for searching_arena in searching_arenas:
                response_arena = {
                    'arena_id' : searching_arena.id,
                    'searching_player': searching_arena.created_by.discord_id,
                    'mode': searching_arena.mode              
                }
                
                if searching_arena.mode == "FRIENDLIES":
                    tiers = searching_arena.get_tiers()
                
                    response_arena.update({
                        'min_tier': searching_arena.min_tier.discord_id,
                        'max_tier': searching_arena.max_tier.discord_id,
                        'tiers': [{'id': tier.discord_id, 'channel': tier.channel_id} for tier in tiers]
                    })

                response_body['arenas'].append(response_arena)
            return Response(response_body, status=status.HTTP_200_OK)
        

        #   ACCEPTED
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
            'player_id' : player.discord_id,
            'arena_id' : arena.id,
            'all_accepted' : all_accepted,            
        }

        if all_accepted:
            # ArenaPlayer status -> PLAYING
            arena_players = arena.arenaplayer_set.all()
            for arena_player in arena_players:
                arena_player.set_status("PLAYING")            
            arena.set_status("PLAYING")

            # Create GameSet if RANKED
            if arena.mode == "RANKED":
                serializer = GameSetSerializer(data={
                    'guild': arena.guild.id,
                    'players': [player.id for player in arena.players.all()],
                    'arena': arena.id
                })
                if serializer.is_valid():
                    game_set = serializer.save()
                    game_set.add_game()
                else:
                    return Response(serializer.errors,  status=status.HTTP_400_BAD_REQUEST)                

            #  Delete "search" arenas
            obsolete_arenas = Arena.objects.filter(created_by__in=players, status__in=("WAITING", "SEARCHING"))            
            for obsolete_arena in obsolete_arenas:
                messages = Message.objects.filter(arena=obsolete_arena).all()
                for message in messages:
                    message.arena = arena
                    message.save()
                obsolete_arena.delete()
            
            # Delete ranked messages
            ranked_messages = Message.objects.filter(arena=arena, mode="RANKED").all()
            response['messages'] = arena.get_messages()
            
            for message in ranked_messages:
                message.delete()
            
        else:
            response['waiting_for'] = unconfirmed_players.first().player.discord_id

        return Response(response, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def invite(self, request, discord_id):
        player = self.get_object()

        if player.status() != "WAITING":
            return Response({'cant_invite': 'not_searching'}, status=status.HTTP_400_BAD_REQUEST)

        channel = request.data['channel']
        arena = Arena.objects.filter(channel_id=channel).first()

        if arena is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        arena.add_player(player, status="INVITED")
        return Response(status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def character(self, request, discord_id):
        """
        Sets the character this player will play this game
        """
        player = self.get_object()
        game = player.get_game()

        if not game:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
        # Set the character
        game_player = game.gameplayer_set.filter(player=player).first()
        game_player.character = request.data['character']
        game_player.save()

        return Response(status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def game_info(self, request, discord_id):
        """
        Returns the information of the current game.
        """
        player = self.get_object()
        game = player.get_game()

        if not game:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # Get characters
        game_players = []
        for gp in game.gameplayer_set.all():
            game_players.append({
                'player': gp.player.discord_id,
                'character': gp.character
            })                    

        # Get channel_id
        channel_id = game.game_set.arena.channel_id
        
        response = {
            'guild': game.guild.discord_id,
            'game_players': game_players,
            'channel_id': channel_id
        }

        return Response(response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'])
    def win_game(self, request, discord_id):
        """
        Marks the current game as a victory.
        Needs the player to be playing a ranked match.
        """
        player = self.get_object()
        game = player.get_game()

        if not game:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        game_set = game.game_set
        
        # Set winner and check if ggs
        game.set_winner(player)
        is_over = game_set.set_winner()

        if is_over:
            # Set finished_at
            game_set.finish()

            # Check if rematch is available
            player1, player2 = game_set.players.all()            
            can_rematch = player1.can_rematch(player2)
                        
            # Update ratings            
            winner_info, loser_info = game_set.update_ratings()

            response = {
                'set_finished': True,
                'can_rematch': can_rematch,
                'winner_info': winner_info,
                'loser_info': loser_info,
            }
        else:
            game_set.add_game()            
            response = {
                'set_finished': False,                
            }
        
        return Response(response, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def surrender(self, request, discord_id):
        """
        Marks the current set as a loss.
        """
        player = self.get_object()
        game_set = player.get_game_set()

        if not game_set:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
        game = player.get_game()
        
        if not game:
            return Response(status=status.HTTP_400_BAD_REQUEST)        
        
        # Set winner
        players = game_set.players.all()

        winner = players.exclude(discord_id=player.discord_id).first()
        game.set_winner(winner)
        
        game_set.winner = winner
        game_set.save()

        # Set finished_at
        game_set.finish()        
                        
        # Update ratings
        winner_info, loser_info = game_set.update_ratings()

        response = {
                'set_finished': True,
                'can_rematch': False,
                'winner_info': winner_info,
                'loser_info': loser_info,
            }

        return Response(response, status=status.HTTP_200_OK)



    
    @action(detail=True, methods=['get'])
    def score(self, request, discord_id):
        """
        Returns the score of the current GameSet this player is playing (or has just finished)
        """
        player = self.get_object()
        game_set = player.get_game_set()

        if not game_set:
            return Response(status=status.HTTP_400_BAD_REQUEST)        

        this_player_wins = game_set.game_set.filter(winner=player).count()
        other_player_wins = game_set.game_set.exclude(winner=player).exclude(winner__isnull=True).count()

        return Response({
            'player_wins': this_player_wins,
            'other_player_wins': other_player_wins
        }, status=status.HTTP_200_OK)

    
    @action(detail=True, methods=['post'])
    def tier(self, request, discord_id):
        """
        Sets the tier of a player
        """
        player = self.get_object()

        guild_id = request.data['guild']
        guild = Guild.objects.filter(discord_id = guild_id).first()
        if not guild:
            return Response({'error': 'GUILD_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
        
        tier_id = request.data['tier']
        tier = Tier.objects.filter(discord_id = tier_id, guild=guild).first()
        if not tier:
            return Response({'error': 'TIER_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
        
        rating, created = Rating.objects.get_or_create(player=player, guild=guild)
        
        # Remove previous tier
        previous_tier_id = None
        if not created:
            previous_tier = player.tier(guild)            
            if previous_tier:
                previous_tier_id = previous_tier.discord_id
                player.tiers.remove(previous_tier)
        
        # Set tier
        player.tiers.add(tier)

        rating.score = tier.threshold
        rating.promotion_wins = None
        rating.promotion_losses = None
        rating.save()

        return Response({
            'old_tier': previous_tier_id,
            'tier': player.tier(guild).discord_id,
            'score': rating.score,
            'wins': rating.promotion_wins,
            'losses': rating.promotion_losses
        }, status=status.HTTP_200_OK)



class RatingViewSet(viewsets.ModelViewSet):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer

    @action(detail=False, methods=['post'])
    def score(self, request):
        """
        Sets the score rating of a player
        """
        # Adding instead of setting
        add_mode = request.data.get('add', False)

        points = int(request.data['points'])
        player_id = request.data['player']
        guild_id = request.data['guild']

        # Check everything exists
        player = Player.objects.filter(discord_id=player_id).first()
        if not player:
            return Response({'error': 'PLAYER_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
        
        guild = Guild.objects.filter(discord_id=guild_id).first()
        if not guild:
            return Response({'error': 'GUILD_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
        
        rating = Rating.objects.filter(player=player, guild=guild).first()
        if not rating:
            return Response({'error': 'RATING_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
        
        old_rating = rating.score        
        
        # Set score
        if add_mode:
            rating.score += points
        else:
            rating.score = points
        
        rating.save()

        return Response({'score': rating.score, 'diff': rating.score - old_rating}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def promotion(self, request):
        """
        Sets the promotion of a player
        """
        promotion_wins = request.data.get('wins')
        promotion_losses = request.data.get('losses')
        
        player_id = request.data['player']
        guild_id = request.data['guild']

        # Check everything exists
        player = Player.objects.filter(discord_id=player_id).first()
        if not player:
            return Response({'error': 'PLAYER_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
        
        guild = Guild.objects.filter(discord_id=guild_id).first()
        if not guild:
            return Response({'error': 'GUILD_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
        
        rating = Rating.objects.filter(player=player, guild=guild).first()
        if not rating:
            return Response({'error': 'RATING_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
        
        # Set promotion score
        rating.promotion_wins = promotion_wins
        rating.promotion_losses = promotion_losses
        rating.save()

        return Response({'wins': rating.promotion_wins, 'losses': rating.promotion_losses}, status=status.HTTP_200_OK)
        

class GameSetViewSet(viewsets.ModelViewSet):
    queryset = GameSet.objects.all()
    serializer_class = GameSetSerializer

    @action(detail=False, methods=['post'])
    def set_winner(self, request):
        """
        Usable by an admin only (checked in Discord).
        """
        channel_id = request.data['channel']        

        # FIND THE GAMESET        
        arena = Arena.objects.filter(channel_id=channel_id).first()
        if not arena:
            return Response({'error': 'ARENA_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)        
        game_set = arena.gameset_set.first()
        if not game_set:
            return Response({'error': 'GAMESET_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)        
        # CHECK THE WINNER IS PLAYING THIS SET
        winner_id = request.data['winner']
        winner = game_set.players.filter(discord_id=winner_id).first()

        if not winner:
            return Response({'error': 'PLAYER_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)
        
        # UPDATE THE WINNER
        game_set.winner = winner
        game_set.save()
        game_set.finish()

        # DELETE UNFINISHED GAMES
        game_set.game_set.filter(winner__isnull=True).delete()

        # Update ratings
        winner_info, loser_info = game_set.update_ratings()

        response = {
            'set_finished': True,
            'can_rematch': False,
            'winner_info': winner_info,
            'loser_info': loser_info,
        }

        return Response(response, status=status.HTTP_200_OK)

class GameViewSet(viewsets.ModelViewSet):
    queryset = Game.objects.all()
    serializer_class = GameSerializer
    
    @action(methods=['get'], detail=False)
    def last_winner(self, request):
        """
        Returns id of the winner of the last game
        """
        player = Player.objects.get(discord_id = request.data['player_id'])

        game = player.get_game()

        if not game:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
        last_game = Game.objects.filter(game_set = game.game_set).exclude(winner__isnull=True).order_by('-number').first()
        
        if not last_game:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
        last_winner = last_game.winner

        return Response({'last_winner': last_winner.discord_id}, status=status.HTTP_200_OK)


    @action(methods=['post'], detail=False)
    def stage(self, request):        
        """
        Sets the stage of the current game for a player
        """
        player_id = request.data['player_id']        
        player = Player.objects.get(discord_id=player_id)
        
        game = player.get_game()

        if not game:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
        # Set stage
        stage_name = request.data['stage_name']
        
        stage_obj = Stage.objects.filter(name=stage_name).first()
        game.stage = stage_obj
        game.save()

        return Response(status=status.HTTP_200_OK)
    
    @action(methods=['post'], detail=False)
    def remake(self, request):
        """
        Deletes the last game with no winner (i.e, the current game) and creates a new one.
        """
        player_id = request.data['player_id']
        player = Player.objects.get(discord_id=player_id)

        game = player.get_game()

        if not game:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
        game_set = game.game_set
        
        # Restart game
        game.delete()
        new_game = game_set.add_game()

        # Get other player
        other_player = GamePlayer.objects.filter(game=new_game).exclude(player=player).first()
        if not other_player:
            return Response(status=status.HTTP_404_NOT_FOUND)

        return Response({
            'game_number': new_game.number,
            'other_player_id' : other_player.player.discord_id
        }, status=status.HTTP_200_OK)

class StageViewSet(viewsets.ModelViewSet):
    queryset = Stage.objects.all()
    serializer_class = StageSerializer
        


class RegionViewSet(viewsets.ModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer

    @action(methods=['post'], detail=False, url_path="import")
    def import_regions(self, request):        
        roles = request.data['roles']

        # Get Guild and Roles
        guild_id = request.data['guild']
        guild = Guild.objects.get(discord_id=guild_id)                   
        
        # Create (or update) the Region roles
        role_count = 0                        
        for role_id in roles:
            region_role, created = Region.objects.update_or_create(guild=guild, discord_id=role_id, defaults={                                    
                                    'guild': guild,
                                    'discord_id': role_id,
                                })
            if created:
                role_count += 1

        return Response({'count': role_count}, status=status.HTTP_200_OK)

class CharacterViewSet(viewsets.ModelViewSet):
    queryset = Character.objects.all()
    serializer_class = CharacterSerializer

    @action(methods=['post'], detail=False, url_path="import")
    def import_characters(self, request):        
        roles = request.data['roles']

        # Get Guild and Roles
        guild_id = request.data['guild']
        guild = Guild.objects.get(discord_id=guild_id)
        
        # Create (or update) the Character roles
        role_count = 0        
                
        for role_id in roles:
            char_role, created = Character.objects.update_or_create(discord_id=role_id, guild=guild,
                                defaults={                                    
                                    'discord_id': role_id,
                                    'guild': guild
                                })
            if created:
                role_count += 1

        return Response({'count': role_count}, status=status.HTTP_200_OK)

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
    lookup_field = 'discord_id'
    queryset = Tier.objects.all()
    serializer_class = TierSerializer

    @action(methods=['post'], detail=False, url_path="import")
    def import_tiers(self, request):
        roles = request.data['roles']

        # Get Guild and Roles
        guild_id = request.data['guild']
        guild = Guild.objects.get(discord_id=guild_id)
        
        # Create (or update) the Tier roles
        role_count = 0                        
        for role in roles:            
            tier_role, created = Tier.objects.update_or_create(guild=guild, discord_id=role['id'], defaults={                                    
                                    'guild': guild,
                                    'discord_id': role['id'],
                                    'weight': role['weight']
                                })
            if created:
                role_count += 1

        return Response({'count': role_count}, status=status.HTTP_200_OK)

    @action(methods=['get'], detail=True)
    def leaderboards(self, request, discord_id):
        """
        Gets the info needed to update the leaderboard of a particular tier.
        """
        tier = self.get_object()
        guild = tier.guild

        # Get players in this tier
        players = Player.objects.filter(tiers=tier).order_by('-rating__score').all()

        player_infos = []
        for player in players:
            rating = Rating.objects.get(player=player)
            
            if rating.promotion_wins is None:
                promotion_info = None
            else:
                promotion_info = {
                    'wins': rating.promotion_wins,
                    'losses': rating.promotion_losses
                }

            player_info = {
                'id' : player.discord_id,
                'rating': rating.score, 
                'promotion_info': promotion_info,
                'streak': player.get_streak(guild, capped=False)
            }

            player_infos.append(player_info)
        
        response = {
            'players': player_infos,
            'leaderboard_channel' : guild.leaderboard_channel,
            'leaderboard_message' : tier.leaderboard_message,
        }

        return Response(response, status=status.HTTP_200_OK)


class GuildViewSet(viewsets.ModelViewSet):
    queryset = Guild.objects.all()
    serializer_class = GuildSerializer
    lookup_field = 'discord_id'
    
    @action(detail=True)
    def list_message(self, request, discord_id):
        guild = self.get_object()
        
        friendlies_searching = Arena.objects.filter(status="SEARCHING", mode="FRIENDLIES")
        ranked_searching = Arena.objects.filter(status="SEARCHING", mode="RANKED")
        
        tiers = Tier.objects.order_by('-weight').all()        
        
        response = {
            'tiers' : [],
            'confirmation' : [],
            'playing': [],
            'list_channel': guild.list_channel,
            'list_message': guild.list_message,
            'ranked_searching': ranked_searching.count()
        }
        
        # TIERS        
        tier_lists = response['tiers']
        for tier in tiers:
            tier_lists.append({'id' : tier.discord_id, 'friendlies_players': [arena.created_by.discord_id for arena in friendlies_searching
                                if tier.between(arena.min_tier, arena.max_tier)],
                                'ranked_players': [arena.created_by.discord_id for arena in ranked_searching if tier == arena.tier]})
        # CONFIRMATION
        confirmation_arenas = Arena.objects.filter(status="CONFIRMATION")
        confirmation_list = response['confirmation']
        for arena in confirmation_arenas:
            confirmation_list.append(
                [
                    {'id' : player.discord_id, 'tier': player.tier(guild).discord_id,
                    'status': player.status(),'mode': arena.mode}
                    for player in arena.players.all()
                ]
            )
        
        # PLAYING        
        playing_arenas = Arena.objects.filter(status="PLAYING").order_by('mode')
        playing_list = response['playing']
        for arena in playing_arenas:
            playing_list.append(
                [
                    {'id' : ap.player.discord_id, 'tier': ap.player.tier(guild).discord_id,
                    'status': ap.status, 'mode': arena.mode} 
                for ap in arena.arenaplayer_set.filter(status="PLAYING").all()])
        
        return Response(response, status=status.HTTP_200_OK)        

    @action(detail=False)
    def ranked_messages(self, request):
        """
        Sends the information about the ranked channels and messages of all guilds.
        """
        guilds = Guild.objects.all()

        response = []
        for guild in guilds:
            info = {
                'guild_id': guild.discord_id,
                'channel_id': guild.ranked_channel,
                'message_id': guild.ranked_message,
            }
            response.append(info)
        
        return Response({'guilds': response}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def beta_reward(self, request, discord_id):
        """
        - Resets ALL Ratings lower than their threshold
        - Gives +20 points to everyone that played 3 or more ranked sets.
        """
        guild = self.get_object()

        # Get players with 3 or more ranked sets
        testers = GameSet.objects.values('players__discord_id').annotate(count=Count('players'))
        testers = testers.filter(count__gte=3).order_by('-count').all()        
        
        tester_response = [
            {
                'player' : tester['players__discord_id'],
                'sets' : tester['count']
            }
            for tester in testers
        ]        


        # Reset ALL Ratings
        tester_ids = [tester['players__discord_id'] for tester in testers]
        tester_players = Player.objects.filter(discord_id__in=tester_ids).all()

        ratings = Rating.objects.filter(guild=guild).all()

        for rating in ratings:
            player = rating.player
            tier = player.tier(guild)

            if rating.score < tier.threshold:
                player.set_tier(tier=tier, guild=guild)
            
            # Add extra points
            if player in tester_players:
                new_rating = player.get_rating(guild)
                new_rating.score += 20
                new_rating.save()
        
        # Get Tiers
        tiers = Tier.objects.filter(guild=guild).all()
        tier_response = [tier.discord_id for tier in tiers]
        
        return Response({
            'testers': tester_response,
            'tiers': tier_response
        }, status=status.HTTP_200_OK)


class ArenaViewSet(viewsets.ModelViewSet):
    queryset = Arena.objects.all()
    serializer_class = ArenaSerializer

    @action(detail=False, methods=['delete'])
    def clean_up(self, request):
        """
        Deletes all arenas. Returns the channels and messages to delete
        If the param startup is True, only the confirmation and waiting arenas are deleted.
        """
        response = []

        startup = request.data.get('startup', False)
        
        if startup:
            arenas = Arena.objects.filter(status__in=("CONFIRMATION", "WAITING")).all()
        else:
            arenas = Arena.objects.all()

        for arena in arenas:
            arena_dict = {'guild': arena.guild.discord_id, 'channel': arena.channel_id,
                'player': arena.created_by.discord_id,
                'status': arena.status,
                'mode': arena.mode,
                'messages': [{'id': message.id, 'channel': message.channel_id} for message in arena.message_set.all()]}
            response.append(arena_dict)

            # Clean up ranked
            game_set = arena.gameset_set.first()
            if arena.mode == "RANKED" and game_set:                
                # If it hasn't finished yet, delete it
                if game_set.winner is None:
                    game_set.delete()
            
            arena.delete()

        return Response({'arenas': response}, status=status.HTTP_200_OK)

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
        guild_id = request.data['guild']

        # Get GGs time
        guild = Guild.objects.get(discord_id=guild_id)

        author = Player.objects.get(discord_id=request.data['author'])

        # RANKED GAMES: Check if set is finished
        if request.data.get('ranked'):
            game_set = author.get_game_set()

            if not game_set:
                return Response(status=status.HTTP_400_BAD_REQUEST)

            if not game_set.winner:
                return Response(status=status.HTTP_409_CONFLICT)

        # Check author in arena
        if arena:
            is_in_arena = arena.arenaplayer_set.filter(status="PLAYING", player=author).exists()

        if not arena or arena.status != "PLAYING" or not is_in_arena:
            return Response({'not_playing': "NOT_PLAYING"}, status=status.HTTP_400_BAD_REQUEST)

        # Min players?        
        is_closed = arena.arenaplayer_set.filter(status="PLAYING").count() <= 2        
        
        if not is_closed:
            arena_player = arena.arenaplayer_set.filter(player=author, status="PLAYING").first()
            if arena_player is None:
                return Response({'not_playing': "NOT_PLAYING"}, status=status.HTTP_400_BAD_REQUEST)
            
            arena_player.status = "GGS"
            arena_player.save()        

        # Get players
        players = arena.get_players()

        # Get messages
        messages = []
        for message in arena.message_set.all():
            messages.append({'id': message.id, 'channel': message.channel_id})
            if is_closed:
                message.delete()

        # Delete Arena
        if is_closed:
            arena.delete()
        
        return Response({'closed': is_closed, 'messages': messages, 'players': players, 'ggs_time': guild.ggs_time}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def cancel(self, request):
        player_id = request.data['player']

        player = Player.objects.get(discord_id=player_id)
        player_status = player.status()

        mode = request.data['mode']        
        arena = Arena.objects.filter(status="SEARCHING", created_by=player, mode=mode).first()

        #  CAN'T CANCEL
        if not player_status or (player_status in ArenaPlayer.CAN_JOIN_STATUS and not arena):
            return Response({'not_searching': "NOT_SEARCHING"}, status=status.HTTP_400_BAD_REQUEST)
        elif not arena:
            return Response({'not_searching' : player_status}, status=status.HTTP_400_BAD_REQUEST)

        # REMOVE INVITATIONS
        for ap in ArenaPlayer.objects.filter(player=player, status="INVITED").all():
            ap.delete()

        messages = []
        for message in arena.message_set.all():
            messages.append({'id': message.id, 'channel': message.channel_id})
            message.delete()

        #  CANCEL
        arena.delete()
                
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
        hosts = [host.discord_id for host in hosts if host.status() == "PLAYING"]
        
        # Search players, and parse
        arenas = host.search(min_tier, max_tier, guild, invite=True).all()        
        players = [arena.created_by for arena in arenas if arena.created_by.status() != "INVITED"]
        players.sort(key=lambda player: player.tier(guild).weight, reverse=True)
        players = [{'id': player.discord_id, 'tier': player.tier(guild).discord_id} for player in players]

        return Response({'players': players, 'hosts': hosts}, status=status.HTTP_200_OK)    

    @action(detail=False, methods=['post'])
    def ranked(self, request):
        guild_id = request.data['guild']
        guild = Guild.objects.get(discord_id=guild_id)

        # Get player
        player_id = request.data['created_by']
        try:
            player = Player.objects.get(discord_id=player_id)
        except Player.DoesNotExist as e:            
            return Response({"cant_join": "PLAYER_DOES_NOT_EXIST"}, status=status.HTTP_400_BAD_REQUEST)
        except Player.MultipleObjectsReturned as e:            
            return Response({"cant_join" : "MULTIPLE_PLAYERS"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if can search
        my_ranked = Arena.objects.filter(created_by=player, mode="RANKED", status="SEARCHING").first()
        player_status = "ALREADY_SEARCHING" if my_ranked else player.status()
        
        if player_status in ArenaPlayer.CANT_JOIN_STATUS or player_status == "ALREADY_SEARCHING" :
            return Response({"cant_join" : player_status}, status=status.HTTP_409_CONFLICT)

        # Check ranked tier:
        rating = player.get_rating(guild)
        tier = player.tier(guild)
        
        if not tier or not rating:
            return Response({"cant_join" : "NO_TIER"}, status=status.HTTP_400_BAD_REQUEST)
        
        # If in promotion
        if rating.promotion_wins is not None: 
            tier = tier.next(guild)
        
        # Create my ranked arena
        arena_data = {
            'guild' : guild.discord_id,
            'created_by': player.discord_id,
            'mode': 'RANKED',
            'status': 'WAITING',
            'tier': tier.discord_id
        }
        arena_serializer = ArenaSerializer(data=arena_data)
        if arena_serializer.is_valid():
            my_arena = arena_serializer.save()
        else:
            return Response(arena_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Matchmaking
        arenas = player.search_ranked(guild=guild, tier=tier)

        if arenas: # Join existing arena
            arena = arenas.first()
            arena.add_player(player, "CONFIRMATION")
            arena.set_status("CONFIRMATION")
            arena.save()

            arena.created_by.confirmation(arena)
            player.confirmation(arena)

            # Messages
            arena_messages = Message.objects.filter(arena=arena).all()
            
            return Response({
                "match_found" : True,
                "id": my_arena.id,
                "tier": arena.tier.discord_id,
                "player_one" : arena.created_by.discord_id,
                "player_two" : player_id,
                "messages" : [{'id': message.id, 'channel': message.channel_id} for message in arena_messages]
            }, status=status.HTTP_201_CREATED)        
        else:
            my_arena.set_status("SEARCHING")
            return Response({"match_found": False, "tier": my_arena.tier.discord_id, "id": my_arena.id}, status=status.HTTP_201_CREATED)



    def create(self, request):
        guild_id = request.data['guild']
        guild = Guild.objects.get(discord_id=guild_id)

        roles = request.data['roles']
        force_tier = request.data.get('force_tier', False)
        
        # Get player tier
        tier_roles = Tier.objects.filter(discord_id__in=roles)        
        if not tier_roles:
            return Response({"cant_join":"NO_TIER"}, status=status.HTTP_400_BAD_REQUEST)        
        player_tier = max(tier_roles, key=lambda role : role.weight)

        # Get player
        player_id = request.data['created_by']
        try:
            player = Player.objects.get(discord_id=player_id)
        except Player.DoesNotExist as e:            
            return Response({"cant_join": "PLAYER_DOES_NOT_EXIST"}, status=status.HTTP_400_BAD_REQUEST)
        except Player.MultipleObjectsReturned as e:            
            return Response({"cant_join" : "MULTIPLE_PLAYERS"}, status=status.HTTP_400_BAD_REQUEST)
        
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
            old_arena = Arena.objects.filter(created_by=player, status="SEARCHING", mode="FRIENDLIES").get()

            # Get added and removed tiers
            old_tiers = Tier.objects.filter(weight__gte=old_arena.min_tier.weight, weight__lte=old_arena.max_tier.weight)
            new_tiers = Tier.objects.filter(weight__gte=min_tier.weight, weight__lte=max_tier.weight)
            
            added_tiers = [tier for tier in new_tiers if tier not in old_tiers]
            removed_tiers = [tier for tier in old_tiers if tier not in new_tiers]

            if not (added_tiers or removed_tiers):
                return Response({"cant_join" : "ALREADY_SEARCHING"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Partial update
            old_serializer = ArenaSerializer(old_arena,
                data={
                    'min_tier' : min_tier.discord_id,
                    'max_tier' : max_tier.discord_id
                }, partial=True)
            
            if old_serializer.is_valid():
                old_serializer.save()
            else:
                return Response({"cant_join" : "BAD_TIERS", 
                    "wanted_tier" : min_tier.discord_id,
                    "player_tier" : max_tier.discord_id},
                status=status.HTTP_400_BAD_REQUEST)

        except Arena.DoesNotExist:
            pass
        
        arenas = player.search(min_tier, max_tier, guild)                

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

            # Put the rest of your arenas or the other player's in WAITING
            for other_arena in Arena.objects.filter(created_by__in=(player, arena.created_by)).exclude(id=arena.id).all():
                other_arena.set_status("WAITING")

            # REMOVE INVITATIONS
            for ap in ArenaPlayer.objects.filter(player__discord_id__in=(player_id, arena.created_by.discord_id), status="INVITED").all():
                ap.delete()

            # Messages
            arena_messages = Message.objects.filter(arena=arena).all()
            old_arena_messages = Message.objects.filter(arena=old_arena).all()

            messages = list(arena_messages) + list(old_arena_messages)
            
            
            return Response({
                "match_found" : True,
                "player_one" : arena.created_by.discord_id,
                "player_two" : player_id,
                "messages" : [{'id': message.id, 'channel': message.channel_id} for message in messages]
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
                player_tier = serializer.context.get('player_tier', None)
                wanted_tier = serializer.context.get('wanted_tier', None)

                errors = {
                    'cant_join': "BAD_TIERS",
                    'player_tier': player_tier,
                    'wanted_tier': wanted_tier,
                } if player_tier and wanted_tier else serializer.errors
                
                return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(response_data, status=status.HTTP_201_CREATED)