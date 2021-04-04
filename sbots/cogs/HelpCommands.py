import discord
import asyncio

from discord.ext import tasks, commands

from .params.roles import SPANISH_REGIONS

from .checks.matchmaking_checks import (in_arena, in_tier_channel)
from .checks.flairing_checks import (in_flairing_channel, in_spam_channel)

class HelpCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.footer_image = "https://www.smashbros.com/assets_v2/img/top/hero05_en.jpg"        
    
    @commands.command()
    async def help(self, ctx, arg = None):
        is_tier_channel = await in_tier_channel(ctx)
        is_in_arena = in_arena(ctx)
        is_flairing_channel = await in_flairing_channel(ctx)
        is_spam_channel = await in_spam_channel(ctx)

        is_default = not is_tier_channel and not is_in_arena and not is_flairing_channel
        is_default = is_default and not is_spam_channel
        
        if arg is None and is_default:
            return await self.default_help(ctx)
        
        if arg is None:
            arg = ''
        
        if is_tier_channel or arg.lower() == 'matchmaking':
            return await self.matchmaking_help(ctx)
        
        if is_in_arena or arg.lower() == 'arenas':
            return await self.arenas_help(ctx)
        
        if is_flairing_channel or arg.lower() == 'roles':
            return await self.flairing_help(ctx)
        
        if is_spam_channel or arg.lower() == 'role-list':
            return await self.spam_help(ctx)
    
    async def default_help(self, ctx):
        embed = discord.Embed(title="Smash Bot Spain", colour=discord.Colour(0x9919e1), description="Escribe el comando .help en los canales relevantes para ver la descripción de los comandos (o `.help matchmaking`, por ejemplo, para ver los comandos de matchmaking).")

        embed.set_image(url="https://www.guiasnintendo.com/2c-switch/super-smash-bros-ultimate/guia-super-smash-bros-ultimate/imagenes/fotos/super-smash-bros-ultimate-00327.jpg")        
        embed.set_footer(text="Smash Bot Spain Help", icon_url=self.footer_image)

        embed.add_field(name="Matchmaking", value="Comandos de búsqueda de matches.", inline=False)
        embed.add_field(name="Arena", value="Comandos de las arenas.", inline=False)
        embed.add_field(name="Roles", value="Comandos relacionados con los roles (a usar en #roles)", inline=False)

        await ctx.send(embed=embed)

    
    async def matchmaking_help(self, ctx):
        embed = discord.Embed(title="Matchmaking:", colour=discord.Colour(0x9919e1), description="A continuación se describen los diferentes comandos de matchmaking (disponibles en los canales #tier):")

        embed.set_image(url="https://i.ytimg.com/vi/83UUsOPq3C0/maxresdefault.jpg")    
        embed.set_footer(text="Matchmaking Help", icon_url=self.footer_image)

        friendlies_field = """Escribe `.friendlies` para buscar partida.
            - Si lo escribes en el canal de tu tier, se te incluirá en esa cola.
            - Si lo escribes en un canal de tier más baja, se te incluirá en todas las colas accesibles hasta esa.\n
            _(Ejemplo: Si eres tier 2 y escribes `.friendlies` en #tier-4, te meteré en la cola de Tier 2, Tier 3 y Tier 4.)_\n
            - Si escribes `.friendlies-here` en un canal de tier más baja, se te incluirá **solo** en esa cola.\n
            _(Ejemplo: Si eres Tier 2 y escribes `.friendlies-here` en #tier-4, te meteré solo en la cola de Tier 4.)_\n
            Cuando se encuentre match, recibirás un MD pidiendo confirmación, y se abrirá una arena privada para los dos.\n
            """
        
        embed.add_field(name="`.friendlies`", value=friendlies_field, inline=False)

        embed.add_field(name="**Actualizar búsqueda**", inline=False, value="Si empiezas a buscar en una Tier y quieres cambiar de lista, simplemente haz otro comando `.friendlies` donde quieras ahora y ya")
        
        embed.add_field(name="`.cancel`", value="Escribe `.cancel` para salir de todas las colas de matchmaking.", inline=False)

        await ctx.send(embed=embed)

    async def arenas_help(self, ctx):
        embed = discord.Embed(title="Arenas:", colour=discord.Colour(0x9919e1), description="A continuación se describen los diferentes comandos disponibles en la arena:")
        embed.set_image(url="https://exion-vault.com/wp-content/uploads/2019/08/Featured-Image-amiibo-Wiki-Battle-Arenas-672x307.png")        
        embed.set_footer(text="Arenas Help", icon_url=self.footer_image)

        embed.add_field(name="`.invite`", value="El comando `.invite` permite añadir a esta arena a una persona que esté buscando partida.\n\t- Si escribís `.invite @X`, invitaréis a esa persona. _(pero tiene que ser con la mención)_.\n\t- Si escribís `.invite` a secas, aparecerán hasta 10 personas que estén en cola. Pulsad el emoji de la persona para enviarles la invitación.\n\nEn cualquier caso, la persona recibirá una invitación por MD.", inline=False)
        embed.add_field(name="`.ggs`", value="Escribe `.ggs` para cerrar la arena.", inline=False)

        await ctx.send(embed=embed)
    
    async def flairing_help(self, ctx):
        embed = discord.Embed(title="Roles:", colour=discord.Colour(0x9919e1), description="Hay tres tipos de roles que os podéis asignar (siempre en el canal #roles):")
        embed.set_footer(text="Roles Help", icon_url=self.footer_image)

        embed.add_field(name="`.region`", inline=False, value=f"El comando `.region` te permite añadir el rol de tu región.\n_(Regiones disponibles: {', '.join([region_name for region_name in SPANISH_REGIONS.keys()])})_\n\n_Ejemplo: `.region Catalunya`_\n")
        
        embed.add_field(
            name="`.main`",
            inline=False,
            value=(
                "Los comandos `.main`, `.second` y `.pocket` te permiten añadir el rol de tu personaje.\n"
                "Solo podréis tener 2 mains, el resto de personajes tendrán que ir a seconds o a pockets.\n"
                "Los roles están en inglés, pero en principio podéis poner el nombre en castellano, y poner nombres alternativos"
                " mientras no desfaséis mucho.\n\n_Ejemplo: `.main palu`_\n"
            )
        )
        embed.add_field(name="`.tier`", inline=False, value=f"El comando `.tier` seguido de un número del 2 al 4 te asignará el rol de esa Tier, para así poder recibir sus pings.\nNo puedes ni quitarte tu propia tier, ni autoasignarte una tier superior.\n\n_Ejemplo: `.tier 4`_\n")
        embed.add_field(name="Eliminar roles", inline=False, value=f"Usando uno de estos comandos cuando ya tenéis el rol, os lo quitará.\n\n_Ejemplo: Si tengo el rol de main Mario y escribo `.main Mario`, se me quitará el rol._")
        await ctx.send(embed=embed)

    async def spam_help(self, ctx):
        embed = discord.Embed(title="Lista de roles:", colour=discord.Colour(0x9919e1), description="Actualmente hay dos roles que podéis usar en el canal de spam: ")
        embed.set_footer(text="Role List Help", icon_url=self.footer_image)

        embed.add_field(name="`.role`", inline=False, value=f"El comando `.role` o `.rol` seguido del nombre del rol (no importan mayúsculas ni minúsculas, y con los pjs se aceptan cosas como gaw, ddd o palu) os dará una lista con todos los jugadores con ese rol.")
        embed.add_field(name="`.regiones`, `.tiers`, `.mains`, `.seconds`, `.pockets`", inline=False, value=f"Escribid cualquiera de estos comandos para obtener una lista con cada rol de esa categoría (regiones, personajes o tiers).")
        
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(HelpCommands(bot))
