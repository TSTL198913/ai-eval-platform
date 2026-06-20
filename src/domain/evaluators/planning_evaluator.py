"""
Planning Evaluator - 任务拆解与计划生成评估器

评估Agent在以下方面的能力：
- 任务拆解：将复杂任务分解为可执行的子目标
- 计划生成：制定合理的执行步骤
- 依赖管理：识别子任务之间的依赖关系
- 顺序正确性：评估子任务执行顺序的合理性
- 完整性：确保计划覆盖所有必要步骤
"""
import re
from difflib import SequenceMatcher
from typing import Any

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("planning")
class PlanningEvaluator:
    """任务规划评估器

    输入payload格式:
    {
        "action": "evaluate_plan",
        "task": "复杂任务描述",
        "generated_plan": ["步骤1", "步骤2", ...],   # Agent生成的计划
        "expected_plan": ["步骤1", "步骤2", ...],    # 期望的标准计划
        "dependencies": [["step1", "step2"], ...]    # 可选的依赖关系
    }
    """

    def __init__(self, client: Any | None = None):
        self.client = client

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        action = request.payload.get("action", "evaluate_plan")
        handler = {
            "evaluate_plan": self._evaluate_plan,
            "decomposition_quality": self._evaluate_decomposition,
            "completeness": self._evaluate_completeness,
            "ordering": self._evaluate_ordering,
            "dependency_correctness": self._evaluate_dependency,
        }.get(action)
        if handler is None:
            return DomainResponse(
                data={"is_valid": False, "error": f"Unknown action: {action}"},
                status_code=400,
            )
        try:
            return handler(request)
        except Exception as e:
            return DomainResponse(
                data={"is_valid": False, "error": str(e)},
                status_code=500,
            )

    def safe_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        return self.evaluate(request)

    # ===================== 核心评估方法 =====================

    def _evaluate_plan(self, request: EvaluationSchema) -> DomainResponse:
        """综合评估计划质量"""
        generated = self._get_payload(request, "generated_plan", [])
        expected = self._get_payload(request, "expected_plan", [])
        task = self._get_payload(request, "task", "")

        if not generated:
            return DomainResponse(
                data={"is_valid": False, "error": "generated_plan不能为空"},
                status_code=400,
            )

        # 多维度评分
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
            data={
                "is_valid": True,
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
        generated = self._get_payload(request, "generated_plan", [])
        expected = self._get_payload(request, "expected_plan", [])

        # 拆解质量 = 步骤粒度合理性
        granularity = self._calc_granularity(generated, expected)
        # 拆解充分度
        completeness = self._calc_completeness(generated, expected)

        return DomainResponse(
            data={
                "is_valid": True,
                "granularity_score": round(granularity, 4),
                "completeness_score": round(completeness, 4),
                "decomposition_quality": round((granularity + completeness) / 2, 4),
                "step_count_ratio": len(generated) / max(len(expected), 1),
            },
            status_code=200,
        )

    def _evaluate_completeness(self, request: EvaluationSchema) -> DomainResponse:
        """评估计划完整性"""
        generated = self._get_payload(request, "generated_plan", [])
        expected = self._get_payload(request, "expected_plan", [])

        score = self._calc_completeness(generated, expected)
        matched = self._match_steps(generated, expected)
        missing = [e for e in expected if not any(self._step_similarity(g, e) > 0.6 for g in generated)]

        return DomainResponse(
            data={
                "is_valid": True,
                "completeness_score": round(score, 4),
                "matched_count": len(matched),
                "expected_count": len(expected),
                "missing_steps": missing[:5],
            },
            status_code=200,
        )

    def _evaluate_ordering(self, request: EvaluationSchema) -> DomainResponse:
        """评估步骤顺序"""
        generated = self._get_payload(request, "generated_plan", [])
        expected = self._get_payload(request, "expected_plan", [])

        score = self._calc_ordering(generated, expected)
        return DomainResponse(
            data={
                "is_valid": True,
                "ordering_score": round(score, 4),
                "generated_sequence": generated,
                "expected_sequence": expected,
            },
            status_code=200,
        )

    def _evaluate_dependency(self, request: EvaluationSchema) -> DomainResponse:
        """评估依赖关系正确性"""
        generated_deps = self._get_payload(request, "generated_dependencies", [])
        expected_deps = self._get_payload(request, "expected_dependencies", [])

        if not expected_deps:
            return DomainResponse(
                data={"is_valid": True, "score": 1.0, "message": "无需评估依赖关系"},
                status_code=200,
            )

        # 计算依赖关系的匹配度
        expected_set = {tuple(sorted(d)) for d in expected_deps}
        generated_set = {tuple(sorted(d)) for d in generated_deps}

        if not expected_set:
            score = 1.0
        else:
            correct = len(expected_set & generated_set)
            score = correct / len(expected_set)

        return DomainResponse(
            data={
                "is_valid": True,
                "dependency_score": round(score, 4),
                "expected_dependencies": list(expected_set),
                "generated_dependencies": list(generated_set),
                "missing_dependencies": list(expected_set - generated_set),
            },
            status_code=200,
        )

    # ===================== 评分算法 =====================

    def _calc_completeness(self, generated: list[str], expected: list[str]) -> float:
        """计算计划完整性（覆盖度）"""
        if not expected:
            return 1.0
        matched = self._match_steps(generated, expected)
        return len(matched) / len(expected)

    def _calc_ordering(self, generated: list[str], expected: list[str]) -> float:
        """计算步骤顺序正确性（Kendall tau距离的简化版）"""
        if not generated or not expected:
            return 0.0
        # 找到generated中匹配expected步骤的位置
        positions = []
        for exp_step in expected:
            best_idx = -1
            best_sim = 0
            for i, gen_step in enumerate(generated):
                sim = self._step_similarity(gen_step, exp_step)
                if sim > best_sim:
                    best_sim = sim
                    best_idx = i
            if best_sim > 0.6 and best_idx >= 0:
                positions.append(best_idx)
        if len(positions) < 2:
            return 1.0 if len(positions) == 1 else 0.0
        # 计算逆序对数
        inversions = 0
        total_pairs = 0
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                total_pairs += 1
                if positions[i] > positions[j]:
                    inversions += 1
        if total_pairs == 0:
            return 1.0
        return 1.0 - inversions / total_pairs

    def _calc_granularity(self, generated: list[str], expected: list[str]) -> float:
        """计算步骤粒度合理性"""
        if not expected:
            return 1.0
        # 理想粒度：生成步骤数 / 期望步骤数 接近 1.0
        ratio = len(generated) / len(expected)
        if 0.7 <= ratio <= 1.5:
            return 1.0
        elif 0.5 <= ratio <= 2.0:
            return 0.7
        else:
            return max(0.0, 0.5 - abs(ratio - 1.0) * 0.2)

    def _calc_relevance(self, generated: list[str], task: str) -> float:
        """计算计划与任务的相关性"""
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
        """计算冗余度惩罚（越低分表示冗余越少）"""
        if len(generated) <= 1:
            return 1.0
        # 步骤间的相似度
        similarities = []
        for i in range(len(generated)):
            for j in range(i + 1, len(generated)):
                sim = self._step_similarity(generated[i], generated[j])
                similarities.append(sim)
        if not similarities:
            return 1.0
        avg_sim = sum(similarities) / len(similarities)
        return max(0.0, 1.0 - avg_sim * 2)

    def _match_steps(self, generated: list[str], expected: list[str]) -> list[str]:
        """匹配生成步骤和期望步骤"""
        matched = []
        for exp in expected:
            if any(self._step_similarity(gen, exp) > 0.6 for gen in generated):
                matched.append(exp)
        return matched

    def _step_similarity(self, step1: str, step2: str) -> float:
        """计算两个步骤的相似度"""
        if not step1 or not step2:
            return 0.0
        s1 = re.sub(r"\s+", "", step1.lower())
        s2 = re.sub(r"\s+", "", step2.lower())
        if s1 == s2:
            return 1.0
        # 使用SequenceMatcher计算文本相似度
        return SequenceMatcher(None, s1, s2).ratio()

    def _extract_keywords(self, text: str) -> list[str]:
        """提取关键词（简单实现）"""
        # 移除标点符号并分词
        words = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
        # 过滤停用词
        stop_words = {"的", "了", "和", "是", "在", "我", "有", "the", "a", "an", "is", "to", "of", "and"}
        return [w for w in words if len(w) > 1 and w not in stop_words]

    @staticmethod
    def _get_payload(request: EvaluationSchema, key: str, default: Any = None) -> Any:
        if hasattr(request, "payload") and request.payload:
            return request.payload.get(key, default)
        return default
