from ..params.matchmaking_params import TIER_CHANNEL_NAMES

# ***********************
# ***********************
#       C H E C K S
# ***********************
# ***********************

def in_their_arena(ctx):
    player = ctx.author
    arena = ctx.channel
    
    if arena not in ctx.bot.get_cog("Matchmaking").arenas:
        return False
    
    return player in ctx.bot.get_cog("Matchmaking").arena_status[arena.name]

def in_tier_channel(ctx):
    return ctx.message.guild is not None and ctx.channel.name in TIER_CHANNEL_NAMES