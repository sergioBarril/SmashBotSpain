from rest_framework import serializers
from smashbotspain.models import Player, Arena, Tier

class PlayerSerializer(serializers.ModelSerializer):
    regions = serializers.StringRelatedField(many=True)
    tier = serializers.StringRelatedField()

    class Meta:
        model = Player
        fields = ('id', 'characters', 'regions', 'tier')
        depth = 1

class ArenaSerializer(serializers.ModelSerializer):    
    created_by = serializers.PrimaryKeyRelatedField(queryset=Player.objects.all())    
    tier = serializers.PrimaryKeyRelatedField(queryset=Tier.objects.all())

    players = serializers.PrimaryKeyRelatedField(queryset=Player.objects.all(), many=True)

    class Meta:
        model = Arena
        fields = ('id', 'status', 'tier', 'created_by', 'max_players', 'num_players', 'players')

class TierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tier
        fields = ('name',)