# src/exceptions.py
from enum import Enum


class ErrorCode(Enum):
    """标准化错误码体系 - 用于测试断言和API响应"""

    # 契约验证错误 (E1xxx)
    EMPTY_INPUT = "E1001"
    INVALID_FORMAT = "E1002"
    MISSING_REQUIRED_FIELD = "E1003"
    INVALID_TYPE = "E1004"
    OUT_OF_RANGE = "E1005"

    # 领域逻辑错误 (E2xxx)
    EVALUATOR_NOT_FOUND = "E2001"
    MODEL_NOT_AVAILABLE = "E2002"
    UNSUPPORTED_ACTION = "E2003"
    INVALID_PAYLOAD = "E2004"
    EVALUATION_FAILED = "E2005"

    # 安全相关错误 (E3xxx)
    INJECTION_DETECTED = "E3001"
    JAILBREAK_DETECTED = "E3002"
    DATA_LEAK_DETECTED = "E3003"
    TOOL_ABUSE_DETECTED = "E3004"

    # 基础设施错误 (E4xxx)
    DB_CONNECTION_FAILED = "E4001"
    REDIS_CONNECTION_FAILED = "E4002"
    LLM_TIMEOUT = "E4003"
    LLM_RATE_LIMITED = "E4004"
    CONNECTION_POOL_EXHAUSTED = "E4005"

    # 分布式系统错误 (E5xxx)
    LOCK_ACQUIRE_FAILED = "E5001"
    IDEMPOTENCY_CONFLICT = "E5002"
    CIRCUIT_BREAKER_OPEN = "E5003"


class BasePlatformError(Exception):
    """平台所有异常的基类"""

    def __init__(self, message: str, code: str | ErrorCode = "INTERNAL_ERROR"):
        if isinstance(code, ErrorCode):
            code = code.value
        self.message = message
        self.code = code
        super().__init__(self.message)

    def __str__(self):
        return f"[{self.code}] {self.message}"

    def to_dict(self) -> dict:
        """转换为API响应格式"""
        return {"code": self.code, "message": self.message}


class ContractValidationError(BasePlatformError):
    """契约层错误：当输入数据不符合 Pydantic 模型时触发"""

    def __init__(
        self, message="输入数据校验失败", code: str | ErrorCode = ErrorCode.INVALID_FORMAT
    ):
        super().__init__(message, code=code)


class EmptyInputError(ContractValidationError):
    """空输入错误"""

    def __init__(self, field_name: str = "input"):
        super().__init__(message=f"{field_name}不能为空", code=ErrorCode.EMPTY_INPUT)


class DomainLogicError(BasePlatformError):
    """领域层错误：业务规则触发的异常（如适配器缺失）"""

    def __init__(self, message="业务执行失败", code: str | ErrorCode = ErrorCode.EVALUATION_FAILED):
        super().__init__(message, code=code)


class EvaluatorNotFoundError(DomainLogicError):
    """评估器未找到"""

    def __init__(self, evaluator_type: str):
        super().__init__(
            message=f"评估器 '{evaluator_type}' 未注册", code=ErrorCode.EVALUATOR_NOT_FOUND
        )


class UnsupportedActionError(DomainLogicError):
    """不支持的操作类型"""

    def __init__(self, action: str):
        super().__init__(message=f"未知的 action: {action}", code=ErrorCode.UNSUPPORTED_ACTION)


class InfrastructureError(BasePlatformError):
    """防腐层错误：底层资源异常（DB/Cache 连接失败）"""

    def __init__(
        self, message="基础设施服务故障", code: str | ErrorCode = ErrorCode.DB_CONNECTION_FAILED
    ):
        super().__init__(message, code=code)


class LLMTimeoutError(InfrastructureError):
    """LLM 调用超时"""

    def __init__(self, timeout_seconds: float):
        super().__init__(message=f"LLM 调用超时 ({timeout_seconds}s)", code=ErrorCode.LLM_TIMEOUT)


class ConnectionPoolExhaustedError(InfrastructureError):
    """连接池耗尽"""

    def __init__(self, pool_type: str = "database"):
        super().__init__(
            message=f"{pool_type} 连接池已耗尽", code=ErrorCode.CONNECTION_POOL_EXHAUSTED
        )


class SecurityError(DomainLogicError):
    """安全检测错误"""

    def __init__(self, message: str, code: ErrorCode):
        super().__init__(message=message, code=code)


class InjectionDetectedError(SecurityError):
    """注入攻击检测"""

    def __init__(self, attack_type: str):
        super().__init__(
            message=f"检测到 {attack_type} 注入攻击", code=ErrorCode.INJECTION_DETECTED
        )


class IdempotencyError(BasePlatformError):
    """幂等性检查错误"""

    def __init__(self, message: str, code: str | ErrorCode = ErrorCode.IDEMPOTENCY_CONFLICT):
        super().__init__(message, code=code)
