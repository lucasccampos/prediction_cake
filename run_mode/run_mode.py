import datetime
from pathlib import Path
import time
import traceback
from eth_account import Account
from lucasutils.logger import Logger
from lucasutils import web3_functions, web3Utilits
from lucasutils.lucasbots_utils import str_yesor_bool
from lucasutils.abi import PANCAKE_PREDICTION_V2_ABI
from lucasutils.web3_functions import getNonce, sendTransaction
from numpy import tile
import orjson
from web3 import Web3
from bet import Bet
from utils.betEnum import BetEnum
from strategies.realtime_strategies import ClosingHigherRealtime, ClosingLowerRealtime
from utils.prediction_utils import PCK_ROUND_FUNC, get_oracle_price, build_signed_bet_txn, get_current_round_info, get_current_round_number, get_round_info
from utils.roundInfo import RoundInfo
from wallet import DoubleWallet, Wallet
from multicall import Call, Multicall
from lucasutils.configbot import MultiAccountConfig, ConfigBot, ObjectsListConfig

PANCAKE_PREDICTION_ADDRESS = "0x18B2A687610328590Bc8F2e5fEdDe3b582A49cdA"

STRATEGIES_REALTIME = {
    "CLOSING_HIGH": ClosingHigherRealtime,
    "CLOSING_LOW": ClosingLowerRealtime,
}
WALLETS = {
    "DOUBLE_WALLET": DoubleWallet,
    "SIMPLE_WALLET": Wallet
}


