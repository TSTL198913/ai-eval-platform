import asyncio
import logging
import time
from typing import Any

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.models.base import BaseLLMClient
from src.exceptions import ContractValidationError, DomainLogicError, InfrastructureError
from src.schemas.evaluation import DomainResponse, EvaluationSchema
from src.schemas.schemas import EvaluationResult, EvaluationStatus

logger = logging.getLogger(__name__)


class EvaluationEngine:
    def __init__(self, client: BaseLLMClient):
        self.client = client

    # ===================== 1. 传统经典同步调度轨 =====================

    def run(self, request: EvaluationSchema) -> EvaluationResult:
        """同步评测单轨：保持对旧版单步流水线、离线脚本的完美向后兼容"""
        start_time = time.perf_counter()

        try:
            actual_output = request.payload.get("actual_output")
            if not actual_output:
                prompt = request.payload.get("prompt", request.payload.get("input"))
                if prompt and self.client:
                    actual_output = self.client.chat(prompt)
                    request.payload["actual_output"] = actual_output

            evaluator = EvaluatorFactory.get(request.type, client=self.client)

            # 【精准对齐】旧版 safe_evaluate 变更为新版标准同步中枢 evaluate
            domain_response = evaluator.evaluate(request)

            return self._build_evaluation_result(request, evaluator, domain_response, start_time)

        except Exception as e:
            return self._handle_engine_exception(request, e, start_time)

    # ===================== 🚀 2. 2026 现代高并发异步调度轨 =====================

    async def run_async(self, request: EvaluationSchema) -> EvaluationResult:
        """
        🚀 原生异步评测轨：专为千级大规模批量测试（Benchmark）和多智能体轨迹评测而生。
        配合 asyncio.gather() 可使平台吞吐量发生数倍的质变。
        """
        start_time = time.perf_counter()

        try:
            actual_output = request.payload.get("actual_output")
            if not actual_output:
                prompt = request.payload.get("prompt", request.payload.get("input"))
                if prompt and self.client:
                    # 防御刺客：如果 LLM Client 还没做异步改造，用 to_thread 轰进线程池，防止卡死主事件循环
                    if hasattr(self.client, "chat_async"):
                        actual_output = await self.client.chat_async(prompt)
                    else:
                        actual_output = await asyncio.to_thread(self.client.chat, prompt)
                    request.payload["actual_output"] = actual_output

            evaluator = EvaluatorFactory.get(request.type, client=self.client)

            # 【核心跃迁】调用新基类的原生异步中枢，享受分布式熔断与平滑策略降级
            domain_response = await evaluator.evaluate_async(request)

            return self._build_evaluation_result(request, evaluator, domain_response, start_time)

        except Exception as e:
            return self._handle_engine_exception(request, e, start_time)

    # ===================== 内部私有辅助收割机 =====================

    def _build_evaluation_result(
        self,
        request: EvaluationSchema,
        evaluator: Any,
        domain_response: DomainResponse,
        start_time: float,
    ) -> EvaluationResult:
        """统一拼装成功的评测领域实体"""
        if domain_response.is_valid:
            status = EvaluationStatus.PASSED
        elif domain_response.error and "_ERROR" in domain_response.error:
            status = EvaluationStatus.ERROR
        else:
            status = EvaluationStatus.FAILED

        return EvaluationResult(
            case_id=request.id,
            status=status,
            model_name=(
                (getattr(self.client.config, "model_name", None) or "unknown")
                if self.client and self.client.config
                else "unknown"
            ),
            adapter_name=evaluator.__class__.__name__,
            response=domain_response,
            latency_ms=(time.perf_counter() - start_time) * 1000,
        )

    def _handle_engine_exception(
        self, request: EvaluationSchema, e: Exception, start_time: float
    ) -> EvaluationResult:
        """将各类灾难性异常和契约校验失败，统一收拢为标准错误相应"""
        latency = (time.perf_counter() - start_time) * 1000
        model_name = (
            (getattr(self.client.config, "model_name", None) or "unknown")
            if self.client and self.client.config
            else "unknown"
        )

        if isinstance(e, ContractValidationError):
            logger.warning("Case %s 契约验证失败: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationStatus.ERROR,
                model_name=model_name,
                adapter_name="contract_validator",
                response=DomainResponse(is_valid=False, error="CONTRACT_ERROR"),
                latency_ms=latency,
                error_message=str(e),
            )
        elif isinstance(e, DomainLogicError):
            logger.error("Case %s 领域逻辑错误: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationStatus.ERROR,
                model_name=model_name,
                adapter_name="domain_handler",
                response=DomainResponse(is_valid=False, error="DOMAIN_ERROR"),
                latency_ms=latency,
                error_message=str(e),
            )
        elif isinstance(e, InfrastructureError):
            logger.error("Case %s 基础设施故障: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationStatus.ERROR,
                model_name=model_name,
                adapter_name="infra_handler",
                response=DomainResponse(is_valid=False, error="INFRA_ERROR"),
                latency_ms=latency,
                error_message=str(e),
            )
        else:
            logger.exception("Case %s 评测失败（未预期异常）: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationStatus.ERROR,
                model_name=model_name,
                adapter_name="error_handler",
                response=DomainResponse(is_valid=False, error="INTERNAL_ERROR"),
                latency_ms=latency,
                error_message=str(e),
            )
