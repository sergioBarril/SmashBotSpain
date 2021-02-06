class RejectedException(Exception):
    REASON = "REJECT"
    def __init__(self, player):
        self.player = player
            
    def __str__(self):
        return f'{player.name} has rejected the match.'

class ConfirmationTimeOutException(Exception):
    REASON = "TIMEOUT"
    def __init__(self, player):
        self.player = player
            
    def __str__(self):
        return f"{player.name} hasn't answered the confirmation."

class TierValidationException(Exception):
    pass

class AlreadyMatchedException(Exception):
    pass