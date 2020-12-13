import discord
import os
import random

import asyncio

from discord.ext import commands

class Matchmaking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.search_list = []
    
    def setup_arenas(self, guild):
        self.guild = guild
        self.arenas =  discord.utils.get(self.guild.categories, name="ARENAS").channels
        self.arena_status = {f"arena-{i}" : None for i in range(1, len(self.arenas) + 1)}        
    
    @commands.command()
    async def friendlies(self, ctx):
        user = ctx.author
        
        # if user in self.search_list:
            # return await ctx.send(f"Hey {user.mention}, you're already in!")
        # else:
        self.search_list.append(user)
        
        await ctx.send(f"Perfecto {user.mention}, te acabo de meter.")

        if len(self.search_list) > 1:
            match = random.sample(self.search_list, 2)
                
            # Remove from the list
            self.search_list.remove(match[0])
            self.search_list.remove(match[1])

            # Get and lock an arena
            arena = await self.get_free_arena()
            self.arena_status[arena.name] = match

            #Set Permissions
            await arena.set_permissions(ctx.guild.default_role, read_messages=False, send_messages=False)
            await arena.set_permissions(match[0], read_messages=True, send_messages=True)
            await arena.set_permissions(match[1], read_messages=True, send_messages=True)
            
            await arena.send(f"¡Match encontrado! {match[0].mention} y {match[1].mention}, ¡os toca!")

    @commands.command()
    async def ggs(self, ctx):
        await ctx.send("GGs, ¡gracias por jugar!")
        await asyncio.sleep(10)
        if ctx.channel in self.arenas:
            await self.delete_arena(ctx.channel)
        
        else: 
            # Search the channel to close
            arena_to_close = None
            for arena in self.arenas:
                if ctx.author in self.arena_status[arena.name]:
                    arena_to_close = arena
                    break            
            # Delete it
            if arena_to_close:
                await self.delete_arena(arena_to_close) 

    #  ***********************************************
    #           A   R   E   N   A   S
    #  ***********************************************
    
    async def get_free_arena(self):
        for arena in self.arenas:
            if not self.arena_status[arena.name]:
                return arena

        # No arena available, let's make one
        return await self.make_arena()

    async def make_arena(self):
        arenas_category = discord.utils.get(self.guild.categories, name="ARENAS")        
        new_arena_name = f'arena-{len(self.arenas) + 1}'
        channel = await arenas_category.create_text_channel(new_arena_name)
        
        # Arena list and status dictionary updated
        self.arenas.append(channel)
        self.arena_status[new_arena_name] = None

        return channel
            
    @commands.command()
    async def delete_arenas(self, ctx):
        for arena in self.arenas:
            await arena.delete()
        self.arena_status = {}
        self.arenas = []

    async def delete_arena(self, arena):
        self.arenas.remove(arena)
        self.arena_status.pop(arena.name, None)
        await arena.delete()


    # ************************************
    #           L I S T
    # ************************************
    
    # @commands.command()
    # async def list(self, ctx):
    #     """
    #     Shows a list with the people waiting for the friendlies list.
    #     This is only for testing now, since there will never be 2 people (match is autoaccepted).

    #     It will serve a purpose when matches can be declined.
        
    #     """
    #     response = "**Friendlies list:**"
    #     users = ", ".join([user.name for user in self.search_list])

    #     if not users:
    #         users = " _Lista vacía_"

    #     await ctx.send(response + users)

def setup(bot):
    bot.add_cog(Matchmaking(bot))