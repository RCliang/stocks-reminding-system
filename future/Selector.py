from typing import Dict, List, Optional, Any
from scipy.signal import find_peaks
import numpy as np
import pandas as pd

def compute_kdj(df: pd.DataFrame, fastk_period: int = 9, slowk_period: int = 3, slowd_period: int = 3) -> pd.DataFrame:
    """计算KDJ指标，参数命名与TA-Lib保持一致，便于对比"""
    if df.empty:
        return df.assign(K=np.nan, D=np.nan, J=np.nan)

    # 计算RSV (9日周期)
    low_n = df["low"].rolling(window=fastk_period, min_periods=1).min()
    high_n = df["high"].rolling(window=fastk_period, min_periods=1).max()
    rsv = (df["close"] - low_n) / (high_n - low_n + 1e-9) * 100

    # 计算K线 (简单移动平均)
    K = rsv.rolling(window=slowk_period, min_periods=1).mean()
    # 计算D线 (K线的简单移动平均)
    D = K.rolling(window=slowd_period, min_periods=1).mean()
    # 计算J线
    J = 3 * K - 2 * D
    
    return df.assign(K=K, D=D, J=J)

def compute_bbi(df: pd.DataFrame) -> pd.Series:
    ma3 = df["close"].rolling(3).mean()
    ma6 = df["close"].rolling(6).mean()
    ma12 = df["close"].rolling(12).mean()
    ma24 = df["close"].rolling(24).mean()
    return (ma3 + ma6 + ma12 + ma24) / 4

def compute_rsv(df: pd.DataFrame, n: int) -> pd.Series:
    low_n = df["low"].rolling(window=n, min_periods=1).min()
    high_close_n = df["close"].rolling(window=n, min_periods=1).max()
    rsv = (df["close"] - low_n) / (high_close_n - low_n + 1e-9) * 100.0
    return rsv

def bbi_deriv_uptrend(
    bbi: pd.Series,
    *,  # 强制使用关键字参数
    min_window: int,
    max_window: int | None = None,
    q_threshold: float = 0.0,
) -> bool:
    """判断 BBI 是否整体上升（优化版本）。"""
    # 参数验证和数据预处理（同前）...
    
    # 计算所有可能的归一化窗口并缓存
    bbi_values = bbi.values
    longest = min(len(bbi), max_window or len(bbi))
    
    # 从最长窗口开始向下搜索
    for w in range(longest, min_window - 1, -1):
        # 计算该窗口的归一化序列
        window_start = len(bbi) - w
        first_val = bbi_values[window_start]
        if first_val == 0:  # 防止除零错误
            continue
        
        # 使用向量化计算提高性能
        norm = bbi_values[window_start:] / first_val
        diffs = np.diff(norm)
        
        # 优化：当 q_threshold 为 0 时，可以直接检查是否有负值
        if q_threshold == 0.0:
            if np.all(diffs >= 0):
                return True
        else:
            # 否则计算分位数
            if np.quantile(diffs, q_threshold) >= 0:
                return True
    
    return False
def compute_dif(df: pd.DataFrame, fast: int = 12, slow: int = 26) -> pd.Series:
    """计算 MACD 指标中的 DIF (EMA fast - EMA slow)。"""
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    return ema_fast - ema_slow
def _find_peaks(
    df: pd.DataFrame,
    *,
    column: str = "high",
    distance: Optional[int] = None,
    prominence: Optional[float] = None,
    height: Optional[float] = None,
    width: Optional[float] = None,
    rel_height: float = 0.5,
    **kwargs: Any,
) -> pd.DataFrame:
    
    if column not in df.columns:
        raise KeyError(f"'{column}' not found in DataFrame columns: {list(df.columns)}")

    y = df[column].to_numpy()

    indices, props = find_peaks(
        y,
        distance=distance,
        prominence=prominence,
        height=height,
        width=width,
        rel_height=rel_height,
        **kwargs,
    )

    peaks_df = df.iloc[indices].copy()
    peaks_df["is_peak"] = True

    # Flatten SciPy arrays into columns (only those with same length as indices)
    for key, arr in props.items():
        if isinstance(arr, (list, np.ndarray)) and len(arr) == len(indices):
            peaks_df[f"peak_{key}"] = arr

    return peaks_df

