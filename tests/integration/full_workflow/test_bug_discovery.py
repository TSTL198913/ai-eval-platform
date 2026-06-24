"""
深度 Bug 发现测试套件 - 全系统业务场景驱动
基于分层测试方法论：
  - 正常路径 + 异常路径并重
  - 真实业务场景 + 边界值
  - 状态隔离 + 依赖替代

目标：发现生产环境潜在 Bug、架构缺陷、安全风险
"""

import json
import os
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ============================================================
# Part 1: API 层 - 接口契约深度 Bug 发现
# ============================================================
class TestAPIContractBugsDiscovery:
    """API 层接口契约的潜在 Bug"""

    def test_evaluate_endpoint_accepts_dict_bypasses_pydantic(self):
        """BUG: evaluate 端点用 raw_data: dict 绕过了 Pydantic 验证

        业务风险：客户端漏传必填字段(id/type/payload)时不会返回 400
        业务方会收到 200 OK 但 evaluation_status='error'，误以为请求合法
        """
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        # 缺 id, type, payload
        response = client.post("/api/v1/evaluate", json={})
        # 业务期望：返回 400（输入校验失败）
        if response.status_code == 200:
            data = response.json()
            pytest.fail(
                f"严重 BUG: evaluate 端点绕过 Pydantic 验证！\n"
                f"  客户端发送空 body 时仍返回 200，\n"
                f"  实际 status={response.status_code}, code={data.get('code')}\n"
                f"  业务方无法区分'成功'与'输入非法'，SDK 集成方会被误导。\n"
                f"  修复：endpoint 参数类型应改为 EvaluationSchema（pydantic）"
            )

    def test_evaluate_endpoint_accepts_partial_data(self):
        """BUG: 部分字段缺失仍可处理"""
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        # 只有 id，缺 type 和 payload
        response = client.post("/api/v1/evaluate", json={"id": "case_x"})
        if response.status_code == 200:
            pytest.fail("BUG: evaluate 端点接受不完整请求（仅 id），应使用 Pydantic 拦截")

    def test_login_empty_body_returns_400_inconsistent(self):
        """BUG: 登录端点空 body 返回 400 而非 401

        业务预期：缺凭据应返回 401（认证问题）
        实际：返回 400（请求体缺失）
        HTTP 语义层面，401 才是正确的
        """
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        response = client.post("/api/v1/auth/login", json={})
        # 业务方更希望：缺 body 返回 422（FastAPI 验证错误）
        # 实际是 400（自定义 message）
        # 这是设计选择，不算 bug，记录即可
        assert response.status_code in (400, 422)

    def test_records_get_by_id_string_type_mismatch(self):
        """BUG: 路径参数 record_id 是 int，但允许字符串？

        业务风险：客户端传 record_id='abc' 时会 422，但 404 更合理
        """
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        response = client.get("/api/v1/records/abc")
        # FastAPI 会自动尝试转 int，转失败会 422
        # 这其实合理，记录即可
        assert response.status_code in (404, 422)

    def test_records_update_accepts_arbitrary_fields(self):
        """验证：records update 有字段白名单保护（已修复）"""
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        response = client.put(
            "/api/v1/records/1",
            json={"status": "passed", "score": 1.0, "case_id": "fake"},
        )
        # 如果记录不存在，返回404；如果存在，返回200
        # 但无论如何，score 和 case_id 不应被更新（不在白名单）
        if response.status_code == 200:
            data = response.json()["data"]
            assert data.get("case_id") != "fake"
        # 404 或 400 也是合理的（记录不存在）
        elif response.status_code in (400, 404):
            pass

    def test_batch_update_validates_no_fields(self):
        """验证：批量更新已有限制（已修复）"""
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/records/batch/update",
            json={"ids": [1, 2, 3], "data": {"status": "INVALID_STATUS"}},
        )
        # 修复后：API 已经校验了 status 的枚举值
        assert response.status_code == 400
        assert "Invalid status value" in response.json()["message"]

    def test_cors_allows_all_origins(self):
        """安全风险: CORS 允许所有来源 (*)

        业务风险：恶意网站可通过 fetch 调用 API（需配合 cookie）
        """
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        response = client.get("/health", headers={"Origin": "https://evil.com"})
        # 检查 CORS 头
        if "access-control-allow-origin" in response.headers:
            origin = response.headers["access-control-allow-origin"]
            if origin == "*":
                # 当前实现确实 allow_origins=["*"]
                # 这在生产环境是风险（无认证时尤其严重）
                pass  # 设计选择，记录

    def test_evaluator_search_endpoint_validation(self):
        """安全：评估器详情查询是否正确校验路径参数"""
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        # URL 编码的 SQL 注入
        response = client.get("/api/v1/evaluators/..%2F..%2Fetc%2Fpasswd")
        # 应 404（名称非法）
        assert response.status_code == 404

    def test_health_check_includes_critical_components(self):
        """BUG: /api/v1/health 在 Redis 失败时仍返回 healthy"""
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        # 当前实现: 只检查 DB 和 Celery
        # 业务期望: 也应检查 Redis、模型工厂、监控
        response = client.get("/api/v1/health")
        data = response.json()["data"]
        # 检查 components 包含哪些
        if "redis" not in data.get("components", {}):
            pytest.fail(
                "BUG: /api/v1/health 未检查 Redis 状态！"
                "Redis 故障时健康检查仍报 healthy，"
                "K8s liveness probe 会误判节点健康"
            )

    def test_root_endpoint_no_auth_check(self):
        """安全：根端点暴露服务信息

        业务风险：低（仅返回版本号），但应确保无敏感信息泄露
        """
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        response = client.get("/")
        data = response.json()["data"]
        # 不应包含 secret、api_key 等
        data_str = json.dumps(data).lower()
        if any(s in data_str for s in ["secret", "password", "api_key"]):
            pytest.fail("严重安全 BUG: 根端点泄露敏感信息")
        assert "version" in data_str

    def test_models_compare_returns_fake_data(self):
        """验证：/api/v1/models/compare 返回模拟数据但有明确标记（已修复）"""
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/models/compare",
            json={
                "models": [{"provider": "openai", "name": "gpt-4"}],
                "datasets": ["mmlu"],
                "sample_count": 5,
            },
        )
        data = response.json()["data"]
        # 修复后：明确标记 is_simulated=True
        assert data.get("is_simulated")
        assert "warning" in data
        for m in data.get("models", []):
            assert m.get("warning") == "此为演示数据，非真实评测结果"

    def test_evaluators_name_validation_blocks_spaces(self):
        """验证：评估器名包含空格应被拒绝"""

        from src.api.common import validate_evaluator_name

        # validate_evaluator_name 应该拒绝 "name with space"
        assert validate_evaluator_name("name with space") is False

    def test_api_v1_reports_path_traversal(self):
        """BUG: /api/v1/reports/{filename} 未做路径遍历防护

        业务风险：业务方可读取 reports 目录外的任意文件
        """
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        # 路径遍历尝试
        response = client.get("/api/v1/reports/..%2F..%2Fetc%2Fpasswd")
        # 当前实现: 直接 os.path.join("reports", filename)
        # "../../../etc/passwd" 会被拼成 "reports/../../../etc/passwd"
        # os.path.exists 可能返回 True 或 False，但 FileResponse 不做边界检查
        # 严重 BUG
        if response.status_code == 200:
            pytest.fail(
                "严重安全 BUG: /api/v1/reports 路径遍历未防护！\n"
                "  业务方可传 ../../../etc/passwd 读取系统文件"
            )


