import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import logging

# 配置日志
logger = logging.getLogger(__name__)

def show_trend_analysis():
    """
    显示趋势分析页面
    """
    st.header("📈 趋势分析")
    
    # 从会话状态获取数据
    portfolio_data = st.session_state.get('portfolio_data')
    
    # 检查数据是否存在
    if portfolio_data is None or portfolio_data.empty:
        st.warning("未找到投资组合数据，请先在投资组合概览页面加载数据。")
        return
    
    # 创建趋势分析选项卡
    trend_tabs = st.tabs(["价值趋势", "收益分析", "风险评估", "对比分析"])
    
    # 价值趋势选项卡
    with trend_tabs[0]:
        st.subheader("📊 投资组合价值趋势")
        
        # 创建价值趋势图
        fig = go.Figure()
        
        # 添加总价值曲线
        fig.add_trace(go.Scatter(
            x=portfolio_data['日期'],
            y=portfolio_data['总价值'],
            mode='lines+markers',
            name='总价值',
            line=dict(color='#1f77b4', width=2)
        ))
        
        # 添加初始资金参考线
        initial_capital = portfolio_data['初始资金'].iloc[0]
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
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 价值变化统计
        col1, col2, col3 = st.columns(3)
        col1.metric("最大值", f"¥{portfolio_data['总价值'].max():,.2f}")
        col2.metric("最小值", f"¥{portfolio_data['总价值'].min():,.2f}")
        col3.metric("平均值", f"¥{portfolio_data['总价值'].mean():,.2f}")
    
    # 收益分析选项卡
    with trend_tabs[1]:
        st.subheader("💰 收益分析")
        
        # 计算每日收益率
        daily_returns = portfolio_data.copy()
        daily_returns['每日收益率'] = daily_returns['总价值'].pct_change() * 100
        daily_returns['累计收益'] = (1 + daily_returns['总价值'].pct_change()).cumprod() - 1
        
        # 创建收益趋势图
        fig = go.Figure()
        
        # 添加累计收益曲线
        fig.add_trace(go.Scatter(
            x=daily_returns['日期'],
            y=daily_returns['累计收益'] * 100,  # 转换为百分比
            mode='lines',
            name='累计收益率(%)',
            line=dict(color='#2ca02c', width=2)
        ))
        
        # 添加零线
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        
        # 更新布局
        fig.update_layout(
            title='累计收益趋势',
            xaxis_title='日期',
            yaxis_title='累计收益率 (%)',
            template='plotly_white',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 每日收益率分布图
        st.subheader("📊 每日收益率分布")
        
        # 过滤掉NaN值
        valid_returns = daily_returns['每日收益率'].dropna()
        
        fig = go.Figure(data=[go.Histogram(
            x=valid_returns,
            nbinsx=30,
            marker_color='#1f77b4',
            opacity=0.7
        )])
        
        fig.update_layout(
            title='每日收益率分布',
            xaxis_title='每日收益率 (%)',
            yaxis_title='频率',
            template='plotly_white',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 收益统计
        st.subheader("📈 收益统计")
        
        # 初始化变量以避免后面计算时引用未定义的变量
        annualized_return = 0
        total_return = 0
        
        try:
            total_return = (portfolio_data['总价值'].iloc[-1] / portfolio_data['初始资金'].iloc[0] - 1) * 100
            
            # 检查日期数据有效性
            if len(portfolio_data) >= 2:
                days_diff = (portfolio_data['日期'].iloc[-1] - portfolio_data['日期'].iloc[0]).days
                # 避免除以零的情况
                if days_diff > 0:
                    annualized_return = ((1 + total_return/100) ** (365 / days_diff) - 1) * 100
                else:
                    annualized_return = 0  # 同一天，无法计算年化
            else:
                annualized_return = 0  # 数据点不足
                
            max_daily_return = valid_returns.max() if not valid_returns.empty else 0
            min_daily_return = valid_returns.min() if not valid_returns.empty else 0
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("总收益率", f"{total_return:.2f}%")
            col2.metric("年化收益率", f"{annualized_return:.2f}%")
            col3.metric("最大单日收益", f"{max_daily_return:.2f}%")
            col4.metric("最大单日亏损", f"{min_daily_return:.2f}%")
        except Exception as e:
            logger.error(f"计算收益统计失败: {str(e)}")
            st.error("收益统计计算失败，请检查数据完整性")
    
    # 风险评估选项卡
    with trend_tabs[2]:
        st.subheader("⚠️ 风险评估")
        
        # 计算风险指标
        daily_returns = portfolio_data['总价值'].pct_change().dropna()
        volatility = daily_returns.std() * np.sqrt(252) * 100  # 年化波动率
        
        # 计算最大回撤
        portfolio_value = portfolio_data['总价值'].values
        running_max = np.maximum.accumulate(portfolio_value)
        drawdown = (portfolio_value - running_max) / running_max * 100
        max_drawdown = drawdown.min() if drawdown.min() != 0 else -0.00001
        
        # 创建最大回撤图表
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=portfolio_data['日期'],
            y=drawdown,
            mode='lines',
            name='回撤(%)',
            fill='tozeroy',
            line=dict(color='#d62728'),
            fillcolor='rgba(214, 39, 40, 0.2)'
        ))
        
        fig.update_layout(
            title='投资组合最大回撤',
            xaxis_title='日期',
            yaxis_title='回撤 (%)',
            template='plotly_white',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 风险指标卡片
        col1, col2 = st.columns(2)
        col1.metric("年化波动率", f"{volatility:.2f}%")
        col2.metric("最大回撤", f"{max_drawdown:.2f}%")
        
        # 风险调整收益
        if volatility > 0:
            sharpe_ratio = (annualized_return - 4) / volatility  # 假设无风险利率为4%
        else:
            sharpe_ratio = 0
            
        col1, col2 = st.columns(2)
        col1.metric("夏普比率", f"{sharpe_ratio:.2f}")
        col2.metric("风险调整收益", f"{total_return / abs(max_drawdown):.2f}")
    
    # 对比分析选项卡
    with trend_tabs[3]:
        st.subheader("📊 对比分析")
        
        # 这里可以添加与基准指数的对比分析
        # 暂时显示模拟数据或提示信息
        st.info("与基准指数的对比分析功能正在开发中...")
        
        # 可以添加一些假设的对比数据
        st.subheader("假设与上证指数对比")
        
        # 生成模拟的基准指数数据
        dates = portfolio_data['日期']
        # 假设基准指数年化收益率为5%
        days = (dates.iloc[-1] - dates.iloc[0]).days
        benchmark_values = [initial_capital * (1 + 0.05 * i / 365) for i in range(days + 1)]
        
        # 创建对比图表
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=portfolio_data['总价值'],
            mode='lines',
            name='投资组合',
            line=dict(color='#1f77b4', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=benchmark_values[:len(dates)],
            mode='lines',
            name='基准指数 (5%年化)',
            line=dict(color='#ff7f0e', width=2, dash='dash')
        ))
        
        fig.update_layout(
            title='投资组合 vs 基准指数',
            xaxis_title='日期',
            yaxis_title='累计价值',
            template='plotly_white',
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)