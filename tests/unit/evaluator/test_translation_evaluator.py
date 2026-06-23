"""翻译评估器测试"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.translation import TranslationEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestTranslationEvaluatorPositiveCases:
    """正向测试 - 正常翻译评估"""

    @staticmethod
    def test_translation_with_expected_output():
        """有expected_output时计算相似度"""
        with patch("src.domain.evaluators.embedding_service.EmbeddingService") as mock_cls:
            service_instance = MagicMock()
            service_instance.is_available.return_value = True
            service_instance.calculate_similarity.return_value = 1.0
            mock_cls.get_instance.return_value = service_instance

            evaluator = TranslationEvaluator()
            request = EvaluationSchema(
                id="trans_001",
                type="translation",
                payload={
                    "actual_output": "Hello, world!",
                    "expected_output": "Hello, world!",
                },
            )
            result = evaluator.evaluate(request)
            assert result.is_valid is True
            assert result.score == 1.0

    @staticmethod
    def test_partial_similarity_translation():
        """部分相似翻译"""
        with patch("src.domain.evaluators.embedding_service.EmbeddingService") as mock_cls:
            service_instance = MagicMock()
            service_instance.is_available.return_value = True
            service_instance.calculate_similarity.return_value = 0.7
            mock_cls.get_instance.return_value = service_instance

            evaluator = TranslationEvaluator()
            request = EvaluationSchema(
                id="trans_002",
                type="translation",
                payload={
                    "actual_output": "Hi, world!",
                    "expected_output": "Hello, world!",
                },
            )
            result = evaluator.evaluate(request)
            assert result.is_valid is True
            assert 0.0 <= result.score <= 1.0


class TestTranslationEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @staticmethod
    def test_empty_actual_output_returns_error():
        """空actual_output应返回错误"""
        evaluator = TranslationEvaluator()
        request = EvaluationSchema(
            id="trans_003",
            type="translation",
            payload={"actual_output": "", "expected_output": "Hello"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert "actual_output" in result.error

    @staticmethod
    def test_missing_actual_output_returns_error():
        """缺少actual_output字段应返回错误"""
        evaluator = TranslationEvaluator()
        request = EvaluationSchema(
            id="trans_004",
            type="translation",
            payload={"expected_output": "Hello"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False

    @staticmethod
    def test_missing_expected_output_returns_error():
        """缺少expected_output字段应返回错误"""
        evaluator = TranslationEvaluator()
        request = EvaluationSchema(
            id="trans_005",
            type="translation",
            payload={"actual_output": "Hello"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert "expected_output" in result.error


class TestTranslationEvaluatorBoundaryCases:
    """边界测试"""

    @staticmethod
    def test_identical_translation_gets_full_score():
        """完全相同翻译得满分"""
        with patch("src.domain.evaluators.embedding_service.EmbeddingService") as mock_cls:
            service_instance = MagicMock()
            service_instance.is_available.return_value = True
            service_instance.calculate_similarity.return_value = 1.0
            mock_cls.get_instance.return_value = service_instance

            evaluator = TranslationEvaluator()
            request = EvaluationSchema(
                id="trans_006",
                type="translation",
                payload={
                    "actual_output": "Hello",
                    "expected_output": "Hello",
                },
            )
            result = evaluator.evaluate(request)
            assert result.is_valid is True
            assert result.score == 1.0

    @staticmethod
    def test_different_translation_gets_low_score():
        """不同翻译得低分"""
        with patch("src.domain.evaluators.embedding_service.EmbeddingService") as mock_cls:
            service_instance = MagicMock()
            service_instance.is_available.return_value = True
            service_instance.calculate_similarity.return_value = 0.1
            mock_cls.get_instance.return_value = service_instance

            evaluator = TranslationEvaluator()
            request = EvaluationSchema(
                id="trans_007",
                type="translation",
                payload={
                    "actual_output": "Goodbye",
                    "expected_output": "Hello",
                },
            )
            result = evaluator.evaluate(request)
            assert result.is_valid is True
            assert result.score < 0.5