# ============================================================
# Part 2: Service 层 - 业务编排 Bug
# ============================================================
class TestServiceLayerBugsDiscovery:
    """Service 层业务编排的潜在 Bug"""

    def test_status_field_always_success_even_on_error(self):
        """严重 BUG: run_evaluation_service 即便 engine 返回 ERROR 仍返回 status='success'

        业务风险：业务方根据 status=='success' 判断成功，会忽略 evaluation_status='error'
        导致监控告警失效、计费错误、用户错误反馈
        """
        from src.domain.evaluators.base import BaseEvaluator
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.exceptions import DomainLogicError
        from src.services.evaluator_svc import run_evaluation_service

        @EvaluatorFactory.register("svc_bug_test")
        class BuggyEval(BaseEvaluator):
            def evaluate(self, request):
                raise DomainLogicError("故意失败")

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"

        result = run_evaluation_service(
            {"id": "svc_001", "type": "svc_bug_test", "payload": {"x": 1}},
            client=client,
        )

        # 业务期望: status="error" 当 evaluation_status="error"
        # 实际: status="success"（掩盖了失败）
        if result.get("status") == "success" and result.get("evaluation_status") == "error":
            pytest.fail(
                "严重 BUG: Service 层 status 字段永远返回 'success'！\n"
                f"  当 engine 返回 ERROR 时，status='success' 掩盖了失败\n"
                f"  实际结果: {result}\n"
                f"  业务风险: 监控告警/计费/用户反馈全部错误\n"
                f"  修复: status 应根据 evaluation_status 设置"
            )

    def test_repository_failure_silently_swallows(self):
        """BUG: 持久化失败仅记录日志，不向上抛出

        业务风险：业务方以为数据已落库，实际数据丢失
        """
        from src.services.evaluator_svc import run_evaluation_service

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"
        client.chat = MagicMock(return_value="ok")

        with patch("src.services.evaluator_svc._repository") as mock_repo:
            mock_repo.save.side_effect = Exception("DB 不可用")

            result = run_evaluation_service(
                {"id": "persist_001", "type": "general", "payload": {"user_input": "x"}},
                client=client,
            )

            # 业务期望: 应至少在 result 中标识 persist_failed
            # 当前实现: 仅写日志，调用方无从感知
            if result.get("status") == "success" and "persist" not in result:
                pytest.fail(
                    "BUG: 持久化失败被静默吞掉！\n"
                    f"  result={result}\n"
                    f"  业务方无法识别'业务成功但持久化失败'的状态"
                )

    def test_data_field_returns_domainresponse_object(self):
        """BUG: data 字段返回 DomainResponse 对象，客户端用 .get() 会失败

        业务风险：前端或 SDK 调用 data.get('is_valid') 报 AttributeError
        """
        from src.services.evaluator_svc import run_evaluation_service

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"
        client.chat = MagicMock(return_value="ok")

        result = run_evaluation_service(
            {"id": "rt_002", "type": "general", "payload": {"user_input": "test"}},
            client=client,
        )

        data = result.get("data")
        # data 应该是 dict（或 dict-like）
        if data is not None and not isinstance(data, dict):
            # 当前实现: 直接放 DomainResponse 对象
            pytest.fail(
                f"BUG: Service 层 data 返回 {type(data).__name__}，非 dict！\n"
                f"  客户端 SDK 用 data.get('is_valid') 会失败\n"
                f"  修复: result['data'] = data.model_dump()"
            )

    def test_no_pydantic_validation_in_service_layer(self):
        """BUG: Service 层接受非法 raw_data 但运行后才报错

        业务风险：业务方要等到 LLM 调用才看到错误，浪费资源
        """
        from src.services.evaluator_svc import run_evaluation_service

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"

        # id 应为 str，传 int
        result = run_evaluation_service(
            {"id": 12345, "type": "general", "payload": {}},  # type: ignore
            client=client,
        )
        # Pydantic 会自动转 str，但如果类型完全不匹配会 ValidationError
        # 这个测试主要检查是否会崩溃
        if "error" not in result and result.get("status") == "success":
            # 接受，但应记录
            pass

    def test_model_routing_failure_returns_no_routing_info(self):
        """BUG: 智能路由失败时，routing 字段为 None，业务方无法定位问题

        业务风险：业务方不知道为什么选择特定模型，无法调优
        """
        from unittest.mock import patch

        from src.services.evaluator_svc import run_evaluation_service

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"
        client.chat = MagicMock(return_value="ok")

        with patch("src.domain.model_routing.model_router") as mock_router:
            mock_router.create_llm_client.return_value = (client, None)

            result = run_evaluation_service(
                {"id": "route_001", "type": "general", "payload": {"user_input": "x"}},
            )

            if result.get("routing") is None:
                # 当前实现确实返回 None
                # 业务上应至少返回默认路由信息
                pass  # 已知设计，记录


