import aiohttp
import discord
import json

# ***********************
# ***********************
#       C H E C K S
# ***********************
# ***********************

def in_arena(ctx):
    arena = ctx.channel
    arenas_category = discord.utils.get(ctx.guild.categories, name="ARENAS")

    return arena in arenas_category.channels

async def in_tier_channel(ctx):
    channel = ctx.channel
    guild = ctx.guild

    async with ctx.bot.session.get(f'http://127.0.0.1:8000/tiers/') as response:
        if response.status == 200:
            html = await response.text()
            resp_body = json.loads(html)

            channel_ids = [tier['channel_id'] for tier in resp_body]            
            return channel.id in channel_ids
        else:
            return False