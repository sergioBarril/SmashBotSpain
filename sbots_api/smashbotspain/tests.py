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
        self.assertEqual(result['status'], 'WAITING')
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