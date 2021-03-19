from ..aux_methods.text import key_format

SPANISH_REGIONS = [
    {'name': "Albacete", 'emoji' : r"<:albacete:821185419685003324>", 'color': 0x981932},
    {'name': "Alicante", 'emoji' : r"<:alicante:821185419881480192>", 'color': 0x1885D6},
    {'name': "Andalucía", 'emoji' : r"<:andalucia:821185419445010432>", 'color': 0x006331},
    {'name': "Aragón", 'emoji' : r"<:aragon:821185419907039242>", 'color': 0xce7b16},
    {'name': "Asturias", 'emoji' : r"<:asturias:821185419123228703>", 'color': 0x0063F7},
    {'name': "Baleares", 'emoji' : r"<:baleares:821185418917576744>", 'color': 0x3E0F4A},
    {'name': "Canarias", 'emoji' : r"<:canarias:821185418946674699>", 'color': 0xF7C600},
    {'name': "Cantabria", 'emoji' : r"<:cantabria:821185418955063316>", 'color': 0xD31119},
    {'name': "Catalunya", 'emoji' : r"<:catalunya:821185418871177297>", 'color': 0xffaa00},
    {'name': "Castellón", 'emoji' : r"<:castellon:821185418597761055>", 'color': 0x018A2C},
    {'name': "Ciudad Real", 'emoji' : r"<:ciudadreal:821185419659051038>", 'color': 0x891F39},
    {'name': "Euskadi", 'emoji' : r"<:euskadi:821185418803675156>", 'color': 0x009646},
    {'name': "Extremadura", 'emoji' : r"<:extremadura:821185420326338632>", 'color': 0x086F37},
    {'name': "Galicia", 'emoji' : r"<:galicia:821185419215503360>", 'color': 0x78B3DF},
    {'name': "Guadalajara", 'emoji' : r"<:guadalajara:821185419819483146>", 'color': 0x81007F},
    {'name': "León", 'emoji' : r"<:leon:821185420439191562>", 'color': 0x981932},
    {'name': "Madrid", 'emoji' : r"<:madrid:821185418904600637>", 'color': 0xC00B1D},
    {'name': "Murcia", 'emoji' : r"<:murcia:821185418565255190>", 'color': 0x9c1f2d},
    {'name': "La Rioja", 'emoji' : r"<:larioja:821185418988355590>", 'color': 0x63B628},
    {'name': "Salamanca", 'emoji' : r"<:salamanca:821185420141264957>", 'color': 0x981932},
    {'name': "Toledo", 'emoji' : r"<:toledo:821185419956715540>", 'color': 0x9D155C},
    {'name': "Valencia", 'emoji' : r"<:valencia:821185419256397874>", 'color': 0x0072BC},
    {'name': "Valladolid", 'emoji' : r"<:valladolid:821185420292653056>", 'color': 0x9B0829},
]

