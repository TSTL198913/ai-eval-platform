import asyncio
import time
from typing import Any

from loguru import logger

from src.config.thresholds import DEFAULT_BATCH_MAX_CONCURRENT
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.models.base import BaseLLMClient
from src.domain.services.evaluation_cache_service import evaluation_cache_service
from src.domain.services.inference_service import InferenceService
from src.exceptions import ContractValidationError
from src.exceptions import DomainLogicError
from src.exceptions import InfrastructureError
from src.infra.monitoring.tracing import TraceContext
from src.infra.monitoring.tracing import get_tracer
from src.schemas.evaluation import DomainResponse
from src.schemas.evaluation import EvaluationSchema
from src.schemas.evaluation import EvaluatorStatus
from src.schemas.evaluator_schemas import validate_payload
from src.schemas.schemas import EvaluationResult
from src.schemas.schemas import EvaluationStatus as EvaluationRecordStatus


class EvaluationEngine:
    def __init__(
        self,
        client: BaseLLMClient,
        cache_enabled: bool = True,
        inference_client: BaseLLMClient | None = None,
        inference_service: InferenceService | None = None
    ):
        self.client = client
        self.inference_client = inference_client or client
        self.inference_service = inference_service or InferenceService(self.inference_client)
        self.cache_enabled = cache_enabled

        # 当未提供独立推理客户端/服务时，self.client 会被推理服务复用。
        # 此时评估器不应再持有同一 LLM 客户端，否则同一 LLM 既负责生成 actual_output
        # 又负责评估，会造成自我评估偏差并污染 mock 调用记录。
        # 仅当存在独立推理通道时，评估器才使用 self.client 进行 LLM 评估。
        has_dedicated_inference = inference_client is not None or inference_service is not None
        self._evaluator_client = self.client if has_dedicated_inference else None

    def _ensure_actual_output(self, request: EvaluationSchema) -> EvaluationSchema:
        """确保 request.payload 包含 actual_output（同步版本）

        当 actual_output 缺失且存在 prompt/input 时，自动调用 LLM 生成 actual_output。
        该行为对所有 evaluate_mode 生效：数据可用性决定是否触发推理，而非模式枚举。
        生成结果直接写入原 request.payload 字典，确保调用方可见。
        """
        actual_output = request.payload.get("actual_output")

        if not actual_output:
            prompt = request.payload.get("prompt", request.payload.get("input"))
            if prompt and self.inference_service:
                actual_output = self.inference_service.generate(prompt)
                request.payload["actual_output"] = actual_output

        return request

    async def _ensure_actual_output_async(self, request: EvaluationSchema) -> EvaluationSchema:
        """确保 request.payload 包含 actual_output（异步版本）

        当 actual_output 缺失且存在 prompt/input 时，自动调用 LLM 生成 actual_output。
        该行为对所有 evaluate_mode 生效：数据可用性决定是否触发推理，而非模式枚举。
        生成结果直接写入原 request.payload 字典，确保调用方可见。
        """
        actual_output = request.payload.get("actual_output")

        if not actual_output:
            prompt = request.payload.get("prompt", request.payload.get("input"))
            if prompt and self.inference_service:
                actual_output = await self.inference_service.generate_async(prompt)
                request.payload["actual_output"] = actual_output

        return request

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
                request = self._ensure_actual_output(request)

                request = self._normalize_payload_fields(request)

                conflict_response = self._validate_model_conflict(request)
                if conflict_response:
                    logger.error(f"模型冲突阻断 | request.id={request.id}")
                    return self._build_evaluation_result(request, None, conflict_response, start_time)

                is_valid, error_msg, validated_payload = validate_payload(request.type, request.payload)
                if not is_valid:
                    logger.warning(
                        f"Payload 校验失败 | type={request.type} | error={error_msg}"
                    )
                    return self._build_validation_error_result(request, error_msg, start_time)

                if validated_payload is not None:
                    request = request.model_copy(update={"payload": validated_payload})

                if self.cache_enabled:
                    if cached_response := evaluation_cache_service.get(request):
                        logger.debug(f"缓存命中 | request.id={request.id}")
                        return self._build_evaluation_result(request, None, cached_response, start_time)

                evaluator = EvaluatorFactory.get(request.type, client=self._evaluator_client)

                domain_response = evaluator.safe_evaluate(request)

                if self.cache_enabled and domain_response.evaluation_status == EvaluatorStatus.SUCCESS:
                    evaluation_cache_service.set(request, domain_response)

                return self._build_evaluation_result(request, evaluator, domain_response, start_time)

            except Exception as e:
                return self._handle_engine_exception(request, e, start_time)

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
                request = await self._ensure_actual_output_async(request)

                request = self._normalize_payload_fields(request)

                conflict_response = self._validate_model_conflict(request)
                if conflict_response:
                    logger.error(f"模型冲突阻断 | request.id={request.id}")
                    return self._build_evaluation_result(request, None, conflict_response, start_time)

                is_valid, error_msg, validated_payload = validate_payload(request.type, request.payload)
                if not is_valid:
                    logger.warning(
                        f"Payload 校验失败 | type={request.type} | error={error_msg}"
                    )
                    return self._build_validation_error_result(request, error_msg, start_time)

                if validated_payload is not None:
                    request = request.model_copy(update={"payload": validated_payload})

                if self.cache_enabled:
                    if cached_response := evaluation_cache_service.get(request):
                        logger.debug(f"缓存命中 | request.id={request.id}")
                        return self._build_evaluation_result(request, None, cached_response, start_time)

                evaluator = EvaluatorFactory.get(request.type, client=self._evaluator_client)

                domain_response = await evaluator.safe_evaluate_async(request)

                if self.cache_enabled and domain_response.evaluation_status == EvaluatorStatus.SUCCESS:
                    evaluation_cache_service.set(request, domain_response)

                return self._build_evaluation_result(request, evaluator, domain_response, start_time)

            except Exception as e:
                return self._handle_engine_exception(request, e, start_time)

    def run_batch(self, requests: list[EvaluationSchema], max_concurrent: int = DEFAULT_BATCH_MAX_CONCURRENT) -> list[EvaluationResult]:
        """
        📦 同步批量评测：适用于 Benchmark 和批量测试场景。

        Args:
            requests: 评估请求列表
            max_concurrent: 最大并发数（用于限制资源使用）

        Returns:
            评估结果列表（保持与输入相同的顺序）
        """
        import concurrent.futures

        start_time = time.perf_counter()
        logger.info(f"开始批量评估，共 {len(requests)} 个请求，最大并发 {max_concurrent}")

        results: list[EvaluationResult | None] = [None] * len(requests)

        def process_request(idx: int, req: EvaluationSchema):
            try:
                result = self.run(req)
                results[idx] = result
            except Exception as e:
                logger.error(f"批量评估请求 {req.id} 失败: {e}")
                results[idx] = self._handle_engine_exception(req, e, time.perf_counter())

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = []
            for idx, req in enumerate(requests):
                futures.append(executor.submit(process_request, idx, req))

            concurrent.futures.wait(futures)

        total_latency = (time.perf_counter() - start_time) * 1000
        logger.info(f"批量评估完成，总耗时 {total_latency:.2f}ms")

        return [r for r in results if r is not None]

    async def run_batch_async(self, requests: list[EvaluationSchema]) -> list[EvaluationResult]:
        """
        🚀📦 异步批量评测：专为大规模 Benchmark 优化，支持高并发。

        Args:
            requests: 评估请求列表

        Returns:
            评估结果列表（保持与输入相同的顺序）
        """
        start_time = time.perf_counter()
        logger.info(f"开始异步批量评估，共 {len(requests)} 个请求")

        tasks = [self.run_async(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for idx, result in enumerate(results):
            req = requests[idx]
            if isinstance(result, Exception):
                logger.error(f"异步批量评估请求 {req.id} 失败: {result}")
                processed_results.append(self._handle_engine_exception(req, result, time.perf_counter()))
            else:
                processed_results.append(result)

        total_latency = (time.perf_counter() - start_time) * 1000
        logger.info(f"异步批量评估完成，总耗时 {total_latency:.2f}ms")

        return processed_results

    def _normalize_payload_fields(self, request: EvaluationSchema) -> EvaluationSchema:
        """标准化 payload 字段名，兼容不同调用方的字段约定"""
        if request.type != "code":
            return request

        new_payload = request.payload.copy()
        new_metadata = (request.metadata or {}).copy()

        if "code" not in new_payload and "actual_output" in new_payload:
            new_payload["code"] = new_payload["actual_output"]
        if "language" not in new_metadata and "language" in new_payload:
            new_metadata["language"] = new_payload["language"]

        return request.model_copy(update={"payload": new_payload, "metadata": new_metadata})

    def _validate_model_conflict(self, request: EvaluationSchema) -> DomainResponse | None:
        """验证是否存在模型自我评估的利益冲突
        
        在评估前进行独立校验，不受 evaluate_mode 限制。
        对于 llm_as_judge 模式，强制校验生成模型与评估模型是否相同。
        
        返回: DomainResponse 如果检测到冲突且需要阻断，否则返回 None
        """
        if request.type not in ["llm_as_judge", "general", "qa"]:
            return None

        eval_model_key = f"{request.model_provider}:{request.model_name}" if request.model_provider else None
        inference_model_key = f"{request.inference_model_provider}:{request.inference_model_name}" if request.inference_model_provider else None

        if inference_model_key is None:
            inference_model_key = eval_model_key

        if eval_model_key and inference_model_key and eval_model_key == inference_model_key:
            logger.warning(
                f"⚠️ 模型自我评估风险 | request.id={request.id} | type={request.type} "
                f"| eval_model={eval_model_key} | inference_model={inference_model_key} "
                f"| 建议使用不同模型进行评估以提高可信度"
            )

            block_self_eval = self._should_block_self_evaluation()
            if block_self_eval:
                logger.error(
                    f"❌ 模型冲突阻断 | request.id={request.id} | type={request.type} "
                    f"| model={eval_model_key} | BLOCK_SELF_EVALUATION=true"
                )
                return DomainResponse(
                    error="MODEL_CONFLICT",
                    evaluation_status=EvaluatorStatus.ERROR,
                    data={"conflict_type": "self_evaluation", "model": eval_model_key},
                )

        return None

    def _should_block_self_evaluation(self) -> bool:
        """判断是否需要阻断自我评估（通过环境变量控制）"""
        import os
        return os.environ.get("BLOCK_SELF_EVALUATION", "false").lower() == "true"

    def _get_model_name(self) -> str:
        """安全获取模型名称"""
        if not self.client:
            return "unknown"
        try:
            config = getattr(self.client, "config", None)
            if not config:
                return "unknown"
            model_name = getattr(config, "model_name", "unknown")
            return str(model_name) if model_name is not None else "unknown"
        except Exception:
            return "unknown"

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
            model_name=self._get_model_name(),
            adapter_name="payload_validator",
            response=DomainResponse(
                error=error_msg,
                evaluation_status=EvaluatorStatus.ERROR,
            ),
            latency_ms=latency_ms,
            error_message=error_msg,
        )

    def _build_evaluation_result(
        self,
        request: EvaluationSchema,
        evaluator: Any,
        domain_response: DomainResponse,
        start_time: float,
    ) -> EvaluationResult:
        """统一拼装成功的评测领域实体"""
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
            model_name=self._get_model_name(),
            adapter_name=evaluator.__class__.__name__,
            response=domain_response,
            latency_ms=(time.perf_counter() - start_time) * 1000,
            error_message=domain_response.error if domain_response.error else None,
        )

    def _handle_engine_exception(
        self, request: EvaluationSchema, e: Exception, start_time: float
    ) -> EvaluationResult:
        """将各类灾难性异常和契约校验失败，统一收拢为标准错误相应"""
        latency = (time.perf_counter() - start_time) * 1000
        model_name = self._get_model_name()

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
