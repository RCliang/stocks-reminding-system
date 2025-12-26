from typing import Any
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import logging
import json
import numpy as np
import json_repair
from datetime import datetime, timedelta
import time
from outlines import Template
from pathlib import Path
from utils import get_ai_recommendation, search_stock_info
from db_tools import DatabaseTools
from fetch_kline_daily import get_market_snapshot
from utils import StockAna


logger = logging.getLogger(__name__)

def get_portfolio_info(account_id):
    """
    获取账户持仓信息
    """
    db_manager = DatabaseTools()
    portfolios = db_manager.get_portfolios_by_account(account_id) if db_manager else []
    # 构建包含持仓信息的提示
    account_info = dict[Any, Any]()
    account_info['initial_capital'] = portfolios[0]['initial_capital']
    account_info['total_return'] = portfolios[0]['total_return'] / account_info['initial_capital']
    positions = db_manager.get_positions_by_portfolio(portfolios[0]['portfolio_id'])
    portfolio = dict[Any, Any]()
    portfolio['total_value'] = portfolios[0]['total_value']
    portfolio['cash'] = portfolios[0]['cash']
    portfolio['positions'] = []
    for item in positions:
        portfolio['positions'].append({
            'name': item['name'],
            'code': item['code'],
            'price': item['price'],
            'quantity': item['quantity'],
            'value': get_market_snapshot(item['code']),
        })
    return account_info, portfolio

