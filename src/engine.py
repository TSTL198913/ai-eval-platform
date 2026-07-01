import asyncio
import time
from typing import Any

from loguru import logger

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.models.base import BaseLLMClient
from src.exceptions import ContractValidationError, DomainLogicError, InfrastructureError
from src.infra.monitoring.tracing import TraceContext, get_tracer
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus
from src.schemas.schemas import EvaluationResult, EvaluationStatus as EvaluationRecordStatus
from src.schemas.evaluator_schemas import validate_payload


class EvaluationEngine:
    def __init__(self, client: BaseLLMClient):
        self.client = client

    # ===================== 1. 传统经典同步调度轨 =====================

    def run(self, request: EvaluationSchema) -> EvaluationResult:
        """同步评测单轨：保持对旧版单步流水线、离线脚本的完美向后兼容"""
        start_time = time.perf_counter()
        trace_id = request.id or f"engine-{time.time()}"

        tracer = get_tracer()
        with TraceContext(
            tracer,
            "pipeline.evaluation",
            attributes={
                "pipeline.type": "sync",
                "request.id": trace_id,
                "request.type": request.type,
            },
        ):
            try:
                actual_output = request.payload.get("actual_output")
                if not actual_output:
                    prompt = request.payload.get("prompt", request.payload.get("input"))
                    if prompt and self.client:
                        actual_output = self.client.chat(prompt)
                        new_payload = request.payload.copy()
                        new_payload["actual_output"] = actual_output
                        request = request.model_copy(update={"payload": new_payload})

                request = self._normalize_payload_fields(request)

                # 【新增】Payload Schema 校验：确保输入符合评估器的契约定义
                is_valid, error_msg, validated_payload = validate_payload(request.type, request.payload)
                if not is_valid:
                    logger.warning(
                        f"Payload 校验失败 | type={request.type} | error={error_msg}"
                    )
                    return self._build_validation_error_result(request, error_msg, start_time)

                # 更新 payload 为校验后的数据（可能包含默认值填充等）
                if validated_payload is not None:
                    request = request.model_copy(update={"payload": validated_payload})

                evaluator = EvaluatorFactory.get(request.type, client=self.client)

                # 【精准对齐】调用 safe_evaluate 确保日志记录和异常捕获
                domain_response = evaluator.safe_evaluate(request)

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
        trace_id = request.id or f"engine-async-{time.time()}"

        tracer = get_tracer()
        with TraceContext(
            tracer,
            "pipeline.evaluation.async",
            attributes={
                "pipeline.type": "async",
                "request.id": trace_id,
                "request.type": request.type,
            },
        ):
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
                        new_payload = request.payload.copy()
                        new_payload["actual_output"] = actual_output
                        request = request.model_copy(update={"payload": new_payload})

                request = self._normalize_payload_fields(request)

                # 【新增】Payload Schema 校验：确保输入符合评估器的契约定义
                is_valid, error_msg, validated_payload = validate_payload(request.type, request.payload)
                if not is_valid:
                    logger.warning(
                        f"Payload 校验失败 | type={request.type} | error={error_msg}"
                    )
                    return self._build_validation_error_result(request, error_msg, start_time)

                # 更新 payload 为校验后的数据（可能包含默认值填充等）
                if validated_payload is not None:
                    request = request.model_copy(update={"payload": validated_payload})

                evaluator = EvaluatorFactory.get(request.type, client=self.client)

                # 【核心跃迁】调用 safe_evaluate_async 确保日志记录和异常捕获
                domain_response = await evaluator.safe_evaluate_async(request)

                return self._build_evaluation_result(request, evaluator, domain_response, start_time)

            except Exception as e:
                return self._handle_engine_exception(request, e, start_time)

    # ===================== 内部私有辅助收割机 =====================

    def _normalize_payload_fields(self, request: EvaluationSchema) -> EvaluationSchema:
        """标准化 payload 字段名，兼容不同调用方的字段约定

        历史遗留问题：不同评估器期望不同的字段名（code vs actual_output）。
        此方法在调用评估器之前做字段映射，确保评估器能拿到正确的字段。

        映射规则：
        - code 类型: actual_output → code（如果 code 不存在但 actual_output 存在）
        - code 类型: language → metadata.language（如果 metadata.language 不存在但 language 存在）

        返回：新的 EvaluationSchema 实例（因为原实例是 frozen 的）
        """
        if request.type != "code":
            return request

        new_payload = request.payload.copy()
        new_metadata = (request.metadata or {}).copy()

        if "code" not in new_payload and "actual_output" in new_payload:
            new_payload["code"] = new_payload["actual_output"]
        if "language" not in new_metadata and "language" in new_payload:
            new_metadata["language"] = new_payload["language"]

        return request.model_copy(update={"payload": new_payload, "metadata": new_metadata})

    def _build_validation_error_result(
        self,
        request: EvaluationSchema,
        error_msg: str,
        start_time: float,
    ) -> EvaluationResult:
        """构建 Payload 校验失败的结果"""
        latency_ms = (time.perf_counter() - start_time) * 1000
        return EvaluationResult(
            case_id=request.id,
            status=EvaluationRecordStatus.ERROR,
            model_name=(
                (getattr(self.client.config, "model_name", None) or "unknown")
                if self.client and self.client.config
                else "unknown"
            ),
            adapter_name="validator",
            response=DomainResponse(error=error_msg, evaluation_status=EvaluatorStatus.ERROR),
            latency_ms=latency_ms,
        )

    def _build_evaluation_result(
        self,
        request: EvaluationSchema,
        evaluator: Any,
        domain_response: DomainResponse,
        start_time: float,
    ) -> EvaluationResult:
        """统一拼装成功的评测领域实体

        状态转换规则（基于枚举判断，而非字符串匹配）：
        - EvaluatorStatus.SUCCESS → EvaluationRecordStatus.PASSED
        - EvaluatorStatus.PARTIAL → EvaluationRecordStatus.PASSED（标记为部分评估）
        - EvaluatorStatus.CANNOT_EVALUATE → EvaluationRecordStatus.ERROR（无法评估视为错误）
        - EvaluatorStatus.ERROR → EvaluationRecordStatus.ERROR
        """
        # 🧠 2026 架构升级：优先使用 evaluation_status 枚举判断
        eval_status = domain_response.evaluation_status

        if eval_status == EvaluatorStatus.SUCCESS:
            status = EvaluationRecordStatus.PASSED
        elif eval_status == EvaluatorStatus.PARTIAL:
            status = EvaluationRecordStatus.PASSED
        elif eval_status == EvaluatorStatus.CANNOT_EVALUATE:
            status = EvaluationRecordStatus.ERROR
        elif eval_status == EvaluatorStatus.ERROR:
            status = EvaluationRecordStatus.ERROR
        else:
            raise ValueError(f"未知的 evaluation_status: {eval_status}")

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
                status=EvaluationRecordStatus.ERROR,
                model_name=model_name,
                adapter_name="contract_validator",
                response=DomainResponse(error="CONTRACT_ERROR", evaluation_status=EvaluatorStatus.ERROR),
                latency_ms=latency,
                error_message=str(e),
            )
        elif isinstance(e, DomainLogicError):
            logger.error("Case %s 领域逻辑错误: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationRecordStatus.ERROR,
                model_name=model_name,
                adapter_name="domain_handler",
                response=DomainResponse(error="DOMAIN_ERROR", evaluation_status=EvaluatorStatus.ERROR),
                latency_ms=latency,
                error_message=str(e),
            )
        elif isinstance(e, InfrastructureError):
            logger.error("Case %s 基础设施故障: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationRecordStatus.ERROR,
                model_name=model_name,
                adapter_name="infra_handler",
                response=DomainResponse(error="INFRA_ERROR", evaluation_status=EvaluatorStatus.ERROR),
                latency_ms=latency,
                error_message=str(e),
            )
        else:
            logger.exception("Case %s 评测失败（未预期异常）: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationRecordStatus.ERROR,
                model_name=model_name,
                adapter_name="error_handler",
                response=DomainResponse(error="INTERNAL_ERROR", evaluation_status=EvaluatorStatus.ERROR),
                latency_ms=latency,
                error_message=str(e),
            )
