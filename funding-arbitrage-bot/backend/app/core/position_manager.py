import logging
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..exchanges.lighter_client import LighterClient
from ..exchanges.binance_client import BinanceClient
from ..models import ArbitrageOrder, Trade
from ..database import get_db_context

logger = logging.getLogger(__name__)


class PositionManager:
    """持仓管理器 - 管理和查询持仓信息"""
    
    def __init__(
        self,
        lighter_client: LighterClient,
        binance_client: BinanceClient
    ):
        self.lighter = lighter_client
        self.binance = binance_client
    
    async def get_all_positions(self) -> List[Dict]:
        """
        获取所有持仓
        
        Returns:
            持仓列表
        """
        try:
            with get_db_context() as db:
                orders = db.query(ArbitrageOrder).filter(
                    ArbitrageOrder.status.in_(['open', 'opening'])
                ).all()
                
                positions = []
                for order in orders:
                    position = await self.get_position_detail(order.order_id)
                    if position:
                        positions.append(position)
                
                return positions
        except Exception as e:
            logger.error(f"获取所有持仓失败: {e}")
            return []
    
    async def get_position_by_symbol(self, symbol: str) -> List[Dict]:
        """
        按交易对查询持仓
        
        Args:
            symbol: 交易对
            
        Returns:
            持仓列表
        """
        try:
            with get_db_context() as db:
                orders = db.query(ArbitrageOrder).filter(
                    ArbitrageOrder.symbol == symbol,
                    ArbitrageOrder.status.in_(['open', 'opening'])
                ).all()
                
                positions = []
                for order in orders:
                    position = await self.get_position_detail(order.order_id)
                    if position:
                        positions.append(position)
                
                return positions
        except Exception as e:
            logger.error(f"按交易对查询持仓失败: {e}")
            return []
    
    async def get_position_detail(self, order_id: str) -> Optional[Dict]:
        """
        获取持仓详情
        
        Args:
            order_id: 订单ID
            
        Returns:
            持仓详情
        """
        try:
            with get_db_context() as db:
                order = db.query(ArbitrageOrder).filter(
                    ArbitrageOrder.order_id == order_id
                ).first()
                
                if not order:
                    return None
                
                # 获取实时持仓数据
                lighter_position = await self.lighter.get_position(order.symbol)
                binance_position = await self.binance.get_position(order.symbol)
                
                # 计算未实现盈亏
                unrealized_pnl = await self.calculate_unrealized_pnl(order_id)
                
                # 获取当前价格
                current_price = await self.lighter.get_price(order.symbol)
                
                # 计算持仓时间
                holding_hours = (datetime.now() - order.created_at).total_seconds() / 3600
                
                return {
                    'order_id': order.order_id,
                    'symbol': order.symbol,
                    'strategy_type': order.strategy_type,
                    'status': order.status,
                    
                    # Lighter 信息
                    'lighter': {
                        'side': order.lighter_side,
                        'entry_price': float(order.lighter_entry_price) if order.lighter_entry_price else 0,
                        'entry_amount': float(order.lighter_entry_amount),
                        'filled_amount': float(order.lighter_filled_amount),
                        'leverage': order.lighter_leverage,
                        'current_amount': float(lighter_position.get('amount', 0)) if lighter_position else 0,
                        'unrealized_pnl': float(lighter_position.get('unrealized_pnl', 0)) if lighter_position else 0,
                    },
                    
                    # 币安信息
                    'binance': {
                        'side': order.binance_side,
                        'entry_price': float(order.binance_entry_price) if order.binance_entry_price else 0,
                        'entry_amount': float(order.binance_entry_amount),
                        'filled_amount': float(order.binance_filled_amount),
                        'leverage': order.binance_leverage,
                        'current_amount': float(binance_position.get('amount', 0)) if binance_position else 0,
                        'unrealized_pnl': float(binance_position.get('unrealized_pnl', 0)) if binance_position else 0,
                    },
                    
                    # 总计信息
                    'current_price': float(current_price) if current_price else 0,
                    'imbalance_amount': float(order.imbalance_amount),
                    'total_unrealized_pnl': unrealized_pnl,
                    'stop_loss_price': float(order.stop_loss_price) if order.stop_loss_price else None,
                    'take_profit_price': float(order.take_profit_price) if order.take_profit_price else None,
                    'entry_funding_rate_diff': float(order.entry_funding_rate_diff) if order.entry_funding_rate_diff else 0,
                    
                    # 时间信息
                    'created_at': order.created_at.isoformat(),
                    'holding_hours': round(holding_hours, 2),
                }
        except Exception as e:
            logger.error(f"获取持仓详情失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def calculate_unrealized_pnl(self, order_id: str) -> float:
        """
        计算未实现盈亏
        
        Args:
            order_id: 订单ID
            
        Returns:
            未实现盈亏
        """
        try:
            with get_db_context() as db:
                order = db.query(ArbitrageOrder).filter(
                    ArbitrageOrder.order_id == order_id
                ).first()
                
                if not order:
                    return 0.0
                
                # 获取实时持仓
                lighter_position = await self.lighter.get_position(order.symbol)
                binance_position = await self.binance.get_position(order.symbol)
                
                lighter_pnl = Decimal(str(lighter_position.get('unrealized_pnl', 0))) if lighter_position else Decimal('0')
                binance_pnl = Decimal(str(binance_position.get('unrealized_pnl', 0))) if binance_position else Decimal('0')
                
                return float(lighter_pnl + binance_pnl)
        except Exception as e:
            logger.error(f"计算未实现盈亏失败: {e}")
            return 0.0
    
    async def update_positions(self):
        """
        更新所有持仓的状态
        
        这个方法会从交易所同步最新的持仓数据到数据库
        """
        try:
            with get_db_context() as db:
                orders = db.query(ArbitrageOrder).filter(
                    ArbitrageOrder.status.in_(['open', 'opening'])
                ).all()
                
                for order in orders:
                    # 获取实时持仓
                    lighter_position = await self.lighter.get_position(order.symbol)
                    binance_position = await self.binance.get_position(order.symbol)
                    
                    # 更新不平衡金额
                    lighter_amount = Decimal(str(lighter_position.get('amount', 0))) if lighter_position else Decimal('0')
                    binance_amount = Decimal(str(binance_position.get('amount', 0))) if binance_position else Decimal('0')
                    
                    order.imbalance_amount = abs(lighter_amount - binance_amount)
                    order.updated_at = datetime.now()
                
                logger.info(f"更新了 {len(orders)} 个持仓")
        except Exception as e:
            logger.error(f"更新持仓失败: {e}")
    
    def get_position_summary(self) -> Dict:
        """
        获取持仓汇总
        
        Returns:
            持仓汇总信息
        """
        try:
            with get_db_context() as db:
                # 统计各状态的订单数量
                status_counts = db.query(
                    ArbitrageOrder.status,
                    func.count(ArbitrageOrder.id)
                ).group_by(ArbitrageOrder.status).all()
                
                # 统计总持仓金额
                open_orders = db.query(ArbitrageOrder).filter(
                    ArbitrageOrder.status == 'open'
                ).all()
                
                total_lighter_amount = sum(
                    float(o.lighter_entry_amount) for o in open_orders
                )
                total_binance_amount = sum(
                    float(o.binance_entry_amount) for o in open_orders
                )
                
                return {
                    'status_counts': {status: count for status, count in status_counts},
                    'open_positions': len(open_orders),
                    'total_lighter_amount': total_lighter_amount,
                    'total_binance_amount': total_binance_amount,
                    'total_amount': total_lighter_amount + total_binance_amount,
                }
        except Exception as e:
            logger.error(f"获取持仓汇总失败: {e}")
            return {
                'status_counts': {},
                'open_positions': 0,
                'total_lighter_amount': 0,
                'total_binance_amount': 0,
                'total_amount': 0,
            }
    
    def get_trades_by_order(self, order_id: str) -> List[Dict]:
        """
        获取订单的所有成交记录
        
        Args:
            order_id: 订单ID
            
        Returns:
            成交记录列表
        """
        try:
            with get_db_context() as db:
                trades = db.query(Trade).filter(
                    Trade.order_id == order_id
                ).order_by(Trade.created_at).all()
                
                return [
                    {
                        'id': t.id,
                        'exchange': t.exchange,
                        'symbol': t.symbol,
                        'side': t.side,
                        'action': t.action,
                        'price': float(t.price),
                        'amount': float(t.amount),
                        'fee': float(t.fee) if t.fee else 0,
                        'exchange_order_id': t.exchange_order_id,
                        'timestamp': t.timestamp,
                        'created_at': t.created_at.isoformat(),
                    }
                    for t in trades
                ]
        except Exception as e:
            logger.error(f"获取成交记录失败: {e}")
            return []
    
    def get_position_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        获取历史持仓
        
        Args:
            symbol: 交易对（可选）
            limit: 返回数量限制
            
        Returns:
            历史持仓列表
        """
        try:
            with get_db_context() as db:
                query = db.query(ArbitrageOrder).filter(
                    ArbitrageOrder.status == 'closed'
                )
                
                if symbol:
                    query = query.filter(ArbitrageOrder.symbol == symbol)
                
                orders = query.order_by(
                    ArbitrageOrder.updated_at.desc()
                ).limit(limit).all()
                
                return [
                    {
                        'order_id': o.order_id,
                        'symbol': o.symbol,
                        'strategy_type': o.strategy_type,
                        'lighter_side': o.lighter_side,
                        'binance_side': o.binance_side,
                        'created_at': o.created_at.isoformat(),
                        'closed_at': o.updated_at.isoformat(),
                        'holding_hours': (o.updated_at - o.created_at).total_seconds() / 3600,
                    }
                    for o in orders
                ]
        except Exception as e:
            logger.error(f"获取历史持仓失败: {e}")
            return []
