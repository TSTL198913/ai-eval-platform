"""
🎯 src/domain/evaluators/ragas_evaluator.py
RAGAS 适配器 - 将 RAGAS 框架的核心指标封装为统一评估器

RAGAS 核心指标：
- Faithfulness: 答案对检索上下文的忠实度（无幻觉）
- Answer Relevancy: 答案与问题的相关度
- Context Precision: 检索上下文的精度
- Context Recall: 检索上下文的召回率
- Context Entity Recall: 上下文实体召回
- Answer Correctness: 答案正确性
- Answer Similarity: 答案相似度

设计要点：
1. 适配器模式 - RAGAS 缺失时降级到本地 Embedding + LLM 实现
2. 统一接口 - 与 BaseEvaluator 协议完全兼容
3. 数据契约 - payload 必须包含 question / context / answer 字段
4. 故障隔离 - 任何子指标失败不影响其他指标输出
"""

import logging
from typing import Any

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)

# 探测 RAGAS 是否可用
try:
    from ragas.metrics import (
        answer_correctness,
        answer_relevancy,
        answer_similarity,
        context_precision,
        context_recall,
        faithfulness,
    )
    # from ragas.metrics._context_entity_recall import ContextEntityRecall  # unused

    HAS_RAGAS = True
except ImportError:
    HAS_RAGAS = False
    logger.warning("⚠️ 未安装 ragas，RAGAS 评估器将降级到本地实现")

# 复用项目内的 Embedding 服务
try:
    from src.domain.evaluators.embedding_service import EmbeddingService

    HAS_EMBEDDING = True
except ImportError:
    HAS_EMBEDDING = False


# ==================== 本地降级实现 ====================


def _local_faithfulness(answer: str, context: str) -> float:
    """忠实度：答案中能溯源到 context 的 token 比例"""
    if not answer or not context:
        return 0.0

    answer_tokens = set(answer.lower().split())
    context_tokens = set(context.lower().split())

    if not answer_tokens:
        return 0.0

    overlap = answer_tokens & context_tokens
    return min(1.0, len(overlap) / len(answer_tokens))


def _local_answer_relevancy(question: str, answer: str) -> float:
    """答案相关性：answer 中与 question 共享的关键词占比"""
    if not question or not answer:
        return 0.0

    question_tokens = set(question.lower().split())
    answer_tokens = set(answer.lower().split())

    if not question_tokens or not answer_tokens:
        return 0.0

    overlap = question_tokens & answer_tokens
    # 用 Jaccard 系数做软匹配
    union = question_tokens | answer_tokens
    return len(overlap) / len(union) if union else 0.0


def _local_context_precision(context: str | list[str], answer: str) -> float:
    """上下文精度：context 中与 answer 相关的部分占比"""
    if isinstance(context, list):
        if not context:
            return 0.0
        scores = [_local_faithfulness(answer, ctx) for ctx in context]
        return sum(scores) / len(scores)
    return _local_faithfulness(answer, context)


def _local_context_recall(context: str | list[str], ground_truth: str) -> float:
    """上下文召回：ground_truth 中能在 context 找到的 token 比例"""
    if not ground_truth:
        return 0.0

    contexts = context if isinstance(context, list) else [context]
    if not contexts:
        return 0.0

    gt_tokens = set(ground_truth.lower().split())
    if not gt_tokens:
        return 0.0

    all_context_tokens: set[str] = set()
    for ctx in contexts:
        all_context_tokens |= set(ctx.lower().split())

    overlap = gt_tokens & all_context_tokens
    return min(1.0, len(overlap) / len(gt_tokens))


def _local_answer_similarity(answer: str, ground_truth: str) -> float:
    """答案相似度：基于余弦相似度（若可用）或 Jaccard"""
    if not answer or not ground_truth:
        return 0.0

    if HAS_EMBEDDING:
        try:
            service = EmbeddingService.get_instance()
            if service.is_available():
                return service.calculate_similarity(answer, ground_truth)
        except Exception as e:
            logger.warning(f"Embedding 相似度计算失败: {e}")

    # 降级：Jaccard
    a_tokens = set(answer.lower().split())
    b_tokens = set(ground_truth.lower().split())
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = a_tokens & b_tokens
    union = a_tokens | b_tokens
    return len(overlap) / len(union) if union else 0.0


def _local_answer_correctness(answer: str, ground_truth: str) -> float:
    """答案正确性：F1 + 相似度的综合"""
    if not answer or not ground_truth:
        return 0.0
    a_tokens = set(answer.lower().split())
    b_tokens = set(ground_truth.lower().split())
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = len(a_tokens & b_tokens)
    if overlap == 0:
        return 0.0
    precision = overlap / len(a_tokens)
    recall = overlap / len(b_tokens)
    f1 = 2 * precision * recall / (precision + recall)
    similarity = _local_answer_similarity(answer, ground_truth)
    # 综合：F1 占 60%，相似度占 40%
    return 0.6 * f1 + 0.4 * similarity


