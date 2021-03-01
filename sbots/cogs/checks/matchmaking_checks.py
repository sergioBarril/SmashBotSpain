from ..params.matchmaking_params import TIER_CHANNEL_NAMES
import discord
# ***********************
# ***********************
#       C H E C K S
# ***********************
# ***********************

def in_arena(ctx):
    arena = ctx.channel
    arenas_category = discord.utils.get(ctx.guild.categories, name="ARENAS")

    return arena in arenas_category.channels

def in_tier_channel(ctx):
    return ctx.message.guild is not None and ctx.channel.name in TIER_CHANNEL_NAMES