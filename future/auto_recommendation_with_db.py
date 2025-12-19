# 带数据库功能的自动推荐程序示例 - 使用SQLAlchemy ORM

# from prompts import get_trading_prompt
import talib as ta
import pandas as pd
import json
from futu import OpenQuoteContext, RET_OK
from utils import get_ai_recommendation
from fetch_kline_daily import KlineFetcher
import datetime
import logging

# 导入数据库相关功能 - SQLAlchemy ORM版本
from db_schema import (
    DatabaseManager, 
    insert_portfolio_and_positions, 
    get_portfolios_by_account, 
    get_positions_by_portfolio,
    update_portfolio,
    delete_portfolio
)

# 配置logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("auto_recommendation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

daily_columns = ['code', 'name', 'update_time', 'last_price', 'open_price', 'high_price', \
    'low_price', 'pe_ratio', 'volume', 'turnover', 'turnover_rate']
hist_columns = ['code', 'name', 'time_key', 'open', \
    'close', 'high', 'low', 'pe_ratio', 'volume', \
        'turnover_rate', 'turnover', 'change_rate']

# 数据库配置
DB_PATH = 'investment_portfolio.db'

# 创建数据库管理器实例
db_manager = DatabaseManager(DB_PATH)

def get_stock_pool(pool_name="全部"):
    """
    获取自选股列表
    """
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    ret, data = quote_ctx.get_user_security(pool_name)
    if ret == RET_OK:
        logger.debug(f"获取到{pool_name}股票池，共{data.shape[0]}只股票")
        if data.shape[0] > 0:  # 如果自选股列表不为空
            res = {code: name for name, code in zip(data['name'].values.tolist(), data['code'].values.tolist())}
        else:
            res = {}
    else:
        logger.error(f"获取{pool_name}股票池失败: {data}")
        res = {}
    quote_ctx.close()
    return res

def create_db_session():
    """
    创建数据库会话
    """
    try:
        # 初始化数据库（如果还未初始化）
        db_manager.init_db()
        # 创建会话
        session = db_manager.create_session()
        logger.info(f"成功创建数据库会话")
        return session
    except Exception as e:
        logger.exception(f"数据库会话创建失败: {str(e)}")
        return None

def create_sample_positions(sample_market_state):
    """
    创建示例持仓数据（如果有持仓的话）
    这里仅作为演示，实际应用中应根据真实持仓情况生成
    """
    positions = []
    # 示例：假设持有一部分ETF
    # 这里可以根据实际情况从其他数据源获取持仓信息
    return positions

def main():
    # 数据库账户ID
    account_id = "user_001"  # 可以从配置文件或用户输入获取
    
    # 创建数据库会话
    db_session = create_db_session()
    if not db_session:
        logger.error("无法创建数据库会话，程序退出")
        return
    
    try:
        logger.info("开始执行自动推荐流程")
        
        # 获取股票池
        stock_pool = get_stock_pool("etf")
        logger.info(f"开始处理{len(stock_pool)}只ETF")
        
        sample_market_state = {}
        fetcher = KlineFetcher(stock_pool.keys(), daily_columns, hist_columns, 'data')
        
        # 获取历史K线数据
        data = fetcher.hist_kline_persistence('kline_etf_data')
        logger.debug(f"数据列: {data.columns.tolist()}")
        
        # 处理每只ETF数据
        for code, name in stock_pool.items():
            logger.debug(f"处理ETF: {code} - {name}")
            try:
                tmp = data[data.code == code]
                if tmp.empty:
                    logger.warning(f"未找到{code}({name})的历史数据")
                    continue
                
                tmp = tmp.sort_values(by='time_key')
                
                # 计算技术指标
                tmp['sma_7'] = ta.SMA(tmp['close'].values, timeperiod=7)
                tmp['sma_14'] = ta.SMA(tmp['close'].values, timeperiod=14)
                tmp['rsi_14'] = ta.RSI(tmp['close'].values, timeperiod=14)
                
                # 构建市场状态信息
                sample_market_state[code] = {
                    'price': tmp['close'].values[-1],
                    'change_24h': tmp['change_rate'].values[-1],
                    'indicators': {
                        'sma_7': tmp['sma_7'].values[-1],
                        'sma_14': tmp['sma_14'].values[-1],
                        'rsi_14': tmp['rsi_14'].values[-1],
                    }
                }
            except Exception as e:
                logger.exception(f"处理{code}({name})时发生异常: {str(e)}")
        
        # 构建投资组合信息
        sample_portfolio = {
            "total_value": 0.00,  # 实际应用中应根据持仓计算
            "cash": 120000.00,
            "positions": []  # 这里可以填充实际持仓
        }
        
        # 构建账户信息
        sample_account_info = {
            "initial_capital": 120000.00,
            "total_return": 0.0
        }
        
        # 生成示例持仓数据（如果需要）
        # positions_data = create_sample_positions(sample_market_state)
        positions_data = None  # 当前无持仓
        
        # 将投资组合数据保存到数据库
        logger.info("正在保存投资组合数据到数据库...")
        portfolio_id = insert_portfolio_and_positions(
            db_session, 
            account_id, 
            sample_portfolio, 
            sample_account_info,
            positions_data  # 如果有持仓数据
        )
        logger.info(f"投资组合数据已成功保存，portfolio_id: {portfolio_id}")
        
        # 查询最近的投资组合历史（可选）
        portfolios = get_portfolios_by_account(db_session, account_id)
        logger.info(f"账户{account_id}共有{len(portfolios)}条投资组合记录")
        
        # 生成交易提示词
        sample_prompt = get_trading_prompt(sample_market_state, sample_account_info, sample_portfolio)
        logger.debug(f"生成的交易提示词长度: {len(sample_prompt)}字符")
        
        # 获取AI推荐
        try:
            reasoning_content, content = get_ai_recommendation(sample_prompt)
            logger.info("获取AI推荐完成")
            logger.info(f"reasoning_content:\n{reasoning_content}")
            logger.info(f"content:\n{content}")
        except Exception as e:
            logger.exception(f"获取AI推荐时发生异常: {str(e)}")
        
    except Exception as e:
        logger.exception(f"主程序执行过程中发生异常: {str(e)}")
    finally:
        # 关闭数据库会话
        if db_session:
            db_session.close()
            logger.info("数据库会话已关闭")
        logger.info("自动推荐流程结束")
    return

