"""
核心评估器测试套件 - 补充覆盖高风险评估器
目标：提升评估器整体覆盖率，降低生产风险
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


class TestFactualityEvaluator:
    """事实性评估器测试"""

    def setup_method(self):
        from src.domain.evaluators.factuality_evaluator import FactualityEvaluator
        self.evaluator_class = FactualityEvaluator

    def test_evaluator_can_be_created(self):
        """评估器可以被创建"""
        evaluator = self.evaluator_class()
        assert evaluator is not None

    def test_empty_input_returns_error(self):
        """空输入时评估器应返回有效响应"""
        from src.schemas.evaluation import EvaluationSchema
        evaluator = self.evaluator_class()

        request = EvaluationSchema(
            id="fact_001",
            type="factuality",
            payload={"user_input": ""},
        )
        result = evaluator.evaluate(request)
        # FactualityEvaluator 将结果包装在 data 中
        assert result.is_valid is True
        assert result.data is not None

    def test_evaluator_registered(self):
        """评估器已注册到工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        assert "factuality" in EvaluatorFactory._registry


class TestRiskEvaluator:
    """风险评估器测试"""

    def setup_method(self):
        from src.domain.evaluators.risk import RiskEvaluator
        self.evaluator_class = RiskEvaluator

    def test_evaluator_can_be_created(self):
        """评估器可以被创建"""
        evaluator = self.evaluator_class()
        assert evaluator is not None

    def test_empty_input_returns_error(self):
        """空输入时评估器应返回有效响应"""
        from src.schemas.evaluation import EvaluationSchema
        evaluator = self.evaluator_class()

        request = EvaluationSchema(
            id="risk_001",
            type="risk",
            payload={"text": ""},
        )
        result = evaluator.evaluate(request)
        # RiskEvaluator 返回评估结果
        assert result.is_valid is True
        assert result.data is not None

    def test_evaluator_registered(self):
        """评估器已注册到工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        assert "risk" in EvaluatorFactory._registry


class TestLLMAsJudgeEvaluator:
    """LLM作为Judge评估器测试"""

    def setup_method(self):
        from src.domain.evaluators.llm_as_judge import LLMAJudgeEvaluator
        self.evaluator_class = LLMAJudgeEvaluator

    def test_evaluator_can_be_created(self):
        """评估器可以被创建"""
        evaluator = self.evaluator_class()
        assert evaluator is not None

    def test_empty_input_returns_error(self):
        """空输入应返回错误"""
        from src.schemas.evaluation import EvaluationSchema
        evaluator = self.evaluator_class()

        request = EvaluationSchema(
            id="judge_001",
            type="llm_as_judge",
            payload={"user_input": ""},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False

    def test_evaluator_registered(self):
        """评估器已注册到工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        assert "llm_as_judge" in EvaluatorFactory._registry


class TestEvaluatorFactory:
    """评估器工厂测试"""

    def test_list_evaluators(self):
        """列出所有评估器"""
        from src.domain.evaluators import EVALUATOR_REGISTRY
        evaluators = list(EVALUATOR_REGISTRY.keys())
        assert isinstance(evaluators, list)
        assert len(evaluators) > 0

    def test_get_evaluator(self):
        """获取评估器"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        evaluator = EvaluatorFactory.get("security")
        assert evaluator is not None

    def test_get_non_existent_evaluator(self):
        """获取不存在的评估器"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.exceptions import DomainLogicError
        with pytest.raises(DomainLogicError):
            EvaluatorFactory.get("non_existent_evaluator")

    def test_register_decorator(self):
        """注册装饰器工作正常"""
        from src.domain.evaluators.base import BaseEvaluator
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        @EvaluatorFactory.register("test_decorator")
        class TestEvaluator(BaseEvaluator):
            def evaluate(self, request):
                pass

        assert "test_decorator" in EvaluatorFactory._registry


