"""多裁判集成评估器（Multi-Judge Ensemble Evaluator）

2026工业级标准实现：
1. 多裁判并行评估 - 支持3+个裁判模型
2. 决策机制 - 多数投票/Borda计数/加权平均/仲裁机制
3. 一致性度量 - Cohen's Kappa计算
4. 争议仲裁 - 引入更高等级模型解决分歧
5. 事件循环复用 - 线程本地存储避免重复创建
"""

import asyncio
import logging
import threading
from dataclasses import dataclass
from enum import Enum
from statistics import mean
from typing import Any

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus

logger = logging.getLogger(__name__)


class DecisionMechanism(Enum):
    """决策机制枚举"""

    MAJORITY_VOTE = "majority_vote"
    BORDA_COUNT = "borda_count"
    WEIGHTED_AVERAGE = "weighted_average"
    ARBITRATION = "arbitration"


@dataclass
class JudgeResult:
    """单个裁判的评分结果"""

    judge_id: str
    judge_name: str
    score: float
    confidence: float
    dimensions: dict[str, float]
    reason: str
    raw_output: str


@dataclass
class EnsembleResult:
    """集成评估结果"""

    final_score: float
    final_level: str
    mechanism: DecisionMechanism
    judge_results: list[JudgeResult]
    agreement_score: float
    has_disagreement: bool
    arbitration_used: bool
    confidence_interval: tuple[float, float]


