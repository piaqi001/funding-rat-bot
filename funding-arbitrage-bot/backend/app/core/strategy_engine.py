import logging
from typing import Dict, Optional, Tuple
from decimal import Decimal
from datetime import datetime
from .data_collector import DataCollector

logger = logging.getLogger(__name__)


class StrategyEngine:
    """策略引擎 - 识别套利机会并生成交易信号"""
    
    def __init__(self, data_collector: DataCollector):
        self.data_collector = data_collector
        
        # 初始化配置（从 settings 加载）
        from ..config import settings
        self.config = {
            'funding_rate_threshold': settings.default_funding_rate_threshold,
            'position_size_per_order': settings.default_position_size_per_order,
            'max_total_position': settings.default_max_total_position,
            'max_imbalance': settings.default_max_imbalance,
            'total_leverage': settings.default_total_leverage,
            'stop_loss_percent': settings.default_stop_loss_percent,
            'take_profit_percent': settings.default_take_profit_percent,
        }
        
        logger.info("策略引擎初始化成功")
    
    def update_config(self, new_config: dict):
        """更新配置"""
        self.config.update(new_config)
        logger.info(f"配置已更新: {new_config}")
    
    def check_arbitrage_opportunity(self, symbol: str) -> Optional[Dict]:
        """检查是否存在套利机会"""
        try:
            rate_diff = self.data_collector.get_rate_diff(symbol)
            if not rate_diff:
                return None
            
            current_diff = Decimal(str(rate_diff.get('current_diff', 0)))
            avg_8h_diff = Decimal(str(rate_diff.get('avg_8h_diff', 0)))
            threshold = Decimal(str(self.config['funding_rate_threshold']))
            
            if abs(current_diff) < threshold or abs(avg_8h_diff) < threshold:
                return None
            
            if current_diff > 0:
                strategy_type = 'lighter_short_binance_long'
                lighter_side = 'short'
                binance_side = 'long'
            else:
                strategy_type = 'lighter_long_binance_short'
                lighter_side = 'long'
                binance_side = 'short'
            
            return {
                'symbol': symbol,
                'strategy_type': strategy_type,
                'lighter_side': lighter_side,
                'binance_side': binance_side,
                'current_diff': float(current_diff),
                'avg_8h_diff': float(avg_8h_diff),
                'lighter_rate': rate_diff.get('lighter_rate', 0),
                'binance_rate': rate_diff.get('binance_rate', 0),
                'expected_profit': float(abs(avg_8h_diff)),
            }
        except Exception as e:
            logger.error(f"检查套利机会失败: {e}")
            return None
    
    def get_all_opportunities(self) -> list:
        """获取所有交易对的套利机会"""
        opportunities = []
        try:
            all_rate_diffs = self.data_collector.get_all_rate_diffs()
            for symbol in all_rate_diffs.keys():
                opportunity = self.check_arbitrage_opportunity(symbol)
                if opportunity:
                    opportunities.append(opportunity)
        except Exception as e:
            logger.error(f"获取所有套利机会失败: {e}")
        return opportunities
    
    def calculate_position_size(self, symbol: str, current_position: Decimal) -> Tuple[Decimal, int]:
        """计算建仓大小"""
        max_position = Decimal(str(self.config['max_total_position']))
        available = max_position - current_position
        if available <= 0:
            return Decimal('0'), 0
        position_size = min(Decimal(str(self.config['position_size_per_order'])), available)
        leverage = self.config['total_leverage']
        return position_size, leverage
    
    def calculate_stop_loss_take_profit(self, entry_price: Decimal, side: str) -> Tuple[Decimal, Decimal]:
        """计算止损止盈价格"""
        stop_loss_pct = Decimal(str(self.config['stop_loss_percent']))
        take_profit_pct = Decimal(str(self.config['take_profit_percent']))
        if side == 'long':
            stop_loss = entry_price * (1 - stop_loss_pct)
            take_profit = entry_price * (1 + take_profit_pct)
        else:
            stop_loss = entry_price * (1 + stop_loss_pct)
            take_profit = entry_price * (1 - take_profit_pct)
        return stop_loss, take_profit
    
    def should_close_position(self, symbol: str, entry_rate_diff: Decimal, current_holding_hours: float) -> bool:
        """判断是否应该平仓"""
        try:
            rate_diff = self.data_collector.get_rate_diff(symbol)
            if not rate_diff:
                return False
            current_diff = Decimal(str(rate_diff.get('current_diff', 0)))
            if (entry_rate_diff > 0 and current_diff < 0) or (entry_rate_diff < 0 and current_diff > 0):
                logger.info(f"费率差反转，建议平仓: {symbol}")
                return True
            threshold = Decimal(str(self.config['funding_rate_threshold']))
            if abs(current_diff) < threshold / 2:
                logger.info(f"费率差缩小，建议平仓: {symbol}")
                return True
            if current_holding_hours > 168:
                logger.info(f"持仓时间过长，建议平仓: {symbol}")
                return True
            return False
        except Exception as e:
            logger.error(f"判断是否平仓失败: {e}")
            return False
