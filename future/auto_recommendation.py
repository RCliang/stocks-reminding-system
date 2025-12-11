from prompts import get_trading_prompt
import talib as ta
import pandas as pd
import json
from futu import OpenQuoteContext, RET_OK
from utils import get_ai_recommendation
from fetch_kline_daily import KlineFetcher
import datetime
import logging

# 配置logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("auto_recommendation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

daily_columns = ['code', 'name', 'update_time', 'last_price', 'open_price', 'high_price', \
    'low_price', 'pe_ratio', 'volume', 'turnover', 'turnover_rate']
hist_columns = ['code', 'name', 'time_key', 'open', \
    'close', 'high', 'low', 'pe_ratio', 'volume', \
        'turnover_rate', 'turnover', 'change_rate']
        
def get_stock_pool(pool_name="全部"):
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    ret, data = quote_ctx.get_user_security(pool_name)
    if ret == RET_OK:
        # print(data)
        if data.shape[0] > 0:  # 如果自选股列表不为空
            res = {code: name for name, code in zip(data['name'].values.tolist(), data['code'].values.tolist())}
        else:
            res = []
    else:
        print('error:', data)
        res = []
    quote_ctx.close()
    return res

def get_market_place():
    stock_pool = get_stock_pool("etf")
    sample_market_state = {}
    fetcher = KlineFetcher(stock_pool.keys(), daily_columns, hist_columns, 'data')
    data = fetcher.hist_kline_persistence('kline_etf_data')
    print(data.columns)
    for code, name in stock_pool.items():
        print(code, name)
        tmp = data[data.code == code]
        tmp = tmp.sort_values(by='time_key')
        tmp['sma_7'] = ta.SMA(tmp['close'].values, timeperiod=7)
        tmp['sma_14'] = ta.SMA(tmp['close'].values, timeperiod=14)
        tmp['rsi_14'] = ta.RSI(tmp['close'].values, timeperiod=14)
        sample_market_state[code] = {
            'price': tmp['close'].values[-1],
            'change_24h': tmp['change_rate'].values[-1],
            'indicators': {
                'sma_7': tmp['sma_7'].values[-1],
                'sma_14': tmp['sma_14'].values[-1],
                'rsi_14': tmp['rsi_14'].values[-1],
            }
        }
    print(sample_market_state)
    return sample_market_state

def main():
    stock_pool = get_stock_pool("etf")
    sample_market_state = {}
    fetcher = KlineFetcher(stock_pool.keys(), daily_columns, hist_columns, 'data')
    data = fetcher.hist_kline_persistence('kline_etf_data')
    print(data.columns)
    for code, name in stock_pool.items():
        print(code, name)
        tmp = data[data.code == code]
        tmp = tmp.sort_values(by='time_key')
        tmp['sma_7'] = ta.SMA(tmp['close'].values, timeperiod=7)
        tmp['sma_14'] = ta.SMA(tmp['close'].values, timeperiod=14)
        tmp['rsi_14'] = ta.RSI(tmp['close'].values, timeperiod=14)
        sample_market_state[code] = {
            'price': tmp['close'].values[-1],
            'change_24h': tmp['change_rate'].values[-1],
            'indicators': {
                'sma_7': tmp['sma_7'].values[-1],
                'sma_14': tmp['sma_14'].values[-1],
                'rsi_14': tmp['rsi_14'].values[-1],
            }
        }
    print(sample_market_state)
    sample_portfolio = {
        "total_value": 0.00,
        "cash": 120000.00,
        "positions": []
    }
    sample_account_info = {
        "initial_capital": 120000.00,
        "total_return": 0.0
    }
    sample_prompt = get_trading_prompt(sample_market_state, sample_account_info, sample_portfolio)
    print(sample_prompt)
    reasoning_content, content = get_ai_recommendation(sample_prompt)
    print(f"reasoning_content:\n{reasoning_content}")
    print(f"content:\n{content}")
    return
if __name__ == "__main__":
    main()
    
