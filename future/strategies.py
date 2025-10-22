import backtrader as bt
import talib as ta
import pandas as pd
import json
from futu import *
import time
import numpy as np
import math
import datetime
import pandas as pd
import backtrader as bt
import backtrader.indicators as btind
import matplotlib
matplotlib.use('nbagg')  # 适用于 Jupyter 的交互式后端
import matplotlib.pyplot as plt  # 导入 matplotlib 确保显示
plt.rcParams['figure.figsize'] = (16, 12)
plt.rcParams['figure.dpi'] = 300

# 回测效果最佳
class BreakoutVolumeKDJStrategy(bt.Strategy):
    params = (
        ('j_threshold', 0.0),
        ('up_threshold', 3.0),
        ('volume_threshold', 2.0/3),
        ('offset', 15),
        ('max_window', 60),
        ('price_range_pct', 80.0),
        ('j_q_threshold', 0.20),
        ('printlog', False),    # 是否打印日志
    )

    def __init__(self):
        # 1. 初始化技术指标
        self.kdj = bt.indicators.StochasticSlow(
            period=9, period_dfast=3, period_dslow=3
        )
        self.k = self.kdj.percK
        # KDJ中的%D对应Stochastic的percD
        self.d = self.kdj.percD
        # 计算%J线（公式：J = 3*K - 2*D）
        self.j = 3 * self.k - 2 * self.d
        self.dif = bt.indicators.MACD().macd - bt.indicators.MACD().signal
        self.short_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=5)
        self.long_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=20)
        # 2. 存储中间计算结果
        self.j_values = []
        self.price_high = bt.indicators.Highest(self.data.high, period=self.p.max_window)
        self.price_low = bt.indicators.Lowest(self.data.low, period=self.p.max_window)
        self.crossover = bt.indicators.CrossOver(
            self.data.close, 
            self.short_ma
        )
        self.pct_change = bt.indicators.PercentChange(self.data.close, period=1)

    def next(self):
        # 1. 基础数据收集
        current_date = self.data.datetime.date(0)
        close = self.data.close[0]
        volume = self.data.volume[0]
        j_value = self.j[0]  # 使用慢速K线近似J值
        dif_value = self.dif[0]
        # 2. 收盘价波动幅度约束
        price_range = (self.price_high[0] / self.price_low[0] - 1) * 100
        if price_range > self.p.price_range_pct:
            return

        # 3. J值分位计算
        self.j_values.append(j_value)
        if len(self.j_values) < self.p.max_window:
            # print("窗口数据不足")
            return

        j_series = pd.Series(self.j_values[-self.p.max_window:])
        j_quantile = j_series.quantile(self.p.j_q_threshold)

        # 4. J值条件和DIF条件
        j_condition = (j_value < self.p.j_threshold) or (j_value <= j_quantile)
        if not j_condition or dif_value <= 0:
            return

        # 实现offset周期内只要满足以下四个条件就生成买入信号：
        # 1) 单日涨幅 ≥ up_threshold（默认3%）
        # 2) 相对放量：突破日成交量 ≥ 其他日的1/volume_threshold倍
        # 3) 创新高：突破日收盘价 > 之前所有收盘价
        # 4) J值维持高位：突破后J值未大幅回落（> 当前J值-10）
        buy_signal = False
        breakout_date = None
        # print("计算循环条件")
        for i in range(-self.p.offset-1, 0):
            condition1 = self.pct_change[i]*100 >= self.p.up_threshold
            if not condition1:
                continue
            # print("条件一满足")
            # 2) 相对放量
            vol_T = self.data.volume[i]
            if vol_T <= 0:
                continue
            
            vols_except_T = [self.data.volume[x] for x in range(-self.p.max_window, 0) if x != i]
            for item in vols_except_T:
                if item > self.p.volume_threshold * vol_T:
                    continue
            # print("条件二满足")
            # 3) 创新高
            tmp = [self.data.close[x] for x in range(-self.p.max_window, 0)]
            if self.data.close[i] > max(tmp):
                continue
            # print("条件三满足")
            # 4) J值维持高位
            for idx in range(i, 0):
                if self.j[idx] <= j_value-10:
                    continue
            # print("条件四满足")
            buy_signal = True
            breakout_date = current_date
            break
        

        # 6. 生成买入信号
        if buy_signal == True and (self.broker.get_cash() >= 200 * self.data.close[0]):
            self.buy(size=200)
            self.log(f'买入: 价格={close:.2f}, 成交量={volume}')
                
        if (self.crossover<0) and (self.position):
            current_size = self.position.size
            self.log(f'价格跌破5日线, 卖出信号, 价格: {self.data.close[0]:.2f}')
            self.order = self.sell(size=current_size)

    def log(self, txt, dt=None):
        dt = dt or self.data.datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

