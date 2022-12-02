from utils.betEnum import BetEnum
import numpy as np
import pandas as pd
from enum import IntEnum


class BacktestingStrategy():
    def __init__(self, logger):
        self.logger = logger

    def log(self, message):
        if self.logger != None:
            self.logger.log(message)
        else:
            print(message)

    @classmethod
    def populate(cls, data):
        pass

    def calculate(data):
        data["bet"] = False

    @classmethod
    def name(cls):
        return "[None Strategy]"

    def strategy_details(self):
        return ""

    def get_data(self):
        return {}

    def wrong_side(self, data):
        data["wrong_side"] = False

    def __repr__(self) -> str:
        return f"{self.name()}\n{self.strategy_details()}"

    def __str__(self) -> str:
        return f"{self.name()}\n{self.strategy_details()}"


# Backtesting strategies


class ClosingHigherBacktesting(BacktestingStrategy):
    def __init__(self, threshold, bet_after_higher_rounds, safe_closing_threshold=0.2, reverse=False, logger=None):
        self.threshold = threshold
        self.logger = logger
        self.reverse = reverse
        self.bet_after_higher_rounds = bet_after_higher_rounds
        self.preload_rounds = bet_after_higher_rounds+3
        self.safe_closing_threshold = safe_closing_threshold

    @classmethod
    def name(cls):
        return "[ClosingHigher Strategy]"

    @classmethod
    def strategy_generator(cls, reverse=False):
        config = {}
        config["SAFE_GAP"] = 0.15
        for x in range(1, 10):
            for y in range(51):
                for z in range(51):
                    yield cls(threshold=y/100, bet_after_higher_rounds=x, safe_closing_threshold=z/100, reverse=reverse, logger=None), config.copy()

    def strategy_details(self):
        return f"\nGap Threshold: {self.threshold}" + \
            f"\nBet after higher rounds: {self.bet_after_higher_rounds}" + \
            f"\nSafe Closing Threshold: {self.safe_closing_threshold}"

    def get_data(self):
        return {"threshold": self.threshold, "bet_after_higher_rounds": self.bet_after_higher_rounds, "safe_closing_threshold": self.safe_closing_threshold, "reverse": self.reverse}

    @classmethod
    def populate(cls, data):
        data["price_gap"] = data["binance_price"] - data["oracle_price"]
        closing_round = data.shift(1)
        data["safe_closing_gap"] = data["oracle_price"] - \
            closing_round["lock_price"]
        data["closing_higher"] = (closing_round["bull_amount"] < closing_round["bear_amount"]) == (
            data["safe_closing_gap"] > 0)
        data["closed_higher"] = (data["close_price"] > data["lock_price"]) == (
            data["bear_amount"] > data["bull_amount"])
        b = (data['closed_higher'].shift(2, fill_value=0)*1)
        c = b.cumsum()
        data["seq_rounds"] = c.sub(
            c.mask(b != 0).ffill(), fill_value=0).astype(int)

    def calculate(self, data):
        data["bet"] = (data["closing_higher"]) & (np.abs(data["price_gap"]) > self.threshold) & (np.abs(
            data["safe_closing_gap"]) > self.safe_closing_threshold) & (data["seq_rounds"] >= self.bet_after_higher_rounds-1)
        bet_rounds = data.loc[data["bet"] == True]
        data["bet_side"] = bet_rounds["price_gap"] > 0
        if self.reverse:
            data["bet_side"] = np.logical_not(data["bet_side"].dropna())

    def wrong_side(self, data):
        data.loc[:, "wrong_side"] = data.loc[:,
                                             "bull_amount"] < data.loc[:, "bear_amount"]
        if self.reverse:
            data["wrong_side"] = np.logical_not(data.loc[:, "wrong_side"])


class ClosingLowerBacktesting(BacktestingStrategy):
    def __init__(self, threshold, bet_after_lower_rounds, safe_closing_threshold=0.2, reverse=False, logger=None):
        self.threshold = threshold
        self.logger = logger
        self.reverse = reverse
        self.bet_after_lower_rounds = bet_after_lower_rounds
        self.preload_rounds = bet_after_lower_rounds+3
        self.safe_closing_threshold = safe_closing_threshold

    @classmethod
    def name(cls):
        return "[ClosingLower Strategy]"

    @classmethod
    def strategy_generator(cls, reverse=False):
        config = {}
        config["SAFE_GAP"] = 0.15
        for x in range(1, 10):
            for y in range(51):
                for z in range(51):
                    yield cls(threshold=y/100, bet_after_lower_rounds=x, safe_closing_threshold=z/100, reverse=reverse, logger=None), config.copy()

    def strategy_details(self):
        return f"\nGap Threshold: {self.threshold}" + \
            f"\nBet after lower rounds: {self.bet_after_lower_rounds}" + \
            f"\nSafe Closing Threshold: {self.safe_closing_threshold}"

    def get_data(self):
        return {"threshold": self.threshold, "bet_after_lower_rounds": self.bet_after_lower_rounds, "safe_closing_threshold": self.safe_closing_threshold, "reverse": self.reverse}

    @staticmethod
    def populate(data):
        data["price_gap"] = data["binance_price"] - data["oracle_price"]
        closing_round = data.shift(1)
        data["safe_closing_gap"] = data["oracle_price"] - \
            closing_round["lock_price"]
        data["closing_lower"] = (closing_round["bull_amount"] > closing_round["bear_amount"]) == (
            data["safe_closing_gap"] > 0)
        data["closed_lower"] = (data["close_price"] > data["lock_price"]) == (
            data["bear_amount"] < data["bull_amount"])
        b = (data['closed_lower'].shift(2, fill_value=0)*1)
        c = b.cumsum()
        data["seq_rounds"] = c.sub(
            c.mask(b != 0).ffill(), fill_value=0).astype(int)

    def calculate(self, data):
        data["bet"] = (data["closing_lower"]) & (np.abs(data["price_gap"]) > self.threshold) & (np.abs(
            data["safe_closing_gap"]) > self.safe_closing_threshold) & (data["seq_rounds"] >= self.bet_after_lower_rounds-1)
        bet_rounds = data.loc[data["bet"] == True]
        data["bet_side"] = bet_rounds["price_gap"] > 0
        if self.reverse:
            data["bet_side"] = np.logical_not(data["bet_side"].dropna())

    def wrong_side(self, data):
        data.loc[:, "wrong_side"] = data.loc[:,
                                             "bull_amount"] < data.loc[:, "bear_amount"]
        if self.reverse:
            data["wrong_side"] = np.logical_not(data.loc[:, "wrong_side"])