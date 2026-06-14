from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel

from src.schemas.evaluation import DomainResponse


class EvaluationStatus(str, Enum):
    """评测执行状态枚举"""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SUCCESS = "success"


class EvaluationResult(BaseModel):
    case_id: str
    status: EvaluationStatus
    model_name: str
    adapter_name: str
    response: DomainResponse
    latency_ms: float
    error_message: Optional[str] = None



class PayloadModel(BaseModel):
    case_id: str
    domain: str
    metadata: Optional[Dict[str, Any]] = None


