from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json
import logging
from ..app_state import get_app_state

router = APIRouter()
logger = logging.getLogger(__name__)

# 存储活跃的 WebSocket 连接
active_connections: list[WebSocket] = []


class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket 连接建立，当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket 连接断开，当前连接数: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def broadcast(self, message: dict):
        """广播消息给所有连接"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"发送消息失败: {e}")


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 主端点"""
    await manager.connect(websocket)
    
    try:
        # 启动数据推送任务
        push_task = asyncio.create_task(push_data(websocket))
        
        # 等待客户端消息
        while True:
            data = await websocket.receive_text()
            
            # 处理客户端消息
            try:
                message = json.loads(data)
                await handle_client_message(websocket, message)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        push_task.cancel()
    
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        manager.disconnect(websocket)


async def push_data(websocket: WebSocket):
    """推送实时数据"""
    try:
        while True:
            state = get_app_state()
            
            # 获取数据
            collector = state.get('data_collector')
            manager_pos = state.get('position_manager')
            
            if collector and manager_pos:
                # 推送费率数据
                rate_diffs = collector.get_all_rate_diffs()
                await websocket.send_json({
                    "type": "funding_rates",
                    "data": rate_diffs
                })
                
                # 推送持仓数据
                positions = await manager_pos.get_all_positions()
                await websocket.send_json({
                    "type": "positions",
                    "data": positions
                })
            
            # 每5秒推送一次
            await asyncio.sleep(5)
    
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"推送数据失败: {e}")


async def handle_client_message(websocket: WebSocket, message: dict):
    """处理客户端消息"""
    msg_type = message.get('type')
    
    if msg_type == 'ping':
        await websocket.send_json({
            "type": "pong"
        })
    
    elif msg_type == 'subscribe':
        # 处理订阅请求
        channel = message.get('channel')
        await websocket.send_json({
            "type": "subscribed",
            "channel": channel
        })
    
    else:
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown message type: {msg_type}"
        })


@router.websocket("/ws/funding-rates")
async def websocket_funding_rates(websocket: WebSocket):
    """资金费率实时推送"""
    await websocket.accept()
    
    try:
        while True:
            state = get_app_state()
            collector = state.get('data_collector')
            
            if collector:
                rate_diffs = collector.get_all_rate_diffs()
                await websocket.send_json(rate_diffs)
            
            await asyncio.sleep(5)
    
    except WebSocketDisconnect:
        pass


@router.websocket("/ws/positions")
async def websocket_positions(websocket: WebSocket):
    """持仓实时推送"""
    await websocket.accept()
    
    try:
        while True:
            state = get_app_state()
            manager_pos = state.get('position_manager')
            
            if manager_pos:
                positions = await manager_pos.get_all_positions()
                await websocket.send_json(positions)
            
            await asyncio.sleep(5)
    
    except WebSocketDisconnect:
        pass
