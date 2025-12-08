import yaml
import backtrader as bt
import talib as ta
import pandas as pd
import json
from futu import *
import time
import datetime

def get_market_snapshot(codes: str):
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)

    ret, data = quote_ctx.get_market_snapshot(codes)
    if ret == RET_OK:
        last_price = data['last_price'][0]
    else:
        print('error:', data)
    quote_ctx.close()
    return last_price

def get_stock_pool(pool_name="全部"):
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    ret, data = quote_ctx.get_user_security(pool_name)
    if ret == RET_OK:
        # print(data)
        if data.shape[0] > 0:  # 如果自选股列表不为空
            res = data['code'].values.tolist()
        else:
            res = []
    else:
        print('error:', data)
        res = []
    quote_ctx.close()
    return res
# 从 config.yaml 文件中读取配置
with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
TARGET_POOLS = get_stock_pool("etf")
daily_columns = ['code', 'name', 'update_time', 'last_price', 'open_price', 'high_price', \
    'low_price', 'pe_ratio', 'volume', 'turnover', 'turnover_rate']
columns_dict = config['columns_dict']
hist_columns = ['code', 'name', 'time_key', 'open', \
    'close', 'high', 'low', 'pe_ratio', 'volume', \
        'turnover_rate', 'turnover', 'change_rate']
        
def acquire_security_list():
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    ret, data = quote_ctx.get_user_security("全部")
    quote_ctx.close()
    if ret == RET_OK:
        if data.shape[0] > 0:  # 如果自选股列表不为空
            return data['code'].values.tolist()
    else:
        print('error:', data)
    return []

class KlineFetcher:
    def __init__(self, target_pools, daily_columns, hist_columns, save_dir):
        self.target_pools = target_pools
        self.daily_columns = daily_columns
        self.hist_columns = hist_columns
        self.save_dir = save_dir

    @staticmethod
    def fetch_kline_daily(daily_columns: list, target_data: list):
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        ret, data = quote_ctx.get_market_snapshot(target_data)
        if ret == RET_OK:
            data = data[daily_columns]
            quote_ctx.close()
            return data
        else:
            print('error:', data)
            quote_ctx.close()
            return None
    
    def process_daily_kline(self, data):
        data = data.rename(columns=columns_dict)
        data['time_key'] = [datetime.datetime.strptime(x[:10], "%Y-%m-%d") for x in data['time_key']]
        data['change_rate'] = (data['close'] - data['open']) / data['open']
        data['change_rate'] = data['change_rate'].round(4)
        return data

    def fetch_hist_kline(self, code, start, end, ktype=KLType.K_DAY, max_count=200, timeout=30):
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        
        try:
            ret, data, page_req_key = quote_ctx.request_history_kline(code, start=start, 
            end=end, ktype=ktype, max_count=max_count)
            if ret != RET_OK:
                print(f'Error fetching data for {code}: {data}')
                return None
            
            data = data[hist_columns]
            page_count = 1
            max_pages = 100  # 设置最大页数，防止无限循环
            
            while page_req_key != None and page_count < max_pages:
                print(f'Fetching page {page_count} for {code}...')
                ret, new_data, page_req_key = quote_ctx.request_history_kline(code, start=start, 
                end=end, ktype=ktype, max_count=200, page_req_key=page_req_key)
                
                if ret != RET_OK:
                    print(f'Error fetching page {page_count} for {code}: {data}')
                    break
                
                new_data = new_data[hist_columns]
                data = pd.concat([data, new_data], axis=0)
                page_count += 1
                
            print(f'Finished fetching data for {code}, total pages: {page_count}')
            return data
        except Exception as e:
            print(f'Exception occurred for {code}: {str(e)}')
            return None
        finally:
            quote_ctx.close()
    
    def hist_kline_persistence(self, file_name, start_date='2024-01-01'):
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        final_data = pd.DataFrame(columns=self.hist_columns)  # 修复列名初始化
        
        total_stocks = len(self.target_pools)
        for i, item in enumerate(self.target_pools):
            print(f'Processing stock {i+1}/{total_stocks}: {item}')
            data = self.fetch_hist_kline(item, start_date, yesterday)
            
            if data is not None and not data.empty:
                data['time_key'] = [datetime.datetime.strptime(x[:10], "%Y-%m-%d") for x in data['time_key']]
                data['change_rate'] = data['change_rate'].round(4)
                final_data = pd.concat([final_data, data], axis=0)
            else:
                print(f'Skipping {item} due to empty data')
        
        final_data.to_parquet(f'{self.save_dir}/{file_name}.parquet', index=False)
        print(f'Data saved to {self.save_dir}/{file_name}.parquet')
        return final_data

    def update_kline_daily(self):
        data = self.fetch_kline_daily(self.daily_columns, self.target_pools)
        data = self.process_daily_kline(data)
        try:
            final_data = pd.read_parquet(f'{self.save_dir}/kline_etf_data.parquet')
        except FileNotFoundError:
            final_data = pd.DataFrame()
        final_data = pd.concat([final_data, data], axis=0)
        final_data.to_parquet(f'{self.save_dir}/kline_etf_data.parquet', index=False)
        print("kline_etf_data.parquet updated")
        return

def main():
    fetcher = KlineFetcher(TARGET_POOLS, daily_columns, hist_columns, 'data')
    tmp = fetcher.hist_kline_persistence()
    # fetcher.update_kline_daily()
    return

if __name__ == '__main__':
    main()


