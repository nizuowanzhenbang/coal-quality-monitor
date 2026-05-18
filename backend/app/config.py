"""应用配置"""
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./coal_quality.db"
    SECRET_KEY: str = "coal-quality-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    APP_NAME: str = "煤质化验数据比对系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: Optional[List[str]] = None

    # 热值偏差阈值（相对偏差率，正值=入厂低于港口）
    CALORIFIC_GENERAL_THRESHOLD: float = 0.010   # 1%
    CALORIFIC_SEVERE_THRESHOLD: float = 0.020    # 2%

    # 灰分偏差阈值（绝对偏差，%，正值=入厂高于港口）
    ASH_GENERAL_THRESHOLD: float = 0.80
    ASH_SEVERE_THRESHOLD: float = 1.50

    # 硫分偏差阈值（绝对偏差，%）
    SULFUR_GENERAL_THRESHOLD: float = 0.080
    SULFUR_SEVERE_THRESHOLD: float = 0.150

    # 水分偏差阈值（绝对偏差，%）
    MOISTURE_GENERAL_THRESHOLD: float = 1.0
    MOISTURE_SEVERE_THRESHOLD: float = 2.0

    # 合同热值亏损阈值（kcal/kg）
    CONTRACT_CAL_GENERAL: float = 200.0
    CONTRACT_CAL_SEVERE: float = 400.0

    # 合同灰分超标阈值（%）
    CONTRACT_ASH_GENERAL: float = 0.50
    CONTRACT_ASH_SEVERE: float = 1.00

    # 合同硫分超标阈值（%）
    CONTRACT_SULFUR_GENERAL: float = 0.05
    CONTRACT_SULFUR_SEVERE: float = 0.10

    # 供应商评分窗口（最近N个批次）
    SUPPLIER_SCORE_WINDOW: int = 20

    # 闭环集成：运输监督系统
    INTEGRATION_SECRET: str = "coal-integration-shared-secret"

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
