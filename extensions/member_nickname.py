import discord

def nickname(self, guild=None):
    if isinstance(self, discord.Member):
        return self.nick if self.nick else self.name
    elif isinstance(self, discord.User):
        if guild is not None:
            return guild.get_member(self.id).nickname()
        else:
            return self.name
    else:
        return None

def setup(bot):
    discord.Member.nickname = nickname
    discord.User.nickname = nickname