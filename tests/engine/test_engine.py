"""
Engine 层测试 - 评测引擎
真实业务场景：评测请求执行、异常处理、状态映射、性能指标
"""
import time
import pytest
from unittest.mock import MagicMock, patch

from src.engine import EvaluationEngine
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.base import BaseEvaluator
from src.schemas.evaluation import (
    DomainResponse,
    EvaluationSchema,
    EvaluationStatus,
)
from src.schemas.schemas import EvaluationResult
from src.exceptions import (
    BasePlatformError,
    ContractValidationError,
    DomainLogicError,
    InfrastructureError,
)


@pytest.fixture(autouse=True)
def reset_evaluators_each_test():
    """
    自动在每个测试前重置 EvaluatorFactory 并重新触发自动发现。
    确保测试隔离，避免全局单例污染。
    """
    from src.domain.evaluators import auto_discover
    from src.domain.evaluators.evaluator_factory import EvaluatorFactory as EF

    # 重置工厂
    EF._registry = {}
    # 强制重新发现（清空 sys.modules 缓存 + 重新 import）
    auto_discover(force=True)
    yield
    EF._registry = {}


# ============================================================
# Part 1: 正常流程 - 真实业务场景
# ============================================================
class TestEvaluationEngineSuccessBusiness:
    """正常评测流程：用户提交请求 → 引擎路由 → 返回结果"""

    def test_engine_routes_request_to_correct_evaluator(self, mock_llm_client):
        """场景：用户提交 general 类型请求"""
        engine = EvaluationEngine(mock_llm_client)
        request = EvaluationSchema(
            id="case_001",
            type="general",
            payload={"user_input": "Hello"},
        )
        result = engine.run(request)
        assert isinstance(result, EvaluationResult)
        assert result.case_id == "case_001"

    def test_engine_returns_passed_status_for_valid_output(self, mock_llm_client):
        """场景：LLM 输出有效，结果状态为 PASSED"""
        engine = EvaluationEngine(mock_llm_client)
        request = EvaluationSchema(
            id="case_002",
            type="general",
            payload={"user_input": "hi"},
        )
        result = engine.run(request)
        # mock_llm_client 返回 "Mock LLM response"，且没有 expected_output，所以 score=1.0
        assert result.status == EvaluationStatus.PASSED

    def test_engine_returns_failed_status_for_invalid_output(self, mock_llm_client):
        """场景：评估器返回 is_valid=False"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"
        # LLM 返回空，但 evaluator 不带 client 时无需 LLM
        engine = EvaluationEngine(client)

        request = EvaluationSchema(
            id="case_003",
            type="general",
            payload={},  # user_input 为空
        )
        result = engine.run(request)
        assert result.status == EvaluationStatus.FAILED

    def test_engine_populates_latency(self, mock_llm_client):
        """场景：结果包含延迟指标（监控/SLA 关键）"""
        engine = EvaluationEngine(mock_llm_client)
        request = EvaluationSchema(
            id="case_004",
            type="general",
            payload={"user_input": "hi"},
        )
        result = engine.run(request)
        assert result.latency_ms > 0
        assert result.latency_ms < 10000  # 单次不应超过 10s

    def test_engine_populates_model_name(self, mock_llm_client):
        """场景：结果中记录使用的模型（用于追溯）"""
        engine = EvaluationEngine(mock_llm_client)
        request = EvaluationSchema(
            id="case_005",
            type="general",
            payload={"user_input": "hi"},
        )
        result = engine.run(request)
        assert result.model_name == "gpt-4"

    def test_engine_populates_adapter_name(self, mock_llm_client):
        """场景：结果中记录评估器（用于追溯）"""
        engine = EvaluationEngine(mock_llm_client)
        request = EvaluationSchema(
            id="case_006",
            type="general",
            payload={"user_input": "hi"},
        )
        result = engine.run(request)
        assert result.adapter_name == "GeneralEvaluator"

    def test_engine_response_includes_evaluator_output(self, mock_llm_client):
        """场景：DomainResponse 包含在 EvaluationResult 中"""
        engine = EvaluationEngine(mock_llm_client)
        request = EvaluationSchema(
            id="case_007",
            type="general",
            payload={"user_input": "test"},
        )
        result = engine.run(request)
        assert result.response is not None
        assert isinstance(result.response, DomainResponse)


# ============================================================
# Part 2: 异常处理 - 真实业务场景
# ============================================================
class TestEvaluationEngineExceptionBusiness:
    """异常处理：用户输入触发不同类型异常时，引擎正确分类"""

    def test_contract_validation_error_returns_error_status(self, mock_llm_client):
        """场景：客户端请求体不合法（错误的数据格式）"""
        engine = EvaluationEngine(mock_llm_client)

        @EvaluatorFactory.register("contract_fail")
        class ContractFailEvaluator(BaseEvaluator):
            def evaluate(self, request):
                raise ContractValidationError("Invalid payload structure")

        request = EvaluationSchema(
            id="case_008",
            type="contract_fail",
            payload={},
        )
        result = engine.run(request)
        assert result.status == EvaluationStatus.ERROR
        assert "Invalid payload structure" in result.error_message
        assert result.adapter_name == "contract_validator"

    def test_domain_logic_error_returns_error_status(self, mock_llm_client):
        """场景：业务规则触发的异常（如模型不支持）"""
        engine = EvaluationEngine(mock_llm_client)

        @EvaluatorFactory.register("domain_fail")
        class DomainFailEvaluator(BaseEvaluator):
            def evaluate(self, request):
                raise DomainLogicError("Model not supported for this domain")

        request = EvaluationSchema(
            id="case_009",
            type="domain_fail",
            payload={},
        )
        result = engine.run(request)
        assert result.status == EvaluationStatus.ERROR
        assert "Model not supported" in result.error_message
        assert result.adapter_name == "domain_handler"

    def test_infrastructure_error_returns_error_status(self, mock_llm_client):
        """场景：底层资源故障（DB/Redis 不可用）"""
        engine = EvaluationEngine(mock_llm_client)

        @EvaluatorFactory.register("infra_fail")
        class InfraFailEvaluator(BaseEvaluator):
            def evaluate(self, request):
                raise InfrastructureError("Database connection lost")

        request = EvaluationSchema(
            id="case_010",
            type="infra_fail",
            payload={},
        )
        result = engine.run(request)
        assert result.status == EvaluationStatus.ERROR
        assert "Database connection" in result.error_message
        assert result.adapter_name == "infra_handler"

    def test_unexpected_exception_returns_error_status(self, mock_llm_client):
        """场景：未预期的 RuntimeError，被 safe_evaluate 捕获并返回 ERROR 状态
        （设计权衡：safe_evaluate 防止进程崩溃，返回 DomainResponse 而非抛出异常）"""
        engine = EvaluationEngine(mock_llm_client)

        @EvaluatorFactory.register("unexpected_fail")
        class UnexpectedFailEvaluator(BaseEvaluator):
            def evaluate(self, request):
                raise RuntimeError("Bug in evaluator")

        request = EvaluationSchema(
            id="case_011",
            type="unexpected_fail",
            payload={},
        )
        result = engine.run(request)
        assert result.status == EvaluationStatus.ERROR
        assert "EVALUATION_ERROR" in result.response.error

    def test_evaluator_not_registered_returns_error(self, mock_llm_client):
        """场景：客户端请求未注册的评估器类型"""
        engine = EvaluationEngine(mock_llm_client)
        request = EvaluationSchema(
            id="case_012",
            type="nonexistent_evaluator",
            payload={},
        )
        result = engine.run(request)
        assert result.status == EvaluationStatus.ERROR

    def test_error_result_still_records_latency(self, mock_llm_client):
        """场景：即使失败，也要记录延迟（用于告警）"""
        engine = EvaluationEngine(mock_llm_client)

        @EvaluatorFactory.register("slow_fail")
        class SlowFailEvaluator(BaseEvaluator):
            def evaluate(self, request):
                time.sleep(0.01)
                raise DomainLogicError("fail")

        request = EvaluationSchema(
            id="case_013",
            type="slow_fail",
            payload={},
        )
        result = engine.run(request)
        assert result.latency_ms >= 10
        assert result.status == EvaluationStatus.ERROR


# ============================================================
# Part 3: 性能与稳定性 - 真实业务场景
# ============================================================
class TestEvaluationEnginePerformanceBusiness:
    """性能：生产环境高 QPS 下的稳定性"""

    def test_engine_handles_concurrent_evaluations(self, mock_llm_client):
        """场景：100 个连续评测请求（生产压测）"""
        engine = EvaluationEngine(mock_llm_client)
        results = []
        for i in range(100):
            request = EvaluationSchema(
                id=f"case_{i:03d}",
                type="general",
                payload={"user_input": f"q_{i}"},
            )
            results.append(engine.run(request))

        assert len(results) == 100
        assert all(r.case_id.startswith("case_") for r in results)

    def test_engine_latency_within_sla(self, mock_llm_client):
        """场景：单次请求延迟应 < 100ms（本地 mock LLM）"""
        engine = EvaluationEngine(mock_llm_client)
        request = EvaluationSchema(
            id="sla_test",
            type="general",
            payload={"user_input": "hi"},
        )

        start = time.perf_counter()
        for _ in range(10):
            engine.run(request)
        avg_ms = (time.perf_counter() - start) * 100

        assert avg_ms < 100, f"Avg latency {avg_ms}ms exceeds SLA"

    def test_engine_does_not_share_state_between_requests(self, mock_llm_client):
        """场景：请求之间不应有状态污染"""
        engine = EvaluationEngine(mock_llm_client)
        request1 = EvaluationSchema(
            id="req_1",
            type="general",
            payload={"user_input": "first"},
        )
        request2 = EvaluationSchema(
            id="req_2",
            type="general",
            payload={"user_input": "second"},
        )
        result1 = engine.run(request1)
        result2 = engine.run(request2)
        assert result1.case_id == "req_1"
        assert result2.case_id == "req_2"


# ============================================================
# Part 4: 评估器自动发现 - 真实业务场景
# ============================================================
class TestEvaluatorAutoDiscoveryBusiness:
    """评估器自动发现：业务方新增评估器后无需手动注册"""

    def test_factory_registers_all_evaluators_at_import(self):
        """场景：import 评估器模块时，所有评估器自动注册"""
        registered = EvaluatorFactory.list_evaluators()
        assert "general" in registered
        assert "security" in registered
        assert "drift" in registered

    def test_factory_get_evaluator_info_audit(self):
        """场景：审计系统查询所有评估器信息"""
        info = EvaluatorFactory.get_evaluator_info()
        assert isinstance(info, list)
        assert len(info) > 0
        for entry in info:
            assert "name" in entry
            assert "class_name" in entry
            assert "docstring" in entry

    def test_factory_supports_runtime_registration(self):
        """场景：业务方在运行时动态注册新评估器"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.domain.evaluators.base import BaseEvaluator
        from src.schemas.evaluation import DomainResponse

        @EvaluatorFactory.register("runtime_new_evaluator")
        class RuntimeEvaluator(BaseEvaluator):
            def evaluate(self, request):
                return DomainResponse(is_valid=True, score=1.0)

        assert "runtime_new_evaluator" in EvaluatorFactory.list_evaluators()
