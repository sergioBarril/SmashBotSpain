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

    players = serializers.PrimaryKeyRelatedField(queryset=Player.objects.all(), many=True, required=False)
    
    class Meta:
        model = Arena
        fields = ('id', 'status', 'max_tier', 'min_tier', 'mode', 'created_by', 'max_players', 'num_players', 'players')

class ArenaPlayerSerializer(serializers.ModelSerializer):
    arena = serializers.PrimaryKeyRelatedField(queryset=Arena.objects.all())
    player = serializers.PrimaryKeyRelatedField(queryset=Player.objects.all())

    def create(self, validated_data):
        arena = validated_data.pop('arena')
        player = validated_data.pop('player')
        ArenaPlayer.objects.create(arena=arena, player=player, status='GGs')

        return
    class Meta:
        model = ArenaPlayer
        fields = ('arena', 'player', 'status')


class TierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tier
        fields = ('id', 'name', 'weight', 'channel_id')






# def validate(self, data):
#     player = data['created_by']
#     if player:
#         tier = data['tier']      
#         if not tier:
#             raise serializers.ValidationError("No tier.")
                    
#         if tier.name < player.tier.name:
#             raise serialzers.ValidationError("Te estás colando de tier")

#     return data