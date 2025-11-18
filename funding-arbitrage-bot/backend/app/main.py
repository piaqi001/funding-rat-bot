import logging
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .config import settings
from .database import init_db
from .app_state import app_state, get_app_state, set_app_state
from .api import routes, websocket
from .core.data_collector import DataCollector
from .core.strategy_engine import StrategyEngine
from .core.order_executor import OrderExecutor
from .core.risk_manager import RiskManager
from .core.position_manager import PositionManager
from .core.pnl_calculator import PnLCalculator
from .exchanges.lighter_client import LighterClient
from .exchanges.binance_client import BinanceClient

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("启动应用...")
    
    # 初始化数据库
    init_db()
    
    # 初始化交易所客户端
    lighter_client = LighterClient()
    binance_client = BinanceClient()
    await lighter_client.initialize()
    await binance_client.initialize()
    
    # 初始化核心模块
    data_collector = DataCollector()
    await data_collector.initialize()
    
    strategy_engine = StrategyEngine(data_collector)
    order_executor = OrderExecutor(lighter_client, binance_client)
    risk_manager = RiskManager(lighter_client, binance_client, order_executor)
    position_manager = PositionManager(lighter_client, binance_client)
    pnl_calculator = PnLCalculator()
    
    # 保存到全局状态
    app_state['data_collector'] = data_collector
    app_state['strategy_engine'] = strategy_engine
    app_state['order_executor'] = order_executor
    app_state['risk_manager'] = risk_manager
    app_state['position_manager'] = position_manager
    app_state['pnl_calculator'] = pnl_calculator
    app_state['lighter_client'] = lighter_client
    app_state['binance_client'] = binance_client
    
    # 启动后台任务
    logger.info("启动数据采集...")
    collector_task = asyncio.create_task(data_collector.start())
    
    logger.info("启动风险管理...")
    risk_task = asyncio.create_task(risk_manager.start())
    
    app_state['tasks'] = [collector_task, risk_task]
    
    logger.info("✅ 应用启动完成")
    
    yield
    
    # 关闭应用
    logger.info("关闭应用...")
    
    # 停止后台任务
    await data_collector.stop()
    await risk_manager.stop()
    
    for task in app_state.get('tasks', []):
        task.cancel()
    
    # 关闭客户端连接
    await lighter_client.close()
    
    logger.info("✅ 应用已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="Funding Rate Arbitrage Bot",
    description="Lighter-Binance 资金费率套利机器人",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(routes.router, prefix=settings.api_v1_prefix)
app.include_router(websocket.router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Funding Rate Arbitrage Bot API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": asyncio.get_event_loop().time()
    }

