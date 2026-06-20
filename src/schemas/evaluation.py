import time
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EvaluationStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class DomainResponse(BaseModel):
    is_valid: bool = True
    text: str | None = None
    score: float | None = None
    error: str | None = None
    metadata: dict | None = None
    data: Any | None = None

    model_config = {"extra": "allow"}


class EvaluationSchema(BaseModel):
    id: str = Field(..., description="评估记录唯一ID")
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
