# 投资组合和持仓数据表设计文档

## 设计概述

根据 `auto_recommendation.py` 中的 `sample_portfolio` 和 `sample_account_info` 数据结构，设计了一套完整的数据库表结构，用于存储投资组合信息和持仓记录，支持按日期和账户ID进行数据查询和历史追踪。

## 数据模型设计

### 1. 投资组合表 (portfolios)

**表结构说明：**

| 字段名 | 数据类型 | 约束 | 描述 |
|-------|---------|-----|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| portfolio_id | TEXT | NOT NULL UNIQUE | 投资组合唯一标识 |
| account_id | TEXT | NOT NULL | 账户ID，用于区分不同用户 |
| total_value | REAL | NOT NULL | 投资组合总价值 |
| cash | REAL | NOT NULL | 现金余额 |
| initial_capital | REAL | NOT NULL | 初始资金（来自account_info） |
| total_return | REAL | NOT NULL | 总收益（来自account_info） |
| date | TEXT | NOT NULL | 记录日期（YYYY-MM-DD格式） |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间戳 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间戳 |

**索引设计：**
- 唯一索引：`(account_id, date)` - 确保每个账户每天只有一条投资组合记录
- 普通索引：`account_id`, `date` - 加速按账户和日期的查询

### 2. 持仓表 (positions)

**表结构说明：**

| 字段名 | 数据类型 | 约束 | 描述 |
|-------|---------|-----|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| position_id | TEXT | NOT NULL UNIQUE | 持仓记录唯一标识 |
| portfolio_id | TEXT | NOT NULL | 关联投资组合ID（外键） |
| account_id | TEXT | NOT NULL | 账户ID |
| code | TEXT | NOT NULL | 股票代码/ETF代码 |
| name | TEXT | NOT NULL | 股票名称/ETF名称 |
| quantity | REAL | NOT NULL | 持仓数量 |
| price | REAL | NOT NULL | 持仓价格（买入均价） |
| value | REAL | NOT NULL | 持仓价值（quantity * price） |
| market_price | REAL | NOT NULL | 当前市场价格 |
| profit_loss | REAL | NOT NULL | 盈亏金额 |
| profit_loss_pct | REAL | NOT NULL | 盈亏百分比 |
| date | TEXT | NOT NULL | 记录日期（YYYY-MM-DD格式） |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间戳 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间戳 |

**索引设计：**
- 外键：`portfolio_id` 关联 `portfolios` 表，支持级联删除
- 普通索引：`portfolio_id`, `account_id`, `code`, `date` - 加速多维度查询

## 功能说明

### 主要功能

1. **数据存储**：将投资组合和持仓信息持久化到SQLite数据库
2. **历史追踪**：按日期记录每个账户的投资组合状态
3. **关联查询**：支持通过portfolio_id查询关联的持仓信息
4. **多维度查询**：支持按账户ID、日期范围、股票代码等条件查询

### 核心函数

1. **insert_portfolio_and_positions**：插入投资组合和持仓数据
   - 自动生成唯一的portfolio_id和position_id
   - 支持同时插入投资组合和多个持仓记录
   - 自动记录当前日期

2. **get_portfolios_by_account**：查询指定账户的投资组合历史
   - 支持按日期范围筛选
   - 按日期降序排序

3. **get_positions_by_portfolio**：查询指定投资组合的持仓明细
   - 通过portfolio_id关联查询

## 与主程序集成方法

### 示例集成代码

```python
# 在auto_recommendation.py中集成数据库功能

from db_schema import insert_portfolio_and_positions, get_portfolios_by_account
import sqlite3

def main():
    # 现有代码...
    
    # 构建投资组合和账户信息
    sample_portfolio = {
        "total_value": 0.00,
        "cash": 120000.00,
        "positions": []
    }
    sample_account_info = {
        "initial_capital": 120000.00,
        "total_return": 0.0
    }
    
    # 集成数据库功能 - 存储投资组合数据
    conn = sqlite3.connect('investment_portfolio.db')
    account_id = "user_001"  # 可以从配置或用户输入获取
    
    # 插入数据
    portfolio_id = insert_portfolio_and_positions(
        conn, 
        account_id, 
        sample_portfolio, 
        sample_account_info
    )
    print(f"投资组合已保存，ID: {portfolio_id}")
    
    # 查询历史数据（可选）
    portfolios = get_portfolios_by_account(conn, account_id)
    print(f"账户{account_id}共有{len(portfolios)}条投资组合记录")
    
    conn.close()
    
    # 后续代码...
```

## 数据模型扩展建议

### 1. 交易记录表

未来可以考虑添加交易记录表，用于追踪每笔交易：

```sql
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT NOT NULL UNIQUE,
    account_id TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    transaction_type TEXT NOT NULL,  -- 'buy' 或 'sell'
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    amount REAL NOT NULL,
    transaction_date TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. 账户信息表

添加账户信息表，存储用户更详细的账户设置：

```sql
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    display_name TEXT,
    risk_level TEXT,  -- 风险等级
    strategy_type TEXT,  -- 策略类型
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3. 性能优化建议

1. **定期清理**：对于大量历史数据，考虑定期归档或清理
2. **索引优化**：根据实际查询模式调整索引策略
3. **数据压缩**：对于历史数据可以考虑压缩存储

## 使用说明

1. 首先运行 `db_schema.py` 初始化数据库和表结构：
   ```bash
   python db_schema.py
   ```

2. 在主程序中导入相应的函数并集成

3. 数据库文件默认保存为 `investment_portfolio.db`，可以根据需要修改路径

## 数据安全考虑

1. 敏感信息（如账户凭证）不建议直接存储在数据库中
2. 考虑对数据库文件设置访问权限
3. 定期备份数据库文件