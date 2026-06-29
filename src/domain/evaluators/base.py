import asyncio
import logging
import re
import threading
import time
import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

from src.distributed.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    global_registry,
)
from src.domain.evaluators.strategies.score_parsing import DEFAULT_PARSER
from src.exceptions import BasePlatformError
from src.schemas.evaluation import DomainResponse, EvaluationSchema

if TYPE_CHECKING:
    from src.domain.evaluators.fallback_policy import BaseFallbackPolicy
    from src.domain.models.base import BaseLLMClient

logger = logging.getLogger(__name__)


class BaseEvaluator(ABC):
    _breaker_cache: dict[str, CircuitBreaker] = {}
    _breaker_cache_lock = threading.Lock()

    def __init__(
        self,
        client: Optional["BaseLLMClient"] = None,
        fallback_policy: Optional["BaseFallbackPolicy"] = None,
    ):
        self.client = client
        # 基类统一管理降级策略，由子类在构造时注入具体策略（如 SemanticTaskPolicy 等）
        self.fallback_policy = fallback_policy

    # ===================== 核心评测契约（双轨制） =====================

    @abstractmethod
    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """
        同步核心逻辑：子类必须实现。
        纯规则评估器或未做异步改造的评估器在此编写核心逻辑。
        """
        pass

    async def _do_evaluate_async(self, request: EvaluationSchema) -> DomainResponse:
        """
        异步核心逻辑：子类可选择性重写。
        默认利用 asyncio.to_thread 将同步方法分发至线程池执行。
        对于外接异步 Client 的高级评估器，重写此方法可以获得极高的并发性能。
        """
        return await asyncio.to_thread(self._do_evaluate, request)

    # ===================== 同步编排中枢 =====================

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """全局统一的同步评测入口，负责拦截异常、触发熔断和执行降级"""
        evaluator_name = type(self).__name__
        breaker = self._get_breaker()
        trace_id = request.id or str(uuid.uuid4())
        start_time = time.perf_counter()

        try:
            result = breaker.call_sync(lambda: self._do_evaluate(request))
            elapsed = time.perf_counter() - start_time
            logger.info(
                f"评估完成 | trace_id={trace_id} | evaluator={evaluator_name} | "
                f"score={result.score if result.score is not None else 0.0:.4f} | "
                f"valid={result.is_valid} | "
                f"elapsed={elapsed:.4f}s"
            )
            if result.data is None:
                result.data = {}
            result.data["execution_time_ms"] = round(elapsed * 1000, 2)
            result.data["trace_id"] = trace_id
            return result
        except CircuitBreakerError as e:
            elapsed = time.perf_counter() - start_time
            logger.error(
                f"熔断触发 | trace_id={trace_id} | evaluator={evaluator_name} | "
                f"elapsed={elapsed:.4f}s | error={e}"
            )
            return self._execute_fallback_infrastructure(request, error=e)
        except BasePlatformError:
            raise
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error(
                f"运行时异常 | trace_id={trace_id} | evaluator={evaluator_name} | "
                f"elapsed={elapsed:.4f}s | error={e}",
                exc_info=True,
            )
            return self._execute_fallback_infrastructure(request, error=e)

    # ===================== 🚀 2026 高并发异步编排中枢 =====================

    async def evaluate_async(self, request: EvaluationSchema) -> DomainResponse:
        """
        全局统一的异步评测入口（原生支持 asyncio）。
        完美承接上层业务的 asyncio.gather() 批量并发调用。
        """
        evaluator_name = type(self).__name__
        breaker = self._get_breaker()
        trace_id = request.id or str(uuid.uuid4())
        start_time = time.perf_counter()

        try:
            result = await breaker.call(lambda: self._do_evaluate_async(request))
            elapsed = time.perf_counter() - start_time
            logger.info(
                f"异步评估完成 | trace_id={trace_id} | evaluator={evaluator_name} | "
                f"score={result.score:.4f} | valid={result.is_valid} | "
                f"elapsed={elapsed:.4f}s"
            )
            if result.data is None:
                result.data = {}
            result.data["execution_time_ms"] = round(elapsed * 1000, 2)
            result.data["trace_id"] = trace_id
            return result
        except CircuitBreakerError as e:
            elapsed = time.perf_counter() - start_time
            logger.error(
                f"异步熔断触发 | trace_id={trace_id} | evaluator={evaluator_name} | "
                f"elapsed={elapsed:.4f}s | error={e}"
            )
            return await self._execute_fallback_infrastructure_async(request, error=e)
        except BasePlatformError:
            raise
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error(
                f"异步运行时异常 | trace_id={trace_id} | evaluator={evaluator_name} | "
                f"elapsed={elapsed:.4f}s | error={e}",
                exc_info=True,
            )
            return await self._execute_fallback_infrastructure_async(request, error=e)

    # ===================== 容错与策略沉降编排 =====================

    def _execute_fallback_infrastructure(
        self, request: EvaluationSchema, error: Exception
    ) -> DomainResponse:
        """同步降级中枢"""
        evaluator_name = type(self).__name__
        if not self.fallback_policy:
            return self.create_error_response(
                error_message=f"评估器 {evaluator_name} 失败且未配置降级策略。原始错误: {error}",
                error_code="NO_FALLBACK_POLICY",
            )
        try:
            actual_output = self.get_payload_data(request, "actual_output", "")
            expected_output = self.get_payload_data(request, "expected_output", "")

            score = self.fallback_policy.get_fallback_score(actual_output, expected_output)
            metadata = self._build_fallback_metadata(error)

            return DomainResponse(
                is_valid=True,
                text=actual_output,
                score=score,
                data={"notice": "Derived from backup pipeline"},
                metadata=metadata,
            )
        except Exception as fallback_err:
            return self._handle_cascading_failure(evaluator_name, error, fallback_err)

    async def _execute_fallback_infrastructure_async(
        self, request: EvaluationSchema, error: Exception
    ) -> DomainResponse:
        """异步降级中枢，防止耗时的 CPU 密集型向量计算阻塞异步事件循环"""
        evaluator_name = type(self).__name__
        if not self.fallback_policy:
            return self.create_error_response(
                error_message=f"评估器 {evaluator_name} 失败且未配置降级策略。原始错误: {error}",
                error_code="NO_FALLBACK_POLICY",
            )
        try:
            actual_output = self.get_payload_data(request, "actual_output", "")
            expected_output = self.get_payload_data(request, "expected_output", "")

            # 将可能耗时较长的 CPU 密集型向量相似度降级计算移出主事件循环
            score = await asyncio.to_thread(
                self.fallback_policy.get_fallback_score, actual_output, expected_output
            )
            metadata = self._build_fallback_metadata(error)

            return DomainResponse(
                is_valid=True,
                text=actual_output,
                score=score,
                data={"notice": "Derived from async backup pipeline"},
                metadata=metadata,
            )
        except Exception as fallback_err:
            return self._handle_cascading_failure(evaluator_name, error, fallback_err)

    # ===================== 内部私有公共提取方法 =====================

    def _build_fallback_metadata(self, error: Exception) -> dict:
        """提取并拼装降级元数据"""
        metadata = self.fallback_policy.get_fallback_metadata()
        metadata["confidence"] = self.fallback_policy.get_confidence()
        metadata["fallback_reason"] = str(error)
        return metadata

    def _handle_cascading_failure(
        self, evaluator_name: str, original_err: Exception, fallback_err: Exception
    ) -> DomainResponse:
        """灾难性故障日志双重对齐与阻断"""
        combined_msg = f"原始错误: {original_err} | 降级策略执行失败: {fallback_err}"
        logger.critical(f"评估器 {evaluator_name} 陷入灾难性双重崩溃: {combined_msg}")
        return self.create_error_response(
            error_message=f"评估器全面崩溃，拒绝不安全静默降级: {combined_msg}",
            error_code="CASCADING_FALLBACK_FAILURE",
        )

    # ===================== 文本/数字全防御盾牌（DRY 沉淀） =====================

    def safe_parse_score(self, llm_output: str) -> float | None:
        """【通用连续型数字解析盾牌】全系统复用，精准拦截各类 Prompt 干扰和标点刺客

        2026工业级标准：支持策略链解析，包括数字提取、语义映射、等级解析、关键词降级
        """
        result = DEFAULT_PARSER.parse(llm_output)
        if result is not None:
            return result.score
        return None

    def safe_parse_score_with_ci(self, llm_output: str) -> dict | None:
        """解析评分并返回置信区间（2026工业级标准）"""
        return DEFAULT_PARSER.parse_with_ci(llm_output)

    def safe_parse_category(self, llm_output: str, allowed_categories: list[str]) -> str | None:
        """【通用离散型分类解析盾牌】全系统复用，专治话痨大模型的前言后记"""
        if not llm_output:
            return None
        cleaned = llm_output.strip().lower().rstrip(".。")
        if cleaned in allowed_categories:
            return cleaned
        pattern = r"\b(" + "|".join(map(re.escape, allowed_categories)) + r")\b"
        match = re.search(pattern, cleaned)
        if match:
            return match.group(1)
        return None

    # ===================== 工具辅助方法 =====================

    def get_payload_data(self, request: Any, key: str, default: Any = None) -> Any:
        return request.payload.get(key, default)

    def get_input_text(self, request: EvaluationSchema, default: str = "") -> str:
        return (
            self.get_payload_data(request, "user_input")
            or self.get_payload_data(request, "text")
            or default
        )

    def validate_input(self, request: EvaluationSchema) -> DomainResponse | None:
        """验证输入数据是否有效

        Returns:
            DomainResponse | None: 如果验证失败返回错误响应，否则返回 None
        """
        user_input = self.get_input_text(request)
        if not user_input or not user_input.strip():
            return self.create_error_response(
                error_message="user_input/text 不能为空", error_code="INVALID_INPUT"
            )
        return None

    def validate_expected(self, request: EvaluationSchema) -> DomainResponse | None:
        """验证期望输出是否有效

        Returns:
            DomainResponse | None: 如果验证失败返回错误响应，否则返回 None
        """
        expected_output = self.get_payload_data(request, "expected_output")
        if not expected_output or (
            isinstance(expected_output, str) and not expected_output.strip()
        ):
            return self.create_error_response(
                error_message="expected_output 不能为空", error_code="INVALID_EXPECTED"
            )
        return None

    def require_client_with_error(self) -> DomainResponse | None:
        """验证 LLM 客户端是否可用

        Returns:
            DomainResponse | None: 如果客户端不可用返回错误响应，否则返回 None
        """
        if not self.client:
            return self.create_error_response(
                error_message="此评估器需要 LLM 客户端，但未提供", error_code="CLIENT_REQUIRED"
            )
        if not hasattr(self.client, "chat"):
            return self.create_error_response(
                error_message="LLM 客户端缺少 chat 方法", error_code="INVALID_CLIENT"
            )
        return None

    def create_error_response(
        self, error_message: str, error_code: str | None = None, metadata: dict | None = None
    ) -> DomainResponse:
        response_metadata = metadata or {}
        if error_code:
            response_metadata["error_code"] = error_code
        return DomainResponse(is_valid=False, error=error_message, metadata=response_metadata)

    def create_success_response(
        self,
        text: str = "评估完成",
        score: float = 1.0,
        data: dict | None = None,
        metadata: dict | None = None,
    ) -> DomainResponse:
        return DomainResponse(
            is_valid=True, text=text, score=score, data=data or {}, metadata=metadata or {}
        )

    def safe_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """安全评估入口：包装 evaluate 方法，确保返回 DomainResponse 而不抛出异常"""
        try:
            return self.evaluate(request)
        except Exception as e:
            logger.error(f"安全评估捕获异常: {e}", exc_info=True)
            return self.create_error_response(
                error_message=f"安全评估失败: {str(e)}", error_code="SAFE_EVALUATE_ERROR"
            )

    def _get_breaker(self) -> CircuitBreaker:
        """获取熔断器实例（线程安全双重检查锁定）"""
        evaluator_name = type(self).__name__
        breaker_key = f"evaluator_run_{evaluator_name}"
        with self._breaker_cache_lock:
            if breaker_key not in self._breaker_cache:
                self._breaker_cache[breaker_key] = global_registry.get_or_create(
                    breaker_key,
                    CircuitBreakerConfig(
                        failure_threshold=5,
                        success_threshold=2,
                        timeout_seconds=30,
                        half_open_max_calls=3,
                    ),
                )
            return self._breaker_cache[breaker_key]
