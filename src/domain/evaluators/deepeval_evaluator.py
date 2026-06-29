"""
🎯 src/domain/evaluators/deepeval_evaluator.py
DeepEval 适配器 - 将 DeepEval 框架的核心指标封装为统一评估器

DeepEval 核心指标：
- Answer Relevancy: 答案与问题相关性
- Faithfulness: 答案对上下文忠实度（无幻觉）
- Contextual Precision: 上下文精度
- Contextual Recall: 上下文召回
- Contextual Relevancy: 上下文相关性
- Bias: 偏见检测
- Toxicity: 毒性检测
- Hallucination: 幻觉检测

设计要点：
1. 适配器模式 - DeepEval 缺失时降级到本地规则实现
2. 统一接口 - 与 BaseEvaluator 协议完全兼容
3. 故障隔离 - 子指标失败不影响整体输出
"""

import logging
import re
from typing import Any

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)

# 探测 DeepEval 是否可用
try:
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        BiasMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        ContextualRelevancyMetric,
        FaithfulnessMetric,
        HallucinationMetric,
        ToxicityMetric,
    )

    # from deepeval.test_case import LLMTestCase  # unused

    HAS_DEEPEVAL = True
except ImportError:
    HAS_DEEPEVAL = False
    logger.warning("⚠️ 未安装 deepeval，DeepEval 评估器将降级到本地实现")


# ==================== 本地降级实现 ====================

# 偏见敏感词（精简版，DeepEval 缺失时使用）
_BIAS_WORDS = {
    "男性都",
    "女性都",
    "老人都",
    "年轻人都",
    "穷人都",
    "富人都",
    "男人不",
    "女人不",
    "北方人",
    "南方人",
    "men always",
    "women always",
    "old people",
    "young people",
    "all men",
    "all women",
    "all poor",
    "all rich",
}

# 毒性词（精简版）
_TOXICITY_WORDS = {
    "stupid",
    "idiot",
    "moron",
    "dumb",
    "hate you",
    "kill yourself",
    "蠢",
    "笨",
    "废物",
    "去死",
    "滚",
    "垃圾",
    "智障",
}

# 幻觉标记：答案中包含"我不知道/无法"时反而说明忠实度高
_HEDGING_WORDS = {
    "可能",
    "也许",
    "或许",
    "不确定",
    "不知道",
    "无法",
    "没有信息",
    "may",
    "might",
    "perhaps",
    "possibly",
    "i don't know",
    "i'm not sure",
}


def _local_answer_relevancy(question: str, answer: str) -> float:
    """答案相关性 - 基于关键词重合"""
    if not question or not answer:
        return 0.0
    q_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", question.lower()))
    a_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", answer.lower()))
    if not q_tokens or not a_tokens:
        return 0.0
    overlap = q_tokens & a_tokens
    return min(1.0, len(overlap) / max(1, len(q_tokens)))


def _local_faithfulness(answer: str, context: str) -> float:
    """忠实度 - 答案是否能在 context 中找到支撑"""
    if not answer or not context:
        return 0.0
    a_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", answer.lower()))
    c_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", context.lower()))
    if not a_tokens:
        return 0.0
    overlap = a_tokens & c_tokens
    return min(1.0, len(overlap) / len(a_tokens))


def _local_contextual_precision(context: list[str], answer: str) -> float:
    """上下文精度 - 相关 context 的占比"""
    if not context:
        return 0.0
    relevant = sum(1 for ctx in context if _local_faithfulness(answer, ctx) > 0.3)
    return relevant / len(context)


def _local_contextual_recall(context: list[str], ground_truth: str) -> float:
    """上下文召回 - ground_truth 信息是否被 context 覆盖"""
    if not context or not ground_truth:
        return 0.0
    gt_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", ground_truth.lower()))
    if not gt_tokens:
        return 0.0
    all_ctx_tokens: set[str] = set()
    for ctx in context:
        all_ctx_tokens |= set(re.findall(r"[\w\u4e00-\u9fff]+", ctx.lower()))
    overlap = gt_tokens & all_ctx_tokens
    return min(1.0, len(overlap) / len(gt_tokens))


