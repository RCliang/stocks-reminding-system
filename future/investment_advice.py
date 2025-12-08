import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import logging
import time
from utils import get_ai_recommendation
from prompts import get_trading_prompt
from db_tools import DatabaseTools
# 配置日志
logger = logging.getLogger(__name__)

def generate_investment_recommendations(account_id):
    """
    生成投资建议
    """
    db_manager = DatabaseTools()
    try:
        logger.info(f"为账户 {account_id} 生成投资建议")
        
        # 这里应该调用AI推荐系统
        # 查询账户持仓情况
        holdings = db_manager.get_positions_by_account(account_id) if db_manager else []
        st.info(holdings)
        # 构建包含持仓信息的提示
        prompt = get_trading_prompt(account_id, holdings)
        # 暂时返回模拟的建议结果
        recommendations = get_ai_recommendation(get_trading_prompt(account_id))
        
        logger.info(f"成功生成 {len(recommendations)} 条投资建议")
        return recommendations
    except Exception as e:
        logger.exception(f"生成投资建议失败: {str(e)}")
        return []

def show_investment_advice(account_id):
    """
    显示投资建议页面
    """
    st.header("💡 投资建议")
    
    # 投资建议生成部分
    st.subheader("🔍 AI智能投资建议")
    
    # 添加生成建议按钮
    if st.button("🚀 生成投资建议", key="generate_advice"):
        with st.spinner("AI正在分析市场数据和您的投资组合..."):
            # 模拟处理时间
            time.sleep(2)
            
            # 调用建议生成函数
            recommendations = generate_investment_recommendations(account_id)
            
            # 保存建议到会话状态
            st.session_state.investment_recommendations = recommendations
            
            st.success(f"✅ 成功生成 {len(recommendations)} 条投资建议！")
    
    # 显示投资建议
    if 'investment_recommendations' in st.session_state:
        recommendations = st.session_state.investment_recommendations
        
        if recommendations:
            st.subheader("📋 投资建议详情")
            
            # 按建议类型分组显示
            recommendation_types = ['买入建议', '持有建议', '卖出建议', '行业配置', '风险提示']
            
            for rec_type in recommendation_types:
                recs_by_type = [r for r in recommendations if r['类型'] == rec_type]
                if recs_by_type:
                    # 创建折叠面板显示该类型的建议
                    with st.expander(f"{rec_type} ({len(recs_by_type)}条)", expanded=True):
                        # 为每条建议创建卡片
                        for rec in recs_by_type:
                            # 根据建议类型设置不同的颜色
                            if rec_type == '买入建议':
                                color = 'rgba(46, 204, 113, 0.1)'
                                border_color = '#2ecc71'
                            elif rec_type == '卖出建议':
                                color = 'rgba(231, 76, 60, 0.1)'
                                border_color = '#e74c3c'
                            elif rec_type == '持有建议':
                                color = 'rgba(52, 152, 219, 0.1)'
                                border_color = '#3498db'
                            elif rec_type == '行业配置':
                                color = 'rgba(155, 89, 182, 0.1)'
                                border_color = '#9b59b6'
                            else:  # 风险提示
                                color = 'rgba(241, 196, 15, 0.1)'
                                border_color = '#f1c40f'
                            
                            # 使用HTML和CSS创建样式化的卡片
                            st.markdown(f"""
                            <div style="background-color: {color}; border-left: 4px solid {border_color}; padding: 12px; margin-bottom: 10px; border-radius: 4px;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <h4 style="margin: 0; color: #333;">{rec['名称']} ({rec['代码']})</h4>
                                    <span style="background-color: {border_color}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px;">{rec['置信度']}</span>
                                </div>
                                <p style="margin: 8px 0; color: #666;">{rec['理由']}</p>
                                {f'<p style="margin: 0; color: #2c3e50; font-weight: bold;">目标价: {rec["目标价"]}</p>' if rec['目标价'] != 'N/A' else ''}
                            </div>
                            """, unsafe_allow_html=True)
            
            # 添加建议总结
            st.subheader("📊 建议总结")
            
            # 统计各类型建议数量
            rec_counts = {}
            for rec in recommendations:
                rec_counts[rec['类型']] = rec_counts.get(rec['类型'], 0) + 1
            
            # 创建建议分布图表
            if rec_counts:
                fig = go.Figure(data=[go.Pie(
                    labels=list(rec_counts.keys()),
                    values=list(rec_counts.values()),
                    hole=.3,
                    marker_colors=['#2ecc71', '#3498db', '#e74c3c', '#9b59b6', '#f1c40f'],
                    textinfo='label+percent',
                    insidetextorientation='radial'
                )])
                
                fig.update_layout(
                    title='投资建议分布',
                    height=300
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            # 投资策略建议
            st.subheader("🎯 投资策略建议")
            
            # 根据建议生成策略
            buy_count = rec_counts.get('买入建议', 0)
            sell_count = rec_counts.get('卖出建议', 0)
            
            if buy_count > sell_count:
                strategy = """
                - **积极配置策略**: 市场机会大于风险，建议增加权益资产配置
                - **关注重点行业**: 优先考虑消费、科技等成长性行业
                - **分批建仓**: 建议采用定投或分批买入策略，降低时点风险
                - **止盈止损**: 设置合理的止盈止损点位，控制单个股票仓位
                """
            elif sell_count > buy_count:
                strategy = """
                - **防御策略**: 市场风险上升，建议降低权益资产配置比例
                - **保留现金**: 增加现金持有比例，等待更好的入场时机
                - **分散投资**: 避免过度集中在单一行业或个股
                - **关注防御性板块**: 考虑配置医药、公用事业等防御性板块
                """
            else:
                strategy = """
                - **均衡配置策略**: 市场机会与风险并存，建议维持均衡配置
                - **结构调整**: 对持仓进行结构性调整，优化投资组合
                - **关注估值**: 优先选择估值合理、业绩稳定的优质个股
                - **灵活应对**: 根据市场变化及时调整仓位和配置
                """
            
            st.markdown(strategy)
            
            # 风险提示
            st.subheader("⚠️ 风险提示")
            st.warning("""
            - 以上建议仅供参考，不构成任何投资建议或投资邀约
            - 投资有风险，入市需谨慎，实际投资决策请结合自身风险承受能力
            - 市场行情瞬息万变，建议定期更新投资建议
            - 如有疑问，请咨询专业投资顾问
            """)
        else:
            st.info("未生成投资建议，请点击上方按钮生成。")
    else:
        st.info("点击上方按钮生成AI智能投资建议。")
    
    # 市场洞察部分
    st.subheader("📰 市场洞察")
    
    # 创建市场洞察选项卡
    market_tabs = st.tabs(["市场热点", "行业动态", "宏观经济", "资金流向"])
    
    with market_tabs[0]:
        st.markdown("""
        ### 当前市场热点
        - **科技创新**: AI、半导体、新能源等科技领域持续受到关注
        - **消费复苏**: 随着经济逐步恢复，消费板块迎来机会
        - **绿色转型**: 环保、碳中和相关产业链表现活跃
        - **数字经济**: 数字中国建设推动相关板块估值提升
        """)
    
    with market_tabs[1]:
        st.markdown("""
        ### 行业动态
        - **新能源**: 光伏、风电等新能源板块持续高速增长
        - **医药生物**: 创新药、医疗器械等细分领域景气度高
        - **金融服务**: 银行估值处于历史低位，具有配置价值
        - **TMT**: 计算机、通信、传媒等科技板块表现活跃
        """)
    
    with market_tabs[2]:
        st.markdown("""
        ### 宏观经济分析
        - **经济复苏**: 国内经济逐步恢复，GDP增速稳步回升
        - **政策支持**: 稳增长政策持续发力，财政货币政策协同
        - **通胀预期**: 温和通胀环境有利于企业盈利修复
        - **外部环境**: 全球经济面临不确定性，需关注美联储政策变化
        """)
    
    with market_tabs[3]:
        st.markdown("""
        ### 资金流向
        - **北向资金**: 近期北向资金呈现净流入态势
        - **机构动向**: 公募基金重点配置科技成长和消费板块
        - **融资融券**: 市场融资余额稳步上升，杠杆水平合理
        - **板块轮动**: 资金在不同板块间轮动，寻找确定性机会
        """)