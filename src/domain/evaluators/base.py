import asyncio
import threading
import time
import uuid
from abc import ABC
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING
from typing import Any
from typing import Optional

from loguru import logger

from src.distributed.circuit_breaker import CircuitBreaker
from src.distributed.circuit_breaker import CircuitBreakerConfig
from src.distributed.circuit_breaker import CircuitBreakerError
from src.distributed.circuit_breaker import global_registry
from src.exceptions import BasePlatformError
from src.infra.monitoring.metrics import EVALUATION_COUNTER
from src.infra.monitoring.metrics import EVALUATION_LATENCY
from src.infra.monitoring.tracing import TraceContext
from src.infra.monitoring.tracing import get_tracer
from src.schemas.evaluation import DomainResponse
from src.schemas.evaluation import EvaluationSchema
from src.schemas.evaluation import EvaluatorStatus

from ._response_factory_mixin import ResponseFactoryMixin
from ._score_parsing import ScoreParsingMixin
from ._fallback_infrastructure import FallbackInfrastructureMixin
from ._calibration_mixin import CalibrationMixin
from ._evaluation_logger import EvaluationLoggerMixin
from ._payload_utils import PayloadUtilsMixin

if TYPE_CHECKING:
    from src.domain.evaluators.fallback_policy import BaseFallbackPolicy
    from src.domain.models.base import BaseLLMClient