def generate_technical_indicator_chart(indicator):
    COLOR_BULL = 'rgba(38,166,154,0.9)'  # #26a69a
    COLOR_BEAR = 'rgba(239,83,80,0.9)'   # #ef5350
    COLOR_BLUE = 'rgba(33,150,243,0.9)'  # #2196f3
    COLOR_GREEN = 'rgba(76,175,80,0.9)'  # #4caf50
    COLOR_RED = 'rgba(244,67,54,0.9)'    # #f44336
    COLOR_PURPLE = 'rgba(156,39,176,0.9)' # #9c27b0
    COLOR_ORANGE = 'rgba(255,152,0,0.9)' # #ff9800
    
    # 创建DataFrame存储所有数据
    dates = pd.date_range(end='2023-12-25', periods=len(indicator['ema_5'])).astype(str).tolist()
    df = pd.DataFrame({
        'time': dates,
        'ema_5': [round(float(v), 2) for v in indicator['ema_5']],
        'ema_10': [round(float(v), 2) for v in indicator['ema_10']],
        'ema_20': [round(float(v), 2) for v in indicator['ema_20']],
        'macd': [round(float(v), 2) for v in indicator['macd']],
        'macdsignal': [round(float(v), 2) for v in indicator['macdsignal']],
        'macdhist': [round(float(v), 2) for v in indicator['macdhist']],
        'slowk': [round(float(v), 2) for v in indicator['slowk']],
        'slowd': [round(float(v), 2) for v in indicator['slowd']],
        'slowj': [round(float(v), 2) for v in indicator['slowj']],
        'rsi_14': [round(float(v), 2) for v in indicator['rsi_14']],
        'volume': [round(float(v), 2) for v in indicator['volume']]
    })
    
    # 1. EMA图表配置
    chartEMAOptions = {
        # "width": 800,
        "height": 200,
        "layout": {
            "background": {
                "type": "solid",
                "color": 'white'
            },
            "textColor": "black"
        },
        "grid": {
            "vertLines": {
                "color": "rgba(197, 203, 206, 0.5)"
            },
            "horzLines": {
                "color": "rgba(197, 203, 206, 0.5)"
            }
        },
        "timeScale": {
            "visible": True,
            "borderColor": "rgba(197, 203, 206, 0.8)",
            "barSpacing": 15
        },
        "watermark": {
            "visible": True,
            "fontSize": 18,
            "horzAlign": 'left',
            "vertAlign": 'top',
            "color": 'rgba(171, 71, 188, 0.7)',
            "text": 'EMA指标',
        }
    }
    
    # 2. MACD图表配置
    chartMACDOptions = {
        # "width": 800,
        "height": 200,
        "layout": {
            "background": {
                "type": "solid",
                "color": 'white'
            },
            "textColor": "black"
        },
        "grid": {
            "vertLines": {
                "color": "rgba(197, 203, 206, 0.5)"
            },
            "horzLines": {
                "color": "rgba(197, 203, 206, 0.5)"
            }
        },
        "timeScale": {
            "visible": False,
            "borderColor": "rgba(197, 203, 206, 0.8)"
        },
        "watermark": {
            "visible": True,
            "fontSize": 18,
            "horzAlign": 'left',
            "vertAlign": 'top',
            "color": 'rgba(171, 71, 188, 0.7)',
            "text": 'MACD指标',
        }
    }
    
    # 3. KDJ图表配置
    chartKDJOptions = {
        # "width": 800,
        "height": 200,
        "layout": {
            "background": {
                "type": "solid",
                "color": 'white'
            },
            "textColor": "black"
        },
        "grid": {
            "vertLines": {
                "color": "rgba(197, 203, 206, 0.5)"
            },
            "horzLines": {
                "color": "rgba(197, 203, 206, 0.5)"
            }
        },
        "timeScale": {
            "visible": False,
            "borderColor": "rgba(197, 203, 206, 0.8)"
        },
        "watermark": {
            "visible": True,
            "fontSize": 18,
            "horzAlign": 'left',
            "vertAlign": 'top',
            "color": 'rgba(171, 71, 188, 0.7)',
            "text": 'KDJ指标',
        }
    }
    
    # 4. RSI图表配置
    chartRSIOptions = {
        # "width": 800,
        "height": 200,
        "layout": {
            "background": {
                "type": "solid",
                "color": 'white'
            },
            "textColor": "black"
        },
        "grid": {
            "vertLines": {
                "color": "rgba(197, 203, 206, 0.5)"
            },
            "horzLines": {
                "color": "rgba(197, 203, 206, 0.5)"
            }
        },
        "timeScale": {
            "visible": False,
            "borderColor": "rgba(197, 203, 206, 0.8)"
        },
        "watermark": {
            "visible": True,
            "fontSize": 18,
            "horzAlign": 'left',
            "vertAlign": 'top',
            "color": 'rgba(171, 71, 188, 0.7)',
            "text": 'RSI指标',
        }
    }
    
    # 5. 交易量图表配置
    chartVolumeOptions = {
        # "width": 800,
        "height": 150,
        "layout": {
            "background": {
                "type": "solid",
                "color": 'white'
            },
            "textColor": "black"
        },
        "grid": {
            "vertLines": {
                "color": "rgba(197, 203, 206, 0.5)"
            },
            "horzLines": {
                "color": "rgba(197, 203, 206, 0.5)"
            }
        },
        "timeScale": {
            "visible": False,
            "borderColor": "rgba(197, 203, 206, 0.8)"
        },
        "watermark": {
            "visible": True,
            "fontSize": 18,
            "horzAlign": 'left',
            "vertAlign": 'top',
            "color": 'rgba(171, 71, 188, 0.7)',
            "text": '交易量',
        }
    }
    
    # 准备各指标数据格式
    ema_5_data = json.loads(df.rename(columns={"ema_5": "value"}).to_json(orient="records"))
    ema_10_data = json.loads(df.rename(columns={"ema_10": "value"}).to_json(orient="records"))
    ema_20_data = json.loads(df.rename(columns={"ema_20": "value"}).to_json(orient="records"))
    
    macd_data = json.loads(df.rename(columns={"macd": "value"}).to_json(orient="records"))
    macdsignal_data = json.loads(df.rename(columns={"macdsignal": "value"}).to_json(orient="records"))
    df['color'] = np.where(df['macdhist'] > 0, COLOR_BULL, COLOR_BEAR)
    macdhist_data = json.loads(df.rename(columns={"macdhist": "value"}).to_json(orient="records"))
    
    slowk_data = json.loads(df.rename(columns={"slowk": "value"}).to_json(orient="records"))
    slowd_data = json.loads(df.rename(columns={"slowd": "value"}).to_json(orient="records"))
    slowj_data = json.loads(df.rename(columns={"slowj": "value"}).to_json(orient="records"))
    
    rsi_14_data = json.loads(df.rename(columns={"rsi_14": "value"}).to_json(orient="records"))
    volume_data = json.loads(df.rename(columns={"volume": "value"}).to_json(orient="records"))
    
    # 创建超买超卖线数据
    df['overbought_80'] = 80
    df['oversold_20'] = 20
    df['overbought_70'] = 70
    df['oversold_30'] = 30
    
    overbought_80_data = json.loads(df.rename(columns={"overbought_80": "value"}).to_json(orient="records"))
    oversold_20_data = json.loads(df.rename(columns={"oversold_20": "value"}).to_json(orient="records"))
    overbought_70_data = json.loads(df.rename(columns={"overbought_70": "value"}).to_json(orient="records"))
    oversold_30_data = json.loads(df.rename(columns={"oversold_30": "value"}).to_json(orient="records"))
    
    # 定义各图表系列
    seriesEMA = [
        {
            "type": 'Line',
            "data": ema_5_data,
            "options": {
                "color": COLOR_BLUE,
                "lineWidth": 2,
                "crosshairMarkerVisible": False,
                "title": 'EMA5'
            }
        },
        {
            "type": 'Line',
            "data": ema_10_data,
            "options": {
                "color": COLOR_GREEN,
                "lineWidth": 2,
                "crosshairMarkerVisible": False,
                "title": 'EMA10'
            }
        },
        {
            "type": 'Line',
            "data": ema_20_data,
            "options": {
                "color": COLOR_RED,
                "lineWidth": 2,
                "crosshairMarkerVisible": False,
                "title": 'EMA20'
            }
        }
    ]
    
    seriesMACD = [
        {
            "type": 'Line',
            "data": macd_data,
            "options": {
                "color": COLOR_BLUE,
                "lineWidth": 2,
                "crosshairMarkerVisible": False,
                "title": 'MACD'
            }
        },
        {
            "type": 'Line',
            "data": macdsignal_data,
            "options": {
                "color": COLOR_RED,
                "lineWidth": 2,
                "crosshairMarkerVisible": False,
                "title": 'Signal'
            }
        },
        {
            "type": 'Histogram',
            "data": macdhist_data,
            "options": {
                "color": 'rgba(255,0,0,0.7)',
                "lineWidth": 1,
                "title": 'Histogram'
            }
        }
    ]
    
    seriesKDJ = [
        {
            "type": 'Line',
            "data": slowk_data,
            "options": {
                "color": COLOR_BLUE,
                "lineWidth": 2,
                "crosshairMarkerVisible": False,
                "title": 'K'
            }
        },
        {
            "type": 'Line',
            "data": slowd_data,
            "options": {
                "color": COLOR_RED,
                "lineWidth": 2,
                "crosshairMarkerVisible": False,
                "title": 'D'
            }
        },
        {
            "type": 'Line',
            "data": slowj_data,
            "options": {
                "color": COLOR_GREEN,
                "lineWidth": 2,
                "crosshairMarkerVisible": False,
                "title": 'J'
            }
        },
        {
            "type": 'Line',
            "data": overbought_80_data,
            "options": {
                "color": "rgba(197, 203, 206, 0.8)",
                "lineWidth": 1,
                "lineStyle": 2,  # 虚线
                "crosshairMarkerVisible": False,
                "title": 'Overbought (80)'
            }
        },
        {
            "type": 'Line',
            "data": oversold_20_data,
            "options": {
                "color": "rgba(197, 203, 206, 0.8)",
                "lineWidth": 1,
                "lineStyle": 2,  # 虚线
                "crosshairMarkerVisible": False,
                "title": 'Oversold (20)'
            }
        }
    ]
    
    seriesRSI = [
        {
            "type": 'Line',
            "data": rsi_14_data,
            "options": {
                "color": COLOR_PURPLE,
                "lineWidth": 2,
                "crosshairMarkerVisible": False,
                "title": 'RSI14'
            }
        },
        {
            "type": 'Line',
            "data": overbought_70_data,
            "options": {
                "color": "rgba(197, 203, 206, 0.8)",
                "lineWidth": 1,
                "lineStyle": 2,  # 虚线
                "crosshairMarkerVisible": False,
                "title": 'Overbought (70)'
            }
        },
        {
            "type": 'Line',
            "data": oversold_30_data,
            "options": {
                "color": "rgba(197, 203, 206, 0.8)",
                "lineWidth": 1,
                "lineStyle": 2,  # 虚线
                "crosshairMarkerVisible": False,
                "title": 'Oversold (30)'
            }
        }
    ]
    
    seriesVolume = [
        {
            "type": 'Histogram',
            "data": volume_data,
            "options": {
                "color": COLOR_ORANGE,
                "lineWidth": 1,
                "title": 'Volume'
            }
        }
    ]
    
    # 返回图表配置列表
    charts = [
        {
            "chart": chartEMAOptions,
            "series": seriesEMA
        },
        {
            "chart": chartMACDOptions,
            "series": seriesMACD
        },
        {
            "chart": chartKDJOptions,
            "series": seriesKDJ
        },
        {
            "chart": chartRSIOptions,
            "series": seriesRSI
        },
        {
            "chart": chartVolumeOptions,
            "series": seriesVolume
        }
    ]
    
    return charts

