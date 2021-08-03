from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core import validators
from django.utils import timezone
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
    leaderboard_channel = models.BigIntegerField(null=True, blank=True)
    
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

    threshold = models.IntegerField(default=1200)
    leaderboard_message = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return f"Tier {self.discord_id} (Weight: {self.weight})"
    
    def __lt__(self, other):
        return self.weight < other.weight
    
    def __eq__(self, other):
        if not isinstance(other, Tier):
            return False
        return self.discord_id == other.discord_id
    
    def __hash__(self):
        return hash(self.discord_id)
    
    def between(self, min_tier, max_tier):
        return min_tier.weight <= self.weight and self.weight <= max_tier.weight
    
    def next(self, guild):
        """
        Returns the next tier in this guild (i.e if self is Tier 3, return Tier 2)
        Returns None if there isn't one.
        """
        return Tier.objects.filter(guild=self.guild, weight= self.weight + 1).first()
    
    def previous(self, guild):
        """
        Returns the previous tier in this guild (i.e if self is Tier 3, return Tier 4)
        Returns None if there isn't one.
        """
        return Tier.objects.filter(guild=self.guild, weight= self.weight - 1).first()


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
    
    def set_tier(self, tier, guild):
        """
        Sets the new tier for this player. If he was in promotion, he's not anymore
        """
        # Set new tier
        current_tier = self.tier(guild)
        self.tiers.remove(current_tier)
        self.tiers.add(tier)
        self.save()

        # Adjust rating
        rating, created = Rating.objects.get_or_create(guild=guild, player=self)        
        rating.promotion_wins = None
        rating.promotion_losses = None

        rating.score = tier.threshold
        rating.save()

        return True


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

        # FILTER REMATCH
        arenas = arenas.exclude(created_by__in=self.get_already_matched().all())
        
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

    def get_game_set(self):
        """
        Returns the current game set this player is playing
        """
        arena_player = ArenaPlayer.objects.filter(player=self, status="PLAYING").first()

        if not arena_player:
            return False
        
        arena = arena_player.arena
        
        if arena.mode != "RANKED":
            return False
        
        game_set = arena.gameset_set.first()

        return game_set


    def get_game(self):
        """
        Returns the current game this player is playing.
        """
        game_set = self.get_game_set()
        # Get current game
        game = Game.objects.filter(game_set=game_set, winner=None).first()
        
        return game
    
    def can_rematch(self, player, search = False):
        """
        Check if can rematch the other player in a ranked game

        If this method is called while searching, there's a limit of 3h between sets.
        """        
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)        

        versus_sets = GameSet.objects.filter(players=player, created_at__gte=today).filter(players=self).order_by('-finished_at')
        
        # Played three times or more
        times_played = versus_sets.count()        
        if times_played > 2:
            return False
        # Played twice, allow only if 1-1
        elif times_played == 2:
            is_even = versus_sets.first().winner != versus_sets.last().winner

            if not is_even:
                return False            
        
        game_set = versus_sets.first()
        
        # Haven't played or actual rematch
        if not game_set or not search:
            return True

        # Check if played in last 3 hours
        last_played_at = game_set.finished_at
        if not last_played_at:
            return False
        
        time_delta = timezone.now() - last_played_at
        hours_difference = time_delta.seconds // 3600
        
        played_in_last_hours =  hours_difference < 3

        return not played_in_last_hours        
    
    def get_already_matched(self):
        """
        Returns a queryset with all the players this user has played already today
        """
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        my_sets = GameSet.objects.filter(players=self, created_at__gte=today)

        players = Player.objects.exclude(discord_id=self.discord_id).filter(gameset__in=my_sets)

        can_rematch_ids = [player.id for player in players.all() if self.can_rematch(player, search=True)]

        players = players.exclude(id__in=can_rematch_ids)
        return players

    def get_rating(self, guild):
        """
        Given a guild, returns the rating of the player
        """
        return self.rating_set.filter(guild=guild).first()
    
    def get_streak(self, guild, capped = True):
        """
        Given a guild, returns how many sets in a row he has won/lost. The number will be positive if it's wins,
        negative if it's losses.
        If capped is True, this will limit the results to the last 4 sets
        """        
        last_sets = GameSet.objects.filter(guild=guild, players=self).order_by('-created_at')

        if capped:
            last_sets = last_sets[:4]

        streak = 0
        
        for game_set in last_sets:
            if game_set.winner is None:
                continue
            elif game_set.winner == self and streak >= 0:
                streak += 1
            elif game_set.winner != self and streak <= 0:
                streak -= 1
            else:
                break
        
        return streak

