import aiohttp
import discord
import asyncio
import time
import re
import itertools
import typing
from collections import defaultdict
from datetime import datetime, timedelta
import json

from discord.ext import tasks, commands
from discord.ext.commands.cooldowns import BucketType

from .Exceptions import (RejectedException, ConfirmationTimeOutException, 
                        TierValidationException, AlreadyMatchedException)

from .params.matchmaking_params import (TIER_NAMES, TIER_CHANNEL_NAMES, EMOJI_CONFIRM, EMOJI_REJECT, 
                    EMOJI_HOURGLASS, NUMBER_EMOJIS, LIST_CHANNEL_ID, LIST_MESSAGE_ID,
                    WAIT_AFTER_REJECT, GGS_ARENA_COUNTDOWN, DEV_MODE,
                    FRIENDLIES_TIMEOUT)

from .checks.matchmaking_checks import (in_arena, in_tier_channel)

class Matchmaking(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.arena_invites = defaultdict(list)
    
    async def setup_matchmaking(self, guild):
        self.guild = guild
        self.reset_matchmaking.start()        
        await self.update_list_message(guild=guild)

    @commands.command(aliases=['freeplays', 'friendlies-here'])
    @commands.check(in_tier_channel)
    async def friendlies(self, ctx, tier_num=None):
        """
        You can join the list of friendlies with this command.
        """
        # Get player and tier
        player = ctx.author        

        # Check Force-tier mode:
        is_force_tier = ctx.invoked_with == "friendlies-here"
        
        body = {
            'guild': ctx.guild.id,            
            'created_by' : ctx.author.id,
            'player_name' : ctx.author.nickname(),
            'min_tier' : ctx.channel.id,
            'max_players' : 2,
            'roles' : [role.id for role in player.roles],
            'force_tier' : is_force_tier
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
                    return await self.matchmaking(ctx, player1, player2, resp_body)                    

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
                await self.delete_messages(ctx, removed_messages)
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
                                
                error_messages = {
                    "NO_TIER" : "No tienes Tier... Habla con algún admin para que te asigne una.",
                    "ALREADY_SEARCHING" : f"Pero {player.mention}, ¡si ya estabas en la cola!",
                    "BAD_TIERS" : f"Intentas colarte en la lista de la {errors.get('wanted_tier')}, pero aún eres de {errors.get('player_tier')}... ¡A seguir mejorando!",
                }
                
                if error:
                    error_message = error_messages[error]
                else:
                    error_message = "\n".join([error[0] for error in errors.values()])
                await ctx.send(error_message)
            return

    @friendlies.error
    async def friendlies_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        else:
            print(error)

    @commands.command()
    @commands.check(in_arena)
    async def ggs(self, ctx):
        arena_channel = ctx.channel
        guild = ctx.guild
        author = ctx.author

        body = {
            'channel_id' : arena_channel.id,
            'guild' : guild.id,
            'author' : author.id
        }

        async with self.bot.session.post('http://127.0.0.1:8000/arenas/ggs/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)

                is_closed = resp_body.get('closed', True)
                messages = resp_body.get('messages', [])
                players = resp_body.get('players', {})
                GGS_ARENA_COUNTDOWN = resp_body.get('ggs_time', 300)
                
                text = self.message_content(guild, players)                
                
                await self.edit_messages(ctx, messages, text)
                await ctx.send("GGs. ¡Gracias por jugar!")
                
                if GGS_ARENA_COUNTDOWN > 60:
                    time_text = time.strftime("%M minutos y %S segundos", time.gmtime(GGS_ARENA_COUNTDOWN))
                else:
                    time_text = time.strftime("%S segundos", time.gmtime(GGS_ARENA_COUNTDOWN))
                await self.update_list_message(guild=ctx.guild)
                
                # Delete arena
                if is_closed:
                    cancel_message = "Parce que ya han dejado de jugar, rip. ¡Presta más atención la próxima vez!"
                    await self.cancel_invites(arena_id=arena_channel.id, message=cancel_message)
                    await asyncio.sleep(GGS_ARENA_COUNTDOWN)
                    await arena_channel.delete()                    
                else:
                    await arena_channel.set_permissions(author, read_messages=False, send_messages=False)
            else:
                await ctx.send("GGs. ¡Gracias por jugar!")
    
    @ggs.error
    async def ggs_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        else:
            print(error)

    @commands.command()
    async def cancel(self, ctx):
        player = ctx.author

        body = {
            'player' : player.id,
            'guild' : ctx.guild.id
        }
        
        async with self.bot.session.post(f'http://127.0.0.1:8000/arenas/cancel/', json=body) as response:
            if response.status == 200:
                html = await response.text()
                resp_body = json.loads(html)
                
                await ctx.send(f"Vale **{player.nickname()}**, te saco de la cola. ¡Hasta pronto!")
                cancel_message = "Has cancelado la búsqueda, así que cancelé también la invitación."
                await self.cancel_invites(player_id=player.id, message=cancel_message)
                
                #  Delete mention messages
                messages = resp_body.get('messages', [])
                await self.delete_messages(ctx, messages)
                
            elif response.status == 400:
                html = await response.text()
                resp_body = json.loads(html)

                error_messages = {
                    'NOT_SEARCHING' : f"No estás en ninguna cola, {player.mention}. Usa `.friendlies` para unirte a una.",
                    'CONFIRMATION' : f"Ya has encontrado match. Acéptalo si quieres jugar, recházalo si no.",
                    'ACCEPTED' : f"Has aceptado el match... espera a que tu rival acepte o cancela el match desde ahí.",
                    'PLAYING' : f"¡Ya estás jugando! Cierra la arena con `.ggs`.",
                }

                await ctx.send(error_messages[resp_body.get('not_searching', 'NOT_SEARCHING')])
            
            await self.update_list_message(guild=ctx.guild)
    
    @commands.command()
    @commands.check(in_arena)
    @commands.cooldown(1, 15, BucketType.channel)
    async def invite(self, ctx):        
        host = ctx.author
        arena = ctx.channel

        asyncio.current_task().set_name(f"invite-{arena.id}")
        
        # Show mentions list        
        players = await self.invite_mention_list(ctx)        
        
        if players is None:
            return        
        
        guest = players['guest']
        hosts = players['hosts']
        
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


    @invite.error
    async def invite_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Calma, calma. No puedes volver a usar el comando `.invite` hasta dentro de {round(error.retry_after, 2)}s.")
        else:
            print(error)



    #  ************************************
    #             M E S S A G E S
    #  ************************************
    def message_content(self, guild, players):
        playing_ids = players.get('PLAYING', [])
        ggs_ids = players.get('GGS', [])

        playing_players = [guild.get_member(player_id) for player_id in playing_ids]
        ggs_players = [guild.get_member(player_id) for player_id in ggs_ids]
        
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
            channel = ctx.guild.get_channel(message_data['channel'])
            try:
                message = await channel.fetch_message(message_data['id'])
                edit_tasks.append(message.edit(content=text))
            except discord.NotFound:
                print(f"Couldn't find message with id {message_data['id']}")
                return False            
        
        await asyncio.gather(*edit_tasks)
        return True

    async def save_messages(self, messages):
        if not messages:
            return False
        
        body = {'messages' : messages}
        
        async with self.bot.session.post('http://127.0.0.1:8000/messages/', json=body) as response:
            if response.status != 201:
                print("ERROR CREATING MESSAGES")
                return False
        return True
        
    
    async def delete_messages(self, ctx, messages):
        if not messages:
            return False
        
        delete_tasks = []        
        
        for message_data in messages:
            channel = ctx.guild.get_channel(message_data['channel'])            
            message = await channel.fetch_message(int(message_data['id']))
            delete_tasks.append(message.delete())
        
        await asyncio.gather(*delete_tasks)
        return True
    
    # ************************************************
    #          M  A  T  C  H  M  A  K  I  N  G
    # ************************************************

    async def matchmaking(self, ctx, player1, player2, resp_body):
        guild = ctx.guild
        match_found = True

        while match_found:
            cancel_message = "¡Felicidades, encontraste match! Cancelo las invitaciones que tenías."
            
            await self.cancel_invites(player_id=player1.id, message=cancel_message)
            await self.cancel_invites(player_id=player2.id, message=cancel_message)
            
            match_confirmation = await self.confirm_match(ctx, player1, player2)

            if match_confirmation.get('all_accepted', False):
                # ACCEPTED MATCH
                arena_id = match_confirmation['arena_id']
                return await self.set_arena(ctx, player1, player2, arena_id)
            else:
                # REJECTED MATCH                
                player_id = match_confirmation.get('searching_player', None)

                if player_id is None:
                    return await self.update_list_message(guild=ctx.guild)
                                
                body = {'min_tier' : match_confirmation['min_tier'], 'max_tier' : match_confirmation['max_tier'], 'guild': guild.id}
                
                # SEARCH AGAIN
                async with self.bot.session.get(f'http://127.0.0.1:8000/players/{player_id}/matchmaking/', json=body) as response:
                    if response.status == 200:
                        html = await response.text()
                        resp_body = json.loads(html)

                        # Match
                        player1 = ctx.guild.get_member(resp_body['player_one'])
                        player2 = ctx.guild.get_member(resp_body['player_two'])
                        match_found = True
                        await self.update_list_message(guild=ctx.guild)
                    
                    elif response.status == 404:
                        #  Ping tiers again
                        match_found = False
                        player = ctx.guild.get_member(player_id)
                        tiers = match_confirmation['tiers']
                        for tier in tiers:
                            channel = ctx.guild.get_channel(tier['channel'])
                            tier_role = ctx.guild.get_role(tier['id'])
                            await channel.send(f"Atención {tier_role.mention}, ¡**{player.nickname()}** sigue buscando rival!")
                            await self.update_list_message(guild=ctx.guild)
                        return

    async def set_arena(self, ctx, player1, player2, arena_id):
        match = player1, player2                
        arena = await self.make_arena()

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

        await arena.send(f"¡Perfecto, aceptasteis ambos! {player1.mention} y {player2.mention}, ¡a jugar!")
        await arena.send(f"Recordad usar `.ggs` al acabar, para así poder cerrar la arena.\n_(Para más información de las arenas, usad el comando `.help`)_")
        await self.update_list_message(guild=ctx.guild)
    
    #  ***********************************************
    #          C  O  N  F  I  R  M  A  T  I  O  N
    #  ***********************************************
        
    async def confirm_match(self, ctx, player1, player2):
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
            return await player1.send(f"¡Match encontrado! {player1.mention}, te toca contra **{player2.nickname()}**. ¿Aceptas?")
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
            if is_timeout and both_rejected:
                passive_message = f"Ni tú ni {active_player.nickname()} estáis... El match ha sido cancelado, y os he quitado a ambos de las listas -- podéis volver a apuntaros si queréis."            
                active_message = f"Ni tú ni {passive_player.nickname()} estáis... El match ha sido cancelado, y os he quitado a ambos de las listas -- podéis volver a apuntaros si queréis."
            elif is_timeout:                
                passive_message = f"¿Hola? Parece que no estás... El match ha sido cancelado, y te he quitado de las listas -- puedes volver a apuntarte si quieres."
                active_message = f"Parece que {passive_player.nickname()} no está... Te he vuelto a meter en las listas de búsqueda."
            else:
                active_message = f"Vale, match rechazado. Te he sacado de todas las colas."
                passive_message = f"**{active_player.nickname()}** ha rechazado el match... ¿en otro momento, quizás?\nTe he metido en las listas otra vez."
            
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
                    print("Error with invite confirmation")
            
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

    async def cancel_invites(self, arena_id=None, player_id=None, message=None):
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
                
                if is_invite and is_wanted:
                    task.cancel(msg=message)



    #  ***********************************************
    #           A   R   E   N   A   S
    #  ***********************************************
    async def make_arena(self):
        """
        Creates a text channel called #arena-X (x is an autoincrementing int).
        Returns this channel.
        """

        def get_arena_number(arena):
            return int(arena.name[arena.name.index("-") + 1:])
        
        arenas_category = discord.utils.get(self.guild.categories, name="ARENAS")
        arenas = arenas_category.channels        
        
        new_arena_number = max(map(get_arena_number, arenas), default=0) + 1
        new_arena_name = f'arena-{new_arena_number}'
        channel = await arenas_category.create_text_channel(new_arena_name)
        
        return channel
            
    # async def delete_arenas(self):
    #     for arena in self.arenas:
    #         await self.delete_arena(arena)        

    # async def delete_arena(self, arena):
    #     if arena not in self.arenas:
    #         return
        
        # self.arenas.remove(arena)
        # self.arena_status.pop(arena.name, None)

        # if arena.name in self.arena_invites.keys():            
        #     for invite in self.arena_invites[arena.name]:
        #         invite.cancel()
        #     self.arena_invites.pop(arena.name, None)
        
        # await arena.delete()
  
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
                    players = [guild.get_member(player_id) for player_id in tier['players']]
                    player_names = ", ".join([player.nickname() for player in players])
                    new_message += f"**{tier['name']}**:\n```{player_names} ```\n"
                
                if resp_body['confirmation']:
                    new_message += "\n**CONFIRMANDO:**\n"

                for arena in resp_body['confirmation']:
                    player1, player2 = [{'name' : guild.get_member(player['id']).nickname(), 'tier': player['tier'], 'status' : player['status']} for player in arena]
                    new_message += (
                        f"**[{EMOJI_CONFIRM if player1['status'] == 'ACCEPTED' else EMOJI_HOURGLASS}]  {player1['name']}** ({player1['tier']})"
                        f" vs. **{player2['name']}** ({player2['tier']}) **[{EMOJI_CONFIRM if player2['status'] == 'ACCEPTED' else EMOJI_HOURGLASS}]**\n"
                    )
                if resp_body['playing']:
                    new_message += "\n**ARENAS:**\n"
                
                for arena in resp_body['playing']:                    
                    players = [{'name' : guild.get_member(player['id']).nickname(), 'tier': player['tier']} for player in arena]
                    players_text = [f"**{player['name']}** ({player['tier']})" for player in players]
                    new_message += f"{' vs. '.join(players_text)}\n"

                list_channel = self.guild.get_channel(resp_body['list_channel'])
                list_message = await list_channel.fetch_message(resp_body['list_message'])

                return await list_message.edit(content=new_message)
            else:
                print("Error")
                return False        
    
    async def invite_mention_list(self, ctx):        
        message_text = (f"**__Lista de menciones:__**\n"
            f"_¡Simplemente reacciona con el emoji del jugador a invitar (solo uno)!_\n")
        
        arena = ctx.channel

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
            player['name'] = ctx.guild.get_member(player['id']).nickname()

        # Message building
        for i, player in enumerate(players, start=1):
            message_text += f"{i}. {player['name']} ({player['tier']})\n"        
        
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
    
    @check_tasks.error
    async def check_tasks_error(self, ctx, error):            
        if isinstance(error, commands.CheckFailure):
            pass
        else:
            print(error)

    # *******************************
    #           C L E A N   U P
    # *******************************
    @tasks.loop(hours=24)
    async def reset_matchmaking(self):
        pass
        # await self.delete_arenas()        
        
        # self.search_list = {f"Tier {i}" : [] for i in range(1, 5)}
        # self.confirmation_list = []
        # self.rejected_list = []
                
        # await self.update_list_message()
        
        # print("Clean up complete")
    
    @reset_matchmaking.before_loop
    async def before_reset_matchmaking(self):
        hour, minute = 5, 15
        now = datetime.now()
        future = datetime(now.year, now.month, now.day, hour, minute)        

        if now.hour >= hour and now.minute > minute:
            future += timedelta(days=1)

        delta = (future - now).seconds
        await asyncio.sleep(delta)

def setup(bot):
    bot.add_cog(Matchmaking(bot))