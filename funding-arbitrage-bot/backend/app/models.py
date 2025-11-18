from sqlalchemy import Column, Integer, String, Numeric, BigInteger, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class FundingRate(Base):
    """资金费率历史表"""
    __tablename__ = "funding_rates"
    
    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(20), nullable=False, index=True)  # 'lighter' or 'binance'
    symbol = Column(String(20), nullable=False, index=True)  # 'BTCUSDC', 'ETHUSDC'
    funding_rate = Column(Numeric(10, 6), nullable=False)  # 资金费率
    timestamp = Column(BigInteger, nullable=False, index=True)  # 时间戳(毫秒)
    created_at = Column(DateTime, default=func.now())


class ArbitrageOrder(Base):
    """套利订单表"""
    __tablename__ = "arbitrage_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(50), unique=True, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    strategy_type = Column(String(20), nullable=False)  # 'time_arbitrage' or 'rate_arbitrage'
    
    # Lighter 端
    lighter_side = Column(String(10), nullable=False)  # 'long' or 'short'
    lighter_entry_price = Column(Numeric(18, 8))
    lighter_entry_amount = Column(Numeric(18, 8))
    lighter_filled_amount = Column(Numeric(18, 8), default=0)
    lighter_leverage = Column(Integer)
    lighter_order_ids = Column(Text)  # JSON 数组，存储多个订单ID
    
    # 币安端
    binance_side = Column(String(10), nullable=False)  # 'long' or 'short'
    binance_entry_price = Column(Numeric(18, 8))
    binance_entry_amount = Column(Numeric(18, 8))
    binance_filled_amount = Column(Numeric(18, 8), default=0)
    binance_leverage = Column(Integer)
    binance_order_ids = Column(Text)  # JSON 数组
    
    # 状态
    status = Column(String(20), nullable=False, index=True)  # 'opening', 'open', 'closing', 'closed'
    imbalance_amount = Column(Numeric(18, 8), default=0)  # 持仓不平衡金额
    
    # 止损止盈
    stop_loss_price = Column(Numeric(18, 8))
    take_profit_price = Column(Numeric(18, 8))
    
    # 费率信息
    entry_funding_rate_diff = Column(Numeric(10, 6))  # 建仓时的费率差
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Trade(Base):
    """成交记录表"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(50), nullable=False, index=True)  # 关联 arbitrage_orders
    exchange = Column(String(20), nullable=False)  # 'lighter' or 'binance'
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # 'long' or 'short'
    action = Column(String(10), nullable=False)  # 'open' or 'close'
    price = Column(Numeric(18, 8), nullable=False)
    amount = Column(Numeric(18, 8), nullable=False)
    fee = Column(Numeric(18, 8), default=0)
    fee_currency = Column(String(10))
    exchange_order_id = Column(String(100))  # 交易所返回的订单ID
    timestamp = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=func.now())


class PnLRecord(Base):
    """盈亏记录表"""
    __tablename__ = "pnl_records"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(50), nullable=False, unique=True, index=True)
    symbol = Column(String(20), nullable=False)
    
    # 价差盈亏
    price_pnl = Column(Numeric(18, 8), default=0)
    
    # 资金费率盈亏
    lighter_funding_pnl = Column(Numeric(18, 8), default=0)
    binance_funding_pnl = Column(Numeric(18, 8), default=0)
    total_funding_pnl = Column(Numeric(18, 8), default=0)
    
    # 手续费
    lighter_fees = Column(Numeric(18, 8), default=0)
    binance_fees = Column(Numeric(18, 8), default=0)
    total_fees = Column(Numeric(18, 8), default=0)
    
    # 总盈亏
    net_pnl = Column(Numeric(18, 8), default=0)
    roi = Column(Numeric(10, 4), default=0)  # 收益率 (%)
    
    # 时间信息
    open_time = Column(DateTime)
    closed_at = Column(DateTime)
    holding_hours = Column(Numeric(10, 2))  # 持仓小时数
    
    created_at = Column(DateTime, default=func.now())


class Config(Base):
    """配置参数表"""
    __tablename__ = "config"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    description = Column(Text)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class SystemLog(Base):
    """系统日志表"""
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(20), nullable=False)  # 'INFO', 'WARNING', 'ERROR'
    module = Column(String(50))  # 模块名称
    message = Column(Text, nullable=False)
    details = Column(Text)  # JSON 格式的详细信息
    created_at = Column(DateTime, default=func.now(), index=True)


class Symbol(Base):
    """交易对配置表"""
    __tablename__ = "symbols"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), unique=True, nullable=False)  # 'BTCUSDC'
    lighter_symbol = Column(String(20))  # Lighter 上的交易对名称
    binance_symbol = Column(String(20))  # 币安上的交易对名称
    enabled = Column(Boolean, default=True)  # 是否启用
    max_leverage_lighter = Column(Integer)  # Lighter 最大杠杆
    max_leverage_binance = Column(Integer)  # 币安最大杠杆
    min_order_size = Column(Numeric(18, 8))  # 最小下单量
    price_precision = Column(Integer)  # 价格精度
    amount_precision = Column(Integer)  # 数量精度
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
