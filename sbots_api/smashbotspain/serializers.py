from rest_framework import serializers
from smashbotspain.models import Player, Arena, Tier, ArenaPlayer, Message, Guild, Character, CharacterRole, Main, Region, RegionRole

from smashbotspain.aux_methods.text import list_with_and

class PlayerSerializer(serializers.ModelSerializer):
    regions = serializers.StringRelatedField(many=True, required=False)
    tiers = serializers.SlugRelatedField(slug_field="discord_id", many=True, queryset=Tier.objects.all(), required=False)
    character_roles = serializers.StringRelatedField(many=True, required=False)
    name = serializers.CharField(required=False)

    class Meta:
        model = Player
        fields = ('id', 'name', 'character_roles', 'regions', 'tiers', 'tier')
        depth = 1
    
    def create(self, validated_data):                
        new_player = Player.objects.create(**validated_data)        
        tier = Tier.objects.get(discord_id=self.context['tier'])
        new_player.tiers.add(tier)
        new_player.save()

        return new_player

class RegionRoleSerializer(serializers.ModelSerializer):
    guild = serializers.PrimaryKeyRelatedField(many=False, queryset=Guild.objects.all())
    player = serializers.PrimaryKeyRelatedField(many=False, queryset=Player.objects.all())
    region = serializers.PrimaryKeyRelatedField(many=False, queryset=Region.objects.all())

    class Meta:
        model = RegionRole
        fields = "__all__"

class RegionSerializer(serializers.ModelSerializer):    
    class Meta:
        model = Region
        fields = "__all__"

class CharacterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Character
        fields = '__all__'

class CharacterRoleSerializer(serializers.ModelSerializer):
    guild = serializers.PrimaryKeyRelatedField(many=False, queryset=Guild.objects.all())
    player = serializers.PrimaryKeyRelatedField(many=False, queryset=Player.objects.all())
    character = serializers.PrimaryKeyRelatedField(many=False, queryset=Character.objects.all())

    class Meta:
        model = CharacterRole
        fields = '__all__'

class MainSerializer(serializers.ModelSerializer):
    player = serializers.PrimaryKeyRelatedField(many=False, queryset=Player.objects.all())
    character_role = serializers.PrimaryKeyRelatedField(many=False, queryset=CharacterRole.objects.all())

    def validate(self, data):
        player = data['player']        
        status = data['status']
        guild = self.context['guild']
        
        if status not in ('MAIN', 'SECOND', 'POCKET'):
            raise serializers.ValidationError(f"Status inválido")
        
        mains =  Main.objects.filter(status=status, player=player, character_role__guild=guild).all()
        count = len(mains)
        
        if status == "MAIN" and count >= 2:
            self.context['mains'] = [main.character_role.character.name for main in mains]            
            raise serializers.ValidationError(f"Ya tienes {count} mains. ¡Pon a alguno en seconds o pocket!")

        return data
    
    class Meta:
        model = Main
        fields = ('id', 'player', 'character_role', 'status')



class ArenaSerializer(serializers.ModelSerializer):    
    guild = serializers.PrimaryKeyRelatedField(queryset=Guild.objects.all())
    created_by = serializers.PrimaryKeyRelatedField(queryset=Player.objects.all())    
    max_tier = serializers.SlugRelatedField(slug_field="discord_id", queryset=Tier.objects.all())
    min_tier = serializers.SlugRelatedField(slug_field="discord_id", queryset=Tier.objects.all())

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
        fields = ('id', 'status', 'max_tier', 'min_tier', 'mode', 'guild', 'created_by', 'max_players', 'players', 'channel_id', 'messages')

class ArenaPlayerSerializer(serializers.ModelSerializer):
    arena = serializers.PrimaryKeyRelatedField(queryset=Arena.objects.all())
    player = serializers.PrimaryKeyRelatedField(queryset=Player.objects.all())
    
    class Meta:
        model = ArenaPlayer
        fields = ('arena', 'player', 'status')

class TierSerializer(serializers.ModelSerializer):
    guild = serializers.PrimaryKeyRelatedField(queryset=Guild.objects.all())
    class Meta:
        model = Tier
        fields = ('discord_id', 'name', 'weight', 'channel_id', 'guild')

class MessageSerializer(serializers.ModelSerializer):    
    tier = serializers.SlugRelatedField(slug_field="discord_id", queryset=Tier.objects.all())
    
    class Meta:
        model = Message
        fields = ('id', 'tier', 'arena')

class GuildSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guild
        fields = '__all__'