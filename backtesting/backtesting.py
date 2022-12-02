import time
import threading
import traceback
import orjson
from utils.bet import Bet
from utils.wallet import DoubleWallet
from utils.roundInfo import RoundInfo

import pandas as pd
import numpy as np

from utils.minimal_logger import MinimalLogger

def backtest_strategy(strategy, config, data, rounds_info, wallet, use_safe_gap=False, sort=True):
    if sort:
        data.sort_values(by=["epoch"], inplace=True)
    
    strategy.calculate(data)
    bet_data = data.loc[data["bet"] == True]
    open_bets = []
    
    if use_safe_gap:
        bet_safe_gap = config.get("SAFE_GAP")
        safe_gap_index = list(data.columns).index("safe_closing_gap")
    
    epoch_index = list(data.columns).index("epoch")
    bet_side_index = list(data.columns).index("bet_side")
    #  
    # backtesting_data = {}
    # backtesting_data["wrong_side"] = 0

    for row in bet_data.values:
        round_number = row[epoch_index]
        
        for open_bet in open_bets:
            if open_bet.epoch <= round_number-2:
                wallet.load_closed_round(rounds_info[open_bet.epoch])
                open_bets.remove(open_bet)

        safe_bet = False
        if use_safe_gap and len(open_bets) > 0:
            last_bet = open_bets[-1]
            round_betted = rounds_info[last_bet.epoch]

            gap = row[safe_gap_index]

            if abs(gap) >= bet_safe_gap:
                # Se o gap fechar para o lado errado é um motivo para apostar
                if (gap > 0) != last_bet.bet_side:
                    safe_bet = True
        else:
            safe_bet = True

        if safe_bet:
            bet_amount = wallet.get_amount_to_bet()
            bet = Bet(epoch=round_number, bet_side=row[bet_side_index],
                      amount=bet_amount)

            wallet.place_bet(bet)
            open_bets.append(bet)
    
    for open_bet in open_bets:
        wallet.load_closed_round(rounds_info[open_bet.epoch])

    betted_data = bet_data.loc[bet_data['epoch'].isin(list(wallet.data['bets'].keys()))]
    strategy.wrong_side(betted_data)

    wallet.data["wrong_side"] = len(betted_data.loc[betted_data['bet_side'] == betted_data['wrong_side']])


def multithreads_backtesting(generator, wallet_generator, strategy_class, from_round, to_round, merged_data, using_safe_gap=True, threads_count=8, get_time=True):
    print(f"Starting MultiBacktesting {from_round} - {to_round}")
    
    backtesting_results = []
    threads_list = []
    lock = threading.Lock()
    
    rounds_info = dict(zip(merged_data["epoch"], list(map(RoundInfo, merged_data.values))))
    # logger = MinimalLogger()
    data = merged_data.loc[(merged_data["epoch"] >= from_round) & (merged_data["epoch"] <= to_round)]
    data.sort_values(by=["epoch"], inplace=True)
    
    strategy_class.populate(data)
    
    def thread_task(thread_number, results_list):
        try:
            print(f"thread({thread_number}) started")
            my_data = data.copy()
            while True:
                with lock:
                    try:
                        strategy, config = next(generator)
                    except:
                        break
                wallet = wallet_generator()
                backtest_strategy(strategy=strategy, config=config, data=my_data, rounds_info=rounds_info, wallet=wallet, use_safe_gap=using_safe_gap, sort=False)
                results_list.append((strategy, config, wallet))
        except:
            traceback.print_exc()
            
    
    if get_time:
        start = time.time()
    
    for thread_number in range(threads_count):
        time.sleep(0.01)
        new_thread = threading.Thread(
            target=thread_task, args=(thread_number, backtesting_results))
        threads_list.append(new_thread)
        new_thread.start()
            
    while True:
        if any(list(map(lambda t: t.is_alive(), threads_list))) == True:
            time.sleep(0.017)
        else:
            break
            
    if get_time:
        end = time.time()
        print(f"backtesting finish; duration: {(end-start):.4f}sec")
    else:
        print("backtesting finish")
    return backtesting_results