def last_valid_ma_cross_up(
    close: pd.Series,
    ma: pd.Series,
    lookback_n: int | None = None,
) -> Optional[int]:
    """
    使用向量化操作查找收盘价有效上穿移动平均线的最后一个交易日位置。
    
    性能优化版本，特别适合处理大型数据集。
    """
    # 参数验证
    if len(close) != len(ma):
        raise ValueError("close和ma的长度必须相同")
    if lookback_n is not None and lookback_n <= 0:
        raise ValueError("lookback_n必须为正整数")
    
    n = len(close)
    if n < 2:
        return None
    
    # 设置搜索范围
    start_idx = 1
    if lookback_n is not None:
        start_idx = max(start_idx, n - lookback_n)
    
    # 提取相关数据范围
    close_slice = close.iloc[start_idx-1:n].values
    ma_slice = ma.iloc[start_idx-1:n].values
    
    # 创建掩码
    valid_mask = ~np.isnan(close_slice) & ~np.isnan(ma_slice)
    
    # 计算上穿条件
    # 上穿定义：前一天close < ma，当天close >= ma
    prev_below = close_slice[:-1] < ma_slice[:-1]
    curr_above_eq = close_slice[1:] >= ma_slice[1:]
    valid_prev = valid_mask[:-1]
    valid_curr = valid_mask[1:]
    
    # 组合条件
    cross_up_mask = prev_below & curr_above_eq & valid_prev & valid_curr
    
    # 查找最后一个满足条件的索引
    cross_up_indices = np.where(cross_up_mask)[0]
    
    if len(cross_up_indices) > 0:
        # 因为我们从start_idx-1开始切片，所以需要加上偏移量
        return cross_up_indices[-1] + start_idx
    
    return None

def compute_zx_lines(
    df: pd.DataFrame,
    m1: int = 14, m2: int = 28, m3: int = 57, m4: int = 114
) -> tuple[pd.Series, pd.Series]:
    """返回 (ZXDQ, ZXDKX)
    ZXDQ = EMA(EMA(C,10),10)
    ZXDKX = (MA(C,14)+MA(C,28)+MA(C,57)+MA(C,114))/4
    """
    close = df["close"].astype(float)
    zxdq = close.ewm(span=10, adjust=False).mean().ewm(span=10, adjust=False).mean()

    ma1 = close.rolling(window=m1, min_periods=m1).mean()
    ma2 = close.rolling(window=m2, min_periods=m2).mean()
    ma3 = close.rolling(window=m3, min_periods=m3).mean()
    ma4 = close.rolling(window=m4, min_periods=m4).mean()
    zxdkx = (ma1 + ma2 + ma3 + ma4) / 4.0
    return zxdq, zxdkx

def passes_day_constraints_today(df: pd.DataFrame, pct_limit: float = 0.02, amp_limit: float = 0.07) -> bool:
    """
    所有战法的统一当日过滤：
    1) 当前交易日相较于前一日涨跌幅 < pct_limit（绝对值）
    2) 当日振幅（High-Low 相对 Low） < amp_limit
    """
    if len(df) < 2:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    close_today = float(last["close"])
    close_yest = float(prev["close"])
    high_today = float(last["high"])
    low_today  = float(last["low"])
    if close_yest <= 0 or low_today <= 0:
        return False
    pct_chg = abs(close_today / close_yest - 1.0)
    amplitude = (high_today - low_today) / low_today
    return (pct_chg < pct_limit) and (amplitude < amp_limit)

