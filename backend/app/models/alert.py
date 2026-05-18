"""预警模型"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Enum, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class AlertType(str, enum.Enum):
    CALORIFIC_SHORTAGE = "CALORIFIC_SHORTAGE"         # 热值亏损（港口>入厂）
    ASH_EXCESS = "ASH_EXCESS"                         # 灰分偏高（入厂>港口）
    SULFUR_EXCESS = "SULFUR_EXCESS"                   # 硫分偏高
    MOISTURE_EXCESS = "MOISTURE_EXCESS"               # 水分偏高
    CONTRACT_CAL_BREACH = "CONTRACT_CAL_BREACH"       # 合同热值违约
    CONTRACT_ASH_BREACH = "CONTRACT_ASH_BREACH"       # 合同灰分违约
    CONTRACT_SULFUR_BREACH = "CONTRACT_SULFUR_BREACH" # 合同硫分违约
    COMPREHENSIVE = "COMPREHENSIVE"                   # 综合异常（多指标同时偏差）
    # 运输监督闭环预警（来自 coal-transport-monitor）
    TRANSPORT_WEIGHT = "TRANSPORT_WEIGHT"             # 运输重量异常
    TRANSPORT_TIME = "TRANSPORT_TIME"                 # 运输超时
    TRANSPORT_SEAL = "TRANSPORT_SEAL"                 # 铅封异常


class Severity(str, enum.Enum):
    GENERAL = "GENERAL"   # 一般预警
    SEVERE = "SEVERE"     # 严重预警


class AlertStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class QualityAlert(Base):
    __tablename__ = "quality_alerts"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("coal_batches.id"), nullable=False, index=True, comment="批次ID")
    alert_type = Column(Enum(AlertType), nullable=False, comment="预警类型")
    severity = Column(Enum(Severity), nullable=False, comment="严重程度")
    description = Column(Text, nullable=False, comment="预警描述")
    port_value = Column(Float, nullable=True, comment="港口检测值")
    factory_value = Column(Float, nullable=True, comment="入厂检测值")
    deviation = Column(Float, nullable=True, comment="绝对偏差")
    deviation_rate = Column(Float, nullable=True, comment="相对偏差率")
    threshold_value = Column(Float, nullable=True, comment="触发阈值")
    status = Column(Enum(AlertStatus), default=AlertStatus.PENDING, comment="处理状态")
    resolved_by = Column(String(50), nullable=True, comment="处理人")
    resolved_at = Column(DateTime, nullable=True, comment="处理时间")
    resolution_notes = Column(Text, nullable=True, comment="处理备注")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    batch = relationship("CoalBatch", back_populates="alerts")
