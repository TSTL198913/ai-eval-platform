"""
多领域评测器集成测试
测试不同领域的评测器功能
"""

from unittest.mock import MagicMock

import pytest

from src.domain.evaluators.base import EvaluatorFactory
from src.domain.evaluators.code import CodeEvaluator
from src.domain.evaluators.finance import FinanceEvaluator
from src.domain.evaluators.qa import QAEvaluator
from src.domain.evaluators.security import SecurityEvaluator
from src.domain.evaluators.translation import TranslationEvaluator
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@pytest.fixture
def mock_client():
    """Mock LLM客户端"""
    client = MagicMock()
    client.config = MagicMock()
    client.config.model_name = "test-model"
    return client


class TestFinanceEvaluatorIntegration:
    """金融评测器集成测试"""

    def test_finance_calculation_accuracy(self, mock_client):
        """测试金融计算准确性"""
        mock_client.chat.return_value = "利息为30元"
        evaluator = FinanceEvaluator(mock_client)

        request = EvaluationSchema(
            id="finance_001",
            type="finance",
            payload={
                "user_input": "计算1000元一年期3%利息",
                "expected_output": "30",
            },
            metadata={},
        )

        response = evaluator.evaluate(request)

        assert response.is_valid is True
        assert response.score >= 0.8

    def test_finance_complex_calculation(self, mock_client):
        """测试复杂金融计算"""
        mock_client.chat.return_value = "本金1000元，利息30元，总计1030元"
        evaluator = FinanceEvaluator(mock_client)

        request = EvaluationSchema(
            id="finance_002",
            type="finance",
            payload={
                "user_input": "计算1000元本金，3%年利率，一年后的本息总额",
                "expected_output": "1030",
            },
            metadata={},
        )

        response = evaluator.evaluate(request)
        assert response is not None

    def test_finance_error_handling(self, mock_client):
        """测试金融评测器错误处理"""
        mock_client.chat.side_effect = Exception("LLM error")
        evaluator = FinanceEvaluator(mock_client)

        request = EvaluationSchema(
            id="finance_error",
            type="finance",
            payload={"user_input": "test", "expected_output": "test"},
            metadata={},
        )

        # 应该能够处理错误而不崩溃
        try:
            response = evaluator.evaluate(request)
        except Exception as e:
            assert "LLM" in str(e) or "error" in str(e)


class TestCodeEvaluatorIntegration:
    """代码评测器集成测试"""

    def test_code_syntax_validation(self, mock_client):
        """测试代码语法验证"""
        mock_client.chat.return_value = "代码语法正确"
        evaluator = CodeEvaluator(mock_client)

        request = EvaluationSchema(
            id="code_001",
            type="code",
            payload={
                "user_input": "def hello():\n    print('Hello')",
                "expected_output": "valid",
            },
            metadata={},
        )

        response = evaluator.evaluate(request)
        assert response is not None

    def test_code_execution_result(self, mock_client):
        """测试代码执行结果"""
        mock_client.chat.return_value = "输出：Hello"
        evaluator = CodeEvaluator(mock_client)

        request = EvaluationSchema(
            id="code_002",
            type="code",
            payload={
                "user_input": "print('Hello')",
                "expected_output": "Hello",
            },
            metadata={},
        )

        response = evaluator.evaluate(request)
        assert response is not None

    def test_code_multiple_languages(self, mock_client):
        """测试多语言代码评测"""
        evaluator = CodeEvaluator(mock_client)

        languages = [
            ("python", "def test(): pass"),
            ("javascript", "function test() {}"),
            ("java", "public class Test {}"),
        ]

        for lang, code in languages:
            mock_client.chat.return_value = f"{lang} code is valid"
            request = EvaluationSchema(
                id=f"code_{lang}",
                type="code",
                payload={"user_input": code, "expected_output": "valid"},
                metadata={"language": lang},
            )

            response = evaluator.evaluate(request)
            assert response is not None


class TestQAEvaluatorIntegration:
    """问答评测器集成测试"""

    def test_qa_accuracy(self, mock_client):
        """测试问答准确性"""
        mock_client.chat.return_value = "答案是正确的"
        evaluator = QAEvaluator(mock_client)

        request = EvaluationSchema(
            id="qa_001",
            type="qa",
            payload={
                "user_input": "什么是Python？",
                "expected_output": "Python是一种编程语言",
            },
            metadata={},
        )

        response = evaluator.evaluate(request)
        assert response is not None

    def test_qa_semantic_similarity(self, mock_client):
        """测试问答语义相似度"""
        mock_client.chat.return_value = "Python是一门流行的编程语言"
        evaluator = QAEvaluator(mock_client)

        request = EvaluationSchema(
            id="qa_002",
            type="qa",
            payload={
                "user_input": "Python是什么？",
                "expected_output": "编程语言",
            },
            metadata={},
        )

        response = evaluator.evaluate(request)
        assert response is not None


