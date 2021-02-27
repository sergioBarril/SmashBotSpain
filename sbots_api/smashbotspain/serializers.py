from rest_framework import serializers
from smashbotspain.models import Player, Arena, Tier, ArenaPlayer, Message

class PlayerSerializer(serializers.ModelSerializer):
    regions = serializers.StringRelatedField(many=True, required=False)
    tier = serializers.PrimaryKeyRelatedField(queryset=Tier.objects.all())
    characters = serializers.StringRelatedField(required=False)
    name = serializers.CharField(required=False)

    class Meta:
        model = Player
        fields = ('id', 'name', 'characters', 'regions', 'tier')
        depth = 1

class ArenaSerializer(serializers.ModelSerializer):    
    created_by = serializers.PrimaryKeyRelatedField(queryset=Player.objects.all())    
    max_tier = serializers.PrimaryKeyRelatedField(queryset=Tier.objects.all())
    min_tier = serializers.PrimaryKeyRelatedField(queryset=Tier.objects.all())

    players = serializers.PrimaryKeyRelatedField(many=True, required=False, read_only=True)

    messages = serializers.PrimaryKeyRelatedField(queryset=Message.objects.all(), required=False)
    
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
        max_tier = data.get('max_tier')
        min_tier = data.get('min_tier')

        if max_tier is None or min_tier is None:
            return data
        elif max_tier < min_tier:
            raise serializers.ValidationError(f"Estás intentando unirte a {min_tier.name}, pero eres {max_tier.name}.")
        return data

    class Meta:
        model = Arena
        fields = ('id', 'status', 'max_tier', 'min_tier', 'mode', 'created_by', 'max_players', 'players', 'channel_id', 'messages')

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

class MessageSerializer(serializers.ModelSerializer):    
    class Meta:
        model = Message
        fields = ('id', 'tier', 'arena')