# 数据库工具类 - 封装db_schema.py中的所有数据操作方法
import talib as ta
import pandas as pd
from db_schema import (
    DatabaseManager,
    insert_portfolio_and_positions,
    get_portfolios_by_account,
    get_positions_by_portfolio,
    update_portfolio,
    delete_portfolio,
    insert_position,
    get_stock_data,
    update_stock,
    get_stock_name,
    delete_stock_data,
    clean_expired_data,
    insert_stock_kline,
    get_latest_date_for_stock,
    get_positions_by_account,
    Stock,
    Position,
    Portfolio
)
from sqlalchemy import func
from futu import OpenQuoteContext, RET_OK
import logging
from contextlib import contextmanager
from fetch_kline_daily import get_market_snapshot


# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_stock_pool(pool_name="全部"):
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    ret, data = quote_ctx.get_user_security(pool_name)
    if ret == RET_OK:
        # print(data)
        if data.shape[0] > 0:  # 如果自选股列表不为空
            res = {code: name for name, code in zip(data['name'].values.tolist(), data['code'].values.tolist())}
        else:
            res = []
    else:
        print('error:', data)
        res = []
    quote_ctx.close()
    return res
class DatabaseTools:
    """
    数据库操作工具类，封装了db_schema.py中的所有数据增删改查方法
    提供会话管理和错误处理机制
    """
    
    def __init__(self, db_file_or_manager='investment_portfolio.db'):
        """
        初始化数据库工具类
        
        参数:
            db_file_or_manager: 数据库文件路径字符串 或 DatabaseManager对象
        """
        if isinstance(db_file_or_manager, DatabaseManager):
            self.db_manager = db_file_or_manager
            # 确保数据库已初始化
            if not self.db_manager.SessionLocal:
                self.db_manager.init_db()
        else:
            # 假设是数据库文件路径
            self.db_manager = DatabaseManager(db_file_or_manager)
            self.db_manager.init_db()

    @contextmanager
    def get_session(self):
        """
        上下文管理器，用于获取和管理数据库会话
        自动处理会话的创建、提交、回滚和关闭
        """
        session = self.db_manager.create_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.exception(f"数据库操作异常: {str(e)}")
            raise
        finally:
            session.close()
    
    def insert_portfolio_and_positions(self, account_id, portfolio_data, account_info, positions_data=None):
        """
        插入投资组合和持仓数据
        """
        with self.get_session() as session:
            return insert_portfolio_and_positions(
                session, account_id, portfolio_data, account_info, positions_data
            )
    
    def get_portfolios_by_account(self, account_id, start_date=None, end_date=None):
        """
        查询指定账户的投资组合历史，并确保返回的数据不依赖于活动会话
        """
        with self.get_session() as session:
            portfolios = get_portfolios_by_account(session, account_id, start_date, end_date)
            # 转换为字典列表以避免会话关闭后的访问问题
            result = []
            for portfolio in portfolios:
                # 创建字典并手动复制所有属性
                portfolio_dict = {}
                # 只获取基本属性，避免触发延迟加载
                for attr in dir(portfolio):
                    if not attr.startswith('_') and not callable(getattr(portfolio, attr)):
                        value = getattr(portfolio, attr)
                        # 处理日期时间格式
                        if hasattr(value, 'strftime'):
                            value = value.strftime('%Y-%m-%d %H:%M:%S')
                        portfolio_dict[attr] = value
                result.append(portfolio_dict)
            return result
    
    def get_positions_by_portfolio(self, portfolio_id):
        """
        查询指定投资组合的持仓，并确保返回的数据不依赖于活动会话
        """
        with self.get_session() as session:
            positions = get_positions_by_portfolio(session, portfolio_id)
            # 转换为字典列表以避免会话关闭后的访问问题
            result = []
            for position in positions:
                # 创建字典并手动复制所有属性
                position_dict = {}
                # 只获取基本属性，避免触发延迟加载
                for attr in dir(position):
                    if not attr.startswith('_') and not callable(getattr(position, attr)):
                        value = getattr(position, attr)
                        # 处理日期时间格式
                        if hasattr(value, 'strftime'):
                            value = value.strftime('%Y-%m-%d %H:%M:%S')
                        position_dict[attr] = value
                result.append(position_dict)
            return result
    
    def update_portfolio(self, portfolio_id, update_data):
        """
        更新投资组合数据
        """
        with self.get_session() as session:
            return update_portfolio(session, portfolio_id, update_data)
    
    def delete_portfolio(self, portfolio_id):
        """
        删除投资组合（会级联删除相关持仓）
        """
        with self.get_session() as session:
            return delete_portfolio(session, portfolio_id)
    
    def insert_position(self, portfolio_id, account_id, position_data):
        """
        新增单个持仓记录到Position表
        """
        with self.get_session() as session:
            return insert_position(session, portfolio_id, account_id, position_data)
    
    def get_stock_data(self, stock_code, limit=100):
        """
        查询股票数据
        """
        with self.get_session() as session:
            return get_stock_data(session, stock_code, limit)
    
    def update_stock(self, stock_data):
        """
        更新股票数据
        """
        with self.get_session() as session:
            return update_stock(session, stock_data)
    
    def delete_stock_data(self, stock_code):
        """
        删除股票数据
        """
        with self.get_session() as session:
            return delete_stock_data(session, stock_code)
    
    def insert_stock_kline(self, stock_data):
        """
        插入股票数据
        """
        with self.get_session() as session:
            return insert_stock_kline(session, stock_data)
    
    def get_latest_date_for_stock(self, stock_code):
        """
        查询某个股票在表中最新的日期
        """
        with self.get_session() as session:
            return get_latest_date_for_stock(session, stock_code)
    
    def get_positions_by_account(self, account_id, start_date=None, end_date=None, code=None):
        """
        查询指定账户的持仓记录
        """
        with self.get_session() as session:
            positions = get_positions_by_account(session, account_id, start_date, end_date, code)
            # 转换为字典列表以避免会话关闭后的访问问题
            result = []
            for position in positions:
                # 创建字典并手动复制所有属性
                position_dict = {}
                # 只获取基本属性，避免触发延迟加载
                for attr in dir(position):
                    if not attr.startswith('_') and not callable(getattr(position, attr)):
                        value = getattr(position, attr)
                        # 处理日期时间格式
                        if hasattr(value, 'strftime'):
                            value = value.strftime('%Y-%m-%d %H:%M:%S')
                        position_dict[attr] = value
                result.append(position_dict)
            return result
    
    def delete_position(self, position_id):
        """
        删除指定ID的持仓记录
        """
        with self.get_session() as session:
            try:
                # 查找持仓记录
                position = session.query(Position).filter(Position.id == position_id).first()
                if position:
                    session.delete(position)
                    session.commit()
                    logger.info(f"成功删除持仓记录，ID: {position_id}")
                    return True
                else:
                    logger.warning(f"未找到持仓记录，ID: {position_id}")
                    return False
            except Exception as e:
                session.rollback()
                logger.exception(f"删除持仓记录失败: {str(e)}")
                raise
    def get_cached_stock_count(self):
        """
        查询缓存的股票数量
        """
        with self.get_session() as session:
            cnts = session.query(Stock.code).distinct().count()
            return cnts
    def get_total_kline_entries(self):
        """
        查询缓存的股票kline数据数量
        """
        with self.get_session() as session:
            cnts = session.query(Stock).count()
            return cnts

    def get_last_update_time(self):
        """
        查询数据库中最新的更新时间
        """
        with self.get_session() as session:
            last_update = session.query(func.max(Stock.time_key)).scalar()
            return last_update
    def insert_portfolio_and_positions(self, account_id, portfolio_data, account_info):
        """
        新增投资组合数据到Portfolio表和Position表
        """
        with self.get_session() as session:
            return insert_portfolio_and_positions(session, account_id, portfolio_data, account_info)
