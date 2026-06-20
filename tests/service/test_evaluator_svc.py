"""
Service 层综合测试 - 真实业务场景
重点：业务编排、跨层数据流转、异常分类、副作用隔离
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# 确保 src 在路径中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture(autouse=True)
def reset_evaluator_registry():
    """确保每个测试前评估器注册表干净"""
    from src.domain.evaluators import auto_discover
    from src.domain.evaluators.evaluator_factory import EvaluatorFactory as EF
    EF._registry = {}
    auto_discover(force=True)
    yield
    EF._registry = {}


from src.exceptions import (
    ContractValidationError,
    DomainLogicError,
    InfrastructureError,
)
from src.schemas.evaluation import EvaluationSchema
from src.services.evaluator_svc import (
    _normalize_raw_data,
    run_evaluation_service,
    service_exception_handler,
)


# ============================================================
# Part 1: 数据规范化 - 真实业务场景
# ============================================================
class TestNormalizeRawDataBusinessScenarios:
    """数据规范化：处理客户端不同格式的请求"""

    def test_normalize_when_payload_present(self):
        """场景：标准格式请求（payload 已存在）"""
        raw = {
            "id": "case_001",
            "type": "general",
            "payload": {"user_input": "hi"},
            "metadata": {"source": "web"},
        }
        result = _normalize_raw_data(raw)
        assert result["id"] == "case_001"
        assert result["type"] == "general"
        assert result["payload"] == {"user_input": "hi"}
        assert result["metadata"] == {"source": "web"}

    def test_normalize_when_payload_missing_flatten_to_payload(self):
        """场景：业务方使用扁平化结构（无 payload）"""
        raw = {
            "id": "case_002",
            "type": "general",
            "user_input": "hello",
            "temperature": 0.5,
        }
        result = _normalize_raw_data(raw)
        # id, type 应保留
        assert result["id"] == "case_002"
        assert result["type"] == "general"
        # 其它字段应平铺进 payload
        assert "user_input" in result["payload"]
        assert result["payload"]["user_input"] == "hello"
        assert result["payload"]["temperature"] == 0.5

    def test_normalize_excludes_meta_fields_from_payload(self):
        """场景：保留 model_provider/model_name/metadata 字段"""
        raw = {
            "id": "case_003",
            "type": "general",
            "user_input": "hi",
            "model_provider": "openai",
            "model_name": "gpt-4",
            "metadata": {"key": "value"},
        }
        result = _normalize_raw_data(raw)
        # 这三个字段不应进入 payload
        assert "model_provider" not in result["payload"]
        assert "model_name" not in result["payload"]
        assert "metadata" not in result["payload"]
        # 但应在顶级保留
        assert result["model_provider"] == "openai"
        assert result["model_name"] == "gpt-4"
        assert result["metadata"] == {"key": "value"}

    def test_normalize_empty_request_id_gets_unknown(self):
        """场景：客户端未传 id"""
        raw = {"type": "general", "user_input": "hi"}
        result = _normalize_raw_data(raw)
        assert result["id"] == "unknown"

    def test_normalize_does_not_mutate_input(self):
        """场景：原 dict 不应被破坏（业务方可能复用）"""
        raw = {
            "id": "case_004",
            "type": "general",
            "user_input": "hi",
        }
        original_copy = dict(raw)
        _normalize_raw_data(raw)
        assert raw == original_copy  # 不可变性


# ============================================================
# Part 2: Service 异常处理装饰器 - 真实业务场景
# ============================================================
class TestServiceExceptionHandlerBusinessScenarios:
    """service_exception_handler：将异常分类为业务可处理的 dict"""

    def test_handles_contract_validation_error(self):
        """场景：用户提交非法数据"""
        @service_exception_handler
        def fail_with_contract():
            raise ContractValidationError("字段缺失")

        result = fail_with_contract()
        assert result["status"] == "error"
        assert result["code"] == "CONTRACT_ERROR"
        assert "字段缺失" in result["message"]

    def test_handles_domain_logic_error(self):
        """场景：业务规则触发（如不支持的模型）"""
        @service_exception_handler
        def fail_with_domain():
            raise DomainLogicError("模型不支持")

        result = fail_with_domain()
        assert result["status"] == "error"
        assert result["code"] == "DOMAIN_ERROR"

    def test_handles_infrastructure_error(self):
        """场景：Redis/DB 不可用"""
        @service_exception_handler
        def fail_with_infra():
            raise InfrastructureError("连接超时")

        result = fail_with_infra()
        assert result["status"] == "error"
        assert result["code"] == "INFRA_ERROR"

    def test_handles_validation_error_pydantic(self):
        """场景：Pydantic ValidationError (非 BasePlatformError)"""
        from pydantic import ValidationError

        @service_exception_handler
        def fail_with_validation():
            try:
                EvaluationSchema()  # 必填字段缺失
            except ValidationError as e:
                raise e

        result = fail_with_validation()
        # 期望 CONTRACT_ERROR（业务约定）
        assert result["status"] == "error"
        assert result["code"] == "CONTRACT_ERROR"

    def test_handles_unexpected_error_as_internal(self):
        """场景：未预期的 RuntimeError"""
        @service_exception_handler
        def fail_unexpected():
            raise RuntimeError("Null pointer")

        result = fail_unexpected()
        assert result["status"] == "error"
        assert result["code"] == "INTERNAL_ERROR"
        # 不应暴露内部堆栈信息
        assert "Null pointer" not in result["message"]

    def test_normal_return_passes_through(self):
        """场景：正常返回不应被包装"""
        @service_exception_handler
        def returns_data():
            return {"score": 0.9, "data": "test"}

        result = returns_data()
        assert result == {"score": 0.9, "data": "test"}


# ============================================================
# Part 3: run_evaluation_service 端到端 - 真实业务场景
# ============================================================
class TestRunEvaluationServiceBusinessScenarios:
    """评测服务编排：从客户端请求到持久化的完整链路"""

    def test_run_evaluation_uses_provided_client(self):
        """场景：业务方注入自定义 LLM 客户端（测试场景）"""
        # 使用 mock 客户端避免真实 LLM 调用
        mock_client = MagicMock()
        mock_client.config = MagicMock()
        mock_client.config.model_name = "test-model"
        mock_client.chat = MagicMock(return_value="test response")

        raw_data = {
            "id": "case_005",
            "type": "general",
            "payload": {"user_input": "test"},
        }
        result = run_evaluation_service(raw_data, client=mock_client)
        # 关键：成功时 status == "success"
        assert result["status"] == "success"
        assert result["evaluation_status"] in ("passed", "failed")
        # 校验有 latency
        assert "latency_ms" in result
        assert result["latency_ms"] >= 0

    def test_run_evaluation_normalizes_flat_input(self):
        """场景：客户端发送扁平格式（无 payload 包装）"""
        mock_client = MagicMock()
        mock_client.config = MagicMock()
        mock_client.config.model_name = "test"
        mock_client.chat = MagicMock(return_value="ok")

        raw_data = {
            "id": "case_006",
            "type": "general",
            "user_input": "hello",
        }
        result = run_evaluation_service(raw_data, client=mock_client)
        assert result["status"] == "success"
        # 验证 normalization 生效
        assert result["record_id"] == "case_006"

    def test_run_evaluation_handles_unknown_evaluator(self):
        """场景：业务方请求未注册的评估器类型"""
        raw_data = {
            "id": "case_007",
            "type": "nonexistent_evaluator_xyz",
            "payload": {"user_input": "test"},
        }
        result = run_evaluation_service(raw_data, client=MagicMock())
        assert result["status"] == "error"
        assert result["code"] == "DOMAIN_ERROR"

    def test_run_evaluation_handles_contract_error(self):
        """场景：必填字段缺失"""
        raw_data = {
            "id": "case_008",
            # 缺少 type 和 payload
        }
        result = run_evaluation_service(raw_data, client=MagicMock())
        assert result["status"] == "error"
        assert result["code"] == "CONTRACT_ERROR"

    def test_run_evaluation_logs_persistence_failure_but_continues(self):
        """场景：DB 写入失败不应影响业务结果返回"""
        mock_client = MagicMock()
        mock_client.config = MagicMock()
        mock_client.config.model_name = "test"
        mock_client.chat = MagicMock(return_value="ok")

        # 模拟 repository.save 失败
        with patch("src.services.evaluator_svc._repository") as mock_repo:
            mock_repo.save.side_effect = Exception("DB connection lost")

            raw_data = {
                "id": "case_009",
                "type": "general",
                "payload": {"user_input": "test"},
            }
            result = run_evaluation_service(raw_data, client=mock_client)
            # 关键：业务结果仍应返回（持久化失败仅记录日志）
            assert result["status"] == "success"
            assert result["evaluation_status"] in ("passed", "failed")


# ============================================================
# Part 4: Service 层副作用问题
# ============================================================
class TestServiceLayerSideEffectsBusinessScenarios:
    """Service 层副作用：import 时是否产生副作用"""

    def test_service_module_import_creates_repository_singleton(self):
        """业务场景：服务模块 import 时立即创建 DB 单例

        风险：测试 import 业务模块时，会立即连接 DB（潜在副作用）
        """
        # 检查 _repository 是否在 import 时就创建
        from src.services import evaluator_svc
        # 注意：单例已存在
        assert hasattr(evaluator_svc, "_repository")
        # 这是已知的设计问题（导入时副作用）
        # 在生产环境可能合理（FastAPI lifespan），但增加了测试复杂度
