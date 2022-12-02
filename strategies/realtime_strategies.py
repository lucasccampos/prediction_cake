from datetime import timezone
import time

from openpyxl import Workbook
from utils.binanceCandle import BinanceCandle
from utils.folders import *
from utils.betEnum import BetEnum
import csv
import requests

from utils.prediction_utils import get_oracle_data_text, get_oracle_price, get_binance_price, get_kcandle


def loadBinanceDataFromRounds(roundsData, symbol="BNBUSDT", timeframe="1m"):
    binanceData = {}
    PATH = BINANCE_FOLDER / symbol / timeframe
    for round_number in roundsData:
        try:
            if roundsData[round_number].cancelled:
                continue
            date = roundsData[round_number].GetDateStr('%Y-%m-%d')
            if date not in binanceData:
                candles = {}
                with open(PATH / f"{symbol}-{timeframe}-{date}.csv", newline='') as csvfile:
                    reader = csv.reader(csvfile)
                    for row in reader:
                        candles[row[0]] = BinanceCandle(row)
                binanceData[date] = candles
        except Exception as e:
            print(f"Error {round_number}")
            print(e)
    return binanceData


# Run mode strategies

class RealTimeStrategy():
    def __init__(self, logger=None):
        self.logger = logger
        self.preload_rounds = 0

    def log(self, message):
        if self.logger != None:
            self.logger.log(message)
        else:
            print(message)

    def name(self):
        return "None Strategy"

    def strategy_details(self):
        return ""

    def populate_indicators(self, data, rounds):
        pass

    def calculate(self, data):
        return None

    def __str__(self):
        return f"{self.name()}\n{self.strategy_details()}"


class BetOneSideStrategy(RealTimeStrategy):
    def __init__(self, side):
        self.betSide = side

    def calculate(self, round_number):
        return self.betSide

    def __str__(self):
        return f"Side: {self.betSide}"


class BetThreshold(RealTimeStrategy):

    def __init__(self, threshold, reverse=False, binancePrice="open"):
        self.threshold = threshold
        self.reverse = reverse
        self.binancePrice = binancePrice

        if binancePrice == "close":
            self.binanceLambda = lambda candle: candle.closePrice
        elif binancePrice == "high":
            self.binanceLambda = lambda candle: candle.highPrice
        elif binancePrice == "low":
            self.binanceLambda = lambda candle: candle.lowPrice
        elif binancePrice == "average":
            self.binanceLambda = lambda candle: (
                candle.highPrice+candle.lowPrice)/2
        else:
            self.binanceLambda = lambda candle: candle.openPrice

    def __str__(self):
        return f"""
    Threshold: {self.threshold}
    Reverse: {self.reverse}
    BinancePrice : {self.binancePrice}"""

    def populate(self, closedData, lockingData, closingData):
        self.closedData = closedData
        self.lockingData = lockingData
        self.closingData = closingData

        self.binanceData = loadBinanceDataFromRounds(self.closedData)

    def calculate(self, round_number):
        if self.lockingData[round_number].cancelled:
            return None

        betSide = None
        sourcePrice = self.lockingData[round_number].currentSourcePrice / (
            10 ** 8)

        dateRound = self.lockingData[round_number].GetDate().replace(
            second=0, microsecond=0)

        binanceCandle = self.binanceData[dateRound.strftime(
            '%Y-%m-%d')].get(str(int(dateRound.timestamp()) * 1000), None)

        if binanceCandle == None:
            return None

        binancePrice = self.binanceLambda(binanceCandle)

        if abs(sourcePrice - binancePrice) >= self.threshold:
            if binancePrice > sourcePrice:
                betSide = BetEnum.UP
            else:
                betSide = BetEnum.DOWN

        if betSide != None and self.reverse:
            betSide = BetEnum.UP if betSide == BetEnum.DOWN else BetEnum.DOWN

        return betSide


class RealTimeBetThreshold(RealTimeStrategy):

    def __init__(self, threshold, timeframe='1m', reverse=False, logger=None):
        super().__init__(logger=logger)
        self.symbol = 'bnbusdt'
        self.threshold = threshold
        self.reverse = reverse
        self.timeframe = timeframe

    def name(self):
        return "Threshold Strategy"

    def strategy_details(self):
        return f"Threshold: {self.threshold}\nReverse: {self.reverse}"

    def populate_indicators(self, data, rounds):
        data["binance_price"] = get_binance_price(
            symbol=self.symbol, timeframe=self.timeframe)

    def calculate(self, data):
        bet_side = None

        price_gap = data["binance_price"] - \
            data["oracle_price"]

        self.log(
            f"Round({data['epoch']}) - Binance Gap: {price_gap:.2f}")

        if abs(price_gap) >= self.threshold:
            bet_side = price_gap > 0

            if self.reverse:
                # reverse
                bet_side = not bet_side

        return bet_side


