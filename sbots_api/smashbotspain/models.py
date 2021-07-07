from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core import validators
from functools import total_ordering
from collections import defaultdict


# Create your models here.

class Guild(models.Model):
    discord_id = models.BigIntegerField()
    spam_channel = models.BigIntegerField(null=True, blank=True)
    flairing_channel = models.BigIntegerField(null=True, blank=True)
    list_channel = models.BigIntegerField(null=True, blank=True)
    list_message = models.BigIntegerField(null=True, blank=True)
    ranked_channel = models.BigIntegerField(null=True, blank=True)
    ranked_message = models.BigIntegerField(null=True, blank=True)
    
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

    role_message_time = models.IntegerField(default=25,
        validators=[
            validators.MinValueValidator(5)
    ])

    class Meta:
        unique_together = ['discord_id']

class Region(models.Model):
    discord_id = models.BigIntegerField()
    guild = models.ForeignKey(Guild, null=True, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ['discord_id']

class Character(models.Model):
    discord_id = models.BigIntegerField()
    guild = models.ForeignKey(Guild, null=True, on_delete=models.CASCADE)

    def __str__(self):
        return f"Character ({self.discord_id})"
    
    class Meta:
        unique_together = ['discord_id']

    
@total_ordering
class Tier(models.Model):
    """
    Model for tiers. More weight == better role.
    Tier 1 > Tier 3
    """
    discord_id = models.BigIntegerField()    
    weight = models.IntegerField(default=0)
    channel_id = models.BigIntegerField(null=True)
    guild = models.ForeignKey(Guild, null=True, on_delete=models.CASCADE)

    def __str__(self):
        return f"Tier {self.discord_id} (Weight: {self.weight})"
    
    def __lt__(self, other):
        return self.weight < other.weight
    
    def __eq__(self, other):
        if not isinstance(other, Tier):
            return False
        return self.discord_id == other.discord_id
    
    def between(self, min_tier, max_tier):
        return min_tier.weight <= self.weight and self.weight <= max_tier.weight

class Player(models.Model):
    discord_id = models.BigIntegerField()
    
    characters = models.ManyToManyField(Character, through="Main", blank=True)
    regions = models.ManyToManyField(Region, blank=True)     
    tiers = models.ManyToManyField(Tier, blank=True)

    class Meta:
        unique_together = ['discord_id']

    def __str__(self):
        return f"Player ({self.discord_id})"
    
    def tier(self, guild):
        """
        Returns the tier of the player in the given guild
        """
        return self.tiers.filter(guild=guild).first()

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

    def search_ranked(self, guild):
        """
        Search compatible ranked arenas.

        TODO: Add MMR constraints
        """
        arenas = Arena.objects.filter(guild=guild)
        arenas = arenas.filter(status="SEARCHING")
        arenas = arenas.filter(mode="RANKED")
        arenas = arenas.filter(tier=self.tier(guild))
        arenas = arenas.exclude(created_by=self)

        # CHECK REJECTED
        my_arena = Arena.objects.filter(created_by=self, status="SEARCHING", mode="RANKED").first()
        if my_arena is not None:
            arenas = arenas.exclude(created_by__in=my_arena.rejected_players.all())
        return arenas

    def search(self, min_tier, max_tier, guild, invite=False):        
        arenas = Arena.objects.filter(guild=guild)        
        arenas = arenas.filter(status="SEARCHING")        
        arenas = arenas.filter(mode = "FRIENDLIES")        
        arenas = arenas.filter(min_tier__weight__lte = max_tier.weight)        

        if not invite:
            arenas = arenas.filter(max_tier__weight__gte = min_tier.weight)
            arenas = arenas.exclude(created_by=self)
        
        arenas = arenas.exclude(rejected_players=self)
        my_status = "PLAYING" if invite else "SEARCHING"
        my_arena = Arena.objects.filter(created_by=self, status=my_status).first()
        if my_arena is not None:
            arenas = arenas.exclude(created_by__in=my_arena.rejected_players.all())
        
        return arenas
    
    def confirmation(self, confirmation_arena):
        """
        A match has been found in <<confirmation_arena>>.
        Sets all other arenas of the player in waiting, and declines current invitations.
        """
        my_other_arenas = Arena.objects.filter(created_by=self).exclude(id=confirmation_arena.id).all()

        for arena in my_other_arenas:
            arena.set_status(status="WAITING")

        # REMOVE INVITATIONS
        for ap in ArenaPlayer.objects.filter(player=self, status="INVITED").all():
            ap.delete()

    def get_game(self):
        """
        Returns the current game this player is playing.
        """
        arena_player = ArenaPlayer.objects.filter(player=self, status="PLAYING").first()
        arena = arena_player.arena
        
        if arena.mode != "RANKED":
            return False
        
        game_set = arena.gameset_set.first()

        # Get current game
        game = Game.objects.filter(game_set=game_set, winner=None).first()
        
        return game
            


class Main(models.Model):
    MAIN_SECOND = [
        ('MAIN', 'Main'),
        ('SECOND', 'Second'),
        ('POCKET', 'Pocket')
    ]

    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    character = models.ForeignKey(Character, on_delete=models.CASCADE)   
    
    status = models.CharField(max_length=10, choices=MAIN_SECOND)

    def __str__(self):
        return f"{self.player} - {self.status} - {self.character}"

class Arena(models.Model):
    STATUS = [
        ('SEARCHING', 'Searching'),
        ('WAITING', 'Waiting'),
        ('CONFIRMATION', 'Confirmation'),
        ('PLAYING', 'Playing')        
    ]
    
    MODE = [
        ("FRIENDLIES", "Friendlies"),
        ("RANKED", "Ranked")
    ]
    
    guild = models.ForeignKey(Guild, null=True, on_delete=models.CASCADE)
    created_by = models.ForeignKey(Player, null=True, related_name="created_by", on_delete=models.SET_NULL)
    status = models.CharField(max_length=12, choices=STATUS, default="SEARCHING")
    mode = models.CharField(max_length=10, choices=MODE, default="FRIENDLIES")
    
    # Friendlies fields
    max_tier = models.ForeignKey(Tier, null=True, related_name="max_tier", on_delete=models.SET_NULL)
    min_tier = models.ForeignKey(Tier, null=True, related_name="min_tier", on_delete=models.SET_NULL)
    
    # Ranked field
    tier = models.ForeignKey(Tier, null=True, related_name="tier", on_delete=models.SET_NULL)

    channel_id = models.BigIntegerField(null=True, blank=True)

    players = models.ManyToManyField(Player, through="ArenaPlayer", blank=True)
    rejected_players = models.ManyToManyField(Player, blank=True, related_name="rejected_players")

    def __str__(self):
        return f"Arena #{self.id}"

    def new_set(self, win_con):
        self.game_set = GameSet(guild=self.guild, players=self.players, win_condition=win_con)
        self.game_set.save()
        return True
    
    def add_player(self, player, status="WAITING"):
        ArenaPlayer.objects.create(arena=self, status=status, player=player)

    def get_tiers(self):
        """
        Returns the iterable with all the tiers between min_tier and max_tier
        """
        tiers = Tier.objects.filter(weight__gte=self.min_tier.weight)
        tiers = tiers.filter(weight__lte=self.max_tier.weight)

        return tiers.all()

    def get_players(self):
        """
        Returns a defaultdict with the discord_id of the players by status        
        """
        arena_players = self.arenaplayer_set.all()

        players = defaultdict(list)
        
        for ap in arena_players:
            players[ap.status].append(ap.player.discord_id)
        
        return players

    def get_messages(self):
        """
        Returns the info of all messages related to this arena
        """
        messages = Message.objects.filter(arena=self).all()
        message_response = [
            {
                'id': message.id,
                'arena': message.arena.id,
                'tier': message.tier.id if message.tier else None,
                'channel_id': message.channel_id,
                'mode': message.mode
            }
            
            for message in messages
        ]
        return message_response
        


    def set_status(self, status):
        """
        Sets the status of the arena, and all its ArenaPlayers
        """
        self.status = status
        self.save()

        players_status = status
        arena_players = self.arenaplayer_set.all()        
        
        if status == "SEARCHING":
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
    CAN_JOIN_STATUS = ["INVITED", "WAITING", "GGS"]
    
    status = models.CharField(max_length=12, choices=STATUS)

    def set_status(self, status):
        self.status = status
        self.save()

    def __str__(self):
        return f"{self.player} in {self.arena}"

class GameSet(models.Model):    
    guild = models.ForeignKey(Guild, null=True, on_delete=models.CASCADE)
    players = models.ManyToManyField(Player)

    WIN_CONDITIONS = [
        ("BO3", "BO3"),
        ("BO5", "BO5"),
        ("FT5", "FT5"),
        ("FT10", "FT10"),
    ]
    
    win_condition = models.CharField(max_length=40, choices=WIN_CONDITIONS)
    winner = models.ForeignKey(Player, null=True, on_delete=models.SET_NULL, related_name="winner_set")    
    arena = models.ForeignKey(Arena, null=True, on_delete=models.SET_NULL)

    def add_game(self):

        game_number = Game.objects.filter(game_set=self).count()

        game = Game(number= game_number + 1, guild=self.guild, game_set=self)
        game.save()

        for player in self.players.all():
            game_player = GamePlayer(player=player, game=game)
            game_player.save()
    
        return game
    
    def set_winner(self):
        """
        Checks if there's already a winner. If there is, it is set, and True is returned.
        
        Returns True if there's a winner, False if no winner is set.
        """
        first_to = None
        games = self.game_set.all()
        
        # SET NUM OF WINS
        if self.win_condition == "BO3":
            first_to = 2
        elif self.win_condition == "BO5":
            first_to = 3
        elif self.win_condition == "FT5":
            first_to = 5
        elif self.win_condition == "FT10":
            first_to = 10
        else:
            return None
        
        # SET WINNER:
        for player in self.players.all():
            win_count = self.game_set.filter(winner=player).count()
            if win_count >= self.win_condition:
                self.winner = player
                self.save()
                return True
        return False


class Stage(models.Model):
    TYPES = [
        ("STARTER", "Starter"),
        ("COUNTERPICK", "Counterpick")
    ]
    
    name = models.CharField(max_length=50)
    emoji = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=TYPES)

    def __str__(self):
        return self.name

