from src.domain.evaluators.prompt_regression import PromptRegressionEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestPromptRegressionEvaluator:
    """Prompt 回归测试评估器测试"""

    def setup_method(self):
        self.evaluator = PromptRegressionEvaluator(client=None)

    def test_compare_similar_prompts(self):
        """测试相似 Prompt 对比"""
        request = EvaluationSchema(
            id="test_compare_similar",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "请分析这段文本的主题。",
                "new_prompt": "请分析这段文本的主题。",
                "old_output": "这段文本的主题是科技发展。",
                "new_output": "这段文本的主题是科技发展。",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert result.data["prompt_similarity"] == 1.0
        assert result.data["output_similarity"] == 1.0
        assert result.data["change_type"] == "minor"

    def test_compare_different_prompts(self):
        """测试不同 Prompt 对比"""
        request = EvaluationSchema(
            id="test_compare_diff",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "请简洁地总结这段文本。",
                "new_prompt": "请详细分析这段文本的每个方面，包括背景、原因和影响，并给出你的专业见解。",
                "old_output": "文本讨论了经济发展。",
                "new_output": "文本主要讨论了经济发展。具体来看，包括以下几个方面：首先，经济增长率达到了预期目标；其次，产业结构持续优化；最后，市场信心有所恢复。",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["prompt_similarity"] < 0.5
        assert result.data["output_similarity"] < 1.0
        assert result.data["change_type"] in ["moderate", "significant", "major"]

    def test_detect_drift_low(self):
        """测试低漂移检测"""
        request = EvaluationSchema(
            id="test_drift_low",
            type="prompt_regression",
            payload={
                "action": "detect_drift",
                "baseline_output": "这是一个测试输出。",
                "current_output": "这是一个测试输出。",
                "threshold": 0.2,
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["drift_level"] in ["none", "low"]
        assert result.data["drift_detected"] is False
        assert result.data["threshold"] == 0.2

    def test_detect_drift_high(self):
        """测试高漂移检测"""
        request = EvaluationSchema(
            id="test_drift_high",
            type="prompt_regression",
            payload={
                "action": "detect_drift",
                "baseline_output": "苹果是一种水果，颜色是红色，味道甜美。",
                "current_output": "香蕉是一种热带水果，生长在南方地区，口感软糯香甜。",
                "threshold": 0.2,
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["drift_level"] in ["medium", "high", "critical"]
        assert result.data["drift_detected"] is True

    def test_analyze_impact_all_dimensions(self):
        """测试多维度影响分析"""
        request = EvaluationSchema(
            id="test_impact",
            type="prompt_regression",
            payload={
                "action": "analyze_impact",
                "old_output": "这是一个测试输出。包含了一些信息。",
                "new_output": "这是一个测试输出。包含了一些信息。",
                "criteria": ["correctness", "completeness", "relevance", "tone", "format"],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score >= 0.9
        assert "impact_dimensions" in result.data
        assert "correctness" in result.data["impact_dimensions"]
        assert "completeness" in result.data["impact_dimensions"]
        assert "relevance" in result.data["impact_dimensions"]
        assert "tone" in result.data["impact_dimensions"]
        assert "format" in result.data["impact_dimensions"]
        assert result.data["regression_acceptable"] is True

    def test_full_regression_test_pass(self):
        """测试完整回归测试通过"""
        request = EvaluationSchema(
            id="test_full_pass",
            type="prompt_regression",
            payload={
                "action": "full_regression_test",
                "old_prompt": "请分析这段文本。",
                "new_prompt": "请分析这段文本。",
                "old_output": "文本主题是科技。",
                "new_output": "文本主题是科技。",
                "baseline_output": "文本主题是科技。",
                "current_output": "文本主题是科技。",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score >= 0.7
        assert result.data["regression_passed"] is True
        assert "compare" in result.data
        assert "drift" in result.data
        assert "impact" in result.data

    def test_full_regression_test_fail(self):
        """测试完整回归测试失败"""
        request = EvaluationSchema(
            id="test_full_fail",
            type="prompt_regression",
            payload={
                "action": "full_regression_test",
                "old_prompt": "简单总结",
                "new_prompt": "极其详细深入全面地分析每个细节背景原因影响并给出专业建议",
                "old_output": "经济",
                "new_output": "经济方面：1. GDP增长5%。2. 产业结构优化。3. 就业率提高。4. 创新能力增强。5. 国际贸易增长。",
                "baseline_output": "经济",
                "current_output": "旅游数据分析：游客数量、满意度、消费情况等。",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score < 0.7
        assert result.data["regression_passed"] is False

    def test_missing_required_fields(self):
        """测试缺少必需字段"""
        # 测试缺少 old_prompt 和 new_prompt
        request = EvaluationSchema(
            id="test_missing",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_output": "输出1",
                "new_output": "输出2",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_missing_old_output(self):
        """测试缺少 old_output"""
        request = EvaluationSchema(
            id="test_missing",
            type="prompt_regression",
            payload={
                "action": "compare",
                "old_prompt": "提示1",
                "new_prompt": "提示2",
                "new_output": "输出2",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_detect_drift_missing_baseline(self):
        """测试漂移检测缺少 baseline_output"""
        request = EvaluationSchema(
            id="test_missing",
            type="prompt_regression",
            payload={
                "action": "detect_drift",
                "current_output": "当前输出",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_analyze_impact_missing_output(self):
        """测试影响分析缺少输出"""
        request = EvaluationSchema(
            id="test_missing",
            type="prompt_regression",
            payload={
                "action": "analyze_impact",
                "old_output": "旧输出",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_unknown_action(self):
        """测试未知 action"""
        request = EvaluationSchema(
            id="test_unknown",
            type="prompt_regression",
            payload={
                "action": "unknown_action",
                "old_prompt": "提示",
                "new_prompt": "新提示",
                "old_output": "输出1",
                "new_output": "输出2",
                "baseline_output": "基准输出",
                "current_output": "当前输出",
            },
        )

        result = self.evaluator.evaluate(request)

        # 未知 action 会执行 full_regression_test
        assert result.is_valid is True

    def test_calculate_similarity(self):
        """测试相似度计算"""
        text1 = "这是一个测试文本"
        text2 = "这是一个测试文本"
        text3 = "那是另一个文本"

        ratio_same = self.evaluator._calculate_similarity(text1, text2)
        ratio_diff = self.evaluator._calculate_similarity(text1, text3)

        assert ratio_same == 1.0
        assert ratio_diff < 1.0

    def test_get_drift_level(self):
        """测试漂移级别判断"""
        assert self.evaluator._get_drift_level(0.05) == "none"
        assert self.evaluator._get_drift_level(0.15) == "low"
        assert self.evaluator._get_drift_level(0.35) == "medium"
        assert self.evaluator._get_drift_level(0.55) == "high"
        assert self.evaluator._get_drift_level(0.75) == "critical"

    def test_get_impact_level(self):
        """测试影响级别判断"""
        assert self.evaluator._get_impact_level(0.95) == "none"
        assert self.evaluator._get_impact_level(0.75) == "low"
        assert self.evaluator._get_impact_level(0.55) == "medium"
        assert self.evaluator._get_impact_level(0.35) == "high"
        assert self.evaluator._get_impact_level(0.15) == "critical"

    def test_extract_keywords(self):
        """测试关键词提取"""
        text = "test text for keyword extraction testing purposes"
        keywords = self.evaluator._extract_keywords(text)

        assert isinstance(keywords, list)
        assert "test" in keywords
        assert "text" in keywords
        assert "keyword" in keywords
        assert "extraction" in keywords
        # 停用词不应该出现
        assert "is" not in keywords
        assert "are" not in keywords
        assert "for" not in keywords

    def test_analyze_tone(self):
        """测试语气分析"""
        positive_text = "这是一个好的解决方案，非常出色！"
        negative_text = "这个方案很差，有很多问题。"
        neutral_text = "这个方案需要进一步分析。"

        pos_tone = self.evaluator._analyze_tone(positive_text)
        neg_tone = self.evaluator._analyze_tone(negative_text)
        neu_tone = self.evaluator._analyze_tone(neutral_text)

        assert pos_tone["sentiment"] == "positive"
        assert neg_tone["sentiment"] == "negative"
        assert neu_tone["sentiment"] == "neutral"

    def test_detect_format(self):
        """测试格式检测"""
        bullet_text = "- 项目一\n- 项目二\n- 项目三"
        numbered_text = "1. 第一步\n2. 第二步\n3. 第三步"
        code_text = "```python\nprint('hello')\n```"
        table_text = "| 列1 | 列2 |\n| --- | --- |\n| 数据1 | 数据2 |"
        title_text = "# 标题\n## 副标题"
        plain_text = "这是一段普通文本，没有特殊格式。"

        assert self.evaluator._detect_format(bullet_text)["has_bullet"] is True
        assert self.evaluator._detect_format(numbered_text)["has_numbered"] is True
        assert self.evaluator._detect_format(code_text)["has_code"] is True
        assert self.evaluator._detect_format(table_text)["has_table"] is True
        assert self.evaluator._detect_format(title_text)["has_title"] is True
        assert self.evaluator._detect_format(plain_text)["has_bullet"] is False
        assert self.evaluator._detect_format(plain_text)["has_numbered"] is False
        assert self.evaluator._detect_format(plain_text)["has_code"] is False
        assert self.evaluator._detect_format(plain_text)["has_table"] is False
        assert self.evaluator._detect_format(plain_text)["has_title"] is False
