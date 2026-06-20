import threading
import time

from pydantic import BaseModel, Field

from src.config import settings


class TokenUsage(BaseModel):
    prompt_tokens: int = Field(0, description="提示词Token数")
    completion_tokens: int = Field(0, description="回答Token数")
    total_tokens: int = Field(0, description="总Token数")


class CostRecord(BaseModel):
    record_id: str = Field(..., description="记录ID")
    model_name: str = Field(..., description="模型名称")
    usage: TokenUsage = Field(default_factory=TokenUsage)
    cost_usd: float = Field(0.0, description="成本(美元)")
    latency_ms: float = Field(0.0, description="延迟(毫秒)")
    request_type: str = Field("evaluation", description="请求类型")
    timestamp: float = Field(default_factory=time.time, description="时间戳")


class CostMetrics(BaseModel):
    daily_cost_usd: float = Field(0.0, description="日成本")
    weekly_cost_usd: float = Field(0.0, description="周成本")
    monthly_cost_usd: float = Field(0.0, description="月成本")
    avg_latency_ms: float = Field(0.0, description="平均延迟")
    p50_latency_ms: float = Field(0.0, description="P50延迟")
    p95_latency_ms: float = Field(0.0, description="P95延迟")
    p99_latency_ms: float = Field(0.0, description="P99延迟")
    total_requests: int = Field(0, description="总请求数")
    avg_tokens_per_request: float = Field(0.0, description="平均Token数")


class CostGovernance:
    """成本治理模块

    监控和控制 LLM API 调用的成本和延迟。
    """

    MODEL_COSTS = {
        "gpt-4": {"prompt": 0.00003, "completion": 0.00006},
        "gpt-3.5-turbo": {"prompt": 0.0000015, "completion": 0.000002},
        "claude-3": {"prompt": 0.000008, "completion": 0.000024},
        "gemini-pro": {"prompt": 0.000001, "completion": 0.0000015},
        "default": {"prompt": 0.000002, "completion": 0.000002},
    }

    def __init__(self, daily_cost_limit=None, weekly_cost_limit=None, monthly_cost_limit=None):
        self.records: list[CostRecord] = []
        self._records_lock = threading.Lock()
        self.daily_cost_limit = (
            daily_cost_limit
            if daily_cost_limit is not None
            else settings.__dict__.get("daily_cost_limit", 100.0)
        )
        self.weekly_cost_limit = (
            weekly_cost_limit
            if weekly_cost_limit is not None
            else settings.__dict__.get("weekly_cost_limit", 500.0)
        )
        self.monthly_cost_limit = (
            monthly_cost_limit
            if monthly_cost_limit is not None
            else settings.__dict__.get("monthly_cost_limit", 2000.0)
        )
        self.hourly_request_limit = settings.__dict__.get("hourly_request_limit", 10000)

    def calculate_cost(self, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        costs = self.MODEL_COSTS.get(model_name.lower(), self.MODEL_COSTS["default"])
        return (prompt_tokens * costs["prompt"]) + (completion_tokens * costs["completion"])

    def record_usage(
        self,
        record_id: str,
        model_name: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: float = 0,
        request_type: str = "evaluation",
    ) -> CostRecord:
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = self.calculate_cost(model_name, prompt_tokens, completion_tokens)

        record = CostRecord(
            record_id=record_id,
            model_name=model_name,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            request_type=request_type,
        )

        with self._records_lock:
            self.records.append(record)
        return record

    def get_metrics(self, hours: int | None = None) -> CostMetrics:
        with self._records_lock:
            if hours is not None:
                if hours <= 0:
                    return CostMetrics()
                cutoff_time = time.time() - (hours * 3600)
                filtered_records = [r for r in self.records if r.timestamp > cutoff_time]
            else:
                filtered_records = list(self.records)

        if not filtered_records:
            return CostMetrics()

        now = time.time()
        day_cutoff = now - 86400
        week_cutoff = now - 604800
        month_cutoff = now - 2592000

        daily_cost = sum(r.cost_usd for r in filtered_records if r.timestamp > day_cutoff)
        weekly_cost = sum(r.cost_usd for r in filtered_records if r.timestamp > week_cutoff)
        monthly_cost = sum(r.cost_usd for r in filtered_records if r.timestamp > month_cutoff)

        latencies = [r.latency_ms for r in filtered_records]
        latencies.sort()

        total_tokens = sum(r.usage.total_tokens for r in filtered_records)

        return CostMetrics(
            daily_cost_usd=daily_cost,
            weekly_cost_usd=weekly_cost,
            monthly_cost_usd=monthly_cost,
            avg_latency_ms=sum(latencies) / len(latencies),
            p50_latency_ms=latencies[len(latencies) // 2] if latencies else 0,
            p95_latency_ms=latencies[int(len(latencies) * 0.95)] if latencies else 0,
            p99_latency_ms=latencies[int(len(latencies) * 0.99)] if latencies else 0,
            total_requests=len(filtered_records),
            avg_tokens_per_request=total_tokens / len(filtered_records),
        )

    def check_budget(self) -> dict[str, bool | float]:
        metrics = self.get_metrics()
        if self.daily_cost_limit <= 0:
            return {
                "daily_budget_ok": False,
                "daily_usage_percent": 100.0 if metrics.daily_cost_usd > 0 else 0.0,
            }
        return {
            "daily_budget_ok": metrics.daily_cost_usd < self.daily_cost_limit,
            "daily_usage_percent": (metrics.daily_cost_usd / self.daily_cost_limit) * 100,
        }

    def record_request(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        model_name: str = "default",
        latency_ms: float = 0,
    ) -> CostRecord:
        """简化版记录请求（兼容测试接口）"""
        record = CostRecord(
            record_id=f"req_{len(self.records)}",
            model_name=model_name,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
        with self._records_lock:
            self.records.append(record)
        return record

    def get_top_models_by_cost(self, limit: int = 5) -> list[dict[str, float]]:
        with self._records_lock:
            records = list(self.records)
        model_costs: dict[str, float] = {}
        for record in records:
            model_costs[record.model_name] = model_costs.get(record.model_name, 0) + record.cost_usd

        return sorted(
            [{"model_name": k, "total_cost": v} for k, v in model_costs.items()],
            key=lambda x: x["total_cost"],
            reverse=True,
        )[:limit]

    def get_top_requests_by_latency(self, limit: int = 10) -> list[CostRecord]:
        with self._records_lock:
            records = list(self.records)
        return sorted(
            records,
            key=lambda r: r.latency_ms,
            reverse=True,
        )[:limit]


cost_governance = CostGovernance()