def zx_condition_at_positions(
    df: pd.DataFrame,
    *,
    require_close_gt_long: bool = True,
    require_short_gt_long: bool = True,
    pos: int | None = None,
) -> bool:
    """
    在指定位置 pos（iloc 位置；None 表示当日）检查知行条件：
      - 收盘 > 长期线（可选）
      - 短期线 > 长期线（可选）
    注：长期线需满样本；若为 NaN 直接返回 False。
    """
    # 数据有效性检查
    if df.empty or "close" not in df.columns:
        return False
    
    # 计算知行线
    short_line, long_line = compute_zx_lines(df)
    
    # 确定检查位置
    check_pos = len(df) - 1 if pos is None else pos
    if check_pos < 0 or check_pos >= len(df):
        return False
    
    try:
        # 获取数据
        short_value = short_line.iloc[check_pos]
        long_value = long_line.iloc[check_pos]
        close_price = df["close"].iloc[check_pos]
        
        # 检查数据有效性
        if pd.isna(short_value) or pd.isna(long_value) or pd.isna(close_price):
            return False
        
        short_value = float(short_value)
        long_value = float(long_value)
        close_price = float(close_price)
        
        # 检查是否为有限值
        if not (np.isfinite(short_value) and np.isfinite(long_value) and np.isfinite(close_price)):
            return False
        
        # 应用条件判断
        conditions_met = True
        
        if require_close_gt_long:
            conditions_met = conditions_met and (close_price > long_value)
            
        if require_short_gt_long and conditions_met:
            conditions_met = conditions_met and (short_value > long_value)
            
        return conditions_met
        
    except (IndexError, KeyError, TypeError):
        return False

class BBIKDJSelector:
    """
    自适应 *BBI(导数)* + *KDJ* 选股器
        • BBI: 允许 bbi_q_threshold 比例的回撤
        • KDJ: J < threshold ；或位于历史 J 的 j_q_threshold 分位及以下
        • MACD: DIF > 0
        • 收盘价波动幅度 ≤ price_range_pct
    """

    def __init__(
        self,
        j_threshold: float = -5,
        bbi_min_window: int = 90,
        max_window: int = 90,
        price_range_pct: float = 100.0,
        bbi_q_threshold: float = 0.05,
        j_q_threshold: float = 0.10,
    ) -> None:
        self.j_threshold = j_threshold
        self.bbi_min_window = bbi_min_window
        self.max_window = max_window
        self.price_range_pct = price_range_pct
        self.bbi_q_threshold = bbi_q_threshold  # ← 原 q_threshold
        self.j_q_threshold = j_q_threshold      # ← 新增

    # ---------- 单支股票过滤 ---------- #
    def _passes_filters(self, hist: pd.DataFrame, debug: bool = False) -> bool:
        # 在每个过滤条件处添加调试信息
        if not passes_day_constraints_today(hist):
            if debug:
                print(f"过滤条件1失败：当日交易约束")
            return False

        # 0. 收盘价波动幅度约束（最近 max_window 根 K 线）
        win = hist.tail(self.max_window)
        high, low = win["close"].max(), win["close"].min()
        if low <= 0 or (high / low - 1) > self.price_range_pct:           
            if debug:
                print(f"过滤条件2失败：收盘价波动幅度 > {self.price_range_pct:.2f}%")
            return False

        # 1. BBI 上升（允许部分回撤）
        if not bbi_deriv_uptrend(
            hist["BBI"],
            min_window=self.bbi_min_window,
            max_window=self.max_window,
            q_threshold=self.bbi_q_threshold,
        ):              
            if debug:
                print(f"过滤条件3失败：BBI 下降")
            return False

        # 2. KDJ 过滤 —— 双重条件
        kdj = compute_kdj(hist)
        j_today = float(kdj.iloc[-1]["J"])

        # 最近 max_window 根 K 线的 J 分位
        j_window = kdj["J"].tail(self.max_window).dropna()
        if j_window.empty:
            if debug:
                print(f"过滤条件4失败：最近 {self.max_window} 根 K 线无有效 J 值")
            return False
        j_quantile = float(j_window.quantile(self.j_q_threshold))

        if not (j_today < self.j_threshold or j_today <= j_quantile):
            if debug:
                print(f"过滤条件4失败：J 值 > {self.j_threshold:.2f} 且 > {j_quantile:.2f}")
            return False
        
        # —— 2.5 60日均线条件（使用通用函数）
        hist["MA60"] = hist["close"].rolling(window=60, min_periods=1).mean()

        # 当前必须在 MA60 上方（保持原条件）
        if hist["close"].iloc[-1] < hist["MA60"].iloc[-1]:
            if debug:
                print(f"过滤条件5失败：当前收盘价 < 60日均线")
            return False

        # 寻找最近一次“有效上穿 MA60”的 T（使用 max_window 作为回看长度，避免过旧）
        t_pos = last_valid_ma_cross_up(hist["close"], hist["MA60"], lookback_n=self.max_window)
        if t_pos is None:
            if debug:
                print(f"过滤条件5失败：最近 {self.max_window} 根 K 线无有效上穿 MA60 记录")
            return False        

        # 3. MACD：DIF > 0
        hist["DIF"] = compute_dif(hist)
        if hist["DIF"].iloc[-1] <= 0:
            if debug:
                print(f"过滤条件6失败：当前 DIF ≤ 0")
            return False
       
        # 4. 当日：收盘>长期线 且 短期线>长期线
        if not zx_condition_at_positions(hist, require_close_gt_long=True, require_short_gt_long=True, pos=None):
            if debug:
                print(f"过滤条件7失败：当日收盘 ≤ 长期线 或 短期线 ≤ 长期线")   
            return False

        return True

    # ---------- 多股票批量 ---------- #
    def select(self, date: pd.Timestamp, data: Dict[str, pd.DataFrame]) -> List[str]:
        picks: List[str] = []
        window_size = self.max_window + 20
        
        # 预处理所有必要的技术指标，避免重复计算
        for code, df in data.items():
            # 使用更高效的数据过滤方式
            hist = df[df["date"] <= date]
            if len(hist) < window_size:
                continue
                
            hist = hist.tail(window_size).copy()
            
            # 预计算所有技术指标
            hist["BBI"] = compute_bbi(hist)
            hist["MA60"] = hist["close"].rolling(window=60, min_periods=1).mean()
            hist["DIF"] = compute_dif(hist)
            
            if self._passes_filters(hist, debug=True):
                picks.append(code)
        return picks