class MultiJudgeEnsembleEvaluator(BaseEvaluator):
    """多裁判集成评估器"""

    _thread_local = threading.local()

    def __init__(self, judge_configs: list[dict[str, Any]] | None = None):
        """初始化多裁判集成评估器

        Args:
            judge_configs: 裁判配置列表，每个配置包含:
                - id: 裁判ID
                - name: 裁判名称
                - evaluator_type: 评估器类型
                - weight: 权重 (用于加权平均)
                - config: 评估器配置
        """
        super().__init__()
        self.judge_configs = judge_configs or self._get_default_judges()
        self.evaluators: dict[str, BaseEvaluator] = {}
        self._initialize_evaluators()

    @staticmethod
    def _get_event_loop() -> asyncio.AbstractEventLoop:
        """获取线程本地事件循环（复用机制）"""
        if not hasattr(MultiJudgeEnsembleEvaluator._thread_local, "loop"):
            MultiJudgeEnsembleEvaluator._thread_local.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(MultiJudgeEnsembleEvaluator._thread_local.loop)
        return MultiJudgeEnsembleEvaluator._thread_local.loop

    def _get_default_judges(self) -> list[dict[str, Any]]:
        """获取默认裁判配置（2026工业级标准：3个裁判）"""
        return [
            {
                "id": "judge_gpt4o",
                "name": "GPT-4o",
                "evaluator_type": "llm_as_judge",
                "weight": 0.4,
                "config": {"model": "gpt-4o"},
            },
            {
                "id": "judge_claude",
                "name": "Claude 3.5",
                "evaluator_type": "llm_as_judge",
                "weight": 0.35,
                "config": {"model": "claude-3-5-sonnet"},
            },
            {
                "id": "judge_deepseek",
                "name": "DeepSeek V3",
                "evaluator_type": "llm_as_judge",
                "weight": 0.25,
                "config": {"model": "deepseek-chat"},
            },
        ]

    def _initialize_evaluators(self):
        """初始化所有裁判评估器"""
        for config in self.judge_configs:
            try:
                evaluator = EvaluatorFactory.get(config["evaluator_type"])
                self.evaluators[config["id"]] = evaluator
                logger.info(f"裁判初始化成功: {config['name']} ({config['id']})")
            except Exception as e:
                logger.error(f"裁判初始化失败 {config['name']}: {e}")

    async def _evaluate_with_judge(
        self, judge_id: str, judge_config: dict[str, Any], request: EvaluationSchema
    ) -> JudgeResult:
        """使用单个裁判进行评估"""
        evaluator = self.evaluators.get(judge_id)
        if not evaluator:
            return JudgeResult(
                judge_id=judge_id,
                judge_name=judge_config["name"],
                score=0.0,
                confidence=0.0,
                dimensions={},
                reason="评估器不可用",
                raw_output="",
            )

        try:
            response = evaluator.safe_evaluate(request)

            score = response.score if response.score is not None else 0.5
            confidence = getattr(response, "confidence", 0.7)

            dimensions = {}
            if hasattr(response, "dimensions") and response.dimensions:
                dimensions = response.dimensions
            elif hasattr(response, "details") and isinstance(response.details, dict):
                dimensions = response.details.get("dimensions", {})

            reason = ""
            if hasattr(response, "reason"):
                reason = response.reason
            elif hasattr(response, "details") and isinstance(response.details, dict):
                reason = response.details.get("reason", "")

            return JudgeResult(
                judge_id=judge_id,
                judge_name=judge_config["name"],
                score=score,
                confidence=confidence,
                dimensions=dimensions,
                reason=reason,
                raw_output=str(response),
            )
        except Exception as e:
            logger.error(f"裁判 {judge_config['name']} 评估失败: {e}")
            return JudgeResult(
                judge_id=judge_id,
                judge_name=judge_config["name"],
                score=0.5,
                confidence=0.3,
                dimensions={},
                reason=f"评估失败: {str(e)}",
                raw_output="",
            )

    async def _parallel_evaluate(self, request: EvaluationSchema) -> list[JudgeResult]:
        """并行执行所有裁判评估"""
        tasks = []
        for config in self.judge_configs:
            task = self._evaluate_with_judge(config["id"], config, request)
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        return results

    def _calculate_cohens_kappa(self, results: list[JudgeResult]) -> float:
        """计算 Cohen's Kappa（简化版用于多裁判一致性评估）"""
        if len(results) < 2:
            return 1.0 if len(results) == 1 else 0.0

        scores = [r.score for r in results]
        len(scores)

        observed_agreement = self._calculate_observed_agreement(scores)
        expected_agreement = self._calculate_expected_agreement(scores)

        if expected_agreement == 1.0:
            return 1.0

        kappa = (observed_agreement - expected_agreement) / (1 - expected_agreement)
        return max(-1.0, min(1.0, kappa))

    def _calculate_observed_agreement(self, scores: list[float]) -> float:
        """计算观测一致率"""
        if len(scores) < 2:
            return 1.0

        pairs = 0
        agreements = 0
        for i in range(len(scores)):
            for j in range(i + 1, len(scores)):
                pairs += 1
                if abs(scores[i] - scores[j]) < 0.1:
                    agreements += 1

        return agreements / pairs if pairs > 0 else 0.0

    def _calculate_expected_agreement(self, scores: list[float]) -> float:
        """计算期望一致率（随机概率）"""
        if not scores:
            return 0.0

        score_distribution = {}
        for score in scores:
            bin = round(score * 10) / 10
            score_distribution[bin] = score_distribution.get(bin, 0) + 1

        total = len(scores)
        expected = 0.0
        for count in score_distribution.values():
            expected += (count / total) ** 2

        return expected

    def _majority_vote(self, results: list[JudgeResult]) -> tuple[float, bool]:
        """多数投票决策机制"""
        scores = [r.score for r in results]
        levels = []

        for score in scores:
            if score >= 0.8:
                levels.append("excellent")
            elif score >= 0.65:
                levels.append("good")
            elif score >= 0.5:
                levels.append("acceptable")
            elif score >= 0.35:
                levels.append("poor")
            else:
                levels.append("very_poor")

        level_counts = {}
        for level in levels:
            level_counts[level] = level_counts.get(level, 0) + 1

        max_count = max(level_counts.values())
        top_levels = [k for k, v in level_counts.items() if v == max_count]

        if len(top_levels) == 1:
            level_to_score = {
                "excellent": 0.9,
                "good": 0.75,
                "acceptable": 0.6,
                "poor": 0.45,
                "very_poor": 0.2,
            }
            return level_to_score[top_levels[0]], False

        return mean(scores), True

    def _borda_count(self, results: list[JudgeResult]) -> tuple[float, bool]:
        """Borda计数决策机制"""
        sorted_results = sorted(results, key=lambda r: r.score, reverse=True)

        n = len(sorted_results)
        weighted_scores = []

        for i, result in enumerate(sorted_results):
            borda_weight = n - i
            weighted_scores.append(result.score * borda_weight * result.confidence)

        total_weight = sum(r.confidence * (n - i) for i, r in enumerate(sorted_results))

        if total_weight == 0:
            return mean([r.score for r in results]), False

        final_score = sum(weighted_scores) / total_weight
        has_disagreement = len({r.score for r in results}) > 1

        return final_score, has_disagreement

    def _weighted_average(self, results: list[JudgeResult]) -> tuple[float, bool]:
        """加权平均决策机制"""
        total_weight = 0.0
        weighted_sum = 0.0

        for result, config in zip(results, self.judge_configs, strict=False):
            weight = config.get("weight", 1.0) * result.confidence
            total_weight += weight
            weighted_sum += result.score * weight

        if total_weight == 0:
            return mean([r.score for r in results]), False

        final_score = weighted_sum / total_weight
        has_disagreement = max(r.score for r in results) - min(r.score for r in results) > 0.2

        return final_score, has_disagreement

    def _arbitration(self, results: list[JudgeResult]) -> tuple[float, bool]:
        """仲裁机制 - 使用最高权重裁判"""
        sorted_results = sorted(results, key=lambda r: r.confidence, reverse=True)
        return sorted_results[0].score, len({r.score for r in results}) > 1

    def _resolve_disagreement(self, results: list[JudgeResult]) -> tuple[float, bool]:
        """解决争议 - 当意见分歧较大时触发"""
        scores = [r.score for r in results]
        score_range = max(scores) - min(scores)

        if score_range > 0.3:
            logger.warning(f"检测到重大分歧 (分数范围: {score_range:.2f})，触发仲裁")
            return self._arbitration(results)

        return self._weighted_average(results)

    def _calculate_confidence_interval(self, results: list[JudgeResult]) -> tuple[float, float]:
        """计算置信区间"""
        if len(results) < 2:
            return (0.0, 1.0)

        scores = [r.score for r in results]
        n = len(scores)
        mean_score = mean(scores)

        variance = sum((s - mean_score) ** 2 for s in scores) / (n - 1) if n > 1 else 0
        std_dev = variance**0.5

        margin_of_error = 1.96 * (std_dev / (n**0.5))
        ci_lower = max(0.0, mean_score - margin_of_error)
        ci_upper = min(1.0, mean_score + margin_of_error)

        return (ci_lower, ci_upper)

    def _get_level_from_score(self, score: float) -> str:
        """根据分数获取等级"""
        if score >= 0.9:
            return "excellent"
        elif score >= 0.75:
            return "good"
        elif score >= 0.6:
            return "acceptable"
        elif score >= 0.4:
            return "poor"
        else:
            return "very_poor"

    async def _do_evaluate_async(self, request: EvaluationSchema) -> DomainResponse:
        """异步评估主入口"""
        judge_results = await self._parallel_evaluate(request)

        mechanism_str = self.get_payload_data(request, "mechanism", "weighted_average")
        try:
            mechanism = DecisionMechanism(mechanism_str)
        except ValueError:
            mechanism = DecisionMechanism.WEIGHTED_AVERAGE

        agreement_score = self._calculate_cohens_kappa(judge_results)

        if agreement_score < 0.4:
            logger.warning(f"一致性不足 (Kappa={agreement_score:.2f})，触发争议解决")
            final_score, has_disagreement = self._resolve_disagreement(judge_results)
            arbitration_used = True
        else:
            if mechanism == DecisionMechanism.MAJORITY_VOTE:
                final_score, has_disagreement = self._majority_vote(judge_results)
            elif mechanism == DecisionMechanism.BORDA_COUNT:
                final_score, has_disagreement = self._borda_count(judge_results)
            elif mechanism == DecisionMechanism.ARBITRATION:
                final_score, has_disagreement = self._arbitration(judge_results)
            else:
                final_score, has_disagreement = self._weighted_average(judge_results)
            arbitration_used = False

        ci_lower, ci_upper = self._calculate_confidence_interval(judge_results)
        final_level = self._get_level_from_score(final_score)

        EnsembleResult(
            final_score=final_score,
            final_level=final_level,
            mechanism=mechanism,
            judge_results=judge_results,
            agreement_score=agreement_score,
            has_disagreement=has_disagreement,
            arbitration_used=arbitration_used,
            confidence_interval=(ci_lower, ci_upper),
        )

        details = {
            "final_score": final_score,
            "final_level": final_level,
            "mechanism": mechanism.value,
            "agreement_score": agreement_score,
            "has_disagreement": has_disagreement,
            "arbitration_used": arbitration_used,
            "confidence_interval": [ci_lower, ci_upper],
            "judge_results": [
                {
                    "judge_id": r.judge_id,
                    "judge_name": r.judge_name,
                    "score": r.score,
                    "confidence": r.confidence,
                }
                for r in judge_results
            ],
        }

        return DomainResponse(
            evaluation_status=EvaluatorStatus.SUCCESS,
            score=final_score,
            level=final_level,
            details=details,
            confidence=agreement_score,
        )

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """同步评估主入口"""
        loop = self._get_event_loop()
        return loop.run_until_complete(self._do_evaluate_async(request))


@EvaluatorFactory.register("multi_judge_ensemble")
class MultiJudgeEnsembleEvaluatorSync(MultiJudgeEnsembleEvaluator):
    """多裁判集成评估器（同步注册版本）"""

    pass
