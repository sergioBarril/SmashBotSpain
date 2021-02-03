import unicodedata
import os
from dotenv import load_dotenv

load_dotenv()
PROD_MODE = os.getenv('PROD_MODE') == "YES"

FLAIRING_CHANNEL_ID = 805889422151122964 if PROD_MODE else 805511941094113291
SPAM_CHANNEL_ID = 806240906784800808 if PROD_MODE else 806239848612364339

REGIONS = [
    "Albacete",
    "Alicante",
    "Andalucía",
    "Aragón",
    "Asturias",
    "Baleares",
    "Canarias",
    "Cantabria",
    "Catalunya",
    "Castellón",
    "Ciudad Real",
    "Euskadi",
    "Extremadura",
    "Galicia",
    "León",
    "Madrid",
    "Murcia",
    "La Rioja",
    "Toledo",
    "Valencia",
    "Valladolid"
]

def no_accents(text):
    text = unicodedata.normalize('NFD', text)\
        .encode('ascii', 'ignore')\
        .decode("utf-8")
    return str(text)

def key_format(text):
    return no_accents(text.lower())


CHARACTERS = [
    "Mario",
    "Donkey Kong",
    "Link",
    "Samus/Dark Samus",
    "Yoshi",
    "Kirby",
    "Fox",
    "Pikachu",
    "Luigi",
    "Ness",
    "Captain Falcon",
    "Jigglypuff",
    "Peach/Daisy",
    "Bowser",
    "Ice Climbers",
    "Sheik",
    "Zelda",
    "Dr. Mario",
    "Pichu",
    "Falco",
    "Marth",
    "Lucina",
    "Young Link",
    "Ganondorf",
    "Mewtwo",
    "Roy",
    "Chrom",
    "Mr. Game & Watch",
    "Meta Knight",
    "Pit/Dark Pit",
    "Zero Suit Samus",
    "Wario",
    "Snake",
    "Ike",
    "Pokémon Trainer",
    "Diddy Kong",
    "Lucas",
    "Sonic",
    "King Dedede",
    "Olimar",
    "Lucario",
    "R.O.B.",
    "Toon Link",
    "Wolf",
    "Villager",
    "Mega Man",
    "Wii Fit Trainer",
    "Rosalina & Luma",
    "Little Mac",
    "Greninja",
    "Mii Swordfighter",
    "Mii Gunner",
    "Mii Brawler",
    "Palutena",
    "Pac-Man",
    "Robin",
    "Shulk",
    "Bowser Jr.",
    "Duck Hunt",
    "Ryu",
    "Ken",
    "Cloud",
    "Corrin",
    "Bayonetta",
    "Inkling",
    "Ridley",
    "Simon/Richter",
    "King K. Rool",
    "Isabelle",
    "Incineroar",
    "Piranha Plant",
    "Joker",
    "Hero",
    "Banjo & Kazooie",
    "Terry",
    "Byleth",
    "Min Min",
    "Steve",
    "Sephiroth"
]

NORMALIZED_CHARACTERS = [key_format(character) for character in CHARACTERS]


def normalize_character(character_name):
    """
    Accepts other ways of calling the characters, and returns the correct one.
    False if the character doesn't exist
    """
    char = key_format(character_name)

    if char in NORMALIZED_CHARACTERS:
        return next((character for character in CHARACTERS if key_format(character) == char), None)

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
    
    return False