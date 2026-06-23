from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.schemas.evaluation import DomainResponse


class EvaluationStatus(str, Enum):
    """评测执行状态枚举"""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SUCCESS = "success"


class JudgeMode(str, Enum):
    """LLM Judge 评判模式枚举"""

    STANDARD = "standard"
    STRICT = "strict"
    LENIENT = "lenient"


JUDGE_MODE_INSTRUCTIONS = {
    JudgeMode.STRICT: "请严格评估，对任何问题都要扣分，证据引用必须精确到句子级别。",
    JudgeMode.LENIENT: "请宽容评估，只要基本满足要求就给高分，容忍小的瑕疵。",
    JudgeMode.STANDARD: "请公平评估，既不严格也不宽容。",
}


class EvaluationResult(BaseModel):
    case_id: str
    status: EvaluationStatus
    model_name: str | None = None
    adapter_name: str
    response: DomainResponse | None = None
    latency_ms: float
    error_message: str | None = None


class PayloadModel(BaseModel):
    case_id: str
    domain: str
    metadata: dict[str, Any] | None = None


# =====================================================================
# API请求模型 - 统一输入验证
# =====================================================================


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""

    ids: list[int] = Field(..., min_length=1, max_length=1000, description="要删除的记录ID列表")


class BatchUpdateRequest(BaseModel):
    """批量更新请求"""

    ids: list[int] = Field(..., min_length=1, max_length=1000, description="要更新的记录ID列表")
    data: dict[str, Any] = Field(..., min_length=1, description="要更新的数据")


class RecordUpdateRequest(BaseModel):
    """单条记录更新请求"""

    model_name: str | None = Field(None, description="模型名称")
    adapter_name: str | None = Field(None, description="适配器名称")
    status: str | None = Field(None, description="状态")


class EvalConfigRequest(BaseModel):
    """评估配置请求"""

    id: str | None = Field(None, description="配置ID，不提供则自动生成")
    name: str = Field(..., min_length=1, max_length=100, description="配置名称")
    evaluator_type: str = Field(..., description="评估器类型")
    config: dict[str, Any] = Field(default_factory=dict, description="配置内容")
    enabled: bool = Field(True, description="是否启用")


class BatchEvaluateRequest(BaseModel):
    """批量评估请求"""

    cases: list[dict[str, Any]] = Field(
        ..., min_length=1, max_length=100, description="评估用例列表"
    )
    evaluator_type: str = Field(..., description="评估器类型")
    model_name: str | None = Field(None, description="模型名称")


class GoldenDatasetRequest(BaseModel):
    """黄金数据集创建请求"""

    name: str = Field(..., min_length=1, max_length=100, description="数据集名称")
    description: str | None = Field(None, max_length=500, description="数据集描述")
    domain: str = Field(..., description="领域")
    samples: list[dict[str, Any]] = Field(default_factory=list, description="样本列表")


class GoldenSampleRequest(BaseModel):
    """黄金样本添加请求"""

    input_text: str = Field(..., min_length=1, description="输入文本")
    expected_output: str = Field(..., description="期望输出")
    metadata: dict[str, Any] | None = Field(None, description="元数据")


class FineTuneExportRequest(BaseModel):
    """微调数据导出请求"""

    evaluator_type: str = Field(..., description="评估器类型")
    format: str = Field("jsonl", pattern="^(jsonl|csv)$", description="导出格式")
    filters: dict[str, Any] | None = Field(None, description="过滤条件")


class ModelCompareRequest(BaseModel):
    """模型比较请求"""

    model_a: str = Field(..., description="模型A名称")
    model_b: str = Field(..., description="模型B名称")
    test_cases: list[dict[str, Any]] = Field(..., min_length=1, description="测试用例")
    metrics: list[str] | None = Field(None, description="比较指标")
