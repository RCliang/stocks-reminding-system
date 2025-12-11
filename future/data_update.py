import streamlit as st
import pandas as pd
import logging
import time
from datetime import datetime
from fetch_kline_daily import get_stock_pool, KlineFetcher
from db_tools import DatabaseTools

daily_columns = ['code', 'name', 'update_time', 'last_price', 'open_price', 'high_price', \
    'low_price', 'pe_ratio', 'volume', 'turnover', 'turnover_rate']
hist_columns = ['code', 'name', 'time_key', 'open', \
    'close', 'high', 'low', 'pe_ratio', 'volume', \
        'turnover_rate', 'turnover', 'change_rate']
# 配置日志
logger = logging.getLogger(__name__)

def update_kline_data(code_list, db_manager=None):
    """
    更新ETF/股票历史K线数据
    """
    # 初始化数据库工具
    db_tools = DatabaseTools('investment_portfolio.db')
    try:
        logger.info(f"开始更新K线数据，股票数量: {len(code_list)}")
        fetcher = KlineFetcher(code_list, daily_columns, hist_columns, 'data')
        # 这里应该调用实际的数据更新接口
        # 为了演示，我们模拟数据更新过程
        results = []
        today = datetime.now().strftime('%Y-%m-%d')

        for code in code_list:
            # 查询该股票在数据库中的最新日期
            latest_date = db_tools.get_latest_date_for_stock(code)
            # 如果数据库返回的是 datetime 对象，则格式化为字符串
            if isinstance(latest_date, datetime):
                latest_date = latest_date.strftime('%Y-%m-%d')
            logger.info(f"股票 {code} 数据库最新日期: {latest_date}")
            tmp = fetcher.fetch_hist_kline(code, start=latest_date, end=today)
            tmp['time_key'] = pd.to_datetime(tmp['time_key'])
            for item in tmp.iterrows():
                stock_data = item[1].to_dict()
                db_tools.insert_stock_kline(stock_data)
            count = tmp.shape[0]
            print(f"已插入 {count}条股票数据")
            # 模拟更新结果
            success = True  # 随机模拟成功率
            if success:
                results.append({
                    'code': code,
                    'status': '成功',
                    'message': '数据更新成功',
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                logger.info(f"股票 {code} 数据更新成功")
            else:
                results.append({
                    'code': code,
                    'status': '失败',
                    'message': '网络超时',
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                logger.warning(f"股票 {code} 数据更新失败")
        
        logger.info(f"K线数据更新完成，成功: {len([r for r in results if r['status'] == '成功'])}, 失败: {len([r for r in results if r['status'] == '失败'])}")
        return results
    except Exception as e:
        logger.exception(f"更新K线数据失败: {str(e)}")
        return []

def clean_expired_data():
    """
    清理过期数据
    """
    db_tools = DatabaseTools('investment_portfolio.db')
    db_tools.clean_expired_data()
    return

def show_data_update():
    """
    显示数据更新页面
    """
    st.header("⚙️ 数据更新")
    
    # 股票池选择部分
    st.subheader("📊 股票池选择")
    
    # 预定义的股票池
    stock_pools = {
        # "全部股票": "all",
        "自选股票": "favorites",
        "沪深300": "hs300",
        "中证500": "zz500",
        "创业板": "cyb",
        "科创板": "kcb",
        "行业ETF": "etf"
    }
    
    # 选择股票池
    selected_pool = st.selectbox(
        "选择股票池",
        options=list(stock_pools.keys()),
        index=0,
        help="选择要更新数据的股票池"
    )
    
    # 显示选定股票池的描述
    pool_descriptions = {
        # "全部股票": "更新所有支持的股票数据（预计耗时较长）",
        "自选股票": "更新您添加的自选股票数据",
        "沪深300": "更新沪深300指数成分股数据",
        "中证500": "更新中证500指数成分股数据",
        "创业板": "更新创业板股票数据",
        "科创板": "更新科创板股票数据",
        "行业ETF": "更新各类行业ETF数据"
    }
    
    st.info(pool_descriptions[selected_pool])
    
    # 自定义股票代码输入
    st.subheader("🔍 自定义股票更新")
    custom_codes = st.text_area(
        "输入股票代码（每行一个）",
        placeholder="例如：\nSH.600519\nSZ.000001\nSZ.300059",
        help="输入您想要单独更新的股票代码，每行一个"
    )
    
    # 数据类型选择
    st.subheader("📈 数据类型选择")
    
    # 多选框选择要更新的数据类型
    data_types = st.multiselect(
        "选择要更新的数据类型",
        options=["日线数据", "周线数据", "月线数据", "基本面数据", "技术指标"],
        default=["日线数据", "基本面数据"],
        help="选择需要更新的数据类型"
    )
    
    # 更新频率设置
    st.subheader("⏰ 更新设置")
    
    # 选择更新频率
    update_frequency = st.radio(
        "更新频率",
        options=["手动更新", "每日自动更新", "每周自动更新"],
        horizontal=True,
        help="设置数据自动更新的频率"
    )
    
    # 显示上次更新时间（模拟数据）
    if 'last_update_time' not in st.session_state:
        db_tools = DatabaseTools()
        last_update_time = db_tools.get_last_update_time()
        if last_update_time:
            st.session_state.last_update_time = last_update_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            st.session_state.last_update_time = "从未更新"
    
    st.info(f"上次更新时间: {st.session_state.last_update_time}")
    
    # 执行更新按钮
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 执行更新", type="primary", use_container_width=True):
            # 收集要更新的股票代码
            codes_to_update = []
            
            # 添加选定股票池的代码（模拟）
            if selected_pool == "自选股票":
                # 模拟少量股票代码用于演示
                codes_to_update.extend(get_stock_pool())
            elif selected_pool == "沪深300":
                codes_to_update.extend(["600519", "000001", "601318", "000858", "002415"])
            elif selected_pool == "行业ETF":
                codes_to_update.extend(get_stock_pool("etf"))
            else:
                # 其他股票池
                codes_to_update.extend(["600519", "000001", "300059"])
            
            # 添加自定义代码
            if custom_codes.strip():
                custom_code_list = [code.strip() for code in custom_codes.strip().split("\n") if code.strip()]
                codes_to_update.extend(custom_code_list)
            
            # 去重
            codes_to_update = list(set(codes_to_update))
            
            # 显示更新信息
            st.info(f"准备更新 {len(codes_to_update)} 只股票的数据")
            
            # 执行更新
            with st.spinner(f"正在更新数据，请稍候..."):
                # 记录开始时间
                start_time = time.time()
                
                # 调用更新函数
                update_results = update_kline_data(codes_to_update)
                
                # 计算耗时
                elapsed_time = time.time() - start_time
                
                # 更新最后更新时间
                st.session_state.last_update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # 显示更新结果
                if update_results:
                    # 统计成功和失败数量
                    success_count = len([r for r in update_results if r['status'] == '成功'])
                    fail_count = len([r for r in update_results if r['status'] == '失败'])
                    
                    st.success(f"✅ 数据更新完成！耗时: {elapsed_time:.2f} 秒")
                    st.info(f"成功: {success_count}, 失败: {fail_count}")
                    
                    # 显示更新结果表格
                    if st.checkbox("显示详细更新结果", value=False):
                        results_df = pd.DataFrame(update_results)
                        st.dataframe(
                            results_df,
                            use_container_width=True,
                            hide_index=True
                        )
                else:
                    st.error("❌ 数据更新失败")
    
    with col2:
        if st.button("🔄 检查更新", type="secondary", use_container_width=True):
            with st.spinner("检查数据更新状态..."):
                time.sleep(1)
                # 模拟检查结果
                st.info("✅ 系统数据已是最新版本")
    
    # 数据统计部分
    st.subheader("📊 数据统计")
    
    # 模拟数据统计信息
    # data_stats = {
    #     "已缓存股票数量": 1000,
    #     "总数据条目": "5,000,000",
    #     "数据存储空间": "1.5 GB",
    #     "平均更新频率": "每日一次"
    # }
    # 数据统计部分
    st.subheader("📊 数据统计")
    
    # 查询数据库表stock中缓存的股票数量和总条目
    db_tools = DatabaseTools('investment_portfolio.db')
    cached_stock_count = db_tools.get_cached_stock_count()
    total_kline_entries = db_tools.get_total_kline_entries()
    
    data_stats = {
        "已缓存股票数量": cached_stock_count,
        "总数据条目": total_kline_entries,
        "数据存储空间": "1.5 GB",
        "平均更新频率": "每日一次"
    }
    
    col1, col2 = st.columns(2)
    
    with col1:
        for key, value in list(data_stats.items())[:2]:
            st.metric(key, value)
    
    with col2:
        for key, value in list(data_stats.items())[2:]:
            st.metric(key, value)
    
    # 数据管理部分
    st.subheader("🗄️ 数据管理")
    
    # 数据清理和管理功能
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🧹 清理过期数据", type="secondary", use_container_width=True):
            with st.spinner("清理过期数据..."):
                clean_expired_data()
                st.success("✅ 过期数据清理完成")
    
    with col2:
        if st.button("📁 导出数据报告", type="secondary", use_container_width=True):
            with st.spinner("生成数据报告..."):
                time.sleep(1)
                st.success("✅ 数据报告生成成功，可在下载中心查看")
    
    # 更新提示
    st.subheader("💡 更新提示")
    st.info("""
    - 建议定期更新数据以确保分析的准确性
    - 初次更新可能需要较长时间，请耐心等待
    - 更新过程中请勿关闭页面或刷新浏览器
    - 大型股票池更新可能会消耗较多资源
    - 如遇更新失败，请检查网络连接后重试
    """)