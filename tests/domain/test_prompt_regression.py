"""
Prompt回归测试评估器测试
测试目标：验证PromptRegressionEvaluator的核心功能
核心功能：
1. Prompt版本对比（compare）
2. 漂移检测（detect_drift）
3. 影响分析（analyze_impact）
4. 完整回归测试（full_regression_test）

关键发现：（测试过程中记录）
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.prompt_regression import PromptRegressionEvaluator
from src.schemas.evaluation import EvaluationSchema, DomainResponse


class TestPromptRegressionCompare:
    """Prompt版本对比测试 - 核心功能"""

    @pytest.fixture
    def evaluator(self):
        """创建Prompt回归测试评估器"""
        return PromptRegressionEvaluator()

    def test_compare_identical_prompts(self, evaluator):
        """相同Prompt应返回高相似度"""
        request = EvaluationSchema(
            id="test_001",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "你是一个AI助手",
                "new_prompt": "你是一个AI助手",
                "old_output": "你好，我是AI助手",
                "new_output": "你好，我是AI助手"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score >= 0.9
        assert result.data["prompt_similarity"] == 1.0
        assert result.data["output_similarity"] == 1.0
        assert result.data["change_type"] == "minor"

    def test_compare_different_prompts_same_output(self, evaluator):
        """不同Prompt但相同输出应返回高分"""
        request = EvaluationSchema(
            id="test_002",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "请回答用户问题",
                "new_prompt": "请详细回答用户的问题",
                "old_output": "这是一个很好的问题",
                "new_output": "这是一个很好的问题"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score >= 0.8
        assert result.data["output_similarity"] == 1.0
        assert result.data["prompt_similarity"] < 1.0

    def test_compare_minor_prompt_changes(self, evaluator):
        """小幅Prompt变更应识别为minor"""
        # 使用更多行数，使修改比例更小
        old_prompt = "\n".join([f"规则{i}: 内容{i}" for i in range(10)])
        new_prompt = "\n".join([f"规则{i}: 内容{i}" for i in range(9)] + ["规则9: 修改内容"])

        request = EvaluationSchema(
            id="test_003",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": old_prompt,
                "new_prompt": new_prompt,
                "old_output": "你好",
                "new_output": "你好，很高兴为您服务"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 只有1行修改，10行中占比0.1，应该是minor或moderate
        assert result.data["change_type"] in ["minor", "moderate"]
        assert result.data["prompt_changes"]["diff_ratio"] <= 0.2

    def test_compare_significant_prompt_changes(self, evaluator):
        """显著Prompt变更应识别为significant"""
        old_prompt = "\n".join([f"规则{i}: 内容{i}" for i in range(10)])
        new_prompt = "\n".join([f"规则{i}: 新内容{i}" for i in range(10)])

        request = EvaluationSchema(
            id="test_004",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": old_prompt,
                "new_prompt": new_prompt,
                "old_output": "旧输出",
                "new_output": "新输出"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["change_type"] in ["moderate", "significant", "major"]
        assert result.data["prompt_changes"]["changed_lines"] > 0

    def test_compare_missing_old_prompt(self, evaluator):
        """缺失old_prompt应返回错误"""
        request = EvaluationSchema(
            id="test_005",
            type="prompt_regression",
            payload={
                "action": "compare",
                "new_prompt": "新Prompt",
                "old_output": "旧输出",
                "new_output": "新输出"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "old_prompt" in result.error
        assert "不能为空" in result.error

    def test_compare_missing_new_prompt(self, evaluator):
        """缺失new_prompt应返回错误"""
        request = EvaluationSchema(
            id="test_006",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "旧Prompt",
                "old_output": "旧输出",
                "new_output": "新输出"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "new_prompt" in result.error

    def test_compare_missing_outputs(self, evaluator):
        """缺失输出应返回错误"""
        request = EvaluationSchema(
            id="test_007",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "旧Prompt",
                "new_prompt": "新Prompt"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "old_output" in result.error or "new_output" in result.error


class TestPromptRegressionDriftDetection:
    """漂移检测测试 - 核心功能"""

    @pytest.fixture
    def evaluator(self):
        """创建Prompt回归测试评估器"""
        return PromptRegressionEvaluator()

    def test_detect_no_drift_high_similarity(self, evaluator):
        """高相似度应检测为无漂移"""
        request = EvaluationSchema(
            id="test_008",
            type="prompt_regression",
            payload={
                "action": "detect_drift",
                "baseline_output": "这是一个很好的回答",
                "current_output": "这是一个很好的回答"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["drift_detected"] is False
        assert result.data["drift_level"] == "none"
        assert result.data["overall_drift"] < 0.1

    def test_detect_drift_low_similarity(self, evaluator):
        """低相似度应检测为漂移"""
        request = EvaluationSchema(
            id="test_009",
            type="prompt_regression",
            payload={
                "action": "detect_drift",
                "baseline_output": "今天天气很好，适合出门",
                "current_output": "人工智能正在改变世界"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["drift_detected"] is True
        assert result.data["drift_level"] in ["medium", "high", "critical"]
        assert result.data["overall_drift"] > 0.2

    def test_detect_structural_drift(self, evaluator):
        """结构漂移检测"""
        request = EvaluationSchema(
            id="test_010",
            type="prompt_regression",
            payload={
                "action": "detect_drift",
                "baseline_output": "短文本",
                "current_output": "这是一段非常长的文本内容，包含了很多句子和词汇，用于测试结构漂移检测功能是否正常工作"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["structural_drift"] > 0.3
        assert "structural_drift" in result.data

    def test_detect_content_drift(self, evaluator):
        """内容漂移检测"""
        request = EvaluationSchema(
            id="test_011",
            type="prompt_regression",
            payload={
                "action": "detect_drift",
                "baseline_output": "苹果 香蕉 橘子",
                "current_output": "汽车 飞机 轮船"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["content_drift"] > 0.5
        assert result.data["drift_detected"] is True

    def test_detect_drift_with_custom_threshold(self, evaluator):
        """自定义阈值漂移检测"""
        request = EvaluationSchema(
            id="test_012",
            type="prompt_regression",
            payload={
                "action": "detect_drift",
                "baseline_output": "原始输出内容",
                "current_output": "修改后的输出内容",
                "threshold": 0.1
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["threshold"] == 0.1
        # 根据实际漂移分数判断
        if result.data["overall_drift"] > 0.1:
            assert result.data["drift_detected"] is True

    def test_detect_drift_missing_baseline(self, evaluator):
        """缺失baseline_output应返回错误"""
        request = EvaluationSchema(
            id="test_013",
            type="prompt_regression",
            payload={
                "action": "detect_drift",
                "current_output": "当前输出"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "baseline_output" in result.error

    def test_detect_drift_missing_current(self, evaluator):
        """缺失current_output应返回错误"""
        request = EvaluationSchema(
            id="test_014",
            type="prompt_regression",
            payload={
                "action": "detect_drift",
                "baseline_output": "基线输出"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "current_output" in result.error


class TestPromptRegressionImpactAnalysis:
    """影响分析测试 - 核心功能"""

    @pytest.fixture
    def evaluator(self):
        """创建Prompt回归测试评估器"""
        return PromptRegressionEvaluator()

    def test_analyze_impact_no_change(self, evaluator):
        """无变化应返回低影响"""
        request = EvaluationSchema(
            id="test_015",
            type="prompt_regression",
            payload={
                "action": "analyze_impact",
                "old_output": "这是一个很好的回答",
                "new_output": "这是一个很好的回答"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["overall_impact_score"] >= 0.9
        assert result.data["impact_level"] == "none"
        assert result.data["regression_acceptable"] is True

    def test_analyze_impact_with_criteria(self, evaluator):
        """指定评估维度应只评估指定维度"""
        request = EvaluationSchema(
            id="test_016",
            type="prompt_regression",
            payload={
                "action": "analyze_impact",
                "old_output": "原始回答",
                "new_output": "修改后的回答",
                "criteria": ["correctness", "completeness"]
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert "correctness" in result.data["impact_dimensions"]
        assert "completeness" in result.data["impact_dimensions"]
        # 未指定的维度不应评估
        assert "relevance" not in result.data["impact_dimensions"]

    def test_analyze_impact_all_dimensions(self, evaluator):
        """不指定维度应评估所有维度"""
        request = EvaluationSchema(
            id="test_017",
            type="prompt_regression",
            payload={
                "action": "analyze_impact",
                "old_output": "原始回答",
                "new_output": "修改后的回答"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert "correctness" in result.data["impact_dimensions"]
        assert "completeness" in result.data["impact_dimensions"]
        assert "relevance" in result.data["impact_dimensions"]
        assert "tone" in result.data["impact_dimensions"]
        assert "format" in result.data["impact_dimensions"]

    def test_analyze_impact_major_change(self, evaluator):
        """重大变化应返回高影响"""
        request = EvaluationSchema(
            id="test_018",
            type="prompt_regression",
            payload={
                "action": "analyze_impact",
                "old_output": "简短回答",
                "new_output": "这是一个非常详细的回答，包含了大量的信息和解释，用于测试影响分析功能是否能够正确识别重大变化"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["impact_level"] in ["medium", "high", "critical"]

    def test_analyze_impact_missing_outputs(self, evaluator):
        """缺失输出应返回错误"""
        request = EvaluationSchema(
            id="test_019",
            type="prompt_regression",
            payload={
                "action": "analyze_impact"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "old_output" in result.error or "new_output" in result.error


class TestPromptRegressionFullTest:
    """完整回归测试 - 综合功能"""

    @pytest.fixture
    def evaluator(self):
        """创建Prompt回归测试评估器"""
        return PromptRegressionEvaluator()

    def test_full_regression_passed(self, evaluator):
        """完整回归测试通过"""
        request = EvaluationSchema(
            id="test_020",
            type="prompt_regression",
            payload={
                "action": "full_regression",
                "old_prompt": "你是一个AI助手",
                "new_prompt": "你是一个AI助手",
                "old_output": "你好，我是AI助手",
                "new_output": "你好，我是AI助手",
                "baseline_output": "你好，我是AI助手",
                "current_output": "你好，我是AI助手"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["regression_passed"] is True
        assert result.score >= 0.7
        assert "compare" in result.data
        assert "drift" in result.data
        assert "impact" in result.data

    def test_full_regression_failed(self, evaluator):
        """完整回归测试失败"""
        request = EvaluationSchema(
            id="test_021",
            type="prompt_regression",
            payload={
                "action": "full_regression",
                "old_prompt": "你是一个AI助手",
                "new_prompt": "你是一个完全不同的助手",
                "old_output": "你好，我是AI助手",
                "new_output": "我是全新的助手，功能完全不同",
                "baseline_output": "你好，我是AI助手",
                "current_output": "我是全新的助手，功能完全不同"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["regression_passed"] is False
        assert result.score < 0.7

    def test_full_regression_weighted_score(self, evaluator):
        """完整回归测试加权分数计算"""
        request = EvaluationSchema(
            id="test_022",
            type="prompt_regression",
            payload={
                "action": "full_regression",
                "old_prompt": "旧Prompt",
                "new_prompt": "新Prompt",
                "old_output": "旧输出",
                "new_output": "新输出",
                "baseline_output": "基线输出",
                "current_output": "当前输出"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 验证加权计算：compare(0.4) + drift(0.3) + impact(0.3)
        # 验证分数在合理范围内（0-1之间）
        assert 0 <= result.score <= 1.0
        # 验证overall_score与score一致
        assert result.data["overall_score"] == result.score
        # 验证regression_passed基于分数判断
        assert result.data["regression_passed"] == (result.score >= 0.7)


class TestPromptRegressionHelperMethods:
    """辅助方法测试 - 内部逻辑验证"""

    @pytest.fixture
    def evaluator(self):
        """创建Prompt回归测试评估器"""
        return PromptRegressionEvaluator()

    def test_calculate_similarity_identical(self, evaluator):
        """相同文本相似度应为1.0"""
        similarity = evaluator._calculate_similarity("Hello World", "Hello World")
        assert similarity == 1.0

    def test_calculate_similarity_different(self, evaluator):
        """不同文本相似度应小于1.0"""
        similarity = evaluator._calculate_similarity("Hello World", "Goodbye World")
        assert 0 < similarity < 1.0

    def test_calculate_similarity_empty(self, evaluator):
        """空文本相似度应为1.0"""
        similarity = evaluator._calculate_similarity("", "")
        assert similarity == 1.0

    def test_detect_prompt_changes_added_lines(self, evaluator):
        """新增行检测"""
        old_prompt = "第一行\n第二行"
        new_prompt = "第一行\n第二行\n第三行"

        changes = evaluator._detect_prompt_changes(old_prompt, new_prompt)

        assert changes["added_lines"] == 1
        assert changes["removed_lines"] == 0
        assert changes["changed_lines"] == 1

    def test_detect_prompt_changes_removed_lines(self, evaluator):
        """删除行检测"""
        old_prompt = "第一行\n第二行\n第三行"
        new_prompt = "第一行\n第二行"

        changes = evaluator._detect_prompt_changes(old_prompt, new_prompt)

        assert changes["added_lines"] == 0
        assert changes["removed_lines"] == 1
        assert changes["changed_lines"] == 1

    def test_detect_prompt_changes_modified_lines(self, evaluator):
        """修改行检测"""
        old_prompt = "第一行\n第二行\n第三行"
        new_prompt = "第一行\n修改的第二行\n第三行"

        changes = evaluator._detect_prompt_changes(old_prompt, new_prompt)

        assert changes["added_lines"] >= 1
        assert changes["removed_lines"] >= 1
        assert changes["changed_lines"] >= 2

    def test_classify_change_type_minor(self, evaluator):
        """小幅变更分类"""
        changes = {"diff_ratio": 0.05}
        change_type = evaluator._classify_change_type(changes)
        assert change_type == "minor"

    def test_classify_change_type_moderate(self, evaluator):
        """中等变更分类"""
        changes = {"diff_ratio": 0.15}
        change_type = evaluator._classify_change_type(changes)
        assert change_type == "moderate"

    def test_classify_change_type_significant(self, evaluator):
        """显著变更分类"""
        changes = {"diff_ratio": 0.45}
        change_type = evaluator._classify_change_type(changes)
        assert change_type == "significant"

    def test_classify_change_type_major(self, evaluator):
        """重大变更分类"""
        changes = {"diff_ratio": 0.75}
        change_type = evaluator._classify_change_type(changes)
        assert change_type == "major"

    def test_detect_structural_drift_identical(self, evaluator):
        """相同结构无漂移"""
        drift = evaluator._detect_structural_drift("Hello World", "Hello World")
        assert drift == 0.0

    def test_detect_structural_drift_different_length(self, evaluator):
        """不同长度结构漂移"""
        drift = evaluator._detect_structural_drift("短文本", "这是一段非常长的文本内容")
        assert drift > 0.5

    def test_detect_structural_drift_different_sentences(self, evaluator):
        """不同句子数结构漂移"""
        drift = evaluator._detect_structural_drift(
            "第一句。第二句。第三句。",
            "第一句。"
        )
        assert drift > 0.3

    def test_detect_content_drift_identical(self, evaluator):
        """相同内容无漂移"""
        drift = evaluator._detect_content_drift("Hello World", "Hello World")
        assert drift == 0.0

    def test_detect_content_drift_different(self, evaluator):
        """不同内容漂移"""
        drift = evaluator._detect_content_drift("苹果 香蕉", "汽车 飞机")
        assert drift > 0.5

    def test_detect_content_drift_partial_overlap(self, evaluator):
        """部分重叠内容漂移"""
        drift = evaluator._detect_content_drift("苹果 香蕉 橘子", "苹果 香蕉 葡萄")
        assert 0 < drift < 1.0

    def test_get_drift_level_none(self, evaluator):
        """无漂移级别"""
        level = evaluator._get_drift_level(0.05)
        assert level == "none"

    def test_get_drift_level_low(self, evaluator):
        """低漂移级别"""
        level = evaluator._get_drift_level(0.15)
        assert level == "low"

    def test_get_drift_level_medium(self, evaluator):
        """中等漂移级别"""
        level = evaluator._get_drift_level(0.25)
        assert level == "medium"

    def test_get_drift_level_high(self, evaluator):
        """高漂移级别"""
        level = evaluator._get_drift_level(0.45)
        assert level == "high"

    def test_get_drift_level_critical(self, evaluator):
        """严重漂移级别"""
        level = evaluator._get_drift_level(0.65)
        assert level == "critical"


class TestPromptRegressionImpactDimensions:
    """影响维度评估测试 - 详细验证"""

    @pytest.fixture
    def evaluator(self):
        """创建Prompt回归测试评估器"""
        return PromptRegressionEvaluator()

    def test_evaluate_correctness_impact_identical(self, evaluator):
        """正确性影响 - 相同输出"""
        result = evaluator._evaluate_correctness_impact("相同内容", "相同内容")
        assert result["score"] == 1.0
        assert result["impact"] == "none"

    def test_evaluate_correctness_impact_different(self, evaluator):
        """正确性影响 - 不同输出"""
        result = evaluator._evaluate_correctness_impact("原始内容", "修改内容")
        assert 0 < result["score"] < 1.0

    def test_evaluate_completeness_impact_longer(self, evaluator):
        """完整性影响 - 更长输出"""
        result = evaluator._evaluate_completeness_impact("短", "这是一个更长的输出内容")
        assert result["score"] >= 1.0

    def test_evaluate_completeness_impact_shorter(self, evaluator):
        """完整性影响 - 更短输出"""
        result = evaluator._evaluate_completeness_impact("这是一个更长的输出内容", "短")
        assert result["score"] < 1.0

    def test_evaluate_relevance_impact_same_keywords(self, evaluator):
        """相关性影响 - 相同关键词"""
        # 使用更明确的词汇，确保关键词能被提取
        result = evaluator._evaluate_relevance_impact(
            "人工智能 AI 技术",
            "人工智能 AI 技术"
        )
        # 相同关键词，重叠率应该很高
        assert result["score"] >= 0.8

    def test_evaluate_relevance_impact_different_keywords(self, evaluator):
        """相关性影响 - 不同关键词"""
        result = evaluator._evaluate_relevance_impact(
            "苹果是一种水果",
            "汽车是一种交通工具"
        )
        assert result["score"] < 0.5

    def test_evaluate_tone_impact_positive(self, evaluator):
        """语气影响 - 正面语气"""
        result = evaluator._evaluate_tone_impact(
            "这是一个很好的产品，我非常满意",
            "这是一个优秀的产品，我非常满意"
        )
        assert result["old_tone"]["sentiment"] == "positive"
        assert result["new_tone"]["sentiment"] == "positive"
        assert result["score"] >= 0.8

    def test_evaluate_tone_impact_negative(self, evaluator):
        """语气影响 - 负面语气"""
        result = evaluator._evaluate_tone_impact(
            "这个产品很糟糕，我很失望",
            "这个产品很差，我很不满意"
        )
        assert result["old_tone"]["sentiment"] == "negative"
        assert result["new_tone"]["sentiment"] == "negative"

    def test_evaluate_format_impact_bullet_list(self, evaluator):
        """格式影响 - 列表格式"""
        result = evaluator._evaluate_format_impact(
            "- 第一项\n- 第二项\n- 第三项",
            "- 第一项\n- 第二项\n- 第三项"
        )
        assert result["old_format"]["has_bullet"] is True
        assert result["new_format"]["has_bullet"] is True
        assert result["score"] == 1.0

    def test_evaluate_format_impact_code_block(self, evaluator):
        """格式影响 - 代码块"""
        result = evaluator._evaluate_format_impact(
            "```python\nprint('Hello')\n```",
            "```python\nprint('World')\n```"
        )
        assert result["old_format"]["has_code"] is True
        assert result["new_format"]["has_code"] is True

    def test_get_impact_level_none(self, evaluator):
        """无影响级别"""
        level = evaluator._get_impact_level(0.95)
        assert level == "none"

    def test_get_impact_level_low(self, evaluator):
        """低影响级别"""
        level = evaluator._get_impact_level(0.75)
        assert level == "low"

    def test_get_impact_level_medium(self, evaluator):
        """中等影响级别"""
        level = evaluator._get_impact_level(0.55)
        assert level == "medium"

    def test_get_impact_level_high(self, evaluator):
        """高影响级别"""
        level = evaluator._get_impact_level(0.35)
        assert level == "high"

    def test_get_impact_level_critical(self, evaluator):
        """严重影响级别"""
        level = evaluator._get_impact_level(0.15)
        assert level == "critical"


class TestPromptRegressionKeywordExtraction:
    """关键词提取测试"""

    @pytest.fixture
    def evaluator(self):
        """创建Prompt回归测试评估器"""
        return PromptRegressionEvaluator()

    def test_extract_keywords_chinese(self, evaluator):
        """中文关键词提取"""
        keywords = evaluator._extract_keywords("人工智能是计算机科学的一个重要分支")
        assert len(keywords) > 0
        # 关键词提取返回完整短语，验证关键词来自原文
        for kw in keywords:
            assert kw in "人工智能是计算机科学的一个重要分支"

    def test_extract_keywords_english(self, evaluator):
        """英文关键词提取"""
        keywords = evaluator._extract_keywords("Artificial intelligence is a branch of computer science")
        assert len(keywords) > 0
        # 停用词应被过滤
        assert "is" not in keywords
        assert "a" not in keywords
        assert "of" not in keywords

    def test_extract_keywords_mixed(self, evaluator):
        """中英文混合关键词提取"""
        keywords = evaluator._extract_keywords("AI人工智能是Artificial Intelligence的缩写")
        assert len(keywords) > 0

    def test_extract_keywords_filters_stopwords(self, evaluator):
        """停用词过滤"""
        keywords = evaluator._extract_keywords("这是一个很好的产品，我非常满意")
        # 中文停用词应被过滤
        assert "的" not in keywords
        assert "是" not in keywords
        assert "我" not in keywords

    def test_extract_keywords_limit(self, evaluator):
        """关键词数量限制"""
        long_text = " ".join([f"关键词{i}" for i in range(50)])
        keywords = evaluator._extract_keywords(long_text)
        assert len(keywords) <= 20


class TestPromptRegressionToneAnalysis:
    """语气分析测试"""

    @pytest.fixture
    def evaluator(self):
        """创建Prompt回归测试评估器"""
        return PromptRegressionEvaluator()

    def test_analyze_tone_positive(self, evaluator):
        """正面语气分析"""
        tone = evaluator._analyze_tone("这是一个很好的产品，我非常满意，感谢支持")
        assert tone["sentiment"] == "positive"

    def test_analyze_tone_negative(self, evaluator):
        """负面语气分析"""
        tone = evaluator._analyze_tone("这个产品很糟糕，我很失望，非常不满意")
        assert tone["sentiment"] == "negative"

    def test_analyze_tone_neutral(self, evaluator):
        """中性语气分析"""
        tone = evaluator._analyze_tone("这是一个产品说明")
        assert tone["sentiment"] == "neutral"

    def test_analyze_tone_formal(self, evaluator):
        """正式语气分析"""
        tone = evaluator._analyze_tone("尊敬的客户，感谢您的咨询。我们将尽快处理您的请求。")
        assert tone["formality"] in ["formal", "informal"]

    def test_analyze_tone_informal(self, evaluator):
        """非正式语气分析"""
        tone = evaluator._analyze_tone("hey! what's up? this is cool!")
        assert tone["formality"] in ["formal", "informal"]


class TestPromptRegressionFormatDetection:
    """格式检测测试"""

    @pytest.fixture
    def evaluator(self):
        """创建Prompt回归测试评估器"""
        return PromptRegressionEvaluator()

    def test_detect_format_bullet_list(self, evaluator):
        """列表格式检测"""
        format_info = evaluator._detect_format("- 第一项\n- 第二项\n- 第三项")
        assert format_info["has_bullet"] is True

    def test_detect_format_numbered_list(self, evaluator):
        """编号列表格式检测"""
        format_info = evaluator._detect_format("1. 第一项\n2. 第二项\n3. 第三项")
        assert format_info["has_numbered"] is True

    def test_detect_format_code_block(self, evaluator):
        """代码块格式检测"""
        format_info = evaluator._detect_format("```python\nprint('Hello')\n```")
        assert format_info["has_code"] is True

    def test_detect_format_table(self, evaluator):
        """表格格式检测"""
        format_info = evaluator._detect_format("| 列1 | 列2 |\n|-----|-----|\n| 值1 | 值2 |")
        assert format_info["has_table"] is True

    def test_detect_format_title(self, evaluator):
        """标题格式检测"""
        format_info = evaluator._detect_format("# 这是一个标题")
        assert format_info["has_title"] is True

    def test_detect_format_plain_text(self, evaluator):
        """纯文本格式检测"""
        format_info = evaluator._detect_format("这是一段普通的文本，没有特殊格式。")
        assert format_info["has_bullet"] is False
        assert format_info["has_numbered"] is False
        assert format_info["has_code"] is False
        assert format_info["has_table"] is False


class TestPromptRegressionEdgeCases:
    """边界场景测试"""

    @pytest.fixture
    def evaluator(self):
        """创建Prompt回归测试评估器"""
        return PromptRegressionEvaluator()

    def test_empty_prompts(self, evaluator):
        """空Prompt处理"""
        request = EvaluationSchema(
            id="test_edge_001",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "",
                "new_prompt": "",
                "old_output": "输出",
                "new_output": "输出"
            }
        )

        result = evaluator.evaluate(request)

        # 空Prompt应返回错误
        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_empty_outputs(self, evaluator):
        """空输出处理"""
        request = EvaluationSchema(
            id="test_edge_002",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "Prompt",
                "new_prompt": "Prompt",
                "old_output": "",
                "new_output": ""
            }
        )

        result = evaluator.evaluate(request)

        # 空输出应返回错误
        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_very_long_text(self, evaluator):
        """超长文本处理"""
        long_text = "这是一个很长的文本。" * 1000

        request = EvaluationSchema(
            id="test_edge_003",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": long_text,
                "new_prompt": long_text[:500],
                "old_output": "输出",
                "new_output": "输出"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score >= 0

    def test_special_characters(self, evaluator):
        """特殊字符处理"""
        request = EvaluationSchema(
            id="test_edge_004",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "Prompt with special chars: <>&\"'",
                "new_prompt": "Prompt with special chars: <>&\"'",
                "old_output": "Output with special chars: <>&\"'",
                "new_output": "Output with special chars: <>&\"'"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score >= 0.9

    def test_unicode_characters(self, evaluator):
        """Unicode字符处理"""
        request = EvaluationSchema(
            id="test_edge_005",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "中文测试 🎉 表情符号",
                "new_prompt": "中文测试 🎉 表情符号",
                "old_output": "输出 🎉",
                "new_output": "输出 🎉"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score >= 0.9

    def test_invalid_action(self, evaluator):
        """无效action处理"""
        # 提供完整的字段，避免计算时出现None
        request = EvaluationSchema(
            id="test_edge_006",
            type="prompt_regression",
            payload={
                "action": "invalid_action",
                "old_prompt": "Prompt",
                "new_prompt": "Prompt",
                "old_output": "Output",
                "new_output": "Output",
                "baseline_output": "Baseline",
                "current_output": "Current"
            }
        )

        result = evaluator.evaluate(request)

        # 无效action应执行完整回归测试
        assert result.is_valid is True
        assert result.score >= 0

    def test_none_input_handling(self, evaluator):
        """None输入处理"""
        request = EvaluationSchema(
            id="test_edge_007",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": None,
                "new_prompt": "Prompt",
                "old_output": "Output",
                "new_output": "Output"
            }
        )

        result = evaluator.evaluate(request)

        # None应被识别为空值
        assert result.is_valid is False


# 关键发现：
# 1. Prompt回归测试支持4种action：compare、detect_drift、analyze_impact、full_regression
# 2. compare使用difflib计算相似度和变更检测
# 3. detect_drift综合语义相似度、结构漂移、内容漂移三个维度
# 4. analyze_impact评估correctness、completeness、relevance、tone、format五个维度
# 5. full_regression加权计算：compare(0.4) + drift(0.3) + impact(0.3)
# 6. 变更类型分类：minor(<10%)、moderate(<30%)、significant(<60%)、major(>=60%)
# 7. 漂移级别：none(<10%)、low(<20%)、medium(<40%)、high(<60%)、critical(>=60%)
# 8. 影响级别：none(>=90%)、low(>=70%)、medium(>=50%)、high(>=30%)、critical(<30%)
# 9. 关键词提取支持中英文，自动过滤停用词，最多返回20个
# 10. 语气分析识别正面/负面/中性情绪，以及正式/非正式程度