class SuperB1Selector:
    """SuperB1 选股器

    过滤逻辑概览
    ----------------
    1. **历史匹配 (t_m)** — 在 *lookback_n* 个交易日窗口内，至少存在一日
       满足 :class:`BBIKDJSelector`。

    2. **盘整区间** — 区间 ``[t_m, date-1]`` 收盘价波动率不超过 ``close_vol_pct``。

    3. **当日下跌** — ``(close_{date-1} - close_date) / close_{date-1}``
       ≥ ``price_drop_pct``。

    4. **J 值极低** — ``J < j_threshold`` *或* 位于历史 ``j_q_threshold`` 分位。
    """

    def __init__(
        self,
        *,
        lookback_n: int = 60,
        close_vol_pct: float = 0.05,
        price_drop_pct: float = 0.03,
        j_threshold: float = -5,
        j_q_threshold: float = 0.10,
        # 嵌套 BBIKDJSelector 配置
        B1_params: Optional[Dict[str, Any]] = None        
    ) -> None:        
        # 参数合法性检查
        self._validate_params(lookback_n, close_vol_pct, price_drop_pct, j_q_threshold, B1_params)

        # 基本参数初始化
        self.lookback_n = lookback_n
        self.close_vol_pct = close_vol_pct
        self.price_drop_pct = price_drop_pct
        self.j_threshold = j_threshold
        self.j_q_threshold = j_q_threshold

        # 内部 BBIKDJSelector 实例化
        self.bbi_selector = BBIKDJSelector(**(B1_params or {}))

        # 为保证给 BBIKDJSelector 提供足够历史，预留额外缓冲
        self._extra_for_bbi = self.bbi_selector.max_window + 20
        # 预计算最小需要的数据长度
        self._min_required_length = self.lookback_n + self._extra_for_bbi

    def _validate_params(self, lookback_n, close_vol_pct, price_drop_pct, j_q_threshold, B1_params):
        """参数合法性验证"""
        if lookback_n < 2:
            raise ValueError("lookback_n 应 ≥ 2")
        if not (0 < close_vol_pct < 1):
            raise ValueError("close_vol_pct 应位于 (0, 1) 区间")
        if not (0 < price_drop_pct < 1):
            raise ValueError("price_drop_pct 应位于 (0, 1) 区间")
        if not (0 <= j_q_threshold <= 1):
            raise ValueError("j_q_threshold 应位于 [0, 1] 区间")
        if B1_params is None:
            raise ValueError("bbi_params没有给出")

    def _passes_filters(self, hist: pd.DataFrame) -> bool:
        """单支股票过滤核心逻辑"""
        # 早期退出条件检查
        if self._check_early_exit_conditions(hist):
            return False

        # 搜索满足条件的历史匹配点(t_m)
        if 'BBI' not in hist.columns:
            hist['BBI'] = compute_bbi(hist)
        tm_idx = self._find_valid_tm_point(hist)
        if tm_idx is None:
            return False

        # 验证匹配日技术条件
        tm_pos = hist.index.get_loc(tm_idx)
        if not zx_condition_at_positions(hist, require_close_gt_long=True, require_short_gt_long=True, pos=tm_pos):
            return False

        # 检查当日跌幅
        if not self._check_price_drop(hist):
            return False

        # 计算并检查KDJ指标
        kdj = compute_kdj(hist)
        if not self._check_j_value_condition(kdj):
            return False

        # 检查当日技术线条件
        return zx_condition_at_positions(hist, require_close_gt_long=False, require_short_gt_long=True, pos=None)

    def _check_early_exit_conditions(self, hist: pd.DataFrame) -> bool:
        """检查早期退出条件，提高性能"""
        # 基本数据量检查
        if len(hist) < 2 or len(hist) < self._min_required_length:
            return True
        
        # 通用交易日约束检查
        if not passes_day_constraints_today(hist):
            return True
            
        return False

    def _find_valid_tm_point(self, hist: pd.DataFrame) -> Optional[int]:
        """搜索满足BBIKDJ条件且后续有稳定盘整区间的历史匹配点"""
        # 只取回溯窗口内的数据，避免不必要的计算
        lb_hist = hist.tail(self.lookback_n + 1)  # +1 以排除自身
        
        # 从最近日期往前搜索，找到第一个满足条件的点即可
        for idx in reversed(lb_hist.index[:-1]):
            if self.bbi_selector._passes_filters(hist.loc[:idx]):
                # 提取盘整区间数据
                stable_seg = hist.loc[idx : hist.index[-2], "close"]
                
                # 验证盘整区间有效性
                if len(stable_seg) >= 3:  # 至少3天
                    high, low = stable_seg.max(), stable_seg.min()
                    if low > 0 and (high / low - 1) <= self.close_vol_pct:
                        return idx
        
        return None

    def _check_price_drop(self, hist: pd.DataFrame) -> bool:
        """检查当日相对前一日的跌幅是否满足要求"""
        close_today, close_prev = hist["close"].iloc[-1], hist["close"].iloc[-2]
        # 避免除以零，并检查跌幅
        return close_prev > 0 and (close_prev - close_today) / close_prev >= self.price_drop_pct

    def _check_j_value_condition(self, kdj: pd.DataFrame) -> bool:
        """检查J值是否处于极低水平"""
        # 获取当日J值
        j_today = float(kdj["J"].iloc[-1])
        
        # 检查绝对阈值条件
        if j_today < self.j_threshold:
            return True
            
        # 计算并检查分位数条件
        j_window = kdj["J"].iloc[-self.lookback_n:].dropna()
        if not j_window.empty:
            j_q_val = float(j_window.quantile(self.j_q_threshold))
            if j_today <= j_q_val:
                return True
                
        return False

    def select(self, date: pd.Timestamp, data: Dict[str, pd.DataFrame]) -> List[str]:
        """批量选股接口"""
        picks: List[str] = []

        # 使用生成器表达式和列表推导式优化批量选股过程
        for code, df in data.items():
            # 提取历史数据，避免创建不必要的数据副本
            hist = df[df["date"] <= date].tail(self._min_required_length)
            
            # 只有数据量足够时才进行后续检查
            if len(hist) >= self._min_required_length and self._passes_filters(hist):
                picks.append(code)

        return picks
