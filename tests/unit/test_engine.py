"""
评测引擎单元测试 - 带有效断言
覆盖: 正常评测、各类异常处理、结果结构、延迟计算
"""
import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.engine import EvaluationEngine
from src.domain.evaluators.base import BaseEvaluator, EvaluatorFactory
from src.schemas.evaluation import EvaluationSchema, DomainResponse
from src.schemas.schemas import EvaluationStatus
from src.exceptions import ContractValidationError, DomainLogicError, InfrastructureError


class MockPassingEvaluator(BaseEvaluator):
    """模拟通过的评估器"""
    def evaluate(self, request):
        return DomainResponse(is_valid=True, score=0.95, text="good")


class MockFailingEvaluator(BaseEvaluator):
    """模拟失败的评估器"""
    def evaluate(self, request):
        return DomainResponse(is_valid=False, score=0.3, text="bad")


class MockExceptionEvaluator(BaseEvaluator):
    """模拟抛出异常的评估器"""
    def evaluate(self, request):
        raise RuntimeError("模拟异常")


class MockNoneEvaluator(BaseEvaluator):
    """模拟返回 None 的评估器"""
    def evaluate(self, request):
        return None


@pytest.fixture(autouse=True)
def reset_registry():
    """每个测试前重置注册表"""
    EvaluatorFactory._registry = {}
    yield
    EvaluatorFactory._registry = {}


class TestEngineNormalExecution:
    """引擎正常执行测试"""

    def test_run_returns_evaluation_result(self):
        """正常执行应返回 EvaluationResult"""
        EvaluatorFactory.register("test_pass")(MockPassingEvaluator)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(id="case_1", type="test_pass", payload={})
        result = engine.run(request)

        assert result.case_id == "case_1"
        assert result.status == EvaluationStatus.PASSED
        assert result.model_name == "test-model"
        assert result.adapter_name == "MockPassingEvaluator"
        assert result.response.is_valid is True
        assert result.response.score == 0.95
        assert result.latency_ms >= 0

    def test_run_failed_evaluation(self):
        """评估失败应返回 FAILED 状态"""
        EvaluatorFactory.register("test_fail")(MockFailingEvaluator)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(id="case_2", type="test_fail", payload={})
        result = engine.run(request)

        assert result.status == EvaluationStatus.FAILED
        assert result.response.is_valid is False

    def test_run_latency_is_positive(self):
        """延迟应为正数"""
        EvaluatorFactory.register("test_pass")(MockPassingEvaluator)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(id="case_3", type="test_pass", payload={})
        result = engine.run(request)

        assert result.latency_ms > 0

    def test_run_model_name_fallback(self):
        """无 model_name 时应回退到 unknown"""
        EvaluatorFactory.register("test_pass")(MockPassingEvaluator)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = None

        engine = EvaluationEngine(client)
        request = EvaluationSchema(id="case_4", type="test_pass", payload={})
        result = engine.run(request)
        assert result.model_name == "unknown"


class TestEngineExceptionHandling:
    """引擎异常处理测试"""

    def test_run_contract_validation_error(self):
        """契约错误应返回 ERROR 状态并保留错误信息"""
        @EvaluatorFactory.register("test_contract")
        class ContractErrorEvaluator(BaseEvaluator):
            def evaluate(self, request):
                raise ContractValidationError("字段缺失")

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(id="case_5", type="test_contract", payload={})
        result = engine.run(request)

        assert result.status == EvaluationStatus.ERROR
        assert result.adapter_name == "contract_validator"
        assert result.response.error == "CONTRACT_ERROR"
        assert "字段缺失" in result.error_message

    def test_run_domain_logic_error(self):
        """领域错误应返回 ERROR 状态"""
        @EvaluatorFactory.register("test_domain")
        class DomainErrorEvaluator(BaseEvaluator):
            def evaluate(self, request):
                raise DomainLogicError("适配器未找到")

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(id="case_6", type="test_domain", payload={})
        result = engine.run(request)

        assert result.status == EvaluationStatus.ERROR
        assert result.adapter_name == "domain_handler"
        assert result.response.error == "DOMAIN_ERROR"
        assert "适配器未找到" in result.error_message

    def test_run_infrastructure_error(self):
        """基础设施错误应返回 ERROR 状态"""
        @EvaluatorFactory.register("test_infra")
        class InfraErrorEvaluator(BaseEvaluator):
            def evaluate(self, request):
                raise InfrastructureError("Redis 连接失败")

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(id="case_7", type="test_infra", payload={})
        result = engine.run(request)

        assert result.status == EvaluationStatus.ERROR
        assert result.adapter_name == "infra_handler"
        assert result.response.error == "INFRA_ERROR"
        assert "Redis 连接失败" in result.error_message

    def test_run_unexpected_error(self):
        """未预期异常应由 safe_evaluate 捕获并返回 ERROR 状态"""
        EvaluatorFactory.register("test_unexpected")(MockExceptionEvaluator)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(id="case_8", type="test_unexpected", payload={})
        result = engine.run(request)

        # BaseEvaluator.safe_evaluate 捕获 RuntimeError 并返回 DomainResponse(is_valid=False, error="...")
        # engine 检测到 error 包含 "_ERROR"，返回 ERROR 状态
        assert result.status == EvaluationStatus.ERROR
        assert result.response.is_valid is False
        assert "EVALUATION_ERROR" in result.response.error

    def test_run_evaluator_returns_none(self):
        """评估器返回 None 应由 safe_evaluate 处理"""
        EvaluatorFactory.register("test_none")(MockNoneEvaluator)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(id="case_9", type="test_none", payload={})
        result = engine.run(request)

        # safe_evaluate 将 None 转换为 DomainResponse(is_valid=False, error="...")
        # engine 检测到 error 包含 "_ERROR"，返回 ERROR 状态
        assert result.status == EvaluationStatus.ERROR
        assert result.response.is_valid is False


class TestEngineEdgeCases:
    """引擎边界情况测试"""

    def test_run_unknown_evaluator(self):
        """未知评估器应返回 DomainLogicError"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(id="case_10", type="unknown_evaluator", payload={})
        result = engine.run(request)

        assert result.status == EvaluationStatus.ERROR
        assert result.adapter_name == "domain_handler"
        assert "未找到" in result.error_message

    def test_run_preserves_case_id(self):
        """case_id 应被保留在结果中"""
        EvaluatorFactory.register("test_pass")(MockPassingEvaluator)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(id="special_case_id_123", type="test_pass", payload={})
        result = engine.run(request)

        assert result.case_id == "special_case_id_123"