def _local_contextual_relevancy(context: list[str], question: str) -> float:
    """上下文相关性 - context 与问题的相关度"""
    if not context or not question:
        return 0.0
    q_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", question.lower()))
    if not q_tokens:
        return 0.0

    scores = []
    for ctx in context:
        c_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", ctx.lower()))
        if not c_tokens:
            scores.append(0.0)
            continue
        overlap = q_tokens & c_tokens
        scores.append(min(1.0, len(overlap) / len(q_tokens)))
    return sum(scores) / len(scores) if scores else 0.0


def _local_bias(text: str) -> float:
    """偏见检测 - 0 表示无偏见，1 表示高偏见"""
    if not text:
        return 0.0
    text_lower = text.lower()
    matched = sum(1 for word in _BIAS_WORDS if word in text_lower)
    return min(1.0, matched * 0.4)


def _local_toxicity(text: str) -> float:
    """毒性检测 - 0 表示无毒，1 表示高毒"""
    if not text:
        return 0.0
    text_lower = text.lower()
    matched = sum(1 for word in _TOXICITY_WORDS if word in text_lower)
    return min(1.0, matched * 0.5)


def _local_hallucination(answer: str, context: str) -> float:
    """幻觉检测 - 答案中无法被 context 支撑的 token 比例"""
    if not answer:
        return 0.0
    if not context:
        return 1.0  # 没有上下文时所有信息都可视为幻觉

    a_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", answer.lower()))
    c_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", context.lower()))

    if not a_tokens:
        return 0.0

    # 剔除 hedging 词的影响
    answer_hedging = sum(1 for w in _HEDGING_WORDS if w in answer.lower())

    unsupported = a_tokens - c_tokens
    # 容忍 1-2 个 hedging 词
    hallucination_score = len(unsupported) / len(a_tokens)
    if answer_hedging > 0:
        hallucination_score *= 0.7  # 有 hedging 词时降低幻觉分数

    return min(1.0, hallucination_score)


# ==================== 评估器实现 ====================