class RealTimeRSI(RealTimeStrategy):

    def __init__(self, reverse=False):
        self.reverse = reverse

    def __str__(self):
        return f"""RSI Strategy
        Reverse: {self.reverse}"""

    def calculate(self, round_number):
        betSide = None
        indicators = self.getIndicators(symbol='bnbusdt', timeframe='1m')

        if indicators["sma_rsi_14"] != None:
            betSide = BetEnum.UP if indicators["rsi_14"] > indicators["sma_rsi_14"] else BetEnum.DOWN

            if self.reverse:
                betSide = BetEnum.UP if betSide == BetEnum.DOWN else BetEnum.DOWN

        return betSide


class RealTimeThresholdAndRSI(RealTimeBetThreshold):
    def __init__(self, threshold, reverse=False, logger=None):
        super().__init__(threshold, reverse=False)
        self.rsiStrategy = RealTimeRSI(reverse=False)
        self.reverse = reverse
        self.logger = logger

    def __str__(self):
        return f""" Threshold And RSI Strategy
        Threshold: {self.threshold}
        Reverse: {self.reverse}
        """

    def Log(self, message):
        if self.logger != None:
            self.logger.log(message)
        else:
            print(message)

    def calculate(self, round_number, data):
        betSide = super().calculate(round_number)
        rsiSide = self.rsiStrategy.calculate(round_number)

        self.Log(f"thresholdSide: {betSide}")
        self.Log(f"RSISide: {rsiSide}")

        if betSide != rsiSide:
            betSide = None

        if betSide != None and self.reverse:
            betSide = BetEnum.UP if betSide == BetEnum.DOWN else BetEnum.DOWN

        return betSide


# Save realtime data in excel file
class RealTimeExcel(RealTimeStrategy):
    def __init__(self, bet_before_sec):
        super().__init__()
        self.nameExcel = f'realtimeExcel_{int(bet_before_sec*100)}sec_{int(time.time())}.xlsx'
        self.wb = Workbook()
        self.wb.save(self.nameExcel)
        self.ws = self.wb.active

    def name(self):
        return "Excel Strategy"

    def strategy_details(self):
        return f"Save Binance and Pancake Oracle Prices"

    def populate_indicators(self, data, rounds):
        data = []
        data.append(int(time.time()))
        data.append(data['epoch'])
        data.append(get_oracle_price())
        data.append(get_kcandle(symbol='bnbusdt', timeframe='1m'))
        data.append(get_kcandle(symbol='bnbusdt', timeframe='5m'))
        data.append(get_kcandle(symbol='bnbusdt', timeframe='1h'))
        data.append(get_kcandle(symbol='bnbusdt', timeframe='4h'))
        self.ws.append(data)

        self.wb.save(self.nameExcel)

# print realtime data
class RealtimeTest(RealTimeStrategy):
    def name(self):
        return "Test Strategy"

    def populate_indicators(self, data, rounds):
        self.log(f"Epoch: {data['epoch']} \ OracleData: {get_oracle_data_text()}")


