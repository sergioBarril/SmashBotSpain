from asyncio.exceptions import CancelledError
import aiohttp
import discord
import asyncio
import time
import re
import itertools
import typing
import traceback
import random
from collections import defaultdict
from datetime import datetime, timedelta
import json
import logging

from discord.ext import tasks, commands
from discord.ext.commands.cooldowns import BucketType

from .params.matchmaking_params import (EMOJI_CONFIRM, EMOJI_REJECT, 
                    EMOJI_HOURGLASS, NUMBER_EMOJIS)

from .checks.flairing_checks import player_exists
from .checks.matchmaking_checks import (in_arena, in_arena_or_ranked, in_ranked, in_tier_channel)

from .aux_methods.roles import find_role


logger = logging.getLogger('discord')

class Ranked(commands.Cog):
    """
    This Cog handles the sets of ranked matches.
    """
    
    def __init__(self, bot):
        self.bot = bot
    
    def game_title(self, game_number):
        """
        Returns the text to write the corresponding title.
        """
        return f'*******************\n     G A M E  {game_number}\n*******************'

    async def game_setup(self, player1, player2, channel, game_number):
        asyncio.current_task().set_name(f"gamesetup-{channel.id}")        
        await channel.send(f'```{self.game_title(game_number)}\n```')
        is_first = game_number == 1

        if is_first:
            await channel.send(f'Escoged personajes -- os he enviado un MD.')
        else:
            async with self.bot.session.get(f'http://127.0.0.1:8000/players/{player1.id}/score/') as response:
                if response.status == 200:
                    html = await response.text()
                    resp_body = json.loads(html)

                    p1_wins = resp_body['player_wins']
                    p2_wins = resp_body['other_player_wins']
                
                    await channel.send(f"El contador está **{player1.nickname()}** {p1_wins} - {p2_wins} **{player2.nickname()}**.")

        guild = channel.guild
        players = (player1, player2)

        guild_roles = await guild.fetch_roles()

        if is_first:
            await asyncio.gather(*[asyncio.create_task(self.character_pick(player, guild, channel, blind=is_first)) for player in players])
            last_winner = None
        else:
            body = {'player_id': player1.id}
            
            async with self.bot.session.get(f'http://127.0.0.1:8000/games/last_winner/', json=body) as response:
                if response.status == 200:
                    html = await response.text()
                    resp_body = json.loads(html)                    
                    last_winner = channel.guild.get_member(resp_body['last_winner'])
                else:
                    html = await response.text()
                    await channel.send("Error al buscar el ganador del último game.")
                    logger.error(f"Error in last_winner call: {html}")
                    return
            
                await asyncio.create_task(self.character_pick(last_winner, guild, channel, blind=False))
                other_player = player1 if last_winner == player2 else player2
                await asyncio.create_task(self.character_pick(other_player, guild, channel, blind=False))                            

        # Get characters
        async with self.bot.session.get(f'http://127.0.0.1:8000/players/{player1.id}/game_info/') as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                game_players = resp_body['game_players']
                
            else:
                html = await response.text()
                await channel.send("No estás jugando ninguna partida.")
                logger.error(f"Error in game_info: {html}")
                return
        
        # Show characters info
        players_info = []
        for gp in game_players:
            player = guild.get_member(gp['player'])
            char_role = find_role(gp['character'], guild_roles, only_chars=True)
            
            players_info.append({
                'player' : player,
                'char_role' : char_role
            })

        text = f"**Game {game_number}:**   "
        text += " vs. ".join([f"{player['player'].nickname()} ({player['char_role'].emoji()})" for player in players_info])
        await channel.send(text)

        # Stage
        stage_ok = await asyncio.create_task(self.stage_strike(player1, player2, channel, is_first, last_winner))

        if not stage_ok:
            return False
        
        # Winner
        set_finished = await asyncio.create_task(self.game_winner(player1, player2, channel, players_info, game_number))
        
        if set_finished:
            await channel.send(f"Podéis seguir jugando en esta arena para hacer freeplays. Cerradla usando `.ggs` cuando acabéis.")
        elif set_finished is None:
            return False
        else:
            asyncio.create_task(self.game_setup(player1, player2, channel, game_number + 1))



    async def game_winner(self, player1, player2, channel, players_info, game_number):
        """
        Choose the game's winner     
        """
        asyncio.current_task().set_name(f"winner-{channel.id}")

        players = player1, player2
        text = f"Ya podéis empezar el Game {game_number}. Cuando acabéis, reaccionad ambos con el personaje del gandor.\n"
        text += "\n".join([f"{i + 1}. {player_info['player'].nickname()} {player_info['char_role'].emoji()}" for i, player_info in enumerate(players_info)])
        
        message = await channel.send(text)

        emojis = [player_info['char_role'].emoji() for player_info in players_info]
        
        # If it's a ditto, use number emojis instead
        if emojis[0] == emojis[1]:
            emojis = [NUMBER_EMOJIS[0], NUMBER_EMOJIS[1]]
        
        # React to message
        emoji_tasks = [asyncio.create_task(message.add_reaction(emoji)) for emoji in emojis]
        asyncio.gather(*emoji_tasks)

        # Wait for an agreement
        decided = False
        while not decided:
            def check(payload):
                return str(payload.emoji) in emojis and payload.message_id == message.id and payload.member in players

            # Wait for a reaction, and remove the other one
            raw_reaction = await self.bot.wait_for('raw_reaction_add', check=check)
            reacted_emoji = str(raw_reaction.emoji)

            other_emoji = emojis[0] if reacted_emoji == emojis[1] else emojis[1]
            await message.remove_reaction(other_emoji, raw_reaction.member)

            # Refetch message
            message = await channel.fetch_message(message.id)
        
            # Check if agreement is reached
            reactions = message.reactions            
            winner_emoji = None
            for reaction in reactions:                
                if str(reaction.emoji) not in emojis:
                    continue
                if reaction.count == 3:                    
                    winner_emoji = str(reaction.emoji)
                    decided = True
                    break
        
        # Get winner
        winner = None
        for player_info in players_info:
            if player_info['char_role'].emoji() == winner_emoji:
                winner = player_info['player']
                break        
        if winner is None:
            i = NUMBER_EMOJIS.index(winner_emoji)
            winner = players_info[i]['player']
        
        # Set winner in DB
        async with self.bot.session.post(f'http://127.0.0.1:8000/players/{winner.id}/win_game/') as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                finished = resp_body['finished']
            else:
                await channel.send("Error al guardar la persona ganadora.")
                return None
        
        # Send feedback message
        await channel.send(f"¡**{winner.nickname()}** {winner_emoji} ha ganado el **Game {game_number}**!")
        return finished

    async def stage_strike(self, player1, player2, channel, is_first, last_winner):        
        asyncio.current_task().set_name(f"stagestrike-{channel.id}")

        # Get stages
        async with self.bot.session.get(f'http://127.0.0.1:8000/stages/') as response:
            if response.status == 200:
                html = await response.text()
                stages = json.loads(html)
            else:
                html = await response.text()
                await channel.send("Error al buscar los escenarios.")
                logger.error(f"Error in get stages: {html}")
                return False
        
        if is_first:
            stages = [stage for stage in stages if stage.get('type', '') == 'STARTER']

        def get_stage_text(next_player, open_stages, mode):
            """
            Returns the text that the message should be changed to.
            """
            action = "banear" if mode == "BAN" else "pickear"            

            text = f"Le toca **{action.upper()}** a {next_player.mention}. Reacciona con el número de stage que quieres {action.lower()}.\n"
            text += "\n".join([f"{r'~~' if stage not in open_stages else ''}{i + 1}.\
                {stage['emoji']} {stage['name']}{r'~~' if stage not in open_stages else ''}"
                for i, stage in enumerate(stages)])
            return text

        # Decide who bans first
        ban_order = []
        
        if is_first:
            players = [player1, player2]
            first_ban = players.pop(random.randint(0, 1))
            other_player = players[0]
            ban_order = [first_ban, other_player, other_player, first_ban]
        else:
            first_ban = last_winner
            other_player = player1 if first_ban.id == player2.id else player2            
            ban_order = [first_ban, first_ban, first_ban, other_player]
        
        open_stages = list(stages.copy())
        open_emojis = list(NUMBER_EMOJIS[:len(open_stages)])

        # Send bans message
        message = await channel.send(get_stage_text(first_ban, open_stages, mode="BAN"))

        # React to message
        emoji_tasks = [asyncio.create_task(message.add_reaction(emoji)) for emoji in open_emojis]
        asyncio.gather(*emoji_tasks)
        
        # STRIKE PROCESS
        mode = "BAN"
        for idx, strike_player in enumerate(ban_order):
            def check(payload):
                return str(payload.emoji) in open_emojis and payload.message_id == message.id and payload.user_id == strike_player.id

            raw_reaction = await self.bot.wait_for('raw_reaction_add', check=check)
            
            # Clear emojis
            emoji = str(raw_reaction.emoji)
            open_emojis.remove(emoji)            

            #  Update open_stages
            if mode != "PICK":                
                open_stages = list(filter(lambda x: NUMBER_EMOJIS[stages.index(x)] != emoji, open_stages))

            # Get next player
            if idx + 1 < len(ban_order):
                next_player = ban_order[idx + 1]
                
                # Last element in ban_order is actually pick if not is_first
                mode = "PICK" if idx + 2 == len(ban_order) and not is_first else "BAN"
                
                # Update message
                text = get_stage_text(next_player, open_stages, mode=mode)                
                await message.edit(content=text)
            else:
                if not mode:
                    mode = "BAN"
                text = get_stage_text(ban_order[-1], open_stages, mode=mode)
                await message.edit(content=text)
        
        if is_first:
            stage = open_stages[0]
        else:
            stage = list(filter(lambda x: NUMBER_EMOJIS[stages.index(x)] == emoji, open_stages))[0]

        
        # SET STAGE
        body = {
            'player_id' : player1.id,
            'stage_name': stage['name']
        }

        async with self.bot.session.post(f'http://127.0.0.1:8000/games/stage/', json=body) as response:
            if response.status == 200:                
                await channel.send(f"El combate tendrá lugar en **{stage['name']}** {stage['emoji']}")
                await message.clear_reactions()
                return True
            else:
                html = await response.text()
                await channel.send("Error al guardar el escenario.")
                logger.error(f"Error in set stages.")
                return False




    @commands.command()
    async def play(self, ctx, *, character_name):
        """
        Command to pick a character in case it's not in the reactions.
        """
        player = ctx.author
        guild = ctx.guild
        is_blind = guild is None

        channel = ctx.channel

        # Get guild id if in DMs
        if not guild:
            async with self.bot.session.get(f'http://127.0.0.1:8000/players/{player.id}/game_info/') as response:
                if response.status == 200:
                    html = await response.text()
                    resp_body = json.loads(html)

                    # Get guild
                    guild_id = resp_body['guild']
                    guild = self.bot.get_guild(guild_id)

                    # Get channel
                    channel_id = resp_body['channel_id']
                    if channel_id:
                        channel = guild.get_channel(channel_id)
                    else:
                        channel = None

                else:
                    html = await response.text()
                    await ctx.send("No estás jugando ninguna partida.")
                    logger.error(f"Error in .play: {html}")
                    return
        
        # Check that the character is legit
        guild_roles = await guild.fetch_roles()
        character_role = find_role(character_name, guild_roles, only_chars=True)        

        if not character_role:
            return await ctx.send(f"No se ha encontrado el personaje {character_name}.")
        
        # Check that a char pick is being asked
        tasks = asyncio.all_tasks()
        is_asked = False

        task_to_cancel =  None        
        for task in tasks:            
            if task.get_name().startswith(f'charpick-{player.id}'):
                split_task_name = task.get_name().split('-')
                message_id = split_task_name[-1] if len(split_task_name) == 3 else None
                is_asked = True
                task_to_cancel = task
                
        # SAVE THE CHOICE IN THE DATABASE
        if is_asked:
            body = {'character' : character_role.name}
            
            async with self.bot.session.post(f'http://127.0.0.1:8000/players/{player.id}/character/', json=body) as response:
                if response.status == 200:
                    message_text = f"**{player.nickname()}** ha elegido a {character_role.name} {character_role.emoji()}."
                    
                    if message_id:
                        message = await ctx.channel.fetch_message(message_id)
                        await message.edit(content=message_text)
                        await message.clear_reactions()
                    else:
                        await ctx.send(message_text)
                    
                    await ctx.message.delete()                    
                    task_to_cancel.cancel()
                    if is_blind:                        
                        return await ctx.send(f"Ya puedes volver a {channel.mention if channel else 'la arena'}.")
                else:
                    html = await response.text()
                    logger.error(f"Error saving character choice.")
                    return await ctx.send("Ha habido un error al guardar el personaje.")
            
        else:
            return await ctx.send("Usa este comando solo cuando se te pida.", delete_after=60)
    
    async def character_pick(self, player, guild, channel, blind = False):
        """
        Handles the menu to choose a character. If blind is True, this is done in DMs.
        """
        try:
            asyncio.current_task().set_name(f"charpick-{player.id}")
            if blind:
                arena = channel
                channel = player
            
            text_message = f"{player.mention}, r" if not blind else 'R'
            text_message += f'eacciona con el personaje que vas a jugar. Si no vas a jugar mains, seconds o pockets, selecciónalo así: `.play luigi`.'
            message = await channel.send(text_message)

            asyncio.current_task().set_name(f"charpick-{player.id}-{message.id}")
            
            body = {
                'guild' : guild.id
            }
            
            # GET CHARACTERS
            async with self.bot.session.get(f'http://127.0.0.1:8000/players/{player.id}/profile/', json=body) as response:
                if response.status == 200:
                    html = await response.text()
                    resp_body = json.loads(html)                
                    
                    mains = resp_body['mains']
                    seconds = resp_body['seconds']
                    pockets = resp_body['pockets']

                    characters = mains + seconds + pockets
                    char_roles = [guild.get_role(role_id) for role_id in characters]
                    char_emojis = [char_role.emoji() for char_role in char_roles]
                else:
                    return await channel.send("Ha habido un error. Prueba usando `.play`.")
            
            # ADD REACTIONS AND WAIT        
            emoji_tasks = [asyncio.create_task(message.add_reaction(emoji)) for emoji in char_emojis if emoji]
            asyncio.gather(*emoji_tasks)

            def check(payload):
                return str(payload.emoji) in char_emojis and payload.message_id == message.id and payload.user_id == player.id

            raw_reaction = await self.bot.wait_for('raw_reaction_add', check=check)

            i = char_emojis.index(str(raw_reaction.emoji))
            chosen_char = char_roles[i]

            await message.edit(content=f"**{player.nickname()}** ha elegido a {chosen_char.name} {chosen_char.emoji()}.")

            body = {
                'character': chosen_char.name
            }
        
            # SAVE THE CHOICE IN THE DATABASE
            async with self.bot.session.post(f'http://127.0.0.1:8000/players/{player.id}/character/', json=body) as response:
                if response.status == 200:
                    html = await response.text()                    
                    if blind:
                        await channel.send(f"Ya puedes volver a la arena: {arena.mention}.")
                else:
                    html = await response.text()
                    logger.error(f"Error saving character choice with character_pick")
                    return await channel.send("Ha habido un error al guardar el personaje.")        
            
            # CLEAR_REACTIONS
            await message.clear_reactions()        
            return True
        except CancelledError as e:
            # Check if it was cancelled with play
            async with self.bot.session.get(f'http://127.0.0.1:8000/players/{player.id}/game_info/') as response:
                if response.status == 200:
                    html = await response.text()
                    resp_body = json.loads(html)
                    game_players = resp_body['game_players']
                else:
                    raise

            if list(filter(lambda x: x['character'] is None and x['player'] == player.id, game_players)):
                raise                


    @commands.command()
    @commands.check(in_ranked)
    @commands.cooldown(1, 15, BucketType.channel)
    async def remake(self, ctx):
        """
        Restart last game.
        """
        body = {
            'player_id': ctx.author.id
        }
        
        async with self.bot.session.post(f'http://127.0.0.1:8000/games/remake/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                game_number = resp_body['game_number']
                other_player_id = resp_body['other_player_id']
            else:
                return await ctx.send("Error haciendo el remake.")
        
        # Cancel game task
        tasks = asyncio.all_tasks()

        for task in tasks:
            if task.get_name() == f'gamesetup-{ctx.channel.id}':
                logger.info(f"Task {task.get_name()} cancelled.")
                task.cancel()

        # Get other player
        other_player = ctx.guild.get_member(other_player_id)
        
        # Restart the game
        await ctx.send(f"Remaking game {game_number}...")
        logger.info(f"Remaking game {game_number} for arena between {ctx.author.nickname()} and {other_player.nickname()}")
        asyncio.create_task(self.game_setup(ctx.author, other_player, ctx.channel, game_number))


    @commands.command()
    async def cancel_task(self, ctx, name):
        tasks = asyncio.all_tasks()
        for task in tasks:
            if task.get_name() == name:
                task.cancel()
        await ctx.send(f"Task {name} cancelada.")
    
    @remake.error
    async def remake_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.errors.MissingPermissions):
            pass
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Calma, calma. No puedes volver a usar el comando `.remake` hasta dentro de {round(error.retry_after, 2)}s.")
        else:
            logger.error(f'Error: {error}')
            raise error


def setup(bot):
    bot.add_cog(Ranked(bot))