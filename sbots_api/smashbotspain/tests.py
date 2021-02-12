# Django
from django.test import TestCase

# Python
import json

# Django Rest Framework
from rest_framework.test import APIClient
from rest_framework import status

# Models
from smashbotspain.models import Arena, Player, ArenaPlayer, Tier


class ArenaTestCase(TestCase):

    def setUp(self):
        # Setup Players
        player1 = Player(
            id=12345678987654,
            name="Tropped",
        )
        player2 = Player(
            id=45678987654321,
            name="Razenokis"
        )
        player1.save()
        player2.save()

        # Setup Tiers
        tier1 = Tier(
            id=45678987654,
            name="Tier 1",
            channel_id=94939382,
            weight=4
        )
        tier2 = Tier(
            id=54678987654,
            name="Tier 2",
            channel_id=9393938,
            weight=3
        )
        tier3 = Tier(
            id=54678987655,
            name="Tier 3",
            channel_id=4848484,
            weight=2
        )
        
        tier1.save()
        tier2.save()
        tier3.save()


    def test_friendlies_search(self):
        client = APIClient()

        body = {
            'status' : 'WAITING',
            'created_by' : 12345678987654,
            'min_tier' : 4848484,  # Tier 3 channel
            'max_players' : 2,
            'num_players' : 1,
            'roles' : [54678987654] # Tier 2
        }
        
        response = client.post(
            '/arenas/', 
            body,
            format='json'
        )

        result = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', result)       
        self.assertEqual(result['status'], 'WAITING')
        self.assertEqual(result['max_tier'], 54678987654)  # Tier 2
        self.assertEqual(result['min_tier'], 54678987655)  # Tier 3
    
    def test_friendlies_tier_too_high(self):
        client = APIClient()

        body = {
            'status' : 'WAITING',
            'created_by' : 12345678987654,  # Tropped
            'min_tier' : 94939382,  # Tier 1 channel
            'max_players' : 2,
            'num_players' : 1,
            'roles' : [54678987654] # Tier 2
        }

        response = client.post(
            '/arenas/', 
            body,
            format='json'
        )

        result = json.loads(response.content)        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # def test_update_education(self):

    #     client = APIClient()
    #     client.credentials(HTTP_AUTHORIZATION='Token ' + self.access_token)

    #     # Creamos un objeto en la base de datos para trabajar con datos
    #     edu = Education.objects.create(
    #         date_ini='2010-09-01T19:41:21Z',
    #         date_end='2012-09-01T19:41:21Z',
    #         title='DAM',
    #         user=self.user
    #     )

    #     test_education_update = {
    #         'date_ini': '2010-09-02T19:41:21Z',
    #         'date_end': '2012-09-02T19:41:21Z',
    #         'title': 'DAA',
    #     }

    #     response = client.put(
    #         f'/education/{edu.pk}/', 
    #         test_education_update,
    #         format='json'
    #     )

    #     result = json.loads(response.content)
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)

    #     if 'pk' in result:
    #         del result['pk']

    #     self.assertEqual(result, test_education_update)

    
    # def test_delete_education(self):

    #     client = APIClient()
    #     client.credentials(HTTP_AUTHORIZATION='Token ' + self.access_token)

    #     # Creamos un objeto en la base de datos para trabajar con datos
    #     edu = Education.objects.create(
    #         date_ini='2010-09-01T19:41:21Z',
    #         date_end='2012-09-01T19:41:21Z',
    #         title='DAM',
    #         user=self.user
    #     )

    #     response = client.delete(
    #         f'/education/{edu.pk}/', 
    #         format='json'
    #     )

    #     self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    #     edu_exists = Education.objects.filter(pk=edu.pk)
    #     self.assertFalse(edu_exists)


    # def test_get_education(self):

    #     client = APIClient()
    #     client.credentials(HTTP_AUTHORIZATION='Token ' + self.access_token)

    #     Education.objects.create(
    #         date_ini='2010-09-01T19:41:21Z',
    #         date_end='2012-09-01T19:41:21Z',
    #         title='DAM',
    #         user=self.user
    #     )

    #     Education.objects.create(
    #         date_ini='2008-09-01T19:41:21Z',
    #         date_end='2010-09-01T19:41:21Z',
    #         title='Bachiller',
    #         user=self.user
    #     )

    #     response = client.get('/education/')
        
    #     result = json.loads(response.content)
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)

    #     self.assertEqual(result['count'], 2)

    #     for edu in result['results']:
    #         self.assertIn('pk', edu)
    #         self.assertIn('date_ini', edu)
    #         self.assertIn('date_end', edu)
    #         self.assertIn('title', edu)
    #         break