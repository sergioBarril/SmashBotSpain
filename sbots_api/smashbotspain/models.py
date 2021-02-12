from django.db import models
from django.core import validators
from functools import total_ordering


# Create your models here.

class Region(models.Model):
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=50)
    
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

    def __str__(self):
        return self.name
    
    def __lt__(self, other):
        return self.weight < other.weight
    
    def __eq__(self, other):
        return self.id == other.id

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
        ('WAITING', 'Waiting'),
        ('CONFIRMATION', 'Confirmation'),
        ('PLAYING', 'Playing'),
        ('CLOSED', 'Closed'),
    ]
    
    MODE = [
        ("FRIENDLIES", "Friendlies"),
        ("RANKED", "Ranked")
    ]
    
    created_by = models.ForeignKey(Player, null=True, related_name="created_by", on_delete=models.SET_NULL)
    status = models.CharField(max_length=12, choices=STATUS, default="WAITING")
    mode = models.CharField(max_length=10, choices=MODE, default="FRIENDLIES")
    
    max_tier = models.ForeignKey(Tier, null=True, related_name="max_tier", on_delete=models.SET_NULL)
    min_tier = models.ForeignKey(Tier, null=True, related_name="min_tier", on_delete=models.SET_NULL)

    max_players = models.IntegerField(validators=[validators.MinValueValidator(2)])
    num_players = models.IntegerField()

    players = models.ManyToManyField(Player, through="ArenaPlayer", blank=True)

    def __str__(self):
        return f"Arena #{self.id}"
    
    @staticmethod
    def search(min_tier, max_tier):        
        arenas = Arena.objects.filter(min_tier__weight__lte = max_tier.weight)
        arenas = arenas.filter(max_tier__weight__gte = min_tier.weight)
        return arenas
    
    def add_player(self, player, status):
        ArenaPlayer.objects.create(arena=self, status=status, player=player)
    
    # def set_confirmation(self):
    #     self.status = "CONFIRMATION"
    #     for player in self.players:
    #         player.status = "CONFIRMATION"

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

    def __str__(self):
        return f"{self.player} in {self.arena}"