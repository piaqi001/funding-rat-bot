import logging
import asyncio
from typing import Dict, Optional, List
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from ..exchanges.lighter_client import LighterClient
from ..exchanges.binance_client import BinanceClient
from ..models import ArbitrageOrder, Trade
from ..database import get_db_context
import json
import uuid

logger = logging.getLogger(__name__)


class OrderExecutor:
    """订单执行器 - 处理建仓和平仓"""
    
    def __init__(self, lighter_client: LighterClient, binance_client: BinanceClient):
        self.lighter = lighter_client
        self.binance = binance_client
        self.active_orders: Dict[str, ArbitrageOrder] = {}
    
    async def execute_open_position(
        self,
        symbol: str,
        lighter_side: str,
        binance_side: str,
        target_amount: Decimal,
        amount_per_order: Decimal,
        leverage: int,
        strategy_type: str,
        max_imbalance: Decimal,
        stop_loss_price: Decimal,
        take_profit_price: Decimal
    ) -> Optional[str]:
        """
        执行建仓操作
        
        Args:
            symbol: 交易对
            lighter_side: Lighter 方向 'long' or 'short'
            binance_side: 币安方向 'long' or 'short'
            target_amount: 目标总金额
            amount_per_order: 单笔订单金额
            leverage: 杠杆倍数
            strategy_type: 策略类型
            max_imbalance: 最大不平衡金额
            stop_loss_price: 止损价
            take_profit_price: 止盈价
            
        Returns:
            订单ID 或 None
        """
        order_id = f"ARB_{symbol}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"开始建仓: {order_id}")
        logger.info(f"  交易对: {symbol}")
        logger.info(f"  Lighter: {lighter_side}, 币安: {binance_side}")
        logger.info(f"  目标金额: {target_amount} USDC")
        
        try:
            # 创建订单记录
            with get_db_context() as db:
                order = ArbitrageOrder(
                    order_id=order_id,
                    symbol=symbol,
                    strategy_type=strategy_type,
                    lighter_side=lighter_side,
                    lighter_entry_amount=target_amount,
                    lighter_filled_amount=Decimal('0'),
                    lighter_leverage=leverage,
                    lighter_order_ids='[]',
                    binance_side=binance_side,
                    binance_entry_amount=target_amount,
                    binance_filled_amount=Decimal('0'),
                    binance_leverage=leverage,
                    binance_order_ids='[]',
                    status='opening',
                    imbalance_amount=Decimal('0'),
                    stop_loss_price=stop_loss_price,
                    take_profit_price=take_profit_price
                )
                db.add(order)
            
            # 分批建仓
            lighter_filled = Decimal('0')
            binance_filled = Decimal('0')
            lighter_order_ids = []
            binance_order_ids = []
            
            while lighter_filled < target_amount or binance_filled < target_amount:
                # 检查不平衡
                imbalance = abs(lighter_filled - binance_filled)
                if imbalance > max_imbalance:
                    logger.warning(f"持仓不平衡 {imbalance} USDC，等待成交...")
                    await asyncio.sleep(5)
                    continue
                
                # 计算本次下单金额
                lighter_remaining = target_amount - lighter_filled
                binance_remaining = target_amount - binance_filled
                
                current_amount = min(amount_per_order, lighter_remaining, binance_remaining)
                
                if current_amount <= 0:
                    break
                
                logger.info(f"分批建仓: {current_amount} USDC")
                
                # 同时在两个平台下单
                lighter_task = self._place_lighter_order(
                    symbol, lighter_side, current_amount, leverage
                )
                binance_task = self._place_binance_order(
                    symbol, binance_side, current_amount, leverage
                )
                
                lighter_result, binance_result = await asyncio.gather(
                    lighter_task, binance_task, return_exceptions=True
                )
                
                # 处理 Lighter 订单结果
                if isinstance(lighter_result, dict) and lighter_result.get('status') == 'filled':
                    lighter_filled += Decimal(str(lighter_result['filled_amount']))
                    lighter_order_ids.append(lighter_result['order_id'])
                    
                    # 记录成交
                    self._record_trade(
                        order_id, 'lighter', symbol, lighter_side, 'open',
                        Decimal(str(lighter_result['price'])),
                        Decimal(str(lighter_result['filled_amount'])),
                        lighter_result['order_id']
                    )
                else:
                    logger.error(f"Lighter 下单失败: {lighter_result}")
                
                # 处理币安订单结果
                if isinstance(binance_result, dict) and binance_result.get('status') in ['FILLED', 'filled']:
                    binance_filled += Decimal(str(binance_result['filled_amount']))
                    binance_order_ids.append(binance_result['order_id'])
                    
                    # 记录成交
                    self._record_trade(
                        order_id, 'binance', symbol, binance_side, 'open',
                        Decimal(str(binance_result['price'])),
                        Decimal(str(binance_result['filled_amount'])),
                        binance_result['order_id']
                    )
                else:
                    logger.error(f"币安下单失败: {binance_result}")
                
                # 更新订单状态
                with get_db_context() as db:
                    order = db.query(ArbitrageOrder).filter(
                        ArbitrageOrder.order_id == order_id
                    ).first()
                    if order:
                        order.lighter_filled_amount = lighter_filled
                        order.binance_filled_amount = binance_filled
                        order.imbalance_amount = abs(lighter_filled - binance_filled)
                        order.lighter_order_ids = json.dumps(lighter_order_ids)
                        order.binance_order_ids = json.dumps(binance_order_ids)
                
                logger.info(f"进度: Lighter {lighter_filled}/{target_amount}, 币安 {binance_filled}/{target_amount}")
                
                # 避免频繁下单
                await asyncio.sleep(2)
            
            # 建仓完成，设置止损止盈
            logger.info("建仓完成，设置止损止盈...")
            await self._set_stop_loss_take_profit(
                symbol, lighter_side, binance_side,
                stop_loss_price, take_profit_price
            )
            
            # 更新订单状态为 open
            with get_db_context() as db:
                order = db.query(ArbitrageOrder).filter(
                    ArbitrageOrder.order_id == order_id
                ).first()
                if order:
                    order.status = 'open'
                    order.lighter_entry_price = await self._get_avg_entry_price(
                        order_id, 'lighter'
                    )
                    order.binance_entry_price = await self._get_avg_entry_price(
                        order_id, 'binance'
                    )
            
            self.active_orders[order_id] = order
            logger.info(f"✅ 建仓成功: {order_id}")
            return order_id
        
        except Exception as e:
            logger.error(f"建仓失败: {e}")
            import traceback
            traceback.print_exc()
            
            # 更新订单状态为失败
            with get_db_context() as db:
                order = db.query(ArbitrageOrder).filter(
                    ArbitrageOrder.order_id == order_id
                ).first()
                if order:
                    order.status = 'failed'
            
            return None
    
    async def execute_close_position(
        self,
        order_id: str,
        amount_per_order: Decimal
    ) -> bool:
        """
        执行平仓操作
        
        Args:
            order_id: 订单ID
            amount_per_order: 单笔平仓金额
            
        Returns:
            是否成功
        """
        logger.info(f"开始平仓: {order_id}")
        
        try:
            # 获取订单信息
            with get_db_context() as db:
                order = db.query(ArbitrageOrder).filter(
                    ArbitrageOrder.order_id == order_id
                ).first()
                
                if not order:
                    logger.error(f"订单不存在: {order_id}")
                    return False
                
                if order.status != 'open':
                    logger.error(f"订单状态不是 open: {order.status}")
                    return False
                
                # 更新状态为 closing
                order.status = 'closing'
            
            symbol = order.symbol
            lighter_side = order.lighter_side
            binance_side = order.binance_side
            
            # 获取当前持仓
            lighter_position = await self.lighter.get_position(symbol)
            binance_position = await self.binance.get_position(symbol)
            
            lighter_amount = Decimal(str(lighter_position.get('amount', 0))) if lighter_position else Decimal('0')
            binance_amount = Decimal(str(binance_position.get('amount', 0))) if binance_position else Decimal('0')
            
            logger.info(f"当前持仓: Lighter {lighter_amount}, 币安 {binance_amount}")
            
            # 分批平仓
            while lighter_amount > 0 or binance_amount > 0:
                current_amount = min(amount_per_order, lighter_amount, binance_amount)
                
                if current_amount <= 0:
                    break
                
                logger.info(f"分批平仓: {current_amount}")
                
                # 平仓方向与开仓相反
                lighter_close_side = 'short' if lighter_side == 'long' else 'long'
                binance_close_side = 'short' if binance_side == 'long' else 'long'
                
                # 同时平仓
                lighter_task = self._place_lighter_order(
                    symbol, lighter_close_side, current_amount, 1
                )
                binance_task = self._place_binance_order(
                    symbol, binance_close_side, current_amount, 1
                )
                
                lighter_result, binance_result = await asyncio.gather(
                    lighter_task, binance_task, return_exceptions=True
                )
                
                # 处理结果并记录
                if isinstance(lighter_result, dict) and lighter_result.get('status') == 'filled':
                    lighter_amount -= Decimal(str(lighter_result['filled_amount']))
                    self._record_trade(
                        order_id, 'lighter', symbol, lighter_close_side, 'close',
                        Decimal(str(lighter_result['price'])),
                        Decimal(str(lighter_result['filled_amount'])),
                        lighter_result['order_id']
                    )
                
                if isinstance(binance_result, dict) and binance_result.get('status') in ['FILLED', 'filled']:
                    binance_amount -= Decimal(str(binance_result['filled_amount']))
                    self._record_trade(
                        order_id, 'binance', symbol, binance_close_side, 'close',
                        Decimal(str(binance_result['price'])),
                        Decimal(str(binance_result['filled_amount'])),
                        binance_result['order_id']
                    )
                
                logger.info(f"剩余持仓: Lighter {lighter_amount}, 币安 {binance_amount}")
                
                await asyncio.sleep(2)
            
            # 更新订单状态为 closed
            with get_db_context() as db:
                order = db.query(ArbitrageOrder).filter(
                    ArbitrageOrder.order_id == order_id
                ).first()
                if order:
                    order.status = 'closed'
            
            if order_id in self.active_orders:
                del self.active_orders[order_id]
            
            logger.info(f"✅ 平仓成功: {order_id}")
            return True
        
        except Exception as e:
            logger.error(f"平仓失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _place_lighter_order(
        self,
        symbol: str,
        side: str,
        amount: Decimal,
        leverage: int
    ) -> Dict:
        """在 Lighter 下单"""
        try:
            result = await self.lighter.create_order(
                symbol=symbol,
                side=side,
                amount=amount,
                order_type='market',
                leverage=leverage
            )
            return result or {}
        except Exception as e:
            logger.error(f"Lighter 下单异常: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _place_binance_order(
        self,
        symbol: str,
        side: str,
        amount: Decimal,
        leverage: int
    ) -> Dict:
        """在币安下单"""
        try:
            result = await self.binance.create_order(
                symbol=symbol,
                side=side,
                amount=amount,
                order_type='MARKET',
                leverage=leverage
            )
            return result or {}
        except Exception as e:
            logger.error(f"币安下单异常: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _record_trade(
        self,
        order_id: str,
        exchange: str,
        symbol: str,
        side: str,
        action: str,
        price: Decimal,
        amount: Decimal,
        exchange_order_id: str
    ):
        """记录成交"""
        try:
            with get_db_context() as db:
                trade = Trade(
                    order_id=order_id,
                    exchange=exchange,
                    symbol=symbol,
                    side=side,
                    action=action,
                    price=price,
                    amount=amount,
                    exchange_order_id=exchange_order_id,
                    timestamp=int(datetime.now().timestamp() * 1000)
                )
                db.add(trade)
        except Exception as e:
            logger.error(f"记录成交失败: {e}")
    
    async def _set_stop_loss_take_profit(
        self,
        symbol: str,
        lighter_side: str,
        binance_side: str,
        stop_loss_price: Decimal,
        take_profit_price: Decimal
    ):
        """设置止损止盈"""
        try:
            # Lighter 止损止盈
            await self.lighter.set_stop_loss_take_profit(
                symbol=symbol,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price
            )
            
            # 币安止损止盈
            await self.binance.set_stop_loss_take_profit(
                symbol=symbol,
                side=binance_side,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price
            )
            
            logger.info("✅ 止损止盈设置成功")
        except Exception as e:
            logger.error(f"设置止损止盈失败: {e}")
    
    async def _get_avg_entry_price(self, order_id: str, exchange: str) -> Decimal:
        """计算平均开仓价"""
        try:
            with get_db_context() as db:
                trades = db.query(Trade).filter(
                    Trade.order_id == order_id,
                    Trade.exchange == exchange,
                    Trade.action == 'open'
                ).all()
                
                if not trades:
                    return Decimal('0')
                
                total_amount = sum(t.amount for t in trades)
                total_value = sum(t.price * t.amount for t in trades)
                
                return total_value / total_amount if total_amount > 0 else Decimal('0')
        except Exception as e:
            logger.error(f"计算平均价失败: {e}")
            return Decimal('0')
