class Bet():
    def __init__(self, epoch, bet_side, amount, date=None):
        self.epoch = epoch
        self.bet_side = bet_side
        self.amount = amount
        self.date = date
        self.closed = False
    
    def __repr__(self) -> str:
        return f"Bet({self.epoch})_({self.amount:4f})"