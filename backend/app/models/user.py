"""用户模型"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean
from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"       # 管理员
    OPERATOR = "OPERATOR" # 操作员
    VIEWER = "VIEWER"     # 只读查看员


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True, comment="用户名")
    hashed_password = Column(String(200), nullable=False, comment="哈希密码")
    role = Column(Enum(UserRole), default=UserRole.VIEWER, comment="角色")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