class RunMode():
    def __init__(self, config, bet_strategy, wallet, account, test_mode=True, logger=None):
        self.config = config
        self.account = account
        self.test_mode = test_mode
        self.bet_strategy = bet_strategy
        self.wallet = wallet

        self.logger = logger
        if self.logger == None:
            self.logger = Logger()

        self.run_loop = False

        # ROUNDS DATA
        self.rounds = {}

        # BETS
        self.bets = {}
        self.open_bets = []

        self.account.WALLET_ADDRESS = Web3.toChecksumAddress(
            self.account.WALLET_ADDRESS)
        self.config.load({
            "PREDICTION_ABI": PANCAKE_PREDICTION_V2_ABI,
            "PREDICTION_ADDRESS": PANCAKE_PREDICTION_ADDRESS
        })

        if self.account == None and self.test_mode == False:
            raise Exception('You need to pass an account to bet')

    def log(self, message):
        if self.logger != None:
            self.logger.log(message)
        else:
            print(message)

    def load_rounds(self, range_rounds):
        calls = []
        for round_number in range_rounds:
            calls.append(Call(self.config.PREDICTION_ADDRESS, [
                         PCK_ROUND_FUNC, round_number], [[round_number, RoundInfo]]))

        try:
            multi_response = Multicall(calls, _w3=self.web3)()
        except:
            multi_response = Multicall(calls, _w3=self.web3)()

        self.rounds.update(multi_response)

    def run(self):

        # , request_kwargs={'timeout':15})
        self.web3 = Web3(Web3.HTTPProvider(self.config.RPC_URL))
        # , request_kwargs={'timeout':15})
        self.web3_txn = Web3(Web3.HTTPProvider(self.config.RPC_URL_TXN))

        if not self.test_mode:
            self.wallet.setup_web3(self.web3, self.account.WALLET_ADDRESS)

        prediction_contract = self.web3.eth.contract(
            address=self.config.PREDICTION_ADDRESS, abi=self.config.PREDICTION_ABI)

        sign_bet_dict = {
            "web3": self.web3_txn,
            "wallet_address": self.account.WALLET_ADDRESS,
            "private_key":  self.account.PRIVATE_KEY,
            "prediction_contract": prediction_contract,
            "gas_limit": self.config.GAS_LIMIT,
            "gas_price": web3Utilits.GWeiToWei(self.config.GAS_PRICE)
        }

        # PRELOAD ROUNDS STRATEGY

        current_epoch = get_current_round_number(
            prediction_contract=prediction_contract)

        self.load_rounds(range(current_epoch-1-self.bet_strategy.preload_rounds,
                         current_epoch-1))

        self.log("Iniciando run loop")
        self.log(f"BET_BEFORE_SEC: {self.config.BET_BEFORE_SEC}")
        self.log(f"TEST MODE: {self.test_mode}")
        if self.test_mode == False:
            self.log(f"WALLET : {self.account.WALLET_ADDRESS}")
        self.log(f"{self.bet_strategy}\n{self.wallet}")

        self.run_loop = True

        while self.run_loop:
            try:
                time.sleep(self.config.DELAY_RELOAD)

                current_round_info = get_current_round_info(
                    prediction_contract=prediction_contract)
                current_epoch = current_round_info.epoch
                self.rounds[current_epoch] = current_round_info

                self.load_rounds(range(current_epoch-2, current_epoch))

                # open bets poderia ficar dentro da carteira
                for open_bet in self.open_bets:
                    if open_bet.epoch <= current_epoch-2:
                        self.log(
                            f"open bet {self.rounds[open_bet.epoch].cancelled}")
                        self.wallet.load_closed_round(
                            self.rounds[open_bet.epoch])
                        self.open_bets.remove(open_bet)

                self.bet_amount = self.wallet.get_amount_to_bet()

                # Pre signed transactions
                if self.test_mode == False:
                    nonce = getNonce(
                        self.web3, self.account.WALLET_ADDRESS)

                    signed_txn_bull = build_signed_bet_txn(
                        **sign_bet_dict, bet_amount=web3Utilits.EtherToWei(self.bet_amount), round_number=current_epoch, bet_side=BetEnum.UP, nonce=nonce)
                    signed_txn_bear = build_signed_bet_txn(
                        **sign_bet_dict, bet_amount=web3Utilits.EtherToWei(self.bet_amount), round_number=current_epoch, bet_side=BetEnum.DOWN, nonce=nonce)
                    signed_txn_bull_emerg = build_signed_bet_txn(
                        **sign_bet_dict, bet_amount=web3Utilits.EtherToWei(self.bet_amount), round_number=current_epoch, bet_side=BetEnum.UP, nonce=nonce+1)
                    signed_txn_bear_emerg = build_signed_bet_txn(
                        **sign_bet_dict, bet_amount=web3Utilits.EtherToWei(self.bet_amount), round_number=current_epoch, bet_side=BetEnum.DOWN, nonce=nonce+1)

                data = {}
                data["epoch"] = current_epoch

                reaming_time_to_lock = (datetime.datetime.utcfromtimestamp(
                    current_round_info.lock_timestamp) - datetime.datetime.utcnow()).total_seconds()

                if reaming_time_to_lock <= self.config.BET_BEFORE_SEC:
                    self.log(
                        f"Apostando muito encima do Round({current_epoch})")
                    self.log(f"Round({current_epoch}) ignorado")
                    time.sleep(self.config.BET_BEFORE_SEC*2)
                    continue

                self.log(f"Esperando Round({current_epoch}) iniciar")
                time.sleep(reaming_time_to_lock -
                           self.config.BET_BEFORE_SEC)

                source_price = get_oracle_price()
                data["oracle_price"] = source_price

                safe_bet = False
                if len(self.open_bets) > 0:
                    for active_bet in self.open_bets:
                        round_betted = self.rounds[active_bet.epoch]

                        round_lock_price = round_betted.lock_price
                        gap = source_price-round_lock_price

                        if abs(gap) >= self.config.SAFE_GAP:
                            # Se o gap fechar para o lado errado é um motivo para apostar
                            if (gap > 0) != active_bet.bet_side:
                                safe_bet = True
                else:
                    safe_bet = True

                if safe_bet == False:
                    self.log("Apostar nesse round nao e seguro")
                    self.log(f"Round({current_epoch}) ignorado")
                    continue

                self.bet_strategy.populate_indicators(
                    data=data, rounds=self.rounds)
                bet_side = self.bet_strategy.calculate(
                    data=data)

                if bet_side == None:
                    self.log(f"Round({current_epoch}) ignorado")
                    continue

                if not self.test_mode:
                    txn_hash = None

                    try:
                        txn_hash = sendTransaction(
                            self.web3_txn, (signed_txn_bull if bet_side == BetEnum.UP else signed_txn_bear))
                    except Exception as e:
                        try:
                            txn_hash = sendTransaction(
                                self.web3_txn, (signed_txn_bull_emerg if bet_side == BetEnum.UP else signed_txn_bear_emerg))
                            # Printando depois para nao atrapalhar na velocidade
                            self.log("Error ao tentar enviar txn")
                            self.log(f"Tentando novamente")
                            self.log(f"{traceback.format_exc()}")
                        except Exception as e2:
                            self.log("Outro error ao tentar novamente")
                            self.log(f"{traceback.format_exc()}")
                else:
                    txn_hash = "test_mode"

                if txn_hash == None:
                    self.log(
                        "Houve algum problema ao tentar enviar sua transacao")
                    self.log(f"Round({current_epoch}) ignorado")
                    continue

                self.log(
                    f"Transacao enviada - BET:{bet_side} no Round({current_epoch}) - Amount: {self.bet_amount}\nhash: {txn_hash}")

                # Verifica o estado da transacao
                if self.test_mode == False:
                    txn_status = web3_functions.loop_check_transaction_status(
                        web3=self.web3, hash=txn_hash, limit_sec=30, delay=1)
                else:
                    txn_status = True

                if txn_status == False:
                    self.log("Transacao nao foi confirmada...")
                    self.log(f"Round({current_epoch}) ignorado")
                    continue

                self.log("Transacao confirmada com sucesso")

                current_bet = Bet(epoch=current_epoch,
                                  bet_side=bet_side, amount=self.bet_amount, date=None)

                self.open_bets.append(current_bet)
                self.wallet.place_bet(current_bet)

            except Exception as e:
                self.log("Error no loop")
                self.log(f"{traceback.format_exc()}")


