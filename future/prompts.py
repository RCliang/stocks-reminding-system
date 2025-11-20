def get_trading_prompt(market_state: dict, account_info: dict, portfolio: dict) -> str:

    prompt = f"""你是一名专业的ETF交易员。请分析市场并做出交易决策。

    市场数据如下:
    """
    for etf, data in market_state.items():
        prompt += f"{etf}: ¥{data['price']:.2f} ({data['change_24h']:+.2f}%)\n"
        if 'indicators' in data and data['indicators']:
            indicators = data['indicators']
            prompt += f"  SMA7: ¥{indicators.get('sma_7', 0):.2f}, SMA14: ¥{indicators.get('sma_14', 0):.2f}, RSI: {indicators.get('rsi_14', 0):.1f}\n"

    prompt += f"""
    账户状态如下:
    - 初始资金: ¥{account_info['initial_capital']:.2f}
    - 总价值: ¥{portfolio['total_value']:.2f}
    - 现金: ¥{portfolio['cash']:.2f}
    - 总收益率: {account_info['total_return']:.2f}%

    当前持仓如下:
    """
    if portfolio['positions']:
        for pos in portfolio['positions']:
            # 从持仓数据中计算平均价格（如果没有直接提供）
            avg_price = pos['value'] / pos['quantity'] if pos['quantity'] > 0 else 0
            prompt += f"- {pos['name']} ({pos['code']}): {pos['quantity']:.4f} 股 @ ¥{avg_price:.2f} \n"
    else:
        prompt += "None\n"
            
    prompt += """
    交易规则如下:
    1. 信号: buy_to_enter (long), sell(if hold), close_position, hold
    2. 风险管理:
    - 最大持仓数量: 3个
    - 每次交易风险: 1-5%
    3. 仓位-sizing:
    - 保守: 1-2%风险
    - 中等: 2-4%风险
    - 激进: 4-5%风险
    4. 退出策略:
    - 快速关闭亏损持仓
    - 让利润奔跑
    - 使用技术指标

    输出格式 (仅JSON):
    ```json
    {
    "SH.512150": {
        "signal": "buy_to_enter|sell|hold|close_position",
        "quantity": 0.5,
        "leverage": 10,
        "profit_target": 45000.0,
        "stop_loss": 42000.0,
        "confidence": 0.75,
        "justification": "Brief reason"
    }
    }
    ```

    分析并仅输出JSON格式。
    """
    return prompt