from django.db import models
from django.core import validators

# Create your models here.

class Region(models.Model):
    name = models.CharField(max_length=50)

class Character(models.Model):
    name = models.CharField(max_length=30)

class Tier(models.Model):
    name = models.CharField(max_length=15)

class Player(models.Model):
    discord_id = models.BigIntegerField(primary_key=True)
    
    characters = models.ManyToManyField(Character, through="Main")
    regions = models.ManyToManyField(Region)
    
    tier = models.ForeignKey(Tier, null=True, on_delete=models.SET_NULL)

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
        ('CONFIRM', 'Confirmation'),
        ('PLAYING', 'Playing'),
        ('CLOSED', 'Closed'),
    ]
    
    created_by = models.ForeignKey(Player, null=True, related_name="created_by", on_delete=models.SET_NULL)
    status = models.CharField(max_length=7, choices=STATUS)
    tier = models.ForeignKey(Tier, null=True, on_delete=models.SET_NULL)
    
    max_players = models.IntegerField(validators=[validators.MinValueValidator(2)])
    num_players = models.IntegerField()

    players = models.ManyToManyField(Player, through="ArenaPlayer")

class ArenaPlayer(models.Model):
    arena = models.ForeignKey(Arena, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, null=True, on_delete=models.SET_NULL)
    
    STATUS = [
        ('WAITING', 'Waiting'),
        ('PLAYING', 'Playing'),        
        ('GGS', 'GGs'),
        ('INVITED', 'Invited'),
    ]
    
    status = models.CharField(max_length=7)