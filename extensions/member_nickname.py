import discord

def nickname(self):
    if isinstance(self, discord.Member):
        return self.nick if self.nick else self.name
    elif isinstance(self, discord.User):
        return self.name
    else:
        return None

def setup(bot):
    discord.Member.nickname = nickname
    discord.User.nickname = nickname