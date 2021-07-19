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

from .params.matchmaking_params import (EMOJI_CONFIRM, EMOJI_LARGE_BLUE_DIAMOND, EMOJI_LARGE_ORANGE_DIAMOND, EMOJI_RECYCLE, EMOJI_REJECT, 
                    EMOJI_HOURGLASS, EMOJI_SKULL, EMOJI_SMALL_BLUE_DIAMOND, EMOJI_SMALL_ORANGE_DIAMOND, EMOJI_WHITE_MEDIUM_SMALL_SQUARE, NUMBER_EMOJIS, EMOJI_FIRE)

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

    @commands.command(aliases=["ff"])
    @commands.check(in_ranked)
    async def surrender(self, ctx):
        """
        Surrenders the set.
        """
        guild = ctx.guild
        player = ctx.author

        # Cancel other tasks
        tasks = asyncio.all_tasks()

        for task in tasks:
            if task.get_name() == f'gamesetup-{ctx.channel.id}':
                logger.info(f"Task {task.get_name()} cancelled.")
                task.cancel()
            
        # Surrender in DB
        async with self.bot.session.post(f'http://127.0.0.1:8000/players/{player.id}/surrender/') as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                # Get winner and loser
                winner = guild.get_member(resp_body['winner_info']['player'])
                loser = guild.get_member(resp_body['loser_info']['player'])                 
                resp_body['winner'] = winner
                resp_body['loser'] = loser                
            elif response.status == 400:
                return await ctx.channel.send("No estás jugando ninguna ranked... ¡así que no te rindas!")
            else:
                logger.error("Error in .surrender")
                await ctx.channel.send("Error al rendirse.")
                return None
        
        # Send feedback message
        await ctx.channel.send(f"¡**{winner.nickname()}** ha ganado el set por abandono!")

        await self.set_end(ctx.channel, resp_body)

    @commands.command()
    async def leaderboard(self, ctx, tier : discord.Role):
        updated = await self.update_leaderboard(tier)

        if updated:
            return await ctx.send(f"La leaderboard de la tier {tier.name} ha sido actualizada.", delete_after=10)
        else:
            return await ctx.send(f"No se ha podido actualizar la leaderboard.", delete_after=10)
            
    async def rematch(self, player1, player2, channel, message):
        """
        Handles the confirmation for rematch.
        """
        guild = channel.guild
        players = player1, player2
        
        # WAIT FOR REACTIONS
        emoji = EMOJI_RECYCLE
        await message.add_reaction(emoji)        

        # Wait for an agreement
        decided = False
        while not decided:
            def check(payload):
                return str(payload.emoji) == emoji and payload.message_id == message.id and payload.member in players

            # Wait for a reaction, and remove the other one
            raw_reaction = await self.bot.wait_for('raw_reaction_add', check=check)
            reacted_emoji = str(raw_reaction.emoji)            

            # Refetch message
            message = await channel.fetch_message(message.id)
        
            # Check if agreement is reached
            reactions = message.reactions  
            winner_emoji = None
            for reaction in reactions:                
                if str(reaction.emoji) != emoji:
                    continue
                if reaction.count == 3:                    
                    decided = True
                    break
        
        # DO REMATCH
        async with self.bot.session.get(f'http://127.0.0.1:8000/players/{player1.id}/rematch/') as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                player1_id = resp_body['player1']
                player2_id = resp_body['player2']

                player1 = guild.get_member(player1_id)
                player2 = guild.get_member(player2_id)
            
            else:
                return await channel.send("Error al intentar hacer rematch. Probablemente ya hayáis jugado demasiado hoy.")
        
        await channel.send("Perfecto, ¡ahí va la revancha!")
        asyncio.create_task(self.game_setup(player1, player2, channel, 1))


    async def update_leaderboard(self, tier):
        """
        Updates the leaderboard message of the given tier
        """
        if not tier:
            logger.error("No tier to update.")
            return False
        
        async with self.bot.session.get(f'http://127.0.0.1:8000/tiers/{tier.id}/leaderboards/') as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)
            else:
                return False
                
        text = ""
        guild = tier.guild
        players = resp_body.get('players')
        
        embed = discord.Embed(title=f"**__{tier.name}__**", colour=tier.color)        
        embed.set_footer(text="SmashBotSpain", icon_url="https://www.smashbros.com/assets_v2/img/top/hero05_en.jpg")
        
        if not players:
            text += "No hay nadie en esta tier... ¡de momento!"
            embed.set_image(url='https://media.giphy.com/media/3oriff4xQ7Oq2TIgTu/giphy.gif')

        for player_info in players:
            player = guild.get_member(player_info['id'])
            rating = player_info['rating']
            streak = player_info['streak']
            
            promotion_info = player_info['promotion_info']
            promotion_wins = promotion_info['wins'] if promotion_info else None
            promotion_losses = promotion_info['losses'] if promotion_info else None            
            
            emoji_dict = {
                0 : EMOJI_WHITE_MEDIUM_SMALL_SQUARE,
                1 : EMOJI_SMALL_ORANGE_DIAMOND,
                -1 : EMOJI_SMALL_BLUE_DIAMOND,                
                2 : EMOJI_LARGE_ORANGE_DIAMOND,
                -2 : EMOJI_LARGE_BLUE_DIAMOND,
            }
            
            if streak >= 3:
                emoji = EMOJI_FIRE
            elif streak <= -3:
                emoji = EMOJI_SKULL
            else:
                emoji = emoji_dict.get(streak)


            text += f" {emoji} "
            
            text += f"**{player.nickname()}** (_{rating}_) "


            if promotion_info:
                text += f" **[{promotion_wins} - {promotion_losses}]**"
            
            text += "\n"
        

        embed.add_field(name="Jugadores", value=text, inline=False)
        leaderboard_channel = guild.get_channel(resp_body['leaderboard_channel'])
        leaderboard_message = await leaderboard_channel.fetch_message(resp_body['leaderboard_message'])

        # Edit the message
        await leaderboard_message.edit(content="", embed=embed)
        logger.info(f"{tier.name} leaderboard updated.")
        return True


    async def rating_response(self, player, guild, info):
        """
        Returns the text to send after a set, regarding a specific player.
        """
        is_promoted = info.get('promoted')
        is_demoted = info.get('demoted')
        
        is_win = is_promoted is not None

        is_promotion = info['promotion']['wins'] is not None
        is_promotion_cancelled = info.get('promotion_cancelled')
        
        # Update leaderboards        
        old_tier = guild.get_role(info['tier']['old_id'])
        asyncio.create_task(self.update_leaderboard(old_tier))
        
        if is_promoted or is_demoted:
            new_tier = guild.get_role(info['tier']['new_id'])
            asyncio.create_task(self.update_leaderboard(new_tier))

            await player.remove_roles(old_tier)
            await player.add_roles(new_tier)

        if is_promoted:
            return f"¡Felicidades, **{player.nickname()}**! Pasas a ser {new_tier.mention}. Ve al canal a saludar :)"                
        
        if is_demoted:            
            return f"**{player.nickname()}**, has caído a {new_tier.mention}... ¡pero no te desanimes! Seguro que en breves vuelves a subir."
        
        if is_promotion:                    
            promotion_info = info['promotion']

            if promotion_info['wins'] == 0 and promotion_info['losses'] == 0:
                return f"¡Felicidades, **{player.nickname()}**! Acabas de entrar en promoción para la siguiente tier. Gana 3 de los próximos 5 sets (contra gente de esa tier), ¡y subirás!"                                                
            return f"La promoción de **{player.nickname()}** va {promotion_info['wins']} - {promotion_info['losses']}."
        
        if is_promotion_cancelled:
            return f"**{player.nickname()}**, no has superado la promoción. Te quedas en esta tier con {info['score']['new']} puntos."
                        
        return f"La puntuación de **{player.nickname()}** ha pasado a **{info['score']['new']}** ({'+' if is_win else '-'}{abs(info['score']['new'] - info['score']['old'])})."


    async def score(self, player):
        """
        Returns the information of the current score in the game
        """
        async with self.bot.session.get(f'http://127.0.0.1:8000/players/{player.id}/score/') as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                p1_wins = resp_body['player_wins']
                p2_wins = resp_body['other_player_wins']
                
                return resp_body

    async def game_setup(self, player1, player2, channel, game_number):
        asyncio.current_task().set_name(f"gamesetup-{channel.id}")        
        await channel.send(f'```{self.game_title(game_number)}\n```')
        is_first = game_number == 1

        if is_first:
            await channel.send(f'Escoged personajes -- os he enviado un MD.')
        else:
            score = await self.score(player1)
            p1_wins = score['player_wins']
            p2_wins = score['other_player_wins']
            
            await channel.send(f"El marcador está **{player1.nickname()}** {p1_wins} - {p2_wins} **{player2.nickname()}**.")

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
        game_end = await asyncio.create_task(self.game_winner(player1, player2, channel, players_info, game_number))
        
        if game_end is None:
            return False

        set_finished =  game_end['set_finished']
        
        if set_finished:
            await self.set_end(channel, game_end)
        elif set_finished is None:
            return False
        else:
            asyncio.create_task(self.game_setup(player1, player2, channel, game_number + 1))

    async def set_end(self, channel, info):
        """
        Handles the end of a set (message sending, tier changes, ratings, etc.) or creating a new game
        """
        guild = channel.guild
        
        # New scores:
        winner = info['winner']
        loser = info['loser']

        score = await self.score(winner)
        p1_wins = score['player_wins']
        p2_wins = score['other_player_wins']
            
        await channel.send(f"¡Se acabó! **{winner.nickname()}** gana el set {p1_wins} - {p2_wins} contra **{loser.nickname()}**.")

        winner_info = info['winner_info']
        loser_info = info['loser_info']

        rating_text = await self.rating_response(winner, guild, winner_info)
        rating_text += "\n" + await self.rating_response(loser, guild, loser_info)            

        await channel.send(rating_text)

        if info['can_rematch']:
            message = await channel.send(f"Todavía podéis jugar un set de ranked más hoy. Reaccionad ambos a este mensaje con {EMOJI_RECYCLE} para jugar otro set.")
            await channel.send(f"Si no, podéis seguir jugando en esta arena para hacer freeplays. Cerradla usando `.ggs` cuando acabéis.")
            await self.rematch(winner, loser, channel, message)
        
        await channel.send(f"Podéis seguir jugando en esta arena para hacer freeplays. Cerradla usando `.ggs` cuando acabéis.")



    async def game_winner(self, player1, player2, channel, players_info, game_number):
        """
        Choose the game's winner     
        """
        asyncio.current_task().set_name(f"winner-{channel.id}")

        players = player1, player2
        text = f"Ya podéis empezar el Game {game_number}. Cuando acabéis, reaccionad ambos con el personaje del gandor.\n"
        text += "__**GANADOR**__\n"
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

                loser = player1 if winner == player2 else player2
                resp_body['winner'] = winner
                resp_body['loser'] = loser
                
            else:
                await channel.send("Error al guardar la persona ganadora.")
                return None
        
        # Send feedback message
        await channel.send(f"¡**{winner.nickname()}** {winner_emoji} ha ganado el **Game {game_number}**!")
        return resp_body

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
                        
                        if not is_blind:
                            await message.clear_reactions()
                    else:
                        await ctx.send(message_text)
                    
                    if not is_blind:
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
            if not blind:
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
    

    @commands.command(aliases=["estadisticas"])
    @commands.check(player_exists)
    @commands.guild_only()    
    async def stats(self, ctx):
        guild = ctx.guild
        player = ctx.author

        body = {
            'guild' : guild.id
        }

        # GET ROLE
        async with self.bot.session.get(f'http://127.0.0.1:8000/players/{player.id}/stats/', json=body) as response:
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