class Game(models.Model):
    number = models.IntegerField()
    players = models.ManyToManyField(Player, through="GamePlayer")
    guild = models.ForeignKey(Guild, null=True, on_delete=models.CASCADE)
    
    game_set = models.ForeignKey(GameSet, null=True, on_delete=models.CASCADE)
    stage = models.ForeignKey(Stage, null=True, on_delete=models.SET_NULL)
    
    winner = models.ForeignKey(Player, null=True, on_delete=models.SET_NULL, related_name="winner_game")
    winner_character = models.CharField(max_length=50, null=True, blank=True)    

    def set_winner(self, player):
        """
        Sets the winner of this game, modifying as well the GamePlayer object
        """        
        # Sets winner GamePlayer
        game_player = self.gameplayer_set.filter(player=player).first()
        game_player.winner = True
        game_player.save()

        self.winner = player
        self.winner_character = game_player.character        
        
        self.save()

class GamePlayer(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    
    character = models.CharField(max_length=50, null=True, blank=True)
    winner = models.BooleanField(null=True)
    
    def __str__(self):
        return f"[{self.game}]: {self.player}({self.character})"

class Message(models.Model):
    MODE = [
        ("FRIENDLIES", "Friendlies"),
        ("RANKED", "Ranked")
    ]

    id = models.BigIntegerField(primary_key=True)
    tier = models.ForeignKey(Tier, on_delete=models.CASCADE, null=True)
    channel_id = models.BigIntegerField(null=True)
    arena = models.ForeignKey(Arena, on_delete=models.CASCADE)
    mode = models.CharField(max_length=10, choices=MODE, default="FRIENDLIES")
