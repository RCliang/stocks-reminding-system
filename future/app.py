# 股票投资组合分析仪表板 - Streamlit应用

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import datetime
import logging
import time
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import func
from db_tools import DatabaseTools

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False    # 用来正常显示负号

# 导入数据库相关功能
from db_schema import (
    DatabaseManager, 
    get_portfolios_by_account, 
    get_positions_by_portfolio,
    Portfolio,
    Position,
    Base  # 添加Base导入
)
from sqlalchemy.orm import sessionmaker  # 添加sessionmaker导入

# 导入推荐系统相关功能
from utils import get_ai_recommendation

# 尝试导入talib，如果不可用则设置一个标志
try:
    import talib as ta
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False
    print("警告：talib库未安装，技术指标计算功能将不可用")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("streamlit_dashboard.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 数据库配置
DB_PATH = 'investment_portfolio.db'

# 创建数据库管理器实例
db_manager = DatabaseManager(DB_PATH)

def reinitialize_portfolio_tables(account_id):
    """
    注意：这将删除所有现有的投资组合和持仓数据
    """
    db_tools = DatabaseTools(db_manager)
    try:
        # 删除所有持仓记录
        with db_manager.SessionLocal() as session:
            session.query(Position).delete()
            session.commit()
            logger.info("所有持仓记录已删除")
        
        # 删除所有投资组合记录
        with db_manager.SessionLocal() as session:
            session.query(Portfolio).delete()
            session.commit()
            logger.info("所有投资组合记录已删除")
        sample_portfolio = {
            "total_value": 120000.00,
            "cash": 120000.00,
            "positions": []
        }
        sample_account_info = {
            "initial_capital": 120000.00,
            "total_return": 0.0
        }
        
        # 插入投资组合数据
        portfolio_id = db_tools.insert_portfolio_and_positions(account_id, sample_portfolio, sample_account_info)
        print(f"投资组合数据已插入，ID: {portfolio_id}")
        
        # 查询投资组合
        portfolios = get_portfolios_by_account(db_manager.create_session(), account_id)
        print(f"查询到{len(portfolios)}个投资组合记录")
        return True, "投资组合和持仓表已成功重新初始化"
    except Exception as e:
        logger.exception(f"重新初始化表失败: {str(e)}")
        return False, f"重新初始化表失败: {str(e)}"


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

def load_portfolio_data(account_id, start_date, end_date):
    """
    加载投资组合数据
    """
    db_session = create_db_session()
    if not db_session:
        return None, None
    
    try:
        # 查询投资组合历史
        portfolios = get_portfolios_by_account(
            db_session, 
            account_id, 
            start_date.strftime('%Y-%m-%d'), 
            end_date.strftime('%Y-%m-%d')
        )
        
        if not portfolios:
            return None, None
        
        # 转换为DataFrame
        portfolio_data = []
        for p in portfolios:
            portfolio_data.append({
                '日期': p.date,
                '总价值': p.total_value,
                '现金': p.cash,
                '初始资金': p.initial_capital,
                '总收益': p.total_return,
                '投资组合ID': p.portfolio_id
            })
        
        portfolio_df = pd.DataFrame(portfolio_data)
        portfolio_df['日期'] = pd.to_datetime(portfolio_df['日期'])
        portfolio_df = portfolio_df.sort_values('日期')
        
        # 获取最新的持仓数据
        latest_portfolio_id = portfolios[0].portfolio_id
        positions = get_positions_by_portfolio(db_session, latest_portfolio_id)
        
        positions_data = []
        for pos in positions:
            positions_data.append({
                '代码': pos.code,
                '名称': pos.name,
                '数量': pos.quantity,
                '持仓价格': pos.price,
                '当前价格': pos.market_price,
                '市值': pos.value,
                '盈亏金额': pos.profit_loss,
                '盈亏百分比': pos.profit_loss_pct
            })
        
        positions_df = pd.DataFrame(positions_data)
        
        return portfolio_df, positions_df
    
    except Exception as e:
        logger.exception(f"加载投资组合数据失败: {str(e)}")
        return None, None
    finally:
        if db_session:
            db_session.close()

def create_profit_loss_chart(portfolio_df):
    """
    创建盈亏趋势图
    """
    if portfolio_df is None or portfolio_df.empty:
        return None
    
    fig = go.Figure()
    
    # 添加总价值曲线
    fig.add_trace(go.Scatter(
        x=portfolio_df['日期'],
        y=portfolio_df['总价值'],
        mode='lines+markers',
        name='总价值',
        line=dict(color='#1f77b4', width=2)
    ))
    
    # 添加初始资金参考线
    if not portfolio_df.empty:
        initial_capital = portfolio_df['初始资金'].iloc[0]
        fig.add_hline(
            y=initial_capital,
            line_dash="dash",
            line_color="red",
            annotation_text=f"初始资金: {initial_capital}",
            annotation_position="right"
        )
    
    # 更新布局
    fig.update_layout(
        title='投资组合价值趋势',
        xaxis_title='日期',
        yaxis_title='金额 (元)',
        template='plotly_white',
        height=400
    )
    
    return fig

# 设置页面配置
st.set_page_config(
    page_title="股票投资组合分析仪表板",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 添加应用标题
st.title("📈 股票投资组合分析仪表板")

# 创建侧边栏
with st.sidebar:
    st.header("🔧 设置")
    
    # 账户ID输入
    account_id = st.text_input(
        "账户ID",
        value="user_001",
        help="输入您的账户ID"
    )
    
    # 日期范围选择
    st.subheader("日期范围")
    end_date = st.date_input("结束日期", datetime.datetime.now())
    start_date = st.date_input("开始日期", datetime.datetime.now() - datetime.timedelta(days=30))
    
    # 分割线
    st.markdown("---")
    
    # 关于部分
    st.header("📝 关于")
    st.info("这是一个股票投资组合分析仪表板，用于展示持仓情况、盈亏分析和投资建议。")
    
    # 数据库重置按钮
    st.markdown("---")
    st.header("⚠️ 数据库操作")
    if st.button("重新初始化投资组合表", type="secondary"):
        # 添加确认对话框（使用标准Streamlit组件）
        success, message = reinitialize_portfolio_tables(account_id)
        if success:
            st.success(message)
        else:
            st.error(message)

# 初始化会话状态
if 'portfolio_data' not in st.session_state:
    st.session_state.portfolio_data = None
    
if 'positions_data' not in st.session_state:
    st.session_state.positions_data = None

if 'latest_portfolio_id' not in st.session_state:
    st.session_state.latest_portfolio_id = None

# 将load_portfolio_data函数保存到会话状态中，供子页面使用
st.session_state.load_portfolio_data = load_portfolio_data

# 导入子页面模块
try:
    from portfolio_overview import show_portfolio_overview
    from trend_analysis import show_trend_analysis
    from investment_advice import show_investment_advice
    from data_update import show_data_update
    from trade_operations import show_trade_operations
    MODULES_LOADED = True
except ImportError as e:
    MODULES_LOADED = False
    st.error(f"模块导入失败: {str(e)}")

# 创建选项卡
tabs = st.tabs(["📊 投资组合概览", "📈 趋势分析", "💡 投资建议", "⚙️ 数据更新", "💰 交易操作"])

# 投资组合概览选项卡
with tabs[0]:
    if MODULES_LOADED:
        show_portfolio_overview(account_id, start_date, end_date)
    else:
        st.warning("请确保所有子模块已正确创建")

# 趋势分析选项卡
with tabs[1]:
    if MODULES_LOADED:
        show_trend_analysis()
    else:
        st.warning("请确保所有子模块已正确创建")

# 投资建议选项卡
with tabs[2]:
    if MODULES_LOADED:
        show_investment_advice(account_id)
    else:
        st.warning("请确保所有子模块已正确创建")

# 数据更新选项卡
with tabs[3]:
    if MODULES_LOADED:
        show_data_update()
    else:
        st.warning("请确保所有子模块已正确创建")

# 交易操作选项卡
with tabs[4]:
    if MODULES_LOADED:
        show_trade_operations(account_id, start_date, end_date)
    else:
        st.warning("请确保所有子模块已正确创建")

# 添加页脚
st.markdown("---")
st.caption("© 2024 股票投资组合分析仪表板")

if __name__ == "__main__":
    # Streamlit应用不需要main函数调用，这里只是为了代码完整性
    pass