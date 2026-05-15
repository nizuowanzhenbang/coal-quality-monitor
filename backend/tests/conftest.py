"""测试固定装置：内存 SQLite 数据库"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
# 导入所有模型，确保建表完整
from app.models.user import User
from app.models.supplier import Supplier
from app.models.batch import CoalBatch
from app.models.test import QualityTest
from app.models.alert import QualityAlert

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_engine():
    """每个测试函数独立的内存数据库 engine"""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """每个测试函数独立的数据库会话"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def sample_supplier(db_session):
    """创建示例供应商"""
    supplier = Supplier(
        name="测试供应商",
        contact_person="张三",
        coal_types="测试煤",
        credit_score=100.0,
    )
    db_session.add(supplier)
    db_session.commit()
    db_session.refresh(supplier)
    return supplier


@pytest.fixture(scope="function")
def sample_batch(db_session, sample_supplier):
    """创建示例批次（含合同指标）"""
    from app.models.batch import CoalBatch, BatchStatus
    batch = CoalBatch(
        batch_number="TEST-BATCH-001",
        supplier_id=sample_supplier.id,
        coal_type="测试煤",
        contract_calorific_value=5800.0,
        contract_ash_max=18.0,
        contract_sulfur_max=1.0,
        contract_moisture_max=15.0,
        status=BatchStatus.PARTIAL,
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)
    return batch
