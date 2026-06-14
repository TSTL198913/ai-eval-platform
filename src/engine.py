import logging
import time

from src.domain.evaluators.base import EvaluatorFactory
from src.domain.models.base import BaseLLMClient
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
                EvaluationStatus.PASSED
                if domain_response.is_valid
                else EvaluationStatus.FAILED
            )

            return EvaluationResult(
                case_id=request.id,
                status=status,
                model_name=getattr(self.client.config, "model_name", "unknown"),
                adapter_name=evaluator.__class__.__name__,
                response=domain_response,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )

        except Exception as e:
            logger.error("Case %s 评测失败: %s", request.id, str(e))
            return EvaluationResult(
                case_id=request.id,
                status=EvaluationStatus.ERROR,
                model_name=getattr(self.client.config, "model_name", "unknown"),
                adapter_name="error_handler",
                response=DomainResponse(is_valid=False, error=str(e)),
                latency_ms=(time.perf_counter() - start_time) * 1000,
                error_message=str(e),
            )
