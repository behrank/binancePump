import pandas as pd
import numpy as np
import requests
import json

import datetime as dt
from datetime import datetime, timedelta, timezone

from tqdm import tqdm as tqdm

import operator
from termcolor import colored

from binance.client import Client
from binance.enums import *
from binance.websockets import BinanceSocketManager

from pricechange import *
from binanceHelper import *
from pricegroup import *

#Definitions

show_only_pair = "USDT" #Select nothing for all, only selected currency will be shown
show_limit = 1      #minimum top query limit
min_perc = 0.05     #min percentage change
price_changes = []
price_groups = {}
last_symbol = "X"
api_url = "http://127.0.0.1:5000/Signal"

#API Connector
def post_signal_to_api(signal_data):
    
    signal_data["requestToken"] = "XnE9BREaitRBYIFIqJ1MTuqbJdZzQRYwhlStPviHxrQN0Wmgl4H98HQVlTgXMIO7Xo3s5p3UaQd62eXN5xoeYcobZicEEVX6FLDoKAaudkksdSYvamoyf8fsQFt9DlnDzbiZjnE8rRMaxtSHoM22r2HwDEAmz9HJOnrzpQDdeso9LMtxiEHM7ynlVOYYetr5uGi59ZpvWtJ0TuHJ15HhFsidB3XhZj4IjIKd36g3WTCOb47M5b4lCBfXVAAL7ys4hs87PyAAFGVp2FxtAHAG8PlZTYJscaWE6Z7ok1SP6NBUzocXaAGM3cwNf3RNAiJY"
    
    try:
        response = requests.post(api_url, json=signal_data)
        
        # Yanıtı kontrol et
        if response.status_code == 200:
            return "Signal sent."
        else:
            return f"Error on send HTTP code: {response.status_code}, Error message: {response.text}"
    except Exception as e:
        return f"Error not send: {str(e)}"


