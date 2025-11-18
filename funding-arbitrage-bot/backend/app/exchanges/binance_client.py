import logging
from typing import Dict, Optional, List
from decimal import Decimal
from binance.client import Client
from binance.exceptions import BinanceAPIException
from ..config import settings

logger = logging.getLogger(__name__)


class BinanceClient:
    """币安客户端 - 真实数据版"""
    
    def __init__(self):
        self.client = None
        self.initialized = False
        logger.info("币安客户端初始化")
    
    async def initialize(self):
        """初始化客户端"""
        try:
            # 如果没有配置 API 密钥，使用公开 API
            if settings.binance_api_key and settings.binance_api_secret:
                self.client = Client(
                    settings.binance_api_key,
                    settings.binance_api_secret,
                    testnet=settings.binance_testnet
                )
                logger.info("币安客户端已初始化（使用 API 密钥）")
            else:
                # 使用公开 API（只读数据）
                self.client = Client()
                logger.info("币安客户端已初始化（公开 API，只读模式）")
            
            self.initialized = True
            
        except Exception as e:
            logger.error(f"币安客户端初始化失败: {e}")
            self.initialized = False
    
    async def get_funding_rate(self, symbol: str) -> Optional[Decimal]:
        """获取单个交易对的资金费率"""
        try:
            # 币安的 symbol 格式
            symbol = symbol.upper()
            
            # 获取资金费率
            funding_info = self.client.futures_funding_rate(symbol=symbol, limit=1)
            
            if funding_info and len(funding_info) > 0:
                rate = Decimal(str(funding_info[0]['fundingRate']))
                logger.debug(f"币安 {symbol} 费率: {rate}")
                return rate
            
            return None
            
        except BinanceAPIException as e:
            logger.error(f"获取币安费率失败 {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"获取币安费率异常 {symbol}: {e}")
            return None
    
    async def get_all_funding_rates(self) -> Dict[str, Decimal]:
        """获取所有交易对的资金费率"""
        try:
            # 主流交易对列表
            symbols = [
                'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT',
                'ADAUSDT', 'DOGEUSDT', 'XRPUSDT', 'DOTUSDT',
                'MATICUSDT', 'LINKUSDT', 'AVAXUSDT', 'UNIUSDT'
            ]
            
            rates = {}
            for symbol in symbols:
                rate = await self.get_funding_rate(symbol)
                if rate is not None:
                    rates[symbol] = rate
            
            logger.info(f"获取到 {len(rates)} 个币安费率")
            return rates
            
        except Exception as e:
            logger.error(f"获取币安所有费率失败: {e}")
            return {}
    
    async def get_price(self, symbol: str) -> Optional[Decimal]:
        """获取当前价格"""
        try:
            symbol = symbol.upper()
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            
            if ticker:
                price = Decimal(str(ticker['price']))
                return price
            
            return None
            
        except Exception as e:
            logger.error(f"获取币安价格失败 {symbol}: {e}")
            return None
    
    async def get_balance(self) -> Optional[Decimal]:
        """获取余额（需要 API 密钥）"""
        if not settings.binance_api_key:
            return Decimal('0')  # 无 API 密钥返回 0
        
        try:
            account = self.client.futures_account()
            balance = Decimal(str(account['totalWalletBalance']))
            return balance
        except Exception as e:
            logger.error(f"获取币安余额失败: {e}")
            return Decimal('0')
    
    async def get_position(self, symbol: str) -> Optional[Dict]:
        """获取持仓（需要 API 密钥）"""
        if not settings.binance_api_key:
            return None
        
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            if positions:
                return positions[0]
            return None
        except Exception as e:
            logger.error(f"获取币安持仓失败: {e}")
            return None
    
    async def create_order(self, **kwargs) -> Optional[Dict]:
        """创建订单（需要 API 密钥，暂不实现）"""
        logger.warning("创建订单功能未实现（安全考虑）")
        return None
    
    async def get_liquidation_price(self, symbol: str) -> Optional[Decimal]:
        """获取爆仓价格"""
        return None
    
    async def set_stop_loss_take_profit(self, **kwargs):
        """设置止损止盈"""
        pass
    
    async def close(self):
        """关闭连接"""
        pass
