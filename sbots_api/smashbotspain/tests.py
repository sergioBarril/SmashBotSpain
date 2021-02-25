# Django
from django.test import TestCase

# Python
import json

# Django Rest Framework
from rest_framework.test import APIClient
from rest_framework import status

# Models
from smashbotspain.models import Arena, Player, ArenaPlayer, Tier

def make_player(id, name, tier=None):
    player = Player(
        id = id,
        name = name,
        tier = tier
    )
    player.save()
    
    return player

def make_tier(id, name, channel_id, weight):
    tier = Tier(
        id=id,
        name = name,
        channel_id = channel_id,
        weight = weight
    )
    tier.save()
    return tier

class ArenaTestCase(TestCase):    
    def setUp(self):
        # Setup Players
        self.tropped = make_player(id=12345678987654, name="Tropped")
        self.razen = make_player(id=45678987654321, name="Razenokis")        
        
        # Setup Tiers
        self.tier1 = make_tier(id=45678987654, name="Tier 1", channel_id=94939382, weight=4)
        self.tier2 = make_tier(id=54678987654, name="Tier 2", channel_id=9393938, weight=3)
        self.tier3 = make_tier(id=54678987655, name="Tier 3", channel_id=4848484, weight=2)
        self.tier4 = make_tier(id=54678987656, name="Tier 4", channel_id=1231566, weight=1)

    def test_friendlies_search(self):
        client = APIClient()

        body = {            
            'created_by' : self.tropped.id,
            'player_name' : self.tropped.name,
            'min_tier' : self.tier3.channel_id,  # Tier 3 channel
            'max_players' : 2,
            'num_players' : 1,
            'roles' : [self.tier2.id] # Tier 2
        }
        
        response = client.post('/arenas/', body, format='json')

        result = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', result)       
        self.assertEqual(result['status'], 'SEARCHING')
        self.assertEqual(result['max_tier'], self.tier2.id)  # Tier 2
        self.assertEqual(result['min_tier'], self.tier3.id)  # Tier 3
    
    def test_already_searching(self):
        self.test_friendlies_search()
        client = APIClient()

        body = {
            'created_by' : self.tropped.id,
            'player_name' : self.tropped.name,
            'min_tier' : self.tier3.channel_id,  # Tier 3 channel
            'max_players' : 2,
            'num_players' : 1,
            'roles' : [self.tier2.id] # Tier 2
        }

        response = client.post('/arenas/', body, format='json')
        result = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(result.get('cant_join'), "ALREADY_SEARCHING")

    def test_friendlies_tier_too_high(self):
        client = APIClient()

        body = {            
            'created_by' : self.tropped.id,  # Tropped
            'player_name' : self.tropped.name,
            'min_tier' : self.tier1.channel_id,  # Tier 1 channel
            'max_players' : 2,
            'num_players' : 1,
            'roles' : [self.tier2.id] # Tier 2
        }

        response = client.post('/arenas/', body, format='json')

        result = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_matched(self):
        client = APIClient()

        body_tropped = {            
            'created_by' : self.tropped.id, # Tropped
            'player_name' : self.tropped.name,
            'min_tier' : self.tier3.channel_id,  # Tier 3 channel
            'max_players' : 2,
            'num_players' : 1,
            'roles' : [self.tier2.id] # Tier 2
        }

        body_razenokis = {            
            'created_by' : self.razen.id, # Razen
            'player_name' : self.razen.name,
            'min_tier' : self.tier2.channel_id,  # Tier 2 channel
            'max_players' : 2,
            'num_players' : 1,
            'roles' : [self.tier1.id] # Tier 1            
        }
        
        search_response = client.post('/arenas/', body_tropped, format='json')
        match_response = client.post('/arenas/', body_razenokis, format='json')
        result = json.loads(match_response.content)

        self.assertEqual(match_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(result.get('match_found'))

        self.assertEqual(result.get('player_one'), self.tropped.id)
        self.assertEqual(result.get('player_two'), self.razen.id)

    def test_force_tier(self):
        client = APIClient()

        body = {            
            'created_by' : self.tropped.id, # Tropped
            'player_name' : self.tropped.name,
            'min_tier' : self.tier3.channel_id,  # Tier 3 channel
            'max_players' : 2,
            'num_players' : 1,
            'roles' : [self.tier2.id], # Tier 2
            'force_tier': True
        }

        # Create        
        response = client.post('/arenas/', body, format='json')
        result = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(result.get('added_tiers'), [{'id': self.tier3.id, 'channel': self.tier3.channel_id}])
        self.assertEqual(result.get('removed_tiers'), [])
        
        # Update search
        body['min_tier'] = self.tier4.channel_id
        
        response = client.post('/arenas/', body, format='json')
        result = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(result.get('added_tiers'), [{'id': self.tier4.id, 'channel': self.tier4.channel_id}])
        self.assertEqual(result.get('removed_tiers'), [{'id': self.tier3.id, 'channel': self.tier3.channel_id}])

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
        response = client.patch(f'/players/{self.tropped.id}/confirmation/', body, format='json')
        result = json.loads(response.content)
                
        arena_tropped = arena.arenaplayer_set.filter(player=self.tropped).get()        
        self.assertTrue(result['player_accepted'])        
        self.assertEqual(arena_tropped.status, "ACCEPTED")
        self.assertFalse(result['all_accepted'])

        obsolete_arena = Arena.objects.filter(status="WAITING").first()
        self.assertIsNotNone(obsolete_arena)
        self.assertEqual(len(ArenaPlayer.objects.all()), 3)

        # After the other accepts
        response = client.patch(f'/players/{self.razen.id}/confirmation/', body, format='json')
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
        response = client.patch(f'/players/{self.tropped.id}/confirmation/', body, format='json')
        result = json.loads(response.content)

        self.assertIsNone(Arena.objects.filter(id=arena.id).first()) # Arena Deleted

        waiting_arena = Arena.objects.filter(created_by=self.razen).first()
        self.assertEqual(waiting_arena.status, "SEARCHING")

        waiting_players = waiting_arena.arenaplayer_set.all()
        self.assertEqual(len(waiting_players), 1)
        self.assertEqual(waiting_players[0].status, "WAITING")

        # Assert Response
        CORRECT_TIERS = [{'id': self.tier1.id, 'channel': self.tier1.channel_id}, {'id': self.tier2.id, 'channel': self.tier2.channel_id}]
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(result['player_accepted'])
        self.assertEqual(result['player_id'], self.tropped.id)
        self.assertEqual(result['searching_player'], self.razen.id)
        self.assertEqual(result['tiers'], CORRECT_TIERS)

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
        response = client.patch(f'/players/{self.tropped.id}/confirmation/', body, format='json')
        result = json.loads(response.content)

        self.assertIsNone(Arena.objects.filter(id=arena.id).first()) # Arena Deleted

        waiting_arena = Arena.objects.filter(created_by=self.razen).first()
        self.assertEqual(waiting_arena.status, "SEARCHING")

        waiting_players = waiting_arena.arenaplayer_set.all()
        self.assertEqual(len(waiting_players), 1)
        self.assertEqual(waiting_players[0].status, "WAITING")

        #  Rejected_players
        self.assertIn(self.tropped, waiting_arena.rejected_players.all())

        # Assert Response
        CORRECT_TIERS = [{'id': self.tier1.id, 'channel': self.tier1.channel_id}, {'id': self.tier2.id, 'channel': self.tier2.channel_id}]
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(result['player_accepted'])
        self.assertEqual(result['player_id'], self.tropped.id)
        self.assertEqual(result['searching_player'], self.razen.id)
        self.assertEqual(result['tiers'], CORRECT_TIERS)