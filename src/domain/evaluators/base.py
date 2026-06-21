from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

from src.exceptions import BasePlatformError
from src.schemas.evaluation import DomainResponse, EvaluationSchema

if TYPE_CHECKING:
    from src.domain.models.base import BaseLLMClient


class BaseEvaluator(ABC):
    def __init__(self, client: Optional["BaseLLMClient"] = None):
        self.client = client

    @abstractmethod
    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """子类实现评测逻辑，禁止返回 None。"""
        pass

    def get_payload_data(self, request: Any, key: str, default: Any = None) -> Any:
        return request.payload.get(key, default)

    def get_input_text(self, request: EvaluationSchema, default: str = "") -> str:
        """兼容 user_input / text 两种字段命名。"""
        return (
            self.get_payload_data(request, "user_input")
            or self.get_payload_data(request, "text")
            or default
        )

    def require_client(self) -> DomainResponse | None:
        if not self.client:
            return DomainResponse(is_valid=False, error="LLM client 未配置")
        return None

    def safe_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        try:
            response = self.evaluate(request)
            if response is None:
                return DomainResponse(
                    is_valid=False, error="EVALUATION_ERROR: Evaluator returned None unexpectedly."
                )
            return response
        except BasePlatformError:
            raise
        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.error(f"Evaluation execution error for {request.type}: {e}", exc_info=True)
            return DomainResponse(is_valid=False, error=f"EVALUATION_ERROR: {str(e)}")

    def create_error_response(
        self, error_message: str, error_code: str | None = None, metadata: dict | None = None
    ) -> DomainResponse:
        """创建统一的错误响应"""
        response_metadata = metadata or {}
        if error_code:
            response_metadata["error_code"] = error_code

        return DomainResponse(is_valid=False, error=error_message, metadata=response_metadata)

    def create_success_response(
        self, text: str = "评估完成", score: float = 1.0, data: dict | None = None
    ) -> DomainResponse:
        """创建统一的成功响应"""
        return DomainResponse(is_valid=True, text=text, score=score, data=data or {})

    # ===================== 公共辅助方法 =====================
    # 降低评估器代码重复率

    def validate_input(self, request: EvaluationSchema) -> DomainResponse | None:
        """验证输入文本，返回错误响应或None"""
        user_input = self.get_input_text(request)
        if not user_input:
            return DomainResponse(is_valid=False, error="user_input/text 不能为空")
        return None

    def validate_expected(
        self, request: EvaluationSchema, key: str = "expected_output"
    ) -> DomainResponse | None:
        """验证期望输出"""
        expected = self.get_payload_data(request, key)
        if not expected:
            return DomainResponse(is_valid=False, error=f"{key} 不能为空")
        return None

    def require_client_with_error(self) -> DomainResponse | None:
        """检查 client 是否配置，返回错误或None"""
        if not self.client:
            return DomainResponse(is_valid=False, error="LLM client 未配置")
        return None

    def build_prompt_response(
        self,
        llm_output: str,
        score: float,
        data_prefix: str = "result",
        metadata: dict | None = None,
    ) -> DomainResponse:
        """构建标准的 Prompt 评估响应"""
        return DomainResponse(
            is_valid=True,
            text=llm_output,
            score=score,
            data=metadata or {f"{data_prefix}": llm_output},
        )