@EvaluatorFactory.register("deepeval")
class DeepEvalEvaluator(BaseEvaluator):
    """DeepEval 综合评估器（适配器模式）

    payload 字段约定：
    - question: 用户问题
    - context: 检索上下文（字符串或字符串列表）
    - answer / actual_output: 模型实际输出
    - ground_truth / expected_output: 标准答案
    - metrics: 要计算的指标列表

    返回的 score 在 data['metrics'] 中以 0-1 表示，越高越好；
    偏见/毒性/幻觉等负面指标会被反转（1 - raw_score）以保持"越高越好"语义一致。
    """

    DEFAULT_METRICS = [
        "answer_relevancy",
        "faithfulness",
        "contextual_precision",
        "contextual_recall",
        "contextual_relevancy",
        "bias",
        "toxicity",
        "hallucination",
    ]

    # 负面指标（越低越好），需要反转
    NEGATIVE_METRICS = {"bias", "toxicity", "hallucination"}

    def __init__(self, client: Any | None = None) -> None:
        super().__init__(client)

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        # 1. 提取数据
        question = self.get_input_text(request)
        actual_output = self.get_payload_data(request, "actual_output") or self.get_payload_data(
            request, "answer", ""
        )
        context = self.get_payload_data(request, "context", "")
        expected_output = self.get_payload_data(
            request, "expected_output"
        ) or self.get_payload_data(request, "ground_truth", "")
        metrics_to_run = self.get_payload_data(request, "metrics", self.DEFAULT_METRICS)

        if not actual_output:
            return self.create_error_response(
                error_message="actual_output/answer 不能为空",
                error_code="MISSING_ANSWER",
            )

        # 2. 计算
        context_list = context if isinstance(context, list) else ([context] if context else [])
        context_str = " ".join(context_list) if context_list else ""

        results: dict[str, dict[str, Any]] = {}
        scores: list[float] = []
        used_implementation = "deepeval" if HAS_DEEPEVAL else "local"

        for metric_name in metrics_to_run:
            try:
                raw_score = self._compute_metric(
                    metric_name, question, actual_output, context_list, context_str, expected_output
                )
                # 负面指标反转：raw_score 越低越好，转换后越高越好
                final_score = (
                    (1.0 - raw_score) if metric_name in self.NEGATIVE_METRICS else raw_score
                )
                results[metric_name] = {
                    "raw_score": round(raw_score, 4),
                    "score": round(final_score, 4),
                    "direction": "negative" if metric_name in self.NEGATIVE_METRICS else "positive",
                    "implementation": used_implementation,
                }
                scores.append(final_score)
            except Exception as e:
                logger.warning(f"DeepEval 指标 {metric_name} 计算失败: {e}")
                results[metric_name] = {
                    "score": 0.0,
                    "error": str(e),
                    "implementation": used_implementation,
                }

        composite_score = sum(scores) / len(scores) if scores else 0.0

        return self.create_success_response(
            text=f"DeepEval 评估完成（实现: {used_implementation}）",
            score=round(composite_score, 4),
            data={
                "question": question,
                "actual_output": actual_output,
                "expected_output": expected_output,
                "metrics": results,
                "composite_score": round(composite_score, 4),
                "implementation": used_implementation,
                "has_deepeval": HAS_DEEPEVAL,
            },
        )

    def _compute_metric(
        self,
        metric_name: str,
        question: str,
        answer: str,
        context_list: list[str],
        context_str: str,
        ground_truth: str,
    ) -> float:
        # DeepEval 优先
        if HAS_DEEPEVAL:
            try:
                return self._deepeval_compute(
                    metric_name, question, answer, context_list, ground_truth
                )
            except Exception as e:
                logger.warning(f"DeepEval 官方实现失败，降级到本地: {e}")

        # 本地降级
        if metric_name == "answer_relevancy":
            return _local_answer_relevancy(question, answer)
        if metric_name == "faithfulness":
            return _local_faithfulness(answer, context_str)
        if metric_name == "contextual_precision":
            return _local_contextual_precision(context_list, answer)
        if metric_name == "contextual_recall":
            return _local_contextual_recall(context_list, ground_truth)
        if metric_name == "contextual_relevancy":
            return _local_contextual_relevancy(context_list, question)
        if metric_name == "bias":
            return _local_bias(answer)
        if metric_name == "toxicity":
            return _local_toxicity(answer)
        if metric_name == "hallucination":
            return _local_hallucination(answer, context_str)
        return 0.0

    def _deepeval_compute(
        self,
        metric_name: str,
        question: str,
        answer: str,
        context_list: list[str],
        ground_truth: str,
    ) -> float:
        """DeepEval 官方 API 调用"""
        from deepeval.test_case import LLMTestCase

        test_case = LLMTestCase(
            input=question,
            actual_output=answer,
            expected_output=ground_truth,
            context=context_list,
            retrieval_context=context_list,
        )

        metric_map = {
            "answer_relevancy": AnswerRelevancyMetric,
            "faithfulness": FaithfulnessMetric,
            "contextual_precision": ContextualPrecisionMetric,
            "contextual_recall": ContextualRecallMetric,
            "contextual_relevancy": ContextualRelevancyMetric,
            "bias": BiasMetric,
            "toxicity": ToxicityMetric,
            "hallucination": HallucinationMetric,
        }

        metric_cls = metric_map.get(metric_name)
        if metric_cls is None:
            return 0.0

        metric = metric_cls()
        metric.measure(test_case)
        # DeepEval 返回 0-1 之间的分数
        return float(metric.score)
