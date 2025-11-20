#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试SQLAlchemy ORM功能的脚本
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import datetime
import logging
from db_schema import (
    DatabaseManager,
    insert_portfolio_and_positions,
    get_portfolios_by_account,
    get_positions_by_portfolio,
    update_portfolio,
    delete_portfolio
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_orm.log')
    ]
)
logger = logging.getLogger('test_orm')

def setup_test_database():
    """设置测试数据库"""
    logger.info("开始设置测试数据库...")
    db_manager = DatabaseManager('test_portfolio.db')
    result = db_manager.init_db()
    if result:
        logger.info("测试数据库设置成功")
    else:
        logger.error("测试数据库设置失败")
    return db_manager

def test_insert_functionality(db_session):
    """测试插入功能"""
    logger.info("测试插入功能...")
    
    # 准备测试数据
    account_id = "test_user_001"
    test_portfolio = {
        "total_value": 150000.00,
        "cash": 50000.00,
        "positions": []
    }
    test_account_info = {
        "initial_capital": 100000.00,
        "total_return": 50.0
    }
    test_positions = [
        {
            "code": "000001.SZ",
            "name": "平安银行",
            "quantity": 1000.0,
            "price": 10.50,
            "value": 10500.00,
            "market_price": 10.80,
            "profit_loss": 300.00,
            "profit_loss_pct": 2.86
        },
        {
            "code": "600036.SH",
            "name": "招商银行",
            "quantity": 500.0,
            "price": 35.20,
            "value": 17600.00,
            "market_price": 36.50,
            "profit_loss": 650.00,
            "profit_loss_pct": 3.69
        }
    ]
    
    # 插入数据
    portfolio_id = insert_portfolio_and_positions(
        db_session,
        account_id,
        test_portfolio,
        test_account_info,
        test_positions
    )
    
    logger.info(f"插入测试数据成功，投资组合ID: {portfolio_id}")
    return account_id, portfolio_id

def test_query_functionality(db_session, account_id, portfolio_id):
    """测试查询功能"""
    logger.info("测试查询功能...")
    
    # 查询投资组合
    portfolios = get_portfolios_by_account(db_session, account_id)
    logger.info(f"查询到{len(portfolios)}个投资组合记录")
    
    if portfolios:
        portfolio = portfolios[0]
        logger.info(f"投资组合详情: ID={portfolio.portfolio_id}, 日期={portfolio.date}, 总价值={portfolio.total_value}")
    
    # 查询持仓
    positions = get_positions_by_portfolio(db_session, portfolio_id)
    logger.info(f"查询到{len(positions)}个持仓记录")
    
    for pos in positions:
        logger.info(f"持仓详情: 代码={pos.code}, 名称={pos.name}, 数量={pos.quantity}, 市值={pos.value}")
    
    return len(portfolios) > 0 and len(positions) > 0

def test_update_functionality(db_session, portfolio_id):
    """测试更新功能"""
    logger.info("测试更新功能...")
    
    # 准备更新数据
    update_data = {
        "total_value": 155000.00,
        "cash": 52000.00,
        "total_return": 55.0
    }
    
    # 执行更新
    result = update_portfolio(db_session, portfolio_id, update_data)
    
    if result:
        logger.info("投资组合更新成功")
        # 验证更新（通过已有的查询函数）
        portfolios = get_portfolios_by_account(db_session, "test_user_001")
        
        for p in portfolios:
            if p.portfolio_id == portfolio_id:
                logger.info(f"更新后的值: 总价值={p.total_value}, 现金={p.cash}, 总收益={p.total_return}")
                break
    
    return result

def test_delete_functionality(db_session, portfolio_id):
    """测试删除功能"""
    logger.info("测试删除功能...")
    
    # 执行删除
    result = delete_portfolio(db_session, portfolio_id)
    
    if result:
        logger.info("投资组合删除成功")
        # 验证删除
        portfolios = get_portfolios_by_account(db_session, "test_user_001")
        portfolio_exists = any(p.portfolio_id == portfolio_id for p in portfolios)
        
        if not portfolio_exists:
            logger.info("删除验证成功，投资组合记录不存在")
        
        # 验证级联删除（检查相关持仓是否也被删除）
        positions = get_positions_by_portfolio(db_session, portfolio_id)
        
        if len(positions) == 0:
            logger.info("级联删除验证成功，相关持仓记录不存在")
    
    return result

def main():
    """主测试函数"""
    logger.info("开始SQLAlchemy ORM功能测试...")
    
    # 不需要直接导入模型，使用已有的函数进行操作
    
    # 设置测试数据库
    db_manager = setup_test_database()
    db_session = db_manager.create_session()
    
    try:
        # 执行测试用例
        logger.info("========== 执行测试用例 ==========")
        
        # 测试1: 插入功能
        try:
            account_id, portfolio_id = test_insert_functionality(db_session)
            logger.info("✅ 插入测试通过")
        except Exception as e:
            logger.exception(f"❌ 插入测试失败: {str(e)}")
            return
        
        # 测试2: 查询功能
        try:
            query_result = test_query_functionality(db_session, account_id, portfolio_id)
            if query_result:
                logger.info("✅ 查询测试通过")
            else:
                logger.error("❌ 查询测试失败")
                return
        except Exception as e:
            logger.exception(f"❌ 查询测试失败: {str(e)}")
            return
        
        # 测试3: 更新功能
        try:
            update_result = test_update_functionality(db_session, portfolio_id)
            if update_result:
                logger.info("✅ 更新测试通过")
            else:
                logger.error("❌ 更新测试失败")
                return
        except Exception as e:
            logger.exception(f"❌ 更新测试失败: {str(e)}")
            return
        
        # 测试4: 删除功能
        try:
            delete_result = test_delete_functionality(db_session, portfolio_id)
            if delete_result:
                logger.info("✅ 删除测试通过")
            else:
                logger.error("❌ 删除测试失败")
                return
        except Exception as e:
            logger.exception(f"❌ 删除测试失败: {str(e)}")
            return
        
        logger.info("🎉 所有测试用例通过！SQLAlchemy ORM功能正常工作。")
        
    except Exception as e:
        logger.exception(f"测试过程中发生未预期的错误: {str(e)}")
    finally:
        if db_session:
            db_session.close()
        logger.info("测试完成")

if __name__ == "__main__":
    main()