TIER_NAMES = ("Tier 1", "Tier 2", "Tier 3", "Tier 4")

EMOJI_CONFIRM = '\u2705' #✅
EMOJI_REJECT = '\u274C' #❌
EMOJI_HOURGLASS = '\U000023f3'

NUMBER_EMOJIS = (
    *[f'{i}\N{variation selector-16}\N{combining enclosing keycap}' for i in range(1, 10)],
    '\N{keycap ten}',
)


WAIT_AFTER_REJECT = 3600
FRIENDLIES_TIMEOUT = 90
GGS_ARENA_COUNTDOWN = 15