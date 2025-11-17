import pandas as pd
import json
from utils import get_ai_recommendation
from typing import Dict, List, Tuple
from futu import *
import time
import json_repair
from openai import OpenAI
from collections import defaultdict

def get_prompt(concept_plates: str, topic: str) -> str:

    return f"""请从以下找出的概念板块中找出和列出的主题相关的概念板块，并以json格式输出
概念板块:
{concept_plates}
主题:
{topic}
输出示例：
```json{{
    "concept": [
        "稀土概念",
        "AI",
    ]
}}```
"""

def get_all_plate(market: Market):
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    ret, data = quote_ctx.get_plate_list(market, Plate.CONCEPT)
    res = {}
    if ret == RET_OK:
        for index, row in data.iterrows():
            res[row['plate_name']] = row['code']
    else:
        print('error:', data)
    quote_ctx.close()
    return res

def filter_stocks_by_kdj_criteria(market: Market, plate_code: str) -> Dict[str, str]:
    """
    根据KDJ指标筛选股票
    
    Args:
        market: 市场类型，如 Market.SH, Market.SZ
        plate_code: 板块代码
    
    Returns:
        Dict[str, str]: 股票代码到股票名称的映射字典
    """
    stock_results = {}
    
    try:
        # 使用上下文管理器自动关闭连接
        with OpenQuoteContext(host='127.0.0.1', port=11111) as quote_ctx:
            # 创建价格过滤器（价格范围2-1000）
            price_filter = SimpleFilter()
            price_filter.filter_min = 2
            price_filter.filter_max = 1000
            price_filter.stock_field = StockField.CUR_PRICE
            price_filter.is_no_filter = True
            
            # 创建KDJ J值过滤器（J值小于-5）
            kdj_filter = CustomIndicatorFilter()
            kdj_filter.ktype = KLType.K_DAY
            kdj_filter.stock_field1 = StockField.KDJ_J
            kdj_filter.stock_field1_para = [9, 3, 3]
            kdj_filter.stock_field2 = StockField.VALUE
            kdj_filter.relative_position = RelativePosition.LESS
            kdj_filter.value = -5
            kdj_filter.is_no_filter = False
            
            # 分页查询
            nBegin = 0
            last_page = False
            ret_list = []
            
            while not last_page:
                nBegin += len(ret_list)
                ret, ls = quote_ctx.get_stock_filter(
                    market=market, 
                    filter_list=[price_filter, kdj_filter], 
                    begin=nBegin, 
                    plate_code=plate_code
                )  
                
                if ret == RET_OK:
                    last_page, all_count, ret_list = ls
                    print(f'板块 {plate_code} 符合条件股票总数 = {all_count}')
                    
                    # 收集股票代码和名称
                    for item in ret_list:
                        stock_results[item.stock_code] = item.stock_name
                else:
                    print(f'筛选失败: {ls}')
                    break
                
                # 添加时间间隔，避免触发限频
                time.sleep(3)
                
    except Exception as e:
        print(f'筛选过程中发生错误: {e}')
    
    return stock_results
def get_plate_stocks(plate_code: str) -> List[str]:
    """获取指定板块下的所有股票代码
    
    Args:
        plate_code: 板块代码
        
    Returns:
        List[str]: 股票代码列表
    """
    try:
        with OpenQuoteContext(host='127.0.0.1', port=11111) as quote_ctx:
            ret, data = quote_ctx.get_plate_stock(plate_code)
            if ret == RET_OK:
                # 尝试获取不同可能的列名
                if 'stock_code' in data.columns:
                    return data['stock_code'].values.tolist()
                elif 'code' in data.columns:
                    return data['code'].values.tolist()
                else:
                    print(f'未知的股票代码列名: {data.columns}')
                    return []
            else:
                print(f'获取板块股票失败: {data}')
    except Exception as e:
        print(f'获取板块股票时发生异常: {e}')
    
    return []

def get_relevant_plates(topic: str, market: Market) -> Tuple[List[str], Dict[str, str]]:
    """获取与指定主题相关的概念板块
    
    Args:
        topic: 需要匹配的主题
        market: 市场类型
        
    Returns:
        Tuple[List[str], Dict[str, str]]: 相关板块名称列表和所有板块映射
    """
    all_plates = get_all_plate(market)
    concept_plates_str = ','.join(all_plates.keys())
    
    prompt = get_prompt(concept_plates_str, topic)
    try:
        ai_response = get_ai_recommendation(prompt)
        decoded = json_repair.loads(ai_response)
        return decoded['concept'], all_plates
    except Exception as e:
        print(f'解析AI响应失败: {e}')
        return [], all_plates

def compute_plate_ratio(topic: str, market: Market = Market.SH) -> pd.DataFrame:
    """计算并返回板块股票筛选比例数据框
    
    Args:
        topic: 主题关键词，用于筛选相关板块
        market: 市场类型，默认为上海市场
        
    Returns:
        pd.DataFrame: 包含板块代码、名称、股票数量和筛选比例的数据框
    """
    # 获取相关板块
    relevant_plate_names, all_plates = get_relevant_plates(topic, market)
    
    # 创建反向映射：code -> name
    code_to_name = {v: k for k, v in all_plates.items()}
    
    # 存储结果数据
    plate_data = []
    
    for plate_name in relevant_plate_names:
        plate_code = all_plates.get(plate_name)
        if not plate_code:
            print(f'警告: 板块 {plate_name} 未找到对应的代码')
            continue
        
        print(f'处理板块: {plate_name} ({plate_code})')
        
        # 获取符合条件的股票
        filtered_stocks = filter_stocks_by_kdj_criteria(market, plate_code)
        filtered_count = len(filtered_stocks)
        
        # 获取该板块所有股票
        all_stocks = get_plate_stocks(plate_code)
        total_count = len(all_stocks)
        
        # 计算比例
        ratio = filtered_count / total_count if total_count > 0 else 0
        
        # 存储数据
        plate_data.append({
            '板块代码': plate_code,
            '板块名称': plate_name,
            '股票数量': total_count,
            '筛选后股票数量': filtered_count,
            '筛选后股票数量占比': ratio
        })
        
        # 避免API调用过于频繁
        time.sleep(10)
    
    # 创建并返回DataFrame
    return pd.DataFrame(plate_data)

# 示例使用代码
if __name__ == "__main__":
    # 计算特定主题的板块比例
    need_plates_topic = ["稀土概念", "人工智能", "新能源汽车", "固态电池", "白酒", "银行保险证券", "芯片", "国产替代", "机器人"]
    result_df = compute_plate_ratio(",".join(need_plates_topic), Market.SH)
    print(result_df)