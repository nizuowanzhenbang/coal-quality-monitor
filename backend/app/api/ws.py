"""WebSocket 广播接口：实时推送预警通知"""
import asyncio
import json
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt

from app.config import settings

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
async def ws_alerts(websocket: WebSocket, token: str = Query(...)):
    """
    WebSocket 端点：/api/ws/alerts?token=<jwt>

    JWT 鉴权后保持长连接，服务端可调用 broadcast() 向所有客户端推送预警。
    客户端可发送 {"type":"ping"} 维持心跳，超时 30s 服务端自动发心跳。
    """
    # JWT 鉴权
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if not payload.get("sub"):
            await websocket.close(code=4001)
            return
    except JWTError:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    _active_connections.add(websocket)
    try:
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "已连接到煤质预警推送服务",
        }, ensure_ascii=False))

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                except json.JSONDecodeError:
                    pass
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text(json.dumps({"type": "heartbeat"}))
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _active_connections.discard(websocket)
