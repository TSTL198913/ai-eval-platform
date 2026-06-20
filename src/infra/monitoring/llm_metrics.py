"""
LLM指标采集器

在LLM调用层面采集Token消耗、延迟、错误等指标
"""

import time
from collections.abc import Callable
from functools import wraps

from prometheus_client import Counter, Histogram

from src.infra.monitoring.metrics import registry

# ============================================================================
# LLM层指标定义
# ============================================================================

LLM_CALLS_TOTAL = Counter(
    "llm_calls_total",
    "Total LLM API calls",
    ["provider", "model"],
    registry=registry,
)

LLM_TOKENS_PROMPT = Counter(
    "llm_tokens_prompt_total",
    "Total prompt tokens consumed",
    ["provider", "model"],
    registry=registry,
)

LLM_TOKENS_COMPLETION = Counter(
    "llm_tokens_completion_total",
    "Total completion tokens generated",
    ["provider", "model"],
    registry=registry,
)

LLM_COST_USD = Counter(
    "llm_cost_usd",
    "LLM API cost in USD",
    ["provider", "model"],
    registry=registry,
)

LLM_LATENCY_SECONDS = Histogram(
    "llm_latency_seconds",
    "LLM API call latency in seconds",
    ["provider", "model"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0],
    registry=registry,
)

LLM_ERRORS_TOTAL = Counter(
    "llm_errors_total",
    "Total LLM API errors",
    ["provider", "model", "error_type"],
    registry=registry,
)

LLM_MODEL_SELECTION = Counter(
    "llm_model_selection_total",
    "Model selection count",
    ["provider", "model", "selection_reason"],
    registry=registry,
)

# Token价格表（单位：美元/千Token）
TOKEN_PRICING = {
    "deepseek": {
        "deepseek-chat": {"prompt": 0.0001, "completion": 0.0003},  # DeepSeek V3
        "deepseek-coder": {"prompt": 0.0001, "completion": 0.0003},
    },
    "openai": {
        "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
        "gpt-4o": {"prompt": 0.0025, "completion": 0.01},
    },
    "anthropic": {
        "claude-3-sonnet": {"prompt": 0.0003, "completion": 0.0015},
        "claude-3-5-sonnet": {"prompt": 0.0003, "completion": 0.0015},
    },
}


def get_token_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """计算Token成本"""
    pricing = TOKEN_PRICING.get(provider, {}).get(model, {"prompt": 0, "completion": 0})
    cost = prompt_tokens * pricing["prompt"] + completion_tokens * pricing["completion"]
    return round(cost, 6)


def record_llm_call(
    provider: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency: float = 0,
    error: str | None = None,
    selection_reason: str = "quality",
):
    """
    记录LLM调用指标

    Args:
        provider: 模型提供者 (deepseek/openai/anthropic)
        model: 模型名称
        prompt_tokens: prompt消耗的token数
        completion_tokens: completion生成的token数
        latency: 调用延迟（秒）
        error: 错误类型，如果有的话
        selection_reason: 模型选择原因 (cost/quality/fallback)
    """
    # 记录调用次数
    LLM_CALLS_TOTAL.labels(provider=provider, model=model).inc()

    # 记录Token消耗
    if prompt_tokens > 0:
        LLM_TOKENS_PROMPT.labels(provider=provider, model=model).inc(prompt_tokens)
    if completion_tokens > 0:
        LLM_TOKENS_COMPLETION.labels(provider=provider, model=model).inc(completion_tokens)

    # 记录成本
    cost = get_token_cost(provider, model, prompt_tokens, completion_tokens)
    if cost > 0:
        LLM_COST_USD.labels(provider=provider, model=model).inc(cost)

    # 记录延迟
    if latency > 0:
        LLM_LATENCY_SECONDS.labels(provider=provider, model=model).observe(latency)

    # 记录错误
    if error:
        LLM_ERRORS_TOTAL.labels(provider=provider, model=model, error_type=error).inc()

    # 记录模型选择
    LLM_MODEL_SELECTION.labels(
        provider=provider, model=model, selection_reason=selection_reason
    ).inc()


def timed_llm_call(provider: str, model: str):
    """
    装饰器：自动记录LLM调用延迟

    用法：
        @timed_llm_call("deepseek", "deepseek-chat")
        def call_llm(prompt):
            return client.chat(prompt)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            error = None
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error = type(e).__name__
                raise
            finally:
                latency = time.time() - start_time
                record_llm_call(
                    provider=provider,
                    model=model,
                    latency=latency,
                    error=error,
                )

        return wrapper

    return decorator


class LLMEvaluatorMetrics:
    """评估器级别的LLM指标聚合"""

    def __init__(self):
        self._evaluator_scores = {}
        self._evaluator_latencies = {}

    def record_evaluation(
        self,
        evaluator_type: str,
        score: float,
        latency: float,
        provider: str = "unknown",
        model: str = "unknown",
    ):
        """记录单个评估的分数和延迟"""
        if evaluator_type not in self._evaluator_scores:
            self._evaluator_scores[evaluator_type] = []
            self._evaluator_latencies[evaluator_type] = []

        self._evaluator_scores[evaluator_type].append(score)
        self._evaluator_latencies[evaluator_type].append(latency)

    def get_avg_score(self, evaluator_type: str) -> float:
        """获取平均分数"""
        scores = self._evaluator_scores.get(evaluator_type, [])
        return sum(scores) / len(scores) if scores else 0.0

    def get_avg_latency(self, evaluator_type: str) -> float:
        """获取平均延迟"""
        latencies = self._evaluator_latencies.get(evaluator_type, [])
        return sum(latencies) / len(latencies) if latencies else 0.0

    def get_pass_rate(self, evaluator_type: str, threshold: float = 0.8) -> float:
        """获取通过率"""
        scores = self._evaluator_scores.get(evaluator_type, [])
        if not scores:
            return 0.0
        passed = sum(1 for s in scores if s >= threshold)
        return passed / len(scores)


# 全局LLM指标采集器实例
llm_evaluator_metrics = LLMEvaluatorMetrics()
