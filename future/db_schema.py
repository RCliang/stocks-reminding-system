# 投资组合和持仓数据表设计 - 使用SQLAlchemy ORM

'''根据portfolio和account_info数据结构设计的数据表方案，使用SQLAlchemy ORM实现'''

"""
数据库架构定义
使用SQLAlchemy ORM框架

依赖安装：
pip install -r requirements.txt

配置说明：
1. 数据库类型：SQLite3
2. 默认数据库文件：investment_portfolio.db
3. 支持的操作：创建表、插入、查询、更新、删除
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index, create_engine, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import datetime
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 创建基类
Base = declarative_base()

# 定义投资组合模型
class Portfolio(Base):
    __tablename__ = 'portfolios'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(String, nullable=False, unique=True, index=True)  # 投资组合唯一标识
    account_id = Column(String, nullable=False, index=True)  # 账户ID
    total_value = Column(Float, nullable=False)  # 总价值
    cash = Column(Float, nullable=False)  # 现金
    initial_capital = Column(Float, nullable=False)  # 初始资金
    total_return = Column(Float, nullable=False)  # 总收益
    date = Column(String, nullable=False, index=True)  # 记录日期
    created_at = Column(DateTime, default=func.now())  # 创建时间
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())  # 更新时间
    
    # 关系定义
    positions = relationship("Position", back_populates="portfolio", cascade="all, delete-orphan")
    
    # 复合索引
    __table_args__ = (
        Index('idx_account_date', 'account_id', 'date'),
    )

# 定义持仓模型
class Position(Base):
    __tablename__ = 'positions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(String, nullable=False, unique=True, index=True)  # 持仓唯一标识
    portfolio_id = Column(String, ForeignKey('portfolios.portfolio_id', ondelete='CASCADE'), nullable=False, index=True)  # 关联投资组合ID
    account_id = Column(String, nullable=False, index=True)  # 账户ID
    code = Column(String, nullable=False, index=True)  # 股票代码
    name = Column(String, nullable=False)  # 股票名称
    quantity = Column(Float, nullable=False)  # 持仓数量
    price = Column(Float, nullable=False)  # 持仓价格
    value = Column(Float, nullable=False)  # 持仓价值
    market_price = Column(Float, nullable=False)  # 当前市场价
    profit_loss = Column(Float, nullable=False)  # 盈亏
    profit_loss_pct = Column(Float, nullable=False)  # 盈亏百分比
    date = Column(String, nullable=False, index=True)  # 记录日期
    created_at = Column(DateTime, default=func.now())  # 创建时间
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())  # 更新时间
    
    # 关系定义
    portfolio = relationship("Portfolio", back_populates="positions")
    
    # 复合索引
    __table_args__ = (
        Index('idx_portfolio_code', 'portfolio_id', 'code'),
    )

# 定义股票日线数据
class Stock(Base):
    __tablename__ = 'stocks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    time_key = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    pe_ratio = Column(Float, nullable=True)
    volume = Column(Float, nullable=False)
    turnover_rate = Column(Float, nullable=True)
    turnover = Column(Float, nullable=True)
    change_rate = Column(Float, nullable=True)

    class Config:
        orm_mode = True

# 数据库连接类
class DatabaseManager:
    def __init__(self, db_file='investment_portfolio.db'):
        self.db_file = db_file
        self._engine = None
        self.SessionLocal = None
    
    def get_engine(self):
        """
        获取数据库引擎实例
        
        配置选项说明：
        - echo=False: 关闭SQL语句日志输出，生产环境建议设置为False
        - 可以根据需要调整连接池参数：pool_size, max_overflow等
        """
        if self._engine is None:
            # SQLite连接配置，可根据需要调整
            self._engine = create_engine(
                f'sqlite:///{self.db_file}',
                echo=False,        # 是否输出SQL语句
                pool_pre_ping=True, # 连接池健康检查
                pool_size=5,       # 连接池大小
                max_overflow=10    # 最大溢出连接数
            )
        return self._engine
    
    def init_db(self):
        """初始化数据库连接"""
        try:
            # 获取数据库引擎
            engine = self.get_engine()
            # 创建所有表
            Base.metadata.create_all(bind=engine)
            # 创建会话工厂
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            logger.info(f"成功初始化数据库: {self.db_file}")
            return True
        except Exception as e:
            logger.exception(f"数据库初始化失败: {str(e)}")
            return False
    
    def get_db(self):
        """获取数据库会话"""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    def create_session(self):
        """创建数据库会话（直接使用）"""
        if not self.SessionLocal:
            self.init_db()
        return self.SessionLocal()

# 数据操作函数
def insert_portfolio_and_positions(db_session, account_id, portfolio_data, account_info, positions_data=None):
    """插入投资组合和持仓数据
    
    参数:
        db_session: 数据库会话对象
        account_id: 账户ID
        portfolio_data: 投资组合数据(dict)
        account_info: 账户信息数据(dict)
        positions_data: 持仓数据列表(可选)
    """
    try:
        # 生成当前日期
        current_date = datetime.datetime.now().strftime('%Y-%m-%d')
        # 生成唯一标识符
        portfolio_id = f"port_{account_id}_{current_date}_{int(time.time())}"
        
        # 创建投资组合对象
        portfolio = Portfolio(
            portfolio_id=portfolio_id,
            account_id=account_id,
            total_value=portfolio_data.get('total_value', 0.0),
            cash=portfolio_data.get('cash', 0.0),
            initial_capital=account_info.get('initial_capital', 0.0),
            total_return=account_info.get('total_return', 0.0),
            date=current_date
        )
        
        # 添加到会话
        db_session.add(portfolio)
        
        # 添加持仓数据(如果有)
        if positions_data:
            for position in positions_data:
                position_id = f"pos_{portfolio_id}_{position['code']}_{int(time.time())}"
                position_obj = Position(
                    position_id=position_id,
                    portfolio_id=portfolio_id,
                    account_id=account_id,
                    code=position.get('code', ''),
                    name=position.get('name', ''),
                    quantity=position.get('quantity', 0.0),
                    price=position.get('price', 0.0),
                    value=position.get('value', 0.0),
                    market_price=position.get('market_price', 0.0),
                    profit_loss=position.get('profit_loss', 0.0),
                    profit_loss_pct=position.get('profit_loss_pct', 0.0),
                    date=current_date
                )
                db_session.add(position_obj)
        
        # 提交事务
        db_session.commit()
        logger.info(f"成功插入投资组合数据，ID: {portfolio_id}")
        return portfolio_id
    except Exception as e:
        db_session.rollback()
        logger.exception(f"插入投资组合数据失败: {str(e)}")
        raise

def get_portfolios_by_account(db_session, account_id, start_date=None, end_date=None):
    """查询指定账户的投资组合历史
    
    参数:
        db_session: 数据库会话对象
        account_id: 账户ID
        start_date: 开始日期
        end_date: 结束日期
    
    返回:
        投资组合列表
    """
    try:
        query = db_session.query(Portfolio).filter(Portfolio.account_id == account_id)
        
        if start_date:
            query = query.filter(Portfolio.date >= start_date)
        if end_date:
            query = query.filter(Portfolio.date <= end_date)
        
        # 按日期降序排序
        portfolios = query.order_by(Portfolio.date.desc()).all()
        logger.info(f"查询到账户{account_id}的{len(portfolios)}个投资组合记录")
        return portfolios
    except Exception as e:
        logger.exception(f"查询投资组合历史失败: {str(e)}")
        raise

def get_positions_by_portfolio(db_session, portfolio_id):
    """查询指定投资组合的持仓
    
    参数:
        db_session: 数据库会话对象
        portfolio_id: 投资组合ID
    
    返回:
        持仓列表
    """
    try:
        positions = db_session.query(Position).filter(Position.portfolio_id == portfolio_id).all()
        logger.info(f"查询到投资组合{portfolio_id}的{len(positions)}个持仓记录")
        return positions
    except Exception as e:
        logger.exception(f"查询持仓数据失败: {str(e)}")
        raise

def update_portfolio(db_session, portfolio_id, update_data):
    """更新投资组合数据
    
    参数:
        db_session: 数据库会话对象
        portfolio_id: 投资组合ID
        update_data: 要更新的数据字典
    """
    try:
        portfolio = db_session.query(Portfolio).filter(Portfolio.portfolio_id == portfolio_id).first()
        if portfolio:
            for key, value in update_data.items():
                if hasattr(portfolio, key):
                    setattr(portfolio, key, value)
            db_session.commit()
            logger.info(f"成功更新投资组合{portfolio_id}")
            return True
        else:
            logger.warning(f"未找到投资组合{portfolio_id}")
            return False
    except Exception as e:
        db_session.rollback()
        logger.exception(f"更新投资组合失败: {str(e)}")
        raise

def delete_portfolio(db_session, portfolio_id):
    """删除投资组合（会级联删除相关持仓）
    
    参数:
        db_session: 数据库会话对象
        portfolio_id: 投资组合ID
    """
    try:
        portfolio = db_session.query(Portfolio).filter(Portfolio.portfolio_id == portfolio_id).first()
        if portfolio:
            db_session.delete(portfolio)
            db_session.commit()
            logger.info(f"成功删除投资组合{portfolio_id}")
            return True
        else:
            logger.warning(f"未找到投资组合{portfolio_id}")
            return False
    except Exception as e:
        db_session.rollback()
        logger.exception(f"删除投资组合失败: {str(e)}")
        raise

def insert_position(db_session, portfolio_id, account_id, position_data):
    """新增单个持仓记录到Position表
    
    参数:
        db_session: 数据库会话对象
        portfolio_id: 投资组合ID
        account_id: 账户ID
        position_data: 持仓数据字典
    
    返回:
        position_id: 创建的持仓记录ID
    """
    try:
        # 验证投资组合是否存在
        portfolio = db_session.query(Portfolio).filter(Portfolio.portfolio_id == portfolio_id).first()
        if not portfolio:
            raise ValueError(f"投资组合{portfolio_id}不存在")
        
        # 生成当前日期
        current_date = datetime.datetime.now().strftime('%Y-%m-%d')
        # 生成唯一标识符
        position_id = f"pos_{portfolio_id}_{position_data['code']}_{int(time.time())}"
        
        # 创建持仓对象
        position = Position(
            position_id=position_id,
            portfolio_id=portfolio_id,
            account_id=account_id,
            code=position_data.get('code', ''),
            name=position_data.get('name', ''),
            quantity=position_data.get('quantity', 0.0),
            price=position_data.get('price', 0.0),
            value=position_data.get('value', 0.0),
            market_price=position_data.get('market_price', 0.0),
            profit_loss=position_data.get('profit_loss', 0.0),
            profit_loss_pct=position_data.get('profit_loss_pct', 0.0),
            date=current_date
        )
        
        # 添加到会话
        db_session.add(position)
        # 提交事务
        db_session.commit()
        logger.info(f"成功插入持仓记录，ID: {position_id}")
        return position_id
    except Exception as e:
        db_session.rollback()
        logger.exception(f"插入持仓记录失败: {str(e)}")
        raise

def get_stock_data(db_session, stock_code):
    """查询股票数据
    参数:
        db_session: 数据库会话对象
        stock_code: 股票代码
    返回:
        股票数据字典
    """
    try:
        stock = db_session.query(Stock).filter(Stock.code == stock_code).first()
        if stock:
            return stock.__dict__
        else:
            logger.warning(f"未找到股票{stock_code}")
            return None
    except Exception as e:
        logger.exception(f"查询股票数据失败: {str(e)}")
        raise

def update_stock(db_session, stock_data):
    """更新股票数据
    
    参数:
        db_session: 数据库会话对象
        stock_data: 股票数据字典
    """
    try:
        stock = db_session.query(Stock).filter(Stock.code == stock_data['code']).first()
        if stock:
            for key, value in stock_data.items():
                if hasattr(stock, key):
                    setattr(stock, key, value)
            db_session.commit()
            logger.info(f"成功更新股票{stock_data['code']}")
            return True
        else:
            logger.warning(f"未找到股票{stock_data['code']}")
            return False
    except Exception as e:
        db_session.rollback()
        logger.exception(f"更新股票数据失败: {str(e)}")
        raise

def delete_stock_data(db_session, stock_code):
    """删除股票数据
    
    参数:
        db_session: 数据库会话对象
        stock_code: 股票代码
    """
    try:
        stock = db_session.query(Stock).filter(Stock.code == stock_code).first()
        if stock:
            db_session.delete(stock)
            db_session.commit()
            logger.info(f"成功删除股票{stock_code}")
            return True
        else:
            logger.warning(f"未找到股票{stock_code}")
            return False
    except Exception as e:
        db_session.rollback()
        logger.exception(f"删除股票数据失败: {str(e)}")
        raise

def insert_stock_kline(db_session, stock_data):
    """插入股票数据
    
    参数:
        db_session: 数据库会话对象
        stock_data: 股票数据字典
    """
    try:
        stock = Stock(**stock_data)
        db_session.add(stock)
        db_session.commit()
        logger.info(f"成功插入股票{stock_data['code']}")
        return True
    except Exception as e:
        db_session.rollback()
        logger.exception(f"插入股票数据失败: {str(e)}")
        raise

def get_latest_date_for_stock(db_session, stock_code):
    """查询某个股票在表中最新的日期
    
    参数:
        db_session: 数据库会话对象
        stock_code: 股票代码
    
    返回:
        最新日期字符串，格式为 'YYYY-MM-DD'；若未找到则返回 None
    """
    try:
        latest_record = (
            db_session.query(Position)
            .filter(Position.code == stock_code)
            .order_by(Position.date.desc())
            .first()
        )
        if latest_record:
            logger.info(f"股票 {stock_code} 最新持仓日期为 {latest_record.date}")
            return latest_record.date
        else:
            logger.warning(f"未找到股票 {stock_code} 的持仓记录")
            return None
    except Exception as e:
        logger.exception(f"查询股票 {stock_code} 最新日期失败: {str(e)}")
        raise

def get_positions_by_account(db_session, account_id, start_date=None, end_date=None, code=None):
    """查询指定账户的持仓记录
    
    参数:
        db_session: 数据库会话对象
        account_id: 账户ID
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）
        code: 股票代码（可选）
    
    返回:
        持仓记录列表
    """
    try:
        query = db_session.query(Position).filter(Position.account_id == account_id)
        
        # 添加日期过滤条件
        if start_date:
            query = query.filter(Position.date >= start_date)
        if end_date:
            query = query.filter(Position.date <= end_date)
        
        # 添加股票代码过滤条件
        if code:
            query = query.filter(Position.code == code)
        
        # 按日期降序排序，相同日期按创建时间降序排序
        positions = query.order_by(
            Position.date.desc(),
            Position.created_at.desc()
        ).all()
        
        logger.info(f"查询到账户{account_id}的{len(positions)}条持仓记录")
        return positions
    except Exception as e:
        logger.exception(f"查询持仓记录失败: {str(e)}")
        raise

# 示例使用代码
def example_usage():
    """示例使用方法"""
    # 创建数据库管理器
    db_manager = DatabaseManager('investment_portfolio.db')
    db_manager.init_db()
    
    # 创建会话
    db = db_manager.create_session()
    
    try:
        # 示例数据 - 基于auto_recommendation.py中的结构
        account_id = "user_001"
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
        portfolio_id = insert_portfolio_and_positions(db, account_id, sample_portfolio, sample_account_info)
        print(f"投资组合数据已插入，ID: {portfolio_id}")
        
        # 查询投资组合
        portfolios = get_portfolios_by_account(db, account_id)
        print(f"查询到{len(portfolios)}个投资组合记录")
        
        # 示例1: 新增持仓记录
        print("\n示例1: 新增持仓记录")
        sample_position = {
            "code": "600519",
            "name": "贵州茅台",
            "quantity": 100,
            "price": 1800.00,
            "value": 180000.00,
            "market_price": 1820.00,
            "profit_loss": 2000.00,
            "profit_loss_pct": 1.11
        }
        
        position_id = insert_position(db, portfolio_id, account_id, sample_position)
        print(f"持仓记录已插入，ID: {position_id}")
        
        # 示例2: 再添加一个持仓记录
        sample_position2 = {
            "code": "000001",
            "name": "平安银行",
            "quantity": 500,
            "price": 12.50,
            "value": 6250.00,
            "market_price": 12.80,
            "profit_loss": 150.00,
            "profit_loss_pct": 2.40
        }
        
        position_id2 = insert_position(db, portfolio_id, account_id, sample_position2)
        print(f"第二个持仓记录已插入，ID: {position_id2}")
        
        # 示例3: 查询指定账户的所有持仓记录
        print("\n示例3: 查询指定账户的所有持仓记录")
        all_positions = get_positions_by_account(db, account_id)
        print(f"查询到{len(all_positions)}条持仓记录")
        for pos in all_positions:
            print(f"代码: {pos.code}, 名称: {pos.name}, 数量: {pos.quantity}, 价值: {pos.value:.2f}")
        
        # 示例4: 按股票代码过滤查询
        print("\n示例4: 按股票代码过滤查询")
        filtered_positions = get_positions_by_account(db, account_id, code="600519")
        print(f"查询到{len(filtered_positions)}条持仓记录")
        for pos in filtered_positions:
            print(f"代码: {pos.code}, 名称: {pos.name}, 盈亏: {pos.profit_loss:.2f} ({pos.profit_loss_pct:.2f}%)")
        
        # 更新投资组合总价值以反映新增的持仓
        portfolio = db.query(Portfolio).filter(Portfolio.portfolio_id == portfolio_id).first()
        if portfolio:
            # 计算新的总价值和现金
            total_position_value = sum(pos.value for pos in all_positions)
            new_total_value = portfolio.cash + total_position_value
            update_data = {
                "total_value": new_total_value,
                "cash": portfolio.cash - total_position_value  # 假设现金减少了持仓价值
            }
            update_portfolio(db, portfolio_id, update_data)
            print(f"\n投资组合已更新，新的总价值: {new_total_value:.2f}")
        
        # 关闭会话
    except Exception as e:
        print(f"示例执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if db:
            db.close()

if __name__ == "__main__":
    example_usage()