import argparse
import pandas as pd
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import logging
import time

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_stock_data_from_parquet(parquet_file: Path) -> Optional[pd.DataFrame]:
    """从单个parquet文件加载股票数据"""
    try:
        if not parquet_file.exists():
            logger.error(f"Parquet文件不存在: {parquet_file}")
            return None
        
        # 读取parquet文件
        df = pd.read_parquet(parquet_file)
        
        # 确保日期列已正确解析
        if 'date' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'])
            
        # 检查数据是否为空
        if df.empty:
            logger.warning(f"Parquet文件 {parquet_file} 没有数据")
            return None
            
        logger.info(f"成功加载parquet文件，共 {len(df)} 条记录")
        return df
    except Exception as e:
        logger.error(f"读取parquet文件 {parquet_file} 失败: {e}")
        return None

def find_by_price_from_df(
    df: pd.DataFrame,
    target_price: float,
    price_type: str = 'close',
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tolerance: float = 0.01
) -> List[Tuple[str, float, str]]:
    """
    从DataFrame中查找指定价格的股票数据
    
    Args:
        df: 包含所有股票数据的DataFrame
        target_price: 目标价格
        price_type: 价格类型 ('close', 'high', 'low')
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        tolerance: 价格容差
        
    Returns:
        符合条件的股票列表 (代码, 价格, 日期)
    """
    # 验证价格类型
    valid_price_types = ['close', 'high', 'low']
    if price_type not in valid_price_types:
        raise ValueError(f"价格类型必须是: {', '.join(valid_price_types)}")
    
    # 验证DataFrame中是否包含必要的列
    required_columns = ['code', 'time_key', price_type]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"DataFrame缺少必要的列: {', '.join(missing_columns)}")
    
    results = []
    
    min_price = target_price - tolerance
    max_price = target_price + tolerance
    
    # 按日期筛选
    df_filtered = df.copy()
    if start_date or end_date:
        # 如果只指定了开始时间，将开始时间作为结束时间
        if start_date and end_date is None:
            end_date = start_date
        # 如果只指定了结束时间，将结束时间作为开始时间
        elif end_date and start_date is None:
            start_date = end_date
            
        if start_date:
            start_dt = pd.to_datetime(start_date)
            df_filtered = df_filtered[df_filtered['time_key'] >= start_dt]
        if end_date:
            end_dt = pd.to_datetime(end_date)
            df_filtered = df_filtered[df_filtered['time_key'] <= end_dt]
        
        if df_filtered.empty:
            logger.info("没有找到符合日期范围的数据")
            return results
    
    # 查找所有符合条件的价格
    mask = (df_filtered[price_type] >= min_price) & (df_filtered[price_type] <= max_price)
    matching_rows = df_filtered[mask]
    
    logger.info(f"找到 {len(matching_rows)} 条符合条件的记录")
    
    # 构建结果列表
    for _, row in matching_rows.iterrows():
        results.append((
            row['code'],  # 股票代码
            row[price_type],  # 价格
            pd.to_datetime(row['time_key']).strftime('%Y-%m-%d')  # 日期
        ))
    
    # 按股票代码和日期排序
    return sorted(results, key=lambda x: (x[0], x[2]))

def print_results(results: List[Tuple[str, float, str]], price_type: str):
    """打印搜索结果"""
    if not results:
        print("未找到符合条件的股票")
        return
    
    price_type_name = {
        'close': '收盘价',
        'high': '最高价', 
        'low': '最低价'
    }.get(price_type, price_type)
    
    print(f"\n找到 {len(results)} 条符合条件的记录:")
    print("-" * 50)
    print(f"{'股票代码':<10} {price_type_name:<10} {'日期':<12}")
    print("-" * 35)
    
    # 显示前20条结果和后20条结果
    display_results = []
    if len(results) <= 40:
        display_results = results
    else:
        display_results = results[:20] + results[-20:]
    
    for code, price, date in display_results:
        print(f"{code:<10} {price:<10.2f} {date:<12}")
    
    # 如果结果太多，提示用户
    if len(results) > 40:
        print(f"\n... 省略了中间 {len(results) - 40} 条结果 ...")

def main():
    parser = argparse.ArgumentParser(description="查找指定历史价格的股票 - 单文件版本")
    parser.add_argument("price", type=float, help="目标价格")
    parser.add_argument("--data-file", default="./data/kline_data.parquet", help="Parquet数据文件路径 (默认: ./data/kline_data.parquet)")
    parser.add_argument("--price-type", choices=['close', 'high', 'low'], default='close', 
                       help="价格类型 (默认: close)")
    parser.add_argument("--start-date", help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--tolerance", type=float, default=0.01, help="价格容差 (默认: 0.01)")
    parser.add_argument("--benchmark", action="store_true", help="显示性能基准测试")
    
    args = parser.parse_args()
    
    start_time = time.time()
    
    # 加载数据
    parquet_file = Path(args.data_file)
    logger.info(f"开始从 {parquet_file} 加载股票数据...")
    df = load_stock_data_from_parquet(parquet_file)
    
    if df is None:
        logger.error("没有找到可用的股票数据")
        return
    
    load_time = time.time() - start_time
    logger.info(f"数据加载完成，耗时: {load_time:.2f}秒")
    
    # 执行搜索
    try:
        search_start_time = time.time()
        logger.info("开始查找符合条件的股票...")
        results = find_by_price_from_df(
            df, 
            args.price, 
            args.price_type,
            args.start_date,
            args.end_date,
            args.tolerance
        )
        search_time = time.time() - search_start_time
        logger.info(f"查找完成，耗时: {search_time:.2f}秒")
        
        print_results(results, args.price_type)
        
        if args.benchmark:
            total_time = time.time() - start_time
            # 统计包含的股票数量
            stock_count = df['code'].nunique() if 'code' in df.columns else 0
            print(f"\n性能统计:")
            print(f"数据加载时间: {load_time:.2f}秒")
            print(f"查找时间: {search_time:.2f}秒")
            print(f"总耗时: {total_time:.2f}秒")
            print(f"数据总行数: {len(df)}")
            print(f"包含股票数量: {stock_count}")
            print(f"找到结果数量: {len(results)}")
            
    except ValueError as e:
        logger.error(f"参数错误: {e}")
        return
    except Exception as e:
        logger.error(f"处理过程中出错: {e}")
        return

if __name__ == "__main__":
    main()
