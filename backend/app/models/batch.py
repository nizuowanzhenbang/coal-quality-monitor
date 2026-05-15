"""煤炭批次模型"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Enum, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class BatchStatus(str, enum.Enum):
    PENDING = "PENDING"       # 待入厂化验
    PARTIAL = "PARTIAL"       # 仅有港口化验
    COMPLETED = "COMPLETED"   # 双端化验完成
    ALERT = "ALERT"           # 存在预警
    SEVERE = "SEVERE"         # 存在严重预警


class CoalBatch(Base):
    __tablename__ = "coal_batches"

    id = Column(Integer, primary_key=True, index=True)
    batch_number = Column(String(50), nullable=False, unique=True, index=True, comment="批次号")
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False, index=True, comment="供应商ID")
    coal_type = Column(String(50), nullable=True, comment="煤种")
    departure_port = Column(String(100), nullable=True, comment="发货港口")
    arrival_plant = Column(String(100), nullable=True, comment="到厂名称")
    contract_quantity = Column(Float, nullable=True, comment="合同数量(吨)")
    actual_quantity = Column(Float, nullable=True, comment="实际数量(吨)")

    # 合同质量指标（基准线）
    contract_calorific_value = Column(Float, nullable=True, comment="合同热值(kcal/kg)")
    contract_ash_max = Column(Float, nullable=True, comment="合同灰分上限(%)")
    contract_sulfur_max = Column(Float, nullable=True, comment="合同硫分上限(%)")
    contract_moisture_max = Column(Float, nullable=True, comment="合同水分上限(%)")

    status = Column(Enum(BatchStatus), default=BatchStatus.PENDING, comment="批次状态")
    alert_count = Column(Integer, default=0, comment="预警数量")
    risk_score = Column(Float, default=0.0, comment="综合风险评分")
    notes = Column(Text, nullable=True, comment="备注")
    arrival_date = Column(DateTime, nullable=True, comment="到厂日期")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    supplier = relationship("Supplier", back_populates="batches")
    tests = relationship("QualityTest", back_populates="batch", cascade="all, delete-orphan")
    alerts = relationship("QualityAlert", back_populates="batch", cascade="all, delete-orphan")
