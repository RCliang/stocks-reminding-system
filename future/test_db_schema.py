from db_schema import Stock, Base, DatabaseManager, insert_stock_kline
from fetch_kline_daily import get_stock_pool, KlineFetcher
from datetime import datetime
from db_tools import DatabaseTools
import pandas as pd

daily_columns = ['code', 'name', 'update_time', 'last_price', 'open_price', 'high_price', \
    'low_price', 'pe_ratio', 'volume', 'turnover', 'turnover_rate']
hist_columns = ['code', 'name', 'time_key', 'open', \
    'close', 'high', 'low', 'pe_ratio', 'volume', \
        'turnover_rate', 'turnover', 'change_rate']
# 打印Stock类的__tablename__属性
print(f"Stock类的__tablename__属性: {Stock.__tablename__}")

# 验证是否是Base的子类
print(f"Stock类是Base的子类: {issubclass(Stock, Base)}")

# 尝试初始化数据库连接（但不创建表）
db_manager = DatabaseManager('investment_portfolio.db')
print("数据库管理器创建成功")

if __name__ == "__main__":
    # 测试插入股票数据
    codes_to_update=[]
    codes_to_update.extend(get_stock_pool("etf"))
    db_tools = DatabaseTools(db_manager)

    count=1
    try:
        # data = db_tools.get_portfolios_by_account("user_001")
        # # 如果数据库返回的是 datetime 对象，则格式化为字符串
        # # 展示查询到的投资组合数据
        # data2 = db_tools.get_positions_by_portfolio("port_user_001_2025-12-01_1764591628")
        latest_date = db_tools.get_latest_date_for_stock('SZ.002466')
        if latest_date:
            # print(f"查询到 {len(data)} 条股票数据记录：")
            print(f"data: {latest_date}")
        # if data2:
        #     print(f"查询到 {len(data2)} 条持仓记录：")
        #     for position_dict in data2:
        #         print(position_dict)
        else:
            print("未查询到任何持仓数据")   
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        # 确保会话关闭
        print("会话已关闭")

