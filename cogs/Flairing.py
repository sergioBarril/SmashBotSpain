import discord
import asyncio
import unicodedata

from discord.ext import tasks, commands

from .params.flairing_params import (REGIONS, CHARACTERS, NORMALIZED_CHARACTERS, key_format, normalize_character)
from .checks.flairing_checks import (in_flairing_channel)


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
                new_role = await self.guild.create_role(name = region, mentionable = True)
                self.region_roles[key_format(region)] = new_role
            else:
                self.region_roles[key_format(region)] = discord.utils.get(all_roles, name=region)
        
        for character in CHARACTERS:
            if character not in all_roles_names:
                new_role = await self.guild.create_role(name = character, mentionable = True)
                self.character_roles[character] = new_role
            else:
                self.character_roles[character] = discord.utils.get(all_roles, name=character)
    
    @commands.command()
    @commands.check(in_flairing_channel)
    async def region(self, ctx, *, region_name):
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
        
    @region.error
    async def region_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass

    @commands.command(aliases=["main", "second"])
    @commands.check(in_flairing_channel)
    async def character(self, ctx, *, char_name):
        player = ctx.author
        character_key = key_format(char_name)
        await ctx.message.delete(delay = 20)
        
        normalized_char = normalize_character(char_name)
        
        if not normalized_char:            
            return await ctx.send(f"No existe el personaje {char_name}... Prueba escribiéndolo diferente o contacta con un admin.", delete_after=20)
        
        # Fetch character role
        new_char_role = self.character_roles[normalized_char]
        old_char_roles = [role for role in player.roles if role.name in CHARACTERS]

        if new_char_role in old_char_roles:
            await player.remove_roles(new_char_role)            
            return await ctx.send(f"Vale, te he quitado el rol de {new_char_role.name}.", delete_after=20)
        elif len(old_char_roles) > 4:
            return await ctx.send(f"Oye, filtra un poco. Ya tienes muchos personajes, quítate alguno antes de añadir más.", delete_after=20)
        else:
            await player.add_roles(new_char_role)
            return await ctx.send(f"Hecho, te he añadido el rol de {new_char_role.name}.", delete_after=20)

    @character.error
    async def character_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass

def setup(bot):
    bot.add_cog(Flairing(bot))