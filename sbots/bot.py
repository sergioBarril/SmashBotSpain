# bot.py
import os
import aiohttp

import discord
from discord.ext import tasks, commands

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('DISCORD_GUILD'))

class SmashBotSpain(commands.Bot):
    VERSION =  "v1.1"

    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)        
        self.help_command = None

    async def on_ready(self):
        self.guild = self.get_guild(GUILD_ID)
        self.session = aiohttp.ClientSession()
        
        print(
            f'{client.user} is connected to the following guild:\n'
            f'{self.guild.name}(id: {self.guild.id})'
        )

        matchmaking = self.get_cog('Matchmaking')        
        await matchmaking.setup_matchmaking(guild=self.guild)        
        
intents = discord.Intents.default()  # All but the two privileged ones
intents.members = True

client = SmashBotSpain(command_prefix=["."], intents=intents)
client.load_extension("extensions.member_nickname")
client.load_extension("cogs.Matchmaking")
client.load_extension("cogs.HelpCommands")
client.load_extension("cogs.Flairing")

client.run(TOKEN)