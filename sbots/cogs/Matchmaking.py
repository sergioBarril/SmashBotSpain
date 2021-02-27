import aiohttp
import discord
import asyncio
import time
import re
import itertools
import typing
from datetime import datetime, timedelta
import json

from discord.ext import tasks, commands
from .Exceptions import (RejectedException, ConfirmationTimeOutException, 
                        TierValidationException, AlreadyMatchedException)

from .params.matchmaking_params import (TIER_NAMES, TIER_CHANNEL_NAMES, EMOJI_CONFIRM, EMOJI_REJECT, 
                    NUMBER_EMOJIS, LIST_CHANNEL_ID, LIST_MESSAGE_ID,
                    WAIT_AFTER_REJECT, GGS_ARENA_COUNTDOWN, DEV_MODE,
                    FRIENDLIES_TIMEOUT)

from .checks.matchmaking_checks import (in_their_arena, in_tier_channel)

class Matchmaking(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.search_list = {f"Tier {i}" : [] for i in range(1, 5)}
        self.confirmation_list = []
        self.rejected_list = []

        self.mention_messages = {}
        self.current_search = {}                
        
        self.arena_status = {}
        self.arena_invites = {}
    
    async def setup_matchmaking(self, guild):
        self.guild = guild        
        self.arenas =  discord.utils.get(self.guild.categories, name="ARENAS").channels
        await self.delete_arenas()
        
        
        # Message that will have the updated search lists
        list_channel = self.guild.get_channel(channel_id=LIST_CHANNEL_ID)
        list_message = await list_channel.fetch_message(LIST_MESSAGE_ID)                        
        self.list_message = list_message
        
        self.tier_roles = {}
        self.tier_channels = {}
        
        for tier_name, tier_channel_name in zip(TIER_NAMES, TIER_CHANNEL_NAMES):
            role = discord.utils.get(self.guild.roles, name = tier_name)
            channel = discord.utils.get(self.guild.channels, name = tier_channel_name)
            
            self.tier_roles[tier_name] = role
            self.tier_channels[tier_name] = channel
        
        self.reset_matchmaking.start()
        await self.update_list_message()

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
    @commands.check(in_their_arena)
    async def ggs(self, ctx):
        arena = ctx.channel
        player = ctx.author
        arena_players = self.arena_status[arena.name]

        if len(arena_players) > 2:
            await ctx.send(f"GGs, **{ctx.author.nickname()}** lo deja por hoy.")
            await self.remove_arena_permissions(player, arena)

            # Edit leaver message
            edited_text = f"**{player.nickname()}** ya ha terminado de jugar."
            await asyncio.gather(*[message.edit(content=edited_text) for message in self.mention_messages.get(player, [])])
            self.mention_messages.pop(player, None)
            arena_players.remove(player)

            # Edit other messages
            player1, player2 = arena_players
            edited_text = f"**¡{player1.nickname()}** y **{player2.nickname()}** están jugando!"
            await asyncio.gather(*[message.edit(content=edited_text) for member in arena_players for message in self.mention_messages.get(member, [])])        
        
        else:
            await ctx.send("GGs, ¡gracias por jugar!")                
                    
            # Edit messages
            match = arena_players
            player1, player2 = match            

            edited_text = f"**{player1.nickname()}** y **{player2.nickname()}** ya han terminado de jugar."
            await asyncio.gather(*[message.edit(content=edited_text) for member in match for message in self.mention_messages.get(member, [])])
            
            for member in match:
                self.mention_messages.pop(player, None)
            
            # Delete arena
            await asyncio.sleep(GGS_ARENA_COUNTDOWN)
            await self.delete_arena(arena)
        
        return await self.update_list_message()

    @ggs.error
    async def ggs_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        else:
            print(error)

    @commands.command()
    async def cancel(self, ctx):
        player = ctx.author
        has_removed = await self.remove_from_search_list(player, range(1, 5))
        
        if has_removed:
            await ctx.send(f"Vale **{player.nickname()}**, te saco de la cola. ¡Hasta pronto!")
            
            # Delete mention messages
            for message in self.mention_messages.get(player, []):
                await message.delete()            
            self.mention_messages.pop(player, None)

            # Delete search record
            self.current_search.pop(player, None)
        
        else:
            await ctx.send(f"No estás en ninguna cola, {player.mention}. Usa `.friendlies` para unirte a una.")

    @commands.command()
    @commands.check(in_their_arena)
    async def invite(self, ctx, guest : typing.Optional[discord.Member]):
        host = ctx.author
        arena = ctx.channel

        if len(self.arena_status[arena.name]) > 2:
            return await ctx.send("Ya sois 3 en la arena (aún no están implementadas las arenas de más de 3 personas).")

        host_tier = self.get_tier(host)
        
        if guest is None:
            # Show mentions list
            tier_range = self.tier_range_validation(host_tier, 4)
            return await self.invite_mention_list(ctx, tier_range)
        
        
        # Get min tier list where the guest is searching
        searched_tiers = [i for i in range(1, 5) if guest in self.search_list[f'Tier {i}']]

        if not searched_tiers:
            return await ctx.send(f"**{guest.nickname()}** no está buscando partidas ahora mismo... decidle que haga `.friendlies` primero.")
        
        min_search_tier = searched_tiers[-1]

        try:
            tier_range = self.tier_range_validation(host_tier, min_search_tier)
        except TierValidationException as e:
            return await ctx.send(f"No parece que **{guest.nickname()}** esté buscando partida de tu tier o inferior.")

        host1, host2 = self.arena_status[arena.name]
        
        # Ask for guest's consent
        await self.confirm_invite(host1, host2, guest, arena)


    @invite.error
    async def invite_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            pass
        else:
            print(error)



    #  ************************************
    #             M E S S A G E S
    #  ************************************

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

    #  ************************************
    #              T I E R S
    #  ************************************
    
    def get_tier(self, player):
        """
        Given a player, returns the role with their Tier.
        """
        if isinstance(player, discord.member.Member):
            member = player
        else:            
            member = self.guild.get_member(player.id)
        return next((role for role in member.roles[::-1] if role in self.tier_roles.values()), None)

    def tier_range_validation(self, tier_role, limit_tier_num, force_tier = False):
        """
        Given a Tier role and a number from 1 to 4,
        validates the input and returns a range of tiers
        that the player will join.

        If force_tier is True, the tier range will only be limit_tier_num
        """
        if not tier_role:
            raise TierValidationException("No tienes Tier... Habla con algún admin para que te asigne una.")
        
        if limit_tier_num is not None:
            limit_tier_name = f'Tier {limit_tier_num}'
            
            if limit_tier_name not in TIER_NAMES: # Invalid number
                raise TierValidationException(f"Formato inválido: únete a la cola con `.friendlies X`, con X siendo un número de 1 a 4")
            
            # Get role of limit_tier
            limit_tier_role = self.tier_roles[limit_tier_name]
            
            if tier_role < limit_tier_role: # Tu tier es inferior a la de la lista
                raise TierValidationException(f"Intentas colarte en la lista de la {limit_tier_name}, pero aún eres de {tier_role.name}... ¡A seguir mejorando!")
        else:
            limit_tier_num = tier_role.name[-1]

        if force_tier:
            return range(int(limit_tier_num), int(limit_tier_num) + 1)
        else:
            return range(int(tier_role.name[-1]), int(limit_tier_num) + 1)

    # *************************************
    #       S E A R C H      L I S T
    # *************************************
    async def can_join_search(self, player):
        if player in self.confirmation_list:
            raise AlreadyMatchedException("¡Ya tienes match! Ve a aceptarlo o espera a que tu rival conteste.")

        for match in self.arena_status.values():
            if match is not None and player in match:
                raise AlreadyMatchedException("¡Ya estás jugando con alguien! ¿Te has olvidado de cerrar la arena con `.ggs`?")
        return True

    def is_match_possible(self, tier_range=range(1, 5)):
        """
        Checks whether a match can be found in the given range
        and if true, returns a set with both players.
        """
        for i in tier_range:
            tier_list = self.search_list[f'Tier {i}']
            if len(tier_list) < 2:
                continue
            match_set_combinations = map(set, itertools.combinations(tier_list, 2))
            match = next((match_set for match_set in match_set_combinations if match_set not in self.rejected_list), None)

            if match is not None:
                return list(match)
        return False
    
    async def add_to_search_list(self, player, tier_range):
        """
        Adds a player to every search list in the passed range.
        Returns a list with the tier numbers where the player
        has been added
        """        
        tiers_added = []
        
        for i in tier_range:
            if DEV_MODE or player not in self.search_list[f'Tier {i}']:
                self.search_list[f'Tier {i}'].append(player)
                tiers_added.append(i)        
        if tiers_added:
            asyncio.create_task(self.update_list_message())

        return tiers_added

    async def remove_from_search_list(self, player, tier_range):
        """
        Removes a player from every list in the given tier_range.
        """
        tiers_removed = []
        
        for i in tier_range:
            if player in self.search_list[f'Tier {i}']:
                self.search_list[f'Tier {i}'].remove(player)
                tiers_removed.append(i)
        
        if tiers_removed:
            asyncio.create_task(self.update_list_message())
        
        return tiers_removed

    async def remove_from_rejected_list(self, match_set):
        await asyncio.sleep(WAIT_AFTER_REJECT)
        self.rejected_list.remove(match_set)
        # After the timeout has happened, try matchmaking in case they're still there
        await self.matchmaking()

    # ************************************************
    #          M  A  T  C  H  M  A  K  I  N  G
    # ************************************************

    async def matchmaking(self, ctx, player1, player2, resp_body):
        match_found = True

        while match_found:
            match_confirmation = await self.confirm_match(player1, player2)

            if match_confirmation.get('all_accepted', False):
                # ACCEPTED MATCH
                arena_id = match_confirmation['arena_id']
                return await self.set_arena(ctx, player1, player2, arena_id)
            else:
                # REJECTED MATCH, SEARCH AGAIN
                player_id = match_confirmation['searching_player']
                body = {'min_tier' : match_confirmation['min_tier'], 'max_tier' : match_confirmation['max_tier']}

                async with self.bot.session.get(f'http://127.0.0.1:8000/players/{player_id}/matchmaking/', json=body) as response:
                    if response.status == 200:
                        html = await response.text()
                        resp_body = json.loads(html)

                        # Match
                        player1 = ctx.guild.get_member(resp_body['player_one'])
                        player2 = ctx.guild.get_member(resp_body['player_two'])
                        match_found = True
                    
                    elif response.status == 404:
                        #  Ping tiers again
                        match_found = False
                        player = ctx.guild.get_member(player_id)
                        tiers = match_confirmation['tiers']
                        for tier in tiers:
                            channel = ctx.guild.get_channel(tier['channel'])
                            tier_role = ctx.guild.get_role(tier['id'])
                            await channel.send(f"Atención {tier_role.mention}, ¡**{player.nickname()}** sigue buscando rival!")                                               
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
        
        # await self.update_list_message()
        
    #         # Edit messages
    #         edited_text = f"**¡{player1.nickname()}** y **{player2.nickname()}** están jugando!"
    #         await asyncio.gather(*[message.edit(content=edited_text) for player in match for message in self.mention_messages.get(player, [])])

    
    #  ***********************************************
    #          C  O  N  F  I  R  M  A  T  I  O  N
    #  ***********************************************
        
    async def confirm_match(self, player1, player2):
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

        # Tasks
        reaction_tasks = []
                    
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
            # React
            await asyncio.gather(message.add_reaction(EMOJI_CONFIRM), message.add_reaction(EMOJI_REJECT))
            await asyncio.sleep(0.5)

            try:
                # Wait for user reaction
                try:
                    emoji, player = await self.bot.wait_for('reaction_add', timeout=FRIENDLIES_TIMEOUT, check=check_message)
                    is_timeout = False
                except asyncio.TimeoutError:                
                    emoji = None
                    is_timeout = True
                finally:
                    remove_reactions = [message.remove_reaction(EMOJI, self.bot.user) for EMOJI in (EMOJI_CONFIRM, EMOJI_REJECT)]
                    await asyncio.gather(*remove_reactions)

                # API Call
                body = { 'accepted' : str(emoji) == EMOJI_CONFIRM, 'timeout' : is_timeout}

                async with self.bot.session.patch(f'http://127.0.0.1:8000/players/{player.id}/confirmation/', json=body) as response:                    
                    if response.status == 200:
                        html = await response.text()
                        resp_body = json.loads(html)

                        all_accepted = resp_body.get('all_accepted', False)
                        player_accepted = resp_body.get('player_accepted', False)

                        #  ACCEPTED, WAITING...
                        if player_accepted and not all_accepted:
                            cancel_message = await player.send("No contesta... puedes esperar un rato más, o cancelar el match.")
                            
                            def check_cancel_message(reaction, user):
                                is_same_message = (reaction.message == cancel_message)
                                is_valid_emoji = (reaction.emoji in (EMOJI_REJECT))

                                return is_same_message and is_valid_emoji
                            
                            await cancel_message.add_reaction(EMOJI_REJECT)
                            await asyncio.sleep(0.5)
                            
                            emoji, player = await self.bot.wait_for('reaction_add', check=check_cancel_message)
                            await cancel_message.remove_reaction(EMOJI_REJECT, self.bot.user)
                            
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
        
        if not player_accepted:
            if is_timeout:
                passive_message = f"¿Hola? Parece que no estás... El match ha sido cancelado, y te he quitado de las listas -- puedes volver a apuntarte si quieres."
                active_message = f"Parece que {passive_player.nickname()} no está... Te he vuelto a meter en las listas de búsqueda."
            else:
                active_message = f"Vale, match rechazado. Te he sacado de todas las colas."
                passive_message = f"**{active_player.nickname()}** ha rechazado el match... ¿en otro momento, quizás?\nTe he metido en las listas otra vez."
            
            await asyncio.gather(active_player.send(active_message), passive_player.send(passive_message))                
        
        return confirmation_data

    async def confirm_invite(self, host1, host2, player, arena):
        message = await player.send(f"**{host1.nickname()}** y **{host2.nickname()}** te invitan a jugar con ellos en su arena. ¿Aceptas?")

        # React
        await asyncio.gather(message.add_reaction(EMOJI_CONFIRM), message.add_reaction(EMOJI_REJECT))
        await asyncio.sleep(0.5)
        
        # Wait for user reaction
        invite_task = asyncio.create_task(self.wait_invite_reaction(message, host1, host2, player, arena), name=f"{host1}{host2}{player}{arena}")
        self.arena_invites[arena.name].append(invite_task)
        await invite_task

    @asyncio.coroutine
    async def wait_invite_reaction(self, message, host1, host2, player, arena):
        def check_message(reaction, user):
            is_same_message = (reaction.message == message)
            is_valid_emoji = (reaction.emoji in (EMOJI_CONFIRM, EMOJI_REJECT))

            return is_same_message and is_valid_emoji

        try:
            emoji, player = await self.bot.wait_for('reaction_add', check=check_message)
            
            remove_reactions = [message.remove_reaction(EMOJI, self.bot.user) for EMOJI in (EMOJI_CONFIRM, EMOJI_REJECT)]
            await asyncio.gather(*remove_reactions)
            
            if str(emoji) == EMOJI_REJECT:
                await player.send(f"Vale, sin problema.")
                await arena.send(f"**{player.nickname()}** ha rechazado la invitación a la arena.")
            else:
                has_removed = await self.remove_from_search_list(player, range(1, 5))
                self.arena_status[arena.name].append(player)
                await self.give_arena_permissions(player, arena)
                await self.update_list_message()
                
                # Delete invites before going to arena
                if arena.name in self.arena_invites.keys():
                    for invite in self.arena_invites[arena.name]:
                        invite_name = invite.get_name()
                        current_task_name = asyncio.current_task().get_name()
                        
                        if invite_name != current_task_name:
                            invite.cancel()
                    self.arena_invites[arena.name] = []
                                
                # Edit messages
                edited_text = f"**{player.nickname(guild=self.guild)}** está jugando con **{host1.nickname()}** y **{host2.nickname()}**."
                await asyncio.gather(*[message.edit(content=edited_text) for message in self.mention_messages.get(player, [])])                

                # Remove current_search
                self.current_search.pop(player, None)

                await arena.send(f"Abran paso, que llega el low tier {player.mention}.")
                await player.send(f"Perfecto {player.mention}, ¡dirígete a {arena.mention} y saluda a tus anfitriones!")

        except asyncio.CancelledError as e:
            remove_reactions = [message.remove_reaction(EMOJI, self.bot.user) for EMOJI in (EMOJI_CONFIRM, EMOJI_REJECT)]
            await asyncio.gather(*remove_reactions)
            await player.send("Ya han dejado de jugar o se ha llenado el hueco, rip. ¡Intenta estar más atento la próxima vez!")
            return

    #  ***********************************************
    #           A   R   E   N   A   S
    #  ***********************************************    
    def get_arena(self, arena_name):
        return next((arena for arena in self.arenas if arena.name == arena_name), None)
    
    async def give_arena_permissions(self, player, arena):
        await arena.set_permissions(player, read_messages=True, send_messages=True)

    async def remove_arena_permissions(self, player, arena):
        await arena.set_permissions(player, read_messages=False, send_messages=False)
    
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
        # Arena list and status dictionary updated
        # self.arenas.append(channel)
        # self.arena_status[new_arena_name] = None
        # self.arena_invites[new_arena_name] = []

        # return channel
            
    async def delete_arenas(self):
        for arena in self.arenas:
            await self.delete_arena(arena)        

    async def delete_arena(self, arena):
        if arena not in self.arenas:
            return
        
        self.arenas.remove(arena)
        self.arena_status.pop(arena.name, None)

        if arena.name in self.arena_invites.keys():            
            for invite in self.arena_invites[arena.name]:
                invite.cancel()
            self.arena_invites.pop(arena.name, None)
        
        await arena.delete()
  
    # *******************************
    #           L I S T
    # *******************************

    async def update_list_message(self):        
        response = ""
        
        for tier in TIER_NAMES:
            players = ", ".join([player.nickname() for player in self.search_list[tier]])
            players = players if players else " "
            response += f"**{tier}**:\n```{players}```\n"
        
        if self.arena_status.values():
            response += f"**ARENAS:**\n"
        for match in self.arena_status.values():            
            match_message = f"**{match[0].nickname()}** ({self.get_tier(match[0]).name})"
            
            for player in match[1:]:
                match_message += f" vs. **{player.nickname()}** ({self.get_tier(player).name})"

            response += f"{match_message}\n"                    
        
        await self.list_message.edit(content=response)
    
    async def invite_mention_list(self, ctx, tier_range):
        response = (f"**__Lista de menciones:__**\n"
            f"_¡Simplemente reacciona con el emoji del jugador a invitar (solo uno)!_\n")
        
        arena = ctx.channel

        # Get unique players
        players = []
       
        for tier_num in tier_range:
            tier_name = f'Tier {tier_num}'
                        
            for player in self.search_list[tier_name]:
                if player not in players:        
                    players.append(player)

        # There are only 10 emojis with numbers. For now that'll be more than enough.
        players = players[:10]

        if not players:
            return await ctx.send("No hay nadie buscando partida.")

        for i, player in enumerate(players, start=1):
            response += f"{i}. {player.nickname()} ({self.get_tier(player).name})\n"
        
        message = await arena.send(response)
        
        message_reactions = [message.add_reaction(emoji) for emoji in NUMBER_EMOJIS[ : len(players)]]
        await asyncio.gather(*message_reactions)

        def check_message(reaction, user):
            is_same_message = (reaction.message == message)
            is_valid_emoji = (reaction.emoji in (NUMBER_EMOJIS))
            is_author = (user == ctx.author)

            return is_same_message and is_valid_emoji and is_author

        emoji, player = await self.bot.wait_for('reaction_add', check=check_message)

        player_index = NUMBER_EMOJIS.index(str(emoji))

        invited_player = players[player_index]

        invite_task = asyncio.create_task(self.invite(ctx, invited_player))        
        return await invite_task
    
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
        await self.delete_arenas()
        
        self.search_list = {f"Tier {i}" : [] for i in range(1, 5)}
        self.confirmation_list = []
        self.rejected_list = []
                
        await self.update_list_message()
        
        print("Clean up complete")
    
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