class BaseEvaluator(
    ABC,
    ResponseFactoryMixin,
    ScoreParsingMixin,
    FallbackInfrastructureMixin,
    CalibrationMixin,
    EvaluationLoggerMixin,
    PayloadUtilsMixin,
):
    _breaker_cache: dict[str, CircuitBreaker] = {}
    _breaker_cache_lock = threading.Lock()

    _evaluation_executor: ThreadPoolExecutor | None = None
    _executor_lock = threading.Lock()
    _default_executor_max_workers = 16

    _current_evaluator = threading.local()

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

    @classmethod
    def get_current_evaluator(cls) -> "BaseEvaluator | None":
        return getattr(cls._current_evaluator, "instance", None)

    @classmethod
    def set_current_evaluator(cls, evaluator: "BaseEvaluator | None") -> None:
        cls._current_evaluator.instance = evaluator

    @abstractmethod
    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        pass

    @classmethod
    def _get_executor(cls) -> ThreadPoolExecutor:
        with cls._executor_lock:
            if cls._evaluation_executor is None:
                cls._evaluation_executor = ThreadPoolExecutor(
                    max_workers=cls._default_executor_max_workers,
                    thread_name_prefix="eval-worker-",
                )
        return cls._evaluation_executor

    async def _do_evaluate_async(self, request: EvaluationSchema) -> DomainResponse:
        return await asyncio.get_event_loop().run_in_executor(
            self._get_executor(),
            self._do_evaluate,
            request,
        )

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        evaluator_name = type(self).__name__

        from src.domain.calibration.unified_calibration_engine import calibration_engine
        calibration_check = calibration_engine.pre_execution_check(evaluator_name)
        if not calibration_check.can_proceed:
            logger.warning(
                f"校准门控拒绝执行 | evaluator={evaluator_name} | "
                f"status={calibration_check.status.value} | message={calibration_check.message}"
            )

            self._start_self_healing(evaluator_name)

            return self.create_error_response(
                error_message=f"评估器 {evaluator_name} 未通过校准检查: {calibration_check.message}",
                error_code="CALIBRATION_FAILED",
                metadata={
                    "calibration_status": calibration_check.status.value,
                    "evaluator_version": calibration_check.evaluator_version,
                },
            )

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
            result = breaker.call_sync(self._do_evaluate, request)
            elapsed = time.perf_counter() - start_time

            if result is None:
                error_msg = f"{evaluator_name}._do_evaluate() 返回 None，违反评估器实现规范"
                logger.error(f"评估失败 | trace_id={trace_id} | evaluator={evaluator_name} | error={error_msg}")
                return self.create_error_response(error_message=error_msg)

            if result.score is not None and result.evaluation_status == EvaluatorStatus.SUCCESS:
                calibrated_score = calibration_engine.apply_calibration(evaluator_name, result.score)
                result = result.model_copy(update={"score": calibrated_score})

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

            try:
                from src.infra.event_bus import EventType
                from src.infra.event_bus import publish_event
                publish_event(
                    EventType.EVALUATION_COMPLETED,
                    evaluator_name=evaluator_name,
                    trace_id=trace_id,
                    score=result.score,
                    status=result.evaluation_status.value,
                    elapsed_ms=round(elapsed * 1000, 2),
                    source="BaseEvaluator.evaluate",
                )
            except Exception as e:
                logger.debug(f"发布评估完成事件失败: {e}")

            result = self._auto_compute_confidence(result)

        return result

    async def evaluate_async(self, request: EvaluationSchema) -> DomainResponse:
        evaluator_name = type(self).__name__

        from src.domain.calibration.unified_calibration_engine import calibration_engine
        calibration_check = calibration_engine.pre_execution_check(evaluator_name)
        if not calibration_check.can_proceed:
            logger.warning(
                f"异步校准门控拒绝执行 | evaluator={evaluator_name} | "
                f"status={calibration_check.status.value} | message={calibration_check.message}"
            )
            return self.create_error_response(
                error_message=f"评估器 {evaluator_name} 未通过校准检查: {calibration_check.message}",
                error_code="CALIBRATION_FAILED",
                metadata={
                    "calibration_status": calibration_check.status.value,
                    "evaluator_version": calibration_check.evaluator_version,
                },
            )

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

            if result.score is not None and result.evaluation_status == EvaluatorStatus.SUCCESS:
                calibrated_score = calibration_engine.apply_calibration(evaluator_name, result.score)
                result = result.model_copy(update={"score": calibrated_score})

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

            result = self._auto_compute_confidence(result)

        return result

    def batch_evaluate(self, requests: list[EvaluationSchema]) -> list[DomainResponse]:
        results = []
        for request in requests:
            try:
                result = self.safe_evaluate(request)
            except Exception as e:
                logger.error(f"批量评估单个请求失败: {e}")
                result = self.create_error_response(
                    error_message=f"批量评估失败: {str(e)}",
                    error_code="BATCH_EVALUATION_ERROR",
                )
            results.append(result)
        return results

    async def batch_evaluate_async(self, requests: list[EvaluationSchema]) -> list[DomainResponse]:
        tasks = []
        for request in requests:
            task = asyncio.create_task(self.safe_evaluate_async(request))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"批量异步评估请求 {i} 失败: {result}")
                final_results.append(
                    self.create_error_response(
                        error_message=f"批量评估失败: {str(result)}",
                        error_code="BATCH_EVALUATION_ERROR",
                    )
                )
            else:
                final_results.append(result)

        return final_results

    def _auto_compute_confidence(self, result: DomainResponse) -> DomainResponse:
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

        needs_auto_compute = result.confidence is None or result.confidence == 0

        if result.data is None:
            result.data = {}

        if needs_auto_compute:
            result.data["confidence_auto_computed"] = True
            result.data["confidence_components"] = {
                "base": base_confidence,
                "score_bonus": score_bonus,
                "time_penalty": time_penalty,
            }
            return result.model_copy(update={"confidence": final_confidence})
        else:
            result.data["confidence_auto_computed"] = True
            return result

    def safe_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        evaluator_name = type(self).__name__
        trace_id = request.id or str(uuid.uuid4())
        start_time = time.perf_counter()

        try:
            response = self.evaluate(request)
            if response is None:
                raise ValueError("评估器返回 None")

            if response.evaluation_status == EvaluatorStatus.ERROR:
                if hasattr(self, '_rule_based_qa') and callable(getattr(self, '_rule_based_qa')):
                    try:
                        actual_output = self.get_payload_data(request, "actual_output", "")
                        expected_output = self.get_payload_data(request, "expected_output", "")
                        question = self.get_payload_data(request, "question", "")
                        score = self._rule_based_qa(question, actual_output, expected_output)
                        if score is not None:
                            response = self.create_partial_response(
                                text=actual_output,
                                score=score,
                                dimensions_evaluated=["rule_based_qa"],
                                dimensions_skipped=["llm_evaluation"],
                                data={"fallback_reason": "ERROR状态，使用_rule_based_qa降级评估"},
                            )
                    except Exception as rule_err:
                        logger.error(f"规则降级失败: {rule_err}")

            self._log_evaluation_result(request, response)

            self._trigger_auto_calibration(evaluator_name, response)

            return response
        except BasePlatformError:
            raise
        except CircuitBreakerError as e:
            elapsed = time.perf_counter() - start_time
            logger.error(
                f"熔断触发 | trace_id={trace_id} | evaluator={evaluator_name} | "
                f"elapsed={elapsed:.4f}s | error={e}"
            )
            if hasattr(self, '_rule_based_qa') and callable(getattr(self, '_rule_based_qa')):
                try:
                    actual_output = self.get_payload_data(request, "actual_output", "")
                    expected_output = self.get_payload_data(request, "expected_output", "")
                    question = self.get_payload_data(request, "question", "")
                    score = self._rule_based_qa(question, actual_output, expected_output)
                    if score is not None:
                        fallback_response = self.create_partial_response(
                            text=actual_output,
                            score=score,
                            dimensions_evaluated=["rule_based_qa"],
                            dimensions_skipped=["llm_evaluation"],
                            data={"fallback_reason": "熔断触发，使用_rule_based_qa降级评估"},
                        )
                        self._log_evaluation_result(request, fallback_response)
                        return fallback_response
                except Exception as rule_err:
                    logger.error(f"规则降级失败: {rule_err}")
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

    def _get_breaker(self) -> CircuitBreaker:
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
