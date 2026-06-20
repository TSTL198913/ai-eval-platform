import logging
import time

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.models.base import BaseLLMClient
from src.exceptions import ContractValidationError, DomainLogicError, InfrastructureError
from src.schemas.evaluation import DomainResponse, EvaluationSchema
from src.schemas.schemas import EvaluationResult, EvaluationStatus

logger = logging.getLogger(__name__)


class EvaluationEngine:
    def __init__(self, client: BaseLLMClient):
        self.client = client

    def run(self, request: EvaluationSchema) -> EvaluationResult:
        start_time = time.perf_counter()

        try:
            evaluator = EvaluatorFactory.get(request.type, client=self.client)
            domain_response = evaluator.safe_evaluate(request)

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
                    if self.client.config
                    else "unknown"
                ),
                adapter_name=evaluator.__class__.__name__,
                response=domain_response,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )

        except ContractValidationError as e:
            logger.warning("Case %s 契约验证失败: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationStatus.ERROR,
                model_name=(
                    (getattr(self.client.config, "model_name", None) or "unknown")
                    if self.client.config
                    else "unknown"
                ),
                adapter_name="contract_validator",
                response=DomainResponse(is_valid=False, error="CONTRACT_ERROR"),
                latency_ms=(time.perf_counter() - start_time) * 1000,
                error_message=str(e),
            )

        except DomainLogicError as e:
            logger.error("Case %s 领域逻辑错误: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationStatus.ERROR,
                model_name=(
                    (getattr(self.client.config, "model_name", None) or "unknown")
                    if self.client.config
                    else "unknown"
                ),
                adapter_name="domain_handler",
                response=DomainResponse(is_valid=False, error="DOMAIN_ERROR"),
                latency_ms=(time.perf_counter() - start_time) * 1000,
                error_message=str(e),
            )

        except InfrastructureError as e:
            logger.error("Case %s 基础设施故障: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationStatus.ERROR,
                model_name=(
                    (getattr(self.client.config, "model_name", None) or "unknown")
                    if self.client.config
                    else "unknown"
                ),
                adapter_name="infra_handler",
                response=DomainResponse(is_valid=False, error="INFRA_ERROR"),
                latency_ms=(time.perf_counter() - start_time) * 1000,
                error_message=str(e),
            )

        except Exception as e:
            logger.exception("Case %s 评测失败（未预期异常）: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationStatus.ERROR,
                model_name=(
                    (getattr(self.client.config, "model_name", None) or "unknown")
                    if self.client.config
                    else "unknown"
                ),
                adapter_name="error_handler",
                response=DomainResponse(is_valid=False, error="INTERNAL_ERROR"),
                latency_ms=(time.perf_counter() - start_time) * 1000,
                error_message=str(e),
            )
