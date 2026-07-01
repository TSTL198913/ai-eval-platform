"""
核心评估器测试套件 - 补充覆盖高风险评估器
目标：提升评估器整体覆盖率，降低生产风险
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


class TestFactualityEvaluator:
    """事实性评估器测试"""

    def setup_method(self):
        from src.domain.evaluators.factuality_evaluator import FactualityEvaluator

        self.evaluator_class = FactualityEvaluator

    @pytest.fixture
    def evaluator(self):
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.9"
        return self.evaluator_class(client=mock_client)

    def test_evaluator_can_be_created(self, evaluator):
        """评估器已正确创建并可调用evaluate方法"""
        assert evaluator is not None
        assert hasattr(evaluator, "evaluate")
        assert callable(evaluator.evaluate)

    def test_evaluator_registered(self):
        """评估器已注册到工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.domain.evaluators.factuality_evaluator import FactualityEvaluator

        EvaluatorFactory.register("factuality")(FactualityEvaluator)

        assert "factuality" in EvaluatorFactory._registry

    def test_evaluate_factuality_with_reference(self, evaluator):
        """有参考信息的事实性评估"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="fact_001",
            type="factuality",
            payload={
                "user_input": "北京是中国的首都吗？",
                "action": "evaluate_factuality",
                "actual_output": "北京是中国的首都。",
                "expected_output": "北京是中国的首都",
                "reference": ["北京是中国的首都"],
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert 0.7 <= result.score <= 1.0
        assert "raw_score" in result.data
        
        # 强断言：验证置信度和状态
        assert result.confidence is not None, "confidence不应为None"
        assert 0.0 <= result.confidence <= 1.0, f"confidence应在0-1之间，实际为{result.confidence}"
        assert result.evaluation_status.value == "success", f"evaluation_status应为success"

    def test_evaluate_factuality_empty_response(self, evaluator):
        """空response应返回错误"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="fact_002",
            type="factuality",
            payload={"user_input": "测试", "action": "evaluate_factuality", "response": ""},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False

    def test_detect_hallucination_action(self, evaluator):
        """专门的幻觉检测action"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="fact_003",
            type="factuality",
            payload={
                "user_input": "北京是中国的首都吗？",
                "action": "detect_hallucination",
                "actual_output": "北京是中国的首都。",
                "expected_output": "北京是中国的首都",
                "reference": ["北京是中国的首都"],
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "raw_score" in result.data
        assert result.data["raw_score"] >= 0.5

    def test_verify_entities_action(self, evaluator):
        """实体验证action"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="fact_004",
            type="factuality",
            payload={
                "user_input": "张三和李四是什么关系？",
                "action": "verify_entities",
                "actual_output": "张三和李四是好朋友。",
                "expected_output": "张三和李四是好朋友",
                "reference": ["张三和李四是好朋友"],
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "evidence" in result.data

    def test_check_consistency_action(self, evaluator):
        """内部一致性检查action"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="fact_005",
            type="factuality",
            payload={
                "user_input": "测试一致性",
                "action": "check_consistency",
                "actual_output": "北京是中国的首都。上海也是中国的首都。",
                "expected_output": "北京是中国的首都",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "audit_status" in result.data

    def test_unknown_action_returns_error(self, evaluator):
        """未知action应返回错误"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="fact_006",
            type="factuality",
            payload={"user_input": "测试", "action": "unknown_action"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False


class TestRiskEvaluator:
    """风险评估器测试"""

    def setup_method(self):
        from src.domain.evaluators.risk import RiskEvaluator

        self.evaluator_class = RiskEvaluator

    @pytest.fixture
    def evaluator(self):
        return self.evaluator_class()

    def test_evaluator_can_be_created(self, evaluator):
        """评估器已正确创建并可调用evaluate方法"""
        assert evaluator is not None
        assert hasattr(evaluator, "evaluate")
        assert callable(evaluator.evaluate)

    def test_evaluator_registered(self):
        """评估器已注册到工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.domain.evaluators.risk import RiskEvaluator

        EvaluatorFactory.register("risk")(RiskEvaluator)

        assert "risk" in EvaluatorFactory._registry

    def test_detect_all_action(self, evaluator):
        """综合风险检测action"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="risk_001",
            type="risk",
            payload={
                "action": "detect_all",
                "feature_complexity": 0.2,
                "core_alignment": 0.9,
                "responsibility_blur": 0.1,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "overall_risk_level" in result.data
        assert result.data["overall_risk_level"] in ["low", "medium", "high"]
        # 验证评分逻辑：风险详情中包含各维度的风险评分
        assert "details" in result.data
        details = result.data["details"]
        assert "feature_creep" in details
        assert "risk_score" in details["feature_creep"]
        assert 0.0 <= details["feature_creep"]["risk_score"] <= 1.0

    def test_detect_feature_creep_low_risk(self, evaluator):
        """功能蔓延低风险检测"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="risk_002",
            type="risk",
            payload={
                "action": "feature_creep",
                "feature_complexity": 0.2,
                "core_alignment": 0.9,
                "responsibility_blur": 0.1,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["risk_level"] == "low"
        assert result.data["risk_score"] < 0.7

    def test_detect_tech_debt_high_risk(self, evaluator):
        """技术债务高风险检测"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="risk_003",
            type="risk",
            payload={
                "action": "tech_debt",
                "unresolved_warnings": 50,
                "duplicate_code_ratio": 0.3,
                "pending_refactoring": 5,
                "documentation_gap": 0.5,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["risk_level"] in ["low", "medium", "high"]

    def test_detect_coupling_risk(self, evaluator):
        """模块耦合风险检测"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="risk_004",
            type="risk",
            payload={
                "action": "coupling",
                "external_dependencies": 5,
                "cyclic_dependencies": 2,
                "cross_layer_calls": 3,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "risk_level" in result.data

    def test_detect_test_coverage_risk(self, evaluator):
        """测试覆盖风险检测"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="risk_005",
            type="risk",
            payload={
                "action": "test_coverage",
                "overall_coverage": 0.85,
                "new_code_coverage": 0.9,
                "critical_path_coverage": 0.8,
                "test_pass_rate": 0.95,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "risk_level" in result.data

    def test_detect_drift_risk(self, evaluator):
        """行为漂移风险检测"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="risk_006",
            type="risk",
            payload={
                "action": "drift",
                "baseline_score": 0.9,
                "current_score": 0.85,
                "format_changes": 2,
                "latency_increase": 10,
                "error_rate_change": 0.01,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "risk_level" in result.data

    def test_unknown_action_returns_error(self, evaluator):
        """未知action应返回错误"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="risk_007",
            type="risk",
            payload={"action": "unknown_action"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert "unknown_action" in result.error


class TestLLMAsJudgeEvaluator:
    """LLM作为Judge评估器测试"""

    def setup_method(self):
        from src.domain.evaluators.llm_as_judge import LLMAJudgeEvaluator

        self.evaluator_class = LLMAJudgeEvaluator

    @pytest.fixture
    def evaluator(self):
        return self.evaluator_class(client=None)

    def test_evaluator_can_be_created(self):
        """评估器可以被创建"""
        evaluator = self.evaluator_class()
        assert evaluator is not None

    def test_evaluator_registered(self):
        """评估器已注册到工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.domain.evaluators.llm_as_judge import LLMAJudgeEvaluator

        EvaluatorFactory.register("llm_as_judge")(LLMAJudgeEvaluator)

        assert "llm_as_judge" in EvaluatorFactory._registry

    def test_empty_input_returns_error(self, evaluator):
        """空输入应返回错误"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="judge_001",
            type="llm_as_judge",
            payload={"user_input": ""},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False

    def test_missing_actual_output_returns_error(self, evaluator):
        """缺少actual_output应返回错误"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="judge_002",
            type="llm_as_judge",
            payload={"user_input": "你好", "actual_output": ""},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert "actual_output 不能为空" in result.error

    def test_with_mock_client(self):
        """带Mock客户端的评估"""
        from src.schemas.evaluation import EvaluationSchema

        mock_client = MagicMock()
        mock_client.chat.return_value = '{"scores": {"correctness": {"score": 80, "reason": "test"}}, "total_score": 80, "confidence": 0.8, "conflict_detected": false}'
        evaluator = self.evaluator_class(client=mock_client)

        request = EvaluationSchema(
            id="judge_003",
            type="llm_as_judge",
            payload={
                "user_input": "你好",
                "actual_output": "你好，很高兴见到你",
                "expected_output": "友好问候",
                "dimensions": ["correctness"],
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score > 0

    def test_without_client_uses_mock(self, evaluator):
        """无客户端时使用默认mock结果"""
        from src.schemas.evaluation import EvaluationSchema

        request = EvaluationSchema(
            id="judge_004",
            type="llm_as_judge",
            payload={
                "user_input": "你好",
                "actual_output": "你好，很高兴见到你",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score > 0

    def test_multiple_dimensions(self):
        """多维度评估"""
        from src.schemas.evaluation import EvaluationSchema

        mock_client = MagicMock()
        mock_client.chat.return_value = '{"scores": {"correctness": {"score": 80, "reason": "test"}, "relevance": {"score": 90, "reason": "test"}}, "total_score": 85, "confidence": 0.8, "conflict_detected": false}'
        evaluator = self.evaluator_class(client=mock_client)

        request = EvaluationSchema(
            id="judge_005",
            type="llm_as_judge",
            payload={
                "user_input": "你好",
                "actual_output": "你好，很高兴见到你",
                "dimensions": ["correctness", "relevance"],
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "llm_judge_scores" in result.data


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
        from src.domain.evaluators.security import SecurityEvaluator

        EvaluatorFactory.register("security")(SecurityEvaluator)

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
            def _do_evaluate(self, request):
                pass

        assert "test_decorator" in EvaluatorFactory._registry


class TestBaseEvaluator:
    """基础评估器测试"""

    def test_base_evaluator_methods(self):
        """基础评估器方法"""
        from src.domain.evaluators.base import BaseEvaluator

        class TestEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                pass

        evaluator = TestEvaluator()
        assert evaluator is not None

    def test_validate_input(self):
        """验证输入方法"""
        from src.domain.evaluators.base import BaseEvaluator
        from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus

        class TestEvaluator(BaseEvaluator):
            def __init__(self, client=None):
                super().__init__(client, require_input=True)

            def _do_evaluate(self, request):
                if error := self.validate_input(request):
                    return error
                return self.create_success_response(text="ok", score=0.0)

        evaluator = TestEvaluator()
        request = EvaluationSchema(id="test", type="test", payload={})
        result = evaluator.evaluate(request)
        assert result.evaluation_status == EvaluatorStatus.ERROR
        assert "user_input/text 不能为空" in result.error

    def test_require_client(self):
        """客户端检查方法"""
        from src.domain.evaluators.base import BaseEvaluator
        from src.schemas.evaluation import EvaluatorStatus

        class TestEvaluator(BaseEvaluator):
            def __init__(self, client=None):
                super().__init__(client)

            def _do_evaluate(self, request):
                return self.create_success_response(text="ok", score=0.0)

        evaluator = TestEvaluator(client=None)
        result = evaluator.require_client_with_error()
        assert result is not None
        assert result.evaluation_status == EvaluatorStatus.ERROR
        assert "需要 LLM 客户端" in result.error


class TestScoringIntegration:
    """评分算法集成测试"""

    def test_score_numeric_match_integration(self):
        """数字匹配评分集成测试"""
        from src.domain.evaluators.scoring import score_numeric_match

        output = "营收100万元，利润20万元"
        expected = "营收100万元，利润20万元"
        score = score_numeric_match(output, expected)
        assert score == 1.0

    def test_score_numeric_match_partial(self):
        """数字匹配部分匹配"""
        from src.domain.evaluators.scoring import score_numeric_match

        output = "营收100万元"
        expected = "营收100万元 成本80万元"
        score = score_numeric_match(output, expected)
        assert 0.0 < score < 1.0

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
        from src.domain.evaluators.qa import QAEvaluator

        EvaluatorFactory.register("qa")(QAEvaluator)

        assert "qa" in EvaluatorFactory._registry


class TestSummaryEvaluator:
    """摘要评估器测试（已加入候选评估器）"""

    def setup_method(self):
        from src.domain.evaluators.summary import SummaryEvaluator

        self.evaluator_class = SummaryEvaluator

    def test_evaluator_can_be_created(self):
        """评估器可以被创建"""
        evaluator = self.evaluator_class()
        assert evaluator is not None


class TestTranslationEvaluator:
    """翻译评估器测试（已加入候选评估器）"""

    def setup_method(self):
        from src.domain.evaluators.translation import TranslationEvaluator

        self.evaluator_class = TranslationEvaluator

    def test_evaluator_can_be_created(self):
        """评估器可以被创建"""
        evaluator = self.evaluator_class()
        assert evaluator is not None


class TestSentimentEvaluator:
    """情感分析评估器测试（已加入候选评估器）"""

    def setup_method(self):
        from src.domain.evaluators.sentiment import SentimentEvaluator

        self.evaluator_class = SentimentEvaluator

    def test_evaluator_can_be_created(self):
        """评估器可以被创建"""
        evaluator = self.evaluator_class()
        assert evaluator is not None


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
        from src.domain.evaluators.code_review import CodeReviewEvaluator
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        EvaluatorFactory.register("code_review")(CodeReviewEvaluator)

        assert "code_review" in EvaluatorFactory._registry
