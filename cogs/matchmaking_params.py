LIST_CHANNEL_ID = 788119086512865311
LIST_MESSAGE_ID = 788119751033487383

TIER_NAMES = ("Tier 1", "Tier 2", "Tier 3", "Tier 4")
TIER_CHANNEL_NAMES = ("tier-1", "tier-2", "tier-3", "tier-4")

DEV_MODE = False  # IF SET TO TRUE, A PLAYER CAN ALWAYS JOIN THE LIST

EMOJI_CONFIRM = '\u2705' #✅
EMOJI_REJECT = '\u274C' #❌

NUMBER_EMOJIS = (
    *[f'{i}\N{variation selector-16}\N{combining enclosing keycap}' for i in range(1, 10)],
    '\N{keycap ten}',
)


WAIT_AFTER_REJECT = 3600
GGS_ARENA_COUNTDOWN = 30