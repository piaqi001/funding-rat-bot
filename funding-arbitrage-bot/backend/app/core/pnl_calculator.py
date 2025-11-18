import logging
from typing import Dict, Optional, List
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models import ArbitrageOrder, Trade, PnLRecord, FundingRate
from ..database import get_db_context

logger = logging.getLogger(__name__)


class PnLCalculator:
    """盈亏计算器 - 计算交易盈亏"""
    
    def calculate_order_pnl(self, order_id: str) -> Optional[Dict]:
        """
        计算订单的完整盈亏
        
        Args:
            order_id: 订单ID
            
        Returns:
            盈亏详情
        """
        try:
            with get_db_context() as db:
                order = db.query(ArbitrageOrder).filter(
                    ArbitrageOrder.order_id == order_id
                ).first()
                
                if not order or order.status != 'closed':
                    return None
                
                # 计算各项盈亏
                price_pnl = self._calculate_price_pnl(order_id)
                funding_pnl = self._calculate_funding_pnl(order_id, order)
                fees = self._calculate_fees(order_id)
                
                # 总盈亏
                net_pnl = price_pnl + funding_pnl['total'] - fees['total']
                
                # ROI
                initial_investment = float(order.lighter_entry_amount + order.binance_entry_amount)
                roi = (net_pnl / initial_investment * 100) if initial_investment > 0 else 0
                
                # 持仓时间
                holding_hours = (order.updated_at - order.created_at).total_seconds() / 3600
                
                pnl_data = {
                    'order_id': order_id,
                    'symbol': order.symbol,
                    'strategy_type': order.strategy_type,
                    
                    # 价差盈亏
                    'price_pnl': price_pnl,
                    
                    # 资金费率盈亏
                    'lighter_funding_pnl': funding_pnl['lighter'],
                    'binance_funding_pnl': funding_pnl['binance'],
                    'total_funding_pnl': funding_pnl['total'],
                    
                    # 手续费
                    'lighter_fees': fees['lighter'],
                    'binance_fees': fees['binance'],
                    'total_fees': fees['total'],
                    
                    # 总盈亏
                    'net_pnl': net_pnl,
                    'roi': roi,
                    
                    # 时间信息
                    'open_time': order.created_at,
                    'close_time': order.updated_at,
                    'holding_hours': holding_hours,
                }
                
                # 保存到数据库
                self._save_pnl_record(pnl_data)
                
                return pnl_data
        except Exception as e:
            logger.error(f"计算订单盈亏失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _calculate_price_pnl(self, order_id: str) -> float:
        """计算价差盈亏"""
        try:
            with get_db_context() as db:
                # 获取所有成交记录
                trades = db.query(Trade).filter(
                    Trade.order_id == order_id
                ).all()
                
                lighter_pnl = Decimal('0')
                binance_pnl = Decimal('0')
                
                for trade in trades:
                    value = trade.price * trade.amount
                    
                    if trade.exchange == 'lighter':
                        if trade.action == 'open':
                            if trade.side == 'long':
                                lighter_pnl -= value  # 买入支出
                            else:  # short
                                lighter_pnl += value  # 卖出收入
                        else:  # close
                            if trade.side == 'long':
                                lighter_pnl += value  # 平多收入
                            else:  # short
                                lighter_pnl -= value  # 平空支出
                    
                    elif trade.exchange == 'binance':
                        if trade.action == 'open':
                            if trade.side == 'long':
                                binance_pnl -= value
                            else:
                                binance_pnl += value
                        else:
                            if trade.side == 'long':
                                binance_pnl += value
                            else:
                                binance_pnl -= value
                
                return float(lighter_pnl + binance_pnl)
        except Exception as e:
            logger.error(f"计算价差盈亏失败: {e}")
            return 0.0
    
    def _calculate_funding_pnl(self, order_id: str, order: ArbitrageOrder) -> Dict:
        """计算资金费率盈亏"""
        try:
            with get_db_context() as db:
                symbol = order.symbol
                start_time = int(order.created_at.timestamp() * 1000)
                end_time = int(order.updated_at.timestamp() * 1000)
                
                # 获取该时间段的资金费率
                lighter_rates = db.query(FundingRate).filter(
                    FundingRate.exchange == 'lighter',
                    FundingRate.symbol == symbol,
                    FundingRate.timestamp >= start_time,
                    FundingRate.timestamp <= end_time
                ).all()
                
                binance_rates = db.query(FundingRate).filter(
                    FundingRate.exchange == 'binance',
                    FundingRate.symbol == symbol,
                    FundingRate.timestamp >= start_time,
                    FundingRate.timestamp <= end_time
                ).all()
                
                # 计算 Lighter 资金费率盈亏
                lighter_funding = Decimal('0')
                position_value = order.lighter_entry_amount * order.lighter_leverage
                
                for rate in lighter_rates:
                    if order.lighter_side == 'long':
                        lighter_funding -= position_value * rate.funding_rate
                    else:  # short
                        lighter_funding += position_value * rate.funding_rate
                
                # 计算币安资金费率盈亏
                binance_funding = Decimal('0')
                position_value = order.binance_entry_amount * order.binance_leverage
                
                for rate in binance_rates:
                    if order.binance_side == 'long':
                        binance_funding -= position_value * rate.funding_rate
                    else:  # short
                        binance_funding += position_value * rate.funding_rate
                
                return {
                    'lighter': float(lighter_funding),
                    'binance': float(binance_funding),
                    'total': float(lighter_funding + binance_funding)
                }
        except Exception as e:
            logger.error(f"计算资金费率盈亏失败: {e}")
            return {'lighter': 0.0, 'binance': 0.0, 'total': 0.0}
    
    def _calculate_fees(self, order_id: str) -> Dict:
        """计算手续费"""
        try:
            with get_db_context() as db:
                trades = db.query(Trade).filter(
                    Trade.order_id == order_id
                ).all()
                
                lighter_fees = sum(
                    float(t.fee) for t in trades
                    if t.exchange == 'lighter' and t.fee
                )
                
                binance_fees = sum(
                    float(t.fee) for t in trades
                    if t.exchange == 'binance' and t.fee
                )
                
                return {
                    'lighter': lighter_fees,
                    'binance': binance_fees,
                    'total': lighter_fees + binance_fees
                }
        except Exception as e:
            logger.error(f"计算手续费失败: {e}")
            return {'lighter': 0.0, 'binance': 0.0, 'total': 0.0}
    
    def _save_pnl_record(self, pnl_data: Dict):
        """保存盈亏记录"""
        try:
            with get_db_context() as db:
                # 检查是否已存在
                existing = db.query(PnLRecord).filter(
                    PnLRecord.order_id == pnl_data['order_id']
                ).first()
                
                if existing:
                    # 更新
                    existing.price_pnl = Decimal(str(pnl_data['price_pnl']))
                    existing.lighter_funding_pnl = Decimal(str(pnl_data['lighter_funding_pnl']))
                    existing.binance_funding_pnl = Decimal(str(pnl_data['binance_funding_pnl']))
                    existing.total_funding_pnl = Decimal(str(pnl_data['total_funding_pnl']))
                    existing.lighter_fees = Decimal(str(pnl_data['lighter_fees']))
                    existing.binance_fees = Decimal(str(pnl_data['binance_fees']))
                    existing.total_fees = Decimal(str(pnl_data['total_fees']))
                    existing.net_pnl = Decimal(str(pnl_data['net_pnl']))
                    existing.roi = Decimal(str(pnl_data['roi']))
                    existing.holding_hours = Decimal(str(pnl_data['holding_hours']))
                else:
                    # 新增
                    record = PnLRecord(
                        order_id=pnl_data['order_id'],
                        symbol=pnl_data['symbol'],
                        price_pnl=Decimal(str(pnl_data['price_pnl'])),
                        lighter_funding_pnl=Decimal(str(pnl_data['lighter_funding_pnl'])),
                        binance_funding_pnl=Decimal(str(pnl_data['binance_funding_pnl'])),
                        total_funding_pnl=Decimal(str(pnl_data['total_funding_pnl'])),
                        lighter_fees=Decimal(str(pnl_data['lighter_fees'])),
                        binance_fees=Decimal(str(pnl_data['binance_fees'])),
                        total_fees=Decimal(str(pnl_data['total_fees'])),
                        net_pnl=Decimal(str(pnl_data['net_pnl'])),
                        roi=Decimal(str(pnl_data['roi'])),
                        open_time=pnl_data['open_time'],
                        closed_at=pnl_data['close_time'],
                        holding_hours=Decimal(str(pnl_data['holding_hours']))
                    )
                    db.add(record)
        except Exception as e:
            logger.error(f"保存盈亏记录失败: {e}")
    
    def get_total_pnl(self, days: int = 30) -> Dict:
        """
        获取总盈亏统计
        
        Args:
            days: 统计天数
            
        Returns:
            盈亏统计
        """
        try:
            with get_db_context() as db:
                start_date = datetime.now() - timedelta(days=days)
                
                records = db.query(PnLRecord).filter(
                    PnLRecord.closed_at >= start_date
                ).all()
                
                if not records:
                    return {
                        'total_pnl': 0,
                        'total_orders': 0,
                        'win_rate': 0,
                        'avg_pnl': 0,
                        'avg_roi': 0
                    }
                
                total_pnl = sum(float(r.net_pnl) for r in records)
                total_orders = len(records)
                win_orders = sum(1 for r in records if r.net_pnl > 0)
                win_rate = win_orders / total_orders * 100 if total_orders > 0 else 0
                avg_pnl = total_pnl / total_orders if total_orders > 0 else 0
                avg_roi = sum(float(r.roi) for r in records) / total_orders if total_orders > 0 else 0
                
                return {
                    'total_pnl': total_pnl,
                    'total_orders': total_orders,
                    'win_orders': win_orders,
                    'loss_orders': total_orders - win_orders,
                    'win_rate': win_rate,
                    'avg_pnl': avg_pnl,
                    'avg_roi': avg_roi,
                    'days': days
                }
        except Exception as e:
            logger.error(f"获取总盈亏统计失败: {e}")
            return {
                'total_pnl': 0,
                'total_orders': 0,
                'win_rate': 0,
                'avg_pnl': 0,
                'avg_roi': 0
            }
    
    def get_pnl_history(self, limit: int = 50) -> List[Dict]:
        """
        获取盈亏历史记录
        
        Args:
            limit: 返回数量
            
        Returns:
            盈亏记录列表
        """
        try:
            with get_db_context() as db:
                records = db.query(PnLRecord).order_by(
                    PnLRecord.closed_at.desc()
                ).limit(limit).all()
                
                return [
                    {
                        'order_id': r.order_id,
                        'symbol': r.symbol,
                        'price_pnl': float(r.price_pnl),
                        'total_funding_pnl': float(r.total_funding_pnl),
                        'total_fees': float(r.total_fees),
                        'net_pnl': float(r.net_pnl),
                        'roi': float(r.roi),
                        'holding_hours': float(r.holding_hours),
                        'closed_at': r.closed_at.isoformat()
                    }
                    for r in records
                ]
        except Exception as e:
            logger.error(f"获取盈亏历史失败: {e}")
            return []
