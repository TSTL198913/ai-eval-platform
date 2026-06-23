"""
评估器日志工具模块
提供结构化日志模板和可观测性辅助功能
"""

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def log_evaluation_start(
    trace_id: str, evaluator_name: str, request_type: str, input_length: int, **kwargs
) -> None:
    """
    记录评估开始日志

    Args:
        trace_id: 追踪ID
        evaluator_name: 评估器名称
        request_type: 请求类型
        input_length: 输入长度
        **kwargs: 额外信息
    """
    log_data = {
        "event": "evaluation_start",
        "trace_id": trace_id,
        "evaluator": evaluator_name,
        "request_type": request_type,
        "input_length": input_length,
        "timestamp": time.time(),
        **kwargs,
    }
    logger.info(json.dumps(log_data))


def log_evaluation_completion(
    trace_id: str,
    evaluator_name: str,
    score: float,
    is_valid: bool,
    execution_time_ms: float,
    **kwargs,
) -> None:
    """
    记录评估完成日志

    Args:
        trace_id: 追踪ID
        evaluator_name: 评估器名称
        score: 评估分数
        is_valid: 是否有效
        execution_time_ms: 执行时间(毫秒)
        **kwargs: 额外信息
    """
    log_data = {
        "event": "evaluation_completion",
        "trace_id": trace_id,
        "evaluator": evaluator_name,
        "score": score,
        "is_valid": is_valid,
        "execution_time_ms": execution_time_ms,
        "timestamp": time.time(),
        **kwargs,
    }
    logger.info(json.dumps(log_data))


def log_evaluation_error(
    trace_id: str,
    evaluator_name: str,
    error_type: str,
    error_message: str,
    execution_time_ms: float,
    **kwargs,
) -> None:
    """
    记录评估错误日志

    Args:
        trace_id: 追踪ID
        evaluator_name: 评估器名称
        error_type: 错误类型
        error_message: 错误消息
        execution_time_ms: 执行时间(毫秒)
        **kwargs: 额外信息
    """
    log_data = {
        "event": "evaluation_error",
        "trace_id": trace_id,
        "evaluator": evaluator_name,
        "error_type": error_type,
        "error_message": error_message,
        "execution_time_ms": execution_time_ms,
        "timestamp": time.time(),
        **kwargs,
    }
    logger.error(json.dumps(log_data))


def log_circuit_breaker_trigger(
    trace_id: str, evaluator_name: str, breaker_name: str, state: str, **kwargs
) -> None:
    """
    记录熔断器触发日志

    Args:
        trace_id: 追踪ID
        evaluator_name: 评估器名称
        breaker_name: 熔断器名称
        state: 熔断器状态
        **kwargs: 额外信息
    """
    log_data = {
        "event": "circuit_breaker_trigger",
        "trace_id": trace_id,
        "evaluator": evaluator_name,
        "breaker_name": breaker_name,
        "state": state,
        "timestamp": time.time(),
        **kwargs,
    }
    logger.warning(json.dumps(log_data))


def log_fallback_execution(
    trace_id: str, evaluator_name: str, fallback_reason: str, score: float, **kwargs
) -> None:
    """
    记录降级执行日志

    Args:
        trace_id: 追踪ID
        evaluator_name: 评估器名称
        fallback_reason: 降级原因
        score: 降级分数
        **kwargs: 额外信息
    """
    log_data = {
        "event": "fallback_execution",
        "trace_id": trace_id,
        "evaluator": evaluator_name,
        "fallback_reason": fallback_reason,
        "score": score,
        "timestamp": time.time(),
        **kwargs,
    }
    logger.warning(json.dumps(log_data))


def log_performance_metric(
    trace_id: str,
    evaluator_name: str,
    metric_name: str,
    metric_value: float,
    unit: str = "",
    **kwargs,
) -> None:
    """
    记录性能指标日志

    Args:
        trace_id: 追踪ID
        evaluator_name: 评估器名称
        metric_name: 指标名称
        metric_value: 指标值
        unit: 单位
        **kwargs: 额外信息
    """
    log_data = {
        "event": "performance_metric",
        "trace_id": trace_id,
        "evaluator": evaluator_name,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "unit": unit,
        "timestamp": time.time(),
        **kwargs,
    }
    logger.info(json.dumps(log_data))


class EvaluationMetrics:
    """
    评估器性能指标收集器
    """

    def __init__(self, trace_id: str, evaluator_name: str):
        self.trace_id = trace_id
        self.evaluator_name = evaluator_name
        self._metrics: dict[str, Any] = {}
        self._timers: dict[str, float] = {}

    def start_timer(self, name: str) -> None:
        """启动计时器"""
        self._timers[name] = time.perf_counter()

    def stop_timer(self, name: str) -> float:
        """停止计时器并返回耗时(毫秒)"""
        if name in self._timers:
            elapsed_ms = (time.perf_counter() - self._timers[name]) * 1000
            self._metrics[f"{name}_duration_ms"] = round(elapsed_ms, 2)
            del self._timers[name]
            return elapsed_ms
        return 0.0

    def record_metric(self, name: str, value: Any) -> None:
        """记录指标"""
        self._metrics[name] = value

    def log_all(self) -> None:
        """记录所有指标"""
        log_performance_metric(
            trace_id=self.trace_id, evaluator_name=self.evaluator_name, **self._metrics
        )

    def get_metrics(self) -> dict[str, Any]:
        """获取所有指标"""
        return dict(self._metrics)
