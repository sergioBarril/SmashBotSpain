import discord

import random

from discord.ext import commands

class Matchmaking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def test(self, ctx):
        await ctx.send("Hey!")

def setup(bot):
    bot.add_cog(Matchmaking(bot))