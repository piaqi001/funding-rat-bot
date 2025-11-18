from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """应用配置"""
    
    # 数据库配置
    database_url: str = "postgresql://admin:password@localhost:5432/funding_arbitrage"
    
    # Redis 配置（可选）
    redis_url: str = "redis://localhost:6379"
    
    # Lighter 配置
    lighter_base_url: str = "https://mainnet.zklighter.elliot.ai"
    lighter_eth_private_key: str = ""
    lighter_api_key_private_key: str = ""
    lighter_account_index: int = 0
    lighter_api_key_index: int = 2
    
    # 币安配置
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = False
    
    # Telegram 配置（可选）
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    
    # 交易配置
    default_funding_rate_threshold: float = 0.01
    default_position_size_per_order: float = 100.0
    default_max_total_position: float = 1000.0
    default_max_imbalance: float = 200.0
    default_total_leverage: int = 3
    default_stop_loss_percent: float = 0.20
    default_take_profit_percent: float = 0.20
    
    # API 配置
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "your-secret-key-change-this"
    access_token_expire_minutes: int = 60 * 24 * 7
    
    # 日志配置
    log_level: str = "INFO"
    log_file: str = "logs/bot.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

settings = Settings()
