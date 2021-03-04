from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core import validators
from functools import total_ordering


# Create your models here.

class Guild(models.Model):
    id = models.BigIntegerField(primary_key=True)
    spam_channel = models.BigIntegerField(null=True, blank=True)
    flairing_channel = models.BigIntegerField(null=True, blank=True)
    list_channel = models.BigIntegerField(null=True, blank=True)
    list_message = models.BigIntegerField(null=True, blank=True)
    
    match_timeout = models.IntegerField(default=600,
        validators=[
            validators.MinValueValidator(10)
    ])
    
    cancel_time = models.IntegerField(default=90,
        validators=[
            validators.MinValueValidator(10)
    ])

    ggs_time = models.IntegerField(default=300,
        validators=[
            validators.MinValueValidator(10)
    ])

class Region(models.Model):
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=50)
    guild = models.ForeignKey(Guild, null=True, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.name 

class Character(models.Model):
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=30)        

    def __str__(self):
        return self.name 

@total_ordering
class Tier(models.Model):
    """
    Model for tiers. More weight == better role.
    Tier 1 > Tier 3
    """
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=15)
    weight = models.IntegerField(default=0)
    channel_id = models.BigIntegerField()
    guild = models.ForeignKey(Guild, null=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.name
    
    def __lt__(self, other):
        return self.weight < other.weight
    
    def __eq__(self, other):
        if not isinstance(other, Tier):
            return False
        return self.id == other.id
    
    def between(self, min_tier, max_tier):
        return min_tier.weight <= self.weight and self.weight <= max_tier.weight

class Player(models.Model):
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=20, null=True, blank=True)
    
    characters = models.ManyToManyField(Character, through="Main")
    regions = models.ManyToManyField(Region)
    
    tier = models.ForeignKey(Tier, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.name} ({self.tier})"
    
    def status(self):
        """
        Returns the status of the player
        """
        for status in ArenaPlayer.CANT_JOIN_STATUS:
            if ArenaPlayer.objects.filter(player=self, status=status):
                return status        
        for status in ArenaPlayer.CAN_JOIN_STATUS:
            if ArenaPlayer.objects.filter(player=self, status=status):
                return status
        return False
    
    def can_join(self):
        """
        Returns False if player is already playing / confirmation step.
        True otherwise.
        """
        pass
        # return not arena_player.exists()
    
    def search(self, min_tier, max_tier, guild):
        arenas = Arena.objects.filter(guild=guild)
        arenas = arenas.filter(min_tier__weight__lte = max_tier.weight)
        arenas = arenas.filter(max_tier__weight__gte = min_tier.weight)
        arenas = arenas.filter(status="SEARCHING")
        arenas = arenas.exclude(created_by=self)
        arenas = arenas.exclude(rejected_players=self)        

        my_arena = Arena.objects.filter(created_by=self).first()
        if my_arena is not None:
            arenas = arenas.exclude(created_by__in=my_arena.rejected_players.all())
        
        return arenas

class Main(models.Model):
    MAIN_SECOND = [
        ('MAIN', 'Main'),
        ('SECOND', 'Second')
    ]

    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    character = models.ForeignKey(Character, on_delete=models.CASCADE)   
    
    main = models.CharField(max_length=10, choices=MAIN_SECOND)

class Arena(models.Model):
    STATUS = [
        ('SEARCHING', 'Searching'),
        ('WAITING', 'Waiting'),
        ('CONFIRMATION', 'Confirmation'),
        ('PLAYING', 'Playing'),
        ('CLOSED', 'Closed'),
        ('CANCELLED', 'Cancelled')
    ]
    
    MODE = [
        ("FRIENDLIES", "Friendlies"),
        ("RANKED", "Ranked")
    ]
    
    guild = models.ForeignKey(Guild, null=True, on_delete=models.CASCADE)
    created_by = models.ForeignKey(Player, null=True, related_name="created_by", on_delete=models.SET_NULL)
    status = models.CharField(max_length=12, choices=STATUS, default="SEARCHING")
    mode = models.CharField(max_length=10, choices=MODE, default="FRIENDLIES")
    
    max_tier = models.ForeignKey(Tier, null=True, related_name="max_tier", on_delete=models.SET_NULL)
    min_tier = models.ForeignKey(Tier, null=True, related_name="min_tier", on_delete=models.SET_NULL)

    max_players = models.IntegerField(validators=[validators.MinValueValidator(2)], default=2)
    channel_id = models.BigIntegerField(null=True, blank=True)

    players = models.ManyToManyField(Player, through="ArenaPlayer", blank=True)
    rejected_players = models.ManyToManyField(Player, blank=True, related_name="rejected_players")

    def __str__(self):
        return f"Arena #{self.id}"
       
    def add_player(self, player, status="WAITING"):
        ArenaPlayer.objects.create(arena=self, status=status, player=player)

    def get_tiers(self):
        """
        Returns the iterable with all the tiers between min_tier and max_tier
        """
        tiers = Tier.objects.filter(weight__gte=self.min_tier.weight)
        tiers = tiers.filter(weight__lte=self.max_tier.weight)

        return tiers.all()


    def set_status(self, status):
        """
        Sets the status of the arena, and all its ArenaPlayers
        """
        self.status = status
        self.save()

        players_status = status
        arena_players = self.arenaplayer_set.all()        
        
        if status == "CANCELLED":
            for arena_player in arena_players:
                arena_player.delete()
            return status

        if status == "CLOSED":
            players_status = "GGS"
        elif status == "SEARCHING":
            players_status = "WAITING"        
        
        for player in self.arenaplayer_set.all():
            player.status = players_status
            player.save()
        return status

class ArenaPlayer(models.Model):
    arena = models.ForeignKey(Arena, on_delete=models.CASCADE, null=True, blank=True)
    player = models.ForeignKey(Player, null=True, blank=True, on_delete=models.SET_NULL)
    
    STATUS = [
        ('WAITING', 'Waiting'),
        ('CONFIRMATION', 'Confirmation'),
        ('ACCEPTED', 'Accepted'),
        ('PLAYING', 'Playing'),
        ('GGS', 'GGs'),
        ('INVITED', 'Invited'),
    ]

    
    CANT_JOIN_STATUS = ["CONFIRMATION", "ACCEPTED", "PLAYING"]
    CAN_JOIN_STATUS = ["WAITING", "INVITED", "GG"]
    
    status = models.CharField(max_length=12, choices=STATUS)

    def set_status(self, status):
        self.status = status
        self.save()

    def __str__(self):
        return f"{self.player} in {self.arena}"

class Message(models.Model):
    id = models.BigIntegerField(primary_key=True)
    tier = models.ForeignKey(Tier, on_delete=models.CASCADE)
    arena = models.ForeignKey(Arena, on_delete=models.CASCADE)
