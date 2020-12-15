import discord
import asyncio

from discord.ext import tasks, commands
from .Exceptions import RejectedException, ConfirmationTimeOutException, AlreadySearchingException


TIER_ROLES = ("Tier 1", "Tier 2", "Tier 3", "Tier 4")
DEV_MODE = True  # IF SET TO TRUE, A PLAYER CAN ALWAYS JOIN THE LIST

class Matchmaking(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.search_list = {f"Tier {i}" : [] for i in range(1, 5)}
    
    def setup_matchmaking(self, guild, list_message):
        self.guild = guild
        
        self.arenas =  discord.utils.get(self.guild.categories, name="ARENAS").channels
        self.arena_status = {f"arena-{i}" : None for i in range(1, len(self.arenas) + 1)}
        
        self.list_message = list_message
    
    @commands.command()
    async def friendlies(self, ctx):
        """
        You can join the list of friendlies with this command.
        """
        # Get player and tier
        player = ctx.author
        tier = self.get_tier(player)
        
        if not tier:
            await ctx.send("No tienes Tier... Habla con algún admin para que te asigne una.")
            return
        
        # Add them to search
        try:
            await self.add_to_search_list(player, tier)
        except AlreadySearchingException:
            return await ctx.send(f"Hey {player.mention}, you're already in!")
        
        await ctx.send(f"Perfecto {player.mention}, te acabo de meter.")        
        
        while self.is_match_possible(tier):

            match = self.search_list[tier.name][:2]

            player1, player2 = match
            
            # Remove from the list
            asyncio.gather(*[self.remove_from_search_list(player, tier) for player in match])

            # Send DM with confirmation
            confirmation = await self.confirm_match(player1, player2)
            if not confirmation['accepted']:
                player_to_reinsert = confirmation['player_to_reinsert']
                tier = self.get_tier(player_to_reinsert)

                await self.add_to_search_list(player_to_reinsert, tier, 0)                
                continue

            # Get and lock an arena
            arena = await self.get_free_arena()
            self.arena_status[arena.name] = match

            #Set Permissions            
            arena_permissions = [arena.set_permissions(player, read_messages=True, send_messages=True) for player in match]
            await asyncio.gather(*arena_permissions)
            
            # Send invites for faster arena access
            await self.send_invites(arena, player1, player2)
            
            await arena.send(f"¡Perfecto, aceptasteis ambos! {match[0].mention} y {match[1].mention}, ¡a jugar!")
            await arena.send(f"Recordad usar `.ggs` al acabar, para así poder cerrar la arena.")

    @commands.command()
    async def ggs(self, ctx):
        await ctx.send("GGs, ¡gracias por jugar!")
        await asyncio.sleep(10)
        if ctx.channel in self.arenas:
            await self.delete_arena(ctx.channel)
        
        else: 
            # Search the channel to close
            arena_to_close = None
            for arena in self.arenas:
                if ctx.author in self.arena_status[arena.name]:
                    arena_to_close = arena
                    break            
            # Delete it
            if arena_to_close:
                await self.delete_arena(arena_to_close)

    @commands.command()
    async def cancel(self, ctx):
        player = ctx.author
        tier = self.get_tier(player)

        if player in self.search_list[tier.name]:
            await self.remove_from_search_list(player, tier)
            await ctx.send(f"Vale {player.mention}, te saco de la cola. ¡Hasta pronto!")
        else:
            await ctx.send(f"No estás en ninguna cola, {player.mention}. Usa `.friendlies` para unirte a una.")
        
    def is_match_possible(self, tier):
        return len(self.search_list[tier.name]) > 1

    def get_tier(self, player):
        if isinstance(player, discord.member.Member):
            member = player
        else:            
            member = self.guild.get_member(player.id)        
        
        return next((role for role in member.roles if role.name in TIER_ROLES), None)    
            

    
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
        EMOJI_CONFIRM = '\u2705' #✅
        EMOJI_REJECT = '\u274C' #❌

        @asyncio.coroutine
        async def send_confirmation(player1, player2):
            return await player1.send(f"¡Match encontrado! {player1.mention}, te toca contra {player2.mention}. ¿Aceptas?")

        # Send confirmation
        task1 = asyncio.create_task(send_confirmation(player1, player2))
        task2 = asyncio.create_task(send_confirmation(player2, player1))
        confirm_message1, confirm_message2 = await asyncio.gather(task1, task2)
        
        @asyncio.coroutine
        async def initial_reactions(message):
            def check_message(reaction, user):
                is_same_message = (reaction.message == message)
                is_valid_emoji = (reaction.emoji in (EMOJI_CONFIRM, EMOJI_REJECT))

                return is_same_message and is_valid_emoji
            
            # React
            await asyncio.gather(message.add_reaction(EMOJI_CONFIRM), message.add_reaction(EMOJI_REJECT))
            await asyncio.sleep(0.5)

            # Wait for user reaction
            try:
                emoji, player = await self.bot.wait_for('reaction_add', timeout=35.0, check=check_message)
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

        reaction_tasks.append(asyncio.create_task(initial_reactions(confirm_message1)))
        reaction_tasks.append(asyncio.create_task(initial_reactions(confirm_message2)))

        try:
            reaction1, reaction2 = await asyncio.gather(*reaction_tasks)
        except (RejectedException, ConfirmationTimeOutException) as e:
            for task in reaction_tasks:
                task.cancel()

            exception_messages = {}
            
            # Different messages for the exceptions
            rejected_message = f"{e.player.mention} ha rechazado el match... ¿en otro momento, quizás?\nEl match ha sido cancelado, y has sido puesto en cola de nuevo."
            rejecter_message = f"Vale, match rechazado."
            timeouted_message = f"{e.player.mention} no responde... ¿se habrá quedado dormido?\nEl match ha sido cancelado, y has sido puesto en cola de nuevo." 
            timeouter_message = f"Parece que no hay nadie en casa...\nEl match ha sido cancelado, vuelve a intentarlo e intenta estar atento."

            exception_messages["REJECT"] = [rejected_message, rejecter_message]
            exception_messages["TIMEOUT"] = [timeouted_message, timeouter_message]
            
            exception_pair = exception_messages[e.reason]

            if e.player == player1:
                exception_pair.reverse()
            
            await player1.send(exception_pair[0])
            await player2.send(exception_pair[1])
            
            return {"accepted": False, "player_to_reinsert": player1 if e.player != player1 else player2}
        return {"accepted": True}


    async def send_invites(self, arena, player1, player2):
        invite_link = await arena.create_invite(max_age=25, max_uses=1, reason="Acceder más rápido al canal")
        
        players = player1, player2

        message_tasks = [player.send(f"Listo, dirígete a la #{arena.name}") for player in players]        
        messages = await asyncio.gather(*message_tasks)

        send_invite_tasks = [player.send(invite_link) for player in players]
        invite_messages = await asyncio.gather(*send_invite_tasks)

        async def delete_invite(invite_message):
            await asyncio.sleep(25)
            await invite_message.delete()
        
        delete_invite_tasks = [delete_invite(invite) for invite in invite_messages]
        asyncio.gather(*delete_invite_tasks)


    #  ***********************************************
    #           A   R   E   N   A   S
    #  ***********************************************
    
    async def add_to_search_list(self, player, tier, index = None):
        if player in self.search_list[tier.name] and not DEV_MODE:
            raise AlreadySearchingException(player)
        
        if index is None:
            self.search_list[tier.name].append(player)
        else:
            self.search_list[tier.name].insert(index, player)
        
        asyncio.create_task(self.update_list_message())
    
    async def remove_from_search_list(self, player, tier):
        if not self.search_list[tier.name]:
            raise Exception()
        self.search_list[tier.name].remove(player)
        asyncio.create_task(self.update_list_message())
        
        return player

    async def get_free_arena(self):
        return next((arena for arena in self.arenas if not arena in self.arena_status[arena.name]), await self.make_arena())

    async def make_arena(self):
        arenas_category = discord.utils.get(self.guild.categories, name="ARENAS")        
        new_arena_name = f'arena-{len(self.arenas) + 1}'
        channel = await arenas_category.create_text_channel(new_arena_name)
        
        # Arena list and status dictionary updated
        self.arenas.append(channel)
        self.arena_status[new_arena_name] = None

        return channel
            
    @commands.command()
    async def delete_arenas(self, ctx):
        for arena in self.arenas:
            await arena.delete()
        self.arena_status = {}
        self.arenas = []

    async def delete_arena(self, arena):
        self.arenas.remove(arena)
        self.arena_status.pop(arena.name, None)
        await arena.delete()
  
    # *******************************
    #           L I S T
    # *******************************

    async def update_list_message(self):        
        response = "**__Friendlies list:__**\n"
        
        for tier in TIER_ROLES:
            players = ", ".join([player.name for player in self.search_list[tier]])
            response += f"__{tier}__: {players}\n"
        
        await self.list_message.edit(content=response)

def setup(bot):
    bot.add_cog(Matchmaking(bot))