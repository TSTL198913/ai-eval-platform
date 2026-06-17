import json
from unittest.mock import MagicMock

from src.domain.evaluators.llm_as_judge import LLMAJudgeEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestLLMAJudgeEvaluator:
    """LLM-as-a-Judge评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_basic(self):
        """测试基本评估"""
        self.mock_client.chat.return_value = json.dumps({
            "scores": {"correctness": {"score": 80, "reason": "基本正确"}},
            "total_score": 80,
            "confidence": 0.8,
        })

        evaluator = LLMAJudgeEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_llm_judge",
            type="llm_as_judge",
            payload={
                "user_input": "什么是AI?",
                "actual_output": "AI是人工智能",
                "dimensions": ["correctness"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.8

    def test_evaluate_with_expected_output(self):
        """测试包含期望输出"""
        self.mock_client.chat.return_value = json.dumps({
            "scores": {
                "correctness": {"score": 90, "reason": "符合期望"},
                "relevance": {"score": 95, "reason": "高度相关"},
            },
            "total_score": 92,
            "confidence": 0.85,
        })

        evaluator = LLMAJudgeEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_expected",
            type="llm_as_judge",
            payload={
                "user_input": "什么是机器学习?",
                "actual_output": "机器学习是AI的一个分支",
                "expected_output": "机器学习是人工智能的一个分支",
                "dimensions": ["correctness", "relevance"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert "llm_judge_scores" in result.data

    def test_evaluate_without_client(self):
        """测试无客户端模式"""
        evaluator = LLMAJudgeEvaluator(None)
        request = EvaluationSchema(
            id="test_no_client",
            type="llm_as_judge",
            payload={
                "user_input": "测试问题",
                "actual_output": "测试回答",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.87

    def test_evaluate_missing_user_input(self):
        """测试缺少用户输入"""
        evaluator = LLMAJudgeEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_missing",
            type="llm_as_judge",
            payload={"actual_output": "回答"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_evaluate_missing_actual_output(self):
        """测试缺少实际输出"""
        evaluator = LLMAJudgeEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_missing",
            type="llm_as_judge",
            payload={"user_input": "问题"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_parse_judge_result_json(self):
        """测试解析JSON结果"""
        evaluator = LLMAJudgeEvaluator(self.mock_client)
        llm_output = json.dumps({
            "scores": {"correctness": {"score": 85, "reason": "测试"}},
            "total_score": 85,
            "confidence": 0.85,
        })

        result = evaluator._parse_judge_result(llm_output, ["correctness"])

        assert result.is_valid is True
        assert result.score == 0.85

    def test_parse_judge_result_fallback(self):
        """测试解析失败回退"""
        evaluator = LLMAJudgeEvaluator(self.mock_client)
        llm_output = "无法解析的结果"

        result = evaluator._parse_judge_result(llm_output, ["correctness"])

        assert result.is_valid is True
        assert result.score == 0.5

    def test_fallback_parse_response(self):
        """测试回退解析响应"""
        evaluator = LLMAJudgeEvaluator(self.mock_client)
        result = evaluator._fallback_parse_response("错误输出", ["correctness", "relevance"])

        assert result.is_valid is True
        assert result.score == 0.5