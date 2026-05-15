"""供应商模型"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Enum, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class SupplierStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"       # 暂停合作
    BLACKLISTED = "BLACKLISTED"   # 黑名单


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True, comment="供应商名称")
    contact_person = Column(String(50), nullable=True, comment="联系人")
    contact_phone = Column(String(20), nullable=True, comment="联系电话")
    coal_types = Column(String(200), nullable=True, comment="供应煤种（逗号分隔）")
    credit_score = Column(Float, default=100.0, comment="信用评分 0-100")
    status = Column(Enum(SupplierStatus), default=SupplierStatus.ACTIVE, comment="合作状态")
    notes = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    batches = relationship("CoalBatch", back_populates="supplier")
