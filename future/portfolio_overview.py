import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import logging
from sqlalchemy import func

# 配置日志
logger = logging.getLogger(__name__)

def show_portfolio_overview(account_id, start_date, end_date):
    """
    显示投资组合概览页面
    """
    st.header("📊 投资组合概览")
    
    # 从会话状态获取数据
    portfolio_data = st.session_state.get('portfolio_data')
    positions_data = st.session_state.get('positions_data')
    
    # 如果没有数据，尝试加载
    if portfolio_data is None or positions_data is None:
        with st.spinner("加载投资组合数据..."):
            # 调用从主页面传入的load_portfolio_data函数
            portfolio_data, positions_data = st.session_state.load_portfolio_data(account_id, start_date, end_date)
            
            # 更新会话状态
            st.session_state.portfolio_data = portfolio_data
            st.session_state.positions_data = positions_data
    
    # 刷新按钮
    if st.button("🔄 刷新数据"):
        with st.spinner("刷新投资组合数据..."):
            # 重新加载数据
            portfolio_data, positions_data = st.session_state.load_portfolio_data(account_id, start_date, end_date)
            
            # 更新会话状态
            st.session_state.portfolio_data = portfolio_data
            st.session_state.positions_data = positions_data
    
    # 检查数据是否加载成功
    if portfolio_data is None or portfolio_data.empty:
        st.warning("未找到投资组合数据，请检查账户ID和日期范围。")
        return
    
    # 获取最新的投资组合数据
    latest_portfolio = portfolio_data.iloc[-1]
    
    # 计算关键指标
    total_value = latest_portfolio['总价值']
    cash = latest_portfolio['现金']
    initial_capital = latest_portfolio['初始资金']
    total_return = latest_portfolio['总收益']
    total_return_pct = (total_return / initial_capital) * 100 if initial_capital > 0 else 0
    
    # 资产概览卡片
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("总价值", f"¥{total_value:,.2f}")
    col2.metric("可用现金", f"¥{cash:,.2f}")
    col3.metric("总收益", f"¥{total_return:,.2f}", f"{total_return_pct:.2f}%")
    col3.metric("总资产比例", f"{(total_value / initial_capital * 100):.2f}%")
    
    # 持仓分布饼图
    st.subheader("📈 持仓分布")
    
    # 计算股票持仓价值和现金比例
    if positions_data is not None and not positions_data.empty:
        stock_values = positions_data['市值'].sum()
    else:
        stock_values = 0
    
    # 创建持仓分布数据
    labels = ['现金', '股票持仓']
    values = [cash, stock_values]
    colors = ['#1f77b4', '#2ca02c']
    
    # 创建饼图
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=.3,
        marker_colors=colors,
        textinfo='label+percent',
        insidetextorientation='radial'
    )])
    
    fig.update_layout(
        title='资产配置',
        height=300
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 如果有持仓数据，显示持仓详情
    if positions_data is not None and not positions_data.empty:
        st.subheader("📋 持仓详情")
        
        # 计算每个持仓的占比
        positions_data['占比'] = (positions_data['市值'] / stock_values * 100).round(2)
        
        # 按市值降序排序
        positions_data = positions_data.sort_values('市值', ascending=False)
        
        # 设置颜色样式
        def highlight_profit(row):
            if row['盈亏百分比'] > 0:
                return ['background-color: rgba(0, 255, 0, 0.1)'] * len(row)
            elif row['盈亏百分比'] < 0:
                return ['background-color: rgba(255, 0, 0, 0.1)'] * len(row)
            else:
                return [''] * len(row)
        
        # 格式化显示数据
        styled_positions = positions_data.style.apply(highlight_profit, axis=1).format({
            '数量': '{:.0f}',
            '持仓价格': '¥{:.2f}',
            '当前价格': '¥{:.2f}',
            '市值': '¥{:,.2f}',
            '盈亏金额': '¥{:,.2f}',
            '盈亏百分比': '{:.2f}%',
            '占比': '{:.2f}%'
        })
        
        st.dataframe(
            styled_positions,
            use_container_width=True,
            hide_index=True
        )
        
        # 持仓股票排名图表（按市值）
        st.subheader("🏆 持仓排名")
        
        # 准备排名数据
        top_stocks = positions_data.nlargest(10, '市值')
        
        # 创建排名柱状图
        fig = go.Figure(data=[go.Bar(
            x=top_stocks['名称'],
            y=top_stocks['市值'],
            marker_color=top_stocks['盈亏百分比'].apply(lambda x: '#2ca02c' if x > 0 else '#d62728')
        )])
        
        fig.update_layout(
            title='持仓市值排名（前10）',
            xaxis_title='股票名称',
            yaxis_title='市值（元）',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("当前没有持仓记录。")
    
    # 显示近期交易活动
    st.subheader("📝 近期交易活动")
    
    # 这里可以添加交易历史记录的显示逻辑
    # 暂时显示模拟数据或提示信息
    st.info("交易历史记录功能正在开发中...")