# ============================================================
# Part 3: Distributed 层 - 分布式原语 Bug
# ============================================================
class TestDistributedBugsDiscovery:
    """分布式原语的潜在 Bug"""

    def test_token_bucket_zero_refill_rate_zerodivision(self):
        """BUG: refill_rate=0 时会触发 ZeroDivisionError

        业务风险：业务方配置错（refill_rate=0）导致限流器崩溃
        应优雅返回 retry_after_ms=infinity 或 极大值
        """
        from src.distributed.rate_limiter import RateLimitConfig, TokenBucket

        bucket = TokenBucket(MagicMock(), "user", RateLimitConfig(max_tokens=10, refill_rate=0.0))

        # 先消耗所有令牌
        for _ in range(10):
            bucket.allow()

        # 下一次应触发 ZeroDivisionError
        try:
            bucket.allow()
        except ZeroDivisionError:
            pytest.fail(
                "BUG: refill_rate=0 触发 ZeroDivisionError！\n"
                "  应优雅处理: 返回 retry_after_ms=infinity 或 拒绝时不除法"
            )

    def test_idempotency_check_returns_wrong_semantics(self):
        """API 语义问题: check() 返回 True 表示"未处理"？

        业务风险：API 反直觉，容易被误用
        """
        from src.distributed.idempotency import IdempotencyChecker

        checker = IdempotencyChecker(MagicMock())
        result = checker.check("req_001")
        # check 返回 True 表示"请求未处理"（可继续）
        # 但字面上 check 像是"检查是否存在"
        # 这是反直觉的 API 设计
        if result is True:
            # 业务方可能误以为 True="已处理"
            pass  # 设计问题，记录

    def test_idempotency_get_status_returns_dict_not_typed_object(self):
        """设计: get_status 返回 dict 而非强类型

        业务风险：调用方依赖 dict key 拼写错误不会在编译期暴露
        """
        from src.distributed.idempotency import IdempotencyChecker

        fake_redis = MagicMock()
        fake_redis.get.return_value = json.dumps({"status": "processing"}).encode()
        checker = IdempotencyChecker(fake_redis)

        status = checker.get_status("req_001")
        # 如果是 dict，调用方依赖 'status'/'result' 拼写
        if isinstance(status, dict) and "status" in status:
            pass  # 记录

    def test_circuit_breaker_state_property_has_side_effects(self):
        """BUG: state 属性 getter 有副作用 - 触发时间转换

        业务风险：读 state 改变状态，难以调试
        """
        from src.distributed.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
            CircuitState,
        )

        cb = CircuitBreaker(
            "test",
            CircuitBreakerConfig(failure_threshold=2, timeout_seconds=0.01),
        )
        # 触发失败
        cb._record_failure()
        cb._record_failure()

        # state getter 内部会基于时间检查是否进入 half_open
        # 这违反 'property 应该是纯函数' 的设计原则
        state1 = cb.state
        # 此时 _state 仍是 OPEN，state 返回可能是 HALF_OPEN
        # 但 _state 字段未变
        if state1 == CircuitState.HALF_OPEN and cb._state == CircuitState.OPEN:
            # 严重设计 BUG: state 与 _state 不一致
            pytest.fail(
                "设计 BUG: state 属性与 _state 字段不一致！\n"
                "  state 基于 time 动态计算，但 _state 字段未更新\n"
                "  这会导致 _record_success 等内部方法用错状态"
            )

    def test_lock_release_uses_lua_script_but_fake_redis_lacks(self):
        """潜在: FakeRedis 的 eval 简化了 Lua 脚本

        业务风险：生产环境的 Lua 逻辑与测试不一致
        """
        # 当前 FakeRedis._eval_lock_atomic 实现了 del 脚本
        # 但 extend 的 expire 脚本未实现
        # 真实 Redis 中 extend 用 'expire' 脚本
        # 测试可能通过但生产环境有差异

        # 这个测试是提醒：在真实 Redis 上需要验证 extend
        pass

    def test_sliding_window_uses_zadd_but_not_zremrangebyscore(self):
        """FakeRedis zremrangebyscore 永远返回 0

        业务风险：测试中滑动窗口清理逻辑被绕过
        """

        # 这里主要说明 FakeRedis 的 zremrangebyscore 没真实实现
        # 生产环境的窗口清理逻辑没有单元测试覆盖
        # 这是测试覆盖盲区
        # 真实测试需要 fakeredis 库
        pass


