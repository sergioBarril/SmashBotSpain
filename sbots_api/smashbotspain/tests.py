# Django
from django.test import TestCase

# Python
import json

# Django Rest Framework
from rest_framework.test import APIClient
from rest_framework import status

# Models
from smashbotspain.models import Arena, Player, ArenaPlayer, Tier, Message, Guild

def make_player(discord_id, tier=None):
    player = Player(
        discord_id = discord_id
    )
    player.save()
    if tier:
        tier.player_set.add(player)
    return player

def make_tier(discord_id, channel_id, weight):
    tier = Tier(
        discord_id=discord_id,        
        channel_id = channel_id,
        weight = weight
    )
    tier.save()
    return tier

class ArenaTestCase(TestCase):    
    def setUp(self):
        # Setup Players        
        self.tropped = make_player(discord_id=12345678987654)
        self.razen = make_player(discord_id=45678987654321)        
        
        # Setup Tiers
        self.tier1 = make_tier(discord_id=45678987654, channel_id=94939382, weight=4)
        self.tier2 = make_tier(discord_id=54678987654, channel_id=9393938, weight=3)
        self.tier3 = make_tier(discord_id=54678987655, channel_id=4848484, weight=2)
        self.tier4 = make_tier(discord_id=54678987656, channel_id=1231566, weight=1)

        # Setup Guild
        self.guild = Guild(discord_id=1284839194, spam_channel=183813893, flairing_channel=3814884,
            list_channel=1190139, list_message=1949194, match_timeout=90, cancel_time=30, ggs_time=15)
        self.guild.save()

    def test_friendlies_search(self):
        client = APIClient()

        body = {            
            'guild' : self.guild.discord_id,
            'created_by' : self.tropped.discord_id,            
            'min_tier' : self.tier3.channel_id,  # Tier 3 channel            
            'roles' : [self.tier2.discord_id], # Tier 2
            'mode' : 'FRIENDLIES'
        }
        
        response = client.post('/arenas/', body, format='json')
        
        result = json.loads(response.content)        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', result)       
        self.assertEqual(result['status'], 'SEARCHING')
        self.assertEqual(result['max_tier'], self.tier2.discord_id)  # Tier 2
        self.assertEqual(result['min_tier'], self.tier3.discord_id)  # Tier 3
    
    def test_already_searching(self):
        self.test_friendlies_search()
        client = APIClient()

        body = {
            'guild' : self.guild.discord_id,
            'created_by' : self.tropped.discord_id,            
            'min_tier' : self.tier3.channel_id,  # Tier 3 channel            
            'roles' : [self.tier2.discord_id],  # Tier 2
            'mode' : 'FRIENDLIES'
        }

        response = client.post('/arenas/', body, format='json')
        result = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(result.get('cant_join'), "ALREADY_SEARCHING")

    def test_friendlies_tier_too_high(self):
        client = APIClient()

        body = {            
            'guild' : self.guild.discord_id,
            'created_by' : self.tropped.discord_id,  # Tropped            
            'min_tier' : self.tier1.channel_id,  # Tier 1 channel            
            'roles' : [self.tier2.discord_id], # Tier 2
            'mode' : 'FRIENDLIES'
        }

        response = client.post('/arenas/', body, format='json')

        result = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_matched(self):
        client = APIClient()

        body_tropped = {            
            'guild' : self.guild.discord_id,
            'created_by' : self.tropped.discord_id, # Tropped            
            'min_tier' : self.tier3.channel_id,  # Tier 3 channel
            'roles' : [self.tier2.discord_id], # Tier 2
            'mode' : 'FRIENDLIES'
        }

        body_razenokis = {            
            'guild' : self.guild.discord_id,
            'created_by' : self.razen.discord_id, # Razen            
            'min_tier' : self.tier2.channel_id,  # Tier 2 channel            
            'roles' : [self.tier1.discord_id], # Tier 1
            'mode' : 'FRIENDLIES'
        }
        
        search_response = client.post('/arenas/', body_tropped, format='json')
        match_response = client.post('/arenas/', body_razenokis, format='json')
        result = json.loads(match_response.content)

        self.assertEqual(match_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(result.get('match_found'))

        self.assertEqual(result.get('player_one'), self.tropped.discord_id)
        self.assertEqual(result.get('player_two'), self.razen.discord_id)

    def test_force_tier(self):
        client = APIClient()

        body = {            
            'guild' : self.guild.discord_id,
            'created_by' : self.tropped.discord_id, # Tropped            
            'min_tier' : self.tier3.channel_id,  # Tier 3 channel
            'roles' : [self.tier2.discord_id], # Tier 2
            'force_tier': True,
            'mode' : 'FRIENDLIES'

        }

        # Create        
        response = client.post('/arenas/', body, format='json')
        result = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(result.get('added_tiers'), [{'id': self.tier3.discord_id, 'channel': self.tier3.channel_id}])
        self.assertEqual(result.get('removed_tiers'), [])
        
        # Update search
        body['min_tier'] = self.tier4.channel_id
        
        response = client.post('/arenas/', body, format='json')
        result = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(result.get('added_tiers'), [{'id': self.tier4.discord_id, 'channel': self.tier4.channel_id}])
        self.assertEqual(result.get('removed_tiers'), [{'id': self.tier3.discord_id, 'channel': self.tier3.channel_id}])

    def test_accepted(self):
        client = APIClient()
        self.test_matched()

        # Before accepting
        arena = Arena.objects.filter(status="CONFIRMATION").first()        

        arena_tropped = arena.arenaplayer_set.filter(player=self.tropped).get()
        arena_razen = arena.arenaplayer_set.filter(player=self.razen).get()
        
        self.assertEqual(arena_tropped.status, "CONFIRMATION")
        self.assertEqual(arena_razen.status, "CONFIRMATION")
        
        body = {'accepted': True}
        
        # After one accepts
        response = client.patch(f'/players/{self.tropped.discord_id}/confirmation/', body, format='json')
        result = json.loads(response.content)
                
        arena_tropped = arena.arenaplayer_set.filter(player=self.tropped).get()        
        self.assertTrue(result['player_accepted'])        
        self.assertEqual(arena_tropped.status, "ACCEPTED")
        self.assertFalse(result['all_accepted'])

        obsolete_arena = Arena.objects.filter(status="WAITING").first()
        self.assertIsNotNone(obsolete_arena)
        self.assertEqual(len(ArenaPlayer.objects.all()), 3)

        # After the other accepts
        response = client.patch(f'/players/{self.razen.discord_id}/confirmation/', body, format='json')
        result = json.loads(response.content)

        arena_razen = arena.arenaplayer_set.filter(player=self.razen).get()
        arena_tropped = arena.arenaplayer_set.filter(player=self.tropped).get()
        
        self.assertTrue(result['player_accepted'])
        self.assertEqual(arena_razen.status, "PLAYING")
        self.assertEqual(arena_tropped.status, "PLAYING")
        self.assertTrue(result['all_accepted'])

        arena = Arena.objects.get(created_by=self.tropped)
        self.assertEqual(arena.status, "PLAYING")

        obsolete_arena = Arena.objects.filter(status="WAITING").first()
        self.assertIsNone(obsolete_arena)
        self.assertEqual(len(ArenaPlayer.objects.all()), 2)

    def test_rejected_timeout(self):
        client = APIClient()
        self.test_matched()

        # Before rejecting
        arena = Arena.objects.filter(status="CONFIRMATION").first()
        waiting_arena = Arena.objects.filter(created_by=self.razen).first()

        self.assertEqual(arena.created_by, self.tropped)        
        self.assertEqual(waiting_arena.status, "WAITING")

        
        arena_tropped = arena.arenaplayer_set.filter(player=self.tropped).get()
        arena_razen = arena.arenaplayer_set.filter(player=self.razen).get()
        
        self.assertEqual(arena_tropped.status, "CONFIRMATION")
        self.assertEqual(arena_razen.status, "CONFIRMATION")

        waiting_players = Arena.objects.filter(created_by=self.razen).first().arenaplayer_set.all()
        self.assertEqual(len(waiting_players), 1)
                
        # After one rejects
        body = {'accepted': False, 'timeout': False}
        response = client.patch(f'/players/{self.tropped.discord_id}/confirmation/', body, format='json')
        result = json.loads(response.content)

        self.assertIsNone(Arena.objects.filter(id=arena.id).first()) # Arena Deleted

        waiting_arena = Arena.objects.filter(created_by=self.razen).first()
        self.assertEqual(waiting_arena.status, "SEARCHING")

        waiting_players = waiting_arena.arenaplayer_set.all()
        self.assertEqual(len(waiting_players), 1)
        self.assertEqual(waiting_players[0].status, "WAITING")

        # Assert Response
        CORRECT_TIERS = [{'id': self.tier1.discord_id, 'channel': self.tier1.channel_id}, {'id': self.tier2.discord_id, 'channel': self.tier2.channel_id}]
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(result['player_accepted'])
        self.assertEqual(result['player_id'], self.tropped.discord_id)

        for arena in result['arenas']:
            self.assertEqual(arena['mode'], 'FRIENDLIES')
            self.assertEqual(arena['searching_player'], self.razen.discord_id)
            self.assertEqual(arena['tiers'], CORRECT_TIERS)

    def test_rejected(self):
        client = APIClient()
        self.test_matched()

        # Before rejecting
        arena = Arena.objects.filter(status="CONFIRMATION").first()
        waiting_arena = Arena.objects.filter(created_by=self.razen).first()

        self.assertEqual(arena.created_by, self.tropped)        
        self.assertEqual(waiting_arena.status, "WAITING")

        
        arena_tropped = arena.arenaplayer_set.filter(player=self.tropped).get()
        arena_razen = arena.arenaplayer_set.filter(player=self.razen).get()
        
        self.assertEqual(arena_tropped.status, "CONFIRMATION")
        self.assertEqual(arena_razen.status, "CONFIRMATION")

        waiting_players = Arena.objects.filter(created_by=self.razen).first().arenaplayer_set.all()
        self.assertEqual(len(waiting_players), 1)
                
        # After one rejects
        body = {'accepted': False, 'timeout': False}
        response = client.patch(f'/players/{self.tropped.discord_id}/confirmation/', body, format='json')
        result = json.loads(response.content)

        self.assertIsNone(Arena.objects.filter(id=arena.id).first()) # Arena Deleted

        waiting_arena = Arena.objects.filter(created_by=self.razen).first()
        self.assertEqual(waiting_arena.status, "SEARCHING")

        waiting_players = waiting_arena.arenaplayer_set.all()
        self.assertEqual(len(waiting_players), 1)
        self.assertEqual(waiting_players[0].status, "WAITING")

        #  Rejected_players
        self.assertIn(self.tropped, waiting_arena.rejected_players.all())
        self.assertEqual(len(waiting_arena.rejected_players.all()), 1)

        # Assert Response
        CORRECT_TIERS = [{'id': self.tier1.discord_id, 'channel': self.tier1.channel_id}, {'id': self.tier2.discord_id, 'channel': self.tier2.channel_id}]
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(result['player_accepted'])
        self.assertEqual(result['player_id'], self.tropped.discord_id)
        
        for arena in result['arenas']:
            self.assertEqual(arena['mode'], 'FRIENDLIES')
            self.assertEqual(arena['searching_player'], self.razen.discord_id)
            self.assertEqual(arena['tiers'], CORRECT_TIERS)

    def test_rejected_reverse(self):
        client = APIClient()
        self.test_matched()

        # Before rejecting
        arena = Arena.objects.filter(status="CONFIRMATION").first()
        waiting_arena = Arena.objects.filter(created_by=self.razen).first()

        self.assertEqual(arena.mode, "FRIENDLIES")
        self.assertEqual(waiting_arena.mode, "FRIENDLIES")

        self.assertEqual(arena.created_by, self.tropped)        
        self.assertEqual(waiting_arena.status, "WAITING")

        
        arena_tropped = arena.arenaplayer_set.filter(player=self.tropped).get()
        arena_razen = arena.arenaplayer_set.filter(player=self.razen).get()
        
        self.assertEqual(arena_tropped.status, "CONFIRMATION")
        self.assertEqual(arena_razen.status, "CONFIRMATION")

        waiting_players = Arena.objects.filter(created_by=self.razen).first().arenaplayer_set.all()
        self.assertEqual(len(waiting_players), 1)
                
        # After one rejects
        body = {'accepted': False, 'timeout': False}
        response = client.patch(f'/players/{self.razen.discord_id}/confirmation/', body, format='json')
        result = json.loads(response.content)

        self.assertIsNone(Arena.objects.filter(id=waiting_arena.id).first()) # Arena Deleted

        waiting_arena = Arena.objects.filter(created_by=self.tropped).first()
        self.assertEqual(waiting_arena.status, "SEARCHING")

        waiting_players = waiting_arena.arenaplayer_set.all()
        self.assertEqual(len(waiting_players), 1)
        self.assertEqual(waiting_players[0].status, "WAITING")

        #  Rejected_players
        self.assertIn(self.razen, waiting_arena.rejected_players.all())
        self.assertEqual(len(waiting_arena.rejected_players.all()), 1)

        # Assert Response
        CORRECT_TIERS = [{'id': self.tier2.discord_id, 'channel': self.tier2.channel_id}, {'id': self.tier3.discord_id, 'channel': self.tier3.channel_id}]
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(result['player_accepted'])
        self.assertEqual(result['player_id'], self.razen.discord_id)
        
        for arena in result['arenas']:
            self.assertEqual(arena['mode'], "FRIENDLIES")
            self.assertEqual(arena['searching_player'], self.tropped.discord_id)
            self.assertEqual(arena['tiers'], CORRECT_TIERS)


    # **************************************
    #           R  A  N  K  E  D
    # **************************************
    def test_ranked_matched(self):    
        client = APIClient()

        body_tropped = {            
            'guild' : self.guild.discord_id,
            'created_by' : self.tropped.discord_id, # Tropped
            'roles' : [self.tier2.discord_id], # Tier 2
            'mode' : 'RANKED'
        }

        body_razenokis = {
            'guild' : self.guild.discord_id,
            'created_by' : self.razen.discord_id, # Razen            
            'roles' : [self.tier1.discord_id], # Tier 1
            'mode' : 'RANKED'
        }
        
        search_response = client.post('/arenas/ranked/', body_tropped, format='json')        
        match_response = client.post('/arenas/ranked/', body_razenokis, format='json')        
        result = json.loads(match_response.content)

        self.assertEqual(match_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(result.get('match_found'))

        self.assertEqual(result.get('player_one'), self.tropped.discord_id)
        self.assertEqual(result.get('player_two'), self.razen.discord_id)

    def test_ranked_search(self):
        client = APIClient()

        body = {            
            'guild' : self.guild.discord_id,
            'created_by' : self.tropped.discord_id,            
            'roles' : [self.tier2.discord_id], # Tier 2
            'mode' : 'RANKED'
        }
        
        response = client.post('/arenas/ranked/', body, format='json')

        result = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)        

    def test_ranked_already_searching(self):
        self.test_ranked_search()
        client = APIClient()
        
        body = {
            'guild' : self.guild.discord_id,
            'created_by' : self.tropped.discord_id,            
            'roles' : [self.tier2.discord_id],  # Tier 2
            'mode' : 'RANKED'
        }

        response = client.post('/arenas/ranked/', body, format='json')
        result = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(result.get('cant_join'), "ALREADY_SEARCHING")

    def test_ranked_accepted(self):
        client = APIClient()
        self.test_ranked_matched()

        # Before accepting
        arena = Arena.objects.filter(status="CONFIRMATION").first()        

        arena_tropped = arena.arenaplayer_set.filter(player=self.tropped).get()
        arena_razen = arena.arenaplayer_set.filter(player=self.razen).get()
        
        self.assertEqual(arena_tropped.status, "CONFIRMATION")
        self.assertEqual(arena_razen.status, "CONFIRMATION")
        
        body = {'accepted': True}
        
        # After one accepts
        response = client.patch(f'/players/{self.tropped.discord_id}/confirmation/', body, format='json')
        result = json.loads(response.content)
                
        arena_tropped = arena.arenaplayer_set.filter(player=self.tropped).get()        
        self.assertTrue(result['player_accepted'])        
        self.assertEqual(arena_tropped.status, "ACCEPTED")
        self.assertFalse(result['all_accepted'])

        obsolete_arena = Arena.objects.filter(status="WAITING").first()
        self.assertIsNotNone(obsolete_arena)
        self.assertEqual(len(ArenaPlayer.objects.all()), 3)

        # After the other accepts
        response = client.patch(f'/players/{self.razen.discord_id}/confirmation/', body, format='json')
        result = json.loads(response.content)

        arena_razen = arena.arenaplayer_set.filter(player=self.razen).get()
        arena_tropped = arena.arenaplayer_set.filter(player=self.tropped).get()
        
        self.assertTrue(result['player_accepted'])
        self.assertEqual(arena_razen.status, "PLAYING")
        self.assertEqual(arena_tropped.status, "PLAYING")
        self.assertTrue(result['all_accepted'])

        arena = Arena.objects.get(created_by=self.tropped)
        self.assertEqual(arena.status, "PLAYING")

        self.assertIsNotNone(arena.game_set)

        obsolete_arena = Arena.objects.filter(status="WAITING").first()
        self.assertIsNone(obsolete_arena)
        self.assertEqual(len(ArenaPlayer.objects.all()), 2)

    def test_ranked_and_friendlies_search(self):
        self.test_ranked_search()
        self.test_friendlies_search()

        tropped_arenas = Arena.objects.filter(created_by=self.tropped).all()

        self.assertEqual(len(tropped_arenas), 2)
        for arena in tropped_arenas:
            self.assertEqual(arena.status, "SEARCHING")    

class MessageTestCase(TestCase):
    def setUp(self):
        # Setup Players
        # self.tropped = make_player(discord_id=12345678987654)
        # self.razen = make_player(discord_id=45678987654321)
        
        # Setup Tiers        

        # self.tier1 = make_tier(discord_id=45678987654, name="Tier 1", channel_id=94939382, weight=4)
        # self.tier2 = make_tier(discord_id=54678987654, name="Tier 2", channel_id=9393938, weight=3)
        # self.tier3 = make_tier(discord_id=54678987655, name="Tier 3", channel_id=4848484, weight=2)
        # self.tier4 = make_tier(discord_id=54678987656, name="Tier 4", channel_id=1231566, weight=1)

        # Setup 1 Arena
        arena_test_case = ArenaTestCase()
        arena_test_case.setUp()
        arena_test_case.test_matched()

        self.arena = Arena.objects.first()        

        self.tier1 = Tier.objects.get(discord_id=45678987654)
        self.tier2 = Tier.objects.get(discord_id=54678987654)
        self.tier3 = Tier.objects.get(discord_id=54678987655)
        self.tier4 = Tier.objects.get(discord_id=54678987656)

        # Setup Messages
        self.message1 = {'id': 17414131341, 'tier': self.tier3.discord_id, 'arena': self.arena.id}
        self.message2 = {'id': 81548391843, 'tier': self.tier2.discord_id, 'arena': self.arena.id}
        self.message3 = {'id': 58348334186, 'tier': self.tier1.discord_id, 'arena': self.arena.id}
    
    def test_create(self):
        client = APIClient()
    
        # BULK  
        body = {'messages' : [self.message1, self.message2] }

        response = client.post(f'/messages/', body, format='json')
        result = json.loads(response.content)        
                
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(result), 2)

        # SIMPLE
        response = client.post(f'/messages/', self.message3, format='json')
        result = json.loads(response.content)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        self.assertEqual(result['id'], self.message3['id'])
        self.assertEqual(result['tier'], self.message3['tier'])
        self.assertEqual(result['arena'], self.message3['arena'])

        self.assertEqual(len(Message.objects.all()), 3)

    def test_destroy(self):
        client = APIClient()
        self.test_create()        
        
        # Single
        response = client.delete(f"/messages/{self.message3['id']}/")
        result = json.loads(response.content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.assertEqual(result['id'], self.message3['id'])
        self.assertEqual(result['tier'], self.message3['tier'])
        self.assertEqual(result['arena'], self.message3['arena'])

        self.assertFalse(Message.objects.filter(id=self.message3['id']).exists())