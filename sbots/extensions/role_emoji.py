import discord

from cogs.params.roles import SMASH_CHARACTERS, SPANISH_REGIONS, DEFAULT_TIERS

def emoji(self):
    """
    Returns the emoji associated to this role (or an empty string)
    if there isn't one.
    """
    role_name = self.name

    for db in (SMASH_CHARACTERS, SPANISH_REGIONS, DEFAULT_TIERS):
        if role := db.get(role_name, False):
            return role.get("emoji", "")
    
    return ""

def setup(bot):
    # pass
    discord.Role.emoji = emoji