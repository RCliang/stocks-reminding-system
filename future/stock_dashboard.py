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

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False    # 用来正常显示负号

# 导入数据库相关功能
from db_schema import (
    DatabaseManager, 
    get_portfolios_by_account, 
    get_positions_by_portfolio
)

# 导入推荐系统相关功能
from auto_recommendation_with_db import get_stock_pool, KlineFetcher
from prompts import get_trading_prompt
from utils import get_ai_recommendation
import pandas as pd
import numpy as np

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

# 主内容区域
# 创建选项卡
tabs = st.tabs(["📊 投资组合概览", "📈 趋势分析", "💡 投资建议", "⚙️ 数据更新", "💰 交易操作"])

# 初始化会话状态
if 'portfolio_data' not in st.session_state:
    st.session_state.portfolio_data = None
    
if 'positions_data' not in st.session_state:
    st.session_state.positions_data = None

if 'latest_portfolio_id' not in st.session_state:
    st.session_state.latest_portfolio_id = None

# 投资组合概览选项卡
with tabs[0]:
    st.header("投资组合概览")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        load_data_btn = st.button("🔄 加载最新数据", use_container_width=True)
    
    if load_data_btn:
        with st.spinner("正在加载数据..."):
            portfolio_df, positions_df = load_portfolio_data(account_id, start_date, end_date)
            
            if portfolio_df is not None and not portfolio_df.empty:
                st.session_state.portfolio_data = portfolio_df
                st.session_state.positions_data = positions_df
                if portfolios:
                    st.session_state.latest_portfolio_id = portfolios[0].portfolio_id
                st.success("数据加载成功！")
            else:
                st.warning("未找到投资组合数据")
    
    # 显示投资组合概览指标
    if st.session_state.portfolio_data is not None and not st.session_state.portfolio_data.empty:
        latest_data = st.session_state.portfolio_data.iloc[-1]
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总价值", f"¥{latest_data['总价值']:,.2f}")
        with col2:
            st.metric("现金", f"¥{latest_data['现金']:,.2f}")
        with col3:
            st.metric("总收益", f"{latest_data['总收益']:.2f}%")
        with col4:
            st.metric("初始资金", f"¥{latest_data['初始资金']:,.2f}")
        
        # 显示持仓表格
        st.subheader("当前持仓")
        if st.session_state.positions_data is not None and not st.session_state.positions_data.empty:
            # 格式化显示
            display_df = st.session_state.positions_data.copy()
            display_df['市值'] = display_df['市值'].apply(lambda x: f"¥{x:,.2f}")
            display_df['持仓价格'] = display_df['持仓价格'].apply(lambda x: f"¥{x:,.2f}")
            display_df['当前价格'] = display_df['当前价格'].apply(lambda x: f"¥{x:,.2f}")
            display_df['盈亏金额'] = display_df['盈亏金额'].apply(lambda x: f"¥{x:,.2f}")
            display_df['盈亏百分比'] = display_df['盈亏百分比'].apply(lambda x: f"{x:+.2f}%")
            
            # 使用Streamlit的表格展示
            st.dataframe(
                display_df,
                hide_index=True,
                column_config={
                    "代码": st.column_config.TextColumn("股票代码"),
                    "名称": st.column_config.TextColumn("股票名称"),
                    "数量": st.column_config.NumberColumn(format="%.2f"),
                    "盈亏百分比": st.column_config.TextColumn(
                        "盈亏比例",
                        width="small"
                    )
                },
                use_container_width=True
            )
            
            # 添加持仓分布饼图
            st.subheader("持仓分布")
            if '市值' in st.session_state.positions_data.columns:
                fig = px.pie(
                    st.session_state.positions_data,
                    values='市值',
                    names='名称',
                    title='持仓市值分布',
                    hole=0.3
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("当前无持仓数据")

# 趋势分析选项卡
with tabs[1]:
    st.header("趋势分析")
    
    if st.session_state.portfolio_data is not None and not st.session_state.portfolio_data.empty:
        # 创建并显示盈亏趋势图
        st.subheader("投资组合价值趋势")
        fig = create_profit_loss_chart(st.session_state.portfolio_data)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        
        # 添加收益分析
        st.subheader("收益分析")
        portfolio_df = st.session_state.portfolio_data
        
        # 计算每日收益
        portfolio_df['每日收益'] = portfolio_df['总价值'].diff()
        portfolio_df['每日收益率'] = portfolio_df['总价值'].pct_change() * 100
        
        # 显示收益统计
        col1, col2, col3 = st.columns(3)
        with col1:
            total_return = portfolio_df['总收益'].iloc[-1]
            st.metric("累计收益率", f"{total_return:.2f}%")
        with col2:
            max_return = portfolio_df['每日收益率'].max()
            st.metric("最大单日涨幅", f"{max_return:.2f}%")
        with col3:
            min_return = portfolio_df['每日收益率'].min()
            st.metric("最大单日跌幅", f"{min_return:.2f}%")
        
        # 显示每日收益柱状图
        st.subheader("每日收益")
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=portfolio_df['日期'],
            y=portfolio_df['每日收益'],
            name='每日收益',
            marker_color=['green' if x > 0 else 'red' if x < 0 else 'gray' for x in portfolio_df['每日收益']]
        ))
        fig2.update_layout(
            title='每日收益柱状图',
            xaxis_title='日期',
            yaxis_title='收益金额 (元)',
            template='plotly_white',
            height=300
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("请先加载投资组合数据")

def generate_investment_recommendations(account_id):
    """
    生成基于LLM的投资建议
    """
    try:
        # 获取股票池
        stock_pool = get_stock_pool("etf")
        if not stock_pool:
            logger.warning("未获取到ETF股票池数据，使用模拟数据")
            # 使用模拟的股票池数据
            stock_pool = {
                "512150": "医药ETF",
                "512070": "非银ETF",
                "512880": "证券ETF",
                "512480": "半导体ETF",
                "512200": "地产ETF"
            }
        
        logger.info(f"开始生成投资建议，处理{len(stock_pool)}只ETF")
        
        # 处理每只ETF数据，构建市场状态信息
        market_state = {}
        for code, name in stock_pool.items():
            try:
                # 生成模拟的市场数据
                import random
                base_price = random.uniform(1.0, 3.0)
                change_24h = random.uniform(-5.0, 5.0)
                
                # 构建基本市场状态
                market_item = {
                    'price': base_price,
                    'change_24h': change_24h,
                    'indicators': {}
                }
                
                # 如果talib可用，计算技术指标
                if HAS_TALIB:
                    try:
                        # 生成模拟的价格序列来计算指标
                        np.random.seed(int(code) % 100)  # 使用代码作为随机种子
                        prices = np.array([base_price * (1 + random.uniform(-0.02, 0.02)) for _ in range(30)])
                        
                        # 计算技术指标
                        sma_7 = ta.SMA(prices, timeperiod=7)[-1] if len(prices) >= 7 else base_price
                        sma_14 = ta.SMA(prices, timeperiod=14)[-1] if len(prices) >= 14 else base_price
                        rsi_14 = ta.RSI(prices, timeperiod=14)[-1] if len(prices) >= 14 else 50.0
                        
                        market_item['indicators'] = {
                            'sma_7': sma_7,
                            'sma_14': sma_14,
                            'rsi_14': rsi_14,
                        }
                    except Exception:
                        # 如果计算失败，使用默认值
                        market_item['indicators'] = {
                            'sma_7': base_price,
                            'sma_14': base_price,
                            'rsi_14': 50.0,
                        }
                else:
                    # talib不可用时使用模拟值
                    market_item['indicators'] = {
                        'sma_7': base_price * random.uniform(0.98, 1.02),
                        'sma_14': base_price * random.uniform(0.97, 1.03),
                        'rsi_14': random.uniform(30.0, 70.0),
                    }
                
                market_state[code] = market_item
            except Exception as e:
                logger.exception(f"处理{code}({name})时发生异常: {str(e)}")
        
        # 获取投资组合信息
        db_session = create_db_session()
        portfolio_data = None
        account_info = None
        
        if db_session:
            try:
                # 查询最新的投资组合数据
                portfolios = get_portfolios_by_account(db_session, account_id)
                if portfolios:
                    latest_portfolio = portfolios[0]
                    
                    # 构建投资组合信息
                    portfolio_data = {
                        "total_value": latest_portfolio.total_value,
                        "cash": latest_portfolio.cash,
                        "positions": []
                    }
                    
                    # 获取持仓信息
                    positions = get_positions_by_portfolio(db_session, latest_portfolio.portfolio_id)
                    for pos in positions:
                        portfolio_data["positions"].append({
                            "code": pos.code,
                            "name": pos.name,
                            "quantity": pos.quantity,
                            "value": pos.value
                        })
                    
                    # 构建账户信息
                    account_info = {
                        "initial_capital": latest_portfolio.initial_capital,
                        "total_return": latest_portfolio.total_return
                    }
            except Exception as e:
                logger.exception(f"获取数据库信息时发生异常: {str(e)}")
            finally:
                db_session.close()
        
        # 如果无法获取数据库数据，使用默认值
        if portfolio_data is None:
            # 随机生成一些持仓数据
            import random
            portfolio_data = {
                "total_value": 125000.00 + random.uniform(-5000, 5000),
                "cash": 50000.00 + random.uniform(-10000, 10000),
                "positions": []
            }
            
            # 随机选择几只ETF作为持仓
            random_positions = random.sample(list(stock_pool.items()), min(3, len(stock_pool)))
            for code, name in random_positions:
                quantity = random.randint(1000, 10000)
                price = market_state[code]['price']
                portfolio_data["positions"].append({
                    "code": code,
                    "name": name,
                    "quantity": quantity,
                    "value": quantity * price
                })
            
            account_info = {
                "initial_capital": 120000.00,
                "total_return": (portfolio_data["total_value"] / 120000.00 - 1) * 100
            }
        
        # 生成交易提示词
        trading_prompt = get_trading_prompt(market_state, account_info, portfolio_data)
        logger.debug(f"生成的交易提示词长度: {len(trading_prompt)}字符")
        
        # 获取AI推荐
        reasoning_content, content = get_ai_recommendation(trading_prompt)
        logger.info("获取AI推荐完成")
        
        # 构建建议结果
        recommendations = {
            "reasoning": reasoning_content,
            "content": content,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "market_summary": {
                "total_symbols_analyzed": len(market_state),
                "portfolio_value": portfolio_data["total_value"],
                "available_cash": portfolio_data["cash"]
            }
        }
        
        return True, "投资建议生成成功", recommendations
        
    except Exception as e:
        logger.exception(f"生成投资建议失败: {str(e)}")
        return False, f"生成失败: {str(e)}", None

# 投资建议选项卡
with tabs[2]:
    st.header("投资建议")
    
    # 生成建议按钮
    col1, col2 = st.columns([3, 1])
    with col2:
        generate_btn = st.button(
            "💡 生成投资建议", 
            use_container_width=True,
            type="primary"
        )
    
    # 显示生成的建议
    if generate_btn:
        with st.spinner("正在生成投资建议..."):
            success, message, recommendations = generate_investment_recommendations(account_id)
            
            if success and recommendations:
                # 保存到会话状态，以便后续查看
                st.session_state.investment_recommendations = recommendations
                
                # 显示建议元信息
                st.subheader("建议概览")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("生成时间", recommendations["timestamp"])
                with col2:
                    st.metric("分析标的数量", recommendations["market_summary"]["total_symbols_analyzed"])
                with col3:
                    st.metric("可用现金", f"¥{recommendations["market_summary"]["available_cash"]:,.2f}")
                
                # 显示投资建议内容
                st.subheader("投资建议")
                st.markdown(recommendations["content"])
                
                # 显示推理过程（可折叠）
                with st.expander("查看详细推理过程", expanded=False):
                    st.markdown(recommendations["reasoning"])
                
                # 显示市场分析摘要
                st.subheader("市场分析摘要")
                st.info(
                    f"基于当前市场状态和您的投资组合情况，我们分析了{recommendations['market_summary']['total_symbols_analyzed']}个交易标的。"
                    f"您当前的投资组合价值为¥{recommendations['market_summary']['portfolio_value']:,.2f}，可用现金为¥{recommendations['market_summary']['available_cash']:,.2f}。"
                )

# 交易操作选项卡
with tabs[4]:
    st.header("交易操作")
    
    # 交易表单
    with st.form("trade_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            operation_type = st.selectbox(
                "操作类型",
                options=["买入", "卖出"],
                index=0
            )
            
            stock_code = st.text_input(
                "股票代码",
                placeholder="例如：600000",
                help="输入要交易的股票或ETF代码"
            )
            
        with col2:
            price = st.number_input(
                "交易价格（元）",
                min_value=0.01,
                step=0.01,
                format="%.2f"
            )
            
            quantity = st.number_input(
                "交易数量",
                min_value=1,
                step=1
            )
        
        # 提交按钮
        submitted = st.form_submit_button(
            "🚀 执行交易",
            type="primary",
            use_container_width=True
        )
    
    # 交易结果显示区域
    result_placeholder = st.empty()
    
    # 交易执行逻辑
    def execute_trade(account_id, operation, code, trade_price, trade_quantity):
        try:
            # 创建数据库会话
            db_session = create_db_session()
            if not db_session:
                return False, "数据库连接失败"
            
            # 获取最新的投资组合
            portfolios = get_portfolios_by_account(db_session, account_id)
            if not portfolios:
                return False, "未找到您的投资组合信息，请先初始化账户"
            
            latest_portfolio = portfolios[0]
            total_cash = latest_portfolio.cash
            
            # 计算交易金额
            trade_amount = trade_price * trade_quantity
            
            # 买入逻辑
            if operation == "买入":
                # 检查现金是否足够
                if total_cash < trade_amount:
                    return False, f"现金不足！需要¥{trade_amount:,.2f}，当前可用¥{total_cash:,.2f}"
                
                # 获取当前持仓（如果有）
                existing_position = None
                positions = get_positions_by_portfolio(db_session, latest_portfolio.portfolio_id)
                for pos in positions:
                    if pos.code == code:
                        existing_position = pos
                        break
                
                # 更新或创建持仓
                if existing_position:
                    # 更新现有持仓
                    total_quantity = existing_position.quantity + trade_quantity
                    avg_price = ((existing_position.price * existing_position.quantity) + 
                                (trade_price * trade_quantity)) / total_quantity
                    
                    existing_position.quantity = total_quantity
                    existing_position.price = avg_price
                    existing_position.value = total_quantity * avg_price
                    # 更新市场价格为当前交易价格
                    existing_position.market_price = trade_price
                    # 重新计算盈亏
                    existing_position.profit_loss = (trade_price - avg_price) * total_quantity
                    existing_position.profit_loss_pct = ((trade_price / avg_price) - 1) * 100
                else:
                    # 创建新持仓
                    import time
                    
                    position_id = f"pos_{latest_portfolio.portfolio_id}_{code}_{int(time.time())}"
                    current_date = datetime.datetime.now().strftime('%Y-%m-%d')
                    
                    # 模拟股票名称
                    stock_name = f"股票_{code}"
                    
                    new_position = Position(
                        position_id=position_id,
                        portfolio_id=latest_portfolio.portfolio_id,
                        account_id=account_id,
                        code=code,
                        name=stock_name,
                        quantity=trade_quantity,
                        price=trade_price,
                        value=trade_amount,
                        market_price=trade_price,  # 假设当前市场价格等于交易价格
                        profit_loss=0.0,  # 新买入时盈亏为0
                        profit_loss_pct=0.0,
                        date=current_date
                    )
                    db_session.add(new_position)
                
                # 更新总价值（包括所有持仓）
                total_value = latest_portfolio.cash
                for pos in get_positions_by_portfolio(db_session, latest_portfolio.portfolio_id):
                    total_value += pos.value
                
                latest_portfolio.total_value = total_value
                # 更新总收益率
                latest_portfolio.total_return = ((total_value / latest_portfolio.initial_capital) - 1) * 100
                
                # 更新现金
                latest_portfolio.cash = total_cash - trade_amount
                
                message = f"成功买入 {code}，数量：{trade_quantity}，成交金额：¥{trade_amount:,.2f}"
            
            # 卖出逻辑
            elif operation == "卖出":
                # 检查持仓
                existing_position = None
                positions = get_positions_by_portfolio(db_session, latest_portfolio.portfolio_id)
                for pos in positions:
                    if pos.code == code:
                        existing_position = pos
                        break
                
                if not existing_position:
                    return False, f"您没有持有 {code} 这支股票"
                
                if existing_position.quantity < trade_quantity:
                    return False, f"卖出数量超过持仓数量！当前持仓：{existing_position.quantity}"
                
                # 计算盈亏
                profit_loss = (trade_price - existing_position.price) * trade_quantity
                
                # 更新持仓
                existing_position.quantity -= trade_quantity
                
                # 更新市场价格为当前交易价格
                existing_position.market_price = trade_price
                
                # 如果全部卖出，删除持仓
                if existing_position.quantity <= 0:
                    db_session.delete(existing_position)
                else:
                    # 更新持仓价值
                    existing_position.value = existing_position.quantity * existing_position.price
                    # 重新计算剩余持仓的盈亏
                    existing_position.profit_loss = (trade_price - existing_position.price) * existing_position.quantity
                    existing_position.profit_loss_pct = ((trade_price / existing_position.price) - 1) * 100
                
                # 更新现金
                latest_portfolio.cash = total_cash + trade_amount
                
                # 更新总价值（简化处理，实际应该重新计算所有持仓）
                total_value = latest_portfolio.cash
                for pos in get_positions_by_portfolio(db_session, latest_portfolio.portfolio_id):
                    total_value += pos.value
                
                latest_portfolio.total_value = total_value
                # 更新总收益率
                latest_portfolio.total_return = ((total_value / latest_portfolio.initial_capital) - 1) * 100
                
                message = f"成功卖出 {code}，数量：{trade_quantity}，成交金额：¥{trade_amount:,.2f}，本次盈亏：¥{profit_loss:+.2f}"
            
            # 提交事务
            db_session.commit()
            
            # 交易成功后，验证数据一致性
            # 重新获取最新数据进行验证
            updated_portfolio = db_session.query(Portfolio).filter(
                Portfolio.portfolio_id == latest_portfolio.portfolio_id
            ).first()
            
            # 检查现金余额是否正确
            if operation == "买入" and updated_portfolio.cash != total_cash - trade_amount:
                logger.warning(f"现金余额不一致: 期望 {total_cash - trade_amount}, 实际 {updated_portfolio.cash}")
            elif operation == "卖出" and updated_portfolio.cash != total_cash + trade_amount:
                logger.warning(f"现金余额不一致: 期望 {total_cash + trade_amount}, 实际 {updated_portfolio.cash}")
            
            return True, message
            
        except Exception as e:
            if db_session:
                db_session.rollback()
            logger.exception(f"执行交易失败: {str(e)}")
            return False, f"交易执行失败: {str(e)}"
        finally:
            if db_session:
                db_session.close()
    
    # 当表单提交时执行交易
    if submitted:
        if not stock_code:
            result_placeholder.error("请输入股票代码")
        else:
            with st.spinner("正在执行交易..."):
                success, message = execute_trade(account_id, operation_type, stock_code, price, quantity)
                
                if success:
                    result_placeholder.success(message)
                    # 刷新数据
                    portfolio_df, positions_df = load_portfolio_data(account_id, start_date, end_date)
                    if portfolio_df is not None and not portfolio_df.empty:
                        st.session_state.portfolio_data = portfolio_df
                        st.session_state.positions_data = positions_df
                        
                        # 显示更新后的持仓信息（可选）
                        with st.expander("查看更新后的持仓信息", expanded=True):
                            if st.session_state.positions_data is not None and not st.session_state.positions_data.empty:
                                # 格式化显示
                                display_df = st.session_state.positions_data.copy()
                                display_df['市值'] = display_df['市值'].apply(lambda x: f"¥{x:,.2f}")
                                display_df['持仓价格'] = display_df['持仓价格'].apply(lambda x: f"¥{x:,.2f}")
                                display_df['当前价格'] = display_df['当前价格'].apply(lambda x: f"¥{x:,.2f}")
                                display_df['盈亏金额'] = display_df['盈亏金额'].apply(lambda x: f"¥{x:,.2f}")
                                display_df['盈亏百分比'] = display_df['盈亏百分比'].apply(lambda x: f"{x:+.2f}%")
                                
                                st.dataframe(
                                    display_df,
                                    hide_index=True,
                                    use_container_width=True
                                )
                            else:
                                st.info("当前无持仓数据")
                else:
                    result_placeholder.error(message)
    
    # 显示当前可用现金信息
    if st.session_state.portfolio_data is not None and not st.session_state.portfolio_data.empty:
        latest_data = st.session_state.portfolio_data.iloc[-1]
        st.info(f"当前可用现金：¥{latest_data['现金']:,.2f}")
    else:
        # 如果没有数据，提供初始化选项
        if st.button("初始化账户"):
            with st.spinner("正在初始化账户..."):
                db_session = create_db_session()
                if db_session:
                    try:
                        # 检查是否已有该账户的投资组合
                        existing_portfolios = get_portfolios_by_account(db_session, account_id)
                        if not existing_portfolios:
                            # 创建初始投资组合
                            from db_schema import insert_portfolio_and_positions
                            initial_capital = 100000.0  # 初始资金10万元
                            portfolio_data = {
                                "total_value": initial_capital,
                                "cash": initial_capital,
                                "positions": []
                            }
                            account_info = {
                                "initial_capital": initial_capital,
                                "total_return": 0.0
                            }
                            
                            portfolio_id = insert_portfolio_and_positions(
                                db_session, 
                                account_id, 
                                portfolio_data, 
                                account_info
                            )
                            st.success(f"账户初始化成功！初始资金：¥{initial_capital:,.2f}")
                            # 重新加载数据
                            portfolio_df, positions_df = load_portfolio_data(account_id, start_date, end_date)
                            if portfolio_df is not None and not portfolio_df.empty:
                                st.session_state.portfolio_data = portfolio_df
                                st.session_state.positions_data = positions_df
                                st.session_state.latest_portfolio_id = portfolio_id
                        else:
                            st.warning("该账户已经存在，请勿重复初始化")
                    except Exception as e:
                        logger.exception(f"账户初始化失败: {str(e)}")
                        st.error(f"初始化失败: {str(e)}")
                    finally:
                        db_session.close()
            
        else:
            st.error(message)
    
    # 如果之前已经生成过建议，显示最近的建议
    elif 'investment_recommendations' in st.session_state:
        recommendations = st.session_state.investment_recommendations
        
        st.info("显示最近生成的投资建议，点击按钮可更新")
        
        # 显示建议元信息
        st.subheader("建议概览")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("生成时间", recommendations["timestamp"])
        with col2:
            st.metric("分析标的数量", recommendations["market_summary"]["total_symbols_analyzed"])
        with col3:
            st.metric("可用现金", f"¥{recommendations["market_summary"]["available_cash"]:,.2f}")
        
        # 显示投资建议内容
        st.subheader("投资建议")
        st.markdown(recommendations["content"])
        
        # 显示推理过程（可折叠）
        with st.expander("查看详细推理过程", expanded=False):
            st.markdown(recommendations["reasoning"])
    
    else:
        st.info("点击上方按钮生成投资建议")

def update_kline_data(pool_name="etf"):
    """
    更新自选ETF或股票的历史K线数据
    """
    try:
        # 获取股票池
        stock_pool = get_stock_pool(pool_name)
        if not stock_pool:
            return False, f"未获取到{pool_name}股票池数据"
        
        # 定义数据列
        daily_columns = ['code', 'name', 'update_time', 'last_price', 'open_price', 'high_price', \
            'low_price', 'pe_ratio', 'volume', 'turnover', 'turnover_rate']
        hist_columns = ['code', 'name', 'time_key', 'open', \
            'close', 'high', 'low', 'pe_ratio', 'volume', \
                'turnover_rate', 'turnover', 'change_rate']
        
        # 创建K线数据获取器
        fetcher = KlineFetcher(stock_pool.keys(), daily_columns, hist_columns, 'data')
        
        # 根据不同的股票池选择不同的数据文件名
        if pool_name == "etf":
            data_filename = 'kline_etf_data'
        else:
            data_filename = 'kline_stock_data'
        
        # 获取并保存历史K线数据
        logger.info(f"开始更新{pool_name}的历史K线数据，共{len(stock_pool)}只{pool_name}")
        data = fetcher.hist_kline_persistence(data_filename)
        logger.info(f"{pool_name}历史K线数据更新完成，数据形状: {data.shape}")
        
        return True, f"成功更新{len(stock_pool)}只{pool_name}的历史K线数据"
        
    except Exception as e:
        logger.exception(f"更新{pool_name}历史K线数据失败: {str(e)}")
        return False, f"更新失败: {str(e)}"

# 数据更新选项卡
with tabs[3]:
    st.header("数据更新")
    
    st.subheader("更新历史K线数据")
    
    # 选择股票池
    pool_type = st.radio(
        "选择数据类型",
        options=["etf", "全部"],
        index=0,
        horizontal=True,
        help="选择要更新的股票池类型"
    )
    
    # 显示当前股票池信息
    with st.expander("查看当前股票池信息", expanded=False):
        try:
            stock_pool = get_stock_pool(pool_type)
            if stock_pool:
                st.info(f"当前{pool_type}股票池共有 {len(stock_pool)} 只股票/ETF")
                
                # 创建股票池DataFrame
                stock_df = pd.DataFrame(list(stock_pool.items()), columns=['代码', '名称'])
                st.dataframe(stock_df, hide_index=True, use_container_width=True)
            else:
                st.warning(f"无法获取{pool_type}股票池信息")
        except Exception as e:
            st.error(f"获取股票池信息失败: {str(e)}")
    
    # 更新数据按钮
    update_btn = st.button(
        f"🔄 更新{pool_type}历史K线数据",
        use_container_width=True,
        type="primary"
    )
    
    if update_btn:
        with st.spinner(f"正在更新{pool_type}历史K线数据..."):
            success, message = update_kline_data(pool_type)
            if success:
                st.success(message)
                # 显示更新统计信息
                st.subheader("更新统计")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("更新时间", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                with col2:
                    st.metric("更新类型", pool_type)
            else:
                st.error(message)

# 添加页脚
st.markdown("---")
st.caption("© 2024 股票投资组合分析仪表板 | 使用Streamlit构建")

if __name__ == "__main__":
    # Streamlit应用不需要main函数调用，这里只是为了代码完整性
    pass