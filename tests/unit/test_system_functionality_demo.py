"""
系统功能展示测试
目标：通过测试展示 AI-Native Industrial Evaluation System 的核心功能模块

覆盖的核心功能：
1. 评估器工厂 (EvaluatorFactory) - 注册和获取评估器
2. 语义评估器 (SemanticEvaluator) - 语义相似度评估
3. 代码评估器 (CodeEvaluator) - 代码语法检查和质量评估
4. 风险评估器 (RiskEvaluator) - 多维度风险检测
5. 评估引擎 (EvaluationEngine) - 同步/异步评估编排
6. 熔断器和降级策略 - 容错机制
7. 评估状态机 - SUCCESS/PARTIAL/CANNOT_EVALUATE/ERROR

测试场景：
- 正向测试：验证正常功能
- 边界测试：验证边界值处理
- 异常测试：验证异常处理和降级
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.semantic import SemanticEvaluator
from src.domain.evaluators.code import CodeEvaluator
from src.domain.evaluators.risk import RiskEvaluator
from src.engine import EvaluationEngine
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus
from src.schemas.schemas import EvaluationStatus as EvaluationRecordStatus


class TestEvaluatorFactoryDemo:
    """评估器工厂功能展示"""

    def test_factory_registry_contains_all_evaluators(self):
        """验证工厂注册了所有评估器"""
        evaluators = EvaluatorFactory.list_evaluators()
        assert len(evaluators) > 0, "评估器工厂应至少注册一个评估器"
        assert "semantic" in evaluators, "语义评估器应已注册"
        assert "code" in evaluators, "代码评估器应已注册"
        assert "risk" in evaluators, "风险评估器应已注册"

    def test_factory_can_get_evaluator(self):
        """验证工厂可以获取评估器实例"""
        evaluator = EvaluatorFactory.get("semantic")
        assert evaluator is not None, "评估器实例不应为None"
        assert hasattr(evaluator, "evaluate"), "评估器应具备evaluate方法"

    def test_factory_get_returns_different_instances(self):
        """验证工厂每次获取新实例（对象池禁用时）"""
        EvaluatorFactory.disable_pool()
        eval1 = EvaluatorFactory.get("semantic")
        eval2 = EvaluatorFactory.get("semantic")
        assert eval1 is not eval2, "禁用对象池时应返回不同实例"
        EvaluatorFactory.enable_pool()


class TestSemanticEvaluatorDemo:
    """语义评估器功能展示"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "0.85"
        return client

    def test_semantic_evaluator_basic_functionality(self, mock_client):
        """验证语义评估器基本功能"""
        evaluator = SemanticEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="sem_demo_001",
            type="semantic",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是人工智能的一个分支，使计算机能够从数据中学习",
                "expected_output": "机器学习是AI的一个分支，让计算机从数据中学习规律",
            },
        )

        result = evaluator.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.SUCCESS
        assert result.score == pytest.approx(0.85, abs=0.01)
        assert result.is_valid is True
        assert result.confidence is not None
        assert 0.0 <= result.confidence <= 1.0
        assert "raw_llm_judgment" in result.data

    def test_semantic_evaluator_identical_outputs(self, mock_client):
        """验证完全相同的输出获得高分"""
        mock_client.chat.return_value = "1.0"
        evaluator = SemanticEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="sem_demo_002",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "actual_output": "这是一个完全相同的回答",
                "expected_output": "这是一个完全相同的回答",
            },
        )

        result = evaluator.evaluate(request)

        assert result.score == 1.0
        assert result.evaluation_status == EvaluatorStatus.SUCCESS

    def test_semantic_evaluator_missing_expected_output(self, mock_client):
        """验证缺少expected_output时返回错误"""
        evaluator = SemanticEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="sem_demo_003",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "actual_output": "实际输出",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert result.evaluation_status == EvaluatorStatus.ERROR
        assert "expected_output" in result.error


