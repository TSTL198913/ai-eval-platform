"""PromptRegressionEvaluator 单元测试"""

import pytest
from unittest.mock import MagicMock, patch

from src.domain.evaluators.prompt_regression import PromptRegressionEvaluator
from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus


class TestPromptRegressionEvaluatorPositiveCases:
    """正向测试用例"""

    def test_prompt_version_compare(self):
        """应正确比较两个版本的Prompt"""
        evaluator = PromptRegressionEvaluator()
        request = EvaluationSchema(
            id="test_case_001",
            type="prompt_regression",
            user_input="测试问题",
            payload={
                "old_prompt": "旧版本Prompt",
                "new_prompt": "新版本Prompt",
                "old_output": "旧版本输出",
                "new_output": "新版本输出",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert 0 <= response.score <= 1.0
        assert "prompt_similarity" in response.data
        assert "output_similarity" in response.data

    def test_drift_detection(self):
        """应正确检测漂移"""
        evaluator = PromptRegressionEvaluator()
        request = EvaluationSchema(
            id="test_case_002",
            type="prompt_regression",
            user_input="测试问题",
            payload={
                "baseline_output": "基线输出内容",
                "current_output": "当前输出内容",
                "action": "detect_drift",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "drift_score" in response.data
        assert "drift_detected" in response.data

    def test_impact_analysis(self):
        """应正确分析Prompt变更的影响"""
        evaluator = PromptRegressionEvaluator()
        request = EvaluationSchema(
            id="test_case_003",
            type="prompt_regression",
            user_input="测试问题",
            payload={
                "old_output": "旧版本详细回答",
                "new_output": "新版本详细回答",
                "action": "analyze_impact",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "impact_dimensions" in response.data
        assert "overall_impact_score" in response.data

    def test_full_regression_test(self):
        """完整回归测试应综合所有维度"""
        evaluator = PromptRegressionEvaluator()
        request = EvaluationSchema(
            id="test_case_004",
            type="prompt_regression",
            user_input="测试问题",
            payload={
                "old_prompt": "旧Prompt",
                "new_prompt": "新Prompt",
                "old_output": "旧输出",
                "new_output": "新输出",
                "baseline_output": "基线输出",
                "current_output": "当前输出",
                "action": "full",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "compare" in response.data
        assert "drift" in response.data
        assert "impact" in response.data

    def test_similar_prompts_have_high_score(self):
        """相似的Prompt应返回高分"""
        evaluator = PromptRegressionEvaluator()
        request = EvaluationSchema(
            id="test_case_005",
            type="prompt_regression",
            user_input="测试问题",
            payload={
                "old_prompt": "请回答以下问题：",
                "new_prompt": "请回答下面的问题：",
                "old_output": "相同的回答内容",
                "new_output": "相同的回答内容",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score >= 0.8

    def test_change_type_classification(self):
        """变更类型分类应正确"""
        evaluator = PromptRegressionEvaluator()
        
        assert evaluator._classify_change_type({"diff_ratio": 0.05}) == "minor"
        assert evaluator._classify_change_type({"diff_ratio": 0.2}) == "moderate"
        assert evaluator._classify_change_type({"diff_ratio": 0.4}) == "significant"
        assert evaluator._classify_change_type({"diff_ratio": 0.8}) == "major"

    def test_drift_level_detection(self):
        """漂移等级检测应正确"""
        evaluator = PromptRegressionEvaluator()
        
        assert evaluator._get_drift_level(0.05) == "none"
        assert evaluator._get_drift_level(0.15) == "low"
        assert evaluator._get_drift_level(0.3) == "medium"
        assert evaluator._get_drift_level(0.5) == "high"
        assert evaluator._get_drift_level(0.7) == "critical"


class TestPromptRegressionEvaluatorNegativeCases:
    """负向测试用例"""

    def test_missing_prompts_for_compare(self):
        """比较时缺少Prompt应返回错误"""
        evaluator = PromptRegressionEvaluator()
        request = EvaluationSchema(
            id="test_case_006",
            type="prompt_regression",
            user_input="测试问题",
            payload={
                "old_prompt": "",
                "new_prompt": "新Prompt",
                "old_output": "旧输出",
                "new_output": "新输出",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.ERROR

    def test_missing_outputs_for_compare(self):
        """比较时缺少输出应返回错误"""
        evaluator = PromptRegressionEvaluator()
        request = EvaluationSchema(
            id="test_case_007",
            type="prompt_regression",
            user_input="测试问题",
            payload={
                "old_prompt": "旧Prompt",
                "new_prompt": "新Prompt",
                "old_output": "",
                "new_output": "新输出",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.ERROR

    def test_missing_baseline_for_drift(self):
        """漂移检测缺少基线应返回错误"""
        evaluator = PromptRegressionEvaluator()
        request = EvaluationSchema(
            id="test_case_008",
            type="prompt_regression",
            user_input="测试问题",
            payload={
                "baseline_output": "",
                "current_output": "当前输出",
                "action": "detect_drift",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.ERROR

    def test_missing_outputs_for_impact(self):
        """影响分析缺少输出应返回错误"""
        evaluator = PromptRegressionEvaluator()
        request = EvaluationSchema(
            id="test_case_009",
            type="prompt_regression",
            user_input="测试问题",
            payload={
                "old_output": "",
                "new_output": "新输出",
                "action": "analyze_impact",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.ERROR

    def test_empty_texts_for_similarity(self):
        """空文本相似度计算应正确处理"""
        evaluator = PromptRegressionEvaluator()
        
        assert evaluator._calculate_similarity("", "") == 1.0
        assert evaluator._calculate_similarity("", "text") == 0.0


class TestPromptRegressionEvaluatorBoundaryCases:
    """边界测试用例"""

    def test_identical_prompts_and_outputs(self):
        """完全相同的Prompt和输出应返回满分"""
        evaluator = PromptRegressionEvaluator()
        request = EvaluationSchema(
            id="test_case_010",
            type="prompt_regression",
            user_input="测试问题",
            payload={
                "old_prompt": "相同的Prompt",
                "new_prompt": "相同的Prompt",
                "old_output": "相同的输出",
                "new_output": "相同的输出",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score >= 0.95

    def test_completely_different_prompts(self):
        """完全不同的Prompt应返回低分"""
        evaluator = PromptRegressionEvaluator()
        request = EvaluationSchema(
            id="test_case_011",
            type="prompt_regression",
            user_input="测试问题",
            payload={
                "old_prompt": "中文Prompt",
                "new_prompt": "English Prompt",
                "old_output": "中文输出",
                "new_output": "English output",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score <= 0.3

    def test_custom_threshold_for_drift(self):
        """自定义漂移阈值应生效"""
        evaluator = PromptRegressionEvaluator()
        request = EvaluationSchema(
            id="test_case_012",
            type="prompt_regression",
            user_input="测试问题",
            payload={
                "baseline_output": "基线",
                "current_output": "略有不同的输出",
                "threshold": 0.1,
                "action": "detect_drift",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.data["threshold"] == 0.1

    def test_regression_passed_when_score_high(self):
        """高分数时应判定回归通过"""
        evaluator = PromptRegressionEvaluator()
        request = EvaluationSchema(
            id="test_case_013",
            type="prompt_regression",
            user_input="测试问题",
            payload={
                "old_prompt": "请回答以下问题：{input}",
                "new_prompt": "请回答以下问题：{input}",
                "old_output": "这是一个详细的回答内容",
                "new_output": "这是一个详细的回答内容",
                "baseline_output": "这是一个详细的回答内容",
                "current_output": "这是一个详细的回答内容",
                "action": "full",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.data["regression_passed"] is True

    def test_structural_drift_detection(self):
        """结构漂移检测应基于长度和句子数"""
        evaluator = PromptRegressionEvaluator()
        result = evaluator._detect_structural_drift("短文本", "非常长的文本内容")
        
        assert 0 < result < 1

    def test_content_drift_detection(self):
        """内容漂移检测应基于词汇差异"""
        evaluator = PromptRegressionEvaluator()
        result = evaluator._detect_content_drift("苹果手机", "香蕉水果")
        
        assert result > 0.5


class TestPromptRegressionEvaluatorIntegration:
    """集成测试用例"""

    def test_evaluator_registered_in_factory(self):
        """评估器应在工厂中注册"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        
        assert "prompt_regression" in EvaluatorFactory.list_evaluators()

    def test_safe_evaluate_returns_error_on_exception(self):
        """异常时应返回错误响应"""
        evaluator = PromptRegressionEvaluator()
        
        with patch.object(evaluator, '_do_evaluate', side_effect=RuntimeError("测试异常")):
            request = EvaluationSchema(
                id="test_case_014",
            type="prompt_regression",
                user_input="测试问题",
                payload={"action": "compare"},
            )
            response = evaluator.safe_evaluate(request)
            
            assert response.evaluation_status == EvaluatorStatus.ERROR

    def test_impact_level_detection(self):
        """影响等级检测应正确"""
        evaluator = PromptRegressionEvaluator()
        
        assert evaluator._get_impact_level(0.95) == "none"
        assert evaluator._get_impact_level(0.75) == "low"
        assert evaluator._get_impact_level(0.55) == "medium"
        assert evaluator._get_impact_level(0.35) == "high"
        assert evaluator._get_impact_level(0.15) == "critical"

    def test_tone_analysis(self):
        """语气分析应检测情感和正式程度"""
        evaluator = PromptRegressionEvaluator()
        tone_positive = evaluator._analyze_tone("太棒了！这是优秀的产品！")
        tone_negative = evaluator._analyze_tone("太差了！这是糟糕的产品！")
        
        assert tone_positive["sentiment"] == "positive"
        assert tone_negative["sentiment"] == "negative"

    def test_format_detection(self):
        """格式检测应识别列表、代码块、表格等"""
        evaluator = PromptRegressionEvaluator()
        
        text_with_list = "- 项目1\n- 项目2"
        text_with_code = "```python\nprint('hello')\n```"
        
        format_list = evaluator._detect_format(text_with_list)
        format_code = evaluator._detect_format(text_with_code)
        
        assert format_list["has_bullet"] is True
        assert format_code["has_code"] is True