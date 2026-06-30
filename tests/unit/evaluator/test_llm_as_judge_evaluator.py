"""
LLMAJudgeEvaluator 专项测试
测试目标：验证LLM-as-Judge评估器的6维评分能力、prompt构建、结果解析和加权计算
关键发现：LLMAJudgeEvaluator支持standard/strict/lenient三种评判模式，6个评分维度（accuracy/relevance/safety/coherence/completeness/conciseness），支持few_shot示例
"""

import json
from unittest.mock import MagicMock

import pytest

from src.domain.evaluators.llm_as_judge import JUDGE_DIMENSIONS, SCORE_LEVELS, LLMAJudgeEvaluator
from src.schemas.evaluation import DomainResponse, EvaluationSchema


class TestLLMAJudgeEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def evaluator(self):
        return LLMAJudgeEvaluator()

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = json.dumps(
            {
                "scores": {
                    "accuracy": {
                        "score": 85,
                        "level": "good",
                        "reason": "测试理由",
                        "evidence": ["证据1"],
                        "citation": "无",
                    },
                    "relevance": {
                        "score": 90,
                        "level": "excellent",
                        "reason": "测试理由",
                        "evidence": ["证据1"],
                        "citation": "无",
                    },
                    "safety": {
                        "score": 100,
                        "level": "excellent",
                        "reason": "测试理由",
                        "evidence": ["证据1"],
                        "citation": "无",
                    },
                    "coherence": {
                        "score": 88,
                        "level": "good",
                        "reason": "测试理由",
                        "evidence": ["证据1"],
                        "citation": "无",
                    },
                    "completeness": {
                        "score": 82,
                        "level": "good",
                        "reason": "测试理由",
                        "evidence": ["证据1"],
                        "citation": "无",
                    },
                    "conciseness": {
                        "score": 80,
                        "level": "good",
                        "reason": "测试理由",
                        "evidence": ["证据1"],
                        "citation": "无",
                    },
                },
                "total_score": 87,
                "confidence": 0.85,
                "conflict_detected": False,
                "summary": "测试总结",
                "improvement_suggestions": ["建议1"],
            }
        )
        return client

    def test_evaluate_with_client(self, evaluator, mock_client):
        """有LLM客户端时应正确评估"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="test-1",
            type="llm_as_judge",
            payload={
                "user_input": "测试问题",
                "actual_output": "测试输出",
                "expected_output": "预期输出",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score > 0
        assert "llm_judge_scores" in result.data
        mock_client.chat.assert_called_once()

    def test_evaluate_without_client_uses_mock(self, evaluator):
        """无LLM客户端时应使用mock结果"""
        request = EvaluationSchema(
            id="test-2",
            type="llm_as_judge",
            payload={
                "user_input": "测试问题",
                "actual_output": "测试输出",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score > 0
        assert "llm_judge_scores" in result.data

    def test_evaluate_custom_dimensions(self, evaluator, mock_client):
        """支持自定义评估维度"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="test-3",
            type="llm_as_judge",
            payload={
                "user_input": "测试问题",
                "actual_output": "测试输出",
                "dimensions": ["accuracy", "relevance"],
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert len(result.data["llm_judge_scores"]) >= 2

    def test_evaluate_strict_mode(self, evaluator, mock_client):
        """支持strict评判模式"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="test-4",
            type="llm_as_judge",
            payload={
                "user_input": "测试问题",
                "actual_output": "测试输出",
                "judge_mode": "strict",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "严格" in mock_client.chat.call_args[0][0]

    def test_evaluate_lenient_mode(self, evaluator, mock_client):
        """支持lenient评判模式"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="test-5",
            type="llm_as_judge",
            payload={
                "user_input": "测试问题",
                "actual_output": "测试输出",
                "judge_mode": "lenient",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "宽容" in mock_client.chat.call_args[0][0]

    def test_calculate_weighted_score(self, evaluator):
        """加权分数计算应正确"""
        scores = {
            "accuracy": {"score": 80},
            "relevance": {"score": 90},
            "safety": {"score": 100},
        }
        weighted_score = evaluator._calculate_weighted_score(scores)
        assert isinstance(weighted_score, float)
        assert 0 <= weighted_score <= 100

    def test_parse_judge_result_v2(self, evaluator):
        """解析v2版本评判结果应正确"""
        llm_output = json.dumps(
            {
                "scores": {
                    "accuracy": {
                        "score": 85,
                        "level": "good",
                        "reason": "test",
                        "evidence": [],
                        "citation": "无",
                    }
                },
                "total_score": 85,
                "confidence": 0.8,
                "conflict_detected": False,
                "summary": "Test summary",
                "improvement_suggestions": [],
            }
        )
        result = evaluator._parse_judge_result_v2(llm_output, ["accuracy"])
        assert result.is_valid is True
        assert result.score == 0.85
        assert result.data["score_levels"]["accuracy"] == "good"

    def test_fallback_parse_v2(self, evaluator):
        """fallback解析应返回默认值"""
        result = evaluator._fallback_parse_response_v2("无效输出", ["accuracy", "relevance"])
        assert result.is_valid is False
        assert result.score == 0.0
        assert "raw_output_preview" in result.data

    def test_fallback_parse_response_v2(self, evaluator):
        """fallback响应应暴露解析失败：is_valid=False, score=0.0

        【行为变更】当 LLM 输出完全无法解析时（如纯文本 "Internal Server Error"），
        评估器绝不能静默通过为 0.5 分。必须返回 is_valid=False 让上游告警系统感知到失败。
        详见 tests/meta_evaluation/test_evaluators.py 的【格式崩坏 Case】。
        """
        result = evaluator._fallback_parse_response_v2("无效JSON", ["accuracy"])
        assert result.is_valid is False
        assert result.score == 0.0
        # 必须保留 error 字段说明失败原因
        assert result.error is not None and len(result.error) > 0
        # 必须保留原始输出预览，便于排查
        assert "raw_output_preview" in result.data


class TestLLMAJudgeEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def evaluator(self):
        return LLMAJudgeEvaluator()

    def test_missing_user_input_returns_error(self, evaluator):
        """缺少user_input应返回错误"""
        request = EvaluationSchema(
            id="test-6",
            type="llm_as_judge",
            payload={"actual_output": "测试输出"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert "user_input/text" in result.error

    def test_missing_actual_output_returns_error(self, evaluator):
        """缺少actual_output应返回错误"""
        request = EvaluationSchema(
            id="test-7",
            type="llm_as_judge",
            payload={"user_input": "测试问题"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False

    def test_invalid_json_output_fallback(self, evaluator):
        """LLM返回无效JSON时必须暴露失败，绝不能静默通过为 0.5 分

        【行为变更】旧实现返回 is_valid=True, score=0.5 掩盖了 LLM 服务异常。
        新实现返回 is_valid=False, score=0.0 让上游告警系统能感知到。
        详见 tests/meta_evaluation/test_evaluators.py::TestFormatCorruption。
        """
        mock_client = MagicMock()
        mock_client.chat.return_value = "无效的JSON输出"
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="test-8",
            type="llm_as_judge",
            payload={
                "user_input": "测试问题",
                "actual_output": "测试输出",
            },
        )
        result = evaluator.evaluate(request)
        # 强断言：必须显式标记为失败
        assert result.is_valid is False
        assert result.score == 0.0
        assert result.error is not None


class TestLLMAJudgeEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def evaluator(self):
        return LLMAJudgeEvaluator()

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = json.dumps(
            {
                "scores": {
                    "accuracy": {
                        "score": 80,
                        "level": "good",
                        "reason": "test",
                        "evidence": [],
                        "citation": "无",
                    }
                },
                "total_score": 80,
                "confidence": 0.8,
                "conflict_detected": False,
                "summary": "Test",
                "improvement_suggestions": [],
            }
        )
        return client

    def test_empty_expected_output(self, evaluator):
        """空expected_output应正常处理"""
        mock_client = MagicMock()
        mock_client.chat.return_value = json.dumps(
            {
                "scores": {
                    "accuracy": {
                        "score": 80,
                        "level": "good",
                        "reason": "test",
                        "evidence": [],
                        "citation": "无",
                    }
                },
                "total_score": 80,
                "confidence": 0.8,
                "conflict_detected": False,
                "summary": "Test",
                "improvement_suggestions": [],
            }
        )
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="test-9",
            type="llm_as_judge",
            payload={
                "user_input": "测试问题",
                "actual_output": "测试输出",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_custom_criteria(self, evaluator, mock_client):
        """自定义评估标准应正确传递到prompt"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="test-10",
            type="llm_as_judge",
            payload={
                "user_input": "测试问题",
                "actual_output": "测试输出",
                "criteria": "必须包含关键词",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "必须包含关键词" in mock_client.chat.call_args[0][0]

    def test_zero_score(self, evaluator):
        """零分情况应正确处理"""
        llm_output = json.dumps(
            {
                "scores": {
                    "accuracy": {
                        "score": 0,
                        "level": "very_poor",
                        "reason": "测试",
                        "evidence": [],
                        "citation": "无",
                    }
                },
                "total_score": 0,
                "confidence": 0.5,
                "conflict_detected": False,
                "summary": "零分",
                "improvement_suggestions": [],
            }
        )
        result = evaluator._parse_judge_result_v2(llm_output, ["accuracy"])
        assert result.is_valid is True
        assert result.score == 0.0

    def test_hundred_score(self, evaluator):
        """满分情况应正确处理"""
        llm_output = json.dumps(
            {
                "scores": {
                    "accuracy": {
                        "score": 100,
                        "level": "excellent",
                        "reason": "测试",
                        "evidence": [],
                        "citation": "无",
                    }
                },
                "total_score": 100,
                "confidence": 0.95,
                "conflict_detected": False,
                "summary": "满分",
                "improvement_suggestions": [],
            }
        )
        result = evaluator._parse_judge_result_v2(llm_output, ["accuracy"])
        assert result.is_valid is True
        assert result.score == 1.0


class TestLLMAJudgeEvaluatorIntegration:
    """集成测试"""

    @pytest.fixture
    def evaluator(self):
        return LLMAJudgeEvaluator()

    def test_evaluator_registered(self):
        """LLMAJudgeEvaluator应已注册到工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.domain.evaluators.llm_as_judge import LLMAJudgeEvaluator

        EvaluatorFactory.register("llm_as_judge")(LLMAJudgeEvaluator)

        assert "llm_as_judge" in EvaluatorFactory.list_evaluators()

    def test_safe_evaluate_returns_domain_response(self, evaluator):
        """safe_evaluate应返回DomainResponse"""
        mock_request = MagicMock()
        mock_request.type = "llm_as_judge"
        mock_request.payload = {"user_input": "test", "actual_output": "test"}
        result = evaluator.safe_evaluate(mock_request)
        assert isinstance(result, DomainResponse)

    def test_judge_dimensions_defined(self):
        """JUDGE_DIMENSIONS常量应正确定义"""
        assert len(JUDGE_DIMENSIONS) == 6
        assert "accuracy" in JUDGE_DIMENSIONS
        assert "relevance" in JUDGE_DIMENSIONS
        assert "safety" in JUDGE_DIMENSIONS
        assert "coherence" in JUDGE_DIMENSIONS
        assert "completeness" in JUDGE_DIMENSIONS
        assert "conciseness" in JUDGE_DIMENSIONS

    def test_score_levels_defined(self):
        """SCORE_LEVELS常量应正确定义"""
        assert len(SCORE_LEVELS) == 5
        for _level, (low, high, desc) in SCORE_LEVELS.items():
            assert low <= high
            assert isinstance(desc, str)
