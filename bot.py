# bot.py
import os

import discord
from discord.ext import tasks, commands

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

class SmashBotSpain(commands.Bot):
    VERSION =  "v0.2"

    def __init__(self, command_prefix):
        super().__init__(command_prefix)        

    async def on_ready(self):        
        self.guild = discord.utils.get(self.guilds, name=GUILD)
        
        print(
            f'{client.user} is connected to the following guild:\n'
            f'{self.guild.name}(id: {self.guild.id})'
        )

        self.get_cog('Matchmaking').setup_arenas(self.guild)

client = SmashBotSpain(command_prefix=["."])
client.load_extension("cogs.Matchmaking")

client.run(TOKEN)