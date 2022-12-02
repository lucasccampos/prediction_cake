from eth_abi import decode_abi
import requests
from utils.betEnum import BetEnum
from utils.roundInfo import RoundInfo
from lucasutils import web3_functions

PCK_ROUND_FUNC = 'rounds(uint256)((uint256,uint256,uint256,uint256,int256,int256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,bool))'
ORACLE_DATA_FUNC = 'getRoundData(uint80)((uint80,int256,uint256,uint256,uint80))'

def get_oracle_data(oracle_id, oracle_contract):
    return oracle_contract.functions.getRoundData(oracle_id).call()


def get_current_round_number(prediction_contract):
    return prediction_contract.functions.currentEpoch().call()


def get_current_round_info(prediction_contract):
    return get_round_info(prediction_contract,  prediction_contract.functions.currentEpoch().call())


def get_round_info(prediction_contract, round_number):
    data = prediction_contract.functions.rounds(round_number).call()
    return RoundInfo(data)

def rounds_unclaimed(prediction_contract, wallet_address):
    pass

def claim_rounds(prediction_contract):
    pass

def build_signed_bet_txn(web3, wallet_address, private_key, prediction_contract, round_number, bet_side, bet_amount, gas_limit, gas_price, nonce):
    if bet_side == BetEnum.UP:
        bet_function = prediction_contract.functions.betBull(
            round_number)
    else:
        bet_function = prediction_contract.functions.betBear(
            round_number)

    txn = web3_functions.build_transaction(
        bet_function, wallet_address, bet_amount, gas_limit, gas_price, nonce, chain_id=56)

    signedTxn = web3_functions.signTransaction(
        web3, txn, private_key)

    return signedTxn

def get_oracle_price():
    return int(requests.get("http://127.0.0.1:5000/oraclePrice").text) / (10 ** 8)

def get_oracle_data_text():
    return requests.get("http://127.0.0.1:5000/oracleData").text

def get_kcandle(symbol, timeframe):
    # response = requests.get(
    #     "https://api.binance.com/api/v3/ticker/price?symbol=BNBUSDT").json()['price']
    return requests.get(f"http://127.0.0.1:5000/candle/{symbol}/{timeframe}").text

def get_binance_price(symbol, timeframe):
    # response = requests.get(
    #     "https://api.binance.com/api/v3/ticker/price?symbol=BNBUSDT").json()['price']
    return float(requests.get(f"http://127.0.0.1:5000/price/{symbol}/{timeframe}").text)

def get_indicators(symbol, timeframe):
    # response = requests.get(
    #     "https://api.binance.com/api/v3/ticker/price?symbol=BNBUSDT").json()['price']
    return requests.get(f"http://127.0.0.1:5000/indicators/{symbol}/{timeframe}").json()