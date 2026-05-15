"""化验记录模型"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Enum, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class TestType(str, enum.Enum):
    PORT = "PORT"       # 港口化验（出发地）
    FACTORY = "FACTORY" # 入厂化验（到达地）


class QualityTest(Base):
    __tablename__ = "quality_tests"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("coal_batches.id"), nullable=False, index=True, comment="批次ID")
    test_type = Column(Enum(TestType), nullable=False, comment="化验类型")
    test_org = Column(String(100), nullable=True, comment="化验机构")
    test_time = Column(DateTime, nullable=True, comment="化验时间")
    report_number = Column(String(100), nullable=True, comment="化验报告编号")

    # 核心化验指标（空气干燥基 ad 或 收到基 ar）
    calorific_value_net = Column(Float, nullable=True, comment="低位发热量 Qnet,ar (kcal/kg)")
    calorific_value_gross = Column(Float, nullable=True, comment="高位发热量 Qgr,ad (kcal/kg)")
    ash_content = Column(Float, nullable=True, comment="灰分 Ad (%)")
    sulfur_content = Column(Float, nullable=True, comment="全硫 St,d (%)")
    moisture_total = Column(Float, nullable=True, comment="全水分 Mt (%)")
    moisture_inherent = Column(Float, nullable=True, comment="分析水分 Mad (%)")
    volatile_matter = Column(Float, nullable=True, comment="挥发分 Vd (%)")
    fixed_carbon = Column(Float, nullable=True, comment="固定碳 FCd (%)")

    notes = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    batch = relationship("CoalBatch", back_populates="tests")
