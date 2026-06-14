from enum import Enum
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EvaluationStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class DomainResponse(BaseModel):
    is_valid: bool = True
    text: Optional[str] = None
    score: Optional[float] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None
    data: Optional[Any] = None

    model_config = {"extra": "allow"}


class EvaluationSchema(BaseModel):
    id: str = Field(..., description="评估记录唯一ID")
    type: str = Field(..., description="评估类型")
    payload: Dict[str, Any] = Field(..., description="业务数据")

    metadata: Optional[Dict[str, Any]] = Field(None, description="可选的元数据配置")

    model_config = ConfigDict(frozen=True)


# 覆盖所有潜在的领域类型
DomainType = Literal["finance", "crm", "hr", "text", "code_review", "general", "code"]
