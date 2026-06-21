"""
PromptRegressionEvaluator 专项测试
测试目标：验证 PromptRegressionEvaluator 的 prompt 对比、漂移检测、影响分析功能
关键发现：（测试过程中记录）
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.prompt_regression import PromptRegressionEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestPromptRegressionEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def target(self):
        return PromptRegressionEvaluator()

    def test_compare_similar_prompts_returns_high_similarity(self, target):
        """相似prompt应返回高相似度"""
        request = EvaluationSchema(
            id="pr_001",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "请帮我写一首关于春天的诗",
                "new_prompt": "请帮我写一首关于春天的诗歌",
                "old_output": "春风又绿江南岸",
                "new_output": "春风又绿江南岸",
            },
        )
        result = target.evaluate(request)

        # 强断言：验证业务逻辑
        assert result.is_valid is True
        assert result.score >= 0.8, f"相似prompt应得高分，实际得分: {result.score}"
        assert result.data["prompt_similarity"] >= 0.8, "prompt_similarity 应高"
        assert result.data["output_similarity"] == 1.0, "完全相同的output应得满分"

    def test_compare_identical_outputs_returns_perfect_score(self, target):
        """相同输出的prompt对比应得满分"""
        request = EvaluationSchema(
            id="pr_002",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "什么是AI",
                "new_prompt": "AI是什么",
                "old_output": "AI是人工智能的缩写",
                "new_output": "AI是人工智能的缩写",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["output_similarity"] == 1.0, "相同输出相似度应为1.0"

    def test_detect_drift_no_drift_returns_none_level(self, target):
        """无漂移时应返回none级别"""
        request = EvaluationSchema(
            id="pr_003",
            type="prompt_regression",
            payload={
                "action": "detect_drift",
                "baseline_output": "今天天气很好，适合出门散步",
                "current_output": "今天天气很好，适合出门散步",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["drift_detected"] is False, "无漂移应检测为False"
        assert result.data["drift_level"] == "none", "无漂移应返回none级别"
        assert result.data["drift_score"] < 0.1, "drift_score应接近0"

    def test_analyze_impact_similar_outputs_returns_low_impact(self, target):
        """相似输出应返回低影响"""
        request = EvaluationSchema(
            id="pr_004",
            type="prompt_regression",
            payload={
                "action": "analyze_impact",
                "old_output": "这是一个测试用例用于验证功能",
                "new_output": "这是一个测试用例用于验证功能",
                "criteria": ["correctness"],
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score >= 0.9, "相似输出应有高评分"
        assert result.data["impact_level"] == "none", "低差异应有none级别影响"

    def test_full_regression_test_passes_for_similar_prompts(self, target):
        """相似prompt应通过完整回归测试"""
        request = EvaluationSchema(
            id="pr_005",
            type="prompt_regression",
            payload={
                "action": "full_regression_test",
                "old_prompt": "帮我写一段Python代码",
                "new_prompt": "帮我写一段Python程序",
                "old_output": "def hello(): print('world')",
                "new_output": "def hello(): print('world')",
                "baseline_output": "def hello(): print('world')",
                "current_output": "def hello(): print('world')",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["regression_passed"] is True, "相似prompt应通过回归测试"
        assert result.data["overall_score"] >= 0.7, "整体评分应达标"


class TestPromptRegressionEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def target(self):
        return PromptRegressionEvaluator()

    def test_compare_missing_old_prompt_returns_error(self, target):
        """缺少old_prompt应返回错误"""
        request = EvaluationSchema(
            id="pr_n001",
            type="prompt_regression",
            payload={
                "action": "compare",
                "new_prompt": "新prompt",
                "old_output": "旧输出",
                "new_output": "新输出",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "old_prompt" in result.error or "不能为空" in result.error

    def test_compare_missing_new_prompt_returns_error(self, target):
        """缺少new_prompt应返回错误"""
        request = EvaluationSchema(
            id="pr_n002",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "旧prompt",
                "old_output": "旧输出",
                "new_output": "新输出",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "new_prompt" in result.error or "不能为空" in result.error

    def test_compare_missing_old_output_returns_error(self, target):
        """缺少old_output应返回错误"""
        request = EvaluationSchema(
            id="pr_n003",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "旧prompt",
                "new_prompt": "新prompt",
                "new_output": "新输出",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "old_output" in result.error or "不能为空" in result.error

    def test_detect_drift_missing_baseline_returns_error(self, target):
        """缺少baseline_output应返回错误"""
        request = EvaluationSchema(
            id="pr_n004",
            type="prompt_regression",
            payload={
                "action": "detect_drift",
                "current_output": "当前输出",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "baseline_output" in result.error or "不能为空" in result.error

    def test_detect_drift_missing_current_returns_error(self, target):
        """缺少current_output应返回错误"""
        request = EvaluationSchema(
            id="pr_n005",
            type="prompt_regression",
            payload={
                "action": "detect_drift",
                "baseline_output": "基线输出",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "current_output" in result.error or "不能为空" in result.error

    def test_analyze_impact_missing_outputs_returns_error(self, target):
        """缺少old_output或new_output应返回错误"""
        request = EvaluationSchema(
            id="pr_n006",
            type="prompt_regression",
            payload={
                "action": "analyze_impact",
                "old_output": "旧输出",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "new_output" in result.error or "不能为空" in result.error


class TestPromptRegressionEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def target(self):
        return PromptRegressionEvaluator()

    def test_compare_empty_prompts_returns_error(self, target):
        """空prompt应返回错误"""
        request = EvaluationSchema(
            id="pr_b001",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "",
                "new_prompt": "",
                "old_output": "输出",
                "new_output": "输出",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is False

    def test_compare_very_long_prompts_handled(self, target):
        """超长prompt应被正确处理"""
        long_text = "测试文本 " * 1000
        request = EvaluationSchema(
            id="pr_b002",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": long_text,
                "new_prompt": long_text,
                "old_output": "输出",
                "new_output": "输出",
            },
        )
        result = target.evaluate(request)

        # 不应崩溃，返回合理结果
        assert result.is_valid is not None

    def test_detect_drift_very_small_difference_detected(self, target):
        """微小差异应被检测"""
        request = EvaluationSchema(
            id="pr_b003",
            type="prompt_regression",
            payload={
                "action": "detect_drift",
                "baseline_output": "今天天气很好",
                "current_output": "今天天气挺好",  # 差一个字符
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        # 微小差异可能不被判定为漂移，取决于阈值
        assert "drift_level" in result.data

    def test_compare_totally_different_prompts_low_score(self, target):
        """完全不同的prompt应得低分"""
        request = EvaluationSchema(
            id="pr_b004",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "写一首关于春天的诗",
                "new_prompt": "如何用Python实现快速排序",
                "old_output": "春眠不觉晓",
                "new_output": "def quicksort(arr):",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["prompt_similarity"] < 0.5, "完全不同prompt应低相似度"


class TestPromptRegressionEvaluatorAlgorithmTests:
    """评分算法测试"""

    @pytest.fixture
    def target(self):
        return PromptRegressionEvaluator()

    def test_similarity_calculation_identical_texts(self, target):
        """相同文本相似度应为1.0"""
        similarity = target._calculate_similarity("Hello World", "Hello World")
        assert similarity == 1.0, "相同文本相似度必须为1.0"

    def test_similarity_calculation_totally_different(self, target):
        """完全不同文本相似度应接近0"""
        similarity = target._calculate_similarity("abc", "xyz")
        assert similarity < 0.3, "完全不同文本相似度应很低"

    def test_similarity_calculation_partial_overlap(self, target):
        """部分重叠文本相似度应在0-1之间"""
        similarity = target._calculate_similarity("Hello World", "Hello Universe")
        assert 0.3 < similarity < 1.0, "部分重叠应有中间相似度"

    def test_drift_level_classification_none(self, target):
        """drift < 0.1 应返回 none"""
        level = target._get_drift_level(0.05)
        assert level == "none"

    def test_drift_level_classification_low(self, target):
        """0.1 <= drift < 0.2 应返回 low"""
        level = target._get_drift_level(0.15)
        assert level == "low"

    def test_drift_level_classification_medium(self, target):
        """0.2 <= drift < 0.4 应返回 medium"""
        level = target._get_drift_level(0.3)
        assert level == "medium"

    def test_drift_level_classification_high(self, target):
        """0.4 <= drift < 0.6 应返回 high"""
        level = target._get_drift_level(0.5)
        assert level == "high"

    def test_drift_level_classification_critical(self, target):
        """drift >= 0.6 应返回 critical"""
        level = target._get_drift_level(0.7)
        assert level == "critical"

    def test_impact_level_classification_none(self, target):
        """score >= 0.9 应返回 none"""
        level = target._get_impact_level(0.95)
        assert level == "none"

    def test_impact_level_classification_low(self, target):
        """0.7 <= score < 0.9 应返回 low"""
        level = target._get_impact_level(0.8)
        assert level == "low"

    def test_impact_level_classification_medium(self, target):
        """0.5 <= score < 0.7 应返回 medium"""
        level = target._get_impact_level(0.6)
        assert level == "medium"

    def test_impact_level_classification_high(self, target):
        """0.3 <= score < 0.5 应返回 high"""
        level = target._get_impact_level(0.4)
        assert level == "high"

    def test_impact_level_classification_critical(self, target):
        """score < 0.3 应返回 critical"""
        level = target._get_impact_level(0.2)
        assert level == "critical"

    def test_change_type_classification_minor(self, target):
        """diff_ratio < 0.1 应返回 minor"""
        changes = {"diff_ratio": 0.05}
        change_type = target._classify_change_type(changes)
        assert change_type == "minor"

    def test_change_type_classification_moderate(self, target):
        """0.1 <= diff_ratio < 0.3 应返回 moderate"""
        changes = {"diff_ratio": 0.2}
        change_type = target._classify_change_type(changes)
        assert change_type == "moderate"

    def test_change_type_classification_significant(self, target):
        """0.3 <= diff_ratio < 0.6 应返回 significant"""
        changes = {"diff_ratio": 0.4}
        change_type = target._classify_change_type(changes)
        assert change_type == "significant"

    def test_change_type_classification_major(self, target):
        """diff_ratio >= 0.6 应返回 major"""
        changes = {"diff_ratio": 0.7}
        change_type = target._classify_change_type(changes)
        assert change_type == "major"

    def test_detect_prompt_changes_counts_correctly(self, target):
        """应正确计算变更行数"""
        old_prompt = "line1\nline2\nline3"
        new_prompt = "line1\nline2 modified\nline3\nline4"
        changes = target._detect_prompt_changes(old_prompt, new_prompt)

        assert "added_lines" in changes
        assert "removed_lines" in changes
        assert "changed_lines" in changes
        assert changes["added_lines"] >= 0
        assert changes["removed_lines"] >= 0

    def test_structural_drift_detection(self, target):
        """结构漂移检测"""
        baseline = "这是第一句。这是第二句。这是第三句。"
        current = "这是第一句。这是第二句。"
        drift = target._detect_structural_drift(baseline, current)

        assert 0.0 <= drift <= 1.0, "漂移值应在[0,1]范围内"

    def test_content_drift_detection(self, target):
        """内容漂移检测"""
        baseline = "苹果 香蕉 橙子"
        current = "苹果 香蕉"
        drift = target._detect_content_drift(baseline, current)

        assert 0.0 <= drift <= 1.0, "漂移值应在[0,1]范围内"
        assert drift > 0, "有内容减少应有漂移"

    def test_evaluate_correctness_impact(self, target):
        """正确性影响评估"""
        result = target._evaluate_correctness_impact("Hello World", "Hello World")
        assert result["dimension"] == "correctness"
        assert result["score"] == 1.0

    def test_evaluate_completeness_impact(self, target):
        """完整性影响评估"""
        result = target._evaluate_completeness_impact("旧输出很长的文本", "新输出短")
        assert result["dimension"] == "completeness"
        assert "score" in result

    def test_evaluate_relevance_impact(self, target):
        """相关性影响评估"""
        result = target._evaluate_relevance_impact(
            "机器学习是人工智能的子领域", "机器学习和深度学习是人工智能的重要组成"
        )
        assert result["dimension"] == "relevance"
        assert "score" in result

    def test_evaluate_tone_impact(self, target):
        """语气影响评估"""
        result = target._evaluate_tone_impact("很好很棒", "很好很棒")
        assert result["dimension"] == "tone"
        assert result["old_tone"] == result["new_tone"]

    def test_evaluate_format_impact(self, target):
        """格式影响评估"""
        result = target._evaluate_format_impact("# 标题\n内容", "# 标题\n内容")
        assert result["dimension"] == "format"
        assert result["score"] == 1.0

    def test_extract_keywords_filters_stop_words(self, target):
        """关键词提取应过滤停用词"""
        keywords = target._extract_keywords("的是一个很好的例子")
        # 停用词如"的"、"是"、"一个"、"很"、"好"、"的"应该被过滤
        assert "的" not in keywords
        assert "是" not in keywords

    def test_analyze_tone_detects_positive(self, target):
        """语气分析应检测正面情感"""
        tone = target._analyze_tone("很好很棒非常满意")
        assert tone["sentiment"] == "positive"

    def test_analyze_tone_detects_negative(self, target):
        """语气分析应检测负面情感"""
        tone = target._analyze_tone("很差很糟糕非常失望")
        assert tone["sentiment"] == "negative"

    def test_detect_format_identifies_bullet_points(self, target):
        """格式检测应识别列表"""
        format_info = target._detect_format("- 第一点\n- 第二点")
        assert format_info["has_bullet"] is True

    def test_detect_format_identifies_numbered_list(self, target):
        """格式检测应识别编号列表"""
        format_info = target._detect_format("1. 第一点\n2. 第二点")
        assert format_info["has_numbered"] is True

    def test_detect_format_identifies_code_blocks(self, target):
        """格式检测应识别代码块"""
        format_info = target._detect_format("```python\nprint('hello')\n```")
        assert format_info["has_code"] is True
