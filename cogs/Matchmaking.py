import discord
import asyncio
import re
import itertools
import typing
from datetime import datetime, timedelta

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
        tier_role = self.get_tier(player)

        # Check if player can join the search lists
        try:
            await self.can_join_search(ctx.author)
        except AlreadyMatchedException as e:
            return await ctx.send(e)

        # Check Force-tier mode:
        is_force_tier = ctx.invoked_with == "friendlies-here"

        # If .friendlies in #tier-x:
        if tier_num is None:
            channel_name = ctx.channel.name if ctx.guild else None
            
            if channel_name in TIER_CHANNEL_NAMES:
                tier_num = channel_name[-1]

        # Validate tiers
        try:
            tier_range = self.tier_range_validation(tier_role, tier_num, is_force_tier)
        except TierValidationException as e:
            return await ctx.send(e)
        
        # Add them to search
        tiers_added = await self.add_to_search_list(player, tier_range)

        # Remove unwanted tiers
        tiers_removed = await self.remove_from_search_list(player, (i for i in range(1, 5) if i not in tier_range))

        if not tiers_added and not tiers_removed:
            return await ctx.send(f"Pero {player.mention}, ¡si ya estabas en la cola!")
        
        # Update current_search record
        self.current_search[player] = tier_range
        
        if not self.is_match_possible(tier_range):
            # Mention @Tier X
            tier_mention_tasks = []
            for tier_num in tiers_added:  
                tier_role = self.tier_roles[f'Tier {tier_num}']
                tier_channel = self.tier_channels[f'Tier {tier_num}']
                mention_message = f"Atención {tier_role.mention}, ¡**{ctx.author.nickname()}** busca rival! Escribe el comando `.friendlies` para retarle a jugar."

                tier_mention_tasks.append(tier_channel.send(mention_message))            
            if tier_mention_tasks:
                if player not in self.mention_messages.keys():
                    self.mention_messages[player] = []
                self.mention_messages[player] += await asyncio.gather(*tier_mention_tasks)
            else:
                tiers_removed_join = ", ".join([f"Tier {i}" for i in tiers_removed])
                if len(tiers_removed) == 1:
                    tiers_removed_str = f"la {tiers_removed_join}"
                else:
                    tiers_removed_str = f"las siguientes tiers: {tiers_removed_join}"                
                
                await ctx.send(f"Vale {player.nickname()}, has dejado de buscar en {tiers_removed_str}.")
        
        # Matchmaking
        await self.matchmaking(tier_range)

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

    async def matchmaking(self, tier_range = range(1, 5)):        
        # MATCH WHILE
        is_reinserted = False
        while match := self.is_match_possible(tier_range):
            is_reinserted = False
            player1, player2 = match            
            
            # Remove from all lists
            asyncio.gather(*[self.remove_from_search_list(player, range(1, 5)) for player in match])            

            # Add them to the confirmation_list
            self.confirmation_list.extend(match)

            # Send DM with confirmation
            confirmation = await self.confirm_match(player1, player2)
            
            if not confirmation['accepted']:
                player_to_reinsert = confirmation['player_to_reinsert']
                
                self.confirmation_list.remove(player1)
                self.confirmation_list.remove(player2)

                if confirmation['reason'] == RejectedException.REASON:
                    self.rejected_list.append({player1, player2})
                    asyncio.create_task(self.remove_from_rejected_list({player1, player2}))
                
                tier_range = self.current_search[player_to_reinsert]
                tiers_added = await self.add_to_search_list(player_to_reinsert, tier_range)                

                if tiers_added:
                    reinsert_message = f"Te he puesto otra vez en la cola de: {', '.join([f'Tier {tier_num}' for tier_num in tiers_added])}"
                    await player_to_reinsert.send(reinsert_message)
                    is_reinserted = True
                continue

            # Get and lock an arena
            arena = await self.make_arena()
            self.arena_status[arena.name] = match
            await self.update_list_message()
                        
            # Remove them from the confirmation list
            self.confirmation_list.remove(player1)
            self.confirmation_list.remove(player2)

            #Set Permissions            
            arena_permissions = [arena.set_permissions(player, read_messages=True, send_messages=True) for player in match]
            await asyncio.gather(*arena_permissions)                        
            
            # Send arena
            message_tasks = [player.send(f"Listo, dirígete a {arena.mention}") for player in match]
            await asyncio.gather(*message_tasks)
            
            await arena.send(f"¡Perfecto, aceptasteis ambos! {player1.mention} y {player2.mention}, ¡a jugar!")
            await arena.send(f"Recordad usar `.ggs` al acabar, para así poder cerrar la arena.\n_(Para más información de las arenas, usad el comando `.help`)_")

            # Edit messages
            edited_text = f"**¡{player1.nickname()}** y **{player2.nickname()}** están jugando!"
            await asyncio.gather(*[message.edit(content=edited_text) for player in match for message in self.mention_messages.get(player, [])])

            # Delete current_search from both players
            self.current_search.pop(player1, None)
            self.current_search.pop(player2, None)

            # Check if there's still someone who can be matched in any tier
            tier_range = range(1, 5)
        
        if is_reinserted:
            for tier_num in tier_range:
                tier = self.tier_roles[f'Tier {tier_num}']
                message = await self.tier_channels[tier.name].send(f"Atención {tier.mention}, ¡**{player_to_reinsert.nickname()}** sigue buscando rival!")
                self.mention_messages[player_to_reinsert].append(message)
    
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
        
        @asyncio.coroutine
        async def reactions(message):
            def check_message(reaction, user):
                is_same_message = (reaction.message == message)
                is_valid_emoji = (reaction.emoji in (EMOJI_CONFIRM, EMOJI_REJECT))

                return is_same_message and is_valid_emoji
            
            # React
            await asyncio.gather(message.add_reaction(EMOJI_CONFIRM), message.add_reaction(EMOJI_REJECT))
            await asyncio.sleep(0.5)

            # Wait for user reaction
            try:
                emoji, player = await self.bot.wait_for('reaction_add', timeout=FRIENDLIES_TIMEOUT, check=check_message)
            except asyncio.TimeoutError:                
                raise ConfirmationTimeOutException(message.channel.recipient)
            finally:
                remove_reactions = [message.remove_reaction(EMOJI, self.bot.user) for EMOJI in (EMOJI_CONFIRM, EMOJI_REJECT)]
                await asyncio.gather(*remove_reactions)

            if str(emoji) == EMOJI_REJECT:
                raise RejectedException(player)
            else:
                await player.send(f"Aceptaste el match — ahora toca esperar a que tu rival conteste.")
        
        reaction_tasks = []

        reaction_tasks.append(asyncio.create_task(reactions(confirm_message1)))
        reaction_tasks.append(asyncio.create_task(reactions(confirm_message2)))

        try:
            reaction1, reaction2 = await asyncio.gather(*reaction_tasks)
        except (RejectedException, ConfirmationTimeOutException) as e:
            for task in reaction_tasks:
                task.cancel()

            exception_messages = {}
            
            # Different messages for the exceptions
            rejected_message = f"**{e.player.nickname()}** ha rechazado el match... ¿en otro momento, quizás?"
            rejecter_message = f"Vale, match rechazado."
            timeouted_message = f"**{e.player.nickname()}** no responde... ¿se habrá quedado dormido?" 
            timeouter_message = f"Parece que no hay nadie en casa... El match ha sido cancelado, vuelve a intentarlo e intenta estar atento."

            exception_messages[RejectedException.REASON] = [rejected_message, rejecter_message]
            exception_messages[ConfirmationTimeOutException.REASON] = [timeouted_message, timeouter_message]
            
            exception_pair = exception_messages[e.REASON]

            if e.player == player1:
                exception_pair.reverse()
            
            await asyncio.gather(player1.send(exception_pair[0]), player2.send(exception_pair[1]))

            return {"accepted": False, "player_to_reinsert": player1 if e.player != player1 else player2, "reason" : e.REASON}
        return {"accepted": True}


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
        def get_arena_number(arena):
            return int(arena.name[arena.name.index("-") + 1:])

        arenas_category = discord.utils.get(self.guild.categories, name="ARENAS")
        new_arena_number = max(map(get_arena_number, self.arenas), default=0) + 1
        new_arena_name = f'arena-{new_arena_number}'
        channel = await arenas_category.create_text_channel(new_arena_name)
        
        # Arena list and status dictionary updated
        self.arenas.append(channel)
        self.arena_status[new_arena_name] = None
        self.arena_invites[new_arena_name] = []

        return channel
            
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