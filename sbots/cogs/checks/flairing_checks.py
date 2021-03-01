import aiohttp
import discord
import json

# ***********************
# ***********************
#       C H E C K S
# ***********************
# ***********************

async def in_flairing_channel(ctx):
    channel = ctx.channel
    guild = ctx.guild

    if isinstance(channel, discord.DMChannel):
        return False
    
    async with ctx.bot.session.get(f'http://127.0.0.1:8000/guilds/{guild.id}') as response:
        if response.status == 200:
            html = await response.text()
            resp_body = json.loads(html)

            flairing_channel = guild.get_channel(channel_id=resp_body['flairing_channel'])
            return channel == flairing_channel            
        else:
            return False

async def in_spam_channel(ctx):
    channel = ctx.channel
    guild = ctx.guild
    
    if isinstance(channel, discord.DMChannel):
        return False
    
    async with ctx.bot.session.get(f'http://127.0.0.1:8000/guilds/{guild.id}') as response:
        if response.status == 200:
            html = await response.text()
            resp_body = json.loads(html)

            spam_channel = guild.get_channel(channel_id=resp_body['spam_channel'])
            return channel == spam_channel
        else:
            return False    