class Rating(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE)

    score = models.IntegerField(default=1000)
    promotion_wins = models.IntegerField(null=True, blank=True)
    promotion_losses = models.IntegerField(null=True, blank=True)


    def __str__(self):
        return f"{self.player.discord_id} rating: {self.score}"
    
    def get_probability(self, other_rating):
        """
        Returns the probability that self.player wins the set against player2
        """
        qa = 10 ** (self.score / 400)
        qb = 10 ** (other_rating.score / 400)

        return qa/(qa + qb)
    
    def win(self, other_rating):        
        old_score = self.score
        old_tier = self.player.tier(self.guild)
        new_tier = old_tier
        promoted = False
        
        next_tier = old_tier.next(self.guild)

        # Not in promotion
        if self.promotion_wins is None:
            if next_tier:
                self.score = int(self.score + 20 + 5 * self.player.get_streak(self.guild))
            else:
                # Tier 1 uses ELO
                prob_win = self.get_probability(other_rating=other_rating)
                self.score = int(self.score + 42 * (1 - prob_win))
            self.save()
            
            # Start promotion
            if next_tier and self.score >= next_tier.threshold:
                self.score = next_tier.threshold
                self.promotion_wins, self.promotion_losses = 0, 0                
        else:            
            self.promotion_wins += 1            
            if self.promotion_wins == 3:
                # Tier up
                promoted = True
                new_tier = next_tier
                self.player.set_tier(new_tier, self.guild)
                self.promotion_wins, self.promotion_losses = None, None

        self.save()
        return {
            'promoted': promoted,
            'player': self.player.discord_id,
            'score':{
                'old': old_score,
                'new': self.score,
            },
            'promotion': {
                'wins': self.promotion_wins,
                'losses': self.promotion_losses
            },
            'tier': {
                'old_id': old_tier.discord_id,                
                'new_id': new_tier.discord_id,
                'old_leaderboard': old_tier.leaderboard_message,
                'new_leaderboard': new_tier.leaderboard_message,
            }            
        }
    
    def lose(self, other_rating):
        old_score = self.score
        old_tier = self.player.tier(self.guild)
        new_tier = old_tier
        demoted = False
        promotion_cancelled = False
        
        next_tier = old_tier.next(self.guild)
        previous_tier = old_tier.previous(self.guild)
        
        # Not in promotion
        if self.promotion_losses is None:
            # Score update
            if next_tier:
                new_score = int(self.score - 15 + 5 * self.player.get_streak(self.guild))
            else:
                # Tier 1 uses ELO
                prob_win = self.get_probability(other_rating)
                new_score = int(self.score - 42 * prob_win)

            if new_score < 900:
                new_score = 900
            self.score = new_score
            self.save()
            
            # Get demoted
            if previous_tier and self.score < old_tier.threshold - 100:
                demoted = True
                
                self.player.set_tier(previous_tier, self.guild)
                self.score = new_score + 70
                new_tier = previous_tier
                
        
        # Promotion
        else:
            self.promotion_losses += 1
            if self.promotion_losses == 3:
                # Stop promotion and -30 score
                self.score -= 30
                self.promotion_wins, self.promotion_losses = None, None
                self.save()
                promotion_cancelled = True
       
        self.save()
        return {
            'demoted': demoted,
            'player': self.player.discord_id,
            'promotion_cancelled': promotion_cancelled,
            'score':{
                'old': old_score,
                'new': self.score,
            },
            'promotion': {
                'wins': self.promotion_wins,
                'losses': self.promotion_losses
            },
            'tier': {
                'old_id': old_tier.discord_id,
                'new_id': new_tier.discord_id,
                'old_leaderboard': old_tier.leaderboard_message,
                'new_leaderboard': new_tier.leaderboard_message,
            }            
        }





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
    created_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    
    guild = models.ForeignKey(Guild, null=True, on_delete=models.CASCADE)
    players = models.ManyToManyField(Player)

    WIN_CONDITIONS = [
        ("BO3", "BO3"),
        ("BO5", "BO5"),
        ("FT5", "FT5"),
        ("FT10", "FT10"),
    ]
    
    win_condition = models.CharField(max_length=40, choices=WIN_CONDITIONS)
    winner = models.ForeignKey(Player, null=True, on_delete=models.SET_NULL, related_name="winner_set", blank=True)
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
            if win_count >= first_to:
                self.winner = player
                self.save()
                return True
        return False
    
    def finish(self):
        self.finished_at = timezone.now()        
        self.save()

    def update_ratings(self):
        """
        Updates the ELO of both players
        """
        # Get winner and loser
        winner = self.winner
        if winner is None:
            return False

        winner_rating = winner.get_rating(guild=self.guild)        
        
        loser = self.players.exclude(discord_id=winner.discord_id).first()
        if loser is None:
            return False
        loser_rating = loser.get_rating(guild=self.guild)

        # Update scores, promotions, etc.
        winner_info = winner_rating.win(other_rating=loser_rating)
        loser_info = loser_rating.lose(other_rating=winner_rating)

        return winner_info, loser_info

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

    def set_winner(self, player):
        """
        Sets the winner of this game
        """                
        self.winner = player        
        self.save()

class GamePlayer(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    
    character = models.CharField(max_length=50, null=True, blank=True)    
    
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
