# bot.py
import os

import discord
from discord.ext import tasks, commands

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

class SmashBotSpain(commands.Bot):
    VERSION =  "v0.3"

    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)        

    async def on_ready(self):        
        self.guild = discord.utils.get(self.guilds, name=GUILD)
        
        print(
            f'{client.user} is connected to the following guild:\n'
            f'{self.guild.name}(id: {self.guild.id})'
        )

        matchmaking = self.get_cog('Matchmaking')
        await matchmaking.setup_matchmaking(guild=self.guild)
        
        
intents = discord.Intents.default()  # All but the two privileged ones
intents.members = True

client = SmashBotSpain(command_prefix=["."], intents=intents)
client.load_extension("cogs.Matchmaking")



client.run(TOKEN)