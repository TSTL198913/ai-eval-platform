"""
📊 src/domain/evaluators/standard_metric_evaluator.py
标准指标评估器 - 将 BLEU/ROUGE/F1-Token 等业界标准指标封装为统一评估器

支持通过 EvaluatorFactory 注册，与项目内的其他评估器无缝协同。
支持 payload 参数：
  - metric: str - 指标名称（BLEU-4 / ROUGE-1 / ROUGE-2 / ROUGE-L / F1-Token / Levenshtein / CosineSimilarity）
  - actual_output: str - 实际输出
  - expected_output: str - 期望输出
"""

import logging
from typing import Any

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.metrics.standard_metrics import (
    BLEUMetric,
    CosineSimilarityMetric,
    F1TokenMetric,
    LevenshteinMetric,
    ROUGEMetric,
    get_metric,
)
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)

SUPPORTED_METRICS = {
    "BLEU-4": lambda: BLEUMetric(max_n=4),
    "BLEU-2": lambda: BLEUMetric(max_n=2),
    "ROUGE-1": lambda: ROUGEMetric("rouge1"),
    "ROUGE-2": lambda: ROUGEMetric("rouge2"),
    "ROUGE-L": lambda: ROUGEMetric("rougeL"),
    "F1-Token": lambda: F1TokenMetric(),
    "Levenshtein": lambda: LevenshteinMetric(),
    "CosineSimilarity": lambda: CosineSimilarityMetric(),
}


@EvaluatorFactory.register("standard_metric")
class StandardMetricEvaluator(BaseEvaluator):
    """通用标准指标评估器（dispatcher）

    通过 payload.metric 字段路由到具体的标准指标实现。
    """

    def __init__(self, client: Any | None = None) -> None:
        super().__init__(client, require_expected=True)

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        # 1. 基础输入验证
        if error := self.validate_input(request):
            return error
        if error := self.validate_expected(request):
            return error

        actual_output = self.get_payload_data(request, "actual_output", "")
        expected_output = self.get_payload_data(request, "expected_output", "")
        metric_name = self.get_payload_data(request, "metric", "BLEU-4")

        # 2. 解析指标
        metric = self._resolve_metric(metric_name)
        if metric is None:
            return self.create_error_response(
                error_message=f"不支持的标准指标: {metric_name}。已支持: {list(SUPPORTED_METRICS.keys())}",
                error_code="UNSUPPORTED_METRIC",
            )

        # 3. 计算分数
        try:
            score = metric.compute(actual_output, expected_output)
        except Exception as e:
            logger.exception(f"标准指标 {metric_name} 计算失败: {e}")
            return self.create_error_response(
                error_message=f"标准指标计算异常: {e}",
                error_code="METRIC_COMPUTE_ERROR",
            )

        return self.create_success_response(
            text=f"{metric_name} 评估完成",
            score=score,
            data={
                "metric": metric_name,
                "actual_output": actual_output,
                "expected_output": expected_output,
                "description": metric.get_description(),
            },
        )

    @staticmethod
    def _resolve_metric(name: str):
        """解析指标名称到具体实现"""
        if name in SUPPORTED_METRICS:
            return SUPPORTED_METRICS[name]()
        # 兼容其他注册指标
        return get_metric(name)


@EvaluatorFactory.register("multi_metric")
class MultiMetricEvaluator(BaseEvaluator):
    """多指标综合评估器：一次调用输出所有标准指标的分数

    适合作为综合报告生成、模型能力画像的入口。
    """

    def __init__(self, client: Any | None = None) -> None:
        super().__init__(client)

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        if error := self.validate_input(request):
            return error
        if error := self.validate_expected(request):
            return error

        actual_output = self.get_payload_data(request, "actual_output", "")
        expected_output = self.get_payload_data(request, "expected_output", "")

        # 可选：仅计算指定的指标子集
        selected = self.get_payload_data(request, "metrics", None)
        if selected and isinstance(selected, list):
            metrics_to_run = {
                name: factory() for name, factory in SUPPORTED_METRICS.items() if name in selected
            }
        else:
            metrics_to_run = {name: factory() for name, factory in SUPPORTED_METRICS.items()}

        if not metrics_to_run:
            return self.create_error_response(
                error_message="未指定有效的指标（metrics 参数为空）",
                error_code="EMPTY_METRICS",
            )

        # 计算所有指标
        results: dict[str, dict] = {}
        scores: list[float] = []
        for name, metric in metrics_to_run.items():
            try:
                score = metric.compute(actual_output, expected_output)
                results[name] = {
                    "score": round(score, 4),
                    "description": metric.get_description(),
                }
                scores.append(score)
            except Exception as e:
                logger.warning(f"指标 {name} 计算失败: {e}")
                results[name] = {"score": 0.0, "error": str(e)}

        # 加权平均综合分（简单算术均值）
        composite_score = sum(scores) / len(scores) if scores else 0.0

        return self.create_success_response(
            text=f"已计算 {len(results)} 个标准指标",
            score=round(composite_score, 4),
            data={
                "actual_output": actual_output,
                "expected_output": expected_output,
                "metrics": results,
                "composite_score": round(composite_score, 4),
                "metric_count": len(results),
            },
        )