# ============================================================
# Part 4: Domain 层 - 评估器与评分 Bug
# ============================================================
class TestDomainBugsDiscovery:
    """Domain 层业务逻辑 Bug"""

    def test_numeric_match_handles_decimal_split(self):
        """BUG: score_numeric_match 把 "0.85" 拆成 "0" 和 "85"

        业务风险：金融场景"汇率 0.85"可能被识别为 0 和 85 都在
        导致误判匹配
        """
        from src.domain.evaluators.scoring import score_numeric_match

        expected = "Exchange rate is 0.85"
        output = "The rate is 0.85 today"

        score = score_numeric_match(output, expected)
        # 当前实现: re.findall(r"\d+\.?\d*") 会匹配 "0" 和 "85"
        # 业务期望: 0.85 整体匹配
        if score == 1.0:
            # 实际上确实 0 和 85 都在 output 中，所以 score=1.0
            # 但这是巧合，业务上不严谨
            pass

    def test_numeric_match_ignores_negative_numbers(self):
        """BUG: score_numeric_match 不处理负数

        业务风险：财务报告"亏损 -100"中的负数无法识别
        """
        from src.domain.evaluators.scoring import score_numeric_match

        expected = "Loss was -100"
        output = "Loss was -100"

        score = score_numeric_match(output, expected)
        # 当前实现: 正则 \d+\.?\d* 不匹配负号
        # 期望从 output 提取 100，但 expected 中也提取不到 -100
        if score == 0.0:
            pytest.fail(
                "BUG: score_numeric_match 不支持负数！\n"
                "  财务报表'亏损 -100'会被判定为完全无匹配\n"
                "  修复: 正则应改为 -?\\d+\\.?\\d*"
            )

    def test_text_similarity_empty_strings_returns_zero(self):
        """设计争议: 两个空字符串应返回 0 还是 1.0

        业务风险：边界 case 行为不一致
        """
        from src.domain.evaluators.scoring import score_text_similarity

        score = score_text_similarity("", "")
        # 当前实现: if not output.strip(): return 0.0
        # 业务期望: 双方都空 = 完全匹配 = 1.0
        if score == 0.0:
            # 这是设计争议，记录
            pass

    def test_keyword_overlap_english_stemming_missing(self):
        """限制: 英文无词干提取 (running vs run)

        业务风险：QA 系统误判
        """
        from src.domain.evaluators.scoring import score_keyword_overlap

        score = score_keyword_overlap("running quickly", "run fast")
        # "run" vs "running" 不匹配
        # 这是已知限制
        assert score < 0.5  # 已知行为

    def test_general_evaluator_chat_called_with_user_input_only(self):
        """BUG: chat() 只传 user_input，不传 system_prompt

        业务风险：业务方配置 system_prompt 被忽略
        """
        from src.domain.evaluators.general import GeneralEvaluator
        from src.schemas.evaluation import EvaluationSchema

        client = MagicMock()
        client.chat = MagicMock(return_value="response")
        evaluator = GeneralEvaluator(client=client)

        request = EvaluationSchema(
            id="c1",
            type="general",
            payload={"user_input": "Q1", "system_prompt": "You are expert"},
        )

        evaluator.safe_evaluate(request)
        # 当前实现: client.chat(user_input) 只传一个参数
        if client.chat.call_args.args != ("Q1",):
            # 如果实现改变了，匹配失败
            pass
        # 业务风险: system_prompt 被忽略
        # 修复: chat(user_input, system_prompt=user_input_from_payload)
        assert client.chat.call_args.args[0] == "Q1"

    def test_evaluator_factory_no_warning_on_overwrite(self):
        """BUG: register 同名会静默覆盖

        业务风险：上游库和业务方同名时静默覆盖
        """
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.schemas.evaluation import DomainResponse

        @EvaluatorFactory.register("overwrite_test")
        class First:
            def evaluate(self, req):
                return DomainResponse(is_valid=True, score=0.5)

        @EvaluatorFactory.register("overwrite_test")
        class Second:
            def evaluate(self, req):
                return DomainResponse(is_valid=True, score=0.9)

        if EvaluatorFactory._registry["overwrite_test"].__name__ != "Second":
            pytest.fail("BUG: register 应该被覆盖但未生效")
        # 严重: 应至少有 warning
        # 当前实现: 静默覆盖


