import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class SampledRequest:
    request_id: str
    user_input: str
    model_output: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OnlineEvaluationResult:
    request_id: str
    is_success: bool
    score: float
    feedback: Optional[str] = None
    error_type: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OnlineEvaluationStats:
    total_samples: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_score: float = 0.0
    error_types: Dict[str, int] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total_samples if self.total_samples > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_samples": self.total_samples,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_rate,
            "avg_score": self.avg_score,
            "error_types": self.error_types,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class ProductionSampler:
    def __init__(self, sample_rate: float = 0.1):
        self.sample_rate = sample_rate
        self._sampled_requests: List[SampledRequest] = []

    def should_sample(self) -> bool:
        return random.random() < self.sample_rate

    def sample(self, request_id: str, user_input: str, model_output: str, **metadata) -> Optional[SampledRequest]:
        if not self.should_sample():
            return None

        request = SampledRequest(
            request_id=request_id,
            user_input=user_input,
            model_output=model_output,
            metadata=metadata,
        )
        self._sampled_requests.append(request)
        return request

    def get_sampled_requests(self, limit: int = 100) -> List[SampledRequest]:
        return self._sampled_requests[-limit:]

    def clear(self):
        self._sampled_requests.clear()


class OnlineEvaluator:
    def __init__(
        self,
        llm_judge: Callable[[str, str], Tuple[bool, float, Optional[str]]],
        dataset_manager=None,
    ):
        self.llm_judge = llm_judge
        self.dataset_manager = dataset_manager
        self._results: List[OnlineEvaluationResult] = []
        self._sampled_requests: List[SampledRequest] = []

    def evaluate(self, request: SampledRequest) -> OnlineEvaluationResult:
        is_success, score, feedback = self.llm_judge(request.user_input, request.model_output)

        result = OnlineEvaluationResult(
            request_id=request.request_id,
            is_success=is_success,
            score=score,
            feedback=feedback,
            error_type=None if is_success else self._classify_error(request, feedback),
        )

        self._results.append(result)
        self._sampled_requests.append(request)
        return result

    def evaluate_batch(self, requests: List[SampledRequest]) -> List[OnlineEvaluationResult]:
        results = []
        for request in requests:
            result = self.evaluate(request)
            results.append(result)
        return results

    def _classify_error(self, request: SampledRequest, feedback: Optional[str]) -> str:
        if feedback:
            feedback_lower = feedback.lower()
            if "hallucination" in feedback_lower or "事实错误" in feedback:
                return "hallucination"
            if "格式错误" in feedback_lower or "format" in feedback_lower:
                return "format_error"
            if "超时" in feedback_lower or "timeout" in feedback_lower:
                return "timeout"
            if "工具调用" in feedback_lower or "tool" in feedback_lower:
                return "tool_error"
            if "拒绝" in feedback_lower or "reject" in feedback_lower:
                return "rejection"
        return "unknown"

    def recycle_failed_samples(
        self,
        dataset_id: str,
        max_recycle: int = 10,
    ) -> List[OnlineEvaluationResult]:
        if not self.dataset_manager:
            return []

        failed_results = [r for r in self._results if not r.is_success]
        failed_results.sort(key=lambda r: r.score)
        to_recycle = failed_results[:max_recycle]

        recycled = []
        for result in to_recycle:
            request = next((r for r in self._sampled_requests if r.request_id == result.request_id), None)
            if request:
                sample_data = {
                    "question": request.user_input,
                    "answer": None,
                    "metadata": {
                        "original_output": request.model_output,
                        "evaluation_score": result.score,
                        "feedback": result.feedback,
                        "error_type": result.error_type,
                        "is_recycled": True,
                        "recycled_at": datetime.utcnow().isoformat(),
                    },
                }
                self.dataset_manager.add_samples(dataset_id, [sample_data])
                recycled.append(result)

        return recycled

    def get_stats(self) -> OnlineEvaluationStats:
        if not self._results:
            return OnlineEvaluationStats()

        total = len(self._results)
        success_count = sum(1 for r in self._results if r.is_success)
        failure_count = total - success_count
        avg_score = sum(r.score for r in self._results) / total

        error_types: Dict[str, int] = {}
        for result in self._results:
            if result.error_type:
                error_types[result.error_type] = error_types.get(result.error_type, 0) + 1

        return OnlineEvaluationStats(
            total_samples=total,
            success_count=success_count,
            failure_count=failure_count,
            avg_score=avg_score,
            error_types=error_types,
            start_time=self._results[0].timestamp,
            end_time=self._results[-1].timestamp,
        )

    def get_results(self) -> List[OnlineEvaluationResult]:
        return self._results

    def clear(self):
        self._results.clear()


class OnlineEvaluationPipeline:
    def __init__(
        self,
        sampler: ProductionSampler,
        evaluator: OnlineEvaluator,
        dataset_manager=None,
        recycle_interval: int = 100,
    ):
        self.sampler = sampler
        self.evaluator = evaluator
        self.dataset_manager = dataset_manager
        self.recycle_interval = recycle_interval
        self._count_since_last_recycle = 0

    def process_request(self, request_id: str, user_input: str, model_output: str, **metadata) -> Optional[OnlineEvaluationResult]:
        sampled = self.sampler.sample(request_id, user_input, model_output, **metadata)
        if not sampled:
            return None

        result = self.evaluator.evaluate(sampled)
        self._count_since_last_recycle += 1

        if self._count_since_last_recycle >= self.recycle_interval and self.dataset_manager:
            self._count_since_last_recycle = 0

        return result

    def trigger_recycle(self, dataset_id: str) -> List[OnlineEvaluationResult]:
        if not self.dataset_manager:
            return []
        return self.evaluator.recycle_failed_samples(dataset_id)

    def get_stats(self) -> OnlineEvaluationStats:
        return self.evaluator.get_stats()
