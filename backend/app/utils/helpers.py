"""工具函数"""
from typing import Any, Optional


def api_response(
    data: Any = None,
    message: str = "success",
    code: int = 200,
) -> dict:
    """统一 API 响应格式"""
    return {"code": code, "message": message, "data": data}


def paginate_response(
    items: list,
    total: int,
    page: int,
    page_size: int,
    message: str = "success",
) -> dict:
    """分页响应格式"""
    return {
        "code": 200,
        "message": message,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
        },
    }
