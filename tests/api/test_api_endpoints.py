"""
API 层综合测试 - 真实业务场景
重点：HTTP 契约、状态码、错误信息、安全防护
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient


# ============================================================
# Part 1: 输入验证 - 真实业务场景
# ============================================================
class TestInputValidationBusinessScenarios:
    """输入验证：API 入口处的安全检查"""

    def test_validate_evaluator_name_accepts_valid(self):
        """场景：合法评估器名"""
        from src.api.server import validate_evaluator_name
        assert validate_evaluator_name("general") is True
        assert validate_evaluator_name("llm_as_judge") is True
        assert validate_evaluator_name("risk-v2") is True
        assert validate_evaluator_name("evaluator_123") is True

    def test_validate_evaluator_name_rejects_sql_injection(self):
        """场景：SQL 注入攻击防护"""
        from src.api.server import validate_evaluator_name
        assert validate_evaluator_name("general; DROP TABLE users") is False
        assert validate_evaluator_name("general' OR 1=1--") is False
        assert validate_evaluator_name("name with space") is False
        assert validate_evaluator_name("name.with.dot") is False
        assert validate_evaluator_name("../etc/passwd") is False

    def test_validate_evaluator_name_rejects_empty(self):
        """场景：空值/单字符边界"""
        from src.api.server import validate_evaluator_name
        assert validate_evaluator_name("") is False
        assert validate_evaluator_name("   ") is False
        assert validate_evaluator_name("/") is False

    def test_validate_dataset_name_rejects_path_traversal(self):
        """场景：路径遍历防护"""
        from src.api.server import validate_dataset_name
        assert validate_dataset_name("mmlu") is True
        assert validate_dataset_name("../../../etc/passwd") is False
        assert validate_dataset_name("dataset;rm") is False


# ============================================================
# Part 2: 响应格式 - 真实业务场景
# ============================================================
class TestResponseFormatBusinessScenarios:
    """响应格式：统一 API 响应结构"""

    def test_success_response_structure(self):
        """场景：成功响应格式"""
        from src.api.server import success_response
        resp = success_response({"key": "value"}, "操作成功")
        assert resp["code"] == 0
        assert resp["message"] == "操作成功"
        assert resp["data"] == {"key": "value"}

    def test_success_response_default_data(self):
        """场景：无 data 时默认为 None"""
        from src.api.server import success_response
        resp = success_response()
        assert resp["code"] == 0
        assert resp["message"] == "success"
        assert resp["data"] is None

    def test_error_response_structure(self):
        """场景：错误响应格式"""
        from src.api.server import error_response
        resp = error_response(404, "资源不存在")
        assert resp["code"] == 404
        assert resp["message"] == "资源不存在"
        assert resp["data"] is None


# ============================================================
# Part 3: 健康检查 - 真实业务场景
# ============================================================
class TestHealthCheckBusinessScenarios:
    """健康检查：K8s/负载均衡健康探测"""

    def test_root_endpoint_responds(self):
        """场景：根端点可达性"""
        from src.api.server import app
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "version" in data["data"]

    def test_simple_health_endpoint(self):
        """场景：基础健康检查"""
        from src.api.server import app
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "healthy"


# ============================================================
# Part 4: 评估器端点 - 真实业务场景
# ============================================================
class TestEvaluatorsEndpointBusinessScenarios:
    """评估器管理：列出/查询评估器"""

    def test_list_evaluators_returns_all_registered(self):
        """场景：前端展示可用评估器列表"""
        from src.api.server import app
        client = TestClient(app)
        response = client.get("/api/v1/evaluators")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        # 至少应包含 general
        names = [e["name"] for e in data["data"]]
        assert "general" in names

    def test_get_evaluator_detail_valid_name(self):
        """场景：查询具体评估器详情"""
        from src.api.server import app
        client = TestClient(app)
        response = client.get("/api/v1/evaluators/general")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["name"] == "general"
        assert "class_name" in data["data"]

    def test_get_evaluator_detail_sql_injection_blocked(self):
        """场景：SQL 注入尝试"""
        from src.api.server import app
        client = TestClient(app)
        # 路径中的特殊字符在 URL 层已被处理
        response = client.get("/api/v1/evaluators/general%3B%20DROP%20TABLE")
        # 应返回 404（无效名称）
        assert response.status_code == 404

    def test_get_evaluator_detail_not_found(self):
        """场景：查询不存在的评估器"""
        from src.api.server import app
        client = TestClient(app)
        response = client.get("/api/v1/evaluators/nonexistent_xyz")
        assert response.status_code == 404


# ============================================================
# Part 5: 登录认证 - 真实业务场景
# ============================================================
class TestLoginEndpointBusinessScenarios:
    """登录：用户身份认证"""

    def test_login_missing_body(self):
        """场景：客户端未传 body（Pydantic 验证失败返回 422）"""
        from src.api.server import app
        client = TestClient(app)
        response = client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_login_missing_username(self):
        """场景：缺少用户名（Pydantic 验证失败返回 422）"""
        from src.api.server import app
        client = TestClient(app)
        response = client.post("/api/v1/auth/login", json={"password": "test"})
        assert response.status_code == 422

    def test_login_missing_password(self):
        """场景：缺少密码（Pydantic 验证失败返回 422）"""
        from src.api.server import app
        client = TestClient(app)
        response = client.post("/api/v1/auth/login", json={"username": "alice"})
        assert response.status_code == 422

    def test_login_with_demo_mode_succeeds(self):
        """场景：演示模式（无 auth 模块）"""
        from src.api.server import app
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "demo", "password": "demo"},
        )
        # 当 HAS_AUTH=False 时，演示模式返回 200
        # 当 HAS_AUTH=True 时，可能 401（用户不存在）
        # 至少应返回结构化响应
        assert response.status_code in (200, 401)
        data = response.json()
        assert "code" in data
        assert "message" in data

    def test_login_strips_whitespace(self):
        """场景：用户名/密码全为空格"""
        from src.api.server import app
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "   ", "password": "   "},
        )
        assert response.status_code == 401


# ============================================================
# Part 6: Records CRUD - 真实业务场景
# ============================================================
class TestRecordsEndpointBusinessScenarios:
    """Records 端点：评测记录查询/管理"""

    def test_records_limit_validation(self):
        """场景：limit 越界"""
        from src.api.server import app
        client = TestClient(app)
        response = client.get("/api/v1/records?limit=0")
        assert response.status_code == 400
        response = client.get("/api/v1/records?limit=101")
        assert response.status_code == 400
        response = client.get("/api/v1/records?limit=10")
        # 数据库可能不可用，但接口契约应正常
        assert response.status_code in (200, 500)

    def test_records_search_limit_validation(self):
        """场景：搜索 limit 越界"""
        from src.api.server import app
        client = TestClient(app)
        response = client.get("/api/v1/records/search?limit=200")
        assert response.status_code == 400

    def test_records_search_offset_validation(self):
        """场景：搜索 offset 越界"""
        from src.api.server import app
        client = TestClient(app)
        response = client.get("/api/v1/records/search?offset=-1")
        assert response.status_code == 400
        response = client.get("/api/v1/records/search?offset=20000")
        assert response.status_code == 400

    def test_records_export_path_traversal_blocked(self):
        """场景：导出端点路径遍历防护

        真实业务风险：未授权用户可能通过 format 参数读取系统文件
        """
        from src.api.server import app
        client = TestClient(app)
        response = client.get("/api/v1/records/export?format=../../../etc/passwd")
        # 关键：应阻断路径遍历
        # 当前实现问题：返回 body 中 code=400 但 HTTP 状态为 200 (BUG!)
        # 客户端可能仅看 HTTP 状态码而忽略 body code
        data = response.json()
        assert data["code"] == 400
        # 应同时设置 HTTP 状态码为 400
        # 这是真实 Bug：HTTP 状态码与 body code 不一致
        if response.status_code == 200:
            # 记录 BUG，不让测试通过
            pytest.fail(
                "BUG: 路径遍历防护失败！HTTP 状态码为 200 但 body code=400，"
                "客户端可能忽略 body 直接当作成功处理"
            )

    def test_records_export_invalid_format(self):
        """场景：导出格式错误（xml 等不支持的格式）

        真实业务风险：客户端可能请求错误格式但拿到 CSV 而不知情
        """
        from src.api.server import app
        client = TestClient(app)
        response = client.get("/api/v1/records/export?format=xml")
        # 期望：HTTP 400 + body code=400
        # 当前实现：HTTP 200 + body code=400 (BUG!)
        data = response.json()
        assert data["code"] == 400
        if response.status_code == 200:
            pytest.fail(
                "BUG: 非法 format 参数未设置 HTTP 状态码！"
                "客户端只检查 HTTP 状态时会误判为成功"
            )


# ============================================================
# Part 7: 异常处理器 - 真实业务场景
# ============================================================
class TestExceptionHandlersBusinessScenarios:
    """FastAPI 异常处理器：统一错误响应"""

    def test_contract_error_returns_400(self):
        """场景：契约错误应返回 400/422

        真实 BUG：evaluate 端点接受 raw_data: dict，绕过了 Pydantic 验证
        """
        from src.exceptions import ContractValidationError
        from src.api.server import app
        client = TestClient(app)

        # 触发 ContractValidationError（通过 evaluate 端点）
        # 客户端传空 body 触发 Pydantic ValidationError
        response = client.post("/api/v1/evaluate", json={"type": "general"})  # 缺 id
        # 期望：400 或 422（契约错误）
        # 当前实现：返回 200 (BUG! 因为 evaluate 端点用 dict 而非 Pydantic model)
        if response.status_code == 200:
            pytest.fail(
                "BUG: evaluate 端点绕过 Pydantic 验证！"
                "必填字段缺失时仍返回 200，业务方无法识别非法请求"
            )
        assert response.status_code in (400, 422)


# ============================================================
# Part 8: 端到端评测流程 - 真实业务场景
# ============================================================
class TestEvaluateEndpointBusinessScenarios:
    """/api/v1/evaluate 端到端业务场景"""

    def test_evaluate_with_mock_client(self):
        """场景：业务方通过 API 提交评测（mock LLM）"""
        from src.api.server import app
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        client = TestClient(app)
        # 注入 mock 客户端：直接 patch service 中的 LLM 调用
        with patch("src.services.evaluator_svc.create_llm_client") as mock_create:
            mock_llm = MagicMock()
            mock_llm.config = MagicMock()
            mock_llm.config.model_name = "test-model"
            mock_llm.chat = MagicMock(return_value="ok response")
            mock_create.return_value = mock_llm

            response = client.post(
                "/api/v1/evaluate",
                json={
                    "id": "api_case_001",
                    "type": "general",
                    "payload": {"user_input": "test query"},
                },
            )

        # 业务上 DB 不可用时返回 200（业务成功）+ 内部持久化失败
        # 或者 500（完全失败）
        # 关键：不应 400（说明是契约错误）
        if response.status_code == 200:
            data = response.json()
            assert data["code"] == 0
        else:
            # DB 不可用属于基础设施问题
            assert response.status_code in (500, 422)

    def test_evaluate_missing_required_fields(self):
        """场景：缺 id 字段"""
        from src.api.server import app
        client = TestClient(app)
        response = client.post(
            "/api/v1/evaluate",
            json={"type": "general", "payload": {"user_input": "test"}},
        )
        # 缺 id 应被 Pydantic 拦截
        assert response.status_code in (400, 422)

    def test_evaluate_unknown_evaluator_type(self):
        """场景：未注册的评估器类型"""
        from src.api.server import app
        client = TestClient(app)
        response = client.post(
            "/api/v1/evaluate",
            json={
                "id": "case_unknown",
                "type": "definitely_not_registered_evaluator_xyz",
                "payload": {"user_input": "test"},
            },
        )
        # 应返回 422（领域错误）
        assert response.status_code in (400, 422)
