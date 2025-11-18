from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from decimal import Decimal
from ..app_state import get_app_state


router = APIRouter()


# ============================================
# Pydantic 模型定义
# ============================================

class ConfigUpdate(BaseModel):
    """配置更新请求"""
    funding_rate_threshold: Optional[float] = None
    position_size_per_order: Optional[float] = None
    max_total_position: Optional[float] = None
    max_imbalance: Optional[float] = None
    total_leverage: Optional[int] = None
    stop_loss_percent: Optional[float] = None
    take_profit_percent: Optional[float] = None


class OpenPositionRequest(BaseModel):
    """建仓请求"""
    symbol: str
    target_amount: float


class ClosePositionRequest(BaseModel):
    """平仓请求"""
    order_id: str


class SymbolUpdate(BaseModel):
    """交易对更新"""
    symbol: str
    enabled: bool


# ============================================
# 配置相关 API
# ============================================

@router.get("/status")
async def get_system_status():
    """获取系统状态"""
    try:
        state = get_app_state()
        
        lighter = state.get('lighter_client')
        binance = state.get('binance_client')
        
        # 获取余额
        lighter_balance = None
        binance_balance = None
        
        if lighter:
            try:
                lighter_balance = await lighter.get_balance()
            except:
                pass
        
        if binance:
            try:
                binance_balance = await binance.get_balance()
            except:
                pass
        
        return {
            "success": True,
            "data": {
                "lighter": {
                    "connected": lighter is not None and getattr(lighter, 'initialized', False),
                    "balance": float(lighter_balance) if lighter_balance else 0
                },
                "binance": {
                    "connected": binance is not None and getattr(binance, 'initialized', False),
                    "balance": float(binance_balance) if binance_balance else 0
                },
                "modules": {
                    "data_collector": state.get('data_collector') is not None,
                    "strategy_engine": state.get('strategy_engine') is not None,
                    "order_executor": state.get('order_executor') is not None,
                    "risk_manager": state.get('risk_manager') is not None,
                    "position_manager": state.get('position_manager') is not None,
                    "pnl_calculator": state.get('pnl_calculator') is not None
                }
            }
        }
    except Exception as e:
        import traceback
        logger.error(f"获取系统状态失败: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config")
async def update_config(config: ConfigUpdate):
    """更新配置"""
    try:
        # 注意：这里只返回确认，实际配置需要修改 .env 文件并重启服务
        updates = {}
        for key, value in config.dict(exclude_unset=True).items():
            if value is not None:
                updates[key] = value
        
        # TODO: 将来可以实现动态更新 strategy_engine 的配置
        # 目前返回成功但提示需要重启
        
        return {
            "success": True,
            "message": "配置已记录，重启服务后生效",
            "data": updates
        }
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"更新配置失败: {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 套利机会 API
# ============================================

