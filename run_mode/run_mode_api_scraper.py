import datetime
from pathlib import Path
import sys
import time
from traceback import TracebackException
from flask import Flask
from flask_restful import Api, Resource
import requests
from web3 import Web3
import websocket
import json
from _thread import *

from web3_utils.abi import ORACLE_ABI
from lucasutils.configbot import ConfigBot


"""

This code scraps realtime data-prices from binance socket api and oracle price data from blockchain contract

"""


def log_error(exc_type, exc_value, tb):
    error = TracebackException(
        type(exc_value), exc_value, tb, limit=None).format(chain=None)
    for line in error:
        print(line)


def show_exception_and_exit(exc_type, exc_value, tb):
    log_error(exc_type, exc_value, tb)


class BinanceSocket():
    ENDPOINT = "wss://stream.binance.com:9443"

    def __init__(self, pairs):
        socket = BinanceSocket.ENDPOINT + f"/ws/BNBUSDT@kline_1m"

        self.ws = websocket.WebSocketApp(socket, on_message=self.on_message,
                                         on_close=self.on_close, on_error=self.on_error, on_open=self.on_open)
        self.pairs = pairs

        self.data = {}

        for pair in self.pairs:
            symbol, timeframe = pair.split("@kline_")
            if self.data.get(symbol, None) == None:
                self.data[symbol] = {}
            self.data[symbol][timeframe] = {}
            self.data[symbol][timeframe]['lastCandle'] = None
            self.data[symbol][timeframe]['close'] = []
            self.data[symbol][timeframe]['indicators'] = {}
            self.data[symbol][timeframe]['indicators']['rsi_14'] = []
            self.data[symbol][timeframe]['indicators']['sma_rsi_14'] = []

        self.load_last_candles()

    def load_last_candles(self):
        for pair in self.pairs:
            symbol, timeframe = pair.lower().split("@kline_")

            candleTimeframeSec = 60

            if 'm' in timeframe:
                candleTimeframeSec *= int(timeframe.replace('m', ''))
            elif 'h' in timeframe:
                candleTimeframeSec *= int(timeframe.replace('h', '')) * 60
            elif 'd' in timeframe:
                candleTimeframeSec *= int(timeframe.replace('d', '')) * 60 * 24

            end_time = int(datetime.datetime.utcnow().timestamp()) * 1000
            start_time = end_time - (241 * candleTimeframeSec * 1000)

            candles = requests.get(url="https://api.binance.com/api/v3/klines",
                                   params={'symbol': symbol.upper(),
                                           'interval': timeframe,
                                           'startTime': start_time,
                                           'endTime': end_time
                                           }).json()

            candle_items = ['t', 'o', 'h', 'l', 'c',
                            'v', 'T', 'q', 'n', 'V', 'Q', 'B']
            self.data[symbol][timeframe]['last_clande'] = dict(
                zip(candle_items, candles[-1]))
            self.data[symbol][timeframe]['last_close'] = float(
                self.data[symbol][timeframe]['last_clande']['c'])

    def update_indicators(self, data):
        try:
            pass
        except Exception as e:
            if "inputs are all nan" not in e.args[0].lower():
                print(e)

    def on_open(self, ws):
        print("Opened connection")
        pairs = str(self.pairs).replace("'", '"').replace(" ", "")
        subscription = '{"method": "SUBSCRIBE", "params": ' + \
            pairs + ', "id": 1}'
        ws.send(subscription)
        print("Subscription sended")

    def on_message(self, ws, message):
        mJson = json.loads(message)
        candle = mJson['k']

        data = self.data[candle['s'].lower()][candle['i']]

        data["last_candle"] = candle
        data["last_close"] = float(candle['c'])

        self.update_indicators(data)

    def on_close(self, ws, close_status_code, close_msg):
        print("### closed ###")

    def on_error(self, ws, error):
        print(error)

    def start(self):
        print("running")
        self.ws.run_forever()


class ServerFlask():
    serverFlask = None

    def __init__(self, FPS, pairs):
        self.FPS = FPS

        self.oracle_price = 0
        self.oracle_id = 0
        self.oracle_data = [0, 0, 0]
        self.bSocket = BinanceSocket(pairs)
        start_new_thread(self.bSocket.start, ())

        self.config_api = ConfigBot(path=Path("configs/bot_api.json"))

        self.app = self.createApp()
        ServerFlask.serverFlask = self
        self.web3 = Web3(Web3.HTTPProvider(endpoint_uri=self.config_api.data.get("RPC_BSC")))
        self.oracle_contract = self.web3.eth.contract(address=Web3.toChecksumAddress(
            "0xd276fcf34d54a926773c399ebaa772c12ec394ac"), abi=ORACLE_ABI)

    def _get_oracle_price(self):
        try:
            return self.oracle_contract.functions.latestAnswer().call()
        except Exception as e:
            print(e)
            return self.oracle_price

    def _get_oracle_id(self):
        try:
            return self.oracle_contract.functions.latestRound().call()
        except Exception as e:
            print(e)
            return self.oracle_id

    def _get_oracle_data(self):
        try:
            return self.oracle_contract.functions.latestRoundData().call()
        except Exception as e:
            print(e)
            return self.oracle_data

    class GetCandle(Resource):
        def get(self, symbol, timeframe):
            return ServerFlask.serverFlask.bSocket.data[symbol][timeframe]["last_candle"]

    class GetPrice(Resource):
        def get(self, symbol, timeframe):
            return ServerFlask.serverFlask.bSocket.data[symbol][timeframe]['last_close']

    class GetIndicators(Resource):
        def get(self, symbol, timeframe):
            return ServerFlask.serverFlask.bSocket.data[symbol][timeframe]['indicators']

    class GetOraclePrice(Resource):
        def get(self):
            return ServerFlask.serverFlask.oracle_price

    class GetOracleData(Resource):
        def get(self):
            return ServerFlask.serverFlask.oracle_data

    class GetOracleId(Resource):
        def get(self):
            return ServerFlask.serverFlask.oracle_id

    def createApp(self):
        app = Flask(__name__)
        api = Api(app)

        api.add_resource(
            self.GetPrice, "/price/<string:symbol>/<string:timeframe>")
        api.add_resource(
            self.GetCandle, "/candle/<string:symbol>/<string:timeframe>")
        api.add_resource(self.GetIndicators,
                         "/indicators/<string:symbol>/<string:timeframe>")
        api.add_resource(self.GetOraclePrice, "/oraclePrice")
        api.add_resource(self.GetOracleData, "/oracleData")
        api.add_resource(self.GetOracleId, "/oracleId")

        return app

    def loop(self):
        while True:
            try:
                self.oracle_data = self._get_oracle_data()
                self.oracle_id = self.oracle_data[0]
                self.oracle_price = self.oracle_data[1]
            except Exception as e:
                print(e)
            time.sleep(1/self.FPS)

    def run(self):
        try:
            start_new_thread(self.loop, ())
            self.app.run()
        except Exception as e:
            print(e)


if __name__ == "__main__":
    sys.excepthook = show_exception_and_exit

    # pairs = ['bnbusdt@kline_1m', 'bnbusdt@kline_3m', 'bnbusdt@kline_5m', 'bnbusdt@kline_15m', 'bnbusdt@kline_30m', 'bnbusdt@kline_1h']
    pairs = ['bnbusdt@kline_1m', 'bnbusdt@kline_5m',
             'bnbusdt@kline_1h', 'bnbusdt@kline_4h']

    server = ServerFlask(FPS=1.5, pairs=pairs)
    server.run()
