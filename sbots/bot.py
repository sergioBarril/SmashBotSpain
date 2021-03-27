# bot.py
import os
import aiohttp
import sys

import discord
import logging

from discord.ext import tasks, commands

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('DISCORD_GUILD'))

# Logger Configuration
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))

stdout_handler = logging.StreamHandler(sys.stdout)

logger.addHandler(stdout_handler)
logger.addHandler(handler)

class SmashBotSpain(commands.Bot):
    VERSION =  "v1.1"

    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)        
        self.help_command = None

    async def on_ready(self):
        self.guild = self.get_guild(GUILD_ID)
        self.session = aiohttp.ClientSession()
        
        logger.info(
            f'{client.user} is connected to the following guild:\n'
            f'{self.guild.name}(id: {self.guild.id})'
        )

        matchmaking = self.get_cog('Matchmaking')        
        await matchmaking.setup_matchmaking()        
        
intents = discord.Intents.default()  # All but the two privileged ones
intents.members = True

client = SmashBotSpain(command_prefix=["."], intents=intents)
client.load_extension("extensions.member_nickname")
client.load_extension("extensions.role_emoji")
client.load_extension("cogs.Matchmaking")
client.load_extension("cogs.HelpCommands")
client.load_extension("cogs.Flairing")

client.run(TOKEN)