class ClosingHigherRealtime(RealTimeBetThreshold):
    def __init__(self, threshold, bet_after_higher_rounds, safe_closing_threshold=0.2, timeframe='1m', reverse=False, logger=None):
        super().__init__(threshold=threshold,
                         timeframe=timeframe, reverse=reverse, logger=logger)
        self.timeframe = timeframe
        self.bet_after_higher_rounds = bet_after_higher_rounds
        self.preload_rounds = bet_after_higher_rounds+3
        self.safe_closing_threshold = safe_closing_threshold

    def populate_indicators(self, data, rounds):
        super().populate_indicators(data=data, rounds=rounds)
        current_round_number = data['epoch']

        closing_round = rounds[current_round_number-1]

        # binance_oracle_gap = (data["binance_price"] - data["source_price"])
        lock_price = closing_round.lock_price
        source_lock_gap = data["oracle_price"] - lock_price
        closing_side = data["oracle_price"] > lock_price

        closing_higher = closing_side != closing_round.GetLowerSideMultiplier() and abs(
            source_lock_gap) >= self.safe_closing_threshold

        sequencial_closed_highers = 0
        sequencial_highers_rounds = []

        # isso nao precisa necessariamente ser feito na hora
        for x in range(self.bet_after_higher_rounds):
            round = rounds[current_round_number-2-x]
            if round.GetLowerSideMultiplier() != round.GetSideWinner():
                sequencial_closed_highers += 1
                sequencial_highers_rounds.append(str(round.epoch))
            else:
                break
        self.log(f"""\n
        Safe Threshold: {source_lock_gap}
        Sequencial highers: {sequencial_closed_highers} [{','.join(sequencial_highers_rounds)}]
        Closing higher: {closing_higher} [{current_round_number-1}]""")

        data["sequencial_closed_highers"] = sequencial_closed_highers
        data["closing_higher"] = closing_higher

    def calculate(self, data):
        bet_side = super().calculate(data=data)

        if bet_side != None:
            # Check if last x rounds are lowers
            if (data["closing_higher"] and data["sequencial_closed_highers"] >= self.bet_after_higher_rounds-1):
                return bet_side
        return None

    def name(self):
        return "[Closing Higher Strategy Realtime]"

    def bet_correct_side(self, bet_side, round):
        bet_lower = round.GetLowerSideMultiplier() == bet_side
        if self.reverse:
            return not bet_lower
        return bet_lower

    def strategy_details(self):
        return super().strategy_details() + \
            f"\nBet after higher rounds: {self.bet_after_higher_rounds}" + \
            f"\nSafe Closing Threshold: {self.safe_closing_threshold}"


class ClosingLowerRealtime(RealTimeBetThreshold):
    def __init__(self, threshold, bet_after_lower_rounds, safe_closing_threshold=0.2, timeframe='1m', reverse=False, logger=None):
        super().__init__(threshold=threshold,
                         timeframe=timeframe, reverse=reverse, logger=logger)
        self.timeframe = timeframe
        self.bet_after_lower_rounds = bet_after_lower_rounds
        self.preload_rounds = bet_after_lower_rounds+3
        self.safe_closing_threshold = safe_closing_threshold

    def populate_indicators(self, data, rounds):
        super().populate_indicators(data=data, rounds=rounds)
        current_round_number = data['epoch']

        closing_round = rounds[current_round_number-1]

        # binance_oracle_gap = (data["binance_price"] - data["source_price"])
        lock_price = closing_round.lock_price
        source_lock_gap = data["oracle_price"] - lock_price
        closing_side = data["oracle_price"] > lock_price

        closing_lower = closing_side == closing_round.GetLowerSideMultiplier() and abs(
            source_lock_gap) >= self.safe_closing_threshold

        sequencial_closed_lowers = 0
        sequencial_lowers_rounds = []

        # isso nao precisa necessariamente ser feito na hora
        for x in range(self.bet_after_lower_rounds):
            round = rounds[current_round_number-2-x]
            if round.GetLowerSideMultiplier() == round.GetSideWinner():
                sequencial_closed_lowers += 1
                sequencial_lowers_rounds.append(str(round.epoch))
            else:
                break
        self.log(f"""\n
        Safe Threshold: {source_lock_gap}
        Sequencial lowers: {sequencial_closed_lowers} [{','.join(sequencial_lowers_rounds)}]
        Closing lower: {closing_lower} [{current_round_number-1}]""")

        data["sequencial_closed_lowers"] = sequencial_closed_lowers
        data["closing_lower"] = closing_lower

    def calculate(self, data):
        bet_side = super().calculate(data=data)

        if bet_side != None:
            if (data["closing_lower"] and data["sequencial_closed_lowers"] >= self.bet_after_lower_rounds-1):
                return bet_side
        return None

    def name(self):
        return "[Closing Lower Strategy Realtime]"

    def bet_correct_side(self, bet_side, round):
        bet_lower = round.GetLowerSideMultiplier() == bet_side
        if self.reverse:
            return not bet_lower
        return bet_lower

    def strategy_details(self):
        return super().strategy_details() + \
            f"\nBet after lower rounds: {self.bet_after_lower_rounds}" + \
            f"\nSafe Closing Threshold: {self.safe_closing_threshold}"