class TestCodeEvaluatorDemo:
    """代码评估器功能展示"""

    def test_code_evaluator_syntax_check(self):
        """验证代码语法检查功能"""
        evaluator = CodeEvaluator(client=None)
        request = EvaluationSchema(
            id="code_demo_001",
            type="code",
            payload={
                "code": "def calculate_sum(a, b):\n    return a + b",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.evaluation_status == EvaluatorStatus.PARTIAL
        assert result.data["syntax_valid"] is True
        assert "syntax" in result.data["scores_breakdown"]

    def test_code_evaluator_syntax_error(self):
        """验证语法错误被正确检测"""
        evaluator = CodeEvaluator(client=None)
        request = EvaluationSchema(
            id="code_demo_002",
            type="code",
            payload={
                "code": "def broken_function()\n    return 1",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert result.evaluation_status == EvaluatorStatus.ERROR
        assert result.score is None
        assert "语法" in result.text

    def test_code_evaluator_with_llm_review(self):
        """验证代码审查功能（带LLM客户端）"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "代码质量良好，符合PEP8规范，建议添加文档字符串"
        evaluator = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="code_demo_003",
            type="code",
            payload={
                "code": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["syntax_valid"] is True
        mock_client.chat.assert_called_once()


class TestRiskEvaluatorDemo:
    """风险评估器功能展示"""

    def test_risk_evaluator_detect_all(self):
        """验证风险评估器全面检测功能"""
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id="risk_demo_001",
            type="risk",
            payload={"action": "detect_all"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.evaluation_status == EvaluatorStatus.SUCCESS
        assert "overall_risk_level" in result.data
        assert "high_risks" in result.data
        assert "medium_risks" in result.data
        assert len(result.data["details"]) == 5

    def test_risk_evaluator_feature_creep_detection(self):
        """验证功能蔓延风险检测"""
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id="risk_demo_002",
            type="risk",
            payload={
                "action": "feature_creep",
                "feature_complexity": 0.8,
                "core_alignment": 0.2,
                "responsibility_blur": 0.7,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["risk_type"] == "feature_creep"
        assert result.data["risk_level"] == "high"
        assert result.score <= 0.3
        assert "suggestion" in result.data

    def test_risk_evaluator_low_risk_scenario(self):
        """验证低风险场景"""
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id="risk_demo_003",
            type="risk",
            payload={
                "action": "detect_all",
                "feature_complexity": 0.1,
                "core_alignment": 0.95,
                "responsibility_blur": 0.1,
                "unresolved_warnings": 10,
                "duplicate_code_ratio": 0.1,
                "pending_refactoring": 1,
                "documentation_gap": 0.1,
                "external_dependencies": 2,
                "cyclic_dependencies": 0,
                "cross_layer_calls": 0.1,
                "overall_coverage": 0.9,
                "new_code_coverage": 0.85,
                "critical_path_coverage": 0.9,
                "test_pass_rate": 1.0,
                "baseline_score": 0.9,
                "current_score": 0.88,
                "format_changes": 1,
                "latency_increase": 5,
                "error_rate_change": 0.01,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["overall_risk_level"] == "low"
        assert result.score >= 0.8


class TestEvaluationEngineDemo:
    """评估引擎功能展示"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "0.9"
        return client

    def test_engine_sync_evaluation(self, mock_client):
        """验证引擎同步评估功能"""
        engine = EvaluationEngine(client=mock_client)
        request = EvaluationSchema(
            id="engine_demo_001",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "actual_output": "实际回答",
                "expected_output": "预期回答",
            },
        )

        result = engine.run(request)

        assert result is not None
        assert result.case_id == "engine_demo_001"
        assert result.status == EvaluationRecordStatus.PASSED
        assert result.model_name == "gpt-4"
        assert result.response is not None
        assert result.response.is_valid is True

    @pytest.mark.asyncio
    async def test_engine_async_evaluation(self, mock_client):
        """验证引擎异步评估功能"""
        engine = EvaluationEngine(client=mock_client)
        request = EvaluationSchema(
            id="engine_demo_002",
            type="semantic",
            payload={
                "user_input": "异步测试问题",
                "actual_output": "异步实际回答",
                "expected_output": "异步预期回答",
            },
        )

        result = await engine.run_async(request)

        assert result is not None
        assert result.case_id == "engine_demo_002"
        assert result.status == EvaluationRecordStatus.PASSED

    def test_engine_payload_validation(self, mock_client):
        """验证引擎Payload校验功能"""
        engine = EvaluationEngine(client=mock_client)
        request = EvaluationSchema(
            id="engine_demo_003",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "actual_output": "实际输出",
            },
        )

        result = engine.run(request)

        assert result.status == EvaluationRecordStatus.ERROR


class TestFallbackAndCircuitBreakerDemo:
    """降级策略和熔断器功能展示"""

    def test_fallback_policy_triggered_on_client_failure(self):
        """验证LLM客户端失败时触发降级策略"""
        failing_client = MagicMock()
        failing_client.chat.side_effect = ConnectionError("LLM service unavailable")

        with patch("src.domain.evaluators.embedding_service.EmbeddingService") as mock_embedding:
            service_instance = MagicMock()
            service_instance.is_available.return_value = True
            service_instance.calculate_similarity.return_value = 0.6
            mock_embedding.get_instance.return_value = service_instance

            evaluator = SemanticEvaluator(client=failing_client)
            request = EvaluationSchema(
                id="fallback_demo_001",
                type="semantic",
                payload={
                    "user_input": "测试问题",
                    "actual_output": "实际输出",
                    "expected_output": "预期输出",
                },
            )

            result = evaluator.safe_evaluate(request)

            assert result.is_valid is True
            assert result.evaluation_status == EvaluatorStatus.PARTIAL
            assert result.score is not None
            assert result.confidence < 0.95

    def test_safe_evaluate_handles_exceptions(self):
        """验证safe_evaluate捕获异常"""
        failing_client = MagicMock()
        failing_client.chat.side_effect = ValueError("Invalid response")

        evaluator = SemanticEvaluator(client=failing_client)
        request = EvaluationSchema(
            id="safe_eval_demo_001",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "actual_output": "实际输出",
                "expected_output": "预期输出",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert isinstance(result, DomainResponse)
        assert result.is_valid is True


class TestEvaluationStatusMachineDemo:
    """评估状态机功能展示"""

    def test_success_status(self):
        """验证SUCCESS状态"""
        response = DomainResponse(
            text="评估完成",
            score=0.85,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.95,
        )
        assert response.is_valid is True
        assert response.evaluation_status == EvaluatorStatus.SUCCESS

    def test_partial_status(self):
        """验证PARTIAL状态（降级评估）"""
        response = DomainResponse(
            text="部分评估完成",
            score=0.6,
            evaluation_status=EvaluatorStatus.PARTIAL,
            confidence=0.5,
            data={
                "dimensions_evaluated": ["fallback_similarity"],
                "dimensions_skipped": ["llm_semantic"],
            },
        )
        assert response.is_valid is True
        assert response.evaluation_status == EvaluatorStatus.PARTIAL

    def test_cannot_evaluate_status(self):
        """验证CANNOT_EVALUATE状态"""
        response = DomainResponse(
            text="无法评估",
            evaluation_status=EvaluatorStatus.CANNOT_EVALUATE,
            confidence=None,
        )
        assert response.is_valid is False
        assert response.evaluation_status == EvaluatorStatus.CANNOT_EVALUATE

    def test_error_status(self):
        """验证ERROR状态"""
        response = DomainResponse(
            error="系统错误",
            evaluation_status=EvaluatorStatus.ERROR,
            confidence=0.0,
        )
        assert response.is_valid is False
        assert response.evaluation_status == EvaluatorStatus.ERROR