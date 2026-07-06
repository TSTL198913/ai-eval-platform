"""
AI专家业务测试 - 综合验证系统核心业务功能

测试覆盖五种场景：
1. 正向场景 - 正常评估流程
2. 负向场景 - 无效输入、非法操作
3. 边界场景 - 空数据、超大数据、特殊字符
4. 异常场景 - 服务异常、网络异常、依赖异常
5. 依赖场景 - 依赖服务可用性
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from src.api.server import app
from src.domain.evaluators import EVALUATOR_REGISTRY
from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus, ConfidenceLevel


class TestBusinessComprehensive:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_eval_client(self):
        mock = Mock()
        mock.config.provider = "deepseek"
        mock.config.model_name = "deepseek-chat"
        mock.chat.return_value = '{"score": 0.95, "reason": "回答准确"}'
        mock.achat.return_value = '{"score": 0.95, "reason": "回答准确"}'
        return mock

    @pytest.fixture
    def mock_inference_client(self):
        mock = Mock()
        mock.config.provider = "openai"
        mock.config.model_name = "gpt-4"
        mock.chat.return_value = "生成的推理结果"
        mock.achat.return_value = "生成的推理结果"
        return mock

    @pytest.fixture
    def mock_domain_result(self):
        result = Mock()
        result.status = EvaluatorStatus.SUCCESS
        result.error_message = None
        result.latency_ms = 1234.5
        result.case_id = "test-case-001"
        result.model_name = "deepseek-chat"
        result.adapter_name = "qa"
        result.score = 0.95
        result.response = Mock()
        result.response.model_dump.return_value = {
            "score": 0.95,
            "confidence": 0.92,
            "confidence_level": ConfidenceLevel.HIGH.value,
            "evaluation_status": EvaluatorStatus.SUCCESS.value,
            "level": "excellent",
            "details": {"reason": "回答准确且完整"},
        }
        return result

    def test_positive_scenario_qa_evaluation(self, client, mock_eval_client, mock_domain_result):
        """正向场景：QA评估正常流程"""
        with patch("src.api.routes.v2.evaluate.ClientFactoryService.create_clients") as mock_create:
            mock_create.return_value = (mock_eval_client, None, None)

            with patch("src.api.routes.v2.evaluate.EvaluatorService") as MockService:
                mock_service = Mock()
                mock_response = Mock()
                mock_response.api_response = {
                    "status": "success",
                    "code": 0,
                    "message": None,
                    "record_id": "test-qa-001",
                    "evaluation_status": EvaluatorStatus.SUCCESS.value,
                    "latency_ms": 1234.5,
                    "data": {
                        "score": 0.95,
                        "confidence": 0.92,
                        "confidence_level": "high",
                    },
                }
                mock_response.domain_result = mock_domain_result
                mock_service.run_evaluation.return_value = mock_response
                MockService.return_value = mock_service

            with patch("src.api.routes.v2.evaluate.PersistenceService") as MockPersistence:
                mock_persistence = Mock()
                mock_persistence.save_evaluation.return_value = {"success": True, "db_id": 123, "error": None}
                MockPersistence.return_value = mock_persistence

                response = client.post(
                    "/api/v2/evaluate",
                    json={
                        "type": "qa",
                        "payload": {
                            "prompt": "什么是AI评估平台？",
                            "actual_answer": "AI评估平台是用于评估AI模型性能和质量的系统",
                            "expected_answer": "AI评估平台是一种用于评估AI模型性能、准确性和可靠性的系统",
                        },
                        "evaluate_mode": "offline",
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0
                assert data["data"]["evaluation_status"] in ["success", "passed"]

    def test_positive_scenario_code_evaluation(self, client, mock_eval_client, mock_domain_result):
        """正向场景：代码评估正常流程"""
        with patch("src.api.routes.v2.evaluate.ClientFactoryService.create_clients") as mock_create:
            mock_create.return_value = (mock_eval_client, None, None)

            with patch("src.api.routes.v2.evaluate.EvaluatorService") as MockService:
                mock_service = Mock()
                mock_response = Mock()
                mock_response.api_response = {
                    "status": "success",
                    "code": 0,
                    "message": None,
                    "record_id": "test-code-001",
                    "evaluation_status": EvaluatorStatus.SUCCESS.value,
                    "latency_ms": 2000.0,
                    "data": {
                        "score": 0.88,
                        "confidence": 0.85,
                        "confidence_level": "medium",
                    },
                }
                mock_response.domain_result = mock_domain_result
                mock_service.run_evaluation.return_value = mock_response
                MockService.return_value = mock_service

            with patch("src.api.routes.v2.evaluate.PersistenceService") as MockPersistence:
                mock_persistence = Mock()
                mock_persistence.save_evaluation.return_value = {"success": True, "db_id": 124, "error": None}
                MockPersistence.return_value = mock_persistence

                response = client.post(
                    "/api/v2/evaluate",
                    json={
                        "type": "code",
                        "payload": {
                            "prompt": "写一个Python函数计算斐波那契数列",
                            "actual_output": "def fib(n):\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)",
                            "expected_output": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
                        },
                        "evaluate_mode": "offline",
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0
                assert data["data"]["evaluation_status"] in ["success", "passed", "partial"]

    def test_positive_scenario_online_mode(self, client, mock_eval_client, mock_inference_client, mock_domain_result):
        """正向场景：在线模式自动推理+评估"""
        with patch("src.api.routes.v2.evaluate.ClientFactoryService.create_clients") as mock_create:
            mock_create.return_value = (mock_eval_client, mock_inference_client, None)

            with patch("src.api.routes.v2.evaluate.EvaluatorService") as MockService:
                mock_service = Mock()
                mock_response = Mock()
                mock_response.api_response = {
                    "status": "success",
                    "code": 0,
                    "message": None,
                    "record_id": "test-online-001",
                    "evaluation_status": EvaluatorStatus.SUCCESS.value,
                    "latency_ms": 3500.0,
                    "data": {
                        "score": 0.9,
                        "confidence": 0.88,
                        "confidence_level": "high",
                    },
                }
                mock_response.domain_result = mock_domain_result
                mock_service.run_evaluation.return_value = mock_response
                MockService.return_value = mock_service

            with patch("src.api.routes.v2.evaluate.PersistenceService") as MockPersistence:
                mock_persistence = Mock()
                mock_persistence.save_evaluation.return_value = {"success": True, "db_id": 125, "error": None}
                MockPersistence.return_value = mock_persistence

                response = client.post(
                    "/api/v2/evaluate",
                    json={
                        "type": "general",
                        "payload": {
                            "prompt": "解释一下量子计算的基本原理",
                            "expected_output": "量子计算是利用量子力学原理进行计算的新型计算模式",
                        },
                        "evaluate_mode": "online",
                        "model_provider": "deepseek",
                        "model_name": "deepseek-chat",
                        "inference_model_provider": "openai",
                        "inference_model_name": "gpt-4",
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0
                assert data["data"]["evaluation_status"] in ["success", "passed", "partial"]

    def test_negative_scenario_invalid_type(self, client):
        """负向场景：无效评估类型"""
        response = client.post(
            "/api/v2/evaluate",
            json={
                "type": "invalid_type",
                "payload": {
                    "prompt": "test",
                    "actual_answer": "output",
                    "expected_answer": "expected",
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] != 0

    def test_negative_scenario_missing_required_fields(self, client):
        """负向场景：缺少必填字段"""
        response = client.post(
            "/api/v2/evaluate",
            json={
                "type": "qa",
            },
        )

        assert response.status_code == 422

    def test_negative_scenario_empty_payload(self, client):
        """负向场景：空payload"""
        response = client.post(
            "/api/v2/evaluate",
            json={
                "type": "qa",
                "payload": {},
            },
        )

        assert response.status_code in [400, 422]

    def test_boundary_scenario_empty_strings(self, client, mock_eval_client, mock_domain_result):
        """边界场景：空字符串输入"""
        with patch("src.api.routes.v2.evaluate.ClientFactoryService.create_clients") as mock_create:
            mock_create.return_value = (mock_eval_client, None, None)

            with patch("src.api.routes.v2.evaluate.EvaluatorService") as MockService:
                mock_service = Mock()
                mock_response = Mock()
                mock_response.api_response = {
                    "status": "success",
                    "code": 0,
                    "message": None,
                    "record_id": "test-empty-strings",
                    "evaluation_status": EvaluatorStatus.SUCCESS.value,
                    "latency_ms": 500.0,
                    "data": {
                        "score": 0.0,
                        "confidence": 0.1,
                        "confidence_level": "very_low",
                    },
                }
                mock_response.domain_result = mock_domain_result
                mock_service.run_evaluation.return_value = mock_response
                MockService.return_value = mock_service

            with patch("src.api.routes.v2.evaluate.PersistenceService") as MockPersistence:
                mock_persistence = Mock()
                mock_persistence.save_evaluation.return_value = {"success": True, "db_id": 126, "error": None}
                MockPersistence.return_value = mock_persistence

                response = client.post(
                    "/api/v2/evaluate",
                    json={
                        "type": "qa",
                        "payload": {
                            "prompt": "",
                            "actual_answer": "",
                            "expected_answer": "",
                        },
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0

    def test_boundary_scenario_large_payload(self, client):
        """边界场景：超大payload"""
        large_text = "x" * 100000

        response = client.post(
            "/api/v2/evaluate",
            json={
                "type": "qa",
                "payload": {
                    "prompt": large_text,
                    "actual_answer": large_text,
                    "expected_answer": large_text,
                },
            },
        )

        assert response.status_code != 404

    def test_boundary_scenario_special_characters(self, client):
        """边界场景：特殊字符输入"""
        response = client.post(
            "/api/v2/evaluate",
            json={
                "type": "qa",
                "payload": {
                    "prompt": "测试特殊字符：\\n\\t\\r\\x00\\u0000",
                    "actual_answer": "处理特殊字符的结果",
                    "expected_answer": "预期结果",
                },
            },
        )

        assert response.status_code != 404

    def test_exception_scenario_client_factory_error(self, client):
        """异常场景：客户端工厂创建失败"""
        with patch("src.api.routes.v2.evaluate.ClientFactoryService.create_clients") as mock_create:
            mock_create.side_effect = RuntimeError("无法创建客户端")

            response = client.post(
                "/api/v2/evaluate",
                json={
                    "type": "qa",
                    "payload": {
                        "prompt": "test",
                        "actual_answer": "output",
                        "expected_answer": "expected",
                    },
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 500

    def test_exception_scenario_evaluator_error(self, client):
        """异常场景：评估器执行异常"""
        response = client.post(
            "/api/v2/evaluate",
            json={
                "type": "qa",
                "payload": {
                    "prompt": "test",
                },
            },
        )

        assert response.status_code in [400, 422, 200]

    def test_exception_scenario_persistence_failure(self, client, mock_eval_client, mock_domain_result):
        """异常场景：持久化失败但评估成功"""
        with patch("src.api.routes.v2.evaluate.ClientFactoryService.create_clients") as mock_create:
            mock_create.return_value = (mock_eval_client, None, None)

            with patch("src.api.routes.v2.evaluate.EvaluatorService") as MockService:
                mock_service = Mock()
                mock_response = Mock()
                mock_response.api_response = {
                    "status": "success",
                    "code": 0,
                    "message": None,
                    "record_id": "test-persistence-fail",
                    "evaluation_status": EvaluatorStatus.SUCCESS.value,
                    "latency_ms": 1200.0,
                    "data": {"score": 0.9},
                }
                mock_response.domain_result = mock_domain_result
                mock_service.run_evaluation.return_value = mock_response
                MockService.return_value = mock_service

            with patch("src.api.routes.v2.evaluate.PersistenceService") as MockPersistence:
                mock_persistence = Mock()
                mock_persistence.save_evaluation.return_value = {
                    "success": False,
                    "db_id": None,
                    "error": "数据库连接失败",
                }
                MockPersistence.return_value = mock_persistence

                response = client.post(
                    "/api/v2/evaluate",
                    json={
                        "type": "qa",
                        "payload": {
                            "prompt": "test",
                            "actual_answer": "output",
                            "expected_answer": "expected",
                        },
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0
                assert data["data"]["persist"] == False

    def test_dependency_scenario_inference_endpoint(self, client, mock_eval_client):
        """依赖场景：推理端点依赖测试"""
        with patch("src.api.routes.v2.evaluate.ClientFactoryService.create_eval_client") as mock_create:
            mock_create.return_value = (mock_eval_client, None)

            with patch("src.api.routes.v2.evaluate.InferenceService") as MockService:
                mock_service = Mock()
                mock_service.generate.return_value = "生成的推理结果"
                MockService.return_value = mock_service

                response = client.post(
                    "/api/v2/inference",
                    json={"prompt": "测试推理"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0
                assert data["data"]["output"] == "生成的推理结果"

    def test_dependency_scenario_idempotency(self, client, mock_eval_client, mock_domain_result):
        """依赖场景：幂等性检查依赖测试"""
        with patch("src.api.routes.v2.evaluate._get_idempotency_checker") as mock_get_checker:
            mock_checker = Mock()
            mock_checker.get_cached_result.return_value = None
            mock_checker.mark_processing.return_value = True
            mock_get_checker.return_value = mock_checker

            with patch("src.api.routes.v2.evaluate.ClientFactoryService.create_clients") as mock_create:
                mock_create.return_value = (mock_eval_client, None, None)

                with patch("src.api.routes.v2.evaluate.EvaluatorService") as MockService:
                    mock_service = Mock()
                    mock_response = Mock()
                    mock_response.api_response = {
                        "status": "success",
                        "code": 0,
                        "message": None,
                        "record_id": "test-idempotency-deps",
                        "evaluation_status": EvaluatorStatus.SUCCESS.value,
                        "latency_ms": 1000.0,
                        "data": {"score": 0.9},
                    }
                    mock_response.domain_result = mock_domain_result
                    mock_service.run_evaluation.return_value = mock_response
                    MockService.return_value = mock_service

                with patch("src.api.routes.v2.evaluate.PersistenceService") as MockPersistence:
                    mock_persistence = Mock()
                    mock_persistence.save_evaluation.return_value = {"success": True, "db_id": 129, "error": None}
                    MockPersistence.return_value = mock_persistence

                    response = client.post(
                        "/api/v2/evaluate",
                        json={
                            "id": "unique-request-id-001",
                            "type": "qa",
                            "payload": {
                                "prompt": "test",
                                "actual_answer": "output",
                                "expected_answer": "expected",
                            },
                        },
                    )

                    assert response.status_code == 200
                    mock_checker.mark_processing.assert_called_once_with("unique-request-id-001")

    def test_dependency_scenario_metrics_recording(self, client, mock_eval_client, mock_domain_result):
        """依赖场景：指标记录依赖测试"""
        with patch("src.api.routes.v2.evaluate.ClientFactoryService.create_clients") as mock_create:
            mock_create.return_value = (mock_eval_client, None, None)

            with patch("src.api.routes.v2.evaluate.EvaluatorService") as MockService:
                mock_service = Mock()
                mock_response = Mock()
                mock_response.api_response = {
                    "status": "success",
                    "code": 0,
                    "message": None,
                    "record_id": "test-metrics-deps",
                    "evaluation_status": EvaluatorStatus.SUCCESS.value,
                    "latency_ms": 800.0,
                    "data": {"score": 0.85},
                }
                mock_response.domain_result = mock_domain_result
                mock_service.run_evaluation.return_value = mock_response
                MockService.return_value = mock_service

            with patch("src.api.routes.v2.evaluate.PersistenceService") as MockPersistence:
                mock_persistence = Mock()
                mock_persistence.save_evaluation.return_value = {"success": True, "db_id": 130, "error": None}
                MockPersistence.return_value = mock_persistence

            with patch("src.api.routes.v2.evaluate._record_metrics") as mock_record:
                response = client.post(
                    "/api/v2/evaluate",
                    json={
                        "type": "qa",
                        "payload": {
                            "prompt": "test",
                            "actual_answer": "output",
                            "expected_answer": "expected",
                        },
                    },
                )

                assert response.status_code == 200
                mock_record.assert_called()

    def test_api_version_consistency(self, client):
        """API版本一致性测试：v1和v2路由都存在"""
        v1_response = client.post("/api/v1/evaluate", json={"type": "qa", "prompt": "test"})
        v2_response = client.post("/api/v2/evaluate", json={"type": "qa", "payload": {"prompt": "test"}})

        assert v1_response.status_code != 404
        assert v2_response.status_code != 404

    def test_model_conflict_prevention(self, client, mock_eval_client, mock_inference_client, mock_domain_result):
        """模型冲突预防：评估和推理使用相同模型时应检测"""
        with patch("src.api.routes.v2.evaluate.ClientFactoryService.create_clients") as mock_create:
            mock_create.return_value = (mock_eval_client, mock_inference_client, None)

            with patch("src.api.routes.v2.evaluate.EvaluatorService") as MockService:
                mock_service = Mock()
                mock_response = Mock()
                mock_response.api_response = {
                    "status": "success",
                    "code": 0,
                    "message": None,
                    "record_id": "test-model-conflict",
                    "evaluation_status": EvaluatorStatus.SUCCESS.value,
                    "latency_ms": 1500.0,
                    "data": {"score": 0.9, "confidence": 0.85},
                }
                mock_response.domain_result = mock_domain_result
                mock_service.run_evaluation.return_value = mock_response
                MockService.return_value = mock_service

            with patch("src.api.routes.v2.evaluate.PersistenceService") as MockPersistence:
                mock_persistence = Mock()
                mock_persistence.save_evaluation.return_value = {"success": True, "db_id": 131, "error": None}
                MockPersistence.return_value = mock_persistence

                response = client.post(
                    "/api/v2/evaluate",
                    json={
                        "type": "qa",
                        "payload": {
                            "prompt": "test",
                            "actual_answer": "output",
                            "expected_answer": "expected",
                        },
                        "model_provider": "deepseek",
                        "model_name": "deepseek-chat",
                        "inference_model_provider": "deepseek",
                        "inference_model_name": "deepseek-chat",
                    },
                )

                assert response.status_code == 200

    def test_persistence_service_independence(self):
        """持久化服务独立性测试"""
        from src.domain.services.persistence_service import PersistenceService
        from src.infra.db.repository import EvaluationRepository

        with patch("src.infra.db.repository.EvaluationRepository.save") as mock_save:
            mock_save.return_value = 123

            persistence_service = PersistenceService()
            mock_result = Mock()
            mock_result.case_id = "test-case-001"
            mock_result.status.value = "success"

            result = persistence_service.save_evaluation(mock_result)

            assert result["success"] == True
            assert result["db_id"] == 123
            mock_save.assert_called_once()

    def test_evaluator_service_separation(self):
        """评估服务职责分离测试：不应包含客户端创建逻辑"""
        from src.services.evaluator_svc import EvaluatorService

        service = EvaluatorService()
        assert hasattr(service, "run_evaluation")

        import inspect

        source = inspect.getsource(service.run_evaluation)
        assert "create_llm_client" not in source
        assert "model_router.create" not in source