class RejectedException(Exception):
    def __init__(self, player):
        self.player = player
        self.reason = "REJECT"
    
    def __str__(self):
        return f'{player.name} has rejected the match.'

class ConfirmationTimeOutException(Exception):
    def __init__(self, player):
        self.player = player
        self.reason = "TIMEOUT"
    
    def __str__(self):
        return f"{player.name} hasn't answered the confirmation."

class TierValidationException(Exception):
    pass

class AlreadyMatchedException(Exception):
    pass