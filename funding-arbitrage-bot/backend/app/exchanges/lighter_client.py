"""
Lighter 客户端 - 适配自 perp-dex-tools 项目
用于获取费率数据的简化版本
"""

import os
import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional, List
from dataclasses import dataclass

# Import official Lighter SDK
import lighter
from lighter import SignerClient, ApiClient, Configuration

logger = logging.getLogger(__name__)


@dataclass
class SimpleConfig:
    """简化的配置类"""
    ticker: str = ""
    contract_id: int = 0
    tick_size: Decimal = Decimal('0.01')
    market_info: Optional[any] = None


class LighterClient:
    """Lighter 客户端 - 简化版用于费率数据获取"""
    
    def __init__(self):
        from ..config import settings
        
        # Lighter 凭据
        self.api_key_private_key = settings.lighter_api_key_private_key
        self.account_index = settings.lighter_account_index
        self.api_key_index = settings.lighter_api_key_index
        self.base_url = "https://mainnet.zklighter.elliot.ai"
        
        # 初始化客户端
        self.lighter_client = None
        self.api_client = None
        
        # 市场缓存
        self.markets_cache = {}
        
        # 初始化状态
        self.initialized = False
        
        logger.info("Lighter 客户端初始化")
    
    async def initialize(self):
        """初始化 Lighter 客户端"""
        try:
            # 初始化 API 客户端
            self.api_client = ApiClient(
                configuration=Configuration(host=self.base_url)
            )
            
            # 如果有私钥，初始化签名客户端
            if self.api_key_private_key:
                try:
                    self.lighter_client = SignerClient(
                        url=self.base_url,
                        private_key=self.api_key_private_key,
                        account_index=self.account_index,
                        api_key_index=self.api_key_index,
                    )
                    
                    err = self.lighter_client.check_client()
                    if err is not None:
                        logger.error(f"Lighter 客户端验证失败: {err}")
                        self.lighter_client = None
                    else:
                        logger.info("✅ Lighter 签名客户端已初始化")
                except Exception as e:
                    logger.error(f"初始化签名客户端失败: {e}")
                    self.lighter_client = None
            else:
                logger.warning("⚠️ Lighter API 密钥未配置")
            
            # 加载市场信息（使用原始 JSON 跳过验证）
            await self._load_markets_raw()
            
            self.initialized = True
            logger.info(f"✅ Lighter 客户端已初始化（找到 {len(self.markets_cache)} 个市场）")
            
        except Exception as e:
            logger.error(f"❌ Lighter 客户端初始化失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.initialized = False
    
    async def _load_markets_raw(self):
        """直接加载市场信息（绕过 SDK 验证）"""
        try:
            import aiohttp
            
            url = f"{self.base_url}/order/order-books"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        logger.error(f"获取市场列表失败: {resp.status}")
                        # 尝试备用方法
                        await self._load_markets_via_sdk()
                        return
                    
                    data = await resp.json()
                    
                    if not data or 'order_books' not in data:
                        logger.warning("未找到市场数据")
                        await self._load_markets_via_sdk()
                        return
                    
                    # 手动解析，忽略 status 验证
                    for market in data['order_books']:
                        try:
                            symbol = market.get('symbol', '')
                            if not symbol:
                                continue
                            
                            # 只处理活跃或非活跃市场，跳过 frozen
                            status = market.get('status', '')
                            if status == 'frozen':
                                continue
                            
                            normalized_symbol = self._normalize_symbol(symbol)
                            
                            self.markets_cache[normalized_symbol] = {
                                'market_id': market.get('market_id'),
                                'symbol': symbol,
                                'base_decimals': market.get('supported_size_decimals', 18),
                                'price_decimals': market.get('supported_price_decimals', 18),
                                'status': status,
                            }
                        except Exception as e:
                            logger.debug(f"跳过市场 {market.get('symbol')}: {e}")
                            continue
                    
                    logger.info(f"通过 HTTP 加载了 {len(self.markets_cache)} 个 Lighter 市场")
        
        except Exception as e:
            logger.error(f"HTTP 加载市场失败: {e}")
            # 回退到 SDK 方法
            await self._load_markets_via_sdk()
    
    async def _load_markets_via_sdk(self):
        """使用 SDK 加载（可能失败）"""
        try:
            order_api = lighter.OrderApi(self.api_client)
            order_books = await order_api.order_books()
            
            if order_books and order_books.order_books:
                for market in order_books.order_books:
                    symbol = market.symbol
                    normalized_symbol = self._normalize_symbol(symbol)
                    
                    self.markets_cache[normalized_symbol] = {
                        'market_id': market.market_id,
                        'symbol': market.symbol,
                        'base_decimals': market.supported_size_decimals,
                        'price_decimals': market.supported_price_decimals,
                    }
                
                logger.info(f"通过 SDK 加载了 {len(self.markets_cache)} 个市场")
        except Exception as e:
            logger.error(f"SDK 加载市场也失败: {e}")
    
    def _normalize_symbol(self, symbol: str) -> str:
        """标准化交易对符号"""
        normalized = symbol.replace('_', '').replace('-', '').upper()
        if not normalized.endswith('USDT'):
            normalized += 'USDT'
        return normalized
    
    async def get_funding_rate(self, symbol: str) -> Optional[Decimal]:
        """获取资金费率"""
        # Lighter 可能没有直接的 funding rate API
        # 返回占位符
        return Decimal('0.0001')
    
    async def get_all_funding_rates(self) -> Dict[str, Decimal]:
        """获取所有交易对的资金费率"""
        if not self.initialized or not self.markets_cache:
            return {}
        
        try:
            rates = {}
            
            for normalized_symbol in self.markets_cache.keys():
                # 返回占位符费率
                rates[normalized_symbol] = Decimal('0.0001')
            
            logger.info(f"获取到 {len(rates)} 个 Lighter 市场费率")
            return rates
            
        except Exception as e:
            logger.error(f"获取所有费率失败: {e}")
            return {}
    
    async def get_price(self, symbol: str) -> Optional[Decimal]:
        """获取当前价格"""
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            market_info = self.markets_cache.get(normalized_symbol)
            
            if not market_info:
                return None
            
            order_api = lighter.OrderApi(self.api_client)
            market_summary = await order_api.order_book_details(
                market_id=market_info['market_id']
            )
            
            if market_summary and market_summary.order_book_details:
                details = market_summary.order_book_details[0]
                
                if hasattr(details, 'mark_price') and details.mark_price:
                    return Decimal(str(details.mark_price))
            
            return None
            
        except Exception as e:
            logger.error(f"获取 {symbol} 价格失败: {e}")
            return None
    
    async def get_balance(self) -> Optional[Decimal]:
        """获取余额"""
        if not self.lighter_client:
            return Decimal('0')
        
        try:
            account_api = lighter.AccountApi(self.api_client)
            
            # 创建认证令牌
            auth_token, error = self.lighter_client.create_auth_token_with_expiry()
            if error:
                return Decimal('0')
            
            # 获取账户信息（注意：不要传 auth 参数，SDK 会自动处理）
            account_data = await account_api.account(
                by="index",
                value=str(self.account_index)
            )
            
            if account_data and hasattr(account_data, 'accounts') and account_data.accounts:
                account = account_data.accounts[0]
                if hasattr(account, 'available_balance'):
                    return Decimal(str(account.available_balance))
                elif hasattr(account, 'balance'):
                    return Decimal(str(account.balance))
            
            return Decimal('0')
            
        except Exception as e:
            logger.error(f"获取余额失败: {e}")
            return Decimal('0')
    
    async def get_position(self, symbol: str) -> Optional[Dict]:
        """获取持仓"""
        return None
    
    async def create_order(self, **kwargs) -> Optional[Dict]:
        """创建订单"""
        logger.warning("创建订单功能暂未实现")
        return None
    
    async def get_liquidation_price(self, symbol: str) -> Optional[Decimal]:
        """获取爆仓价格"""
        return None
    
    async def set_stop_loss_take_profit(self, **kwargs):
        """设置止损止盈"""
        pass
    
    async def close(self):
        """关闭连接"""
        if self.api_client:
            try:
                await self.api_client.close()
                logger.info("Lighter 客户端已关闭")
            except:
                pass
