import discord
import asyncio
import unicodedata
import aiohttp
import json
import typing



from discord.ext import tasks, commands

from .params.matchmaking_params import (TIER_NAMES)

from .checks.flairing_checks import (in_flairing_channel, in_spam_channel)

from .formatters.text import list_with_and
from .params.roles import SPANISH_REGIONS, SMASH_CHARACTERS, DEFAULT_TIERS
from .aux_methods.roles import update_or_create_roles, find_role

class Flairing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["create_roles", "update_roles"])
    async def setup_roles(self, ctx, role_type=None):
        guild = ctx.guild
        mode = ctx.invoked_with

        update = (mode == "update_roles")
        
        all_roles = await guild.fetch_roles()
        all_roles_names = [role.name for role in all_roles]

        if role_type is None or role_type == "regions":
            created, updated = await update_or_create_roles(guild, all_roles, all_roles_names, SPANISH_REGIONS, update)
            await ctx.send(f"Regiones creadas: {created}. Regiones actualizadas (o dejadas igual): {updated}")
        if role_type is None or role_type == "characters":
            created, updated = await update_or_create_roles(guild, all_roles, all_roles_names, SMASH_CHARACTERS, update)
            await ctx.send(f"Personajes creados: {created}. Personajes actualizados (o dejados igual): {updated}")
        if role_type is None or role_type == "tiers":
            created, updated = await update_or_create_roles(guild, all_roles, all_roles_names, DEFAULT_TIERS, update)
            await ctx.send(f"Tiers creadas: {created}. Tiers actualizadas (o dejadas igual): {updated}")        

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
        
        # BAD COMMAND
        if param is None:
            return await ctx.send(f"Así no: simplemente pon `.{role_type} X`, cambiando `X` por el nombre del rol. _(Ej.: `.main palutena`)_",
                delete_after=25)
        
        # GET ROLE
        guild_roles = await guild.fetch_roles()
        role = find_role(param, guild_roles)
        if not role:
            return await ctx.send(f"No se ha encontrado ningún rol con el nombre de **{param}**... ¿Lo has escrito bien?",
                delete_after=25)        
        
        body = {
            'guild': guild.id,
            'role_type': role_type,
            'player': player.id,
            'role_id' : role.id,
        }        
        
        async with self.bot.session.post(f'http://127.0.0.1:8000/players/{player.id}/roles/', json=body) as response:            
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)
                
                # Get params                
                action = resp_body['action']                
                                
                
                ROLE_MESSAGE_TIME = resp_body.get('role_message_time', 25)                
                                
                #  SET EMOJI TEXT
                emoji = role.emoji()
                
                if emoji and role_type in ('main', 'second', 'pocket'):
                    emoji_text = f' ({emoji})'
                elif emoji and role_type == 'region':
                    emoji_text = f' {emoji}'
                else:
                    emoji_text = ""

                # Add/Remove role and send message
                if action == "REMOVE":
                    await player.remove_roles(role)
                    message_text = f"Te he quitado el rol de **{role.name}**{emoji_text}."
                # REGIONS
                elif role_type == "region":
                    await player.add_roles(role)
                    message_text = f"Te he puesto el rol de **{role.name}**{emoji_text}."
                # CHARACTERS
                elif role_type in ('main', 'second', 'pocket'):
                    if action == "ADD":
                        await player.add_roles(role)
                        message_text= f"Te he añadido como {role_type} **{role.name}**{emoji_text}."
                    elif action == "SWAP":
                        message_text = f"Perfecto, **{role.name}**{emoji_text} es ahora tu {role_type}."
                # TIERS
                elif role_type == 'tier':
                    if role in player.roles:
                        await player.remove_roles(role)
                        message_text = f"Vale, te he quitado el rol de **{role.name}** -- ya no recibirás sus pings."
                    else:
                        await player.add_roles(role)
                        message_text = f"Vale, te he añadido el rol de **{role.name}** -- a partir de ahora recibirás sus pings."
                
                await ctx.send(message_text, delete_after=ROLE_MESSAGE_TIME)

            elif response.status == 400:
                html = await response.text()
                resp_body = json.loads(html)

                mains = resp_body.get('mains', [])
                tier_error = resp_body.get('tier_error', False)
                
                ROLE_MESSAGE_TIME = resp_body.get('role_message_time', 25)
                
                # ERROR WITH MAINS
                if mains:
                    mains_names = []
                    for main_id in mains:
                        role = guild.get_role(main_id)
                        mains_names.append(role.name) if role else mains_names.append(main_id)
                    
                    mains_text = list_with_and(mains_names, bold=True)
                    error_text = f"Ya tienes {len(mains)} mains: **{mains_text}**. ¡Pon a alguno en seconds o pocket!"
                
                # ERROR WITH TIER
                elif tier_error:
                    player_tier_id = resp_body.get('player_tier', None)
                    wanted_tier_id = resp_body.get('id', None)

                    player_tier = guild.get_role(player_tier_id)                    
                    wanted_tier = guild.get_role(wanted_tier_id)
                    
                    if tier_error == "NO_TIER":
                        error_text = f"¡Pero si no tienes **Tier** aún! Espérate a que algún admin te coloque en tu tier."
                    elif tier_error == "SAME_TIER":
                        error_text = (f"Estás intentando borrarte de **{player_tier.name}**."
                            f" Es normal perder la confianza en uno a veces, pero si los panelistas te han puesto en **{player_tier.name}** será por algo."
                            " ¡Así que no te borraré!")
                    elif tier_error == "HIGHER_TIER":
                        error_text = (f"Estás intentando asignarte el rol de **{wanted_tier.name}**, pero tú eres solo **{player_tier.name}**."
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
                    
                    if role_type in ('main', 'second', 'pocket'):
                        role_type = 'personaje.'
                    elif role_type == 'region':
                        role_type = 'región.'
                    elif role_type == 'tier':
                        role_type = 'tier.'

                    return await ctx.send(f"El rol **{role.name}** no es un rol de {role_type}")
                else:
                    return await ctx.send(f"Error al modificar tus roles.", delete_after=ROLE_MESSAGE_TIME)
    
    @commands.command(aliases=['import'])
    async def import_roles(self, ctx, *, role_type=None):
        guild = ctx.guild
        all_roles = await guild.fetch_roles()
        
        name_list = []
        if role_type.lower() in ('regiones', 'regions'):
            role_type = 'regions'
            name_list = SPANISH_REGIONS.keys()
        
        elif role_type.lower() in ('personajes', 'chars', 'characters'):
            role_type = 'characters'
            name_list = SMASH_CHARACTERS.keys()
        
        elif role_type.lower() in ('tiers', 'tier'):
            role_type = 'tiers'
            name_list = DEFAULT_TIERS

        if not name_list:
            return await ctx.send(f"No se puede importar la categoría **{role_type}**.")

        # GET RELEVANT IDS
        if role_type == 'tiers':
            relevant_ids = [
                {'id': role.id, 'weight': DEFAULT_TIERS[role.name]['weight']}
                for role in all_roles if role.name in DEFAULT_TIERS.keys()
            ]
        else:
            relevant_ids = [role.id for role in all_roles if role.name in name_list]
        
        body = {
            'guild' : guild.id,
            'roles' : relevant_ids
        }
        
        async with self.bot.session.post(f'http://127.0.0.1:8000/{role_type}/import/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                count = resp_body['count']
                
                if role_type == 'regions':
                    count_text = f"{count} región" if count == 1 else f"{count} regiones"
                elif role_type == 'characters':
                    count_text = f"{count} personaje" if count == 1 else f"{count} personajes"
                elif role_type == 'tiers':
                    count_text = f"{count} tier" if count == 1 else f"{count} tiers"

                await ctx.send(f"Se han creado **{count_text}**.")
            else:
                await ctx.send(f"Error con el import.")

    @commands.command(aliases=["rol"])
    @commands.check(in_spam_channel)
    async def role(self, ctx, *, param = None):
        """
        Sends a message with the players that have the role with name "param"
        (or similar).
        """
        # BAD COMMAND
        if param is None:
            return await ctx.send(f"Así no: para ver los jugadores con un rol, simplemente pon `.role X`, cambiando `X` por el nombre del rol. _(Ej.: `.role palutena`)_",
                delete_after=25)        
        
        # Get role
        guild = ctx.guild
        guild_roles = await guild.fetch_roles()
                        
        # GET ROLE
        role = find_role(param, guild_roles)

        if not role:
            return ctx.send(f"No existe el rol **{param}**... ¿Seguro que lo has escrito bien?")
                
        member_amount = len(role.members)
        if member_amount == 0:
            return await ctx.send(f"No hay nadie con el rol **{role.name}**.")
        else:                
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

        # Build the message
        header = f"**__{role_type.upper()}__**\n"
        messages = []
        
        for role in role_list:
            role_message = ""
            members = [guild.get_member(player_id) for player_id in role['players']]
            members = [member for member in members if member]
            num_members = len(members)

            discord_role = guild.get_role(role['id'])
            role_message += f"**{discord_role.name}** [{num_members}]:\n"
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
        
        for region_id in regions[:2]:
            region = guild.get_role(region_id)
            region_text += f"{region.name} {region.emoji()}\n"

        # CHARACTERS
        main_title = "Main:" if len(mains) < 2 else "Mains:"
        main_text = ""

        for main_id in mains:            
            main = guild.get_role(main_id)            
            main_text += f"{main.name} ({main.emoji()})\n"
        
        second_title = f"Second:" if len(seconds) < 2 else "Seconds:"
        second_text = u"\u200C"

        for second_id in seconds:
            second = guild.get_role(second_id)
            second_text += f"{second.emoji()}  "        
        
        pocket_title = f"Pocket:" if len(pockets) < 2 else "Pockets:"        
        pocket_text = u"\u200C"
        
        for pocket_id in pockets:
            pocket = guild.get_role(pocket_id)
            pocket_text += f"{pocket.emoji()}  "
        
        # EMBED
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
            raise error

    @commands.command()
    async def tier_channel(self, ctx, tier: typing.Optional[discord.Role], channel: typing.Optional[discord.TextChannel]):
        """
        Given a tier and a channel, sets the tier's channel.        
        """
        guild = ctx.guild

        if tier is None:
            return await ctx.send("Para utilizar este comando, escribe `.tier_channel @Tier3 #tier-3`, por ejemplo.")
        
        if channel is None:
            channel = ctx.channel

        body = {'channel_id': channel.id}

        async with self.bot.session.patch(f'http://127.0.0.1:8000/tiers/{tier.id}/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)
                await ctx.send(f"Hecho: a partir de ahora el canal de {tier} será {channel.mention}.")
            else:
                await ctx.send("Ha habido un error. ¿Quizá ese canal ya lo está usando otra tier?")


    @list_role.error
    async def list_role_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        else:
            raise error        
def setup(bot):
    bot.add_cog(Flairing(bot))