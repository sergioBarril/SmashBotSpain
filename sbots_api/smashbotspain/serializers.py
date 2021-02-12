from rest_framework import serializers
from smashbotspain.models import Player, Arena, Tier, ArenaPlayer

class PlayerSerializer(serializers.ModelSerializer):
    regions = serializers.StringRelatedField(many=True, required=False)
    tier = serializers.StringRelatedField()
    characters = serializers.StringRelatedField(required=False)

    class Meta:
        model = Player
        fields = ('id', 'characters', 'regions', 'tier')
        depth = 1

class ArenaSerializer(serializers.ModelSerializer):    
    created_by = serializers.PrimaryKeyRelatedField(queryset=Player.objects.all())    
    max_tier = serializers.PrimaryKeyRelatedField(queryset=Tier.objects.all())
    min_tier = serializers.PrimaryKeyRelatedField(queryset=Tier.objects.all())

    players = serializers.PrimaryKeyRelatedField(many=True, required=False, read_only=True)
    
    def create(self, validated_data):
        new_arena = Arena.objects.create(**validated_data)        
        arena_player = {
            'player': validated_data['created_by'].id,
            'arena' : new_arena.id,
            'status': "WAITING"
        }
        
        ap_serializer = ArenaPlayerSerializer(data=arena_player)
        if ap_serializer.is_valid():
            ap_serializer.save()
            return new_arena
    
    def validate(self, data):
        if data['max_tier'] < data['min_tier']:
            raise serializers.ValidationError(f"Estás intentando unirte a {data['min_tier'].name}, pero eres {data['max_tier'].name}.")
        return data

    class Meta:
        model = Arena
        fields = ('id', 'status', 'max_tier', 'min_tier', 'mode', 'created_by', 'max_players', 'num_players', 'players')

class ArenaPlayerSerializer(serializers.ModelSerializer):
    arena = serializers.PrimaryKeyRelatedField(queryset=Arena.objects.all())
    player = serializers.PrimaryKeyRelatedField(queryset=Player.objects.all())
    
    class Meta:
        model = ArenaPlayer
        fields = ('arena', 'player', 'status')

class TierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tier
        fields = ('id', 'name', 'weight', 'channel_id')