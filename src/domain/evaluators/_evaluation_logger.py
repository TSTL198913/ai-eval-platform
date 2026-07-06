import json
import threading
import time
from datetime import datetime

from loguru import logger

from src.infra.monitoring.metrics import EVAL_CONFIDENCE_HISTOGRAM
from src.infra.monitoring.metrics import EVAL_STATUS_COUNTER
from src.schemas.evaluation import DomainResponse
from src.schemas.evaluation import EvaluationSchema


class EvaluationLoggerMixin:
    _score_cache: dict[str, list[float]] = {}
    _score_cache_lock = threading.Lock()
    _score_cache_max_size = 100

    def _log_evaluation_result(self, request: EvaluationSchema, response: DomainResponse) -> None:
        evaluator_type = type(self).__name__
        input_text = self.get_input_text(request)
        actual_output = self.get_payload_data(request, "actual_output")
        expected_output = self.get_payload_data(request, "expected_output")

        status_label = response.evaluation_status.value
        EVAL_STATUS_COUNTER.labels(evaluator=evaluator_type, status=status_label).inc()

        if response.confidence is not None and response.confidence_level is not None:
            EVAL_CONFIDENCE_HISTOGRAM.labels(
                evaluator=evaluator_type,
                confidence_level=response.confidence_level.value,
            ).observe(response.confidence)

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

        self._record_for_calibration(evaluator_type, response, request)