def generate_investment_recommendations(account_id):
    """
    生成投资建议
    """
    db_manager = DatabaseTools()
    try:
        logger.info(f"为账户 {account_id} 生成投资建议")
        
        # 这里应该调用AI推荐系统
        # 查询账户持仓情况
        account_info, portfolio = get_portfolio_info(account_id)
        tech_sum = db_manager.get_market_place()
        template = Template.from_file(Path("prompts/trading_prompt.jinja"))
        prompt = template(tech_sum=tech_sum, account_info=account_info, portfolio=portfolio)
        st.markdown(prompt)
        # 暂时返回模拟的建议结果
        reasoning_content, content = get_ai_recommendation(prompt)
        logger.info(f"投资建议: \n{content}")
        logger.info(f"推理内容: \n{reasoning_content}")
        return reasoning_content, content
    except Exception as e:
        logger.exception(f"生成投资建议失败: {str(e)}")
        return [], []

def init_session_state():
    """初始化会话状态"""
    if 'investment_recommendations' not in st.session_state:
        st.session_state.investment_recommendations = []
    if 'basic_data' not in st.session_state:
        st.session_state.basic_data = ''
    if 'stock_advice' not in st.session_state:
        st.session_state.stock_advice = ''
    if 'indicator' not in st.session_state:
        st.session_state.indicator = {}
    return