#Main func
def main():

    def process_message(tickers):
        # print("stream: {} data: {}".format(msg['stream'], msg['data']))
        # print("Len {}".format(len(msg)))
        # print("Currentb Price Of {} is {}".format(msg[0]['s'], msg[0]['c']))
        
        for ticker in tickers:
            symbol = ticker['s']

            if not show_only_pair in symbol:
                continue

            price = float(ticker['c'])
            total_trades = int(ticker['n'])
            open = float(ticker['o'])
            volume = float(ticker['v'])
            event_time = dt.datetime.fromtimestamp(int(ticker['E'])/1000)
            if len(price_changes) > 0:
                price_change = filter(lambda item: item.symbol == symbol, price_changes)
                price_change = list(price_change)
                if (len(price_change) > 0):
                    price_change = price_change[0]
                    price_change.event_time = event_time
                    price_change.prev_price = price_change.price
                    price_change.prev_volume = price_change.volume
                    price_change.price = price
                    price_change.total_trades = total_trades
                    price_change.open = open
                    price_change.volume = volume
                    price_change.isPrinted = False
                else:
                    price_changes.append(PriceChange(symbol, price, price, total_trades, open, volume, False, event_time, volume))
            else:
                price_changes.append(PriceChange(symbol, price, price, total_trades, open, volume, False, event_time, volume))

        price_changes.sort(key=operator.attrgetter('price_change_perc'), reverse=True)
        #print(len(price_changes))
        
        for price_change in price_changes:
            console_color = 'green'
            if price_change.price_change_perc < 0:
                console_color = 'red'

            if (not price_change.isPrinted 
                and abs(price_change.price_change_perc) > min_perc 
                and price_change.volume_change_perc > min_perc):

                price_change.isPrinted = True 
                
                if not price_change.symbol in price_groups:
                    price_groups[price_change.symbol] = PriceGroup(price_change.symbol,                                                                
                                                                1,                                                                
                                                                abs(price_change.price_change_perc),
                                                                price_change.price_change_perc,
                                                                price_change.volume_change_perc,                                                                
                                                                price_change.price,                                                                                                                             
                                                                price_change.event_time,
                                                                price_change.open,
                                                                price_change.volume,
                                                                False,
                                                                )
                else:
                    price_groups[price_change.symbol].tick_count += 1
                    price_groups[price_change.symbol].last_event_time = price_change.event_time
                    price_groups[price_change.symbol].volume = price_change.volume
                    price_groups[price_change.symbol].last_price = price_change.price
                    price_groups[price_change.symbol].isPrinted = False
                    price_groups[price_change.symbol].total_price_change += abs(price_change.price_change_perc)
                    price_groups[price_change.symbol].relative_price_change += price_change.price_change_perc
                    price_groups[price_change.symbol].total_volume_change += price_change.volume_change_perc                

        if len(price_groups)>0:
            anyPrinted = False 
            sorted_price_group = sorted(price_groups, key=lambda k:price_groups[k]['tick_count'])
            if (len(sorted_price_group)>0):
                sorted_price_group = list(reversed(sorted_price_group))
                for s in range(show_limit):
                    header_printed=False
                    if (s<len(sorted_price_group)):
                        max_price_group = sorted_price_group[s]
                        max_price_group = price_groups[max_price_group]
                        if not max_price_group.isPrinted:
                            if not header_printed:
                                msg = "Top Ticks"
                                print(msg)

                                header_printed = True
                            
                            print(max_price_group.to_string(True))
                            
                            signal_data = {
                                "SignalType": 0,
                                "SymbolCode": max_price_group.symbol,
                                "IsUp": console_color != 'red',
                                "EventTime": str(max_price_group.last_event_time.astimezone().isoformat()),
                                "RecentPriceChange": str(max_price_group.relative_price_change),
                                "TopPriceChange": str(max_price_group.total_price_change),
                                "VolumeChange": str(max_price_group.total_volume_change),
                                "LastPrice": str(max_price_group.last_price),
                                "LastVolume": str(max_price_group.volume)
                            }
                            result_message = post_signal_to_api(signal_data)
                            print(result_message)
                            anyPrinted = True

            sorted_price_group = sorted(price_groups, key=lambda k:price_groups[k]['total_price_change'])
            if (len(sorted_price_group)>0):
                sorted_price_group = list(reversed(sorted_price_group))
                for s in range(show_limit):
                    header_printed=False
                    if (s<len(sorted_price_group)):
                        max_price_group = sorted_price_group[s]
                        max_price_group = price_groups[max_price_group]
                        if not max_price_group.isPrinted:
                            if not header_printed:
                                msg = "Top Total Price Change"
                                print(msg)
                                header_printed = True
                            print(max_price_group.to_string(True))

                            signal_data = {
                                "SignalType": 1,
                                "SymbolCode": max_price_group.symbol,
                                "IsUp": console_color != 'red',
                                "EventTime": str(max_price_group.last_event_time.astimezone().isoformat()),
                                "RecentPriceChange": str(max_price_group.relative_price_change),
                                "TopPriceChange": str(max_price_group.total_price_change),
                                "VolumeChange": str(max_price_group.total_volume_change),
                                "LastPrice": str(max_price_group.last_price),
                                "LastVolume": str(max_price_group.volume)
                            }
                            result_message = post_signal_to_api(signal_data)
                            print(result_message)

                            anyPrinted = True

            sorted_price_group = sorted(price_groups, key=lambda k:abs(price_groups[k]['relative_price_change']))
            if (len(sorted_price_group)>0):
                sorted_price_group = list(reversed(sorted_price_group))
                for s in range(show_limit):
                    header_printed=False
                    if (s<len(sorted_price_group)):
                        max_price_group = sorted_price_group[s]
                        max_price_group = price_groups[max_price_group]
                        if not max_price_group.isPrinted:
                            if not header_printed:
                                msg = "Top Relative Price Change"
                                print(msg)
                                header_printed = True
                            print(max_price_group.to_string(True))
                            signal_data = {
                                "SignalType": 3,
                                "SymbolCode": max_price_group.symbol,
                                "IsUp": console_color != 'red',
                                "EventTime": str(max_price_group.last_event_time.astimezone().isoformat()),
                                "RecentPriceChange": str(max_price_group.relative_price_change),
                                "TopPriceChange": str(max_price_group.total_price_change),
                                "VolumeChange": str(max_price_group.total_volume_change),
                                "LastPrice": str(max_price_group.last_price),
                                "LastVolume": str(max_price_group.volume)
                            }
                            result_message = post_signal_to_api(signal_data)
                            print(result_message)
                            anyPrinted = True

            sorted_price_group = sorted(price_groups, key=lambda k:price_groups[k]['total_volume_change'])
            if (len(sorted_price_group)>0):
                sorted_price_group = list(reversed(sorted_price_group))
                for s in range(show_limit):
                    header_printed=False
                    if (s<len(sorted_price_group)):
                        max_price_group = sorted_price_group[s]
                        max_price_group = price_groups[max_price_group]
                        if not max_price_group.isPrinted:
                            if not header_printed:
                                msg = "Top Total Volume Change"
                                print(msg)
                                header_printed = True
                            print(max_price_group.to_string(True))
                            signal_data = {
                                "SignalType": 2,
                                "SymbolCode": max_price_group.symbol,
                                "IsUp": console_color != 'red',
                                "EventTime": str(max_price_group.last_event_time.astimezone().isoformat()),
                                "RecentPriceChange": str(max_price_group.relative_price_change),
                                "TopPriceChange": str(max_price_group.total_price_change),
                                "VolumeChange": str(max_price_group.total_volume_change),
                                "LastPrice": str(max_price_group.last_price),
                                "LastVolume": str(max_price_group.volume)
                            }
                            result_message = post_signal_to_api(signal_data)
                            print(result_message)
                            anyPrinted = True

            if anyPrinted:
                print("")

    client = Client("ClekRwvhp7KJ3Qumjhn1aTboWLFyssY1AOgPmHKP0gCJMorjXsqxB32aTNZ0dP3O", "KdiFqvTqW1s5r2nsW7ZnAWItr54yOm1BIa8yQmQyJzu475C537FlDghm0kFavyC4")
          
    bm = BinanceSocketManager(client)
    conn_key = bm.start_ticker_socket(process_message)
    bm.start()
    print('bm socket started')

    input("Press Enter to continue...")

    bm.stop_socket(conn_key)
    bm.close()
    
    print('Socket Closed')
    return    

if __name__ == '__main__':
    main()
