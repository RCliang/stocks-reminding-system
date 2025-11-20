import unittest
import json
from prompts import get_trading_prompt
import sys
sys.path.append('../future')
from utils import get_ai_recommendation


class TestPrompts(unittest.TestCase):
    
    def test_get_trading_prompt(self):
        # 准备测试数据 - market_state参数
        market_state = {
            "SPY": {
                "price": 450.25,
                "change_24h": 1.25,
                "indicators": {
                    "sma_7": 448.50,
                    "sma_14": 445.75,
                    "rsi_14": 65.8
                }
            },
            "QQQ": {
                "price": 375.80,
                "change_24h": -0.75,
                "indicators": {
                    "sma_7": 377.20,
                    "sma_14": 379.50,
                    "rsi_14": 42.3
                }
            },
            "IWM": {
                "price": 225.30,
                "change_24h": 0.95,
                "indicators": None  # 测试没有指标的情况
            }
        }
        
        # 准备测试数据 - account_info参数
        account_info = {
            "initial_capital": 100000.00,
            "total_return": 8.5
        }
        
        # 准备测试数据 - portfolio参数
        portfolio = {
            "total_value": 108500.00,
            "cash": 50000.00,
            "positions": [
                {
                    "etf": "SPY",
                    "side": "long",
                    "quantity": 100.0,
                    "avg_price": 445.50
                },
                {
                    "etf": "QQQ",
                    "side": "long",
                    "quantity": 50.0,
                    "avg_price": 380.20
                }
            ]
        }
        
        # 调用函数生成提示词
        prompt = get_trading_prompt(market_state, account_info, portfolio)
        
        # 验证返回值是否为字符串
        self.assertIsInstance(prompt, str)
        
        # 验证提示词中包含所有必要的信息
        self.assertIn("You are a professional eft trader", prompt)
        self.assertIn("MARKET DATA:", prompt)
        self.assertIn("SPY: $450.25 (+1.25%)", prompt)
        self.assertIn("QQQ: $375.80 (-0.75%)", prompt)
        self.assertIn("IWM: $225.30 (+0.95%)", prompt)
        self.assertIn("ACCOUNT STATUS:", prompt)
        self.assertIn("Initial Capital: $100000.00", prompt)
        self.assertIn("Total Value: $108500.00", prompt)
        self.assertIn("Cash: $50000.00", prompt)
        self.assertIn("Total Return: 8.50%", prompt)
        self.assertIn("CURRENT POSITIONS:", prompt)
        self.assertIn("SPY long: 100.0000 @ $445.50", prompt)
        self.assertIn("QQQ long: 50.0000 @ $380.20", prompt)
        self.assertIn("TRADING RULES:", prompt)
        self.assertIn("OUTPUT FORMAT (JSON only):", prompt)
    
    def test_get_trading_prompt_empty_positions(self):
        """测试没有持仓的情况"""
        # 准备测试数据 - 最小化的测试用例，没有持仓
        market_state = {
            "SPY": {
                "price": 450.25,
                "change_24h": 1.25,
                "indicators": {}
            }
        }
        
        account_info = {
            "initial_capital": 100000.00,
            "total_return": 0.0
        }
        
        portfolio = {
            "total_value": 100000.00,
            "cash": 100000.00,
            "positions": []  # 空持仓列表
        }
        
        # 调用函数生成提示词
        prompt = get_trading_prompt(market_state, account_info, portfolio)
        
        # 验证返回值包含None作为持仓信息
        self.assertIn("CURRENT POSITIONS:\n    None", prompt)
    
    def test_get_trading_prompt_format_consistency(self):
        """测试提示词格式一致性"""
        # 准备两组不同的测试数据
        market_state1 = {
            "SPY": {
                "price": 450.25,
                "change_24h": 1.25,
                "indicators": None
            }
        }
        
        market_state2 = {
            "QQQ": {
                "price": 375.80,
                "change_24h": -0.75,
                "indicators": None
            }
        }
        
        # 基本账户信息
        base_account_info = {"initial_capital": 100000.00, "total_return": 0.0}
        base_portfolio = {"total_value": 100000.00, "cash": 100000.00, "positions": []}
        
        # 生成两个提示词
        prompt1 = get_trading_prompt(market_state1, base_account_info, base_portfolio)
        prompt2 = get_trading_prompt(market_state2, base_account_info, base_portfolio)
        
        # 验证提示词结构一致（除了市场数据部分）
        parts1 = prompt1.split("MARKET DATA:\n")
        parts2 = prompt2.split("MARKET DATA:\n")
        
        # 验证第一部分（指令部分）相同
        self.assertEqual(parts1[0], parts2[0])
        
        # 验证后半部分（账户信息和规则）相同
        # 提取MARKET DATA之后的部分，但不包括市场数据本身
        after_market1 = "MARKET DATA:\n".join(parts1[1:]).split("\n\nACCOUNT STATUS:")
        after_market2 = "MARKET DATA:\n".join(parts2[1:]).split("\n\nACCOUNT STATUS:")
        
        # 验证账户状态和之后的部分相同
        if len(after_market1) > 1 and len(after_market2) > 1:
            self.assertEqual(after_market1[1], after_market2[1])


if __name__ == "__main__":
    # 运行所有测试
    # unittest.main()

    # 演示函数使用示例
    print("\n--- 示例输出 ---")
    
    # 创建一个简单的示例
    sample_market_state = {
        "SPY": {
            "price": 450.25,
            "change_24h": 1.25,
            "indicators": {
                "sma_7": 448.50,
                "sma_14": 445.75,
                "rsi_14": 65.8
            }
        }
    }
    
    sample_account_info = {
        "initial_capital": 100000.00,
        "total_return": 5.2
    }
    
    sample_portfolio = {
        "total_value": 105200.00,
        "cash": 50000.00,
        "positions": [
            {
                "etf": "SPY",
                "side": "long",
                "quantity": 100.0,
                "avg_price": 445.50
            }
        ]
    }
    
    # 生成并打印示例提示词
    sample_prompt = get_trading_prompt(sample_market_state, sample_account_info, sample_portfolio)
    print(f"sample_prompt:\n{sample_prompt}")
    reasoning_content, content = get_ai_recommendation(sample_prompt)
    print(f"reasoning_content:\n{reasoning_content}")
    print(f"content:\n{content}")