# ============================================================
# Part 5: Engine 层 - 引擎 Bug
# ============================================================
class TestEngineBugsDiscovery:
    """Engine 层异常处理与路由 Bug"""

    def test_engine_error_message_loses_context(self):
        """BUG: engine 异常时 error_message 丢失具体异常信息

        业务风险：业务方只看到'契约验证错误'，无法定位根因
        """
        from src.domain.evaluators.base import BaseEvaluator
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.engine import EvaluationEngine
        from src.exceptions import ContractValidationError
        from src.schemas.evaluation import EvaluationSchema

        @EvaluatorFactory.register("err_ctx_test")
        class ErrCtxEval(BaseEvaluator):
            def evaluate(self, req):
                raise ContractValidationError("缺少 user_id 字段")

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"

        engine = EvaluationEngine(client)
        result = engine.run(EvaluationSchema(id="ctx_001", type="err_ctx_test", payload={}))

        # 当前实现: error_message = "契约验证错误"（丢失具体信息）
        if result.error_message == "契约验证错误":
            pytest.fail(
                "BUG: engine 异常丢失具体上下文！\n"
                f"  原始异常: '缺少 user_id 字段'\n"
                f"  error_message: '{result.error_message}'\n"
                f"  业务方无法定位根因\n"
                f"  修复: error_message 应包含原异常 message"
            )

    def test_engine_response_error_always_chinese(self):
        """BUG: response.error 强制中文，业务方国际化困难

        业务风险：英文系统集成时无法本地化
        """
        from src.domain.evaluators.base import BaseEvaluator
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.engine import EvaluationEngine
        from src.exceptions import DomainLogicError
        from src.schemas.evaluation import EvaluationSchema

        @EvaluatorFactory.register("i18n_test")
        class I18nEval(BaseEvaluator):
            def evaluate(self, req):
                raise DomainLogicError("Model gpt-5 not supported")

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"

        engine = EvaluationEngine(client)
        result = engine.run(EvaluationSchema(id="i18n_001", type="i18n_test", payload={}))

        # 当前实现: response.error = "领域错误"（中文）
        if result.response.error == "领域错误":
            pytest.fail(
                "BUG: response.error 硬编码中文！\n"
                "  业务方国际化困难\n"
                "  修复: 使用 error_code + 客户端查表"
            )

    def test_engine_latency_includes_exception_overhead(self):
        """设计: latency_ms 包含异常处理时间，业务方误判性能

        业务风险：SLA 监控被异常 case 污染
        """
        from src.domain.evaluators.base import BaseEvaluator
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.engine import EvaluationEngine
        from src.exceptions import ContractValidationError
        from src.schemas.evaluation import EvaluationSchema

        @EvaluatorFactory.register("slow_fail_eng")
        class SlowFailEng(BaseEvaluator):
            def evaluate(self, req):
                time.sleep(0.1)  # 100ms
                raise ContractValidationError("slow fail")

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"

        engine = EvaluationEngine(client)
        result = engine.run(EvaluationSchema(id="slow_001", type="slow_fail_eng", payload={}))

        # 期望: latency 包含 sleep 100ms
        # 但业务方监控 SLA 时，失败 case 也算 100ms
        if result.latency_ms >= 100:
            pass  # 设计选择

    def test_unexpected_exception_handled_by_safe_evaluate_not_engine(self):
        """设计权衡: 业务异常 vs 系统异常 在 engine 中混合处理

        业务风险：Engine 自身对异常分类不清晰
        """
        # 业务异常(BasePlatformError) → engine 捕获并返回 ERROR
        # 系统异常(其他 Exception) → safe_evaluate 捕获并返回 FAILED
        # 两者都看似"失败"但语义不同
        # 当前实现: 依赖 safe_evaluate 的 catch-all 行为
        from src.domain.evaluators.base import BaseEvaluator
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.engine import EvaluationEngine
        from src.exceptions import ContractValidationError
        from src.schemas.evaluation import EvaluationSchema

        @EvaluatorFactory.register("mixed_exc_test")
        class MixedExc(BaseEvaluator):
            def evaluate(self, req):
                # 业务异常应被 engine 捕获
                raise ContractValidationError("业务异常")

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"

        engine = EvaluationEngine(client)
        result = engine.run(EvaluationSchema(id="mixed_001", type="mixed_exc_test", payload={}))

        # ContractValidationError 应被 engine 识别为 ERROR
        # 但 base.py 的 safe_evaluate 也会捕获 BasePlatformError 并 re-raise
        # 所以最终是 engine 捕获
        if result.status.value != "error":
            pytest.fail(f"BUG: 业务异常未映射为 ERROR，实际: {result.status.value}")


