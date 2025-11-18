import logging
import asyncio
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from ..exchanges.lighter_client import LighterClient
from ..exchanges.binance_client import BinanceClient
from ..models import ArbitrageOrder, SystemLog
from ..database import get_db_context

logger = logging.getLogger(__name__)


class RiskManager:
    """风险管理器 - 监控风险并执行保护措施"""
    
    def __init__(
        self,
        lighter_client: LighterClient,
        binance_client: BinanceClient,
        order_executor
    ):
        self.lighter = lighter_client
        self.binance = binance_client
        self.executor = order_executor
        self.running = False
        self.alert_thresholds = {
            'max_imbalance_ratio': 0.2,  # 最大不平衡比例 20%
            'min_margin_ratio': 0.3,  # 最小保证金率 30%
            'liquidation_buffer': 0.05,  # 爆仓价格缓冲 5%
        }
    
    async def start(self):
        """启动风险监控"""
        self.running = True
        logger.info("风险管理器启动")
        
        tasks = [
            self._monitor_positions(),
            self._monitor_stop_loss_take_profit(),
            self._monitor_liquidation_risk(),
            self._monitor_balance()
        ]
        await asyncio.gather(*tasks)
    
    async def stop(self):
        """停止风险监控"""
        self.running = False
        logger.info("风险管理器停止")
    
    async def _monitor_positions(self):
        """监控持仓风险"""
        while self.running:
            try:
                with get_db_context() as db:
                    # 获取所有开仓状态的订单
                    orders = db.query(ArbitrageOrder).filter(
                        ArbitrageOrder.status.in_(['open', 'opening'])
                    ).all()
                    
                    for order in orders:
                        await self._check_position_risk(order)
                
            except Exception as e:
                logger.error(f"监控持仓风险失败: {e}")
            
            await asyncio.sleep(5)  # 每5秒检查一次
    
    async def _check_position_risk(self, order: ArbitrageOrder):
        """检查单个持仓的风险"""
        try:
            symbol = order.symbol
            
            # 获取实时持仓
            lighter_position = await self.lighter.get_position(symbol)
            binance_position = await self.binance.get_position(symbol)
            
            if not lighter_position or not binance_position:
                return
            
            # 检查持仓不平衡
            lighter_amount = Decimal(str(lighter_position.get('amount', 0)))
            binance_amount = Decimal(str(binance_position.get('amount', 0)))
            imbalance = abs(lighter_amount - binance_amount)
            total = lighter_amount + binance_amount
            
            if total > 0:
                imbalance_ratio = float(imbalance / total)
                
                if imbalance_ratio > self.alert_thresholds['max_imbalance_ratio']:
                    self._log_alert(
                        'high_imbalance',
                        f"持仓不平衡过高: {order.order_id}, 比例: {imbalance_ratio:.2%}",
                        {'order_id': order.order_id, 'imbalance_ratio': imbalance_ratio}
                    )
            
            # 检查未实现盈亏
            lighter_pnl = Decimal(str(lighter_position.get('unrealized_pnl', 0)))
            binance_pnl = Decimal(str(binance_position.get('unrealized_pnl', 0)))
            total_pnl = lighter_pnl + binance_pnl
            
            # 如果亏损超过初始投入的50%，发出警告
            initial_investment = order.lighter_entry_amount + order.binance_entry_amount
            if total_pnl < -initial_investment * Decimal('0.5'):
                self._log_alert(
                    'high_loss',
                    f"亏损过高: {order.order_id}, 盈亏: {total_pnl}",
                    {'order_id': order.order_id, 'pnl': float(total_pnl)}
                )
        
        except Exception as e:
            logger.error(f"检查持仓风险失败: {e}")
    
    async def _monitor_stop_loss_take_profit(self):
        """监控止损止盈触发"""
        while self.running:
            try:
                with get_db_context() as db:
                    orders = db.query(ArbitrageOrder).filter(
                        ArbitrageOrder.status == 'open'
                    ).all()
                    
                    for order in orders:
                        await self._check_stop_loss_take_profit(order)
            
            except Exception as e:
                logger.error(f"监控止损止盈失败: {e}")
            
            await asyncio.sleep(1)  # 每秒检查一次
    
    async def _check_stop_loss_take_profit(self, order: ArbitrageOrder):
        """检查止损止盈是否触发"""
        try:
            symbol = order.symbol
            
            # 获取当前价格
            current_price = await self.lighter.get_price(symbol)
            if not current_price:
                return
            
            stop_loss = order.stop_loss_price
            take_profit = order.take_profit_price
            
            should_close = False
            reason = ""
            
            # 检查止损
            if stop_loss:
                if order.lighter_side == 'long' and current_price <= stop_loss:
                    should_close = True
                    reason = f"触发止损 (价格 {current_price} <= 止损价 {stop_loss})"
                elif order.lighter_side == 'short' and current_price >= stop_loss:
                    should_close = True
                    reason = f"触发止损 (价格 {current_price} >= 止损价 {stop_loss})"
            
            # 检查止盈
            if take_profit and not should_close:
                if order.lighter_side == 'long' and current_price >= take_profit:
                    should_close = True
                    reason = f"触发止盈 (价格 {current_price} >= 止盈价 {take_profit})"
                elif order.lighter_side == 'short' and current_price <= take_profit:
                    should_close = True
                    reason = f"触发止盈 (价格 {current_price} <= 止盈价 {take_profit})"
            
            if should_close:
                logger.warning(f"{reason}, 准备平仓: {order.order_id}")
                self._log_alert(
                    'stop_triggered',
                    reason,
                    {'order_id': order.order_id, 'current_price': float(current_price)}
                )
                
                # 触发平仓（这里应该调用 order_executor 的平仓方法）
                # 注意：实际应该通过通知机制让用户决定是否平仓
                # await self.executor.execute_close_position(order.order_id, Decimal('100'))
        
        except Exception as e:
            logger.error(f"检查止损止盈失败: {e}")
    
    async def _monitor_liquidation_risk(self):
        """监控爆仓风险"""
        while self.running:
            try:
                with get_db_context() as db:
                    orders = db.query(ArbitrageOrder).filter(
                        ArbitrageOrder.status == 'open'
                    ).all()
                    
                    for order in orders:
                        await self._check_liquidation_risk(order)
            
            except Exception as e:
                logger.error(f"监控爆仓风险失败: {e}")
            
            await asyncio.sleep(10)  # 每10秒检查一次
    
    async def _check_liquidation_risk(self, order: ArbitrageOrder):
        """检查爆仓风险"""
        try:
            symbol = order.symbol
            
            # 获取当前价格
            current_price = await self.lighter.get_price(symbol)
            if not current_price:
                return
            
            # 获取爆仓价格
            lighter_liq_price = await self.lighter.get_liquidation_price(symbol)
            binance_liq_price = await self.binance.get_liquidation_price(symbol)
            
            buffer = Decimal(str(self.alert_thresholds['liquidation_buffer']))
            
            # 检查 Lighter 爆仓风险
            if lighter_liq_price:
                if order.lighter_side == 'long':
                    safe_price = lighter_liq_price * (1 + buffer)
                    if current_price <= safe_price:
                        self._log_alert(
                            'liquidation_risk',
                            f"Lighter 接近爆仓: {order.order_id}, 当前 {current_price}, 爆仓 {lighter_liq_price}",
                            {
                                'order_id': order.order_id,
                                'exchange': 'lighter',
                                'current_price': float(current_price),
                                'liquidation_price': float(lighter_liq_price)
                            }
                        )
                else:  # short
                    safe_price = lighter_liq_price * (1 - buffer)
                    if current_price >= safe_price:
                        self._log_alert(
                            'liquidation_risk',
                            f"Lighter 接近爆仓: {order.order_id}, 当前 {current_price}, 爆仓 {lighter_liq_price}",
                            {
                                'order_id': order.order_id,
                                'exchange': 'lighter',
                                'current_price': float(current_price),
                                'liquidation_price': float(lighter_liq_price)
                            }
                        )
            
            # 检查币安爆仓风险
            if binance_liq_price:
                if order.binance_side == 'long':
                    safe_price = binance_liq_price * (1 + buffer)
                    if current_price <= safe_price:
                        self._log_alert(
                            'liquidation_risk',
                            f"币安接近爆仓: {order.order_id}, 当前 {current_price}, 爆仓 {binance_liq_price}",
                            {
                                'order_id': order.order_id,
                                'exchange': 'binance',
                                'current_price': float(current_price),
                                'liquidation_price': float(binance_liq_price)
                            }
                        )
                else:  # short
                    safe_price = binance_liq_price * (1 - buffer)
                    if current_price >= safe_price:
                        self._log_alert(
                            'liquidation_risk',
                            f"币安接近爆仓: {order.order_id}, 当前 {current_price}, 爆仓 {binance_liq_price}",
                            {
                                'order_id': order.order_id,
                                'exchange': 'binance',
                                'current_price': float(current_price),
                                'liquidation_price': float(binance_liq_price)
                            }
                        )
        
        except Exception as e:
            logger.error(f"检查爆仓风险失败: {e}")
    
    async def _monitor_balance(self):
        """监控账户余额"""
        while self.running:
            try:
                # 获取余额
                lighter_balance = await self.lighter.get_balance()
                binance_balance = await self.binance.get_balance()
                
                # 检查余额是否过低
                min_balance = Decimal('100')  # 最小余额 100 USDC
                
                if lighter_balance and lighter_balance < min_balance:
                    self._log_alert(
                        'low_balance',
                        f"Lighter 余额过低: {lighter_balance} USDC",
                        {'exchange': 'lighter', 'balance': float(lighter_balance)}
                    )
                
                if binance_balance and binance_balance < min_balance:
                    self._log_alert(
                        'low_balance',
                        f"币安余额过低: {binance_balance} USDT",
                        {'exchange': 'binance', 'balance': float(binance_balance)}
                    )
            
            except Exception as e:
                logger.error(f"监控余额失败: {e}")
            
            await asyncio.sleep(60)  # 每分钟检查一次
    
    def _log_alert(self, level: str, message: str, details: dict = None):
        """记录告警日志"""
        try:
            logger.warning(f"[{level.upper()}] {message}")
            
            with get_db_context() as db:
                log = SystemLog(
                    level='WARNING',
                    module='risk_manager',
                    message=message,
                    details=str(details) if details else None
                )
                db.add(log)
        except Exception as e:
            logger.error(f"记录告警失败: {e}")
    
    async def emergency_close_all(self) -> bool:
        """紧急平仓所有持仓"""
        logger.warning("执行紧急平仓...")
        
        try:
            with get_db_context() as db:
                orders = db.query(ArbitrageOrder).filter(
                    ArbitrageOrder.status == 'open'
                ).all()
                
                for order in orders:
                    logger.warning(f"紧急平仓: {order.order_id}")
                    await self.executor.execute_close_position(
                        order.order_id,
                        Decimal('1000')  # 大金额快速平仓
                    )
            
            self._log_alert(
                'emergency_close',
                "执行紧急平仓",
                {'action': 'emergency_close_all'}
            )
            
            return True
        except Exception as e:
            logger.error(f"紧急平仓失败: {e}")
            return False
