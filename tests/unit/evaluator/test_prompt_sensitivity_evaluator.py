"""PromptSensitivityEvaluator 单元测试"""

import pytest
from unittest.mock import MagicMock, patch

from src.domain.evaluators.prompt_sensitivity import PromptSensitivityEvaluator, PromptVariant
from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus


class TestPromptSensitivityEvaluatorPositiveCases:
    """正向测试用例"""

    def test_prompt_sensitivity_evaluation_with_default_variants(self):
        """使用默认变体应正确评估Prompt敏感度"""
        evaluator = PromptSensitivityEvaluator()
        request = EvaluationSchema(
            id="test_case_001",
            type="prompt_sensitivity",
            user_input="测试输入问题",
            payload={
                "base_prompt": "请回答用户的问题：{input}",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert 0 <= response.score <= 1.0
        assert "stability_score" in response.data
        assert "sensitivity_level" in response.data

    def test_stable_output_when_variants_produce_similar_results(self):
        """变体产生相似结果时应返回高稳定性分数"""
        evaluator = PromptSensitivityEvaluator()
        custom_variants = [
            PromptVariant(
                name="variant1",
                template="回答问题：{input}",
                variables={"input": "简单问题"},
            ),
            PromptVariant(
                name="variant2",
                template="请回答问题：{input}",
                variables={"input": "简单问题"},
            ),
        ]
        request = EvaluationSchema(
            id="test_case_002",
            type="prompt_sensitivity",
            user_input="简单问题",
            payload={
                "base_prompt": "回答问题：{input}",
                "variants": custom_variants,
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "is_stable" in response.data
        assert "sensitivity_level" in response.data

    def test_custom_variants_are_used(self):
        """自定义变体应被正确使用"""
        evaluator = PromptSensitivityEvaluator()
        custom_variants = [
            PromptVariant(
                name="variant1",
                template="模板1：{input}",
                variables={"input": "测试输入"},
            ),
            PromptVariant(
                name="variant2",
                template="模板2：{input}",
                variables={"input": "测试输入"},
            ),
        ]
        request = EvaluationSchema(
            id="test_case_003",
            type="prompt_sensitivity",
            user_input="测试输入",
            payload={
                "base_prompt": "基础模板",
                "variants": custom_variants,
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.data["variant_count"] == 2

    def test_lexical_variance_calculation(self):
        """词汇方差计算应正确工作"""
        evaluator = PromptSensitivityEvaluator()
        mock_results = [
            {"response": "这是一个简短的回答", "success": True},
            {"response": "这是一个非常非常非常长的详细回答内容", "success": True},
        ]
        result = evaluator._calculate_lexical_variance(mock_results)
        
        assert "length_variance" in result
        assert "vocabulary_diversity" in result
        assert result["length_variance"] > 0

    def test_semantic_variance_calculation(self):
        """语义方差计算应基于关键词重叠"""
        evaluator = PromptSensitivityEvaluator()
        mock_results = [
            {"response": "苹果手机很受欢迎", "success": True},
            {"response": "苹果手机非常流行", "success": True},
        ]
        result = evaluator._calculate_semantic_variance(mock_results)
        
        assert "keyword_overlap" in result
        assert "normalized_variance" in result
        assert result["keyword_overlap"] >= 0

    def test_stylistic_variance_calculation(self):
        """风格方差计算应检测标点和句子长度"""
        evaluator = PromptSensitivityEvaluator()
        mock_results = [
            {"response": "你好！这是测试。", "success": True},
            {"response": "你好这是测试", "success": True},
        ]
        result = evaluator._calculate_stylistic_variance(mock_results)
        
        assert "punctuation_usage" in result
        assert "avg_sentence_length" in result

    def test_recommendations_generation(self):
        """建议生成应基于敏感度分析"""
        evaluator = PromptSensitivityEvaluator()
        analysis = {
            "sensitivity_level": "high",
            "metrics": {
                "lexical": {"normalized_variance": 0.6},
                "semantic": {"keyword_overlap": 0.4},
            },
            "failed_count": 0,
        }
        recommendations = evaluator._generate_recommendations(analysis)
        
        assert len(recommendations) > 0
        assert "Prompt变化" in recommendations[0]

    def test_with_actual_llm_client(self):
        """使用真实LLM客户端时应正确执行"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "模型回答内容"
        
        evaluator = PromptSensitivityEvaluator(client=mock_client)
        custom_variants = [
            PromptVariant(
                name="test_variant",
                template="回答用户的问题",
                variables={},
            ),
        ]
        request = EvaluationSchema(
            id="test_case_004",
            type="prompt_sensitivity",
            payload={
                "base_prompt": "回答用户的问题",
                "variants": custom_variants,
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert mock_client.chat.call_count > 0


class TestPromptSensitivityEvaluatorNegativeCases:
    """负向测试用例"""

    def test_missing_base_prompt(self):
        """缺少基础Prompt应返回错误"""
        evaluator = PromptSensitivityEvaluator()
        request = EvaluationSchema(
            id="test_case_005",
            type="prompt_sensitivity",
            user_input="测试输入",
            payload={},
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.ERROR
        assert "base_prompt" in response.error

    def test_empty_base_prompt(self):
        """空基础Prompt应返回错误"""
        evaluator = PromptSensitivityEvaluator()
        request = EvaluationSchema(
            id="test_case_006",
            type="prompt_sensitivity",
            user_input="测试输入",
            payload={
                "base_prompt": "",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.ERROR

    def test_all_variants_failed(self):
        """所有变体失败时应返回零稳定性分数"""