"""WebSocket 广播接口：实时推送预警通知"""
import asyncio
import json
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["WebSocket"])

# 存储所有活跃连接
_active_connections: Set[WebSocket] = set()


async def broadcast(message: dict) -> None:
    """向所有已连接的 WebSocket 客户端广播消息"""
    if not _active_connections:
        return
    text = json.dumps(message, ensure_ascii=False, default=str)
    dead = set()
    for ws in list(_active_connections):
        try:
            await ws.send_text(text)
        except Exception:
            dead.add(ws)
    _active_connections.difference_update(dead)


@router.websocket("/api/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    """
    WebSocket 端点：/api/ws/alerts
    客户端连接后接收实时预警推送。
    服务端每30秒发送心跳包保持连接活跃。
    """
    await websocket.accept()
    _active_connections.add(websocket)
    try:
        # 发送欢迎消息
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "已连接到煤质预警推送服务",
        }, ensure_ascii=False))

        while True:
            try:
                # 等待客户端消息（支持 ping/pong）
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # 超时发送心跳
                await websocket.send_text(json.dumps({"type": "heartbeat"}))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _active_connections.discard(websocket)