class BBIShortLongSelector(bt.Strategy):
    params = (
        ('n_short', 5),
        ('n_long', 20),
        ('m', 3),
        ('offset', 15),
        ('bbi_min_window', 90),
        ('max_window', 150),
        ('bbi_q_threshold', 0.05),
        ('long_rsv', 21),
        ('short_rsv', 3),
        ('printlog', False),    # 是否打印日志
    )

    def __init__(self):
        # 1. 初始化技术指标
        self.short_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=3)
        self.mid_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=6)
        self.long_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=12)
        self.longer_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=24)
        self.bbi = (self.short_ma+self.mid_ma+self.long_ma+self.longer_ma)/4
        # 计算长短期RSV值
        self.long_rsv = bt.indicators.Stochastic(
            self.data,
            period=self.params.long_rsv,
            period_dfast=3,
            period_dslow=3
        )
        self.short_rsv = bt.indicators.Stochastic(
            self.data,
            period=self.params.short_rsv,
            period_dfast=3,
            period_dslow=3
        )   
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=12,
            period_me2=26,
            period_signal=9
        )
        self.dif = self.macd.macd - self.macd.signal
        self.short_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=5)
        self.long_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=20)
        # 2. 存储中间计算结果
        self.j_values = []
        self.price_high = bt.indicators.Highest(self.data.high, period=self.p.max_window)
        self.price_low = bt.indicators.Lowest(self.data.low, period=self.p.max_window)
        self.crossover = bt.indicators.CrossOver(
            self.data.close, 
            self.short_ma
        )
        self.pct_change = bt.indicators.PercentChange(self.data.close, period=1)
    def bbi_deriv_uptrend(self, 
        bbi,
        *,
        min_window: int,
        max_window: int | None = None,
        q_threshold: float = 0.0,
    ) -> bool:
        if not 0.0 <= q_threshold <= 1.0:
            raise ValueError("q_threshold 必须位于 [0, 1] 区间内")
        bbi_data = []
        for i in range(-self.params.max_window, 1):  # 索引范围：-n, -(n-1), ..., 0
            if isinstance(bbi, float):
                continue
            else:
                bbi_val = bbi[i]
            if not math.isnan(bbi_val):
                bbi_data.append(bbi_val)
        # print(f"bbi_data: {len(bbi_data)}")
        bbi = pd.Series(bbi_data).dropna()

        if len(bbi) < min_window:
            return False

        longest = min(len(bbi), max_window or len(bbi))

        # 自最长窗口向下搜索，找到任一满足条件的区间即通过
        for w in range(longest, min_window - 1, -1):
            seg = bbi.iloc[-w:]           # 区间 [T-w+1, T]
            norm = seg / seg.iloc[0]           # 归一化
            diffs = np.diff(norm.values)       # 一阶差分
            if np.quantile(diffs, q_threshold) >= 0:
                return True
        return False
    def next(self):
        # 1. 基础数据收集
        position = self.getposition(self.data)
        current_size = position.size
        # 均线多头排列: 短期 > 中期 > 长期 > 更长期
        ma_condition = self.bbi_deriv_uptrend(
            self.bbi, 
            min_window=self.params.bbi_min_window, 
            max_window=self.params.max_window, 
            q_threshold=self.params.bbi_q_threshold)
        long_ok = True
        short_has_below_20 = False
        for i in range(-self.params.m, 1):
            if self.long_rsv[i] < 80:
                long_ok = False
                break
        for i in range(-self.params.m, 1):
            if self.short_rsv[i] < 20:
                short_has_below_20 = True
                break
        short_start_end_ok = (
            self.short_rsv[-self.params.m] >= 80 and self.short_rsv[0] >= 80
        )
        dif_condition = self.dif[0] > 0
        buy_signal = (ma_condition and long_ok and short_start_end_ok and short_has_below_20 and dif_condition)
        # 6. 生成买入信号
        if buy_signal == True and (self.broker.get_cash() >= 200 * self.data.close[0]):
            self.buy(size=200)
            self.log(f'买入: 价格={close:.2f}, 成交量={volume}')
                
        if (self.crossover<0) and (self.position):
            current_size = self.position.size
            self.log(f'价格跌破5日线, 卖出信号, 价格: {self.data.close[0]:.2f}')
            self.order = self.sell(size=current_size)

    def log(self, txt, dt=None):
        dt = dt or self.data.datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

