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
    

    @commands.command()
    async def print_emojis(self, ctx):
        guild = ctx.guild

        emojis = guild.emojis
        for i, emoji in enumerate(emojis):
            print(str(emoji))            
        print(len(emojis))

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
            return await ctx.send(f"Así no: simplemente pon `.{role_type} X`, cambiando `X` por el nombre del rol. _(Ej.: `.main palutena`)_",
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
                emoji = resp_body.get('emoji', "")
                ROLE_MESSAGE_TIME = resp_body.get('role_message_time', 25)

                role = guild.get_role(role_id)

                if role is None:
                    return await ctx.send(
                        (f"No se ha encontrado el rol **{role_name}** en el servidor, pero en la aplicación sí..."
                        "Habla con un admin.")
                    )             

                #  SET EMOJI TEXT
                if emoji and role_type in ('main', 'second', 'pocket'):
                    emoji_text = f' ({emoji})'
                elif emoji and role_type == 'region':
                    emoji_text = f' {emoji}'
                else:
                    emoji_text = ""

                # Add/Remove role and send message
                if action == "REMOVE":
                    await player.remove_roles(role)
                    message_text = f"Te he quitado el rol de **{role_name}**{emoji_text}."
                # REGIONS
                elif role_type == "region":
                    await player.add_roles(role)
                    message_text = f"Te he puesto el rol de **{role_name}**{emoji_text}."
                # CHARACTERS
                elif role_type in ('main', 'second', 'pocket'):
                    if action == "ADD":
                        await player.add_roles(role)
                        message_text= f"Te he añadido como {role_type} **{role_name}**{emoji_text}."
                    elif action == "SWAP":
                        message_text = f"Perfecto, **{role_name}**{emoji_text} es ahora tu {role_type}."
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
                role_count = resp_body['role_count']
                
                if role_type == 'regions':
                    count_text = f"{count} región" if count == 1 else f"{count} regiones"
                elif role_type == 'characters':
                    count_text = f"{count} personaje" if count == 1 else f"{count} personajes"

                await ctx.send(f"Se han creado **{count_text}** y **{role_count} roles**.")
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

    
    @commands.command(aliases=["regiones", "regions", "tiers", "mains", "seconds", "pockets"])
    @commands.check(in_spam_channel)
    async def list_role(self, ctx):        
        guild = ctx.guild
        
        # Select roles        
        role_type = ctx.invoked_with
        if role_type == 'list_role':
            return None
        if role_type == "regiones":
            role_type = "regions"

        body = {
            'guild': guild.id,
            'role_type': role_type,
        }

        async with self.bot.session.get(f'http://127.0.0.1:8000/players/roles/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                roles = resp_body['roles']
            else:
                print(response)
                return await ctx.send("Error, contacta con algún admin")
        
        role_list = [role for role in roles if role['players']]        
        if not role_list:
            return await ctx.send(f"Nadie tiene un rol de la categoría **{role_type.capitalize()}**")
        
        # member_lists = {role.name : role.members for role in role_list}

        # Build the message
        header = f"**__{role_type.upper()}__**\n"
        messages = []
        
        for role in role_list:
            role_message = ""
            members = [guild.get_member(player_id) for player_id in role['players']]
            members = [member for member in members if member]
            num_members = len(members)

            role_message += f"**{role['name']}** [{num_members}]:\n"
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


    @commands.command(aliases=["perfil"])
    async def profile(self, ctx):
        guild = ctx.guild
        player = ctx.author

        body = {
            'guild' : guild.id
        }

        # GET ROLE
        async with self.bot.session.get(f'http://127.0.0.1:8000/players/{player.id}/profile/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                regions = resp_body['regions']
                
                mains = resp_body['mains']
                seconds = resp_body['seconds']
                pockets = resp_body['pockets']

                tier_id = resp_body['tier']
            else:
                return await ctx.send("Error al mostrar el perfil. Contacta con un admin.")        
        
        # TIER
        if tier_id:
            tier = guild.get_role(tier_id)        
        tier_text = f" ({tier.name})" if tier_id else ""
        tier_color = tier.color if tier_id else discord.Colour()

        # REGIONS
        region_title = "Región:" if len(regions) < 2 else "Regiones:"
        region_text = ""
        
        for region in regions[:2]:
            region_text += f"{region['name']} {region['emoji']}\n"

        # CHARACTERS
        main_title = "Main:" if len(mains) < 2 else "Mains:"
        main_text = ""

        for main in mains:
            main_text += f"{main['name']} ({main['emoji']})\n"
        
        second_title = f"Second:" if len(seconds) < 2 else "Seconds:"
        second_text = ""

        for second in seconds:
            second_text += f"{second['emoji']}  "
        
        pocket_title = f"Pocket:" if len(pockets) < 2 else "Pockets:"
        pocket_text = ""
        for pocket in pockets:
            pocket_text += f"{pocket['emoji']}  "

        
        embed = discord.Embed(title=f"**__{player.nickname()}__{tier_text}**", colour=tier_color)
        embed.set_thumbnail(url=player.avatar_url)
        embed.set_footer(text="SmashBotSpain", icon_url="https://www.smashbros.com/assets_v2/img/top/hero05_en.jpg")

        if regions:
            embed.add_field(name=region_title, value=region_text, inline=False)
        if mains:
            embed.add_field(name=main_title, value=main_text, inline=False)
        if seconds:
            embed.add_field(name=second_title, value=second_text, inline=True)
        if pockets:
            embed.add_field(name=pocket_title, value=pocket_text, inline=True)
        
        return await ctx.send(embed=embed)

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