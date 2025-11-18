import logging
import asyncio
import time
from typing import Dict, Optional
from decimal import Decimal
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DataCollector:
    """数据采集器 - 负责采集和管理费率数据"""
    
    def __init__(self):
        self.lighter_client = None
        self.binance_client = None
        self.running = False
        
        # 存储费率数据
        self.funding_rates = {
            'lighter': {},  # {symbol: {'rate': float, 'timestamp': int}}
            'binance': {}
        }
        
        logger.info("数据采集器初始化")
    
    async def initialize(self):
        """初始化采集器"""
        from ..exchanges.lighter_client import LighterClient
        from ..exchanges.binance_client import BinanceClient
        
        self.lighter_client = LighterClient()
        self.binance_client = BinanceClient()
        
        await self.lighter_client.initialize()
        await self.binance_client.initialize()
        
        logger.info("数据采集器初始化成功")
    
    async def start(self):
        """启动数据采集"""
        self.running = True
        logger.info("数据采集器启动")
        
        while self.running:
            try:
                await self.collect_funding_rates()
                await asyncio.sleep(60)  # 每分钟采集一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"数据采集循环错误: {e}")
                await asyncio.sleep(10)
    
    async def stop(self):
        """停止数据采集"""
        self.running = False
        logger.info("数据采集器停止")
    
    async def collect_funding_rates(self):
        """采集资金费率数据"""
        try:
            # 并发获取两个交易所的费率
            lighter_rates_task = asyncio.create_task(
                self.lighter_client.get_all_funding_rates()
            )
            binance_rates_task = asyncio.create_task(
                self.binance_client.get_all_funding_rates()
            )
            
            # 等待结果，即使有异常也继续
            results = await asyncio.gather(
                lighter_rates_task,
                binance_rates_task,
                return_exceptions=True
            )
            
            lighter_rates = results[0] if not isinstance(results[0], Exception) else {}
            binance_rates = results[1] if not isinstance(results[1], Exception) else {}
            
            # 处理异常
            if isinstance(results[0], Exception):
                logger.error(f"获取 Lighter 费率失败: {results[0]}")
            
            if isinstance(results[1], Exception):
                logger.error(f"获取币安费率失败: {results[1]}")
            
            # 保存数据
            timestamp = int(time.time())
            
            # 获取所有交易对
            all_symbols = set(list(lighter_rates.keys()) + list(binance_rates.keys()))
            
            for symbol in all_symbols:
                lighter_rate = lighter_rates.get(symbol)
                binance_rate = binance_rates.get(symbol)
                
                if lighter_rate is not None:
                    self.funding_rates['lighter'][symbol] = {
                        'rate': float(lighter_rate),
                        'timestamp': timestamp
                    }
                
                if binance_rate is not None:
                    self.funding_rates['binance'][symbol] = {
                        'rate': float(binance_rate),
                        'timestamp': timestamp
                    }
            
            logger.info(f"费率采集完成: Lighter {len(lighter_rates)}, 币安 {len(binance_rates)}")
            
        except Exception as e:
            logger.error(f"采集资金费率失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def get_rate_diff(self, symbol: str) -> Optional[Dict]:
        """获取指定交易对的费率差"""
        try:
            lighter_data = self.funding_rates['lighter'].get(symbol)
            binance_data = self.funding_rates['binance'].get(symbol)
            
            if not lighter_data or not binance_data:
                return None
            
            lighter_rate = lighter_data['rate']
            binance_rate = binance_data['rate']
            
            # 计算费率差 (Lighter - 币安)
            current_diff = lighter_rate - binance_rate
            
            # 简化：8小时平均差 = 当前差 (实际应该查历史数据)
            avg_8h_diff = current_diff
            
            # 获取价格（从币安）
            price = 0.0
            
            return {
                'symbol': symbol,
                'lighter_rate': lighter_rate,
                'binance_rate': binance_rate,
                'current_diff': current_diff,
                'avg_8h_diff': avg_8h_diff,
                'price': price
            }
            
        except Exception as e:
            logger.error(f"计算费率差失败 {symbol}: {e}")
            return None
    
    def get_all_rate_diffs(self) -> Dict[str, Dict]:
        """获取所有交易对的费率差"""
        rate_diffs = {}
        
        # 获取所有交易对
        all_symbols = set(
            list(self.funding_rates['lighter'].keys()) +
            list(self.funding_rates['binance'].keys())
        )
        
        for symbol in all_symbols:
            diff = self.get_rate_diff(symbol)
            if diff:
                rate_diffs[symbol] = diff
        
        return rate_diffs
