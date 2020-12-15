# bot.py
import os

import discord
from discord.ext import tasks, commands

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
LIST_MESSAGE = int(os.getenv('LIST_MESSAGE_ID'))
LIST_CHANNEL = int(os.getenv('LIST_CHANNEL_ID'))

class SmashBotSpain(commands.Bot):
    VERSION =  "v0.2"

    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)        

    async def on_ready(self):        
        self.guild = discord.utils.get(self.guilds, name=GUILD)
        
        print(
            f'{client.user} is connected to the following guild:\n'
            f'{self.guild.name}(id: {self.guild.id})'
        )

        list_channel = self.guild.get_channel(channel_id=LIST_CHANNEL)
        list_message = await list_channel.fetch_message(LIST_MESSAGE)

        matchmaking = self.get_cog('Matchmaking')
        matchmaking.setup_matchmaking(guild=self.guild, list_message=list_message)
        
        
        


intents = discord.Intents.default()  # All but the two privileged ones
intents.members = True

client = SmashBotSpain(command_prefix=["."], intents=intents)
client.load_extension("cogs.Matchmaking")



client.run(TOKEN)