import talib
import numpy as np
import pandas as pd
from typing import List, Dict, Any
from itertools import product
from Selector import BBIKDJSelector, SuperB1Selector
import os

def select_stocks(df: pd.DataFrame, custom_selector: SuperB1Selector) -> List[str]:
    # 选股逻辑，假设BBIKDJSelector类已经实现了选股方法
    # 这里简化处理，实际使用时应该调用selector的选股方法
    df = df.rename(columns={'time_key': 'date'})
    latest_date = df['date'].max()
    stockes = df['code'].unique()
    multi_stock_data = dict()
    for stock_code in stockes:
        multi_stock_data[stock_code] = df[df['code'] == stock_code]
    return custom_selector.select(latest_date, multi_stock_data)

def run_hyperparameter_experiment(df: pd.DataFrame, params_dict: Dict[str, List[Any]]) -> pd.DataFrame:
    """
    运行超参组合实验，返回实验结果DataFrame
    """
    # 准备实验结果数据结构
    results = []
    
    # 获取参数名和对应的值列表
    param_names = list(params_dict.keys())
    param_values_list = [params_dict[name] for name in param_names]
    
    # 生成所有参数组合
    print(f"开始参数组合实验，共 {np.prod([len(vals) for vals in param_values_list])} 种组合...")
    
    for i, param_values in enumerate(product(*param_values_list)):
        # 创建参数字典
        params = dict(zip(param_names, param_values))
        
        # 注意参数名映射：BBIKDJSelector使用max_window而不是bbi_max_window
        selector_params = {
            'lookback_n': params.get('lookback_n'),
            'close_vol_pct': params.get('close_vol_pct'),
            'price_drop_pct': params.get('price_drop_pct'),  # 映射参数名
            'j_threshold': params.get('j_threshold'),
            'j_q_threshold': params.get('j_q_threshold'),
            'B1_params': {'j_threshold': -5, 'bbi_min_window': 30, 'max_window': 120, 'price_range_pct': 50,'bbi_q_threshold': 0.5, 'j_q_threshold': 0.3},
        }
        
        print(f"\n实验 {i+1}: 参数组合 {selector_params}")
        
        try:
            # 创建选股器实例
            selector = SuperB1Selector(**selector_params)
            
            # 执行选股
            selected_stocks = select_stocks(df, selector)
            
            print(f"  选出股票数量: {len(selected_stocks)}")
            print(f"  选出股票: {selected_stocks}")
            
            # 记录结果
            for stock in selected_stocks:
                result_row = {
                    'experiment_id': i + 1,
                    'stock_code': stock,
                    **selector_params  # 展开所有参数
                }
                results.append(result_row)
                
            # 如果没有选出股票，也记录一条空结果
            if not selected_stocks:
                result_row = {
                    'experiment_id': i + 1,
                    'stock_code': None,
                    **selector_params
                }
                results.append(result_row)
                
        except Exception as e:
            print(f"  实验失败: {str(e)}")
            
            # 记录失败结果
            result_row = {
                'experiment_id': i + 1,
                'stock_code': None,
                'error': str(e),
                **selector_params
            }
            results.append(result_row)
    
    # 转换为DataFrame
    results_df = pd.DataFrame(results)
    
    # 添加选出股票数量统计
    stock_counts = results_df.groupby('experiment_id')['stock_code'].count().reset_index()
    stock_counts.columns = ['experiment_id', 'selected_count']
    results_df = results_df.merge(stock_counts, on='experiment_id', how='left')
    
    print(f"\n实验完成！共 {len(results_df['experiment_id'].unique())} 组实验，结果已保存到DataFrame")
    
    return results_df

def main():
    # 定义超参范围
    params_dict = {
        'lookback_n': [30, 120, 30],
        'close_vol_pct': [0.05, 0.3, 0.05],  # 注意：这里使用close_vol_pct，但会映射到selector的close_vol_pct
        'price_drop_pct': [0.02, 0.05, 0.01],
        'j_threshold': [-5, 10, 5],
        'j_q_threshold': [0.10, 0.30, 0.10],
    }
    
    # 加载数据
    print("加载股票数据...")
    try:
        df = pd.read_parquet('future/data/kline_data.parquet')
    except Exception:
        # 尝试相对路径
        df = pd.read_parquet('data/kline_data.parquet')
    
    print(f"数据加载完成，共 {len(df)} 条记录，包含 {df['code'].nunique()} 只股票")
    
    # 运行超参实验
    results_df = run_hyperparameter_experiment(df, params_dict)
    
    # 保存结果
    output_file = 'BBIKDJ_selector_experiment_results.parquet'
    results_df.to_parquet(output_file, index=False)
    print(f"\n实验结果已保存到: {output_file}")
    
    # 显示结果摘要
    print("\n=== 实验结果摘要 ===")
    print(f"总实验次数: {results_df['experiment_id'].nunique()}")
    print("各实验选出股票数量:")
    for exp_id, count in results_df.groupby('experiment_id')['selected_count'].first().items():
        print(f"  实验 {exp_id}: {count} 只股票")
    
    # 显示选出股票最多的参数组合
    if not results_df.empty:
        max_count = results_df['selected_count'].max()
        best_experiments = results_df[results_df['selected_count'] == max_count]
        if not best_experiments.empty:
            best_exp = best_experiments.iloc[0]
            print(f"\n选出股票最多的参数组合 ({max_count} 只):")
            param_cols = ['j_threshold', 'bbi_min_window', 'max_window', 'price_range_pct', 'bbi_q_threshold', 'j_q_threshold']
            for col in param_cols:
                if col in best_exp:
                    print(f"  {col}: {best_exp[col]}")


if __name__ == "__main__":
    main()
