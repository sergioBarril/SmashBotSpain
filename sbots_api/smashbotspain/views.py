from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from smashbotspain.models import Player, Arena
from smashbotspain.serializers import PlayerSerializer, ArenaSerializer

# Create your views here.
class PlayerViewSet(viewsets.ModelViewSet):
    """
    This viewset automatically provides `list`, `create`, `retrieve`,
    `update` and `destroy` actions.    
    """
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer

class ArenaViewSet(viewsets.ModelViewSet):
    queryset = Arena.objects.all()
    serializer_class = ArenaSerializer