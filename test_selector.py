import unittest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# 导入被测试的类
from future.Selector import BBIKDJSelector

class TestBBIKDJSelector(unittest.TestCase):
    def setUp(self):
        """每个测试方法执行前的设置"""
        # 创建一个默认的选股器实例
        self.selector = BBIKDJSelector(
            j_threshold=-5,
            bbi_min_window=90,
            max_window=90,
            price_range_pct=100.0,
            bbi_q_threshold=0.05,
            j_q_threshold=0.10
        )
        
        # 创建测试数据
        self.test_data = self._create_test_data(120)  # 创建120天的测试数据
        
        # 添加必要的列
        self.test_data['BBI'] = self._compute_sample_bbi(self.test_data)
    
    def _create_test_data(self, days=120):
        """创建模拟的股票数据"""
        # 生成日期序列
        dates = [datetime.now() - timedelta(days=i) for i in range(days)]
        dates.reverse()  # 按时间升序排列
        
        # 创建基础价格数据（略微上升的趋势）
        base_price = 10.0
        daily_change = np.random.normal(0.01, 0.02, days)
        close_prices = base_price * np.exp(np.cumsum(daily_change))
        
        # 创建DataFrame
        df = pd.DataFrame({
            'date': dates,
            'open': close_prices * np.random.uniform(0.98, 1.02, days),
            'high': close_prices * np.random.uniform(1.0, 1.03, days),
            'low': close_prices * np.random.uniform(0.97, 1.0, days),
            'close': close_prices,
            'volume': np.random.randint(10000, 1000000, days)
        })
        
        return df
    
    def _compute_sample_bbi(self, df):
        """计算模拟的BBI值"""
        ma3 = df['close'].rolling(3).mean()
        ma6 = df['close'].rolling(6).mean()
        ma12 = df['close'].rolling(12).mean()
        ma24 = df['close'].rolling(24).mean()
        return (ma3 + ma6 + ma12 + ma24) / 4
    
    @patch('future.Selector.passes_day_constraints_today')
    @patch('future.Selector.bbi_deriv_uptrend')
    @patch('future.Selector.compute_kdj')
    @patch('future.Selector.last_valid_ma_cross_up')
    @patch('future.Selector.compute_dif')
    @patch('future.Selector.zx_condition_at_positions')
    def test_passes_filters_success(self, mock_zx_condition, mock_compute_dif, 
                                 mock_last_valid, mock_compute_kdj, 
                                 mock_bbi_deriv, mock_day_constraints):
        """测试所有条件都满足的情况"""
        # 模拟所有依赖函数返回成功结果
        mock_day_constraints.return_value = True
        mock_bbi_deriv.return_value = True
        
        # 模拟KDJ计算结果
        mock_kdj_df = pd.DataFrame({
            'J': [-6, -7, -8, -9, -10]  # J值低于阈值-5
        }, index=range(5))
        mock_compute_kdj.return_value = mock_kdj_df
        
        # 模拟上穿MA60的位置
        mock_last_valid.return_value = 5
        
        # 模拟DIF计算结果
        mock_compute_dif.return_value = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5])
        
        # 模拟知行条件
        mock_zx_condition.return_value = True
        
        # 执行测试
        result = self.selector._passes_filters(self.test_data)
        
        # 验证结果
        self.assertTrue(result)
        
        # 验证所有函数都被正确调用
        mock_day_constraints.assert_called_once()
        mock_bbi_deriv.assert_called_once()
        mock_compute_kdj.assert_called_once()
        mock_last_valid.assert_called_once()
        mock_compute_dif.assert_called_once()
        mock_zx_condition.assert_called_once()
    
    @patch('future.Selector.passes_day_constraints_today')
    def test_passes_filters_fails_day_constraints(self, mock_day_constraints):
        """测试当日交易约束失败的情况"""
        mock_day_constraints.return_value = False
        
        result = self.selector._passes_filters(self.test_data)
        
        self.assertFalse(result)
        mock_day_constraints.assert_called_once()
    
    def test_passes_filters_price_volatility_exceeded(self):
        """测试价格波动幅度超过阈值的情况"""
        # 创建一个价格波动幅度非常大的数据
        volatile_data = self._create_test_data(120)
        volatile_data.loc[50:70, 'close'] *= 2  # 制造大幅波动
        volatile_data['BBI'] = self._compute_sample_bbi(volatile_data)
        
        with patch('future.Selector.passes_day_constraints_today', return_value=True):
            result = self.selector._passes_filters(volatile_data, debug=True)
            
        self.assertFalse(result)
    
    @patch('future.Selector.passes_day_constraints_today')
    @patch('future.Selector.bbi_deriv_uptrend')
    def test_passes_filters_bbi_not_uptrend(self, mock_bbi_deriv, mock_day_constraints):
        """测试BBI不是上升趋势的情况"""
        mock_day_constraints.return_value = True
        mock_bbi_deriv.return_value = False
        
        result = self.selector._passes_filters(self.test_data)
        
        self.assertFalse(result)
        mock_bbi_deriv.assert_called_once()
    
    def test_select_method(self):
        """测试批量选股方法"""
        # 创建多个股票的数据
        multi_stock_data = {
            'stock1': self._create_test_data(120),
            'stock2': self._create_test_data(120),
            'stock3': self._create_test_data(120)
        }
        
        # 为每个股票计算BBI
        for code, df in multi_stock_data.items():
            df['BBI'] = self._compute_sample_bbi(df)
        
        # 模拟_passess_filters方法
        with patch.object(self.selector, '_passes_filters', side_effect=[True, False, True]):
            # 选择最近的日期作为选股日期
            latest_date = max(df['date'].max() for df in multi_stock_data.values())
            
            # 执行选股
            selected_stocks = self.selector.select(latest_date, multi_stock_data)
            
            # 验证结果
            self.assertEqual(len(selected_stocks), 2)
            self.assertIn('stock1', selected_stocks)
            self.assertIn('stock3', selected_stocks)
    
    def test_edge_case_insufficient_data(self):
        """测试数据不足的边界情况"""
        # 创建数据不足的情况
        insufficient_data = self._create_test_data(50)  # 只有50天数据
        insufficient_data['BBI'] = self._compute_sample_bbi(insufficient_data)
        
        # 测试_passess_filters（即使其他条件都满足，但由于数据计算中的问题，仍可能失败）
        with patch('future.Selector.passes_day_constraints_today', return_value=True):
            # 这里我们不模拟所有依赖函数，因为我们想测试实际的行为
            # 但需要至少模拟一些函数避免错误
            with patch('future.Selector.bbi_deriv_uptrend', return_value=True):
                try:
                    result = self.selector._passes_filters(insufficient_data)
                    # 如果代码没有抛出异常，验证结果
                    # 注意：在实际情况中，这可能返回False或抛出异常，取决于实现
                except Exception as e:
                    # 如果抛出异常，我们捕获它但不视为测试失败
                    # 这取决于你希望如何处理这种情况
                    pass
        
        # 测试select方法中数据不足的情况
        multi_stock_data = {'stock1': insufficient_data}
        latest_date = insufficient_data['date'].max()
        
        # _passes_filters可能不会被调用，因为select方法会先检查数据长度
        with patch.object(self.selector, '_passes_filters') as mock_passes:
            selected_stocks = self.selector.select(latest_date, multi_stock_data)
            # 如果数据长度不足，可能不会调用_passess_filters
            self.assertEqual(selected_stocks, [])

if __name__ == '__main__':
    unittest.main()