# ==================== 评估器实现 ====================


@EvaluatorFactory.register("ragas")
class RAGASEvaluator(BaseEvaluator):
    """RAGAS 综合评估器（适配器模式）

    payload 字段约定：
    - question: 用户问题
    - context: 检索上下文（字符串或字符串列表）
    - answer: 模型实际输出
    - ground_truth: 标准答案（可选）
    - metrics: 要计算的指标列表（默认全量）
    """

    DEFAULT_METRICS = [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "answer_correctness",
        "answer_similarity",
    ]

    def __init__(self, client: Any | None = None) -> None:
        super().__init__(client)

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        # 1. 提取数据
        question = self.get_input_text(request)
        answer = self.get_payload_data(request, "answer", "")
        context = self.get_payload_data(request, "context", "")
        ground_truth = self.get_payload_data(request, "ground_truth", "")
        metrics_to_run = self.get_payload_data(request, "metrics", self.DEFAULT_METRICS)

        # 2. 基础验证
        if not question:
            return self.create_error_response(
                error_message="question 不能为空",
                error_code="MISSING_QUESTION",
            )
        if not answer:
            return self.create_error_response(
                error_message="answer 不能为空",
                error_code="MISSING_ANSWER",
            )

        # 3. 计算各指标
        results: dict[str, dict[str, Any]] = {}
        scores: list[float] = []
        used_implementation = "ragas" if HAS_RAGAS else "local"

        for metric_name in metrics_to_run:
            try:
                score = self._compute_metric(metric_name, question, answer, context, ground_truth)
                results[metric_name] = {
                    "score": round(score, 4),
                    "implementation": used_implementation,
                }
                scores.append(score)
            except Exception as e:
                logger.warning(f"RAGAS 指标 {metric_name} 计算失败: {e}")
                results[metric_name] = {
                    "score": 0.0,
                    "error": str(e),
                    "implementation": used_implementation,
                }

        # 4. 综合分
        composite_score = sum(scores) / len(scores) if scores else 0.0

        return self.create_success_response(
            text=f"RAGAS 评估完成（实现: {used_implementation}）",
            score=round(composite_score, 4),
            data={
                "question": question,
                "answer": answer,
                "ground_truth": ground_truth,
                "metrics": results,
                "composite_score": round(composite_score, 4),
                "implementation": used_implementation,
                "has_ragas": HAS_RAGAS,
            },
        )

    def _compute_metric(
        self,
        metric_name: str,
        question: str,
        answer: str,
        context: str | list[str],
        ground_truth: str,
    ) -> float:
        """计算单个 RAGAS 指标

        优先调用 RAGAS 官方实现，失败/缺失时降级到本地实现。
        """
        # 优先路径：RAGAS 官方
        if HAS_RAGAS:
            try:
                return self._ragas_compute(metric_name, question, answer, context, ground_truth)
            except Exception as e:
                logger.warning(f"RAGAS 官方实现失败，降级到本地: {e}")

        # 降级路径：本地实现
        if metric_name == "faithfulness":
            return _local_faithfulness(
                answer, context if isinstance(context, str) else " ".join(context or [])
            )
        if metric_name == "answer_relevancy":
            return _local_answer_relevancy(question, answer)
        if metric_name == "context_precision":
            return _local_context_precision(context, answer)
        if metric_name == "context_recall":
            return _local_context_recall(context, ground_truth)
        if metric_name == "answer_correctness":
            return _local_answer_correctness(answer, ground_truth)
        if metric_name == "answer_similarity":
            return _local_answer_similarity(answer, ground_truth)
        return 0.0

    def _ragas_compute(
        self,
        metric_name: str,
        question: str,
        answer: str,
        context: str | list[str],
        ground_truth: str,
    ) -> float:
        """RAGAS 官方 API 调用（统一包装）

        RAGAS 新版采用 evaluate() 批处理，此处构造单样本输入做近似计算。
        """
        from datasets import Dataset

        context_list = context if isinstance(context, list) else [context]

        data = {
            "question": [question],
            "contexts": [context_list],
            "answer": [answer],
            "ground_truth": [ground_truth] if ground_truth else [answer],
        }
        ds = Dataset.from_dict(data)

        # 指标映射
        metric_map = {
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "context_precision": context_precision,
            "context_recall": context_recall,
            "answer_correctness": answer_correctness,
            "answer_similarity": answer_similarity,
        }
        metric = metric_map.get(metric_name)
        if metric is None:
            return 0.0

        from ragas import evaluate

        result = evaluate(ds, metrics=[metric])
        return float(result[metric_name])
