import pandas as pd
import logging
from datetime import datetime
import random
import time
from db_schema import DatabaseManager, get_portfolios_by_account, get_positions_by_account, get_positions_by_portfolio, update_portfolio, insert_position, Portfolio, Position
from sqlalchemy.orm import Session
import streamlit as st
from fetch_kline_daily import get_market_snapshot
from db_tools import DatabaseTools
SLIP_FEE_RATE = 0.00008
# 配置日志
logger = logging.getLogger(__name__)

def execute_trade(account_id, trade_type, code, name, price, quantity, db_manager=None):
    """
    执行交易操作
    
    参数:
        account_id: 账户ID
        trade_type: 交易类型，'买入'或'卖出'
        code: 股票代码
        name: 股票名称
        price: 交易价格
        quantity: 交易数量
        db_manager: 数据库管理器实例（可选）
    
    返回:
        tuple: (success, result)
    """
    db_manager = DatabaseManager('investment_portfolio.db')
    db_tools = DatabaseTools(db_manager)
    # 参数验证
    try:
        # 输入参数验证
        if not isinstance(account_id, str) or not account_id.strip():
            raise ValueError("账户ID必须是非空字符串")
        
        if trade_type not in ["买入", "卖出"]:
            raise ValueError("交易类型必须是'买入'或'卖出'")
        
        if not isinstance(code, str) or not code.strip():
            raise ValueError("股票代码必须是非空字符串")
        
        if not isinstance(name, str) or not name.strip():
            raise ValueError("股票名称必须是非空字符串")
        
        # 价格验证和转换
        try:
            price = float(price)
            if price <= 0:
                raise ValueError("价格必须是正数")
        except (ValueError, TypeError):
            raise ValueError("价格必须是有效的数字")
        
        # 数量验证和转换
        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError("数量必须是正整数")
        except (ValueError, TypeError):
            raise ValueError("数量必须是有效的整数")
            
    except ValueError as ve:
        logger.error(f"参数验证失败: {str(ve)}")
        return False, f"参数错误: {str(ve)}"
    session = None
    try:
        # 确保有数据库管理器
        if not db_manager:
            db_manager = DatabaseManager()
            db_manager.init_db()
        
        # 创建数据库会话
        session = db_manager.create_session()
        
        logger.info(f"执行交易: 账户={account_id}, 类型={trade_type}, 代码={code}, 名称={name}, 价格={price}, 数量={quantity}")
        
        # 验证价格和数量
        if price <= 0 or quantity <= 0:
            return False, "价格和数量必须大于0"
        
        # 计算交易金额
        trade_amount = price * quantity
        
        # 获取账户最新的投资组合
        portfolios = get_portfolios_by_account(session, account_id)
        if not portfolios:
            # 如果没有投资组合，创建一个新的
            from db_schema import insert_portfolio_and_positions
            initial_portfolio = {
                "total_value": 100000.00,  # 默认初始资金10万元
                "cash": 100000.00,
                "positions": []
            }
            account_info = {
                "initial_capital": 100000.00,
                "total_return": 0.0
            }
            portfolio_id = insert_portfolio_and_positions(session, account_id, initial_portfolio, account_info)
            # 重新获取投资组合
            portfolios = get_portfolios_by_account(session, account_id)
        
        # 获取最新的投资组合
        portfolio = portfolios[0]
        portfolio_id = portfolio.portfolio_id
        current_cash = portfolio.cash
        initial_capital = portfolio.initial_capital
        
        # 获取当前持仓信息
        current_positions = get_positions_by_portfolio(session, portfolio_id)
        
        if trade_type == "买入":
            # 检查资金是否充足
            if trade_amount > current_cash:
                return False, f"资金不足，需要 {trade_amount:.2f} 元，但账户余额只有 {current_cash:.2f} 元"
            
            # 计算新的现金余额
            new_cash = current_cash - trade_amount
            
            # 查找是否已有该股票的持仓
            existing_position = next((p for p in current_positions if p.code == code), None)
            
            # 模拟市场价格（在实际应用中应该从外部API获取）
            market_price = get_market_snapshot(code)
            
            # 计算盈亏
            profit_loss = (market_price - price) * quantity
            profit_loss_pct = (profit_loss / trade_amount) * 100
            
            # 如果已有持仓，计算平均持仓价格和总数量
            if existing_position:
                total_quantity = existing_position.quantity + quantity
                total_cost = (existing_position.quantity * existing_position.price) + (quantity * price)
                avg_price = total_cost / total_quantity
                
                # 更新持仓信息
                existing_position.quantity = total_quantity
                existing_position.price = avg_price
                existing_position.value = total_quantity * market_price
                existing_position.market_price = market_price
                existing_position.profit_loss = (market_price - avg_price) * total_quantity
                existing_position.profit_loss_pct = (existing_position.profit_loss / (total_quantity * avg_price)) * 100
                session.commit()
            else:
                # 创建新的持仓记录
                position_data = {
                    "code": code,
                    "name": name,
                    "quantity": quantity,
                    "price": price,
                    "value": quantity * market_price,
                    "market_price": market_price,
                    "profit_loss": profit_loss,
                    "profit_loss_pct": profit_loss_pct
                }
                insert_position(session, portfolio_id, account_id, position_data)
            
            # 构建交易结果
            result = {
                "status": "success",
                "message": f"买入成功！已买入 {quantity} 股 {name}({code})",
                "trade_type": trade_type,
                "code": code,
                "name": name,
                "price": price,
                "quantity": quantity,
                "trade_amount": trade_amount,
                "cash_before": current_cash,
                "cash_after": new_cash,
                "market_price": market_price,
                "profit_loss": profit_loss,
                "profit_loss_pct": profit_loss_pct,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        elif trade_type == "卖出":
            # 查找持仓
            existing_position = next((p for p in current_positions if p.code == code), None)
            
            if not existing_position:
                return False, f"未找到持仓: {name}({code})"
            
            # 检查持仓数量是否足够
            current_quantity = existing_position.quantity
            if quantity > current_quantity:
                return False, f"持仓不足，当前持有 {current_quantity} 股，但尝试卖出 {quantity} 股"
            
            # 计算盈亏
            holding_price = existing_position.price
            # 考虑滑点费用万分之0.8
            
            slip_fee = holding_price * quantity * SLIP_FEE_RATE
            profit_loss = (price - holding_price) * quantity - slip_fee
            profit_loss_pct = (profit_loss / (holding_price * quantity)) * 100
            
            # 更新现金余额
            new_cash = current_cash + trade_amount - slip_fee
            
            # 更新持仓数量
            remaining_quantity = current_quantity - quantity
            
            if remaining_quantity == 0:
                # 如果全部卖出，删除持仓记录
                db_tools = DatabaseTools()
                db_tools.delete_position(existing_position.id)
            else:
                # 否则更新持仓数量
                existing_position.quantity = remaining_quantity
                existing_position.value = remaining_quantity * price
                session.commit()
            
            # 构建交易结果
            result = {
                "status": "success",
                "message": f"卖出成功！已卖出 {quantity} 股 {name}({code})",
                "trade_type": trade_type,
                "code": code,
                "name": name,
                "price": price,
                "quantity": quantity,
                "trade_amount": trade_amount,
                "cash_before": current_cash,
                "cash_after": new_cash,
                "holding_price": holding_price,
                "profit_loss": profit_loss,
                "profit_loss_pct": profit_loss_pct,
                "remaining_quantity": remaining_quantity,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        # 更新投资组合信息
        # 重新获取所有持仓以计算总市值
        updated_positions = db_tools.get_positions_by_portfolio(portfolio_id)
        total_position_value = sum(pos['value'] for pos in updated_positions)
        portfolio_value = new_cash + total_position_value
        st.info(f"当前持仓价值: {total_position_value:.2f}")
        st.info(f"当前现金余额: {new_cash:.2f}")
        total_return = portfolio_value - initial_capital
        total_return_pct = (total_return / initial_capital) * 100
        
        # 更新投资组合数据
        update_data = {
            "total_value": portfolio_value,
            "cash": new_cash,
            "total_return": total_return
        }
        update_portfolio(session, portfolio_id, update_data)
        
        # 更新交易结果中的投资组合信息
        result["portfolio_value"] = portfolio_value
        result["total_return"] = total_return
        result["total_return_pct"] = total_return_pct
        
        # 提交事务
        session.commit()
        logger.info("交易事务提交成功")
        
        # 验证数据一致性
        # 重新查询数据库验证交易结果
        updated_portfolio = session.query(Portfolio).filter(Portfolio.portfolio_id == portfolio_id).first()
        if abs(updated_portfolio.cash - new_cash) > 0.01:
            logger.error("现金余额不一致，交易可能存在问题")
        
        logger.info(f"交易执行成功: {result['message']}")
        return True, result
        
    except ValueError as ve:
        logger.exception(f"业务逻辑验证失败: {str(ve)}")
        # 确保事务回滚
        if session and session.is_active:
            session.rollback()
        return False, f"交易验证失败: {str(ve)}"
    except Exception as e:
        logger.exception(f"交易执行异常: {str(e)}")
        # 确保事务回滚
        if session and session.is_active:
            session.rollback()
        return False, f"交易执行失败: {str(e)}"
    finally:
        # 确保会话关闭
        if session:
            session.close()

def refresh_position_prices(db_session, positions):
    """
    刷新持仓股票的最新价格并计算盈亏
    
    参数:
        db_session: 数据库会话对象
        positions: 持仓列表
    
    返回:
        更新后的持仓列表
    """
    updated_positions = []
    for position in positions:
        # 模拟获取最新价格（在实际应用中应该从外部API获取）
        latest_price = get_market_snapshot(position.code)
        
        # 考虑滑点费用万分之0.8
        slip_fee = latest_price * position.quantity * SLIP_FEE_RATE
        
        # 计算新的盈亏和盈亏百分比
        profit_loss = (latest_price - position.price) * position.quantity - slip_fee
        profit_loss_pct = (profit_loss / (position.price * position.quantity)) * 100
        
        # 更新持仓信息
        position.market_price = latest_price
        position.value = position.quantity * latest_price
        position.profit_loss = profit_loss
        position.profit_loss_pct = profit_loss_pct
        
        # 更新数据库
        db_session.merge(position)
        updated_positions.append(position)
    
    return updated_positions

def show_trade_operations(account_id, start_date=None, end_date=None):
    """
    显示交易操作页面
    
    参数:
        account_id: 账户ID
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）
    """
    # 仅在需要时导入streamlit
    import streamlit as st
    
    # 初始化数据库连接
    db_manager = DatabaseManager()
    db_manager.init_db()
    
    st.header("💰 交易操作")
    
    # 创建交易表单
    with st.form("trade_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            # 股票代码输入
            code = st.text_input(
                "股票代码",
                placeholder="请输入股票代码",
                help="例如：600519"
            )
            
            # 股票名称输入
            name = st.text_input(
                "股票名称",
                placeholder="请输入股票名称",
                help="例如：贵州茅台"
            )
        
        with col2:
            # 交易数量输入
            quantity = st.number_input(
                "交易数量 (股)",
                min_value=1,
                step=1,
                help="请输入交易数量"
            )
        
        # 交易价格输入
        price = st.number_input(
            "交易价格 (元)",
            min_value=0.01,
            step=0.01,
            format="%.2f",
            help="请输入交易价格"
        )
        
        # 计算交易金额
        trade_amount = price * quantity
        
        # 提交按钮
        col1, col2 = st.columns(2)
        with col1:
            buy_button = st.form_submit_button("📈 买入", type="primary")
        with col2:
            sell_button = st.form_submit_button("📉 卖出", type="primary")
    
    # 处理交易提交
    if buy_button or sell_button:
        # 确定交易类型
        trade_type = "买入" if buy_button else "卖出"
        
        # 验证表单数据
        if not code or not name:
            st.error("请输入股票代码和名称")
        elif price <= 0 or quantity <= 0:
            st.error("价格和数量必须大于0")
        else:
            # 显示交易确认信息
            st.info(f"正在执行{trade_type}操作，请稍候...")
            
            # 执行交易
            success, result = execute_trade(account_id, trade_type, code, name, price, quantity)
            
            if success:
                # 显示交易成功消息
                st.success(result["message"])
                
                # 显示交易详情
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**交易时间:** {result['timestamp']}")
                    st.markdown(f"**交易类型:** {result['trade_type']}")
                    st.markdown(f"**股票代码:** {result['code']}")
                    st.markdown(f"**股票名称:** {result['name']}")
                    st.markdown(f"**交易价格:** ¥{result['price']:.2f}")
                
                with col2:
                    st.markdown(f"**交易数量:** {result['quantity']} 股")
                    st.markdown(f"**交易金额:** ¥{result['trade_amount']:,.2f}")
                    st.markdown(f"**现金余额:** ¥{result['cash_after']:,.2f}")
                    st.markdown(f"**投资组合总价值:** ¥{result['portfolio_value']:,.2f}")
                
                # 显示盈亏信息
                profit_color = "green" if result['profit_loss'] > 0 else "red"
                st.markdown(f"**盈亏金额:** <span style='color:{profit_color};font-weight:bold'>¥{result['profit_loss']:,.2f}</span>", unsafe_allow_html=True)
                st.markdown(f"**盈亏比例:** <span style='color:{profit_color};font-weight:bold'>{result['profit_loss_pct']:.2f}%</span>", unsafe_allow_html=True)
            else:
                # 显示交易失败消息
                st.error(result)
    
    # 显示当前持仓
    st.subheader("📊 当前持仓")
    
    # 创建数据库会话
    session = db_manager.create_session()
    
    try:
        # 获取账户的投资组合
        portfolios = get_portfolios_by_account(session, account_id)
        if portfolios:
            portfolio = portfolios[0]
            portfolio_id = portfolio.portfolio_id
            
            # 获取当前持仓
            positions = get_positions_by_portfolio(session, portfolio_id)
            
            if positions:
                # 显示持仓表格
                position_data = []
                for pos in positions:
                    profit_color = "green" if pos.profit_loss > 0 else "red"
                    position_data.append({
                        "股票代码": pos.code,
                        "股票名称": pos.name,
                        "持仓数量": pos.quantity,
                        "成本价": pos.price,
                        "当前价": pos.market_price,
                        "持仓价值": pos.value,
                        "盈亏金额": pos.profit_loss,
                        "盈亏比例": pos.profit_loss_pct
                    })
                
                df = pd.DataFrame(position_data)
                
                # 格式化显示
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "成本价": st.column_config.NumberColumn(format="¥%.2f"),
                        "当前价": st.column_config.NumberColumn(format="¥%.2f"),
                        "持仓价值": st.column_config.NumberColumn(format="¥%.2f"),
                        "盈亏金额": st.column_config.NumberColumn(format="¥%.2f"),
                        "盈亏比例": st.column_config.NumberColumn(format="%.2f%%")
                    }
                )
                
                # 计算盈亏按钮
                if st.button("🔄 计算盈亏", type="primary"):
                    with st.spinner("正在刷新最新价格并计算盈亏..."):
                        # 刷新持仓价格
                        updated_positions = refresh_position_prices(session, positions)
                        session.commit()
                        
                        # 重新显示持仓
                        st.success("盈亏计算完成！")
                        st.rerun()
            else:
                st.info("暂无持仓。")
        else:
            st.info("暂无投资组合，请先初始化账户。")
            
            # 初始化账户按钮
            if st.button("🔄 初始化账户"):
                try:
                    with st.spinner("正在初始化账户..."):
                        from db_schema import insert_portfolio_and_positions
                        initial_portfolio = {
                            "total_value": 100000.00,
                            "cash": 100000.00,
                            "positions": []
                        }
                        account_info = {
                            "initial_capital": 100000.00,
                            "total_return": 0.0
                        }
                        insert_portfolio_and_positions(session, account_id, initial_portfolio, account_info)
                        st.success("账户初始化成功！已设置初始资金10万元。")
                        st.rerun()
                except Exception as e:
                    logger.error(f"账户初始化失败: {str(e)}")
                    st.error(f"账户初始化失败: {str(e)}")
    except Exception as e:
        logger.error(f"获取持仓信息失败: {str(e)}")
        st.error(f"获取持仓信息失败: {str(e)}")
    finally:
        session.close()
    
    # 交易提示
    st.subheader("💡 交易提示")
    st.info("""
    - 请确保输入正确的股票代码和名称
    - 交易前请确认您的账户余额充足
    - 卖出前请确认您持有足够的股票数量
    - 实际交易价格以市场成交价为准
    - 点击"计算盈亏"按钮可刷新最新价格并重新计算盈亏
    """)