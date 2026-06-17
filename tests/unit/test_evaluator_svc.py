from unittest.mock import MagicMock, patch

import pytest

from src.exceptions import DomainLogicError
from src.schemas.evaluation import DomainResponse


class TestServiceExceptionHandler:
    """服务异常处理器测试"""

    def test_platform_error(self):
        """测试平台业务异常"""
        from src.services.evaluator_svc import service_exception_handler

        @service_exception_handler
        def raise_platform_error():
            from src.exceptions import BasePlatformError

            raise BasePlatformError("test message", "TEST_ERROR")

        result = raise_platform_error()
        assert result["status"] == "error"
        assert result["code"] == "TEST_ERROR"
        assert "test message" in result["message"]

    def test_validation_error(self):
        """测试验证异常"""
        from src.services.evaluator_svc import service_exception_handler

        class FakeValidationError(Exception):
            pass

        @service_exception_handler
        def raise_validation_error():
            raise FakeValidationError("invalid input")

        result = raise_validation_error()
        assert result["status"] == "error"
        assert result["code"] == "CONTRACT_ERROR"

    def test_generic_exception(self):
        """测试通用异常"""
        from src.services.evaluator_svc import service_exception_handler

        @service_exception_handler
        def raise_generic_error():
            raise RuntimeError("something broke")

        result = raise_generic_error()
        assert result["status"] == "error"
        assert result["code"] == "INTERNAL_ERROR"


class TestNormalizeRawData:
    """数据规范化测试"""

    def test_with_payload(self):
        """测试已有payload"""
        from src.services.evaluator_svc import _normalize_raw_data

        raw = {"id": "123", "type": "qa", "payload": {"question": "q"}, "metadata": {}}
        result = _normalize_raw_data(raw)

        assert result == raw

    def test_without_payload(self):
        """测试无payload"""
        from src.services.evaluator_svc import _normalize_raw_data

        raw = {"id": "123", "type": "qa", "question": "q", "answer": "a", "metadata": {"k": "v"}}
        result = _normalize_raw_data(raw)

        assert result["id"] == "123"
        assert result["type"] == "qa"
        assert result["payload"]["question"] == "q"
        assert result["payload"]["answer"] == "a"
        assert result["metadata"] == {"k": "v"}

    def test_without_payload_no_id(self):
        """测试无payload且无id"""
        from src.services.evaluator_svc import _normalize_raw_data

        raw = {"type": "qa", "question": "q"}
        result = _normalize_raw_data(raw)

        assert result["id"] == "unknown"
        assert result["metadata"] == {}


class TestRunEvaluationService:
    """评测服务测试"""

    @patch("src.services.evaluator_svc._repository")
    @patch("src.services.evaluator_svc.EvaluationEngine")
    def test_run_evaluation_success(self, mock_engine_class, mock_repo, mock_llm):
        """测试评测成功"""
        from src.services.evaluator_svc import run_evaluation_service
        from src.schemas.schemas import EvaluationStatus

        mock_result = MagicMock()
        mock_result.case_id = "c1"
        mock_result.status = EvaluationStatus.PASSED
        mock_result.latency_ms = 100.0
        mock_result.response = DomainResponse(is_valid=True, score=1.0)

        mock_engine = MagicMock()
        mock_engine.run.return_value = mock_result
        mock_engine_class.return_value = mock_engine

        mock_repo.save.return_value = 1

        raw_data = {
            "id": "c1",
            "type": "general",
            "payload": {"user_input": "hello"},
            "metadata": {},
        }

        result = run_evaluation_service(raw_data, client=mock_llm)

        assert result["status"] == "success"
        assert result["record_id"] == "c1"
        mock_repo.save.assert_called_once()

    @patch("src.services.evaluator_svc._repository")
    @patch("src.services.evaluator_svc.EvaluationEngine")
    def test_run_evaluation_persistence_failure(self, mock_engine_class, mock_repo, mock_llm):
        """测试评测持久化失败"""
        from src.services.evaluator_svc import run_evaluation_service
        from src.schemas.schemas import EvaluationStatus

        mock_result = MagicMock()
        mock_result.case_id = "c1"
        mock_result.status = EvaluationStatus.PASSED
        mock_result.latency_ms = 100.0
        mock_result.response = DomainResponse(is_valid=True, score=1.0)

        mock_engine = MagicMock()
        mock_engine.run.return_value = mock_result
        mock_engine_class.return_value = mock_engine

        mock_repo.save.side_effect = RuntimeError("DB error")

        raw_data = {
            "id": "c1",
            "type": "general",
            "payload": {"user_input": "hello"},
            "metadata": {},
        }

        result = run_evaluation_service(raw_data, client=mock_llm)

        assert result["status"] == "success"
        mock_repo.save.assert_called_once()

    def test_run_evaluation_unknown_type(self):
        """测试未知评测类型"""
        from src.services.evaluator_svc import run_evaluation_service

        raw_data = {
            "id": "c1",
            "type": "nonexistent_type_xyz",
            "payload": {},
            "metadata": {},
        }

        result = run_evaluation_service(raw_data)

        assert result["status"] == "error"
        assert "No adapter found" in result["message"]