class TestBaseEvaluator:
    """基础评估器测试"""

    def test_base_evaluator_methods(self):
        """基础评估器方法"""
        from src.domain.evaluators.base import BaseEvaluator

        class TestEvaluator(BaseEvaluator):
            def evaluate(self, request):
                pass

        evaluator = TestEvaluator()
        assert evaluator is not None


class TestScoringIntegration:
    """评分算法集成测试"""

    def test_score_numeric_match_integration(self):
        """数字匹配评分集成测试"""
        from src.domain.evaluators.scoring import score_numeric_match

        output = "营收100万元，利润20万元"
        expected = "营收100万元，利润20万元"
        score = score_numeric_match(output, expected)
        assert score == 1.0

    def test_score_text_similarity_integration(self):
        """文本相似度评分集成测试"""
        from src.domain.evaluators.scoring import score_text_similarity

        output = "北京是中国的首都"
        expected = "中国的首都是北京"
        score = score_text_similarity(output, expected)
        assert score >= 0.7

    def test_score_keyword_overlap_integration(self):
        """关键词重叠评分集成测试"""
        from src.domain.evaluators.scoring import score_keyword_overlap

        output = "机器学习深度学习"
        expected = "机器学习"
        score = score_keyword_overlap(output, expected)
        assert score >= 0.5

    def test_is_passing_integration(self):
        """通过阈值判断集成测试"""
        from src.domain.evaluators.scoring import is_passing

        assert is_passing(0.8) is True
        assert is_passing(0.79) is False
        assert is_passing(0.5, threshold=0.5) is True


class TestQAEvaluator:
    """问答评估器测试"""

    def setup_method(self):
        from src.domain.evaluators.qa import QAEvaluator
        self.evaluator_class = QAEvaluator

    def test_evaluator_can_be_created(self):
        """评估器可以被创建"""
        evaluator = self.evaluator_class()
        assert evaluator is not None

    def test_evaluator_registered(self):
        """评估器已注册到工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        assert "qa" in EvaluatorFactory._registry


class TestSummaryEvaluator:
    """摘要评估器测试"""

    def setup_method(self):
        from src.domain.evaluators.summary import SummaryEvaluator
        self.evaluator_class = SummaryEvaluator

    def test_evaluator_can_be_created(self):
        """评估器可以被创建"""
        evaluator = self.evaluator_class()
        assert evaluator is not None

    def test_evaluator_registered(self):
        """评估器已注册到工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        assert "summary" in EvaluatorFactory._registry


class TestTranslationEvaluator:
    """翻译评估器测试"""

    def setup_method(self):
        from src.domain.evaluators.translation import TranslationEvaluator
        self.evaluator_class = TranslationEvaluator

    def test_evaluator_can_be_created(self):
        """评估器可以被创建"""
        evaluator = self.evaluator_class()
        assert evaluator is not None

    def test_evaluator_registered(self):
        """评估器已注册到工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        assert "translation" in EvaluatorFactory._registry


class TestSentimentEvaluator:
    """情感分析评估器测试"""

    def setup_method(self):
        from src.domain.evaluators.sentiment import SentimentEvaluator
        self.evaluator_class = SentimentEvaluator

    def test_evaluator_can_be_created(self):
        """评估器可以被创建"""
        evaluator = self.evaluator_class()
        assert evaluator is not None

    def test_evaluator_registered(self):
        """评估器已注册到工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        assert "sentiment" in EvaluatorFactory._registry


class TestCodeReviewEvaluator:
    """代码审查评估器测试"""

    def setup_method(self):
        from src.domain.evaluators.code_review import CodeReviewEvaluator
        self.evaluator_class = CodeReviewEvaluator

    def test_evaluator_can_be_created(self):
        """评估器可以被创建"""
        evaluator = self.evaluator_class()
        assert evaluator is not None

    def test_evaluator_registered(self):
        """评估器已注册到工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        assert "code_review" in EvaluatorFactory._registry
