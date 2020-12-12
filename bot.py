# bot.py
import os

import discord
from discord.ext import tasks, commands

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

class SmashBotSpain(commands.Bot):
    VERSION =  "v0"

    def __init__(self, command_prefix):
        super().__init__(command_prefix)

    async def on_ready(self):
        guild = discord.utils.get(client.guilds, name=GUILD)    
        
        print(
            f'{client.user} is connected to the following guild:\n'
            f'{guild.name}(id: {guild.id})'
        )

client = SmashBotSpain(command_prefix=["."])
client.load_extension("cogs.Matchmaking")
client.run(TOKEN)