from ..params.flairing_params import (FLAIRING_CHANNEL_ID, SPAM_CHANNEL_ID)

# ***********************
# ***********************
#       C H E C K S
# ***********************
# ***********************

def in_flairing_channel(ctx):
    return ctx.channel.id == FLAIRING_CHANNEL_ID

def in_spam_channel(ctx):
    return ctx.channel.id == SPAM_CHANNEL_ID