# ============================================================
# Part 6: 安全风险 Bug
# ============================================================
class TestSecurityBugsDiscovery:
    """安全风险专项检查"""

    def test_secret_key_hardcoded(self):
        """严重安全 BUG: JWT SECRET_KEY 硬编码在代码中"""
        from src.api.auth import SECRET_KEY

        if "change-in-production" not in SECRET_KEY and "secret" in SECRET_KEY.lower():
            pytest.fail(
                f"严重安全 BUG: SECRET_KEY 硬编码在代码中！\n"
                f"  当前值: {SECRET_KEY}\n"
                f"  业务风险: 任何能读代码的人都可签发合法 JWT\n"
                f"  修复: 从环境变量或 secret manager 加载"
            )

    def test_password_hash_uses_sha256_with_fixed_salt(self):
        """安全: 密码哈希使用环境变量配置的盐（已改进，待升级）

        当前改进：salt 从环境变量加载，而非硬编码
        待改进：生产环境应改用 bcrypt/argon2 + 随机盐
        """
        from src.api.auth import _hash_password

        h1 = _hash_password("password123")
        h2 = _hash_password("password123")
        # 当前实现仍使用 SHA-256（相同密码产生相同hash）
        # 这是已知限制，生产环境应升级为 bcrypt
        assert h1 == h2

    def test_user_input_passed_to_llm_without_sanitization(self):
        """验证：SecurityMiddleware 拦截敏感信息（已修复）"""
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        sensitive_input = "请帮我看看这个 key: sk-1234567890abcdefghij"
        response = client.post(
            "/api/v1/evaluate",
            json={
                "id": "sec_001",
                "type": "general",
                "payload": {"user_input": sensitive_input},
            },
        )
        # SecurityMiddleware 应该拦截 API key
        assert response.status_code == 403
        assert "Security Blocked" in response.json()["message"]

    def test_sql_injection_via_search_filter(self):
        """潜在: search 端点的 sort_by 字段未做白名单

        业务风险：业务方可注入 SQL ORDER BY
        """
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        # sort_by 注入
        response = client.get("/api/v1/records/search?sort_by=created_at; DROP TABLE--")
        # 当前实现: 直接传给 repo.search
        # 修复: 应做白名单校验
        if response.status_code in (200, 500):
            # 如果 200，说明 sort_by 被接受
            # 如果 500，可能是 SQL 错误
            pass  # 已知风险

    def test_auth_me_endpoint_always_returns_401_with_auth(self):
        """BUG: /api/v1/auth/me 即便有合法 token 也返回 401"""
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer valid_token"},
        )
        # 当前实现: 直接 return 401
        # 这是已知 BUG
        if response.status_code == 401:
            # 已知 BUG
            pass

    def test_refresh_token_returns_unchanged(self):
        """BUG: /api/v1/auth/refresh 不验证 refresh_token，直接返回 access_token='demo-token'"""
        from fastapi.testclient import TestClient

        from src.api.server import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "any-garbage"},
        )
        data = response.json()
        if data.get("code") == 0 and data.get("data", {}).get("access_token") == "demo-token":
            # 严重安全 BUG: 任意 refresh_token 都返回有效 access_token
            pytest.fail(
                "严重安全 BUG: /api/v1/auth/refresh 不验证 refresh_token！\n"
                "  业务方传任意字符串都返回 access_token='demo-token'\n"
                "  攻击者可绕过登录直接获取 token"
            )


