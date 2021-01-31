import discord
import asyncio
import unicodedata

from discord.ext import tasks, commands

from .params.flairing_params import (REGIONS)
from .checks.flairing_checks import (in_flairing_channel)

def no_accents(text):
    text = unicodedata.normalize('NFD', text)\
        .encode('ascii', 'ignore')\
        .decode("utf-8")
    return str(text)

def key_format(text):
    return no_accents(text.lower())

class Flairing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.region_roles = {}
        self.character_roles = {}

    async def setup_flairing(self, guild):
        self.guild = guild
        all_roles = await self.guild.fetch_roles()
        all_roles_names = [role.name for role in all_roles]
        
        for region in REGIONS:
            if region not in all_roles_names:
                await self.guild.create_role(name = region, mentionable = True)
            self.region_roles[key_format(region)] = discord.utils.get(all_roles, name=region)
    
    
    @commands.command()
    @commands.check(in_flairing_channel)
    async def region(self, ctx, region_name):
        player = ctx.author
        region_key = key_format(region_name)
        await ctx.message.delete(delay = 20)

        if region_key not in self.region_roles.keys():            
            return await ctx.send(f"Por ahora no está contemplado {region_name} como región. ¡Asegúrate de que lo hayas escrito bien!", delete_after=20)        
        
        # Fetch new region
        new_region_role = self.region_roles[key_format(region_name)]                
        old_region_roles = [role for role in player.roles if role.name in REGIONS]

        if new_region_role in old_region_roles:
            await player.remove_roles(new_region_role)            
            return await ctx.send(f"Vale, te he quitado el rol de {new_region_role.name}.", delete_after=20)

        if len(old_region_roles) != 1:
            await player.add_roles(new_region_role)
            return await ctx.send(f"Hecho, te he añadido el rol de {new_region_role.name}.", delete_after=20)
        else:
            await player.remove_roles(old_region_roles[0])
            await player.add_roles(new_region_role)
            return await ctx.send(f"Perfecto, te he quitado el rol de {old_region_roles[0].name} y te he añadido el rol de {new_region_role.name}.", delete_after=20)

def setup(bot):
    bot.add_cog(Flairing(bot))