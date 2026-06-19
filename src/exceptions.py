# src/exceptions.py


class BasePlatformError(Exception):
    """平台所有异常的基类"""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)

    def __str__(self):
        return f"[{self.code}] {self.message}"


class ContractValidationError(BasePlatformError):
    """契约层错误：当输入数据不符合 Pydantic 模型时触发"""

    def __init__(self, message="输入数据校验失败"):
        super().__init__(message, code="CONTRACT_ERROR")


class DomainLogicError(BasePlatformError):
    """领域层错误：业务规则触发的异常（如适配器缺失）"""

    def __init__(self, message="业务执行失败"):
        super().__init__(message, code="DOMAIN_ERROR")


class InfrastructureError(BasePlatformError):
    """防腐层错误：底层资源异常（DB/Cache 连接失败）"""

    def __init__(self, message="基础设施服务故障"):
        super().__init__(message, code="INFRA_ERROR")
