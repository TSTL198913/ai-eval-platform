import time
import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class EvaluationStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class EvaluatorStatus(str, Enum):
    SUCCESS = "success"
    CANNOT_EVALUATE = "cannot_evaluate"
    PARTIAL = "partial"
    ERROR = "error"


class ConfidenceLevel(str, Enum):
    """置信度等级 - 2026工业级标准要求

    用于量化评估结果的可靠性，下游系统根据置信度决定是否信任结果。
    """
    HIGH = "high"      # >= 0.9: 完整数据 + LLM评估
    MEDIUM = "medium"  # >= 0.7: 部分数据 + LLM评估 或 完整数据 + Embedding
    LOW = "low"        # >= 0.5: 部分数据 + Embedding
    VERY_LOW = "very_low"  # < 0.5: 仅语法检查 或 数据严重缺失


class DomainResponse(BaseModel):
    text: str | None = None
    score: float | None = None
    evaluation_status: EvaluatorStatus = EvaluatorStatus.SUCCESS
    confidence: float | None = Field(
        default=None,
        ge=0.0, le=1.0,
        description="评估置信度 (0.0-1.0)，越高表示结果越可靠"
    )
    confidence_level: ConfidenceLevel | None = Field(
        default=None,
        description="置信度等级（从 confidence 自动计算）"
    )
    error: str | None = None
    metadata: dict | None = None
    data: Any | None = None
    level: str | None = Field(
        default=None,
        description="评估等级（excellent/good/acceptable/poor）"
    )
    details: dict | None = Field(
        default=None,
        description="评估详情"
    )
    status_code: int | None = Field(
        default=None,
        description="HTTP状态码（用于API响应）"
    )

    model_config = {"extra": "forbid"}

    @model_validator(mode="before")
    @classmethod
    def warn_deprecated_is_valid(cls, values: dict) -> dict:
        """警告旧代码传入 is_valid 参数"""
        if "is_valid" in values:
            import warnings
            warnings.warn(
                "is_valid 参数已废弃，请使用 evaluation_status 替代",
                DeprecationWarning,
                stacklevel=3
            )
            del values["is_valid"]
        return values

    @computed_field(return_type=bool)
    @property
    def is_valid(self) -> bool:
        """
        兼容旧代码的计算属性，基于 evaluation_status 推导。
        
        2026 工业级标准：移除 is_valid 字段，只使用 evaluation_status。
        is_valid 仅作为向后兼容的计算属性保留，使用 @computed_field 确保序列化包含此字段。
        
        状态映射：
        - SUCCESS → True（评估成功，有有效分数）
        - PARTIAL → True（部分评估，结果有效）
        - CANNOT_EVALUATE → False（无法评估，无有效结果）
        - ERROR → False（评估失败，结果无效）
        """
        return self.evaluation_status in (EvaluatorStatus.SUCCESS, EvaluatorStatus.PARTIAL)

    @model_validator(mode="after")
    def compute_confidence_level(self) -> "DomainResponse":
        """自动计算置信度等级（2026工业级标准要求）"""
        if self.confidence is not None and self.confidence_level is None:
            if self.confidence >= 0.9:
                self.confidence_level = ConfidenceLevel.HIGH
            elif self.confidence >= 0.7:
                self.confidence_level = ConfidenceLevel.MEDIUM
            elif self.confidence >= 0.5:
                self.confidence_level = ConfidenceLevel.LOW
            else:
                self.confidence_level = ConfidenceLevel.VERY_LOW
        return self


class EvaluationSchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="评估记录唯一ID")
    type: str = Field(..., description="评估类型")
    payload: dict[str, Any] = Field(..., description="业务数据")

    metadata: dict[str, Any] | None = Field(None, description="可选的元数据配置")

    model_provider: str | None = Field(
        None, description="评估器使用的LLM提供者（deepseek/openai/anthropic/ollama/qwen）"
    )
    model_name: str | None = Field(None, description="评估器使用的LLM模型名称")

    model_config = ConfigDict(frozen=True)


class TrajectoryStep(BaseModel):
    step_id: str
    action: str
    thought: str | None = None
    observation: str | None = None
    tool_name: str | None = None
    tool_args: dict | None = None
    tool_result: Any | None = None
    timestamp: float = Field(default_factory=lambda: time.time())
    token_usage: int = 0
    latency_ms: float = 0


class AgentTrajectory(BaseModel):
    trajectory_id: str
    case_id: str
    model_name: str
    steps: list[TrajectoryStep] = []
    total_tokens: int = 0
    total_latency_ms: float = 0
    final_output: str | None = None
    success: bool = False

    def add_step(self, step: TrajectoryStep):
        self.steps.append(step)
        self.total_tokens += step.token_usage
        self.total_latency_ms += step.latency_ms


class DriftDetectionResult(BaseModel):
    case_id: str
    drift_detected: bool
    baseline_score: float
    current_score: float
    drift_score: float
    confidence: float
    warning_threshold: float = 0.2


class CostMetrics(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float


DomainType = Literal[
    "finance",
    "crm",
    "hr",
    "text",
    "code_review",
    "general",
    "code",
    "semantic",
    "sentiment",
    "classification",
    "translation",
    "grammar",
    "summary",
    "fact_check",
    "qa",
    "llm_as_judge",
    "security",
    "drift",
    "trajectory",
    "prompt_regression",
    "memory",
    "function_call",
    "multi_agent",
]


class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名", min_length=1)
    password: str = Field(..., description="密码", min_length=1)


class BatchDeleteRequest(BaseModel):
    ids: list[int] = Field(..., description="要删除的记录ID列表", min_length=1)


class BatchUpdateRequest(BaseModel):
    ids: list[int] = Field(..., description="要更新的记录ID列表", min_length=1)
    data: dict = Field(..., description="更新数据")


class BatchEvaluateRequest(BaseModel):
    cases: list[dict] = Field(..., description="评估用例列表", min_length=1)
