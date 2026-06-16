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

    model_config = ConfigDict(frozen=True)


# 覆盖所有潜在的领域类型
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
]
