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

            status = (
                EvaluationStatus.PASSED if domain_response.is_valid else EvaluationStatus.FAILED
            )

            return EvaluationResult(
                case_id=request.id,
                status=status,
                model_name=getattr(self.client.config, "model_name", "unknown"),
                adapter_name=evaluator.__class__.__name__,
                response=domain_response,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )

        except ContractValidationError as e:
            # 契约验证错误 - 输入数据不符合要求
            logger.warning("Case %s 契约验证失败: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationStatus.ERROR,
                model_name=getattr(self.client.config, "model_name", "unknown"),
                adapter_name="contract_validator",
                response=DomainResponse(is_valid=False, error=f"契约验证错误: {str(e)}"),
                latency_ms=(time.perf_counter() - start_time) * 1000,
                error_message=str(e),
            )

        except DomainLogicError as e:
            # 领域逻辑错误 - 业务规则触发的异常
            logger.error("Case %s 领域逻辑错误: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationStatus.ERROR,
                model_name=getattr(self.client.config, "model_name", "unknown"),
                adapter_name="domain_handler",
                response=DomainResponse(is_valid=False, error=f"领域错误: {str(e)}"),
                latency_ms=(time.perf_counter() - start_time) * 1000,
                error_message=str(e),
            )

        except InfrastructureError as e:
            # 基础设施错误 - 底层资源异常
            logger.error("Case %s 基础设施故障: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationStatus.ERROR,
                model_name=getattr(self.client.config, "model_name", "unknown"),
                adapter_name="infra_handler",
                response=DomainResponse(is_valid=False, error=f"基础设施错误: {str(e)}"),
                latency_ms=(time.perf_counter() - start_time) * 1000,
                error_message=str(e),
            )

        except Exception as e:
            # 未预期的异常 - 记录完整堆栈
            logger.exception("Case %s 评测失败（未预期异常）: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationStatus.ERROR,
                model_name=getattr(self.client.config, "model_name", "unknown"),
                adapter_name="error_handler",
                response=DomainResponse(is_valid=False, error=str(e)),
                latency_ms=(time.perf_counter() - start_time) * 1000,
                error_message=str(e),
            )