def menu(list_options, name_lambda=lambda s: s.NAME, title="Select One:", logger=None):
    def log(message):
        if logger != None:
            logger.log(message)
        else:
            print(message)

    def log_input(message):
        if logger != None:
            return logger.log_input(message)
        else:
            return input(message)
    while True:
        log(f"\n{title}")
        for i, v in enumerate(list_options):
            log(f"{i} - {name_lambda(v)}")
        # cls()
        comando = int(log_input(">:"))
        if comando <= len(list_options)-1:
            return list_options[comando]


if __name__ == "__main__":
    logger = Logger(f"run_mode_{int(time.time())}", MINIMAL=False)

    config_folder = Path("configs")
    run_mode_config = ConfigBot(path=config_folder / "run_mode.json")
    strategies_config = ObjectsListConfig(
        class_object=ConfigBot, list_name="STRATEGIES", path=config_folder / "default_strategies.json")
    wallets_config = ObjectsListConfig(
        class_object=ConfigBot, list_name="WALLETS", path=config_folder / "default_wallets.json")
    accounts_config = MultiAccountConfig(path=config_folder / "accounts.json", base_config={
                                         "NAME": "WALLET_NAME", "SECRET_KEY": None, "WALLET_ADDRESS": None})

    logger.log(f"Run mode configs\n{run_mode_config}\n")
    account = menu(accounts_config.ACCOUNTS, title="Select trading account:")

    strategy_selected = menu(strategies_config.STRATEGIES,
                             title="Select strategy:")
    strategy = STRATEGIES_REALTIME.get(strategy_selected.CLASS_NAME.upper(), None)(
        **strategy_selected.SETTINGS, logger=logger)

    wallet_selected = menu(wallets_config.WALLETS,
                           title="Select wallet:")

    logger.log(str(strategy)+"\n\n")

    test_mode = str_yesor_bool(
        logger.log_input("Wanna play in test_mode >: "))

    base_bet_amount = float(logger.log_input(
        "How much $$$ is going to be your base bet >: ").strip()) / get_oracle_price()

    wallet = WALLETS.get(wallet_selected.CLASS_NAME.upper(), None)(
        logger=logger, base_bet_amount=base_bet_amount, **wallet_selected.SETTINGS)

    run = RunMode(config=run_mode_config, bet_strategy=strategy,
                  wallet=wallet, account=account, test_mode=test_mode, logger=logger)
    run.run()