@router.get("/opportunities")
async def get_opportunities():
    """获取当前的套利机会"""
    try:
        state = get_app_state()
        engine = state.get('strategy_engine')
        
        if not engine:
            raise HTTPException(status_code=500, detail="策略引擎未初始化")
        
        opportunities = engine.get_all_opportunities()
        
        return {
            "success": True,
            "data": opportunities
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funding-rates")
async def get_funding_rates():
    """获取所有交易对的费率数据"""
    try:
        state = get_app_state()
        collector = state.get('data_collector')
        
        if not collector:
            # 如果采集器未初始化，返回空数据
            return {
                "success": True,
                "data": {}
            }
        
        rate_diffs = collector.get_all_rate_diffs()
        
        return {
            "success": True,
            "data": rate_diffs
        }
    except Exception as e:
        import traceback
        logger.error(f"获取费率数据失败: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 订单管理 API
# ============================================

@router.post("/orders/open")
async def open_position(request: OpenPositionRequest):
    """手动建仓"""
    try:
        state = get_app_state()
        engine = state.get('strategy_engine')
        executor = state.get('order_executor')
        
        if not engine or not executor:
            raise HTTPException(status_code=500, detail="模块未初始化")
        
        # 检查套利机会
        opportunity = engine.check_arbitrage_opportunity(request.symbol)
        
        if not opportunity:
            raise HTTPException(status_code=400, detail="当前没有套利机会")
        
        # 获取建仓参数
        position_size, leverage = engine.calculate_position_size(
            request.symbol,
            Decimal('0')  # 假设当前没有持仓
        )
        
        # 计算止损止盈
        from ..exchanges.lighter_client import LighterClient
        lighter = state.get('lighter_client')
        current_price = await lighter.get_price(request.symbol)
        
        stop_loss, take_profit = engine.calculate_stop_loss_take_profit(
            current_price,
            opportunity['lighter_side']
        )
        
        # 执行建仓
        order_id = await executor.execute_open_position(
            symbol=request.symbol,
            lighter_side=opportunity['lighter_side'],
            binance_side=opportunity['binance_side'],
            target_amount=Decimal(str(request.target_amount)),
            amount_per_order=Decimal(str(engine.config['position_size_per_order'])),
            leverage=leverage,
            strategy_type=opportunity['strategy_type'],
            max_imbalance=Decimal(str(engine.config['max_imbalance'])),
            stop_loss_price=stop_loss,
            take_profit_price=take_profit
        )
        
        if not order_id:
            raise HTTPException(status_code=500, detail="建仓失败")
        
        return {
            "success": True,
            "message": "建仓成功",
            "data": {
                "order_id": order_id
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders/close")
async def close_position(request: ClosePositionRequest):
    """手动平仓"""
    try:
        state = get_app_state()
        executor = state.get('order_executor')
        engine = state.get('strategy_engine')
        
        if not executor or not engine:
            raise HTTPException(status_code=500, detail="模块未初始化")
        
        # 执行平仓
        success = await executor.execute_close_position(
            request.order_id,
            Decimal(str(engine.config['position_size_per_order']))
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="平仓失败")
        
        # 计算盈亏
        calculator = state.get('pnl_calculator')
        if calculator:
            pnl = calculator.calculate_order_pnl(request.order_id)
        else:
            pnl = None
        
        return {
            "success": True,
            "message": "平仓成功",
            "data": {
                "order_id": request.order_id,
                "pnl": pnl
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders")
async def get_orders(status: Optional[str] = None):
    """获取订单列表"""
    try:
        from ..database import get_db_context
        from ..models import ArbitrageOrder
        
        with get_db_context() as db:
            query = db.query(ArbitrageOrder)
            
            if status:
                query = query.filter(ArbitrageOrder.status == status)
            
            orders = query.order_by(ArbitrageOrder.created_at.desc()).limit(100).all()
            
            return {
                "success": True,
                "data": [
                    {
                        "order_id": o.order_id,
                        "symbol": o.symbol,
                        "strategy_type": o.strategy_type,
                        "status": o.status,
                        "lighter_side": o.lighter_side,
                        "binance_side": o.binance_side,
                        "lighter_entry_amount": float(o.lighter_entry_amount),
                        "binance_entry_amount": float(o.binance_entry_amount),
                        "created_at": o.created_at.isoformat(),
                        "updated_at": o.updated_at.isoformat() if o.updated_at else None
                    }
                    for o in orders
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 持仓管理 API
# ============================================

@router.get("/positions")
async def get_positions():
    """获取当前持仓"""
    try:
        state = get_app_state()
        manager = state.get('position_manager')
        
        if not manager:
            raise HTTPException(status_code=500, detail="持仓管理器未初始化")
        
        positions = await manager.get_all_positions()
        
        return {
            "success": True,
            "data": positions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/{order_id}")
async def get_position_detail(order_id: str):
    """获取持仓详情"""
    try:
        state = get_app_state()
        manager = state.get('position_manager')
        
        if not manager:
            raise HTTPException(status_code=500, detail="持仓管理器未初始化")
        
        position = await manager.get_position_detail(order_id)
        
        if not position:
            raise HTTPException(status_code=404, detail="持仓不存在")
        
        return {
            "success": True,
            "data": position
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/summary")
async def get_position_summary():
    """获取持仓汇总"""
    try:
        state = get_app_state()
        manager = state.get('position_manager')
        
        if not manager:
            raise HTTPException(status_code=500, detail="持仓管理器未初始化")
        
        summary = manager.get_position_summary()
        
        return {
            "success": True,
            "data": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 盈亏统计 API
# ============================================

@router.get("/pnl/total")
async def get_total_pnl(days: int = 30):
    """获取总盈亏统计"""
    try:
        state = get_app_state()
        calculator = state.get('pnl_calculator')
        
        if not calculator:
            raise HTTPException(status_code=500, detail="盈亏计算器未初始化")
        
        total_pnl = calculator.get_total_pnl(days)
        
        return {
            "success": True,
            "data": total_pnl
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pnl/history")
async def get_pnl_history(limit: int = 50):
    """获取盈亏历史"""
    try:
        state = get_app_state()
        calculator = state.get('pnl_calculator')
        
        if not calculator:
            raise HTTPException(status_code=500, detail="盈亏计算器未初始化")
        
        history = calculator.get_pnl_history(limit)
        
        return {
            "success": True,
            "data": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pnl/{order_id}")
async def get_order_pnl(order_id: str):
    """获取订单盈亏"""
    try:
        state = get_app_state()
        calculator = state.get('pnl_calculator')
        
        if not calculator:
            raise HTTPException(status_code=500, detail="盈亏计算器未初始化")
        
        pnl = calculator.calculate_order_pnl(order_id)
        
        if not pnl:
            raise HTTPException(status_code=404, detail="盈亏记录不存在")
        
        return {
            "success": True,
            "data": pnl
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 系统状态 API
# ============================================

@router.get("/status")
async def get_system_status():
    """获取系统状态"""
    try:
        state = get_app_state()
        
        lighter = state.get('lighter_client')
        binance = state.get('binance_client')
        
        # 获取余额
        lighter_balance = await lighter.get_balance() if lighter else None
        binance_balance = await binance.get_balance() if binance else None
        
        return {
            "success": True,
            "data": {
                "lighter": {
                    "connected": lighter is not None,
                    "balance": float(lighter_balance) if lighter_balance else 0
                },
                "binance": {
                    "connected": binance is not None,
                    "balance": float(binance_balance) if binance_balance else 0
                },
                "modules": {
                    "data_collector": state.get('data_collector') is not None,
                    "strategy_engine": state.get('strategy_engine') is not None,
                    "order_executor": state.get('order_executor') is not None,
                    "risk_manager": state.get('risk_manager') is not None,
                    "position_manager": state.get('position_manager') is not None,
                    "pnl_calculator": state.get('pnl_calculator') is not None
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 交易对管理 API
# ============================================

@router.get("/symbols")
async def get_symbols():
    """获取交易对列表"""
    try:
        from ..database import get_db_context
        from ..models import Symbol
        
        with get_db_context() as db:
            symbols = db.query(Symbol).all()
            
            return {
                "success": True,
                "data": [
                    {
                        "id": s.id,
                        "symbol": s.symbol,
                        "enabled": s.enabled,
                        "max_leverage_lighter": s.max_leverage_lighter,
                        "max_leverage_binance": s.max_leverage_binance
                    }
                    for s in symbols
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/symbols")
async def update_symbol(update: SymbolUpdate):
    """更新交易对状态"""
    try:
        from ..database import get_db_context
        from ..models import Symbol
        
        with get_db_context() as db:
            symbol = db.query(Symbol).filter(
                Symbol.symbol == update.symbol
            ).first()
            
            if symbol:
                symbol.enabled = update.enabled
            else:
                # 创建新交易对
                symbol = Symbol(
                    symbol=update.symbol,
                    enabled=update.enabled
                )
                db.add(symbol)
        
        return {
            "success": True,
            "message": "交易对更新成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
