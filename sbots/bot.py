# bot.py
import os
import aiohttp
import sys

import discord
import logging
import datetime

from discord.ext import tasks, commands

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('DISCORD_GUILD'))

# Logger Configuration
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)

now = datetime.datetime.now()
file_name = f"logs/discord-{now.strftime('%Y%m%d%H%M')}.log"

handler = logging.FileHandler(filename=file_name, encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))

stdout_handler = logging.StreamHandler(sys.stdout)

logger.addHandler(stdout_handler)
logger.addHandler(handler)

class SmashBotSpain(commands.Bot):
    VERSION =  "v2.0"

    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)        
        self.help_command = None

    async def on_ready(self):        
        self.session = aiohttp.ClientSession()        
        
        logger.info(f'{client.user} is connected')
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
client.load_extension("cogs.Ranked")
client.load_extension("cogs.Admin")

client.run(TOKEN)