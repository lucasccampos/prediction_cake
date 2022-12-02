"""
PancakeData

epoch = data[0]
startTimestamp = data[1]
lockTimestamp = data[2]
closeTimestamp = data[3]
lockPrice = data[4]
closePrice = data[5]
lockOracleId = data[6]
closeOracleId = data[7]
totalAmount = data[8]
bullAmount = data[9]
bearAmount = data[10]
rewardBaseCalAmount = data[11]
rewardAmount = data[12]
oracleCalled = data[13]
currentPrice = data[14]

"""


import datetime
from utils.betEnum import BetEnum


class RoundInfo:
    def __init__(self, data):
        list_struct = ['epoch', 'start_timestamp', 'lock_timestamp', 'close_timestamp', 'lock_price', 'close_price', 'lock_oracle_id', 'close_oracle_id', 'total_amount', 'bull_amount', 'bear_amount', 'reward_base', 'reward_amount', 'oracle_called']

        if type(data) != dict:
            data = dict(zip(list_struct, data))

        self.data = data
        self.data["lock_price"] /= 10**8
        self.data["close_price"] /= 10**8
        self.__dict__.update(self.data)

        self.cancelled = self.bear_amount <= 0 or self.bull_amount <= 0 or self.lock_price <= 0 or self.close_price <= 0 or (self.close_price == self.lock_price)

    def __repr__(self) -> str:
        return f"Round({self.epoch}) - Closed({self.GetSideWinner()})"

    def GetDate(self):
        date = datetime.datetime.fromtimestamp(self.lock_timestamp, tz=datetime.timezone.utc)#.replace(tzinfo=datetime.timezone.utc)

        return date

    def GetDateStr(self, format="%d/%m/%y"):
        return self.GetDate().strftime(format)

    def GetSideWinner(self):
        return BetEnum.UP if self.lock_price < self.close_price else BetEnum.DOWN

    def GetMultiplier(self, side):
        if(self.cancelled):
            return 0

        if(side == BetEnum.UP):
            return self.total_amount / self.bull_amount
        return self.total_amount / self.bear_amount

    def GetWinnerSideMultiplier(self):
        return self.GetMultiplier(self.GetSideWinner())

    def GetLowerSideMultiplier(self):
        return BetEnum.UP if self.bull_amount > self.bear_amount else BetEnum.DOWN
