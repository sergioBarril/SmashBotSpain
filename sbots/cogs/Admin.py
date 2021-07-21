from asyncio.exceptions import CancelledError
import typing
from .params.roles import DEFAULT_TIERS, SMASH_CHARACTERS, SPANISH_REGIONS
import aiohttp
import discord
import asyncio
import random
from collections import defaultdict
from datetime import datetime, timedelta
import json
import logging

from discord.ext import tasks, commands
from discord.ext.commands.cooldowns import BucketType

from .params.matchmaking_params import (EMOJI_CONFIRM, EMOJI_LARGE_BLUE_DIAMOND, EMOJI_LARGE_ORANGE_DIAMOND, EMOJI_RECYCLE, EMOJI_REJECT, 
                    EMOJI_HOURGLASS, EMOJI_SKULL, EMOJI_SMALL_BLUE_DIAMOND, EMOJI_SMALL_ORANGE_DIAMOND, EMOJI_WHITE_MEDIUM_SMALL_SQUARE, NUMBER_EMOJIS, EMOJI_FIRE)

from .checks.flairing_checks import player_exists
from .checks.matchmaking_checks import (in_arena, in_arena_or_ranked, in_ranked, in_tier_channel)

from .aux_methods.roles import find_role, update_or_create_roles


logger = logging.getLogger('discord')