class TestSecurityEvaluatorIntegration:
    """安全评测器集成测试"""

    def test_security_vulnerability_detection(self, mock_client):
        """测试安全漏洞检测"""
        mock_client.chat.return_value = "检测到潜在的安全漏洞"
        evaluator = SecurityEvaluator(mock_client)

        request = EvaluationSchema(
            id="security_001",
            type="security",
            payload={
                "user_input": "SELECT * FROM users WHERE id = " + "1; DROP TABLE users;--",
                "expected_output": "vulnerability_detected",
            },
            metadata={},
        )

        response = evaluator.evaluate(request)
        assert response is not None

    def test_security_safe_code(self, mock_client):
        """测试安全代码检测"""
        mock_client.chat.return_value = "代码安全，无漏洞"
        evaluator = SecurityEvaluator(mock_client)

        request = EvaluationSchema(
            id="security_002",
            type="security",
            payload={
                "user_input": "def safe_function(): return 'safe'",
                "expected_output": "safe",
            },
            metadata={},
        )

        response = evaluator.evaluate(request)
        assert response is not None


class TestTranslationEvaluatorIntegration:
    """翻译评测器集成测试"""

    def test_translation_accuracy(self, mock_client):
        """测试翻译准确性"""
        mock_client.chat.return_value = "Hello World"
        evaluator = TranslationEvaluator(mock_client)

        request = EvaluationSchema(
            id="translation_001",
            type="translation",
            payload={
                "user_input": "你好世界",
                "expected_output": "Hello World",
                "source_lang": "zh",
                "target_lang": "en",
            },
            metadata={},
        )

        response = evaluator.evaluate(request)
        assert response is not None

    def test_translation_multiple_languages(self, mock_client):
        """测试多语言翻译"""
        evaluator = TranslationEvaluator(mock_client)

        translations = [
            ("zh", "en", "你好", "Hello"),
            ("en", "zh", "Hello", "你好"),
            ("zh", "ja", "你好", "こんにちは"),
        ]

        for src, tgt, input_text, expected in translations:
            mock_client.chat.return_value = expected
            request = EvaluationSchema(
                id=f"trans_{src}_{tgt}",
                type="translation",
                payload={
                    "user_input": input_text,
                    "expected_output": expected,
                    "source_lang": src,
                    "target_lang": tgt,
                },
                metadata={},
            )

            response = evaluator.evaluate(request)
            assert response is not None


class TestEvaluatorFactoryIntegration:
    """评测器工厂集成测试"""

    def test_factory_creates_all_evaluators(self, mock_client):
        """测试工厂创建所有评测器"""
        domains = ["finance", "code", "qa", "security", "translation", "general", "text"]

        for domain in domains:
            evaluator = EvaluatorFactory.get(domain, client=mock_client)
            assert evaluator is not None

    def test_factory_invalid_domain(self):
        """测试工厂无效领域"""
        with pytest.raises(ValueError):
            EvaluatorFactory.get("invalid_domain", client=mock_client)

    def test_factory_evaluator_consistency(self, mock_client):
        """测试工厂评测器一致性"""
        # 同一领域应该返回相同类型的评测器
        evaluator1 = EvaluatorFactory.get("finance", client=mock_client)
        evaluator2 = EvaluatorFactory.get("finance", client=mock_client)

        assert type(evaluator1) == type(evaluator2)


class TestMultiDomainIntegration:
    """多领域集成测试"""

    def test_cross_domain_evaluation(self, mock_client):
        """测试跨领域评测"""
        domains = ["finance", "code", "qa"]

        results = []
        for domain in domains:
            evaluator = EvaluatorFactory.get(domain, client=mock_client)
            mock_client.chat.return_value = f"{domain} response"

            request = EvaluationSchema(
                id=f"cross_{domain}",
                type=domain,
                payload={"user_input": "test", "expected_output": "test"},
                metadata={},
            )

            response = evaluator.evaluate(request)
            results.append(response)

        # 所有领域都应该成功评测
        assert len(results) == 3
        for result in results:
            assert result is not None

    def test_domain_specific_scoring(self, mock_client):
        """测试领域特定评分"""
        # 不同领域应该有不同的评分机制
        domains_scores = {}

        for domain in ["finance", "code", "qa"]:
            evaluator = EvaluatorFactory.get(domain, client=mock_client)
            mock_client.chat.return_value = "test response"

            request = EvaluationSchema(
                id=f"score_{domain}",
                type=domain,
                payload={"user_input": "test", "expected_output": "test"},
                metadata={},
            )

            response = evaluator.evaluate(request)
            domains_scores[domain] = response.score

        # 各领域应该都有评分
        assert len(domains_scores) == 3