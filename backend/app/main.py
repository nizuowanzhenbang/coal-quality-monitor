"""FastAPI 应用入口"""
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, SessionLocal

# 导入所有模型确保建表时包含（顺序不可颠倒）
from app.models.user import User, UserRole
from app.models.supplier import Supplier
from app.models.batch import CoalBatch
from app.models.test import QualityTest
from app.models.alert import QualityAlert
from app.database import Base

from app.api import auth, batches, tests, alerts, suppliers, dashboard, export, ws, integration


def _create_default_admin(db) -> None:
    """若不存在 admin 用户则自动创建"""
    from passlib.context import CryptContext
    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        return
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    admin = User(
        username="admin",
        hashed_password=pwd_context.hash("admin123"),
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(admin)
    db.commit()
    print("[启动] 默认管理员账户已创建：admin / admin123")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表并创建默认 admin"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _create_default_admin(db)
    finally:
        db.close()
    print(f"[启动] {settings.APP_NAME} v{settings.APP_VERSION} 已就绪")
    yield
    print("[关闭] 应用正在关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="煤质化验数据比对系统 API：对比港口化验与入厂化验，自动检测异常偏差，生成分级预警",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
allowed_origins = settings.ALLOWED_ORIGINS or [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 注册路由 ──────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(batches.router)
app.include_router(tests.router)
app.include_router(alerts.router)
app.include_router(suppliers.router)
app.include_router(dashboard.router)
app.include_router(export.router)
app.include_router(ws.router)
app.include_router(integration.router)


# ── 健康检查 ──────────────────────────────────────────────────────────────────

@app.get("/health", tags=["系统"], summary="健康检查")
def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/", tags=["系统"], summary="根路径")
def root():
    return {
        "message": f"欢迎使用 {settings.APP_NAME}",
        "docs": "/docs",
        "redoc": "/redoc",
    }
