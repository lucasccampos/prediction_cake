from lucasutils.web3_functions import get_balance
from lucasutils.web3Utilits import *


class Wallet():
    def __init__(self, start_balance=4, base_bet_amount=5/260, txn_fee=0.00053, house_fee=3, wallet_address=None, web3=None, logger=None):
        self.data = {}
        self.data["start_balance_amount"] = start_balance
        self.data["bets"] = {}
        self.data["sequencials_losts"] = {}
        self.data["sequencials_wins"] = {}
        self.data["total_bets"] = 0
        self.data["wins"] = 0
        self.data["losts"] = 0
        self.data["bet_amount"] = base_bet_amount
        self.data["base_bet_amount"] = base_bet_amount
        self.data["last_bet_amount"] = base_bet_amount
        self.data["max_sequencial_wins"] = 0
        self.data["max_sequencial_losts"] = 0
        self.data["current_sequencial_losts"] = 0
        self.data["current_sequencial_wins"] = 0
        self.data["lower_balance"] = start_balance
        self.data["higher_balance"] = start_balance
        self.data["balance"] = start_balance
        self.data["house_fee"] = house_fee
        self.data["txn_fee"] = txn_fee

        self.wallet_address = wallet_address
        self.web3 = web3

        self.setup_web3(web3, wallet_address)

        self.logger = logger
        self.log("Wallet criada")

    def __repr__(self) -> str:
        return self.print_wallet()

    def setup_web3(self, web3, address):
        if address == None or web3 == None:
            return
        self.web3 = web3
        self.wallet_address = address
        self.set_balance(WeiToEther(get_balance(
            web3=self.web3, address=self.wallet_address)))
        self.data["start_balance_amount"] = self.data["balance"]

    def log(self, message):
        if self.logger != None:
            self.logger.log(message)
        else:
            print(message)

    def wallet_add(self, value):
        self.data["balance"] += value

        self.data["lower_balance"] = min(
            self.data["lower_balance"], self.data["balance"])
        self.data["higher_balance"] = max(
            self.data["higher_balance"], self.data["balance"])

    def calculate_profit(self, bet_multiplier, bet_amount):
        total_profit = (bet_multiplier *
                        (1 - (self.data["house_fee"] / 100)) * bet_amount)
        only_profit = total_profit - self.data["txn_fee"] - bet_amount
        return total_profit, only_profit

    def place_bet(self, bet):
        self.wallet_add(-bet.amount-self.data["txn_fee"])
        self.data["bets"][bet.epoch] = bet
        self.data["last_bet_amount"] = bet.amount
        self.data["total_bets"] += 1

    def set_sequencial_lost(self, current_sequencial_lost):
        if current_sequencial_lost == 0:
            return
        if self.data["sequencials_losts"].get(current_sequencial_lost, None) == None:
            self.data["sequencials_losts"][current_sequencial_lost] = 0
        self.data["sequencials_losts"][current_sequencial_lost] += 1

    def set_sequencial_win(self, current_sequencial_win):
        if current_sequencial_win == 0:
            return
        if self.data["sequencials_wins"].get(current_sequencial_win, None) == None:
            self.data["sequencials_wins"][current_sequencial_win] = 0
        self.data["sequencials_wins"][current_sequencial_win] += 1

    def load_closed_round(self, closed_round):
        if closed_round.epoch not in self.data["bets"]:
            return

        bet = self.data["bets"][closed_round.epoch]

        if bet.closed == True:
            return

        if bet.bet_side == closed_round.GetSideWinner() and closed_round.cancelled == False:
            # Won
            total_profit, only_profit = self.calculate_profit(
                bet_multiplier=closed_round.GetWinnerSideMultiplier(), bet_amount=bet.amount)
            self.wallet_add(total_profit)
            self.data["wins"] += 1
            self.data["current_sequencial_wins"] += 1
            self.data["max_sequencial_wins"] = max(
                self.data["current_sequencial_wins"], self.data["max_sequencial_wins"])

            self.set_sequencial_lost(self.data["current_sequencial_losts"])
            self.data["current_sequencial_losts"] = 0

            self.log(
                f"Win({bet.epoch}) - Amount {bet.amount:.4f} - Profit {only_profit:.4f} ({closed_round.GetWinnerSideMultiplier():.2f}x)")
        else:
            self.data["losts"] += 1
            self.data["current_sequencial_losts"] += 1
            self.data["max_sequencial_losts"] = max(
                self.data["current_sequencial_losts"], self.data["max_sequencial_losts"])
            self.set_sequencial_win(self.data["current_sequencial_wins"])
            self.data["current_sequencial_wins"] = 0

            self.log(f"Lost({bet.epoch}) - Amount {bet.amount:.4f}")
        self.log(str(self))

        bet.closed = True

    def wallet_name(self):
        return "Normal wallet"

    def get_data(self):
        soma_sequencials_losts = sum(self.data["sequencials_losts"].values())
        soma_custom_losts = sum(
            map(lambda kv: (kv[0]**2)*kv[1], self.data["sequencials_losts"].items()))

        soma_sequencials_wins = sum(self.data["sequencials_wins"].values())
        soma_custom_wins = sum(
            map(lambda kv: (kv[0]**2)*kv[1], self.data["sequencials_wins"].items()))

        media_custom_losts = 0
        media_ponderada_losts = 0
        media_custom_wins = 0
        media_ponderada_wins = 0
        win_rate = 0
        wrong_rate = 0

        if self.data["total_bets"] > 0:
            win_rate = self.get_win_rate()
            wrong_rate = self.data.get(
                "wrong_side", -1) / self.data["total_bets"]

            if self.data["losts"] > 0:
                if soma_sequencials_losts > 0:
                    media_ponderada_losts = self.data["losts"] / \
                        soma_sequencials_losts
                media_custom_losts = soma_custom_losts/self.data["losts"]
            
            if self.data["wins"] > 0:
                if soma_sequencials_wins > 0:
                    media_ponderada_wins = self.data["wins"] / \
                        soma_sequencials_wins
                media_custom_wins = soma_custom_wins/self.data["wins"]

        self.data["win_rate"] = win_rate
        self.data["wrong_rate"] = wrong_rate
        self.data["media_ponderada_losts"] = media_ponderada_losts
        self.data["media_custom_losts"] = media_custom_losts
        self.data["media_ponderada_wins"] = media_ponderada_wins
        self.data["media_custom_wins"] = media_custom_wins
        return self.data

    def print_wallet(self):
        msg = f"\n[{self.wallet_name()}]\n"
        priority_keys = ["total_bets", "wins", "losts", "max_sequencial_losts",
                         "lower_balance", "bet_amount", "higher_balance", "start_balance_amount", "balance", "current_sequencial_losts", "wrong_side"]

        for key in priority_keys:
            value = self.data.get(key, None)
            if value != None:
                msg += f"{key}: {value}"
                msg += "\n"

        msg += f'win_rate: {self.get_win_rate():.2f}%\n'
        return msg

    def get_win_rate(self):
        try:
            return self.data["wins"]/self.data["total_bets"]
        except:
            return 0

    def get_amount_to_bet(self):
        return self.data["bet_amount"]

    def set_balance(self, value):
        self.data["balance"] = value

    def get_balance(self):
        return self.data["balance"]

    def has_balance_to_bet(self):
        return (self.get_amount_to_bet() + self.data["txn_fee"]) <= self.get_balance()


class DoubleWallet(Wallet):
    def __init__(self, lost_multiplier=2, start_balance=1000, base_bet_amount=5, txn_fee=0.15, house_fee=3, logger=None):
        super().__init__(start_balance=start_balance, base_bet_amount=base_bet_amount,
                         txn_fee=txn_fee, house_fee=house_fee, logger=logger)
        self.data["lost_multiplier"] = lost_multiplier

    def wallet_name(self):
        return "Double Wallet"

    def get_amount_to_bet(self):
        if self.data["current_sequencial_losts"] > 0:
            amount = self.data["last_bet_amount"]
            # * (2**(self.data["current_sequencial_losts"]-1))
            amount *= self.data["lost_multiplier"]
            amount += self.data["txn_fee"]
        else:
            amount = self.data["bet_amount"]
        return amount