SMASH_CHARACTERS = [
    {"name" : "Mario", "emoji": r"<:mario:821163357162700890>", "color": 0xE90E13},
    {"name" : "Donkey Kong", "emoji": r"<:donkeykong:821163356928081990>", "color": 0x784326},
    {"name" : "Link", "emoji": r"<:link:821163357096378398>", "color": 0x6E73A2},
    {"name" : "Samus/Dark Samus", "emoji": r"<:samus:821160189889478687>/<:darksamus:821163356927819806>", "color": 0xFA9C46},
    {"name" : "Yoshi", "emoji": r"<:yoshi:821160189973102602>", "color": 0x6BC55C},
    {"name" : "Kirby", "emoji": r"<:kirby:821163357037789214>", "color": 0xFFA5BE},
    {"name" : "Fox", "emoji": r"<:fox:821163356761096233>", "color": 0xF0D18C},
    {"name" : "Pikachu", "emoji": r"<:pikachu:821160189817389086>", "color": 0xFDDE45},
    {"name" : "Luigi", "emoji": r"<:luigi:821163357112631337>", "color": 0x51A83E},
    {"name" : "Ness", "emoji": r"<:ness:821163357049454592>", "color": 0xF7666A},
    {"name" : "Captain Falcon", "emoji": r"<:captainfalcon:821163356756115466>", "color": 0xFE6571},
    {"name" : "Jigglypuff", "emoji": r"<:jigglypuff:821163356995846194>", "color": 0xF2BBC0},
    {"name" : "Peach/Daisy", "emoji": r"<:peach:821160189524049952>/<:daisy:821163357187866624>", "color": 0xF285AE},
    {"name" : "Bowser", "emoji": r"<:bowser:821163356734881832>", "color": 0x1D770A},
    {"name" : "Ice Climbers", "emoji": r"<:iceclimbers:821163356521889813>", "color": 0x5A5DBA},
    {"name" : "Sheik", "emoji": r"<:sheik:821160190106927124>", "color": 0x9C9BAD},
    {"name" : "Zelda", "emoji": r"<:zelda:821160189624713228>", "color": 0xEB78A3},
    {"name" : "Dr. Mario", "emoji": r"<:drmario:821163356626747403>", "color": 0xCBCDCE},
    {"name" : "Pichu", "emoji": r"<:pichu:821160190073503774>", "color": 0xFCF0B0},
    {"name" : "Falco", "emoji": r"<:falco:821163356621766688>", "color": 0x3256CA},
    {"name" : "Marth", "emoji": r"<:marth:821163357281320961>", "color": 0x385A73},
    {"name" : "Lucina", "emoji": r"<:lucina:821163356793995336>", "color": 0x385A73},
    {"name" : "Young Link", "emoji": r"<:younglink:821160190182162462>", "color": 0x5B8D56},
    {"name" : "Ganondorf", "emoji": r"<:ganondorf:821163356995846154>", "color": 0x91835B},
    {"name" : "Mewtwo", "emoji": r"<:mewtwo:821163357276471326>", "color": 0xD9CFE6},
    {"name" : "Roy", "emoji": r"<:roy:821160189825777734>", "color": 0x853031},
    {"name" : "Chrom", "emoji": r"<:chrom:821163356660170763>", "color": 0x5B7392},
    {"name" : "Mr. Game & Watch", "emoji": r"<:gaw:821163356835938384>", "color": 0x000000},
    {"name" : "Meta Knight", "emoji": r"<:metaknight:821163357054566410>", "color": 0xA0AAB2},
    {"name" : "Pit/Dark Pit", "emoji": r"<:pit:821160190006394880>/<:darkpit:821163356886663208>", "color": 0xFCD7A3},
    {"name" : "Zero Suit Samus", "emoji": r"<:zerosuitsamus:821160190077829190>", "color": 0x496AB6},
    {"name" : "Wario", "emoji": r"<:wario:821160189649485826>", "color": 0xF5EB2D},
    {"name" : "Snake", "emoji": r"<:snake:821160190006657136>", "color": 0x627075},
    {"name" : "Ike", "emoji": r"<:ike:821163356739338291>", "color": 0x525375},
    {"name" : "Pokémon Trainer", "emoji": r"<:pokemontrainer:821160189809917982>", "color": 0xFB4433},
    {"name" : "Diddy Kong", "emoji": r"<:diddykong:821163356772892692>", "color": 0xBB8056},
    {"name" : "Lucas", "emoji": r"<:lucas:821163357054697523>", "color": 0xE9C166},
    {"name" : "Sonic", "emoji": r"<:sonic:821160190094868580>", "color": 0x354CF3},
    {"name" : "King Dedede", "emoji": r"<:dedede:821163356441542677>", "color": 0x1D64DF},
    {"name" : "Olimar", "emoji": r"<:olimar:821163357067018261>", "color": 0xD0C161},
    {"name" : "Lucario", "emoji": r"<:lucario:821163357087465483>", "color": 0x2D6DA4},
    {"name" : "R.O.B.", "emoji": r"<:rob:821160189922115604>", "color": 0xD6D6D6},
    {"name" : "Toon Link", "emoji": r"<:toonlink:821160190073896961>", "color": 0x80B561},
    {"name" : "Wolf", "emoji": r"<:wolf:821160190049124372>", "color": 0x585697},
    {"name" : "Villager", "emoji": r"<:villager:821160190141005824>", "color": 0xF2312D},
    {"name" : "Mega Man", "emoji": r"<:megaman:821163356856516669>", "color": 0x457EE2},
    {"name" : "Wii Fit Trainer", "emoji": r"<:wiifittrainer:821160189704011777>", "color": 0xE3E1E0},
    {"name" : "Rosalina & Luma", "emoji": r"<:rosalina:821160190010589184>", "color": 0x6EF1E3},
    {"name" : "Little Mac", "emoji": r"<:littlemac:821163357154705438>", "color": 0x6AB259},
    {"name" : "Greninja", "emoji": r"<:greninja:821163356886663228>", "color": 0x3A4FEB},
    {"name" : "Mii Swordfighter", "emoji": r"<:miiswordfighter:821163357004365824>", "color": 0x728DE2},
    {"name" : "Mii Gunner", "emoji": r"<:miigunner:821163356848521257>", "color": 0xF0B03D},
    {"name" : "Mii Brawler", "emoji": r"<:miibrawler:821163356957966336>", "color": 0xD34243},
    {"name" : "Palutena", "emoji": r"<:palutena:821160189477912587>", "color": 0x3B9336},
    {"name" : "Pac-Man", "emoji": r"<:pacman:821160189935878214>", "color": 0xFDF168},
    {"name" : "Robin", "emoji": r"<:robin:821160190023696385>", "color": 0x1B1B1D},
    {"name" : "Shulk", "emoji": r"<:shulk:821160189893804043>", "color": 0xFD5D6B},
    {"name" : "Bowser Jr.", "emoji": r"<:bowserjr:821163356685598760>", "color": 0x96C450},
    {"name" : "Duck Hunt", "emoji": r"<:duckhuntduo:821163356794388540>", "color": 0xCD6838},
    {"name" : "Ryu", "emoji": r"<:ryu:821160190082285588>", "color": 0xA2A198},
    {"name" : "Ken", "emoji": r"<:ken:821163357142122556>", "color": 0xCB5647},
    {"name" : "Cloud", "emoji": r"<:cloud:821163356823879700>", "color": 0x5C5473},
    {"name" : "Corrin", "emoji": r"<:corrin:821163356424896524>", "color": 0xE6D0B3},
    {"name" : "Bayonetta", "emoji": r"<:bayonetta:821163356647194676>", "color": 0xA13EF7},
    {"name" : "Inkling", "emoji": r"<:inkling:821163356857040947>", "color": 0xF49231},
    {"name" : "Ridley", "emoji": r"<:ridley:821160190010196009>", "color": 0x888095},
    {"name" : "Simon/Richter", "emoji": r"<:simon:821160190152802364>/<:richter:821160189846880276>", "color": 0x878B8C},
    {"name" : "King K. Rool", "emoji": r"<:kingkrool:821163356932407316>", "color": 0xACCE8D},
    {"name" : "Isabelle", "emoji": r"<:isabelle:821163357079994378>", "color": 0xFEF69E},
    {"name" : "Incineroar", "emoji": r"<:incineroar:821163356874211348>", "color": 0xF66A63},
    {'name': "Piranha Plant", 'emoji': r"<:piranhaplant:821160189469524009>", "color": 0x388334},
    {"name" : "Joker", "emoji" : r"<:joker:821163357456564274", "color": 0x4F78E9},
    {"name" : "Hero", "emoji" : r"<:hero:821163356836069386>", "color": 0xB38CC3},
    {"name" : "Banjo & Kazooie","emoji" : r"<:banjokazooie:821163356613378079>", "color": 0xA55943},
    {"name" : "Terry","emoji" : r"<:terry:821160189905862657>", "color": 0xB4454F},
    {"name" : "Byleth","emoji" : r"<:byleth:821163356273901589>", "color": 0x32576B},
    {"name" : "Min Min","emoji" : r"<:minmin:821163357163618305>", "color": 0xEABA5F},
    {"name" : "Steve","emoji" : r"<:steve:821160190056726548>", "color": 0x15C4C4},
    {"name" : "Sephiroth","emoji" : r"<:sephiroth:821160190132224010>", "color": 0xB6BBC7},
    {"name" : "Pyra/Mythra","emoji" : r"<:pyra:821160189813850212>", "color": 0x2AF8D3},
]

DEFAULT_TIERS = [
    {'name': "Tier 1", "emoji": "", "color": 0xE74C3C},
    {'name': "Tier 2", "emoji": "", "color": 0x3498DB},
    {'name': "Tier 3", "emoji": "", "color": 0xF1C40F},
    {'name': "Tier 4", "emoji": "", "color": 0xE91E63},
]

NORMALIZED_SMASH_CHARACTERS =  [key_format(character['name']) for character in SMASH_CHARACTERS]