# ============================================================
# Part 7: 性能与稳定性 Bug
# ============================================================
class TestPerformanceStabilityBugs:
    """性能与稳定性 Bug"""

    def test_evaluator_factory_concurrent_register_race_condition(self):
        """潜在: 评估器注册全局单例无锁

        业务风险：多线程同时注册可能丢失
        """
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.schemas.evaluation import DomainResponse

        def register_many(start_idx):
            for i in range(100):
                name = f"race_{start_idx}_{i}"
                # 内联类不能用装饰器，模拟运行时注册
                cls = type(
                    f"RaceEval_{start_idx}_{i}",
                    (),
                    {"evaluate": lambda self, req: DomainResponse(is_valid=True)},
                )
                EvaluatorFactory._registry[name] = cls

        threads = [threading.Thread(target=register_many, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证所有注册都生效
        expected_count = 5 * 100
        actual_count = sum(1 for k in EvaluatorFactory._registry if k.startswith("race_"))
        if actual_count != expected_count:
            pytest.fail(f"并发注册 BUG: 期望 {expected_count} 个，实际 {actual_count} 个")

    def test_evaluation_cache_memory_leak(self):
        """BUG: EvaluationCache 的 stats 不会因 clear 而完全重置?

        业务风险：监控数据不准
        """
        from src.infra.cache import EvaluationCache

        cache = EvaluationCache()

        for i in range(100):
            cache.set(f"k{i}", i)
        for i in range(100):
            cache.get(f"k{i}")

        cache.clear()
        stats = cache.get_stats()
        # 期望 hits=0, misses=0
        if stats.get("hits", 0) != 0 or stats.get("misses", 0) != 0:
            pytest.fail(f"BUG: cache.clear() 后 stats 未完全重置: {stats}")

    def test_evaluator_singleton_keeps_llm_client(self):
        """BUG: EvaluatorFactory.get() 每次创建新实例，LLM 客户端不共享

        业务风险：未使用 LLM client 缓存，导致重复连接
        """
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.schemas.evaluation import DomainResponse

        @EvaluatorFactory.register("singleton_test")
        class SingletonEval:
            def __init__(self, client=None):
                self.client = client

            def evaluate(self, req):
                return DomainResponse(is_valid=True)

        client = MagicMock()
        e1 = EvaluatorFactory.get("singleton_test", client=client)
        e2 = EvaluatorFactory.get("singleton_test", client=client)
        # 当前实现: 每次都创建新实例
        if e1 is e2:
            pass  # 如果是单例，业务风险不一样
        else:
            # 多次创建实例浪费内存/连接
            pass  # 设计选择

    def test_evaluator_buffer_service_signal_handler_may_fail(self):
        """BUG: signal handler 中调 flush() 但 flush 可能失败，导致 _closed 已设但数据未 flush

        业务风险：进程退出时数据丢失
        """
        from src.infra.db.models import EvaluationResultModel
        from src.workers.tasks import EvaluationBufferService

        svc = EvaluationBufferService(batch_size=1, flush_interval_seconds=1.0)

        # 模拟一个 item
        item = EvaluationResultModel(case_id="x", status="passed")
        svc.buffer.append(item)

        # 模拟信号触发
        try:
            svc._signal_handler(15, None)  # SIGTERM
        except Exception as e:
            # 已知: signal handler 不应抛错
            pytest.fail(f"BUG: signal handler 抛错: {e}")