# 示例使用代码
    def get_market_place(self):
        stock_pool = get_stock_pool("etf")
        sample_market_state = {}
        for code, name in stock_pool.items():
            print(code, name)
            tmp_data = self.get_stock_data(code, limit=100)
            tmp_data = pd.DataFrame(tmp_data)
            tmp = tmp_data.sort_values(by='time_key')
            tmp['sma_5'] = ta.SMA(tmp['close'].values, timeperiod=5)
            tmp['sma_10'] = ta.SMA(tmp['close'].values, timeperiod=10)
            tmp['sma_20'] = ta.SMA(tmp['close'].values, timeperiod=20)
            tmp['rsi_14'] = ta.RSI(tmp['close'].values, timeperiod=14)
            sample_market_state[code] = {
                'last_price': tmp['close'].values[-1],
                'change_24h': tmp['change_rate'].values[-1],
                'now_price': get_market_snapshot(code),
                'indicators': {
                    'sma_5': tmp['sma_5'].values[-1],
                    'sma_10': tmp['sma_10'].values[-1],
                    'sma_20': tmp['sma_20'].values[-1], 
                    'rsi_14': tmp['rsi_14'].values[-1],
                }
            }
        print(sample_market_state)
        return sample_market_state
    def clean_expired_data(self):
        """
        清理过期数据
        """
        with self.get_session() as session:
            clean_expired_data(session)
    def get_stock_name(self, stock_code):
        """
        查询股票名称
        """
        with self.get_session() as session:
            return get_stock_name(session, stock_code)

def example_usage():
    """示例使用方法"""
    try:
        # 创建数据库工具实例
        db_tools = DatabaseTools('investment_portfolio.db')  # 也可以传入DatabaseManager对象
        
        # 示例数据
        account_id = "user_001"
        sample_portfolio = {
            "total_value": 120000.00,
            "cash": 120000.00,
            "positions": []
        }
        sample_account_info = {
            "initial_capital": 120000.00,
            "total_return": 0.0
        }
        
        # 示例1: 插入投资组合数据
        print("\n示例1: 插入投资组合数据")
        portfolio_id = db_tools.insert_portfolio_and_positions(
            account_id, sample_portfolio, sample_account_info
        )
        print(f"投资组合数据已插入，ID: {portfolio_id}")
        
        # 示例2: 查询投资组合
        print("\n示例2: 查询投资组合")
        portfolios = db_tools.get_portfolios_by_account(account_id)
        print(f"查询到{len(portfolios)}个投资组合记录")
        
        # 示例3: 插入持仓记录
        print("\n示例3: 插入持仓记录")
        sample_position = {
            "code": "600519",
            "name": "贵州茅台",
            "quantity": 100,
            "price": 1800.00,
            "value": 180000.00,
            "market_price": 1820.00,
            "profit_loss": 2000.00,
            "profit_loss_pct": 1.11
        }
        position_id = db_tools.insert_position(portfolio_id, account_id, sample_position)
        print(f"持仓记录已插入，ID: {position_id}")
        
        # 示例4: 查询持仓
        print("\n示例4: 查询持仓")
        positions = db_tools.get_positions_by_portfolio(portfolio_id)
        print(f"查询到{len(positions)}个持仓记录")
        for pos in positions:
            print(f"代码: {pos.code}, 名称: {pos.name}, 数量: {pos.quantity}, 价值: {pos.value:.2f}")
        
    except Exception as e:
        logger.exception(f"示例运行失败: {str(e)}")

if __name__ == "__main__":
    example_usage()