"""Planning Evaluator - 任务拆解与计划生成评估器

用于评估 Agent 在复杂任务规划、依赖解算、逆序对分析等维度的性能表现。
工业特性：预编译正则状态机、现代 match-case 状态分发、强类型防御、纯函数零状态污染。
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Any

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema

# 工业级结构化日志
logger = logging.getLogger(__name__)

# ========================== 模块级预编译正则（防御 ReDoS 并极大提升高频调用性能） ==========================
_WHITESPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[\w\u4e00-\u9fff]+")

# 预定义高频停用词表（优化为 O(1) 查找的静态集合）
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "的",
        "了",
        "和",
        "是",
        "在",
        "我",
        "有",
        "与",
        "或",
        "就",
        "the",
        "a",
        "an",
        "is",
        "to",
        "of",
        "and",
        "in",
        "on",
        "at",
        "for",
    }
)


@EvaluatorFactory.register("planning")
class PlanningEvaluator(BaseEvaluator):
    """任务规划评估器 (2026 生产级高性能版)"""

    def __init__(self, client: Any | None = None):
        super().__init__(client)

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """评估主入口（采用现代 Python 3.10+ 模式匹配分发）"""
        action = self.get_payload_data(request, "action", "evaluate_plan")

        logger.debug(f"PlanningEvaluator 开始解析动作分发: {action}")

        try:
            match action:
                case "evaluate_plan":
                    return self._evaluate_plan(request)
                case "decomposition_quality":
                    return self._evaluate_decomposition(request)
                case "completeness":
                    return self._evaluate_completeness(request)
                case "ordering":
                    return self._evaluate_ordering(request)
                case "dependency_correctness":
                    return self._evaluate_dependency(request)
                case _:
                    return DomainResponse(
                        is_valid=False,
                        error=f"未知的动作请求类型: {action}",
                        status_code=400,
                    )
        except Exception as e:
            logger.exception(f"PlanningEvaluator 执行 {action} 期间发生未捕获的系统异常")
            return DomainResponse(
                is_valid=False,
                error=f"内部执行错误: {str(e)}",
                status_code=500,
            )

    def safe_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """安全评估向后兼容接口"""
        return self.evaluate(request)

    # ===================== 核心评估处理器 =====================

    def _evaluate_plan(self, request: EvaluationSchema) -> DomainResponse:
        """综合评估计划质量"""
        generated: list[str] = self.get_payload_data(request, "generated_plan", [])
        expected: list[str] = self.get_payload_data(request, "expected_plan", [])
        task: str = self.get_payload_data(request, "task", "")

        if not generated:
            return DomainResponse(
                is_valid=False,
                error="generated_plan 字段不可为空或缺少步骤数据",
                status_code=400,
            )

        # 多维度健康分并行解算
        scores = {
            "completeness": self._calc_completeness(generated, expected),
            "ordering": self._calc_ordering(generated, expected),
            "granularity": self._calc_granularity(generated, expected),
            "relevance": self._calc_relevance(generated, task),
            "redundancy_penalty": self._calc_redundancy(generated),
        }

        weights = {
            "completeness": 0.30,
            "ordering": 0.25,
            "granularity": 0.15,
            "relevance": 0.20,
            "redundancy_penalty": 0.10,
        }

        overall = sum(scores[k] * weights[k] for k in scores)

        return DomainResponse(
            is_valid=True,
            score=round(overall, 4),
            text="综合计划生成评估执行成功",
            data={
                "overall_score": round(overall, 4),
                "dimension_scores": scores,
                "weights": weights,
                "generated_step_count": len(generated),
                "expected_step_count": len(expected),
                "matched_steps": self._match_steps(generated, expected),
            },
            status_code=200,
        )

    def _evaluate_decomposition(self, request: EvaluationSchema) -> DomainResponse:
        """评估任务拆解质量"""
        generated: list[str] = self.get_payload_data(request, "generated_plan", [])
        expected: list[str] = self.get_payload_data(request, "expected_plan", [])

        granularity = self._calc_granularity(generated, expected)
        completeness = self._calc_completeness(generated, expected)
        decomposition_quality = (granularity + completeness) / 2

        return DomainResponse(
            is_valid=True,
            score=round(decomposition_quality, 4),
            text="任务拆解质量评估完成",
            data={
                "granularity_score": round(granularity, 4),
                "completeness_score": round(completeness, 4),
                "decomposition_quality": round(decomposition_quality, 4),
                "step_count_ratio": round(len(generated) / max(len(expected), 1), 4),
            },
            status_code=200,
        )

    def _evaluate_completeness(self, request: EvaluationSchema) -> DomainResponse:
        """评估计划完整性"""
        generated: list[str] = self.get_payload_data(request, "generated_plan", [])
        expected: list[str] = self.get_payload_data(request, "expected_plan", [])

        score = self._calc_completeness(generated, expected)
        matched = self._match_steps(generated, expected)

        # 提取高价值缺失步骤
        missing = [
            e for e in expected if not any(self._step_similarity(g, e) > 0.6 for g in generated)
        ]

        return DomainResponse(
            is_valid=True,
            score=round(score, 4),
            text="计划完整性检查完毕",
            data={
                "completeness_score": round(score, 4),
                "matched_count": len(matched),
                "expected_count": len(expected),
                "missing_steps": missing[:5],
            },
            status_code=200,
        )

    def _evaluate_ordering(self, request: EvaluationSchema) -> DomainResponse:
        """评估步骤顺序（时序合理性）"""
        generated: list[str] = self.get_payload_data(request, "generated_plan", [])
        expected: list[str] = self.get_payload_data(request, "expected_plan", [])

        score = self._calc_ordering(generated, expected)

        return DomainResponse(
            is_valid=True,
            score=round(score, 4),
            text="时序依赖及执行顺序正确性解算完成",
            data={
                "ordering_score": round(score, 4),
                "generated_sequence": generated,
                "expected_sequence": expected,
            },
            status_code=200,
        )

    def _evaluate_dependency(self, request: EvaluationSchema) -> DomainResponse:
        """评估强依赖关系正确性"""
        generated_deps: list[list[str]] = self.get_payload_data(
            request, "generated_dependencies", []
        )
        expected_deps: list[list[str]] = self.get_payload_data(request, "expected_dependencies", [])

        if not expected_deps:
            return DomainResponse(
                is_valid=True,
                score=1.0,
                text="标准用例中无需强制进行依赖关系拓扑验证",
                data={"dependency_score": 1.0, "message": "无需评估依赖关系"},
                status_code=200,
            )

        # 集合化处理确保拓扑顺序与方向无关性匹配
        expected_set = {tuple(sorted(d)) for d in expected_deps if len(d) >= 2}
        generated_set = {tuple(sorted(d)) for d in generated_deps if len(d) >= 2}

        if not expected_set:
            score = 1.0
        else:
            correct = len(expected_set & generated_set)
            score = correct / len(expected_set)

        return DomainResponse(
            is_valid=True,
            score=round(score, 4),
            text="显式依赖链图结构校验完成",
            data={
                "dependency_score": round(score, 4),
                "expected_dependencies": [list(d) for d in expected_set],
                "generated_dependencies": [list(d) for d in generated_set],
                "missing_dependencies": [list(d) for d in (expected_set - generated_set)],
            },
            status_code=200,
        )

    # ===================== 底层高性能解算算法 =====================

    def _calc_completeness(self, generated: list[str], expected: list[str]) -> float:
        """计算计划完整性（覆盖率）"""
        if not expected:
            return 1.0
        matched = self._match_steps(generated, expected)
        return len(matched) / len(expected)

    def _calc_ordering(self, generated: list[str], expected: list[str]) -> float:
        """基于逆序对数的 Kendall tau 距离高速解算算法"""
        if not generated or not expected:
            return 0.0

        positions: list[int] = []
        for exp_step in expected:
            best_idx = -1
            best_sim = 0.0
            for i, gen_step in enumerate(generated):
                sim = self._step_similarity(gen_step, exp_step)
                if sim > best_sim:
                    best_sim = sim
                    best_idx = i
            if best_sim > 0.6 and best_idx >= 0:
                positions.append(best_idx)

        if len(positions) < 2:
            return 1.0 if len(positions) == 1 else 0.0

        # 计算时序反转对数（Inversions）
        inversions = 0
        total_pairs = 0
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                total_pairs += 1
                if positions[i] > positions[j]:
                    inversions += 1

        if total_pairs == 0:
            return 1.0
        return max(0.0, 1.0 - inversions / total_pairs)

    def _calc_granularity(self, generated: list[str], expected: list[str]) -> float:
        """计算步骤拆解的粒度合理性得分"""
        if not expected:
            return 1.0
        ratio = len(generated) / len(expected)
        if 0.7 <= ratio <= 1.5:
            return 1.0
        elif 0.5 <= ratio <= 2.0:
            return 0.7
        else:
            return max(0.0, 0.5 - abs(ratio - 1.0) * 0.2)

    def _calc_relevance(self, generated: list[str], task: str) -> float:
        """计算生成的执行步骤与总任务目标的相关性"""
        if not task or not generated:
            return 0.0
        task_keywords = set(self._extract_keywords(task))
        if not task_keywords:
            return 0.5

        match_count = 0
        for step in generated:
            step_keywords = set(self._extract_keywords(step))
            if task_keywords & step_keywords:
                match_count += 1
        return match_count / len(generated)

    def _calc_redundancy(self, generated: list[str]) -> float:
        """计算计划间的步骤冗余惩罚系数"""
        if len(generated) <= 1:
            return 1.0

        similarities: list[float] = []
        for i in range(len(generated)):
            for j in range(i + 1, len(generated)):
                sim = self._step_similarity(generated[i], generated[j])
                similarities.append(sim)

        if not similarities:
            return 1.0

        avg_sim = sum(similarities) / len(similarities)
        # 温和惩罚公式升级：防范过度惩罚缺陷，让梯度分布更加科学合理
        return max(0.0, 1.0 - avg_sim * 0.5)

    def _match_steps(self, generated: list[str], expected: list[str]) -> list[str]:
        """寻找匹配成功的高语义相关步骤集合"""
        matched: list[str] = []
        for exp in expected:
            if any(self._step_similarity(gen, exp) > 0.6 for gen in generated):
                matched.append(exp)
        return matched

    def _step_similarity(self, step1: str, step2: str) -> float:
        """利用高性能预编译正则对两组文本做高维清洗，计算文本相似度比率"""
        if not step1 or not step2:
            return 0.0
        s1 = _WHITESPACE_RE.sub("", step1.lower())
        s2 = _WHITESPACE_RE.sub("", step2.lower())
        if s1 == s2:
            return 1.0
        return SequenceMatcher(None, s1, s2).ratio()

    def _extract_keywords(self, text: str) -> list[str]:
        """工业级极速分词与特征提取，避免高频调用下的重复正则编译"""
        words = _WORD_RE.findall(text.lower())
        return [w for w in words if len(w) > 1 and w not in _STOP_WORDS]
