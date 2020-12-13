# bot.py
import os

import discord
from discord.ext import tasks, commands

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

class SmashBotSpain(commands.Bot):
    VERSION =  "v0.1"

    def __init__(self, command_prefix):
        super().__init__(command_prefix)        

    async def on_ready(self):        
        self.guild = discord.utils.get(self.guilds, name=GUILD)
        
        print(
            f'{client.user} is connected to the following guild:\n'
            f'{self.guild.name}(id: {self.guild.id})'
        )

        self.get_cog('Matchmaking').setup_arenas(self.guild)

        # self.saludon.start()

    # @tasks.loop(seconds=5)
    # async def saludon(self):
    #     channel = await self.fetch_channel(786726412554862616)
    #     await channel.send(f"Hola! te saludo.")

client = SmashBotSpain(command_prefix=["."])
client.load_extension("cogs.Matchmaking")

client.run(TOKEN)