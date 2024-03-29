from rest_framework import serializers
from rest_framework.fields import ReadOnlyField
from smashbotspain.models import Player, Arena, Rating, Stage, Tier, ArenaPlayer, Message, Guild, Character, Main, Region, Game, GameSet, GamePlayer

from smashbotspain.aux_methods.text import list_with_and

class PlayerSerializer(serializers.ModelSerializer):
    regions = serializers.StringRelatedField(many=True, required=False)
    tiers = serializers.SlugRelatedField(slug_field="discord_id", many=True, queryset=Tier.objects.all(), required=False)
    characters = serializers.StringRelatedField(many=True, required=False)

    class Meta:
        model = Player
        fields = ('discord_id', 'characters', 'regions', 'tiers', 'url')
        depth = 1
        lookup_field = 'discord_id'
        extra_kwargs = {'url': {'lookup_field': 'discord_id'}}
    
    def create(self, validated_data):                
        new_player = Player.objects.create(**validated_data)        
        tier = Tier.objects.get(discord_id=self.context['tier'])
        new_player.tiers.add(tier)
        new_player.save()

        return new_player

class RegionSerializer(serializers.ModelSerializer):
    guild = serializers.SlugRelatedField(slug_field="discord_id", queryset=Guild.objects.all())    

    class Meta:
        model = Region
        fields = "__all__"



class CharacterSerializer(serializers.ModelSerializer):
    guild = serializers.SlugRelatedField(slug_field="discord_id", queryset=Guild.objects.all())    

    class Meta:
        model = Character
        fields = '__all__'

class MainSerializer(serializers.ModelSerializer):
    player = serializers.SlugRelatedField(slug_field="discord_id", many=False, queryset=Player.objects.all())
    character = serializers.SlugRelatedField(slug_field="discord_id", many=False, queryset=Character.objects.all())

    def validate(self, data):
        player = data['player']
        status = data['status']
        guild = self.context['guild']
        
        if status not in ('MAIN', 'SECOND', 'POCKET'):
            raise serializers.ValidationError(f"Status inválido")
        
        mains =  Main.objects.filter(status=status, player=player, character__guild=guild).all()
        count = len(mains)
        
        if status == "MAIN" and count >= 2:
            self.context['mains'] = [main.character.discord_id for main in mains]            
            raise serializers.ValidationError(f"Ya tienes {count} mains. ¡Pon a alguno en seconds o pocket!")

        return data
    
    class Meta:
        model = Main
        fields = ('id', 'player', 'character', 'status')

class GameSetSerializer(serializers.ModelSerializer):
    guild = serializers.PrimaryKeyRelatedField(queryset=Guild.objects.all(), many=False)
    players = serializers.PrimaryKeyRelatedField(queryset=Player.objects.all(), many=True)

    win_condition = serializers.CharField(default="BO5")
    winner = serializers.PrimaryKeyRelatedField(queryset=Player.objects.all(), many=False, required=False)

    arena = serializers.PrimaryKeyRelatedField(queryset=Arena.objects.all(), many=False, required=False)

    class Meta:
        model = GameSet
        fields = '__all__'

class GameSerializer(serializers.ModelSerializer):
    players = serializers.PrimaryKeyRelatedField(queryset=Player.objects.all(), many=True)
    guild = serializers.PrimaryKeyRelatedField(queryset=Guild.objects.all(), many=False)
    
    game_set = serializers.PrimaryKeyRelatedField(queryset=GameSet.objects.all(), required=True, many=False)
    stage = serializers.SlugRelatedField(slug_field='name', queryset=Game.objects.all())
    
    winner = serializers.PrimaryKeyRelatedField(queryset=Player.objects.all(), required=False, many=False)
    winner_character = serializers.CharField(required=False)

    class Meta:
        model = Game
        fields = '__all__'

class GamePlayerSerializer(serializers.ModelSerializer):
    player = serializers.PrimaryKeyRelatedField(queryset=Player.objects.all(), required=True)
    game = serializers.PrimaryKeyRelatedField(queryset=Game.objects.all(), required=True)
    
    character = serializers.CharField(required=False)
    winner = serializers.BooleanField(required=False)

    class Meta:
        model = GamePlayer
        fields = '__all__'


class TierSerializer(serializers.ModelSerializer):
    guild = serializers.SlugRelatedField(slug_field="discord_id", queryset=Guild.objects.all())
    class Meta:
        model = Tier
        fields = ('discord_id', 'weight', 'channel_id', 'guild')
        lookup_field = 'discord_id'
        extra_kwargs = {'url': {'lookup_field': 'discord_id'}}

class MessageSerializer(serializers.ModelSerializer):    
    tier = serializers.SlugRelatedField(slug_field="discord_id", queryset=Tier.objects.all(), required=False)
    
    def create(self, validated_data):                
        message = Message.objects.create(**validated_data)
        if message.tier is not None:
            message.channel_id = message.tier.channel_id
            message.save()
        return message
    
    class Meta:
        model = Message
        fields = '__all__'


class ArenaSerializer(serializers.ModelSerializer):    
    guild = serializers.SlugRelatedField(slug_field="discord_id", queryset=Guild.objects.all())
    created_by = serializers.SlugRelatedField(slug_field="discord_id", queryset=Player.objects.all())
    
    mode = serializers.CharField(required=True)
    status = serializers.CharField(required=False)
    
    # Friendlies
    max_tier = serializers.SlugRelatedField(slug_field="discord_id", queryset=Tier.objects.all(), required=False)
    min_tier = serializers.SlugRelatedField(slug_field="discord_id", queryset=Tier.objects.all(), required=False)

    # Ranked
    tier = serializers.SlugRelatedField(slug_field='discord_id', queryset=Tier.objects.all(), required=False)

    players = serializers.SlugRelatedField(slug_field="discord_id", many=True, required=False, read_only=True)

    message_set = MessageSerializer(required=False, many=True, read_only=True)
    
    def create(self, validated_data):
        new_arena = Arena.objects.create(**validated_data)        
        arena_player = {
            'player': validated_data['created_by'].discord_id,
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
            self.context['player_tier'] = max_tier.discord_id
            self.context['wanted_tier'] = min_tier.discord_id
            raise serializers.ValidationError("HIGHER_TIER")            
        return data

    class Meta:
        model = Arena
        fields = ('id', 'status', 'max_tier', 'min_tier', 'tier', 'mode', 'guild', 'created_by', 'players', 'channel_id', 'message_set')
        depth = 2

class ArenaPlayerSerializer(serializers.ModelSerializer):
    arena = serializers.PrimaryKeyRelatedField(queryset=Arena.objects.all())
    player = serializers.SlugRelatedField(slug_field="discord_id", queryset=Player.objects.all())
    
    class Meta:
        model = ArenaPlayer
        fields = ('arena', 'player', 'status')

class GuildSerializer(serializers.ModelSerializer):    
    class Meta:
        model = Guild
        fields = '__all__'
        lookup_field = 'discord_id'
        extra_kwargs = {'url': {'lookup_field': 'discord_id'}}

class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stage
        fields = '__all__'

class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = '__all__'