"""
🧪 tests/integration/api/test_new_evaluator_api_integration.py
新评估器 API 集成测试 - standard_metric / ragas / deepeval / multi_metric

测试目标：验证新的标准指标评估器、RAGAS/DeepEval 适配器
通过统一 /api/v1/evaluate 端点的完整集成。
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """FastAPI 测试客户端"""
    from src.api.server import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_idempotency_checker():
    """Mock 幂等性检查器（自动应用）"""
    with patch("src.api.routes.evaluation_routes._get_idempotency_checker", create=True) as mock:
        checker = MagicMock()
        checker.get_cached_result.return_value = None
        checker.mark_processing.return_value = True
        checker.mark_processed.return_value = None
        checker.clear.return_value = None
        mock.return_value = checker
        yield checker


def _post_evaluate(client, eval_id, eval_type, payload):
    """辅助函数：调用 evaluate 端点"""
    return client.post(
        "/api/v1/evaluate",
        json={
            "id": eval_id,
            "type": eval_type,
            "payload": payload,
        },
    )


# ==================== standard_metric 端点集成测试 ====================


class TestStandardMetricEndpoint:
    """标准指标评估器 API 端点测试"""

    def test_evaluate_bleu_4_perfect_match(self, client):
        """BLEU-4 完全匹配 - 1.0"""
        response = _post_evaluate(
            client,
            "sm-bleu-1",
            "standard_metric",
            {
                "user_input": "测试输入",
                "actual_output": "the cat is on the mat",
                "expected_output": "the cat is on the mat",
                "metric": "BLEU-4",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        result = data["data"]
        assert result["evaluation_status"] == "passed"
        assert result["data"]["is_valid"] is True
        assert result["data"]["score"] >= 0.95

    def test_evaluate_rouge_l_high_overlap(self, client):
        """ROUGE-L 高重合"""
        response = _post_evaluate(
            client,
            "sm-rouge-1",
            "standard_metric",
            {
                "user_input": "test",
                "actual_output": "Paris is the capital of France",
                "expected_output": "Paris is the capital of France",
                "metric": "ROUGE-L",
            },
        )
        assert response.status_code == 200
        result = response.json()["data"]
        assert result["data"]["score"] >= 0.95

    def test_evaluate_levenshtein_exact(self, client):
        """Levenshtein 精确匹配"""
        response = _post_evaluate(
            client,
            "sm-lev-1",
            "standard_metric",
            {
                "user_input": "test",
                "actual_output": "hello",
                "expected_output": "hello",
                "metric": "Levenshtein",
            },
        )
        assert response.status_code == 200
        result = response.json()["data"]
        assert result["data"]["score"] == 1.0

    def test_evaluate_f1_token(self, client):
        """F1-Token 评估"""
        response = _post_evaluate(
            client,
            "sm-f1-1",
            "standard_metric",
            {
                "user_input": "test",
                "actual_output": "Python is a programming language",
                "expected_output": "Python is a programming language",
                "metric": "F1-Token",
            },
        )
        assert response.status_code == 200
        result = response.json()["data"]
        assert result["data"]["is_valid"] is True
        assert result["data"]["score"] >= 0.9

    def test_evaluate_unsupported_metric_returns_error(self, client):
        """不支持的指标 - 返回错误"""
        response = _post_evaluate(
            client,
            "sm-unsup-1",
            "standard_metric",
            {
                "user_input": "test",
                "actual_output": "text",
                "expected_output": "text",
                "metric": "NONEXISTENT_METRIC_XYZ",
            },
        )
        assert response.status_code == 200
        result = response.json()["data"]
        # 应返回 invalid
        assert result["data"]["is_valid"] is False


# ==================== multi_metric 端点集成测试 ====================


class TestMultiMetricEndpoint:
    """多指标综合评估器 API 端点测试"""

    def test_evaluate_all_metrics(self, client):
        """多指标综合评估"""
        response = _post_evaluate(
            client,
            "mm-1",
            "multi_metric",
            {
                "user_input": "test",
                "actual_output": "Paris is the capital of France",
                "expected_output": "Paris is the capital of France",
            },
        )
        assert response.status_code == 200
        result = response.json()["data"]["data"]
        assert result["is_valid"] is True
        assert "metrics" in result["data"]
        assert "composite_score" in result["data"]
        assert result["data"]["metric_count"] > 0

    def test_evaluate_with_selected_metrics(self, client):
        """选择性指标评估"""
        response = _post_evaluate(
            client,
            "mm-2",
            "multi_metric",
            {
                "user_input": "test",
                "actual_output": "the quick brown fox",
                "expected_output": "the quick brown fox",
                "metrics": ["BLEU-4", "ROUGE-L", "F1-Token"],
            },
        )
        assert response.status_code == 200
        result = response.json()["data"]["data"]
        assert result["data"]["metric_count"] == 3
        assert "BLEU-4" in result["data"]["metrics"]
        assert "ROUGE-L" in result["data"]["metrics"]
        assert "F1-Token" in result["data"]["metrics"]


# ==================== RAGAS 评估器端点集成测试 ====================


class TestRAGASEvaluatorEndpoint:
    """RAGAS 评估器 API 端点测试"""

    def test_evaluate_ragas_with_all_inputs(self, client):
        """RAGAS 全量输入评估"""
        response = _post_evaluate(
            client,
            "ragas-1",
            "ragas",
            {
                "user_input": "什么是 RAG?",
                "answer": "RAG 是检索增强生成",
                "context": "RAG 是 Retrieval-Augmented Generation 的缩写",
                "ground_truth": "RAG 是检索增强生成技术",
            },
        )
        assert response.status_code == 200
        result = response.json()["data"]["data"]
        assert result["is_valid"] is True
        metrics = result["data"]["metrics"]
        assert "faithfulness" in metrics
        assert "answer_relevancy" in metrics
        assert "context_precision" in metrics

    def test_evaluate_ragas_missing_answer_returns_error(self, client):
        """RAGAS 缺失 answer - 返回错误"""
        response = _post_evaluate(
            client,
            "ragas-2",
            "ragas",
            {
                "user_input": "什么是 RAG?",
                "answer": "",
            },
        )
        assert response.status_code == 200
        result = response.json()["data"]["data"]
        assert result["is_valid"] is False
        assert "answer" in result["error"].lower()

    def test_evaluate_ragas_with_selective_metrics(self, client):
        """RAGAS 选择性指标"""
        response = _post_evaluate(
            client,
            "ragas-3",
            "ragas",
            {
                "user_input": "什么是 RAG?",
                "answer": "RAG 是检索增强生成",
                "context": "RAG 是 Retrieval-Augmented Generation 的缩写",
                "ground_truth": "RAG 是检索增强生成技术",
                "metrics": ["faithfulness", "answer_relevancy"],
            },
        )
        assert response.status_code == 200
        result = response.json()["data"]["data"]
        assert result["is_valid"] is True
        metrics = result["data"]["metrics"]
        # 应只返回指定的两个
        assert set(metrics.keys()) == {"faithfulness", "answer_relevancy"}


# ==================== DeepEval 评估器端点集成测试 ====================


class TestDeepEvalEvaluatorEndpoint:
    """DeepEval 评估器 API 端点测试"""

    def test_evaluate_deepeval_hallucination(self, client):
        """DeepEval 幻觉检测"""
        response = _post_evaluate(
            client,
            "deepeval-1",
            "deepeval",
            {
                "user_input": "Python 是什么?",
                "answer": "Python 是一种编程语言",
                "context": "Python 是一种广泛使用的解释型编程语言",
                "ground_truth": "Python 是一种解释型编程语言",
            },
        )
        assert response.status_code == 200
        result = response.json()["data"]["data"]
        assert result["is_valid"] is True
        # 至少应包含 hallucination 指标
        if "metrics" in result["data"]:
            assert "hallucination" in result["data"]["metrics"]

    def test_evaluate_deepeval_missing_answer(self, client):
        """DeepEval 缺失 answer - 返回错误"""
        response = _post_evaluate(
            client,
            "deepeval-2",
            "deepeval",
            {
                "user_input": "Python 是什么?",
                "answer": "",
            },
        )
        assert response.status_code == 200
        result = response.json()["data"]["data"]
        assert result["is_valid"] is False


# ==================== 端到端综合场景测试 ====================


class TestEndToEndEvaluatorScenarios:
    """端到端评估场景"""

    def test_multi_evaluator_pipeline(self, client):
        """多评估器流水线 - 同一输入多视角评估"""
        text_input = "什么是 Python?"
        actual = "Python 是一种解释型、面向对象、动态数据类型的高级编程语言。"
        expected = "Python 是一种广泛使用的解释型编程语言。"

        results = {}

        # 1. 标准指标
        resp = _post_evaluate(
            client,
            "e2e-1",
            "standard_metric",
            {
                "user_input": text_input,
                "actual_output": actual,
                "expected_output": expected,
                "metric": "ROUGE-L",
            },
        )
        assert resp.status_code == 200
        results["rouge_l"] = resp.json()["data"]["data"]["score"]

        # 2. F1-Token
        resp = _post_evaluate(
            client,
            "e2e-2",
            "standard_metric",
            {
                "user_input": text_input,
                "actual_output": actual,
                "expected_output": expected,
                "metric": "F1-Token",
            },
        )
        assert resp.status_code == 200
        results["f1_token"] = resp.json()["data"]["data"]["score"]

        # 3. 所有分数应在 0-1 区间
        for name, score in results.items():
            assert 0.0 <= score <= 1.0, f"{name} 分数越界: {score}"