def show_investment_advice(account_id):
    """
    显示投资建议页面
    """
    init_session_state()
    st.header("💡 投资建议")
    
    # 投资建议生成部分
    st.subheader("🔍 AI智能投资建议")
    
    # 添加生成建议按钮
    if st.button("🚀 生成ETF投资建议", key="generate_advice"):
        with st.spinner("AI正在分析市场数据和您的投资组合..."):
            # 调用建议生成函数
            _, recommendations = generate_investment_recommendations(account_id)
            
            # 保存建议到会话状态
            st.session_state.investment_recommendations = recommendations
            
            st.success(f"✅ 成功生成投资建议！")
    db_manager = DatabaseTools()
    # 显示投资建议
    if 'investment_recommendations' in st.session_state:
        recommendations = st.session_state.investment_recommendations
        
        if recommendations:
            st.subheader("📋 投资建议详情")
            df = pd.DataFrame(json_repair.loads(recommendations)).T.reset_index().rename(columns={'index': 'code'})
            df = df[df['signal'] != 'hold']
            df['name'] = df['code'].apply(lambda x: db_manager.get_stock_name(x))
            df['leverage'] = df['code'].apply(lambda x: get_market_snapshot(x))
            df['leverage'] = (df['leverage']*df['quantity']).apply(lambda x: f"{x:.2f}")
            df.rename(columns={'leverage': 'values'}, inplace=True)
            st.dataframe(df)
            # 按建议类型分组显示
            recommendation_types = ['买入建议', '持有建议', '卖出建议', '行业配置', '风险提示']
            
            # for rec_type in recommendation_types:
            #     recs_by_type = [r for r in recommendations if r['类型'] == rec_type]
            #     if recs_by_type:
            #         # 创建折叠面板显示该类型的建议
            #         with st.expander(f"{rec_type} ({len(recs_by_type)}条)", expanded=True):
            #             # 为每条建议创建卡片
            #             for rec in recs_by_type:
            #                 # 根据建议类型设置不同的颜色
            #                 if rec_type == '买入建议':
            #                     color = 'rgba(46, 204, 113, 0.1)'
            #                     border_color = '#2ecc71'
            #                 elif rec_type == '卖出建议':
            #                     color = 'rgba(231, 76, 60, 0.1)'
            #                     border_color = '#e74c3c'
            #                 elif rec_type == '持有建议':
            #                     color = 'rgba(52, 152, 219, 0.1)'
            #                     border_color = '#3498db'
            #                 elif rec_type == '行业配置':
            #                     color = 'rgba(155, 89, 182, 0.1)'
            #                     border_color = '#9b59b6'
            #                 else:  # 风险提示
            #                     color = 'rgba(241, 196, 15, 0.1)'
            #                     border_color = '#f1c40f'
                            
            #                 # 使用HTML和CSS创建样式化的卡片
            #                 st.markdown(f"""
            #                 <div style="background-color: {color}; border-left: 4px solid {border_color}; padding: 12px; margin-bottom: 10px; border-radius: 4px;">
            #                     <div style="display: flex; justify-content: space-between; align-items: center;">
            #                         <h4 style="margin: 0; color: #333;">{rec['名称']} ({rec['代码']})</h4>
            #                         <span style="background-color: {border_color}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px;">{rec['置信度']}</span>
            #                     </div>
            #                     <p style="margin: 8px 0; color: #666;">{rec['理由']}</p>
            #                     {f'<p style="margin: 0; color: #2c3e50; font-weight: bold;">目标价: {rec["目标价"]}</p>' if rec['目标价'] != 'N/A' else ''}
            #                 </div>
            #                 """, unsafe_allow_html=True)
            
            # 添加建议总结
            st.subheader("📊 建议总结")

            # 统计各类型建议数量
            rec_counts = {}
            # for rec in recommendations:
            #     rec_counts[rec['类型']] = rec_counts.get(rec['类型'], 0) + 1
            
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
    st.subheader("📰 个股洞察")
    col1, col2 = st.columns(2)
    with col1:
        stock_code = st.text_input("请输入股票代码（例如：000001）")
    with col2:
        stock_name = st.text_input("请输入股票名称（例如：平安银行）")
    stock_advice_btn = st.button("获取个股建议")
    # 创建市场洞察选项卡
    stock_tabs = st.tabs(["个股动态", "个股技术面", "AI建议"])
    if stock_advice_btn:
        if stock_code and stock_name:
            st.write(f"正在为股票 {stock_name} ({stock_code}) 生成建议...")
            st_ana = StockAna()
            end_date = datetime.today().strftime('%Y-%m-%d')
            start_date = (datetime.today() - timedelta(days=100)).strftime('%Y-%m-%d')
            stock_name, indicator, last_price, basic_data = st_ana.get_market_place(stock_code, start_date, end_date)
            account_info, portfolio = get_portfolio_info(account_id)
            res = f"当前未持仓股票"
            for item in portfolio['positions']:
                if item['code'] == stock_code:
                    res = f"当前持仓: {item['quantity']} 股，成本: {item['price']}， 现价: {item['value']}"
            template = Template.from_file("prompts/stock_prompt.jinja")
            prompt = template(stock_name=stock_name, indicator=indicator, basic_data=basic_data, last_price=last_price, positions=res)
            reasoning_content, content = get_ai_recommendation(prompt)
            st.session_state.basic_data = basic_data
            st.session_state.stock_advice = content
            st.session_state.indicator = indicator

    with stock_tabs[0]:
        if "basic_data" in st.session_state:
            st.write(st.session_state.basic_data)
        else:
            st.info("点击获取个股建议")
    # 技术指标展示
    with stock_tabs[1]:
        if 'indicator' in st.session_state and st.session_state.indicator != {}:
            st.subheader("技术指标图表")
            # 调用函数生成图表配置
            charts_data = generate_technical_indicator_chart(st.session_state.indicator)
            # 使用renderLightweightCharts渲染图表
            renderLightweightCharts(charts_data, 'technical_indicators')
        else:
            st.info("请在'投资建议'标签页点击'获取个股建议'按钮获取技术指标")
    
    with stock_tabs[2]:
        if "stock_advice" in st.session_state:
            st.markdown(st.session_state.stock_advice)
        else:
            st.info("点击获取个股建议")
    
    # with stock_tabs[3]:
    #     st.markdown("""
    #     ### 资金流向
    #     - **北向资金**: 近期北向资金呈现净流入态势
    #     - **机构动向**: 公募基金重点配置科技成长和消费板块
    #     - **融资融券**: 市场融资余额稳步上升，杠杆水平合理
    #     - **板块轮动**: 资金在不同板块间轮动，寻找确定性机会
    #     """)