def update_portfolio_data(portfolio_id, update_data):
    """
    更新投资组合数据的辅助函数
    
    参数:
        portfolio_id: 投资组合ID
        update_data: 要更新的数据字典
    """
    db_session = create_db_session()
    if not db_session:
        return False
    
    try:
        result = update_portfolio(db_session, portfolio_id, update_data)
        if result:
            logger.info(f"投资组合{portfolio_id}已成功更新")
        return result
    except Exception as e:
        logger.exception(f"更新投资组合时发生异常: {str(e)}")
        return False
    finally:
        if db_session:
            db_session.close()

def delete_portfolio_record(portfolio_id):
    """
    删除投资组合记录的辅助函数
    
    参数:
        portfolio_id: 投资组合ID
    """
    db_session = create_db_session()
    if not db_session:
        return False
    
    try:
        result = delete_portfolio(db_session, portfolio_id)
        if result:
            logger.info(f"投资组合{portfolio_id}已成功删除")
        return result
    except Exception as e:
        logger.exception(f"删除投资组合时发生异常: {str(e)}")
        return False
    finally:
        if db_session:
            db_session.close()

def view_portfolio_history(account_id=None):
    """
    查看投资组合历史记录的辅助函数
    """
    if not account_id:
        account_id = "user_001"
        
    db_session = create_db_session()
    if not db_session:
        return
    
    try:
        # 查询最近7天的投资组合记录
        end_date = datetime.datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        
        portfolios = get_portfolios_by_account(db_session, account_id, start_date, end_date)
        
        print(f"\n账户 {account_id} 在 {start_date} 到 {end_date} 期间的投资组合记录：")
        print(f"{'日期':<12}{'总价值':>12}{'现金':>12}{'总收益':>12}{'投资组合ID':<20}")
        print("-" * 70)
        
        # 使用ORM对象属性访问
        for p in portfolios:
            print(f"{p.date:<12}{p.total_value:>12.2f}{p.cash:>12.2f}{p.total_return:>12.2f}%{p.portfolio_id:<20}")
        
        # 如果有记录，显示最新记录的持仓
        if portfolios:
            latest_portfolio_id = portfolios[0].portfolio_id
            positions = get_positions_by_portfolio(db_session, latest_portfolio_id)
            
            if positions:
                print(f"\n最新持仓明细（日期：{portfolios[0].date}）：")
                print(f"{'代码':<10}{'名称':<12}{'数量':>10}{'价格':>10}{'市值':>12}{'盈亏':>10}")
                print("-" * 70)
                for pos in positions:
                    print(f"{pos.code:<10}{pos.name:<12}{pos.quantity:>10.2f}{pos.market_price:>10.2f}{pos.value:>12.2f}{pos.profit_loss_pct:>10.2f}%")
            else:
                print("\n当前无持仓")
                
    except Exception as e:
        logger.exception(f"查看投资组合历史时发生异常: {str(e)}")
    finally:
        if db_session:
            db_session.close()

if __name__ == "__main__":
    # 执行主程序
    # main()
    view_portfolio_history()
    # 查看投资组合历史（可选）
    # view_portfolio_history()