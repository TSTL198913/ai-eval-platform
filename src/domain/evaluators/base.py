import asyncio
import re
import threading
import time
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from src.distributed.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    global_registry,
)
from src.domain.evaluators.strategies.score_parsing import DEFAULT_PARSER
from src.exceptions import BasePlatformError
from src.infra.monitoring.metrics import (
    EVALUATION_COUNTER,
    EVALUATION_ERRORS,
    EVALUATION_LATENCY,
    EVAL_STATUS_COUNTER,
    EVAL_CONFIDENCE_HISTOGRAM,
)
from src.infra.monitoring.tracing import TraceContext, get_tracer
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus

if TYPE_CHECKING:
    from src.domain.evaluators.fallback_policy import BaseFallbackPolicy
    from src.domain.models.base import BaseLLMClient


class BaseEvaluator(ABC):
    _breaker_cache: dict[str, CircuitBreaker] = {}
    _breaker_cache_lock = threading.Lock()

    _evaluation_executor: ThreadPoolExecutor | None = None
    _executor_lock = threading.Lock()
    _default_executor_max_workers = 16

    _score_cache: dict[str, list[float]] = {}
    _score_cache_lock = threading.Lock()
    _score_cache_max_size = 100

    def __init__(
        self,
        client: Optional["BaseLLMClient"] = None,
        fallback_policy: Optional["BaseFallbackPolicy"] = None,
        require_input: bool = False,
        require_expected: bool = False,
    ):
        self.client = client
        self.fallback_policy = fallback_policy
        self._require_input = require_input
        self._require_expected = require_expected

    # ===================== 核心评测契约（双轨制） =====================

    @abstractmethod
    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """
        同步核心逻辑：子类必须实现。
        纯规则评估器或未做异步改造的评估器在此编写核心逻辑。
        """
        pass

    @classmethod
    def _get_executor(cls) -> ThreadPoolExecutor:
        """获取专用的评估线程池，避免耗尽默认 asyncio 线程池"""
        with cls._executor_lock:
            if cls._evaluation_executor is None:
                cls._evaluation_executor = ThreadPoolExecutor(
                    max_workers=cls._default_executor_max_workers,
                    thread_name_prefix="eval-worker-",
                )
        return cls._evaluation_executor

    async def _do_evaluate_async(self, request: EvaluationSchema) -> DomainResponse:
        """
        异步核心逻辑：子类可选择性重写。
        使用专用线程池执行同步评估任务，避免耗尽默认 asyncio 线程池。
        对于外接异步 Client 的高级评估器，重写此方法可以获得极高的并发性能。
        """
        return await asyncio.get_event_loop().run_in_executor(
            self._get_executor(),
            self._do_evaluate,
            request,
        )

    # ===================== 同步编排中枢 =====================

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """同步评测核心逻辑：仅做编排（前置处理→熔断保护→后置处理），不处理异常

        设计原则：
        - 保留熔断器保护（circuit breaker）
        - BasePlatformError 向上传播，由上层处理
        - 非业务异常（Exception）向上传播，由 safe_evaluate() 统一处理
        - fallback 逻辑上移到 safe_evaluate()
        - 集成 tracing 和 metrics
        """
        evaluator_name = type(self).__name__
        breaker = self._get_breaker()
        trace_id = request.id or str(uuid.uuid4())
        start_time = time.perf_counter()

        tracer = get_tracer()
        with TraceContext(
            tracer,
            f"evaluator.{evaluator_name}",
            attributes={
                "evaluator.name": evaluator_name,
                "request.id": trace_id,
                "request.type": request.type,
            },
        ):
            result = breaker.call_sync(lambda: self._do_evaluate(request))
            elapsed = time.perf_counter() - start_time

            if result is None:
                error_msg = f"{evaluator_name}._do_evaluate() 返回 None，违反评估器实现规范"
                logger.error(f"评估失败 | trace_id={trace_id} | evaluator={evaluator_name} | error={error_msg}")
                return self.create_error_response(error_message=error_msg)

            status_label = result.evaluation_status.value
            EVALUATION_LATENCY.labels(domain=evaluator_name, status=status_label).observe(elapsed)
            EVALUATION_COUNTER.labels(domain=evaluator_name, status=status_label).inc()

            logger.info(
                f"评估完成 | trace_id={trace_id} | evaluator={evaluator_name} | "
                f"score={result.score if result.score is not None else 0.0:.4f} | "
                f"status={result.evaluation_status} | "
                f"elapsed={elapsed:.4f}s"
            )
            if result.data is None:
                result.data = {}
            result.data["execution_time_ms"] = round(elapsed * 1000, 2)
            result.data["trace_id"] = trace_id
            
            result = self._auto_compute_confidence(result)
            
        return result

    # ===================== 🚀 2026 高并发异步编排中枢 =====================

    async def evaluate_async(self, request: EvaluationSchema) -> DomainResponse:
        """异步评测核心逻辑：仅做编排（前置处理→熔断保护→后置处理），不处理异常

        设计原则：
        - 保留熔断器保护（circuit breaker）
        - BasePlatformError 向上传播，由上层处理
        - 非业务异常（Exception）向上传播，由 safe_evaluate_async() 统一处理
        - fallback 逻辑上移到 safe_evaluate_async()
        - 集成 tracing 和 metrics
        """
        evaluator_name = type(self).__name__
        breaker = self._get_breaker()
        trace_id = request.id or str(uuid.uuid4())
        start_time = time.perf_counter()

        tracer = get_tracer()
        with TraceContext(
            tracer,
            f"evaluator.{evaluator_name}.async",
            attributes={
                "evaluator.name": evaluator_name,
                "request.id": trace_id,
                "request.type": request.type,
                "execution.mode": "async",
            },
        ):
            result = await breaker.call(self._do_evaluate_async, request)
            elapsed = time.perf_counter() - start_time

            if result is None:
                error_msg = f"{evaluator_name}._do_evaluate_async() 返回 None，违反评估器实现规范"
                logger.error(f"异步评估失败 | trace_id={trace_id} | evaluator={evaluator_name} | error={error_msg}")
                return self.create_error_response(error_message=error_msg)

            status_label = result.evaluation_status.value
            EVALUATION_LATENCY.labels(domain=evaluator_name, status=status_label).observe(elapsed)
            EVALUATION_COUNTER.labels(domain=evaluator_name, status=status_label).inc()

            logger.info(
                f"异步评估完成 | trace_id={trace_id} | evaluator={evaluator_name} | "
                f"score={result.score if result.score is not None else 0.0:.4f} | status={result.evaluation_status} | "
                f"elapsed={elapsed:.4f}s"
            )
            if result.data is None:
                result.data = {}
            result.data["execution_time_ms"] = round(elapsed * 1000, 2)
            result.data["trace_id"] = trace_id
        return result

    # ===================== 容错与策略沉降编排 =====================

    def _execute_fallback_infrastructure(
        self, request: EvaluationSchema, error: Exception
    ) -> DomainResponse:
        """同步降级中枢

        🧠 2026 架构升级：降级结果应返回 PARTIAL 状态，而非 SUCCESS。
        这样下游系统可以区分"LLM评估（高置信）"和"Embedding降级（低置信）"。
        """
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

            return self.create_partial_response(
                text=f"降级评估结果（基于 Embedding 相似度）：{actual_output}",
                score=score,
                dimensions_evaluated=["fallback_similarity"],
                dimensions_skipped=["llm_semantic"],
                skip_reasons={"llm_semantic": f"LLM 评估失败: {str(error)}"},
                data={"notice": "Derived from backup pipeline (Embedding fallback)"},
                metadata=metadata,
                evaluation_method="embedding",
            )
        except Exception as fallback_err:
            return self._handle_cascading_failure(evaluator_name, error, fallback_err)

    async def _execute_fallback_infrastructure_async(
        self, request: EvaluationSchema, error: Exception
    ) -> DomainResponse:
        """异步降级中枢，防止耗时的 CPU 密集型向量计算阻塞异步事件循环

        🧠 2026 架构升级：降级结果应返回 PARTIAL 状态，而非 SUCCESS。
        """
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

            return self.create_partial_response(
                text=f"降级评估结果（基于 Embedding 相似度）：{actual_output}",
                score=score,
                dimensions_evaluated=["fallback_similarity"],
                dimensions_skipped=["llm_semantic"],
                skip_reasons={"llm_semantic": f"LLM 评估失败: {str(error)}"},
                data={"notice": "Derived from async backup pipeline (Embedding fallback)"},
                metadata=metadata,
                evaluation_method="embedding",
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

    # ===================== 置信度自动计算（2026工业级标准） =====================

    def _auto_compute_confidence(self, result: DomainResponse) -> DomainResponse:
        """自动计算置信度（当置信度未设置或为0时）
        
        2026工业级标准：根据评估状态、分数、执行时间综合计算置信度
        
        置信度计算规则：
        1. 如果已设置置信度且>0，保持不变
        2. 根据 evaluation_status 确定基础置信度
        3. 根据分数距离边界的远近调整（极端分数置信度更高）
        4. 根据执行时间调整（超时或极短时间完成置信度降低）
        """
        if result.confidence is not None and result.confidence > 0:
            return result
        
        base_confidence = 0.5
        
        if result.evaluation_status == EvaluatorStatus.SUCCESS:
            base_confidence = 0.85
        elif result.evaluation_status == EvaluatorStatus.PARTIAL:
            base_confidence = 0.65
        elif result.evaluation_status == EvaluatorStatus.CANNOT_EVALUATE:
            base_confidence = 0.20
        elif result.evaluation_status == EvaluatorStatus.ERROR:
            base_confidence = 0.05
        
        score_bonus = 0.0
        if result.score is not None:
            distance_from_boundary = min(result.score, 1.0 - result.score)
            if distance_from_boundary < 0.1:
                score_bonus = 0.08
            elif distance_from_boundary < 0.2:
                score_bonus = 0.04
        
        time_penalty = 0.0
        exec_time_ms = result.data.get("execution_time_ms", 0) if result.data else 0
        if exec_time_ms > 60000:
            time_penalty = 0.10
        elif exec_time_ms < 10:
            time_penalty = 0.05
        
        final_confidence = max(0.05, min(0.95, base_confidence + score_bonus - time_penalty))
        
        if result.data is None:
            result.data = {}
        
        result.data["confidence_auto_computed"] = True
        result.data["confidence_components"] = {
            "base": base_confidence,
            "score_bonus": score_bonus,
            "time_penalty": time_penalty,
        }
        
        return result.model_copy(update={"confidence": final_confidence})

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

        默认情况下，输入验证是可选的，由子类在构造时通过 require_input 参数控制。
        这样可以避免不使用 user_input/text 字段的评估器（如 RiskEvaluator、ToolUseEvaluator）
        被强制要求提供这些字段。

        Returns:
            DomainResponse | None: 如果验证失败返回错误响应，否则返回 None
        """
        if not self._require_input:
            return None

        user_input = self.get_input_text(request)
        if not user_input or not user_input.strip():
            return self.create_error_response(
                error_message="user_input/text 不能为空", error_code="INVALID_INPUT"
            )
        return None

    def validate_expected(self, request: EvaluationSchema) -> DomainResponse | None:
        """验证期望输出是否有效

        默认情况下，期望输出验证是可选的，由子类在构造时通过 require_expected 参数控制。

        Returns:
            DomainResponse | None: 如果验证失败返回错误响应，否则返回 None
        """
        if not self._require_expected:
            return None

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
        self,
        error_message: str,
        error_code: str | None = None,
        metadata: dict | None = None,
        confidence: float | None = None,
    ) -> DomainResponse:
        """创建错误响应

        Args:
            error_message: 错误信息
            error_code: 错误码
            metadata: 元数据
            confidence: 置信度（默认0.0表示完全不可信）
        """
        response_metadata = metadata or {}
        if error_code:
            response_metadata["error_code"] = error_code
        final_confidence = confidence if confidence is not None else 0.0
        return DomainResponse(
            error=error_message,
            metadata=response_metadata,
            evaluation_status=EvaluatorStatus.ERROR,
            confidence=final_confidence,
        )

    def create_success_response(
        self,
        text: str = "评估完成",
        score: float = 1.0,
        data: dict | None = None,
        metadata: dict | None = None,
        confidence: float | None = None,
        is_full_evaluation: bool = True,
    ) -> DomainResponse:
        """创建成功响应

        Args:
            text: 评估文本
            score: 评分
            data: 数据
            metadata: 元数据
            confidence: 置信度（默认0.95表示LLM完整评估）
            is_full_evaluation: 是否为完整评估（决定默认置信度）
        """
        final_confidence = confidence if confidence is not None else (0.95 if is_full_evaluation else 0.85)
        return DomainResponse(
            text=text,
            score=score,
            data=data or {},
            metadata=metadata or {},
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=final_confidence,
        )

    def create_cannot_evaluate_response(
        self,
        reason: str,
        dimensions_skipped: list[str] | None = None,
        metadata: dict | None = None,
        confidence: float | None = None,
    ) -> DomainResponse:
        """创建无法评估响应

        Args:
            reason: 无法评估的原因
            dimensions_skipped: 跳过的维度
            metadata: 元数据
            confidence: 置信度（无法评估时通常为None，表示无置信度）
        """
        response_data = {
            "dimensions_skipped": dimensions_skipped or [],
            "skip_reason": reason,
        }
        return DomainResponse(
            score=None,
            text=f"无法评估: {reason}",
            data=response_data,
            metadata=metadata or {},
            evaluation_status=EvaluatorStatus.CANNOT_EVALUATE,
            confidence=confidence,
        )

    def create_partial_response(
        self,
        text: str,
        score: float,
        dimensions_evaluated: list[str],
        dimensions_skipped: list[str],
        skip_reasons: dict[str, str] | None = None,
        data: dict | None = None,
        metadata: dict | None = None,
        confidence: float | None = None,
        evaluation_method: str = "llm",
    ) -> DomainResponse:
        """创建部分评估响应

        Args:
            text: 评估文本
            score: 评分
            dimensions_evaluated: 已评估的维度
            dimensions_skipped: 跳过的维度
            skip_reasons: 跳过原因
            data: 数据
            metadata: 元数据
            confidence: 置信度
            evaluation_method: 评估方法 ("llm", "embedding", "heuristic")
        """
        response_data = (data or {}).copy()
        response_data.update({
            "dimensions_evaluated": dimensions_evaluated,
            "dimensions_skipped": dimensions_skipped,
            "skip_reasons": skip_reasons or {},
        })

        if confidence is None:
            total_dims = len(dimensions_evaluated) + len(dimensions_skipped)
            coverage_ratio = len(dimensions_evaluated) / max(total_dims, 1)

            if evaluation_method == "llm":
                final_confidence = 0.7 * coverage_ratio + 0.25
            elif evaluation_method == "embedding":
                final_confidence = 0.5 * coverage_ratio + 0.3
            else:
                final_confidence = 0.3 * coverage_ratio + 0.2

            confidence = round(final_confidence, 2)

        return DomainResponse(
            text=text,
            score=score,
            data=response_data,
            metadata=metadata or {},
            evaluation_status=EvaluatorStatus.PARTIAL,
            confidence=confidence,
        )

    def safe_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """安全评估入口：统一异常处理、降级策略和日志记录

        设计原则：
        - BasePlatformError 向上传播，由 engine.py 处理业务异常
        - CircuitBreakerError 触发降级评估（fallback）
        - 非业务异常（Exception）触发降级评估（fallback）
        - 只有成功评估或降级成功时才记录日志
        """
        evaluator_name = type(self).__name__
        trace_id = request.id or str(uuid.uuid4())
        start_time = time.perf_counter()

        try:
            response = self.evaluate(request)
            if response is None:
                raise ValueError("评估器返回 None")
            self._log_evaluation_result(request, response)
            return response
        except BasePlatformError:
            raise
        except CircuitBreakerError as e:
            elapsed = time.perf_counter() - start_time
            logger.error(
                f"熔断触发 | trace_id={trace_id} | evaluator={evaluator_name} | "
                f"elapsed={elapsed:.4f}s | error={e}"
            )
            fallback_response = self._execute_fallback_infrastructure(request, error=e)
            self._log_evaluation_result(request, fallback_response)
            return fallback_response
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error(
                f"运行时异常 | trace_id={trace_id} | evaluator={evaluator_name} | "
                f"elapsed={elapsed:.4f}s | error={e}",
                exc_info=True,
            )
            fallback_response = self._execute_fallback_infrastructure(request, error=e)
            self._log_evaluation_result(request, fallback_response)
            return fallback_response

    async def safe_evaluate_async(self, request: EvaluationSchema) -> DomainResponse:
        """安全异步评估入口：统一异常处理、降级策略和日志记录

        设计原则：
        - BasePlatformError 向上传播，由 engine.py 处理业务异常
        - CircuitBreakerError 触发降级评估（fallback）
        - 非业务异常（Exception）触发降级评估（fallback）
        - 只有成功评估或降级成功时才记录日志
        """
        evaluator_name = type(self).__name__
        trace_id = request.id or str(uuid.uuid4())
        start_time = time.perf_counter()

        try:
            response = await self.evaluate_async(request)
            if response is None:
                raise ValueError("评估器返回 None")
            self._log_evaluation_result(request, response)
            return response
        except BasePlatformError:
            raise
        except CircuitBreakerError as e:
            elapsed = time.perf_counter() - start_time
            logger.error(
                f"异步熔断触发 | trace_id={trace_id} | evaluator={evaluator_name} | "
                f"elapsed={elapsed:.4f}s | error={e}"
            )
            fallback_response = await self._execute_fallback_infrastructure_async(request, error=e)
            self._log_evaluation_result(request, fallback_response)
            return fallback_response
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error(
                f"异步运行时异常 | trace_id={trace_id} | evaluator={evaluator_name} | "
                f"elapsed={elapsed:.4f}s | error={e}",
                exc_info=True,
            )
            fallback_response = await self._execute_fallback_infrastructure_async(request, error=e)
            self._log_evaluation_result(request, fallback_response)
            return fallback_response

    def _log_evaluation_result(self, request: EvaluationSchema, response: DomainResponse) -> None:
        """记录评估结果日志，为基准测试收集数据
        
        根据 Phase 1.5 诊断期要求，记录每次评估的：
        - 评估器类型
        - 输入内容
        - 评估结果（分数、状态、置信度）
        - 原始请求元数据
        同时更新状态机监控指标和统计置信度分析
        """
        import json
        from datetime import datetime
        
        evaluator_type = type(self).__name__
        input_text = self.get_input_text(request)
        actual_output = self.get_payload_data(request, "actual_output")
        expected_output = self.get_payload_data(request, "expected_output")
        
        # 状态机监控指标记录
        status_label = response.evaluation_status.value
        EVAL_STATUS_COUNTER.labels(evaluator=evaluator_type, status=status_label).inc()
        
        # 置信度分布记录
        if response.confidence is not None and response.confidence_level is not None:
            EVAL_CONFIDENCE_HISTOGRAM.labels(
                evaluator=evaluator_type,
                confidence_level=response.confidence_level.value,
            ).observe(response.confidence)
        
        # 统计置信度分析：缓存最近评分并计算统计指标
        confidence_analysis = None
        if response.score is not None:
            with self._score_cache_lock:
                if evaluator_type not in self._score_cache:
                    self._score_cache[evaluator_type] = []
                scores = self._score_cache[evaluator_type]
                scores.append(response.score)
                if len(scores) > self._score_cache_max_size:
                    scores.pop(0)
            
            if len(scores) >= 5:
                from tests.utils.confidence_analyzer import analyze_confidence
                try:
                    confidence_analysis = analyze_confidence(scores)
                except Exception as e:
                    logger.warning(f"置信度分析失败: {e}")
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "evaluator_type": evaluator_type,
            "request_id": request.id,
            "evaluation_type": request.type,
            "input_text": input_text[:500] if input_text else None,
            "actual_output": actual_output[:500] if actual_output else None,
            "expected_output": expected_output[:500] if expected_output else None,
            "score": response.score,
            "evaluation_status": response.evaluation_status.value,
            "confidence": response.confidence,
            "confidence_level": response.confidence_level.value if response.confidence_level else None,
            "is_valid": response.is_valid,
            "error": response.error,
            "metadata_keys": list(request.metadata.keys()) if request.metadata else [],
            "dimensions_evaluated": response.data.get("dimensions_evaluated") if response.data else None,
            "dimensions_skipped": response.data.get("dimensions_skipped") if response.data else None,
            "confidence_analysis": confidence_analysis,
        }
        
        logger.info(f"[EVALUATION_LOG] {json.dumps(log_entry, ensure_ascii=False)}")

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
