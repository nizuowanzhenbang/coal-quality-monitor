"""化验列既定口径；显式单位换算不推断分析基准。"""
from math import isfinite
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, FiniteFloat, ValidationInfo, field_validator

BASES = {
    'calorific_value_net': 'ar', 'calorific_value_gross': 'ad',
    'ash_content': 'd', 'sulfur_content': 'd', 'moisture_total': 'ar',
    'moisture_inherent': 'ad', 'volatile_matter': 'd', 'fixed_carbon': 'd',
}
CORE = ('calorific_value_net', 'ash_content', 'sulfur_content', 'moisture_total')
CONTROL_FIELDS = {'calorific_value_unit', 'measurement_bases'}


def normalize_nonfinite(value):
    # FastAPI 的 422 详情也须能序列化，不能直接包含解析后的 inf/nan。
    return str(value) if isinstance(value, float) and not isfinite(value) else value


HeatMeasurement = Annotated[FiniteFloat, BeforeValidator(normalize_nonfinite), Field(ge=0, le=10000)]
PercentMeasurement = Annotated[FiniteFloat, BeforeValidator(normalize_nonfinite), Field(ge=0, le=100)]


class MeasurementInput(BaseModel):
    # 必须在热值字段之前，field validator 只换算本次给出的值。
    calorific_value_unit: Literal['kcal/kg', 'MJ/kg'] = 'kcal/kg'
    measurement_bases: dict[str, str] = Field(default_factory=dict)
    calorific_value_net: HeatMeasurement | None = None
    calorific_value_gross: HeatMeasurement | None = None
    ash_content: PercentMeasurement | None = None
    sulfur_content: PercentMeasurement | None = None
    moisture_total: PercentMeasurement | None = None
    moisture_inherent: PercentMeasurement | None = None
    volatile_matter: PercentMeasurement | None = None
    fixed_carbon: PercentMeasurement | None = None

    @field_validator('calorific_value_net', 'calorific_value_gross', mode='before')
    @classmethod
    def convert_heat(cls, value, info: ValidationInfo):
        if value is None or info.data.get('calorific_value_unit') != 'MJ/kg':
            return value
        try:
            return normalize_nonfinite(float(value) * 1000 / 4.1868)
        except (ValueError, TypeError):
            return value  # 交由有限数校验产生字段级错误。

    @field_validator('measurement_bases')
    @classmethod
    def validate_bases(cls, value):
        for field, basis in value.items():
            if field not in BASES or basis != BASES[field]:
                raise ValueError('不支持该指标或基准；请提供既定口径，不能自动换算分析基准')
        return value


def measurement_metadata():
    return {
        'calorific_value_unit': 'kcal/kg',
        'measurement_bases': dict(BASES),
        'measurement_units': {field: 'kcal/kg' if field.startswith('calorific') else '%' for field in BASES},
    }


def assessment(tests):
    by_source = {test.test_type: test for test in tests}
    missing = {}
    for source in ('PORT', 'FACTORY'):
        record = by_source.get(source)
        missing[source] = [field for field in CORE if record is None or getattr(record, field) is None]
    return {'complete': not any(missing.values()), 'missing_by_source': missing}


def safe_rate(difference, baseline):
    """不可表示的相对偏差不保存无穷值；绝对偏差仍可用于预警。"""
    if difference is None or baseline is None or baseline == 0:
        return None
    rate = difference / baseline
    return rate if isfinite(rate) else None