class BBIKDJStrategy(bt.Strategy):
    params = (
        ('j_threshold', -5),          # J值绝对阈值
        ('bbi_min_window', 90),       # BBI最小窗口
        ('max_window', 90),           # 最大窗口周期
        ('price_range_pct', 100.0),   # 价格波动阈值(百分比)
        ('bbi_q_threshold', 0.05),    # BBI分位阈值
        ('j_q_threshold', 0.10),      # J值分位阈值
        ('printlog', False),          # 是否打印日志
    )

    def __init__(self):
        # 1. 初始化技术指标
        # BBI指标 (3,6,12,24日均线)
        self.short_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=3)
        self.mid_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=6)
        self.long_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=12)
        self.longer_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=24)
        self.bbi = (self.short_ma + self.mid_ma + self.long_ma + self.longer_ma) / 4

        # KDJ指标
        self.stoch = bt.indicators.Stochastic(
            period=9, period_dfast=3, period_dslow=3, movav=bt.ind.MovAv.SMA
        )
        self.k = self.stoch.percK
        self.d = self.stoch.percD
        self.j = 3 * self.k - 2 * self.d  # J值计算

        # MACD指标
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=12,
            period_me2=26,
            period_signal=9
        )
        self.dif = self.macd.macd - self.macd.signal

        # 价格波动指标
        self.price_high = bt.indicators.Highest(self.data.high, period=self.p.max_window)
        self.price_low = bt.indicators.Lowest(self.data.low, period=self.p.max_window)

        # 交易状态管理
        self.order = None
        self.buyprice = 0
        self.buycomm = 0

    def log(self, txt, dt=None, doprint=False):
        """日志记录"""
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')

    def notify_order(self, order):
        """订单状态处理"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'买入, 价格: {order.executed.price:.2f}, 成本: {order.executed.value:.2f}, 手续费: {order.executed.comm:.2f}')
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:
                self.log(f'卖出, 价格: {order.executed.price:.2f}, 收入: {order.executed.value:.2f}, 手续费: {order.executed.comm:.2f}')
            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/拒绝')
        self.order = None

    def notify_trade(self, trade):
        """交易状态处理"""
        if not trade.isclosed:
            return
        self.log(f'交易利润, 总利润: {trade.pnl:.2f}, 净利润: {trade.pnlcomm:.2f}')

    def bbi_deriv_uptrend(self, bbi_series, min_window=30):
        """BBI趋势判断"""
        if len(bbi_series) < min_window:
            return False
        # 计算归一化后的BBI斜率分位数
        norm = bbi_series / bbi_series.iloc[0]
        diffs = np.diff(norm.values)
        return np.quantile(diffs, self.p.bbi_q_threshold) >= 0

    def next(self):
        """策略主逻辑"""
        if self.order:
            return

        # 1. 基础数据收集
        close = self.data.close[0]
        volume = self.data.volume[0]

        # 2. 收盘价波动幅度约束
        win_high = self.price_high[0]
        win_low = self.price_low[0]
        if win_low <= 0:
            return
        price_range = (win_high / win_low - 1) * 100
        if price_range > self.p.price_range_pct:
            return

        # 3. BBI趋势判断
        bbi_values = [self.bbi[i] for i in range(-self.p.max_window, 0) if not math.isnan(self.bbi[i])]
        if not self.bbi_deriv_uptrend(pd.Series(bbi_values), min_window=self.p.bbi_min_window):
            return

        # 4. KDJ J值条件
        j_values = [self.j[i] for i in range(-self.p.max_window, 0) if not math.isnan(self.j[i])]
        if len(j_values) < self.p.max_window:
            return
        j_quantile = np.percentile(j_values, self.p.j_q_threshold * 100)
        j_condition = self.j[0] < self.p.j_threshold or self.j[0] <= j_quantile
        if not j_condition:
            return

        # 5. MACD DIF > 0条件
        if self.dif[0] <= 0:
            return

        # 6. 生成买入信号
        if not self.position:
            cash_needed = 200 * close
            if self.broker.get_cash() >= cash_needed:
                self.log(f'买入信号触发, 价格: {close:.2f}')
                self.order = self.buy(size=200)

class SuperB1Strategy(bt.Strategy):
    params = (
        ('lookback_n', 60),          # 回溯周期
        ('close_vol_pct', 0.05),     # 价格波动阈值(5%)
        ('price_drop_pct', 0.03),    # 单日跌幅阈值(3%)
        ('j_threshold', -5),         # J值绝对阈值
        ('j_q_threshold', 0.10),     # J值分位阈值(10%)
        ('bbikdj_window', 20),       # BBIKDJ匹配窗口
        ('printlog', False),         # 日志开关
    )

    def __init__(self):
        # 1. 指标初始化
        # BBI指标 (3,6,12,24日均线)
        self.short_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=3)
        self.mid_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=6)
        self.long_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=12)
        self.longer_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=24)
        self.bbi = (self.short_ma + self.mid_ma + self.long_ma + self.longer_ma) / 4

        # KDJ指标
        self.stoch = bt.indicators.Stochastic(
            period=9, period_dfast=3, period_dslow=3, movav=bt.ind.MovAv.SMA
        )
        self.k = self.stoch.percK
        self.d = self.stoch.percD
        self.j = 3 * self.k - 2 * self.d  # J值计算

        # 价格波动指标
        self.price_high = bt.indicators.Highest(self.data.high, period=self.p.lookback_n)
        self.price_low = bt.indicators.Lowest(self.data.low, period=self.p.lookback_n)

        # 交易状态管理
        self.order = None
        self.buyprice = 0
        self.buycomm = 0

    def log(self, txt, dt=None, doprint=False):
        """日志记录"""
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')

    def notify_order(self, order):
        """订单状态处理"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'买入, 价格: {order.executed.price:.2f}, 成本: {order.executed.value:.2f}, 手续费: {order.executed.comm:.2f}')
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:
                self.log(f'卖出, 价格: {order.executed.price:.2f}, 收入: {order.executed.value:.2f}, 手续费: {order.executed.comm:.2f}')
            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/拒绝')
        self.order = None

    def notify_trade(self, trade):
        """交易状态处理"""
        if not trade.isclosed:
            return
        self.log(f'交易利润, 总利润: {trade.pnl:.2f}, 净利润: {trade.pnlcomm:.2f}')

    def bbi_deriv_uptrend(self, bbi_series, min_window=30):
        """BBI趋势判断"""
        if len(bbi_series) < min_window:
            return False
        # 计算归一化后的BBI斜率分位数
        norm = bbi_series / bbi_series.iloc[0]
        diffs = np.diff(norm.values)
        return np.quantile(diffs, self.p.j_q_threshold) >= 0

    def next(self):
        """策略主逻辑"""
        if self.order:
            return

        # 1. 收集基础数据
        close = self.data.close[0]
        pct_change = self.data.close[0] / self.data.close[-1] - 1
        high = self.data.high[0]
        low = self.data.low[0]

        # 2. 计算价格波动约束 (区间振幅 <= 5%)
        price_range = (self.price_high[0] / self.price_low[0] - 1) 
        if price_range > self.p.close_vol_pct:
            return

        # 3. 单日跌幅条件 (跌幅 >= 3%)
        if pct_change > -self.p.price_drop_pct:
            return

        # 4. J值条件 (J < -5 或 低于10%分位)
        j_values = [self.j[i] for i in range(-self.p.lookback_n, 0) if not math.isnan(self.j[i])]
        if len(j_values) < self.p.lookback_n:
            return
        j_quantile = np.percentile(j_values, self.p.j_q_threshold * 100)
        j_condition = self.j[0] < self.p.j_threshold or self.j[0] <= j_quantile
        if not j_condition:
            return

        # 5. BBI趋势判断
        bbi_values = [self.bbi[i] for i in range(-self.p.lookback_n, 0) if not math.isnan(self.bbi[i])]
        if not self.bbi_deriv_uptrend(pd.Series(bbi_values)):
            return

        # 6. 生成买入信号
        if not self.position:
            self.log(f'买入信号触发, 价格: {close:.2f}')
            self.order = self.buy(size=200)
        else:
            # 7. 卖出条件 (可根据需要添加)
            if self.data.close[0] < self.bbi[0]:
                self.log(f'BBI下穿, 卖出信号, 价格: {close:.2f}')
                self.order = self.sell(size=self.position.size)

    def stop(self):
        self.log(f'最终资产价值: {self.broker.getvalue():.2f}', doprint=True)
