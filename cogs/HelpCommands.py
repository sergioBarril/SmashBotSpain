import discord
import asyncio

from discord.ext import tasks, commands

from .params.matchmaking_params import (TIER_NAMES, TIER_CHANNEL_NAMES, EMOJI_CONFIRM, EMOJI_REJECT, 
                    NUMBER_EMOJIS, LIST_CHANNEL_ID, LIST_MESSAGE_ID,
                    WAIT_AFTER_REJECT, GGS_ARENA_COUNTDOWN, DEV_MODE,
                    FRIENDLIES_TIMEOUT)

from .checks.matchmaking_checks import (in_their_arena, in_tier_channel)

class HelpCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.footer_image = "https://www.smashbros.com/assets_v2/img/top/hero05_en.jpg"        
    
    @commands.command()
    async def help(self, ctx, arg = None):
        if arg is None and not in_tier_channel(ctx) and not in_their_arena(ctx):
            return await self.default_help(ctx)        
        
        if arg is None:
            arg = ''
        
        if in_tier_channel(ctx) or arg.lower() == 'matchmaking':
            return await self.matchmaking_help(ctx)
        
        if in_their_arena(ctx) or arg.lower() == 'arenas':
            return await self.arenas_help(ctx)

    
    async def default_help(self, ctx):
        embed = discord.Embed(title="Smash Bot Spain", colour=discord.Colour(0x9919e1), description="Escribe el comando .help en los canales relevantes para ver la descripción de los comandos (o `.help matchmaking`, por ejemplo, para ver los comandos de matchmaking).")

        embed.set_image(url="https://www.guiasnintendo.com/2c-switch/super-smash-bros-ultimate/guia-super-smash-bros-ultimate/imagenes/fotos/super-smash-bros-ultimate-00327.jpg")        
        embed.set_footer(text="Smash Bot Spain Help", icon_url=self.footer_image)

        embed.add_field(name="Matchmaking", value="Comandos de búsqueda de matches.", inline=False)
        embed.add_field(name="Arena", value="Comandos de las arenas.", inline=False)

        await ctx.send(embed=embed)

    
    async def matchmaking_help(self, ctx):
        embed = discord.Embed(title="Matchmaking:", colour=discord.Colour(0x9919e1), description="A continuación se describen los diferentes comandos de matchmaking:")

        embed.set_image(url="https://i.ytimg.com/vi/83UUsOPq3C0/maxresdefault.jpg")    
        embed.set_footer(text="Matchmaking Help", icon_url=self.footer_image)

        embed.add_field(name="`.friendlies`", value="Escribe `.friendlies` para buscar partida.\n\t- Si lo escribes en el canal de tu tier, se te incluirá en esa cola.\n\t- Si lo escribes en un canal de tier más baja, se te incluirá en todas las colas accesibles hasta esa.\n\n(_Ejemplo: Si eres tier 2 y escribes `.friendlies` en #tier-4, te meteré en la cola de Tier 2, Tier 3 y Tier 4._)\n\nCuando se encuentre match, recibirás un MD pidiendo confirmación, y se abrirá una arena privada para los dos.", inline=False)
        embed.add_field(name="`.cancel`", value="Escribe `.cancel` para salir de todas las colas de matchmaking.", inline=False)

        await ctx.send(embed=embed)

    async def arenas_help(self, ctx):
        embed = discord.Embed(title="Arenas:", colour=discord.Colour(0x9919e1), description="A continuación se describen los diferentes comandos disponibles en la arena:")
        embed.set_image(url="https://exion-vault.com/wp-content/uploads/2019/08/Featured-Image-amiibo-Wiki-Battle-Arenas-672x307.png")        
        embed.set_footer(text="Arenas Help", icon_url=self.footer_image)

        embed.add_field(name="`.invite`", value="El comando `.invite` permite añadir a esta arena a una persona que esté buscando partida.\n\t- Si escribís `.invite @X`, invitaréis a esa persona. _(pero tiene que ser con la mención)_.\n\t- Si escribís `.invite` a secas, aparecerán hasta 10 personas que estén en cola. Pulsad el emoji de la persona para enviarles la invitación.\n\nEn cualquier caso, la persona recibirá una invitación por MD.", inline=False)
        embed.add_field(name="`.ggs`", value="Escribe `.ggs` para cerrar la arena.", inline=False)

        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(HelpCommands(bot))
