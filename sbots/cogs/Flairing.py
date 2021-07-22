import discord
import asyncio
import aiohttp
import json
import logging



from discord.ext import commands

from .params.matchmaking_params import (TIER_NAMES, EMOJI_CONFIRM)
from .params.settings import PRIVACY_POLICY

from .checks.flairing_checks import (in_flairing_channel, in_spam_channel, player_exists)

from .formatters.text import list_with_and
from .params.roles import SPANISH_REGIONS, SMASH_CHARACTERS, DEFAULT_TIERS
from .aux_methods.roles import update_or_create_roles, find_role

logger = logging.getLogger('discord')

class Flairing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    
    @commands.command(aliases=["region", "main", "second", "pocket", "tier"])
    @commands.check(player_exists)
    @commands.check_any(commands.check(in_flairing_channel), commands.check(in_spam_channel))    
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
                    logger.error(f"Error with tier ping setting: {resp_body}")
                    player_tier_id = resp_body.get('player_tier', None)
                    wanted_tier_id = resp_body.get('discord_id', None)

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
                    logger.error("SET_ROLE ERROR 400")
                    return logger.error(resp_body)
                
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
                    logger.error("SET_ROLE ERROR 404")
                    return await ctx.send(f"Error al modificar tus roles.", delete_after=25)
    

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
            return await ctx.send(f"No existe el rol **{param}**... ¿Seguro que lo has escrito bien?")
                
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
                logger.error("LIST_ROLE ERROR")
                logger.error(response)
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
    @commands.check(player_exists)
    @commands.guild_only()    
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
                rating_score = resp_body.get('score')
                promotion = resp_body.get('promotion')
            
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

        # RATING
        rating_title = "Ranked:"
        if rating_score:
            rating_text = f"Puntuación: {rating_score}\n"
            
            if promotion:
                rating_text += f"Promoción: {promotion['wins']}-{promotion['losses']}\n"

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
        if rating_score:
            embed.add_field(name=rating_title, value=rating_text, inline=False)
        if mains:
            embed.add_field(name=main_title, value=main_text, inline=False)
        if seconds:
            embed.add_field(name=second_title, value=second_text, inline=True)
        if pockets:
            embed.add_field(name=pocket_title, value=pocket_text, inline=True)
        
        return await ctx.send(embed=embed)
    
    # ***************************
    #       R E G I S T E R
    # ***************************    
    async def register(self, player, guild):
        # CANCEL PREVIOUS TASK
        tasks = asyncio.all_tasks()
        register_task_name = f"policy-{player.id}"

        for task in tasks:
            task_name = task.get_name()
            
            if task_name == register_task_name:
                task.cancel()
                break

        # NAME THIS TASK
        asyncio.current_task().set_name(f"policy-{player.id}")

        # POLICY CONFIRMATION MESSAGE
        try:
            message = await player.send((
                "Este bot guarda información de los jugadores (IDs de Discord, regiones, mains, resultados de sets, etc) para poder funcionar.\n"
                f"El uso de datos está detallado en la política de privacidad: {PRIVACY_POLICY}.\n\n"
                f"Reacciona con {EMOJI_CONFIRM} para aceptar la política de privacidad y tener acceso al bot."
            ))

            def check_message(reaction, user):
                is_same_message = (reaction.message == message)
                is_valid_emoji = (reaction.emoji == EMOJI_CONFIRM)
                is_player = (user.id == player.id)

                return is_same_message and is_valid_emoji and is_player
            
            await message.add_reaction(EMOJI_CONFIRM)
            await self.bot.wait_for('reaction_add', check=check_message)        
        
        except asyncio.CancelledError:
            await message.delete()
            raise
        
        # PLAYER PROFILE CREATION
        body = {
            'player': player.id,
            'guild': guild.id,
            'roles': [role.id for role in player.roles]
        }

        async with self.bot.session.post(f'http://127.0.0.1:8000/players/', json=body) as response:
            if response.status == 200:                
                await player.send("¡Perfil creado! Ya puedes usar el resto de comandos del bot.")
                html = await response.text()
                resp_body = json.loads(html)

                tier = guild.get_role(resp_body['tier'])
                ranked = self.bot.get_cog('Ranked')
                asyncio.create_task(ranked.update_leaderboard(tier))
                return True
            else:
                logger.error("PLAYER CREATION ERROR")
                logger.error(response)
                await player.send("Ha habido un problema con la creación de tu ficha. Contacta con algún admin y vuelve a probar.")
                return False
    
    # *****************************
    #        ERROR HANDLERS
    # *****************************
    @set_role.error
    async def set_role_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.errors.MissingPermissions):
            pass
        else:
            raise error
    
    @profile.error
    async def profile_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.errors.MissingPermissions):
            pass
        else:
            raise error

    @role.error
    async def role_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.errors.MissingPermissions):
            pass
        else:
            raise error    

    @list_role.error
    async def list_role_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.errors.MissingPermissions):
            pass
        else:
            raise error        
def setup(bot):
    bot.add_cog(Flairing(bot))