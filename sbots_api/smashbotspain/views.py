from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

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

    @action(detail=False)
    def playing(self, request):
        playing_arenas = Arena.objects.filter(status="PLAYING")

        page = self.paginate_queryset(playing_arenas)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(playing_arenas, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def get_last(self, request):
        arenas = self.get_queryset().last()
        serializer = self.get_serializer(arenas)
        return Response(serializer.data)
        
    def create(self, request):
        serializer = ArenaSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    