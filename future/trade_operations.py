import streamlit as st
import pandas as pd
import logging
from datetime import datetime
import random
import time
from db_schema import DatabaseManager, get_portfolios_by_account, get_positions_by_account, get_positions_by_portfolio, update_portfolio, insert_position, Portfolio, Position
from sqlalchemy.orm import Session

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
            market_price = price * (1 + random.uniform(-0.02, 0.02))
            
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
            profit_loss = (price - holding_price) * quantity
            profit_loss_pct = (profit_loss / (holding_price * quantity)) * 100
            
            # 更新现金余额
            new_cash = current_cash + trade_amount
            
            # 更新持仓数量
            remaining_quantity = current_quantity - quantity
            
            if remaining_quantity == 0:
                # 如果全部卖出，删除持仓记录
                session.delete(existing_position)
            else:
                # 否则更新持仓数量
                existing_position.quantity = remaining_quantity
                existing_position.value = remaining_quantity * existing_position.market_price
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
        updated_positions = get_positions_by_portfolio(session, portfolio_id)
        total_position_value = sum(pos.value for pos in updated_positions)
        portfolio_value = new_cash + total_position_value
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

def test_trade_operations():
    """
    测试交易操作功能
    
    此函数测试execute_trade函数的基本功能，包括买入、卖出和错误处理。
    在实际应用中，应该使用数据库事务来隔离测试，避免污染生产数据。
    """
    try:
        test_account_id = "test_account_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        test_code = "600000"
        test_name = "浦发银行"
        
        print("开始测试交易功能...")
        
        # 初始化测试数据库会话
        db_manager = DatabaseManager()
        db_manager.init_db()
        db_session = db_manager.create_session()
        
        print("\n测试1: 测试参数验证 - 无效价格")
        success, result = execute_trade(test_account_id, "买入", test_code, test_name, -10.0, 100)
        print(f"结果: {success}, {result}")
        assert not success, "测试1失败: 无效价格的交易应该失败"
        
        print("\n测试2: 测试参数验证 - 无效数量")
        success, result = execute_trade(test_account_id, "买入", test_code, test_name, 10.0, 0)
        print(f"结果: {success}, {result}")
        assert not success, "测试2失败: 无效数量的交易应该失败"
        
        print("\n测试3: 测试参数验证 - 无效交易类型")
        success, result = execute_trade(test_account_id, "持仓", test_code, test_name, 10.0, 100)
        print(f"结果: {success}, {result}")
        assert not success, "测试3失败: 无效交易类型的交易应该失败"
        
        print("\n测试4: 执行买入操作")
        success, result = execute_trade(test_account_id, "买入", test_code, test_name, 10.0, 100)
        print(f"结果: {success}, {result.get('message', 'No message')}")
        assert success, "测试4失败: 正常买入操作应该成功"
        assert result.get('cash_after', 0) >= 98000.0, f"测试4失败: 买入后现金余额不正确"
        
        print("\n测试5: 执行卖出操作")
        success, result = execute_trade(test_account_id, "卖出", test_code, test_name, 11.0, 50)
        print(f"结果: {success}, {result.get('message', 'No message')}")
        assert success, "测试5失败: 正常卖出操作应该成功"
        assert result.get('profit_loss', -1) >= 0, "测试5失败: 卖出盈利计算不正确"
        
        print("\n测试6: 测试卖出超出持仓数量")
        success, result = execute_trade(test_account_id, "卖出", test_code, test_name, 11.0, 100)
        print(f"结果: {success}, {result}")
        assert not success, "测试6失败: 超出持仓数量的卖出应该失败"
        
        print("\n所有测试通过！")
        return True
    
    except AssertionError as ae:
        print(f"\n测试失败: {str(ae)}")
        return False
    except Exception as e:
        print(f"\n测试过程中出现异常: {str(e)}")
        return False
    finally:
        if 'db_session' in locals():
            db_session.close()

# 如果直接运行此文件，执行测试
if __name__ == "__main__":
    test_trade_operations()

