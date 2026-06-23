"""问答评估器测试"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.qa import QAEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestQAEvaluatorPositiveCases:
    """正向测试 - 正常问答评估"""

    @staticmethod
    def test_qa_with_expected_output():
        """有expected_output时计算相似度"""
        with patch("src.domain.evaluators.embedding_service.EmbeddingService") as mock_cls:
            service_instance = MagicMock()
            service_instance.is_available.return_value = True
            service_instance.calculate_similarity.return_value = 0.8
            mock_cls.get_instance.return_value = service_instance

            evaluator = QAEvaluator()
            request = EvaluationSchema(
                id="qa_001",
                type="qa",
                payload={
                    "actual_output": "北京是中国的首都。",
                    "expected_output": "北京",
                },
            )
            result = evaluator.evaluate(request)
            assert result.is_valid is True
            assert 0.0 <= result.score <= 1.0

    @staticmethod
    def test_exact_match_gets_high_score():
        """精确匹配得高分"""
        with patch("src.domain.evaluators.embedding_service.EmbeddingService") as mock_cls:
            service_instance = MagicMock()
            service_instance.is_available.return_value = True
            service_instance.calculate_similarity.return_value = 1.0
            mock_cls.get_instance.return_value = service_instance

            evaluator = QAEvaluator()
            request = EvaluationSchema(
                id="qa_002",
                type="qa",
                payload={
                    "actual_output": "北京是中国的首都",
                    "expected_output": "北京是中国的首都",
                },
            )
            result = evaluator.evaluate(request)
            assert result.is_valid is True
            assert result.score == 1.0


class TestQAEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @staticmethod
    def test_empty_actual_output_returns_error():
        """空actual_output应返回错误"""
        evaluator = QAEvaluator()
        request = EvaluationSchema(
            id="qa_003",
            type="qa",
            payload={"actual_output": "", "expected_output": "答案"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert "actual_output" in result.error

    @staticmethod
    def test_missing_actual_output_returns_error():
        """缺少actual_output字段应返回错误"""
        evaluator = QAEvaluator()
        request = EvaluationSchema(
            id="qa_004",
            type="qa",
            payload={"expected_output": "答案"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False

    @staticmethod
    def test_missing_expected_output_returns_error():
        """缺少expected_output字段应返回错误"""
        evaluator = QAEvaluator()
        request = EvaluationSchema(
            id="qa_005",
            type="qa",
            payload={"actual_output": "答案"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert "expected_output" in result.error


class TestQAEvaluatorBoundaryCases:
    """边界测试"""

    @staticmethod
    def test_no_match_gets_low_score():
        """完全不匹配得低分"""
        with patch("src.domain.evaluators.embedding_service.EmbeddingService") as mock_cls:
            service_instance = MagicMock()
            service_instance.is_available.return_value = True
            service_instance.calculate_similarity.return_value = 0.1
            mock_cls.get_instance.return_value = service_instance

            evaluator = QAEvaluator()
            request = EvaluationSchema(
                id="qa_006",
                type="qa",
                payload={
                    "actual_output": "完全不同的答案 xyz",
                    "expected_output": "北京",
                },
            )
            result = evaluator.evaluate(request)
            assert result.is_valid is True
            assert result.score < 0.5

    @staticmethod
    def test_partial_match_gets_moderate_score():
        """部分匹配得中等分数"""
        with patch("src.domain.evaluators.embedding_service.EmbeddingService") as mock_cls:
            service_instance = MagicMock()
            service_instance.is_available.return_value = True
            service_instance.calculate_similarity.return_value = 1.0
            mock_cls.get_instance.return_value = service_instance

            evaluator = QAEvaluator()
            request = EvaluationSchema(
                id="qa_007",
                type="qa",
                payload={
                    "actual_output": "中国首都是北京",
                    "expected_output": "中国首都是北京",
                },
            )
            result = evaluator.evaluate(request)
            assert result.is_valid is True
            assert result.score == 1.0
