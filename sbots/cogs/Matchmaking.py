import aiohttp
import discord
import asyncio
import time
import re
import itertools
import typing
import traceback
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

logger = logging.getLogger('discord')

class Matchmaking(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.arena_invites = defaultdict(list)
    
    async def setup_matchmaking(self):        
        self.reset_matchmaking.start()
        await self.reset_arenas(startup=True)
        await self.ranked_messages()

    async def wait_ranked_emojis(self, message):
        def check(payload):
            return str(payload.emoji) in [EMOJI_CONFIRM, EMOJI_REJECT] and payload.message_id == message.id and payload.user_id != self.bot.user.id        
        
        await asyncio.gather(message.add_reaction(EMOJI_CONFIRM), message.add_reaction(EMOJI_REJECT))
        logger.info(f"Ranked message in guild {message.guild} ready.")
        while True:
            raw_reaction = await self.bot.wait_for('raw_reaction_add', check=check)
            asyncio.create_task(message.remove_reaction(raw_reaction.emoji, raw_reaction.member))
            logger.info(f"{raw_reaction.member.nickname()} ha reaccionado con {'ACEPTAR' if str(raw_reaction.emoji) == EMOJI_CONFIRM else 'RECHAZAR'}")

            if str(raw_reaction.emoji) == EMOJI_CONFIRM:
                asyncio.create_task(self.rankeds(raw_reaction.member, message.channel))
            else:
                asyncio.create_task(self.cancel(raw_reaction.member, message.guild, "RANKED", message.channel))

    async def ranked_messages(self):
        guilds = []
        async with self.bot.session.get(f'http://127.0.0.1:8000/guilds/ranked_messages/') as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)
                guilds = resp_body.get('guilds')
        
        if not guilds:
            return logger.error("ERROR - No guilds available.")
        
        messages = []
        
        for guild_info in guilds:
            guild = self.bot.get_guild(guild_info['guild_id'])
            channel = guild.get_channel(guild_info['channel_id'])
            message = await channel.fetch_message(guild_info['message_id'])
            messages.append(message)

        wait_tasks = [asyncio.create_task(self.wait_ranked_emojis(message)) for message in messages]
        
        await asyncio.gather(*wait_tasks)

    async def rankeds(self, member, channel):
        player = member
        guild = member.guild        

        body = {
            'guild': guild.id,            
            'created_by' : player.id,            
            'mode': 'RANKED'
        }
        
        # CHECK PLAYER IS CREATED, ELSE DO IT
        async with self.bot.session.get(f'http://127.0.0.1:8000/players/{player.id}') as response:
            if response.status != 200:
                flairing = self.bot.get_cog('Flairing')
                await flairing.register(player, guild)

        async with self.bot.session.post('http://127.0.0.1:8000/arenas/ranked/', json=body) as response:            
            # MATCH FOUND OR STARTED SEARCHING
            if response.status == 201:
                html = await response.text()
                resp_body = json.loads(html)
                
                if resp_body['match_found']:
                    player1 = guild.get_member(resp_body['player_one'])
                    player2 = guild.get_member(resp_body['player_two'])

                    messages = []
                    tier_role = guild.get_role(resp_body['tier'])
                    message = await channel.send(f"¡Match de ranked encontrado en **{tier_role.name}**! Mirad vuestros DMs y confirmad.")
                    messages.append({'id': message.id, 'channel_id': channel.id, 'arena': resp_body['id'], 'mode': 'RANKED'})                    
                    await self.save_messages(messages)
                    
                    return await self.matchmaking(channel, player1, player2, ranked=True)

                else:
                    mention_messages = []

                    tier_role = guild.get_role(resp_body['tier'])
                    message = await channel.send(f"{tier_role.mention}, ¡hay **alguien** buscando partida ranked! Reacciona al mensaje inicial para buscar partida tú también.")
                    mention_messages.append({'id': message.id, 'channel_id': channel.id, 'arena': resp_body['id'], 'mode': 'RANKED'})
                    
                    await self.save_messages(mention_messages)                    
                    await self.update_list_message(guild=guild)
            
            # STATUS_CONFLICT ERROR
            elif response.status == 409:
                html = await response.text()

                error_messages = {
                    "CONFIRMATION" : "¡Tienes una partida pendiente de ser aceptada! Mira tus MDs.",
                    "ACCEPTED" : "Ya has aceptado tu partida, pero tu rival no. ¡Espérate!",
                    "PLAYING" : "¡Ya estás jugando! Cierra la arena escribiendo en ella el comando `.ggs`.",
                    "ALREADY_SEARCHING" : f"Pero {player.mention}, ¡si ya estabas en la cola de ranked! Pulsa el otro botón para dejar de buscar.",
                }
                
                errors = json.loads(html)

                player_status = errors["cant_join"]
                await player.send(error_messages[player_status])
            
            elif response.status == 400:
                html = await response.text()
                errors = json.loads(html)
                
                error = errors.get("cant_join", False)                                                
                error_messages = {
                    "NO_TIER" : "No tienes Tier... Habla con algún admin para que te asigne una.",
                    "ALREADY_SEARCHING" : f"Pero {player.mention}, ¡si ya estabas en la cola!",
                }                
                
                if error:
                    error_message = error_messages[error]
                    await player.send(error_message)
            return

        

    @commands.command(aliases=['freeplays', 'friendlies-here'])
    @commands.check(player_exists)
    @commands.check(in_tier_channel)
    async def friendlies(self, ctx, tier_num=None):
        """
        You can join the list of friendlies with this command.
        """
        # Get player and tier
        player = ctx.author

        guild = ctx.guild
        # Check Force-tier mode:
        is_force_tier = ctx.invoked_with == "friendlies-here"
        
        body = {
            'guild': guild.id,            
            'created_by' : player.id,            
            'min_tier' : ctx.channel.id,            
            'roles' : [role.id for role in player.roles],
            'force_tier' : is_force_tier,
            'mode': 'FRIENDLIES'
        }

        async with self.bot.session.post('http://127.0.0.1:8000/arenas/', json=body) as response:            
            # MATCH FOUND OR STARTED SEARCHING
            if response.status == 201:
                html = await response.text()
                resp_body = json.loads(html)
                
                if resp_body['match_found']:
                    player1 = ctx.guild.get_member(resp_body['player_one'])
                    player2 = ctx.guild.get_member(resp_body['player_two'])

                    messages = resp_body.get('messages', [])
                    await self.edit_messages(ctx, messages, f"¡Match encontrado entre **{player1.nickname()}** y **{player2.nickname()}**!")                    
                    return await self.matchmaking(ctx, player1, player2)                    

                else:
                    mention_messages = []
                    for tier in resp_body['added_tiers']:
                        tier_role = ctx.guild.get_role(tier['id'])
                        tier_channel = ctx.guild.get_channel(tier['channel'])
                        
                        message = await tier_channel.send(f"Atención {tier_role.mention}, ¡**{player.nickname()}** busca rival! Escribe el comando `.friendlies` para retarle a jugar.")
                        mention_messages.append({'id': message.id, 'tier': tier_role.id, 'arena': resp_body['id']})
                    
                    await self.save_messages(mention_messages)
                    await self.update_list_message(guild=ctx.guild)
            
            # UPDATE SEARCH
            elif response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)
                
                # Add tiers
                mention_messages = []
                for tier in resp_body['added_tiers']:
                    tier_role = ctx.guild.get_role(tier['id'])
                    tier_channel = ctx.guild.get_channel(tier['channel'])                    
                    
                    message = await tier_channel.send(f"Atención {tier_role.mention}, ¡**{player.nickname()}** busca rival! Escribe el comando `.friendlies` para retarle a jugar.")
                    mention_messages.append({'id': message.id, 'tier': tier_role.id, 'arena': resp_body['id']})
                
                await self.save_messages(mention_messages)

                # Remove tiers
                if not resp_body['added_tiers']:
                    removed_roles = [ctx.guild.get_role(tier['id']) for tier in resp_body['removed_tiers']]
                    tiers_removed_str = ", ".join([role.name for role in removed_roles])

                    await ctx.send(f"Vale **{player.nickname()}**, has dejado de buscar en: {tiers_removed_str}.")
                
                removed_messages = resp_body.get('removed_messages', [])
                await self.delete_messages(guild, removed_messages)
                await self.update_list_message(guild=ctx.guild)
            
            # STATUS_CONFLICT ERROR
            elif response.status == 409:
                html = await response.text()

                error_messages = {
                    "CONFIRMATION" : "¡Tienes una partida pendiente de ser aceptada! Mira tus MDs.",
                    "ACCEPTED" : "Ya has aceptado tu partida, pero tu rival no. ¡Espérate!",
                    "PLAYING" : "¡Ya estás jugando! Cierra la arena escribiendo en ella el comando `.ggs`."
                }
                
                errors = json.loads(html)

                player_status = errors["cant_join"]
                await ctx.send(error_messages[player_status])
            
            elif response.status == 400:
                html = await response.text()
                errors = json.loads(html)
                
                error = errors.get("cant_join", False)
                wanted_tier_id = errors.get('wanted_tier', None)
                player_tier_id = errors.get('player_tier', None)
                                
                error_messages = {
                    "NO_TIER" : "No tienes Tier... Habla con algún admin para que te asigne una.",
                    "ALREADY_SEARCHING" : f"Pero {player.mention}, ¡si ya estabas en la cola!",                    
                }

                if wanted_tier_id and player_tier_id:
                    wanted_tier = guild.get_role(wanted_tier_id)
                    player_tier = guild.get_role(player_tier_id)

                    error_messages["BAD_TIERS"] = (
                        f"Intentas colarte en la lista de la {wanted_tier.name},"
                        f" pero aún eres de {player_tier.name}... ¡A seguir mejorando!"
                    )                    
                
                if error:
                    error_message = error_messages[error]
                    await ctx.send(error_message)
            return
    
    @commands.command()
    @commands.check(player_exists)
    @commands.check(in_arena_or_ranked)    
    async def ggs(self, ctx):
        arena_channel = ctx.channel
        guild = ctx.guild
        author = ctx.author

        is_ranked = in_ranked(ctx)

        body = {
            'channel_id' : arena_channel.id,
            'guild' : guild.id,
            'author' : author.id,
            'ranked' : is_ranked
        }

        async with self.bot.session.post('http://127.0.0.1:8000/arenas/ggs/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                is_closed = resp_body.get('closed', True)
                messages = resp_body.get('messages', [])
                players = resp_body.get('players', {})
                GGS_ARENA_COUNTDOWN = resp_body.get('ggs_time', 300)

                text = self.message_content(guild, players, is_closed)
                
                await self.edit_messages(ctx, messages, text)
                await ctx.send("GGs. ¡Gracias por jugar!")
                
                if GGS_ARENA_COUNTDOWN > 60:
                    time_text = time.strftime("%M minutos y %S segundos", time.gmtime(GGS_ARENA_COUNTDOWN))
                else:
                    time_text = time.strftime("%S segundos", time.gmtime(GGS_ARENA_COUNTDOWN))                
                await self.update_list_message(guild=ctx.guild)
                
                # Delete arena
                if is_closed:
                    await ctx.send(f"_La arena se destruirá en `{time_text}`._")
                    cancel_message = "Parce que ya han dejado de jugar, rip. ¡Presta más atención la próxima vez!"
                    await self.cancel_invites(arena_id=arena_channel.id, message=cancel_message)                    
                    await asyncio.sleep(GGS_ARENA_COUNTDOWN)
                    await arena_channel.delete()                    
                else:
                    await arena_channel.set_permissions(author, read_messages=False, send_messages=False)
            elif response.status == 409:
                await ctx.send("GG. ¡Pero aún queda set por jugar!")
            else:                
                await ctx.send("GGs. ¡Gracias por jugar!")        
    
    @commands.command(aliases=["cancel"])
    @commands.check(player_exists)
    @commands.check(in_tier_channel)    
    async def cancel_friendlies(self, ctx):
        player = ctx.author
        guild = ctx.guild
        mode = "FRIENDLIES"
        channel = ctx.channel

        return await self.cancel(player, guild, mode, channel)

    async def cancel(self, player, guild, mode, channel):
        body = {
            'player' : player.id,
            'guild' : guild.id,
            'mode': mode
        }
        
        async with self.bot.session.post(f'http://127.0.0.1:8000/arenas/cancel/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)
                
                if mode == 'FRIENDLIES':
                    await channel.send(f"Vale **{player.nickname()}**, te saco de la cola. ¡Hasta pronto!")
                else:
                    await player.send(f"Vale **{player.nickname()}**, te saqué de la cola Ranked. ¡Hasta pronto!")
                
                cancel_message = "Has cancelado la búsqueda, así que cancelé también la invitación."
                await self.cancel_invites(player_id=player.id, message=cancel_message)
                
                #  Delete mention messages
                messages = resp_body.get('messages', [])
                await self.delete_messages(guild, messages, is_ranked=True)
                await self.delete_messages(guild, messages)
                
            elif response.status == 400:
                html = await response.text()
                resp_body = json.loads(html)

                error_messages = {
                    'NOT_SEARCHING' : f"No estás en ninguna cola, {player.mention}. Usa `.friendlies` para unirte a una.",
                    'CONFIRMATION' : f"Ya has encontrado match. Acéptalo si quieres jugar, recházalo si no.",
                    'ACCEPTED' : f"Has aceptado el match... espera a que tu rival acepte o cancela el match desde ahí.",
                    'PLAYING' : f"¡Ya estás jugando! Cierra la arena con `.ggs`.",
                }
                if mode == "FRIENDLIES":
                    await channel.send(error_messages[resp_body.get('not_searching', 'NOT_SEARCHING')])
                else:
                    await player.send(error_messages[resp_body.get('not_searching', 'NOT_SEARCHING')])
            
            await self.update_list_message(guild=guild)
    
    @commands.command()
    @commands.check(player_exists)
    @commands.check(in_arena)    
    @commands.cooldown(1, 15, BucketType.channel)
    async def invite(self, ctx):        
        host = ctx.author
        arena = ctx.channel

        await self.cancel_invites(arena_id=arena.id, is_list=True)

        asyncio.current_task().set_name(f"invite-{arena.id}")
        
        # Show mentions list        
        players = await self.invite_mention_list(ctx)        
        
        if players is None:
            return        
        
        guest = players['guest']
        hosts = players['hosts']

        await ctx.send(f"Invitación enviada a **{guest.nickname()}**.")
        
        asyncio.current_task().set_name(f"invite-{arena.id}-{guest.id}")

        # Add as invited
        body = {'channel' : arena.id }
        async with self.bot.session.post(f'http://127.0.0.1:8000/players/{guest.id}/invite/', json=body) as response:
            if response.status == 200:
                # html = await response.text()
                # resp_body = json.loads(html)
                pass
            else:
                return await ctx.send(f"No se pudo invitar a {guest.nickname()}")
        
        # Ask for guest's consent
        await self.confirm_invite(ctx, guest, hosts)

    #  ************************************
    #             M E S S A G E S
    #  ************************************
    def message_content(self, guild, players, is_closed = False):
        playing_ids = players.get('PLAYING', [])
        ggs_ids = players.get('GGS', [])

        playing_players = [guild.get_member(player_id) for player_id in playing_ids]
        ggs_players = [guild.get_member(player_id) for player_id in ggs_ids]

        if is_closed:
            ggs_players += playing_players
            playing_players = False
        
        text = ""
        # Playing names
        if playing_players:
            player_names = [player.nickname() for player in playing_players]
            names_text = ", ".join(player_names[:-1])            
            names_text += "** y **"
            names_text += player_names[-1]
            text += f"¡**{names_text}** están jugando!"            
        # GGs names
        if ggs_players:
            ggs_names = [player.nickname() for player in ggs_players]
            ggs_text = ", ".join(ggs_names[:-1])                        
            extra_n = ''
            if len(ggs_players) > 1:
                ggs_text += "** y **"
                extra_n = 'n'
            ggs_text += ggs_names[-1]                    
            text += f" **{ggs_text}** ya ha{extra_n} dejado de jugar."
        
        return text

    async def edit_messages(self, ctx, messages, text):
        if not messages:
            return False
        
        edit_tasks = []
        for message_data in messages:
            channel = ctx.guild.get_channel(message_data.get('channel', message_data.get('channel_id')))
            try:
                message = await channel.fetch_message(message_data['id'])
                edit_tasks.append(message.edit(content=text))
            except discord.NotFound:
                logger.error(f"Couldn't find message with id {message_data['id']}")
                return False            
        
        await asyncio.gather(*edit_tasks)
        return True

    async def save_messages(self, messages):
        if not messages:
            return False
        
        body = {'messages' : messages}
        logger.info(f"Saving messages: {messages}")
        
        async with self.bot.session.post('http://127.0.0.1:8000/messages/', json=body) as response:
            if response.status != 201:
                logger.error("ERROR CREATING MESSAGES")
                logger.error(response)
                return False
        return True
        
    
    async def delete_messages(self, guild, messages, is_ranked = False):
        if not messages:
            return False        
        
        delete_tasks = []
        
        if is_ranked:
            messages = [message for message in messages if message.get('mode') == 'RANKED']
        
        for message_data in messages:
            logger.info(f"Deleting message: {message_data}")
            channel = guild.get_channel(message_data.get('channel', message_data.get('channel_id')))
            message = await channel.fetch_message(int(message_data['id']))
            delete_tasks.append(message.delete())
        
        await asyncio.gather(*delete_tasks)
        return True
    
    # ************************************************
    #          M  A  T  C  H  M  A  K  I  N  G
    # ************************************************

    async def matchmaking(self, ctx, player1, player2, ranked = False):
        guild = ctx.guild                    
        cancel_message = "¡Felicidades, encontraste match! Cancelo las invitaciones que tenías."
        logger.info(f"{'Ranked ' if ranked else ''}Match found between {player1.nickname()} and {player2.nickname()}.")
            
        await self.cancel_invites(player_id=player1.id, message=cancel_message)
        await self.cancel_invites(player_id=player2.id, message=cancel_message)
                
        match_confirmation = await self.confirm_match(ctx, player1, player2, ranked)

        if match_confirmation.get('all_accepted', False):
            # ACCEPTED MATCH
            logger.info(f"{'Ranked ' if ranked else ''}Match accepted between {player1.nickname()} and {player2.nickname()}.")
            arena_id = match_confirmation['arena_id']
            await self.delete_messages(guild, match_confirmation.get('messages'), is_ranked=True)
            return await self.set_arena(ctx, player1, player2, arena_id, ranked)
        else:
            # REJECTED MATCH

            searching_arenas = match_confirmation.get('arenas', [])
            logger.info(f'Searching arenas: {searching_arenas}')
            
            ranked_message = match_confirmation.get('ranked_message', {})
            is_ranked_rematch = False

            messages = []
            matched_players = set()

            for arena in searching_arenas:
                player_id = arena.get('searching_player')
                is_ranked = arena.get('mode', '') == "RANKED"
                
                if arena['mode'] == "FRIENDLIES":            
                    body = {'min_tier' : arena['min_tier'], 'max_tier' : arena['max_tier'], 'guild': guild.id}
                elif arena['mode'] == 'RANKED':
                    body = {'guild': guild.id}                
                    
                # SEARCH AGAIN
                async with self.bot.session.get(f'http://127.0.0.1:8000/players/{player_id}/{"ranked_" if is_ranked else ""}matchmaking/', json=body) as response:
                    if response.status == 200:
                        html = await response.text()
                        resp_body = json.loads(html)

                        logger.info(f'Arena matched')

                        # Match
                        player1 = guild.get_member(resp_body['player_one'])
                        player2 = guild.get_member(resp_body['player_two'])

                        if is_ranked:
                            is_ranked_rematch = True                            

                        asyncio.create_task(self.matchmaking(ctx, player1, player2, is_ranked))
                        matched_players.add(player1.id)
                        matched_players.add(player2.id)
                        
                        await self.update_list_message(guild=ctx.guild)
                        
                    elif response.status == 404:
                        html = await response.text()
                        resp_body = json.loads(html)
                        
                        #  Ping tiers again
                        player = ctx.guild.get_member(player_id)

                        if not is_ranked:
                            logger.info(f"Friendly arena not matched")
                            tiers = arena['tiers']
                            for tier in tiers:
                                channel = ctx.guild.get_channel(tier['channel'])
                                tier_role = ctx.guild.get_role(tier['id'])
                                messages.append({'arena': arena['arena_id'], 'tier': tier_role, 'player': player, 'channel': channel})
                        else:
                            logger.info(f'Ranked arena not matched')
                    else:
                        html = await response.text()                        

                        logger.error(f"ERROR IN MATCHMAKING: {html}")
            
            messages_infos = [message for message in messages if message['player'] not in matched_players]            
            
            # Send messages, and save them in the DB            
            messages = []
            if not ranked:
                for message in messages_infos:
                    channel, tier_role, player = message['channel'], message['tier'], message['player']
                    sent_message = await channel.send(f"Atención {tier_role.mention}, ¡**{player.nickname()}** sigue buscando rival!")
                    messages.append({'id': sent_message.id, 'arena': message['arena'], 'tier': tier_role.id})
            
            await self.save_messages(messages)
            
            if not is_ranked_rematch and ranked_message:
                await self.delete_messages(guild, [ranked_message], is_ranked=True)
                channel = ctx.guild.get_channel(ranked_message['channel_id'])                
                tier_role = ctx.guild.get_role(ranked_message['tier'])

                sent_message = await channel.send(f"{tier_role.mention}, ¡hay **alguien** buscando partida ranked! Reacciona al mensaje inicial para buscar partida tú también.")
                ranked_message['id'] = sent_message.id

                ranked_message = {
                    'id': sent_message.id,
                    'channel_id': channel.id,
                    'arena': ranked_message['arena'],
                    'mode': 'RANKED',
                }                
                await self.save_messages([ranked_message])
            
            await self.update_list_message(guild=ctx.guild)

    async def set_arena(self, ctx, player1, player2, arena_id, is_ranked = False):
        match = player1, player2
        guild = ctx.guild
        arena = await self.make_arena(ctx.guild, is_ranked)

        # Set channel in API
        body = { 'channel_id' : arena.id }
        async with self.bot.session.patch(f'http://127.0.0.1:8000/arenas/{arena_id}/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)
        #Set Permissions
        arena_permissions = [arena.set_permissions(player, read_messages=True, send_messages=True) for player in match]
        await asyncio.gather(*arena_permissions)

        # Send arena
        message_tasks = [player.send(f"Perfecto, dirígete a {arena.mention}.") for player in match]
        await asyncio.gather(*message_tasks)

        #Edit public messages
        players = {'PLAYING' : [player1.id, player2.id]}
        text = self.message_content(guild, players, is_closed=False)

        # Delete messages in #ranked, and edit all the public ones.
        await self.delete_messages(guild, resp_body.get('message_set'), is_ranked=True)
        await self.edit_messages(ctx, resp_body.get('message_set'), text)        

        await arena.send(f"¡Perfecto, aceptasteis ambos! {player1.mention} y {player2.mention}, ¡a jugar!")

        asyncio.create_task(self.update_list_message(guild=ctx.guild))
        
        if not is_ranked:
            await arena.send(f"Recordad usar `.ggs` al acabar, para así poder cerrar la arena.\n_(Para más información de las arenas, usad el comando `.help`)_")
        else:
            await self.bot.get_cog('Ranked').game_setup(player1, player2, arena, 1)

        
    
    #  ***********************************************
    #          C  O  N  F  I  R  M  A  T  I  O  N
    #  ***********************************************
        
    async def confirm_match(self, ctx, player1, player2, is_ranked = False):
        """
        This function manages the confirmation of the match, via DM.

        Params:
            player1, player2 := the matched players
        
        Returns:
            A dictionary d with d['accepted'] being True or False. If d['accepted'] is false, the dictionary
            also has a key d['player_to_reinsert'] with the User that was rejected.
        """
        match = player1, player2

        @asyncio.coroutine
        async def send_confirmation(player1, player2):
            if is_ranked:
                text_confirmation = f"¡Match de ranked encontrado! ¿Aceptas, {player1.mention}?"
            else:
                text_confirmation = f"¡Match encontrado! {player1.mention}, te toca contra **{player2.nickname()}**. ¿Aceptas?"
            return await player1.send(text_confirmation)
        # Send confirmation
        task1 = asyncio.create_task(send_confirmation(player1, player2))
        task2 = asyncio.create_task(send_confirmation(player2, player1))
        confirm_message1, confirm_message2 = await asyncio.gather(task1, task2)
        await self.update_list_message(guild=ctx.guild)

        # Tasks
        reaction_tasks = []

        # Get TIMEOUT_TIMES
        guild = ctx.guild
        async with self.bot.session.get(f'http://127.0.0.1:8000/guilds/{guild.id}/') as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                MATCH_TIMEOUT = resp_body['match_timeout']
                CANCEL_TIMEOUT = resp_body['cancel_time']
            
            else:
                MATCH_TIMEOUT = 900
                CANCEL_TIMEOUT = 90

        @asyncio.coroutine
        async def reactions(message):
            def check_message(reaction, user):
                is_same_message = (reaction.message == message)
                is_valid_emoji = (reaction.emoji in (EMOJI_CONFIRM, EMOJI_REJECT))

                return is_same_message and is_valid_emoji            

            def cancel_other_tasks():
                current_task_name = asyncio.current_task().get_name()                        
                for task in reaction_tasks:
                    if task.get_name() != current_task_name:
                        task.cancel()
            
            cancel_message = None
            # React
            await asyncio.gather(message.add_reaction(EMOJI_CONFIRM), message.add_reaction(EMOJI_REJECT))
            await asyncio.sleep(0.5)

            start_time = time.time()
            try:
                # Wait for user reaction
                try:
                    emoji, player = await self.bot.wait_for('reaction_add', timeout=MATCH_TIMEOUT + 5, check=check_message)
                    is_timeout = False
                except asyncio.TimeoutError:                
                    emoji = None
                    player = message.channel.recipient
                    is_timeout = True                
                finally:
                    remove_reactions = [message.remove_reaction(EMOJI, self.bot.user) for EMOJI in (EMOJI_CONFIRM, EMOJI_REJECT)]
                    await asyncio.gather(*remove_reactions)

                # API Call
                body = { 'accepted' : str(emoji) == EMOJI_CONFIRM, 'timeout' : is_timeout, 'guild': ctx.guild.id}

                async with self.bot.session.patch(f'http://127.0.0.1:8000/players/{player.id}/confirmation/', json=body) as response:                    
                    if response.status == 200:
                        html = await response.text()
                        resp_body = json.loads(html)

                        all_accepted = resp_body.get('all_accepted', False)
                        player_accepted = resp_body.get('player_accepted', False)

                        #  ACCEPTED, WAITING...
                        if player_accepted and not all_accepted:
                            await player.send("¡Aceptado! Ahora a esperar a tu rival...")
                            await self.update_list_message(guild=ctx.guild)
                            
                            await asyncio.sleep(CANCEL_TIMEOUT - (time.time() - start_time))

                            time_elapsed = time.time() - start_time
                            time_left = MATCH_TIMEOUT - time_elapsed
                            time_text = time.strftime("%M minutos y %S segundos", time.gmtime(time_left))

                            cancel_message = await player.send(f"Tu rival no contesta... puedes esperar {time_text} más, o cancelar el match.")
                            
                            def check_cancel_message(reaction, user):
                                is_same_message = (reaction.message == cancel_message)
                                is_valid_emoji = (reaction.emoji in (EMOJI_REJECT))

                                return is_same_message and is_valid_emoji
                            
                            await cancel_message.add_reaction(EMOJI_REJECT)
                            await asyncio.sleep(0.5)                            
                            
                            try:
                                emoji, player = await self.bot.wait_for('reaction_add', timeout=time_left, check=check_cancel_message)
                            except asyncio.TimeoutError:
                                pass
                            await cancel_message.remove_reaction(EMOJI_REJECT, self.bot.user)
                                                        
                            missing_player_id = resp_body['waiting_for']
                            cancel_other_tasks()
                            body = {'accepted' : False, 'timeout': True}

                            async with self.bot.session.patch(f'http://127.0.0.1:8000/players/{missing_player_id}/confirmation/', json=body) as response:
                                if response.status == 200:
                                    html = await response.text()
                                    resp_body = json.loads(html)
                        
                        cancel_other_tasks()
                        return resp_body
                    else:
                        return None
            except asyncio.CancelledError:
                if cancel_message is not None:
                    await cancel_message.delete()
                return None
        reaction_tasks.append(asyncio.create_task(reactions(confirm_message1), name=f"reactions_{confirm_message1.id}"))
        reaction_tasks.append(asyncio.create_task(reactions(confirm_message2), name=f"reactions_{confirm_message2.id}"))
        
        reaction1, reaction2 = await asyncio.gather(*reaction_tasks)

        # MESSAGES
        confirmation_data = reaction1
        active_player, passive_player = player1, player2
        
        if confirmation_data is None:
            confirmation_data = reaction2
            active_player, passive_player = player2, player1
        
        player_accepted = confirmation_data.get('player_accepted')
        all_accepted = confirmation_data.get('all_accepted')
        is_timeout = confirmation_data.get('timeout', False)
        both_rejected = confirmation_data.get('arena_id', False) is None
        
        if not player_accepted:
            # Delete messages of deleted arenas
            asyncio.create_task(self.delete_messages(guild, confirmation_data.get('messages', [])))            

            if is_timeout and both_rejected:
                passive_message = f"Ni tú ni {active_player.nickname() if not is_ranked else 'tu rival'} estáis... El match ha sido cancelado, y os he quitado a ambos de las listas -- podéis volver a apuntaros si queréis."            
                active_message = f"Ni tú ni {passive_player.nickname() if not is_ranked else 'tu rival'} estáis... El match ha sido cancelado, y os he quitado a ambos de las listas -- podéis volver a apuntaros si queréis."
                logger.info(f"{active_player.nickname()} and {passive_player.nickname()} timed out.")
            elif is_timeout:                
                passive_message = f"¿Hola? Parece que no estás... El match ha sido cancelado, y te he quitado de las listas -- puedes volver a apuntarte si quieres."
                active_message = f"Parece que {passive_player.nickname() if not is_ranked else 'tu rival'} no está... Te he vuelto a meter en las listas de búsqueda."
                logger.info(f"{active_player.nickname()} timed out, and {passive_player.nickname()} accepted.")
            else:
                active_message = f"Vale, match rechazado. Te he sacado de esta cola."
                passive_message = f"**{active_player.nickname() if not is_ranked else 'Tu rival'}** ha rechazado el match... ¿en otro momento, quizás?\nTe he metido en las listas otra vez."
                logger.info(f"{active_player.nickname()} rejected the match against {passive_player.nickname()}")
            
            await asyncio.gather(active_player.send(active_message), passive_player.send(passive_message))                
        
        return confirmation_data

    async def confirm_invite(self, ctx, guest, hosts):
        arena = ctx.channel        
        
        # Get hosts name string:
        host_names = [host.nickname() for host in hosts]
        
        names_text = ", ".join(host_names[:-1])        
        
        if len(hosts) > 1:
            names_text += "** y **"
        
        names_text += host_names[-1]
        
        message = await guest.send(f"**{names_text}** te invitan a jugar con ellos en su arena. ¿Aceptas?")

        # React
        await asyncio.gather(message.add_reaction(EMOJI_CONFIRM), message.add_reaction(EMOJI_REJECT))
        await asyncio.sleep(0.5)
        
        # Wait for user reaction
        invite_task = asyncio.create_task(self.wait_invite_reaction(ctx, message, guest, hosts))
        self.arena_invites[guest.id].append(invite_task)
        await invite_task

    @asyncio.coroutine
    async def wait_invite_reaction(self, ctx, message, guest, hosts):
        arena = ctx.channel
        guild = ctx.guild

        def check_message(reaction, user):
            is_same_message = (reaction.message == message)
            is_valid_emoji = (reaction.emoji in (EMOJI_CONFIRM, EMOJI_REJECT))

            return is_same_message and is_valid_emoji

        try:
            emoji, player = await self.bot.wait_for('reaction_add', check=check_message)
            
            remove_reactions = [message.remove_reaction(EMOJI, self.bot.user) for EMOJI in (EMOJI_CONFIRM, EMOJI_REJECT)]
            await asyncio.gather(*remove_reactions)
            
            is_accepted = str(emoji) == EMOJI_CONFIRM

            body = {
                'invited': True,
                'accepted': is_accepted,
                'channel': arena.id,                
            }
            
            async with self.bot.session.patch(f'http://127.0.0.1:8000/players/{guest.id}/confirmation/', json=body) as response:
                if response.status == 200:
                    html = await response.text()
                    resp_body = json.loads(html)

                    messages = resp_body.get('messages', [])
                    players = resp_body.get('players', {})
                else:
                    logger.error("Error with invite confirmation")
                    logger.error(response)            
            
            if is_accepted:
                await arena.set_permissions(guest, read_messages=True, send_messages=True)
                await self.update_list_message(guild=ctx.guild)               
                

                edited_text = self.message_content(guild, players)

                await self.edit_messages(ctx, messages, edited_text)            

                await arena.send(f"Abran paso, que llega el low tier {player.mention}.")
                await guest.send(f"Perfecto {guest.mention}, ¡dirígete a {arena.mention} y saluda a tus anfitriones!")
            else:
                await arena.send(f"**{player.nickname()}** rechazó la invitación.")
                await guest.send(f"Vale, **{player.nickname()}**: invitación rechazada.")

        except asyncio.CancelledError as e:
            remove_reactions = [message.remove_reaction(EMOJI, self.bot.user) for EMOJI in (EMOJI_CONFIRM, EMOJI_REJECT)]
            await asyncio.gather(*remove_reactions)
            await guest.send(str(e))
            await arena.send(f"**{guest.nickname()}** no puede venir...")
            return

    async def cancel_invites(self, arena_id=None, player_id=None, message=None, is_list=False):
        """
        Cancels the invite tasks, with the player id or arena id given.
        """
        current_mode = 1 if arena_id is not None else 2
        modes = {
            1: str(arena_id),
            2: str(player_id),
        }
        
        tasks = asyncio.all_tasks()
        for task in tasks:
            task_name = task.get_name()                        
            detailed_task = task_name.split("-")
            
            if len(detailed_task) > current_mode:
                is_invite = detailed_task[0] == "invite"
                is_wanted = detailed_task[current_mode] == modes[current_mode]
                
                if is_list:
                    is_wanted = is_wanted and len(detailed_task) == 2
                
                if is_invite and is_wanted:
                    task.cancel(msg=message)



    #  ***********************************************
    #           A   R   E   N   A   S
    #  ***********************************************
    async def make_arena(self, guild, is_ranked):
        """
        Creates a text channel called #arena-X (x is an autoincrementing int).
        Returns this channel.
        """

        def get_arena_number(arena):
            return int(arena.name[arena.name.index("-") + 1:])
        
        category_name = "RANKEDS" if is_ranked else "ARENAS"
        arenas_category = discord.utils.get(guild.categories, name=category_name)
        arenas = arenas_category.channels
        
        new_arena_number = max(map(get_arena_number, arenas), default=0) + 1
        new_arena_name = f'{"ranked" if is_ranked else "arena"}-{new_arena_number}'
        channel = await arenas_category.create_text_channel(new_arena_name)        
        
        return channel
  
    # *******************************
    #           L I S T
    # *******************************

    async def update_list_message(self, guild=None):

        new_message = "__**FRIENDLIES**__\n"
        async with self.bot.session.get(f'http://127.0.0.1:8000/guilds/{guild.id}/list_message/') as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                for tier in resp_body['tiers']:
                    tier_role = guild.get_role(tier['id'])
                    players = [guild.get_member(player_id) for player_id in tier['players']]
                    
                    player_names = ", ".join([player.nickname() for player in players])
                    new_message += f"**{tier_role.name}**:\n```{player_names} ```\n"
                
                if resp_body['confirmation']:
                    new_message += "\n**CONFIRMANDO:**\n"

                for arena in resp_body['confirmation']:
                    player1, player2 = [{'name' : guild.get_member(player['id']).nickname(), 'tier': guild.get_role(player['tier']).name, 'status' : player['status']} for player in arena]
                    if arena[0]['mode'] == 'RANKED':
                        player1['name'], player2['name'] = "Alguien", "Alguien"
                    new_message += (
                        f"**[{EMOJI_CONFIRM if player1['status'] == 'ACCEPTED' else EMOJI_HOURGLASS}]  {player1['name']}** ({player1['tier']})"
                        f" vs. **{player2['name']}** ({player2['tier']}) **[{EMOJI_CONFIRM if player2['status'] == 'ACCEPTED' else EMOJI_HOURGLASS}]**\n"
                    )
                if resp_body['playing']:
                    new_message += "\n**ARENAS:**\n"
                
                for arena in resp_body['playing']:                    
                    players = [{'name' : guild.get_member(player['id']).nickname(), 'tier': guild.get_role(player['tier']).name} for player in arena]
                    players_text = [f"**{player['name']}** ({player['tier']})" for player in players]
                    new_message += f"{'**RANKED**:' if arena[0]['mode'] == 'RANKED' else ''}{' vs. '.join(players_text)}\n"

                list_channel = guild.get_channel(resp_body['list_channel'])
                list_message = await list_channel.fetch_message(resp_body['list_message'])

                return await list_message.edit(content=new_message)
            else:
                logger.error(f"Error updating the list message")
                return False        
    
    async def invite_mention_list(self, ctx):        
        message_text = (f"**__Lista de menciones:__**\n"
            f"_¡Simplemente reacciona con el emoji del jugador a invitar (solo uno)!_\n")
        
        arena = ctx.channel
        guild = ctx.guild

        body = {'channel': arena.id}

        # Get unique players
        async with self.bot.session.get('http://127.0.0.1:8000/arenas/invite_list/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)
                
                players = resp_body['players']
                hosts = resp_body['hosts']
            else:
                await ctx.send("Error, no se puede mostrar la lista. ¿Quizá cerrasteis la arena?")
                return

        # There are only 10 emojis with numbers. For now that'll be more than enough.
        players = players[:10]

        if not players:
            await ctx.send("No hay nadie buscando partida.")
            return
                
        # Get player name        
        for player in players:
            player['name'] = guild.get_member(player['id']).nickname()

        # Message building
        for i, player in enumerate(players, start=1):
            tier = guild.get_role(player['tier'])
            message_text += f"{i}. {player['name']} ({tier.name})\n"        
        
        message = await arena.send(message_text)
        
        message_reactions = [message.add_reaction(emoji) for emoji in NUMBER_EMOJIS[ : len(players)]]
        await asyncio.gather(*message_reactions)

        def check_message(reaction, user):
            is_same_message = (reaction.message == message)
            is_valid_emoji = (reaction.emoji in (NUMBER_EMOJIS))
            is_author = (user == ctx.author)

            return is_same_message and is_valid_emoji and is_author

        emoji, player = await self.bot.wait_for('reaction_add', check=check_message)

        player_index = NUMBER_EMOJIS.index(str(emoji))

        guest = ctx.guild.get_member(players[player_index]['id'])
        hosts = [ctx.guild.get_member(host) for host in hosts]    
        
        return {'guest': guest, 'hosts': hosts}
    
    @commands.command()
    @commands.has_any_role("Dev","admin")
    async def check_tasks(self, ctx):
        tasks = asyncio.all_tasks()
        tasks_name = [task.get_name() for task in tasks]
        await ctx.send(tasks_name)

    # *******************************
    #           C L E A N   U P
    # *******************************
    async def reset_arenas(self, startup=False):
        """
        Deletes all open arenas. If startup is True, deletes only those in WAITING
        or CONFIRMATION.
        """
        # GET ARENAS INFO
        body = {'startup': startup}
        async with self.bot.session.delete('http://127.0.0.1:8000/arenas/clean_up/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                arenas = resp_body.get('arenas', [])
            else:
                logger.error("ERROR WITH CLEAN_UP")
                logger.error(response)
                return
        
        guild_set = set()
        member_set = set()

        for arena in arenas:
            # GET GUILD
            guild = self.bot.get_guild(arena['guild'])
            guild_set.add(guild)

            # DELETE TEXT CHANNEL
            channel_id = arena['channel']
            
            if channel_id:
                arena_channel = guild.get_channel(channel_id)
                if arena_channel:
                    arena_channel.delete()
            
            # MEMBER
            member = guild.get_member(arena.get('player'))
            if member:
                member_set.add(member)
                
            # DELETE MESSAGES
            await self.delete_messages(guild, arena.get('messages', []))
        
        for guild in guild_set:
            await self.update_list_message(guild=guild)

        if startup:
            for member in member_set:
                await member.send(f"Se reinició el bot, así que se perdió tu búsqueda de partida. ¡Lo siento! Vuelve a buscar partida.")
        
        logger.info("CLEAN UP OK!")

    @tasks.loop(hours=24)
    async def reset_matchmaking(self):
        """
        Deletes all open arenas, everyday at 5:15 AM.
        """
        return await self.reset_arenas()
       
    
    @reset_matchmaking.before_loop
    async def before_reset_matchmaking(self):
        hour, minute = 5, 15
        now = datetime.now()
        future = datetime(now.year, now.month, now.day, hour, minute)        

        if now.hour >= hour and now.minute > minute:
            future += timedelta(days=1)

        delta = (future - now).seconds
        await asyncio.sleep(delta)
    
    # **********************************
    #           ERROR HANDLERS
    # **********************************

    @friendlies.error
    async def friendlies_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.errors.MissingPermissions):
            pass
        else:
            raise error
    
    @ggs.error
    async def ggs_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.errors.MissingPermissions):
            pass
        else:
            raise error
    
    @invite.error
    async def invite_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.errors.MissingPermissions):
            pass
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Calma, calma. No puedes volver a usar el comando `.invite` hasta dentro de {round(error.retry_after, 2)}s.")
        else:
            raise error
    
    @check_tasks.error
    async def check_tasks_error(self, ctx, error):            
        if isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.errors.MissingPermissions):
            pass
        else:
            raise error

def setup(bot):
    bot.add_cog(Matchmaking(bot))