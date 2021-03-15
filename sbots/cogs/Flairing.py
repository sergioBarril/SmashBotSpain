import discord
import asyncio
import unicodedata
import aiohttp
import json


from discord.ext import tasks, commands

from .params.flairing_params import (REGIONS, CHARACTERS, NORMALIZED_CHARACTERS, key_format, normalize_character)
from .params.matchmaking_params import (TIER_NAMES)

from .checks.flairing_checks import (in_flairing_channel, in_spam_channel)

from .formatters.text import list_with_and


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
    

    @commands.command(aliases=["region", "main", "second", "pocket", "tier"])
    @commands.check(in_flairing_channel)
    async def set_role(self, ctx, *, param = None):
        player = ctx.author
        guild = ctx.guild
        
        await ctx.message.delete(delay=20)

        role_type = ctx.invoked_with
        if role_type == "set_role":
            return
        if param is None:
            await ctx.send(f"Así no: simplemente pon `.{role_type} X`, cambiando `X` por el nombre del rol. _(Ej.: `.main palutena`)_",
                delete_after=25)

        body = {
            'guild': guild.id,
            'role_type': role_type,
            'player': player.id,
            'param' : param,
        }        


        async with self.bot.session.post(f'http://127.0.0.1:8000/players/{player.id}/roles/', json=body) as response:            
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)
                
                # Get params
                role_name = resp_body['name']
                action = resp_body['action']
                role_id = resp_body['discord_id']
                ROLE_MESSAGE_TIME = resp_body.get('role_message_time', 25)

                role = guild.get_role(role_id)

                if role is None:
                    return await ctx.send(
                        (f"No se ha encontrado el rol **{role_name}** en el servidor, pero en la aplicación sí..."
                        "Habla con un admin.")
                    )             
                
                # Add/Remove role and send message
                if action == "REMOVE":
                    await player.remove_roles(role)
                    message_text = f"Te he quitado el rol de **{role_name}**."
                # REGIONS
                elif role_type == "region":
                    await player.add_roles(role)
                    message_text = f"Te he puesto el rol de **{role_name}**."
                # CHARACTERS
                elif role_type in ('main', 'second', 'pocket'):
                    if action == "ADD":
                        await player.add_roles(role)
                        message_text= f"Te he añadido como {role_type} **{role_name}**."
                    elif action == "SWAP":
                        message_text = f"Perfecto, **{role_name}** es ahora tu {role_type}."
                # TIERS
                elif role_type == 'tier':
                    if role in player.roles:
                        await player.remove_roles(role)
                        message_text = f"Vale, te he quitado el rol de **{role_name}** -- ya no recibirás sus pings."
                    else:
                        await player.add_roles(role)
                        message_text = f"Vale, te he añadido el rol de **{role_name}** -- a partir de ahora recibirás sus pings."
                
                await ctx.send(message_text, delete_after=ROLE_MESSAGE_TIME)

            elif response.status == 400:
                html = await response.text()
                resp_body = json.loads(html)

                mains = resp_body.get('mains', [])
                tier_error = resp_body.get('tier_error', False)
                
                ROLE_MESSAGE_TIME = resp_body.get('role_message_time', 25)
                
                # ERROR WITH MAINS
                if mains:
                    mains_text = list_with_and(mains, bold=True)
                    error_text = f"Ya tienes {len(mains)} mains: **{mains_text}**. ¡Pon a alguno en seconds o pocket!"
                
                # ERROR WITH TIER
                elif tier_error:
                    player_tier = resp_body.get('player_tier', None)
                    tier_name = resp_body.get('name', None)
                    
                    if tier_error == "NO_TIER":
                        error_text = f"¡Pero si no tienes **Tier** aún! Espérate a que algún admin te coloque en tu tier."
                    elif tier_error == "SAME_TIER":
                        error_text = (f"Estás intentando borrarte de **{tier_name}**."
                            f" Es normal perder la confianza en uno a veces, pero si los panelistas te han puesto en **{tier_name}** será por algo."
                            " ¡Así que no te borraré!")
                    elif tier_error == "HIGHER_TIER":
                        error_text = (f"Estás intentando asignarte el rol de **{tier_name}**, pero tú eres solo **{player_tier}**."
                            " ¡Solo puedes autoasignarte roles inferiores al tuyo!")                            
                
                # OTHER ERRORS
                else:
                    error_text = "Error al modificar tus roles."                
                    return print(resp_body)
                
                await ctx.send(error_text, delete_after=ROLE_MESSAGE_TIME)
            
            elif response.status == 404:
                html = await response.text()
                if html:
                    resp_body = json.loads(html)
                    ROLE_MESSAGE_TIME = resp_body.get('role_message_time', 25)
                    param_name = f"Tier {param}" if role_type == 'tier' else param
                    await ctx.send(f"No he encontrado ningún rol con el nombre de _{param}_... ¿Lo has escrito bien?",
                        delete_after=ROLE_MESSAGE_TIME)
                else:
                    await ctx.send(f"Error al modificar tus roles.", delete_after=ROLE_MESSAGE_TIME)
    
    @commands.command(aliases=['import'])
    async def import_roles(self, ctx, *, role_type=None):
        guild = ctx.guild
        all_roles = await guild.fetch_roles()

        body = {
            'guild' : guild.id,
            'roles' : [{'id': role.id, 'name': role.name} for role in all_roles]            
        }

        if role_type.lower() == 'regiones':
            role_type = 'regions'
        elif role_type.lower() in ('personajes', 'chars'):
            role_type = 'characters'        


        async with self.bot.session.post(f'http://127.0.0.1:8000/{role_type}/import/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                count = resp_body['count']
                
                if role_type == 'regions':
                    count_text = f"{count} región" if count == 1 else f"{count} regiones"
                elif role_type == 'characters':
                    count_text = f"{count} personaje" if count == 1 else f"{count} personajes"

                await ctx.send(f"Se han creado **{count_text}**.")
            else:
                await ctx.send(f"Error con el import.")

    @commands.command(aliases=["rol"])
    @commands.check(in_spam_channel)
    async def role(self, ctx, *, param):
        # Get role        
        guild = ctx.guild

        body = {
            'param': param
        }

        role = None
        # GET ROLE
        async with self.bot.session.get(f'http://127.0.0.1:8000/guilds/{guild.id}/role', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                role_id = resp_body['discord_id']
                role_name = resp_body['name']                
                role = guild.get_role(role_id)
            
            elif response.status == 404:
                html = await response.text()
                if html:
                    resp_body = json.loads(html)                                        
                    role = discord.utils.get(guild.roles, name=param)                    
                    if role is None:
                        return await ctx.send(f"No existe el rol **{param}**... ¿Seguro que lo has escrito bien?")
                else:
                    return await ctx.send(f"No se ha encontrado la Guild... contacta con algún admin.")
            
            else:
                print(response)
                return await ctx.send("Error inesperado. Contacta con algún admin.")                

        if not role:
            return await ctx.send("Hay una discrepancia entre el bot y el server. Contacta con algún admin, y que lo actualice.")
        
        member_amount = len(role.members)

        if member_amount == 0:
            return await ctx.send(f"No hay nadie con el rol **{role.name}**.")
                
        return await ctx.send(f"**{role.name}** [{member_amount}]:\n```{', '.join([member.nickname() for member in role.members])}```")

    
    @commands.command(aliases=["regiones", "regions", "tiers", "mains"])
    @commands.check(in_spam_channel)
    async def list_role(self, ctx):        
        # Select roles        
        mode = ctx.invoked_with
        if mode == 'list_role':
            return None
        if mode == "regions":
            mode = "regiones"        
        
        roles = { 
            "regiones" : self.region_roles,
            "tiers" : self.tier_roles,
            "mains" : self.character_roles
        }

        role_list = [role for role in roles[mode].values() if role.members]        
        if not role_list:
            return await ctx.send(f"Nadie tiene un rol de la categoría **{mode.capitalize()}**")

        # Sort the list
        if mode == "tiers":
            role_list.sort(key=lambda role : role.name)
        
        elif mode == "regiones" or mode == "mains":
            role_list.sort(key=lambda role : len(role.members), reverse=True)

        # If showing tiers, show only their true tier, without counting
        # the role for pings.
        if mode == "tiers":
            all_members = []            
            member_lists = {role.name : [] for role in role_list}
            
            for role in role_list[:]:
                for member in role.members:                    
                    if member not in all_members:
                        all_members.append(member)
                        member_lists[role.name].append(member)
                
                if not member_lists[role.name]:
                    role_list.remove(role)
        else:
            member_lists = {role.name : role.members for role in role_list}
                        
        # Build the message
        header = f"**__{mode.upper()}__**\n"
        messages = []
        
        for role in role_list:
            role_message = ""
            members = member_lists[role.name]
            num_members = len(members)

            role_message += f"**{role.name}** [{num_members}]:\n"
            role_message += f"```{', '.join([member.nickname() for member in members])}```\n"
            
            messages.append(role_message)
        
        # Join full message in n messages (if needed)
        full_message = [header]
        message_index = 0

        for message in messages:
            if len(full_message[message_index]) + len(message) >= 2000:
                message_index += 1
                full_message.append("")
            
            full_message[message_index] += message

        # Send the message
        for message in full_message:
            await ctx.send(message)


    @role.error
    async def role_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        else:
            print(error)

    @list_role.error
    async def list_role_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        else:
            print(error)        
def setup(bot):
    bot.add_cog(Flairing(bot))