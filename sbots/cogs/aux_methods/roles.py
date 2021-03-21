import discord

from .text import key_format
from ..params.roles import SMASH_CHARACTERS, NORMALIZED_SMASH_CHARACTERS

async def update_or_create_roles(guild, all_roles, all_roles_names, roles, update=False):
    """
    Creates or updates the roles in the guild.
    """
    created_count = 0
    updated_count = 0
    
    for role_name in roles.keys():        
        # GET COLOR
        color_hex = roles[role_name].get('color')
        if color_hex:
            color = discord.Color(value=color_hex)
        else:
            color = discord.Color.default()
        
        # CREATE
        if role_name not in all_roles_names:
            new_role = await guild.create_role(name=role_name, mentionable=True, color=color)
            created_count += 1
        # UPDATE
        elif update:
            old_role = next((role for role in all_roles if role.name == role_name), None)
            await old_role.edit(name=role_name, mentionable=True, color=color)
            updated_count += 1
    
    return created_count, updated_count
    

def normalize_character(character_name):
    """
    Accepts other ways of calling the characters, and returns the correct one.
    False if the character doesn't exist
    """
    char = key_format(character_name)

    if char in NORMALIZED_SMASH_CHARACTERS:
        return next((char_name for char_name in SMASH_CHARACTERS.keys() if key_format(char_name) == char), None)

    if char in ('dk', 'donkey', 'donkey kong'):
        return 'Donkey Kong'
    if char in ('samus', 'dark samus', 'samus/dark samus', 'upb'):
        return 'Samus/Dark Samus'
    if char in ('captain falcon', 'capitan falcon', 'falcon'):
        return 'Captain Falcon'
    if char in ('peach/daisy', 'peach', 'daisy'):
        return 'Peach/Daisy'
    if char in ('ice climbers', 'icies', 'ics', 'ic'):
        return 'Ice Climbers'
    if char in ('dr. mario', 'dr.mario', 'doc', 'doctor mario', 'dr mario'):
        return 'Dr. Mario'
    if char in ('young link', 'link niño', 'yink'):
        return 'Young Link'
    if char in ('ganondorf', 'ganon'):
        return 'Ganondorf'
    if char in ('gaw', 'mr. game & watch', 'mr. game and watch', 'g&w', 'mr gaw', 'mr. gaw', 'game and watch', 'game & watch', 'game&watch'):
        return 'Mr. Game & Watch'
    if char in ('meta knight', 'metaknight', 'mk', 'metalknight'):
        return 'Meta Knight'
    if char in ('pit/dark pit', 'pit', 'dark pit', 'pittoo', 'dpit', 'pit sombrio'):
        return 'Pit/Dark Pit'
    if char in ('zero suit samus', 'zss', 'zzs', 'samus zero'):
        return 'Zero Suit Samus'
    if char in ('pokemon trainer', 'pkmn trainer', 'pokemon', 'charizard', 'ivysaur', 'squirtle'):
        return 'Pokémon Trainer'
    if char in ('diddy kong', 'diddy', 'ddk'):
        return 'Diddy Kong'
    if char in ('king dedede', 'rey dedede', 'ddd', 'd3', '3d', 'dedede'):
        return 'King Dedede'
    if char in ('olimar', 'alph'):
        return 'Olimar'
    if char in ('r.o.b.', 'rob', 'r.o.b', 'r.ob', 'robot'):
        return 'R.O.B.'
    if char in ('atun', 'toon', 'tink', 'tlink'):
        return 'Toon Link'
    if char in ('aldeano'):
        return 'Villager'
    if char in ('megaman', 'mega', 'mega-man'):
        return 'Mega Man'
    if char in ('wft', 'wii fit', 'entrenadora', 'entrenadora de wii fit'):
        return 'Wii Fit Trainer'
    if char in ('rosalina and luma', 'estela y destello', 'rosalina', 'estela', 'luma', 'destello', 'estela & destello'):
        return 'Rosalina & Luma'
    if char in ('mac', 'lmac', 'lm'):
        return 'Little Mac'
    if char in ('mii espadachin', 'espadachin', 'swordfighter', 'mii sword'):
        return 'Mii Swordfighter'
    if char in ('mii karateka', 'karateka', 'brawler'):
        return 'Mii Brawler'
    if char in ('pacman', 'pac man', 'pac', 'waka'):
        return 'Pac-Man'
    if char in ('palu', 'patulena'):
        return 'Palutena'
    if char in ('daraen'):
        return 'Robin'
    if char in ('bowser jr', 'bowsy', 'larry', 'ludwig', 'lemmy', 'iggy', 'wendy', 'morton', 'roy koopa', 'koopaling', 'koopalings'):
        return 'Bowser Jr.'
    if char in ('dhd', 'duck hunt duo', 'duo duck hunt', 'perro', 'perropato', 'duckhunt', 'dick hunt', 'ddh', 'dog'):
        return 'Duck Hunt'
    if char in ('bayonneta', 'bayonneta', 'bayo'):
        return 'Bayonetta'
    if char in ('rydle', 'ridel', 'ridli'):
        return 'Ridley'
    if char in ('simon', 'richter', 'belmonts', 'belmont'):
        return 'Simon/Richter'
    if char in ('king k rool', 'k rool', 'kkr', 'king krool', 'k. rool', 'cocodrilo'):
        return 'King K. Rool'
    if char in ('canela'):
        return 'Isabelle'
    if char in ('pp', 'planta pirana', 'planta', 'plant'):
        return 'Piranha Plant'
    if char in ('el bromas', 'bromista', 'arsene', 'persona'):
        return 'Joker'
    if char in ('heroe', 'dragon quest', 'dq'):
        return 'Hero'
    if char in ('b&k', 'banjo', 'kazooie', 'banjo and kazooie', 'banjo&kazooie'):
        return 'Banjo & Kazooie'
    if char in ('minmin', 'min-min', 'ramen', 'noodle'):
        return 'Min Min'
    if char in ('minecraft', 'esteban', 'alex', 'zombi', 'zombie', 'enderman', 'ender'):
        return 'Steve'
    if char in ('sefirot', 'sefiroth', 'sephirot'):
        return 'Sephiroth'
    if char in ('pyra', 'mythra', 'pythra', 'aegis', 'homura', 'hikari', 'homura/hikari'):
        return 'Pyra/Mythra'
    
    return False

def find_role(param, role_list):
    """
    Given a param, this method returns the role 
    with an "acceptable" name in that list,
    acceptable meaning lowercase + no accent matching,
    and for characters some name variations are allowed as well.
    """
    key_param = key_format(param)
    
    role_dict = {key_format(role.name): role for role in role_list}

    # DIRECTLY:
    if key_param in role_dict.keys():
        return role_dict[key_param]

    # CHECK IF TIER ROLE
    tier_key = f'tier {key_param}'
    if tier_key in role_dict.keys():
        return role_dict[tier_key]

    # CHECK IF CHARACTER    
    if normalized_key := normalize_character(key_param):
        return role_dict[key_format(normalized_key)]

    return False    