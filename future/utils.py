import backtrader as bt
import talib as ta
import pandas as pd
import json
from futu import *
import time
import numpy as np
import math
import datetime
from openai import OpenAI
import pandas as pd
import backtrader as bt
import backtrader.indicators as btind


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

def get_ai_recommendation(prompt: str) -> str:
    client = OpenAI(api_key="sk-8c887e6454f741cc9553da2be62487af", base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个专业的股票助手。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1024,
        temperature=0.7,
        stream=False
    )
    return response.choices[0].message.content