from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from smashbotspain.models import Player, Arena, Region, Tier, ArenaPlayer
from smashbotspain.serializers import PlayerSerializer, ArenaSerializer, TierSerializer, ArenaPlayerSerializer

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

class TierViewSet(viewsets.ModelViewSet):
    queryset = Tier.objects.all()
    serializer_class = TierSerializer

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
        roles = request.data['roles']      

        # Get player tier
        tier_roles = Tier.objects.filter(pk__in=roles)
        player_tier = max(tier_roles, key=lambda role : role.weight)

        # Get or create player
        player_id = request.data['created_by']
        try:
            player = Player.objects.get(pk=player_id)
        except Player.DoesNotExist:
            player_data = {
                'id' : player_id,
                'tier' : max_tier
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
        max_tier = player_tier
        min_tier = Tier.objects.filter(channel_id=request.data['min_tier']).first()
        
        data = request.data.copy()
        data['min_tier'] = min_tier.id
        data['max_tier'] = max_tier.id
        
        arenas = Arena.search(min_tier, max_tier)

        if arenas: # Join existing arena
            arena = arenas.first()
            arena.status = "CONFIRMATION"
            arena.add_player(player, "CONFIRMATION")
            
            arena.save()
            serializer = ArenaSerializer(arena)
        
        else: # Create new arena
            serializer = ArenaSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                arena = serializer.data
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.data, status=status.HTTP_201_CREATED)