class Admin(commands.Cog):
    """
    This Cog handles the commands usable only by admins.

    They manage things like ranked points, tiers, sets...
    Roles, etc.
    """
    
    def __init__(self, bot):
        self.bot = bot
    
    # *********************
    #      R A N K E D
    # *********************

    @commands.command()    
    @commands.check(in_ranked)
    @commands.has_any_role("Dev","Admin")
    async def set_winner(self, ctx, *, winner: discord.Member):
        """
        Gives the win to the player mentioned.
        """

        if winner is None:
            logger.error(f"No winner was set.")
            return await ctx.send(f"Marca el ganador **del set** con `.set_winner @Tropped`, por ejemplo.")                
        
        guild = ctx.guild

        body = {
            'channel': ctx.channel.id,
            'winner': winner.id,
        }

        # Set winner in DB
        async with self.bot.session.post(f'http://127.0.0.1:8000/gamesets/set_winner/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                # Get winner and loser
                winner = guild.get_member(resp_body['winner_info']['player'])
                loser = guild.get_member(resp_body['loser_info']['player'])
                resp_body['winner'] = winner
                resp_body['loser'] = loser

                # End the set
                ranked = self.bot.get_cog('Ranked')
                await ranked.set_end(ctx.channel, resp_body)
            
            elif response.status == 404:                
                html = await response.text()
                logger.error(f"Error in set_winner: {html}")
                resp_body = json.loads(html)

                if error_type := resp_body.get('error'):
                    logger.error(f"Error setting set winner by admin {ctx.author.nickname()}.")
                    ERRORS = {
                        'ARENA_NOT_FOUND': 'No se encontró la arena asociada a este canal.',
                        'GAMESET_NOT_FOUND': 'No se encontró el set asociado a esta arena.',
                        'PLAYER_NOT_FOUND': 'El jugador mencionado no está jugando este set.',
                    }

                    error_message = ERRORS[error_type]
                    return await ctx.send(error_message)
            else:                
                return await ctx.channel.send("Error al marcar el ganador.")

        # Cancel other tasks
        tasks = asyncio.all_tasks()

        for task in tasks:
            if task.get_name() == f'gamesetup-{ctx.channel.id}':
                logger.info(f"Task {task.get_name()} cancelled.")
                task.cancel()        
        
        # Send feedback message
        await ctx.channel.send(f"¡**{winner.nickname()}** ha ganado el set por abandono!")        
    
    @commands.command(aliases=["add_points", "remove_points"])
    @commands.has_permissions(administrator=True)
    async def set_points(self, ctx, player : discord.Member, points):
        """
        Sets the points of the player.
        """
        if points is None:
            return await ctx.send(f"Error. Usa este comando así: `.set_points @Tropped 1800`.")
        
        # Cast points to integer
        try:
            score = int(points)
        except Exception as e:
            return await ctx.send(f"Error: `{points}` no es una cantidad de puntos válida.")

        add_mode = ctx.invoked_with == 'add_points'

        if ctx.invoked_with == "remove_points":
            add_mode = True
            score *= -1


        # Change it in DB
        
        body = {
            'player': player.id,
            'guild': ctx.guild.id,
            'points': score,
            'add': add_mode            
        }

        async with self.bot.session.post(f'http://127.0.0.1:8000/ratings/score/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)
                point_difference = int(resp_body['diff'])
                difference = f"{'+' if point_difference >= 0 else ''}{point_difference}"        
                await ctx.send(f"La puntuación de **{player.nickname()}** ha pasado a ser {resp_body['score']} ({difference}).")
            elif response.status == 404:
                html = await response.text()
                resp_body = json.loads(html)

                error_type = resp_body.get('error')

                if not error_type:
                    return await ctx.send("Error")

                logger.error(f"Error setting rating score of player {player.nickname()} by admin {ctx.author.nickname()}.")
                ERRORS = {
                    'PLAYER_NOT_FOUND': 'No se ha encontrado al jugador mencionado.',
                    'GUILD_NOT_FOUND': 'No se encontró este servidor.',
                    'RATING_NOT_FOUND': 'No se encontró el rating asociado a este jugador en este servidor.'
                }
                error_message = ERRORS[error_type]
                return await ctx.send(error_message)
            else:
                return await ctx.send("Error")


    @commands.command(aliases=['remove_promotion'])
    @commands.has_permissions(administrator=True)
    async def set_promotion(self, ctx, player : discord.Member, wins = None, losses = None):
        """
        Sets the promotion. The player must be in the threshold.
        """
        # Cast score to integer
        if ctx.invoked_with == "remove_promotion":
            wins, losses = None, None
        else:
            try:
                wins = int(wins)
                losses = int(losses)
            except Exception as e:
                return await ctx.send(f"Error: `{wins}-{losses}` no es una promoción válida de puntos válida.")               

        # Change it in DB
        
        body = {
            'player': player.id,
            'guild': ctx.guild.id,            
            'wins': wins,
            'losses': losses
        }

        async with self.bot.session.post(f'http://127.0.0.1:8000/ratings/promotion/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)
                new_wins = resp_body.get('wins')
                new_losses = resp_body.get('losses')
                
                if new_wins:
                    promo_text = f"La promoción de **{player.nickname()}** ha pasado a ser {new_wins}-{new_losses}."
                
                else:
                    promo_text = f"**{player.nickname()}** ya no está en promoción."
                
                await ctx.send(promo_text)
            elif response.status == 404:
                html = await response.text()
                resp_body = json.loads(html)

                error_type = resp_body.get('error')

                if not error_type:
                    return await ctx.send("Error")

                logger.error(f"Error setting promotion score of player {player.nickname()} by admin {ctx.author.nickname()}.")
                ERRORS = {
                    'PLAYER_NOT_FOUND': 'No se ha encontrado al jugador mencionado.',
                    'GUILD_NOT_FOUND': 'No se encontró este servidor.',
                    'RATING_NOT_FOUND': 'No se encontró el rating asociado a este jugador en este servidor.'
                }
                error_message = ERRORS[error_type]
                return await ctx.send(error_message)
            else:
                return await ctx.send("Error")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_tier(self, ctx, player : discord.Member, tier : discord.Role):
        guild = ctx.guild
        
        body = {
            'guild': guild.id,            
            'tier': tier.id,
        }

        async with self.bot.session.post(f'http://127.0.0.1:8000/players/{player.id}/tier/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                # Get info
                old_tier_id = resp_body.get('old_tier')
                if old_tier_id:
                    old_tier = guild.get_role(old_tier_id)
                
                new_tier_id = resp_body.get('tier')
                new_tier = guild.get_role(new_tier_id)

                score = resp_body.get('score')                
                
                # Change tiers
                if old_tier_id:
                    await player.remove_roles(old_tier)
                
                await player.add_roles(new_tier)

                # Send message
                if old_tier_id:
                    text = f"**{player.nickname()}** ha pasado de ser **{old_tier.name}** a ser **{new_tier.name}**, "
                else:
                    text = f"**{player.nickname()}** será a partir de ahora **{new_tier.name}**, "
                
                text += f"con una puntuación de {score}."
                
                await ctx.send(text)
            elif response.status == 404:
                html = await response.text()
                resp_body = json.loads(html)

                error_type = resp_body.get('error')

                if not error_type:
                    return await ctx.send("Error")

                logger.error(f"Error setting tier of player {player.nickname()} by admin {ctx.author.nickname()}.")
                ERRORS = {
                    'PLAYER_NOT_FOUND': 'No se ha encontrado al jugador mencionado.',
                    'GUILD_NOT_FOUND': 'No se encontró este servidor.',
                    'TIER_NOT_FOUND': 'No se encontró la Tier seleccionada.'
                }
                error_message = ERRORS[error_type]
                return await ctx.send(error_message)
            else:
                return await ctx.send("Error")


    @commands.command()
    @commands.has_permissions(administrator=True)
    async def beta_reward(self, ctx):
        """
        Deletes all gamesets, resets ratings and gives extra points to testers
        """
        guild = ctx.guild
        tester_role = discord.utils.get(guild.roles, name="Beta Tester")

        async with self.bot.session.post(f'http://127.0.0.1:8000/guilds/{guild.id}/beta_reward/') as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                testers = resp_body['testers']

                tester_message = "**Testers:**\n"
                
                for idx, tester_info in enumerate(testers, start=1):
                    player = guild.get_member(tester_info['player'])
                    await player.add_roles(tester_role)
                    tester_message += f"{idx}. **{player.nickname()}** ({tester_info['sets']})\n"
                                
                await ctx.send(tester_message)

                # Update leaderboards
                tiers = resp_body['tiers']
                ranked = self.bot.get_cog('Ranked')
                
                for tier_id in tiers:
                    tier_role = guild.get_role(tier_id)
                    asyncio.create_task(ranked.update_leaderboard(tier_role))            
            else:
                logger.error("Error with beta rewards")
                logger.error(response)
                return await ctx.send(f"Error al dar los rewards de la beta.")


    @commands.command()
    @commands.has_any_role("Dev","Admin")
    async def leaderboard(self, ctx, tier : discord.Role):
        """
        Update the leaderboard of the mentioned tier
        """
        ranked = self.bot.get_cog('Ranked')
        updated = await ranked.update_leaderboard(tier)

        if updated:
            return await ctx.send(f"La leaderboard de la tier {tier.name} ha sido actualizada.", delete_after=10)
        else:
            return await ctx.send(f"No se ha podido actualizar la leaderboard.", delete_after=10)

    # **********************
    #     T A S K S
    # **********************
    
    @commands.command()
    @commands.has_any_role("Dev","Admin")
    async def cancel_task(self, ctx, name):
        """
        Cancel a task with the given name
        """
        tasks = asyncio.all_tasks()
        for task in tasks:
            if task.get_name() == name:
                task.cancel()
        await ctx.send(f"Task {name} cancelada.")

    @commands.command()
    @commands.has_any_role("Dev","Admin")
    async def check_tasks(self, ctx):
        """
        Prints all current tasks (of all guilds)
        """
        tasks = asyncio.all_tasks()
        tasks_name = [task.get_name() for task in tasks]
        await ctx.send(tasks_name)


    # ***************************
    #   G U I L D  P A R A M S
    # ***************************
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
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

    # ***********************
    #      F L A I R I N G
    # ***********************
    
    @commands.command(aliases=["create_roles", "update_roles"])
    @commands.has_permissions(administrator=True)
    async def setup_roles(self, ctx, role_type=None):
        """
        Creates the Discord roles in the guild.
        """
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

    @commands.command(aliases=['import'])
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def import_roles(self, ctx, *, role_type=None):
        """
        Saves the roles in the DB
        """
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
    
    @check_tasks.error
    async def check_tasks_error(self, ctx, error):            
        if isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.errors.MissingPermissions):
            pass
        else:
            raise error
        
    @tier_channel.error
    async def role_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.errors.MissingPermissions):
            pass
        else:
            raise error

def setup(bot):
    bot.add_cog(Admin(bot))