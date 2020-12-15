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

class AlreadySearchingException(Exception):
    def __init__(self, player):
        self.player = player
        self.reason = "REPEATED"
    
    def __str__(self):
        return f"{player.name} is already in that search_list"