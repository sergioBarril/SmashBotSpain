import discord
import asyncio
import unicodedata

from discord.ext import tasks, commands

from .params.flairing_params import (REGIONS, CHARACTERS, NORMALIZED_CHARACTERS, key_format, normalize_character)
from .params.matchmaking_params import (TIER_NAMES)

from .checks.flairing_checks import (in_flairing_channel)


class Flairing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.region_roles = {}
        self.character_roles = {}
        self.tier_roles = {}

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

        for tier_name in TIER_NAMES:
            if tier_name not in all_roles_names:
                new_role = await self.guild.create_role(name = tier_name, mentionable = True)
                self.tier_roles[tier_name] = new_role
            else:
                self.tier_roles[tier_name] = discord.utils.get(all_roles, name=tier_name)
    
    @commands.command()
    @commands.check(in_flairing_channel)
    async def region(self, ctx, *, region_name = None):        
        player = ctx.author
        await ctx.message.delete(delay=20)
        
        if region_name is None:
            return await ctx.send(f"Así no: simplemente pon `.region X`, cambiando `X` por el nombre de tu región.", delete_after=20)
        
        region_key = key_format(region_name)

        if region_key not in self.region_roles.keys():            
            return await ctx.send(f"Por ahora no está contemplado {region_name} como región. ¡Asegúrate de que lo hayas escrito bien!", delete_after=20)        
        
        # Fetch new region
        new_region_role = self.region_roles[key_format(region_name)]                
        old_region_roles = [role for role in player.roles if role.name in REGIONS]

        if new_region_role in old_region_roles:
            await player.remove_roles(new_region_role)            
            return await ctx.send(f"Vale, te he quitado el rol de {new_region_role.name}.", delete_after=20)
        else:
            await player.add_roles(new_region_role)
            return await ctx.send(f"Hecho, te he añadido el rol de {new_region_role.name}.", delete_after=20)
        
    @commands.command(aliases=["main", "second"])
    @commands.check(in_flairing_channel)
    async def character(self, ctx, *, char_name=None):
        player = ctx.author
        await ctx.message.delete(delay = 20)
        
        if char_name is None:
            return await ctx.send(f"Así no: simplemente pon `.main X`, cambiando `X` por el nombre de tu personaje.", delete_after=20)

        character_key = key_format(char_name)
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

    @commands.command()
    @commands.check(in_flairing_channel)
    async def tier(self, ctx, *, tier_num = None):
        player = ctx.author
        await ctx.message.delete(delay=20)

        # Format check
        if tier_num is None or len(tier_num) != 1 or not tier_num.isdigit():
            return await ctx.send(f"Así no: simplemente pon `.tier X`, cambiando `X` por un número del 1 al 4.", delete_after=20)        
        
        if int(tier_num) not in (1,2,3,4):
            return await ctx.send(f"Lo siento, pero...¡la Tier {tier_num} no existe!")

        # Get tier
        real_tier = next((role for role in player.roles[::-1] if role.name in TIER_NAMES), None)        
        
        if not real_tier:
            return await ctx.send(f"¡Pero si no tienes tier aún! Espérate a que algún admin te coloque en tu tier.", delete_after=20)
        
        real_tier_num = real_tier.name[-1]

        # Check asked tier
        if tier_num < real_tier_num:
            return await ctx.send(f"Estás intentando asignarte el rol de Tier {tier_num}, pero tú eres Tier {real_tier_num}. ¡Solo puedes autoasignarte roles inferiores al tuyo!", delete_after=20)
        elif tier_num == real_tier_num:
            return await ctx.send(f"Estás intentando borrarte de la Tier {tier_num}. Es normal perder la confianza en uno a veces, pero si los panelistas te han puesto en Tier {tier_num} será por algo. ¡Así que no te borraré!", delete_after=20)
        
        # Add/Delete
        new_tier_role = self.tier_roles[f'Tier {tier_num}']
        old_tier_roles = [role for role in player.roles if role.name in TIER_NAMES]
        
        if new_tier_role in old_tier_roles:
            await player.remove_roles(new_tier_role)
            return await ctx.send(f"Vale, te he quitado el rol de {new_tier_role.name} -- ya no recibirás sus pings.", delete_after=20)
        else:
            await player.add_roles(new_tier_role)
            return await ctx.send(f"Vale, te he añadido el rol de {new_tier_role.name} -- a partir de ahora recibirás sus pings.", delete_after=20)        



    @region.error
    async def region_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        else:
            print(error)

    @character.error
    async def character_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        else:
            print(error)
    
    @tier.error
    async def character_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        else:
            print(error)
        
def setup(bot):
    bot.add_cog(Flairing(bot))