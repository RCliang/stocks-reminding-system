import backtrader as bt
import talib as ta
import pandas as pd
import json
from futu import *
import time
import numpy as np
import tushare as ts
import requests
import datetime
from openai import OpenAI
import pandas as pd
import backtrader as bt
import backtrader.indicators as btind
from dotenv import load_dotenv
load_dotenv('.env')
token = os.getenv('OPENAI_API_KEY')
api_url = os.getenv('API_URL')
api_key = os.getenv('API_KEY')
ts_key = os.getenv('TS_KEY')

def run_backtest(strategy, stock_code, start_date, end_date, initial_cash=100000):
    # 创建回测引擎
    cerebro = bt.Cerebro()
    
    # 添加策略
    cerebro.addstrategy(strategy, printlog=True)
    
    # 获取数据
    df = pd.read_parquet('data/kline_data.parquet')
    df = df[df['code'] == stock_code]
    df['time_key'] = pd.to_datetime(df['time_key'])
    df.set_index('time_key', inplace=True)
    df = df[start_date:end_date]
    df = df[['open', 'high', 'low', 'close', 'volume']]


    
    # 转换为backtrader数据格式
    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)
    
    # 设置初始资金
    cerebro.broker.setcash(initial_cash)
    
    # 设置手续费
    cerebro.broker.setcommission(commission=0.001)  # 0.1%手续费
    
    # 添加分析指标
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_analyzer')
    
    print(f'初始资金: {initial_cash:.2f}')
    
    # 运行回测
    results = cerebro.run()
    strat = results[0]
    
    # 输出分析结果
    print(f'最终资金: {cerebro.broker.getvalue():.2f}')
    print(f'总收益率: {strat.analyzers.returns.get_analysis()["rtot"]:.2%}')
    print(f'夏普比率: {strat.analyzers.sharpe.get_analysis()["sharperatio"]:.2f}')
    print(f'最大回撤: {strat.analyzers.drawdown.get_analysis()["max"]["drawdown"]:.2%}')
    
    # 交易统计
    trade_analysis = strat.analyzers.trade_analyzer.get_analysis()
    if 'total' in trade_analysis:
        print(f'总交易次数: {trade_analysis["total"]["total"]}')
        print(f'盈利交易次数: {trade_analysis["won"]["total"]}')
        print(f'亏损交易次数: {trade_analysis["lost"]["total"]}')
        if trade_analysis["won"]["total"] > 0:
            print(f'平均盈利: {trade_analysis["won"]["pnl"]["average"]:.2f}')
        if trade_analysis["lost"]["total"] > 0:
            print(f'平均亏损: {trade_analysis["lost"]["pnl"]["average"]:.2f}')
    
    # 绘制回测结果
    fig = cerebro.plot()[0][0]
    fig.set_size_inches(12, 8)
    fig.savefig('test.png')

    return results

def get_market_snapshot(codes: str):
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)

    ret, data = quote_ctx.get_market_snapshot(codes)
    if ret == RET_OK:
        last_price = data['last_price'][0]
        name = data['name'][0]
    else:
        print('error:', data)
    quote_ctx.close()
    return last_price, name
    
def get_ai_recommendation(prompt: str, system_prompt: str="你是一个专业的证券操盘手，专注于股票的交易策略的执行，擅长根据股票的历史数据和当前市场情况，进行交易。") -> str:
    client = OpenAI(api_key=token, base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=8196,
        temperature=0.1,
        stream=False
    )
    reasoning_content = response.choices[0].message.reasoning_content
    content = response.choices[0].message.content
    return reasoning_content, content

def search_stock_info(stock_name: str) -> str:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    data = {
        "company_name": stock_name
    }
    try:
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()['key_information']
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None


class StockAna:
    def __init__(self, config: dict={}):
        self.config = config

    def fetch_stock_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        stock_code = stock_code.split('.')[1]+'.'+stock_code.split('.')[0]
        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')
        df = ts.pro_bar(ts_code=stock_code, start_date=start_date, end_date=end_date)
        df['time_key'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        # df['ts_code'] = [x.split('.')[1]+'.'+x.split('.')[0] for x in df['ts_code']]
        df = df.rename(columns={'ts_code': 'code','vol':'volume', 'pct_chg':'change_rate'})
        kept_cols = ['time_key', 'code', 'open', 'high', 'low', 'close', 'volume', 'change_rate']
        df = df[kept_cols]
        return df
    
    def get_market_place(self, stock_code: str, start_date: str, end_date: str) -> str:
        df = self.fetch_stock_data(stock_code, start_date, end_date)
        df = df.sort_values(by='time_key')
        df['ema_5'] = ta.EMA(df['close'].values, timeperiod=5)
        df['ema_10'] = ta.EMA(df['close'].values, timeperiod=10)
        df['ema_20'] = ta.EMA(df['close'].values, timeperiod=20)
        df['rsi_14'] = ta.RSI(df['close'].values, timeperiod=14)
        macd, macdsignal, macdhist = ta.MACD(
            df['close'].values,
            fastperiod=12,
            slowperiod=26,
            signalperiod=9
        )
        macd = [str(round(x, 2)) for x in macd]
        macdsignal = [str(round(x, 2)) for x in macdsignal]
        macdhist = [str(round(x, 2)) for x in macdhist]
        slowk, slowd = ta.STOCH(df['high'].values, df['low'].values, df['close'].values, fastk_period=9, slowk_period=3, slowd_period=3)
        slowj = 3 * slowk - 2 * slowd
        slowk = [str(round(x, 2)) for x in slowk]
        slowd = [str(round(x, 2)) for x in slowd]
        slowj = [str(round(x, 2)) for x in slowj]
        indicator = {
            'ema_5': df['ema_5'].iloc[-10:].tolist(),
            'ema_10': df['ema_10'].iloc[-10:].tolist(),
            'ema_20': df['ema_20'].iloc[-10:].tolist(),
            'macd': macd[-10:],
            'macdsignal': macdsignal[-10:],
            'macdhist': macdhist[-10:],
            'slowk': slowk[-10:],
            'slowd': slowd[-10:],
            'slowj': slowj[-10:],
            'rsi_14': df['rsi_14'].iloc[-10:].tolist(),
            'volume': df['volume'].iloc[-10:].tolist(),
        }
        last_price, stock_name = get_market_snapshot(stock_code)
        basic_data = search_stock_info(stock_name)
        return stock_name, indicator, last_price, basic_data