def show_trade_operations(account_id, start_date, end_date):
    """
    显示交易操作页面
    """
    # 初始化数据库连接
    db_manager = DatabaseManager()
    db_manager.init_db()
    session = db_manager.create_session()
    
    # 获取账户信息和投资组合数据
    try:
        portfolios = get_portfolios_by_account(session, account_id)
        if portfolios:
            portfolio = portfolios[0]
            current_cash = portfolio.cash
            portfolio_value = portfolio.total_value
        else:
            current_cash = 100000.00  # 默认初始资金
            portfolio_value = 100000.00
    except Exception as e:
        logger.error(f"获取账户信息失败: {str(e)}")
        current_cash = 100000.00
        portfolio_value = 100000.00
    finally:
        session.close()
    
    st.header("💰 交易操作")
    
    # 创建交易表单
    with st.form("trade_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            # 交易类型选择
            trade_type = st.radio(
                "交易类型",
                options=["买入", "卖出"],
                horizontal=True
            )
            
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
            # 交易价格输入
            price = st.number_input(
                "交易价格 (元)",
                min_value=0.01,
                step=0.01,
                format="%.2f",
                help="请输入交易价格"
            )
            
            # 交易数量输入
            quantity = st.number_input(
                "交易数量 (股)",
                min_value=1,
                step=1,
                help="请输入交易数量"
            )
        
        # 计算交易金额
        trade_amount = price * quantity
        
        # 显示交易金额和账户余额
        st.info(f"交易金额: ¥{trade_amount:,.2f}")
        st.info(f"当前账户余额: ¥{current_cash:,.2f}")
        
        # 提交按钮
        submit_button = st.form_submit_button(
            f"🚀 确认{trade_type}",
            type="primary"
        )
    
    # 处理交易提交
    if submit_button:
        # 验证表单数据
        if not code or not name:
            st.error("请输入股票代码和名称")
        elif price <= 0 or quantity <= 0:
            st.error("价格和数量必须大于0")
        else:
            # 显示交易确认信息
            st.info(f"正在执行{trade_type}操作，请稍候...")
            
            # 模拟交易处理延迟
            with st.spinner("交易处理中..."):
                time.sleep(2)
                
                # 执行交易
                success, result = execute_trade(account_id, trade_type, code, name, price, quantity)
                
                if success:
                    # 将交易记录添加到会话状态
                    if 'trade_history' not in st.session_state:
                        st.session_state.trade_history = []
                    
                    # 创建交易记录
                    trade_record = {
                        "timestamp": result['timestamp'],
                        "trade_type": result['trade_type'],
                        "code": result['code'],
                        "name": result['name'],
                        "price": result['price'],
                        "quantity": result['quantity'],
                        "trade_amount": result['trade_amount'],
                        "profit_loss": result['profit_loss'],
                        "profit_loss_pct": result['profit_loss_pct']
                    }
                    
                    # 添加到交易历史的开头
                    st.session_state.trade_history.insert(0, trade_record)
                    
                    # 限制历史记录数量
                    if len(st.session_state.trade_history) > 50:
                        st.session_state.trade_history = st.session_state.trade_history[:50]
                    
                    # 显示交易成功消息
                    st.success(result["message"])
                    
                    # 使用折叠面板显示交易详情
                    with st.expander("交易详情", expanded=True):
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
                            
                            # 根据交易类型显示不同的信息
                            if trade_type == "买入":
                                st.markdown(f"**当前价格:** ¥{result['market_price']:.2f}")
                            else:
                                st.markdown(f"**持仓价格:** ¥{result['holding_price']:.2f}")
                                st.markdown(f"**剩余持仓:** {result['remaining_quantity']} 股")
                        
                        # 显示盈亏信息
                        profit_color = "green" if result['profit_loss'] > 0 else "red"
                        st.markdown(f"**盈亏金额:** <span style='color:{profit_color};font-weight:bold'>¥{result['profit_loss']:,.2f}</span>", unsafe_allow_html=True)
                        st.markdown(f"**盈亏比例:** <span style='color:{profit_color};font-weight:bold'>{result['profit_loss_pct']:.2f}%</span>", unsafe_allow_html=True)
                        
                        # 显示投资组合总价值和总收益率
                        st.markdown(f"**投资组合总价值:** ¥{result['portfolio_value']:,.2f}")
                        
                        total_return_color = "green" if result['total_return'] > 0 else "red"
                        st.markdown(f"**总收益:** <span style='color:{total_return_color};font-weight:bold'>¥{result['total_return']:,.2f}</span>", unsafe_allow_html=True)
                        st.markdown(f"**总收益率:** <span style='color:{total_return_color};font-weight:bold'>{result['total_return_pct']:.2f}%</span>", unsafe_allow_html=True)
                    
                    # 显示提示信息
                    st.info("交易已成功执行，投资组合概览页面将自动更新。")
                    
                    # 刷新会话状态中的数据
                    if 'load_portfolio_data' in st.session_state:
                        portfolio_data, positions_data = st.session_state.load_portfolio_data(account_id, start_date, end_date)
                        st.session_state.portfolio_data = portfolio_data
                        st.session_state.positions_data = positions_data
                    
                    # 刷新页面以显示最新的账户余额
                    st.rerun()
                else:
                    # 显示交易失败消息
                    st.error(result)
    
    # 交易记录部分
    st.subheader("📋 近期交易记录")
    
    # 初始化交易历史记录
    if 'trade_history' not in st.session_state:
        st.session_state.trade_history = []
    
    # 如果有交易记录，显示交易历史表格
    if st.session_state.trade_history:
        trade_df = pd.DataFrame(st.session_state.trade_history)
        
        # 格式化交易记录显示
        st.dataframe(
            trade_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "timestamp": "交易时间",
                "trade_type": "交易类型",
                "code": "股票代码",
                "name": "股票名称",
                "price": st.column_config.NumberColumn("交易价格", format="¥%.2f"),
                "quantity": "交易数量",
                "trade_amount": st.column_config.NumberColumn("交易金额", format="¥%.2f"),
                "profit_loss": st.column_config.NumberColumn("盈亏金额", format="¥%.2f"),
                "profit_loss_pct": st.column_config.NumberColumn("盈亏比例", format="%.2f%%")
            }
        )
    else:
        st.info("暂无交易记录。")
    
    # 账户管理部分
    st.subheader("💼 账户管理")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 显示当前账户信息（从数据库获取）
        st.markdown(f"**账户ID:** {account_id}")
        st.markdown(f"**当前日期:** {datetime.now().strftime('%Y-%m-%d')}")
        st.markdown(f"**账户余额:** ¥{current_cash:,.2f}")
        st.markdown(f"**投资组合总价值:** ¥{portfolio_value:,.2f}")
    
    with col2:
        # 初始化账户按钮
        if st.button("🔄 初始化账户", type="secondary"):
            try:
                with st.spinner("正在初始化账户..."):
                    # 创建数据库会话
                    db_session = db_manager.create_session()
                    
                    # 检查是否已存在投资组合
                    existing_portfolios = get_portfolios_by_account(db_session, account_id)
                    
                    if not existing_portfolios:
                        # 创建新的投资组合
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
                        insert_portfolio_and_positions(db_session, account_id, initial_portfolio, account_info)
                        
                        # 重置交易历史
                        st.session_state.trade_history = []
                        
                        st.success("账户初始化成功！已设置初始资金10万元。")
                        st.rerun()  # 重新加载页面以显示更新后的账户信息
                    else:
                        st.warning("账户已初始化，无需重复操作。")
            except Exception as e:
                logger.error(f"账户初始化失败: {str(e)}")
                st.error(f"账户初始化失败: {str(e)}")
            finally:
                if 'db_session' in locals():
                    db_session.close()
        
        # 重置交易记录按钮
        if st.button("🗑️ 重置交易记录", type="secondary"):
            if st.session_state.trade_history:
                # Streamlit没有confirm_dialog函数，使用button组代替
                confirm_container = st.container()
                with confirm_container:
                    col1, col2 = st.columns(2)
                    with col1:
                        confirm = st.button("确认重置", type="primary")
                    with col2:
                        cancel = st.button("取消")
                    
                    if confirm:
                        st.session_state.trade_history = []
                        st.success("交易记录已重置。")
                        st.rerun()
                    elif cancel:
                        confirm_container.empty()
            else:
                st.info("当前没有交易记录需要重置。")
    
    # 交易提示
    st.subheader("💡 交易提示")
    st.info("""
    - 请确保输入正确的股票代码和名称
    - 交易前请确认您的账户余额充足
    - 卖出前请确认您持有足够的股票数量
    - 实际交易价格以市场成交价为准
    - 系统将自动计算盈亏并更新投资组合价值
    """)