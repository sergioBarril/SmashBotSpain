from ..matchmaking_params import TIER_CHANNEL_NAMES

# ***********************
# ***********************
#       C H E C K S
# ***********************
# ***********************

def in_their_arena(ctx):
    player = ctx.author
    arena = ctx.channel
    
    if arena not in ctx.cog.arenas:
        return False
    
    return player in ctx.cog.arena_status[arena.name]

def in_tier_channel(ctx):    
    return ctx.channel.name in TIER_CHANNEL_NAMES