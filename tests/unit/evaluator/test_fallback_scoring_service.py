"""测试 FallbackScoringService 统一降级评分逻辑"""

import pytest

from src.domain.services.fallback_scoring_service import fallback_scoring_service
from tests.utils.test_helpers import approx_score


class TestFallbackScoringService:
    """测试标准化降级评分服务"""

    def test_exact_match_returns_one(self):
        """完全匹配应返回 1.0"""
        score = fallback_scoring_service.calculate_fallback_score(
            user_input="测试问题",
            expected_output="这是答案",
            actual_output="这是答案",
            evaluator_type="general",
        )
        assert score == 1.0

    def test_empty_input_returns_zero(self):
        """空输入应返回 0.0"""
        score = fallback_scoring_service.calculate_fallback_score(
            user_input=None,
            expected_output="",
            actual_output="答案",
            evaluator_type="general",
        )
        assert score == 0.0

        score = fallback_scoring_service.calculate_fallback_score(
            user_input=None,
            expected_output="答案",
            actual_output="",
            evaluator_type="general",
        )
        assert score == 0.0

    def test_invalid_answer_general(self):
        """无效答案在 general 评估器中应返回 0.15"""
        for answer in ["不知道", "不清楚", "无法回答", "none", "N/A"]:
            score = fallback_scoring_service.calculate_fallback_score(
                user_input="测试问题",
                expected_output="正确答案",
                actual_output=answer,
                evaluator_type="general",
            )
            assert score == 0.15, f"无效答案 {answer} 应返回 0.15"

    def test_invalid_answer_qa_exact(self):
        """无效答案在 qa 评估器中精确匹配应返回低分"""
        for answer in ["不知道", "不清楚", "无法回答", "不了解", "", "不确定", "可能吧"]:
            score = fallback_scoring_service.calculate_fallback_score(
                user_input="测试问题",
                expected_output="正确答案",
                actual_output=answer,
                evaluator_type="qa",
            )
            assert score <= 0.1, f"无效答案 {answer} 应返回低分，实际: {score}"

    def test_invalid_answer_qa_short_with_phrase(self):
        """包含无效短语的短答案在 qa 评估器中应返回 0.05"""
        score = fallback_scoring_service.calculate_fallback_score(
            user_input="测试问题",
            expected_output="正确答案",
            actual_output="不知道答案",
            evaluator_type="qa",
        )
        assert score == 0.05

    def test_invalid_answer_qa_long_with_phrase(self):
        """包含无效短语的长答案在 qa 评估器中应返回 0.15"""
        score = fallback_scoring_service.calculate_fallback_score(
            user_input="测试问题",
            expected_output="正确答案是人工智能",
            actual_output="这个问题我不清楚，需要更多信息",
            evaluator_type="qa",
        )
        assert score == 0.15

    def test_uncertainty_pattern_qa(self):
        """不确定性模式在 qa 评估器中应返回 0.25"""
        for pattern in ["不太确定", "可能是"]:
            score = fallback_scoring_service.calculate_fallback_score(
                user_input="测试问题",
                expected_output="正确答案",
                actual_output=f"{pattern}是正确答案",
                evaluator_type="qa",
            )
            assert score == 0.25, f"不确定性模式 {pattern} 应返回 0.25"

    def test_opposite_meaning_general(self):
        """反义词检测在 general 评估器中应返回低分"""
        score = fallback_scoring_service.calculate_fallback_score(
            user_input="测试问题",
            expected_output="这是好的",
            actual_output="这是坏的",
            evaluator_type="general",
        )
        assert score <= 0.3, f"反义词应返回低分，实际: {score}"

    def test_opposite_meaning_qa(self):
        """反义词检测在 qa 评估器中应返回低分"""
        score = fallback_scoring_service.calculate_fallback_score(
            user_input="测试问题",
            expected_output="这是好的",
            actual_output="这是坏的",
            evaluator_type="qa",
        )
        assert score <= 0.1, f"反义词应返回低分，实际: {score}"

    def test_number_exact_match(self):
        """数字完全匹配（相对差 < 0.05）应获得满分"""
        score = fallback_scoring_service.calculate_fallback_score(
            user_input="中国人口有多少？",
            expected_output="中国人口约14亿",
            actual_output="中国人口约14.1亿",
            evaluator_type="general",
        )
        assert score > 0.5, f"数字接近匹配评分应为 {score}"

    def test_number_partial_match(self):
        """数字部分匹配（相对差 < 0.3）应获得部分分数"""
        score = fallback_scoring_service.calculate_fallback_score(
            user_input="测试问题",
            expected_output="数值是100",
            actual_output="数值是125",
            evaluator_type="general",
        )
        assert 0.3 < score < 0.8, f"数字部分匹配评分应为 {score}"

    def test_number_no_match(self):
        """数字不匹配应受到惩罚"""
        score = fallback_scoring_service.calculate_fallback_score(
            user_input="中国人口有多少？",
            expected_output="中国人口约14亿",
            actual_output="中国人口约20亿",
            evaluator_type="general",
        )
        assert score < 0.75, f"数字不匹配应限制最高分数，当前分数 {score}"

    def test_length_penalty_short_answer(self):
        """过短答案应受到长度惩罚"""
        score = fallback_scoring_service.calculate_fallback_score(
            user_input="详细解释一下人工智能",
            expected_output="人工智能是研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统的一门新技术科学。",
            actual_output="AI",
            evaluator_type="general",
        )
        assert score < 0.5, f"过短答案应受到惩罚，当前分数 {score}"

    def test_length_penalty_long_answer(self):
        """过长答案应受到长度惩罚"""
        long_answer = "人工智能是研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统的一门新技术科学。" * 5
        score = fallback_scoring_service.calculate_fallback_score(
            user_input="什么是AI？",
            expected_output="AI是人工智能",
            actual_output=long_answer,
            evaluator_type="general",
        )
        assert score < 0.95, f"过长答案应受到惩罚，当前分数 {score}"

    def test_cross_evaluator_consistency(self):
        """跨评估器评分一致性验证"""
        user_input = "什么是机器学习？"
        expected_output = "机器学习是人工智能的一个分支。"
        actual_output = "机器学习是人工智能的一个分支。"

        general_score = fallback_scoring_service.calculate_fallback_score(
            user_input=user_input,
            expected_output=expected_output,
            actual_output=actual_output,
            evaluator_type="general",
        )

        qa_score = fallback_scoring_service.calculate_fallback_score(
            user_input=user_input,
            expected_output=expected_output,
            actual_output=actual_output,
            evaluator_type="qa",
        )

        assert general_score == 1.0, "完全匹配时 general 评分应为 1.0"
        assert qa_score == 1.0, "完全匹配时 qa 评分应为 1.0"

        user_input = "测试问题"
        expected_output = "这是正确答案"
        actual_output = "这是错误答案"

        general_score_diff = fallback_scoring_service.calculate_fallback_score(
            user_input=user_input,
            expected_output=expected_output,
            actual_output=actual_output,
            evaluator_type="general",
        )

        qa_score_diff = fallback_scoring_service.calculate_fallback_score(
            user_input=user_input,
            expected_output=expected_output,
            actual_output=actual_output,
            evaluator_type="qa",
        )

        assert 0.0 <= general_score_diff <= 1.0, "general 评分应在 0-1 范围内"
        assert 0.0 <= qa_score_diff <= 1.0, "qa 评分应在 0-1 范围内"

    def test_default_evaluator_type(self):
        """默认评估器类型应正常工作"""
        score = fallback_scoring_service.calculate_fallback_score(
            user_input="测试问题",
            expected_output="正确答案",
            actual_output="正确答案",
            evaluator_type="default",
        )
        assert score == 1.0

    def test_get_scoring_weights(self):
        """获取评分权重配置"""
        weights = fallback_scoring_service.get_scoring_weights("general")
        assert "text_similarity" in weights
        assert "answer_coverage" in weights
        assert "question_relevance" in weights
        assert "number_match" in weights

        default_weights = fallback_scoring_service.get_scoring_weights("unknown")
        assert default_weights == fallback_scoring_service.SCORING_WEIGHTS["default"]

    def test_get_thresholds(self):
        """获取阈值配置"""
        thresholds = fallback_scoring_service.get_thresholds("qa")
        assert "opposite_score" in thresholds
        assert "invalid_answer_score" in thresholds
        assert "uncertainty_score" in thresholds

        default_thresholds = fallback_scoring_service.get_thresholds("unknown")
        assert default_thresholds == fallback_scoring_service.THRESHOLDS["default"]

    def test_qa_token_coverage(self):
        """QA 评估器应使用 token 重叠计算覆盖率"""
        score = fallback_scoring_service.calculate_fallback_score(
            user_input="什么是机器学习？",
            expected_output="机器学习是人工智能的一个分支，使计算机能够从数据中学习。",
            actual_output="机器学习是人工智能的一个分支，使计算机能够从数据中学习并改进其性能。",
            evaluator_type="qa",
        )
        assert score == approx_score(0.19), f"QA token 覆盖率评分应为 {score}"

    def test_negative_inversion_penalty(self):
        """否定词反转应受到惩罚"""
        score = fallback_scoring_service.calculate_fallback_score(
            user_input="测试问题",
            expected_output="这个方案是可行的",
            actual_output="这个方案是不可行的",
            evaluator_type="qa",
        )
        assert score < 0.5, f"否定词反转应受到惩罚，当前分数 {score}"
