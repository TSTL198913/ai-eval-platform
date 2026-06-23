"""
Services模块专项测试
测试目标：验证EvaluationDataService和evaluator_svc的核心功能
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.exceptions import DomainLogicError
from src.services.data_svc import EvaluationDataService, get_data_service
from src.services.evaluator_svc import (
    _normalize_raw_data,
    service_exception_handler,
)


class TestEvaluationDataService:
    """EvaluationDataService数据服务测试"""

    @pytest.fixture
    def mock_repository(self):
        repo = MagicMock()
        repo.count.return_value = 100
        repo.get_recent.return_value = [{"id": 1}, {"id": 2}]
        repo.search.return_value = [{"id": 1, "case_id": "CASE_001"}]
        repo.get_all_for_export.return_value = []
        repo.get_by_id.return_value = {"id": 1}
        repo.update.return_value = True
        repo.delete.return_value = True
        repo.batch_delete.return_value = 2
        repo.batch_update.return_value = 3
        repo.get_all.return_value = [{"id": 1}]
        repo.create.return_value = {"id": 1}
        repo.save_config.return_value = {"status": "ok"}
        return repo

    def test_count(self, mock_repository):
        """count应返回记录数"""
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.count()

            assert result == 100
            mock_repository.count.assert_called_once()

    def test_get_recent(self, mock_repository):
        """get_recent应返回最近记录"""
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.get_recent(limit=50)

            assert len(result) == 2
            mock_repository.get_recent.assert_called_with(limit=50)

    def test_search(self, mock_repository):
        """search应调用repository的search方法"""
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.search(evaluator="test", status="PASSED")

            assert len(result) == 1
            mock_repository.search.assert_called()

    def test_get_all_for_export(self, mock_repository):
        """get_all_for_export应返回所有记录"""
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.get_all_for_export()

            assert result == []
            mock_repository.get_all_for_export.assert_called_once()

    def test_get_by_id(self, mock_repository):
        """get_by_id应返回指定ID的记录"""
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.get_by_id(1)

            assert result == {"id": 1}
            mock_repository.get_by_id.assert_called_with(1)

    def test_update(self, mock_repository):
        """update应调用repository的update方法"""
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.update(1, {"status": "PASSED"})

            assert result is True
            mock_repository.update.assert_called_with(1, {"status": "PASSED"})

    def test_delete(self, mock_repository):
        """delete应调用repository的delete方法"""
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.delete(1)

            assert result is True
            mock_repository.delete.assert_called_with(1)

    def test_batch_delete(self, mock_repository):
        """batch_delete应调用repository的batch_delete方法"""
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.batch_delete([1, 2])

            assert result == 2
            mock_repository.batch_delete.assert_called_with([1, 2])

    def test_batch_update(self, mock_repository):
        """batch_update应调用repository的batch_update方法"""
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.batch_update([1, 2, 3], {"status": "PASSED"})

            assert result == 3
            mock_repository.batch_update.assert_called_with([1, 2, 3], {"status": "PASSED"})

    def test_get_all(self, mock_repository):
        """get_all应返回所有记录"""
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.get_all(limit=10)

            assert len(result) == 1
            mock_repository.get_all.assert_called_with(limit=10)

    def test_create(self, mock_repository):
        """create应调用repository的create方法"""
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.create({"case_id": "CASE_001"})

            assert result == {"id": 1}
            mock_repository.create.assert_called_with({"case_id": "CASE_001"})

    def test_save_config(self, mock_repository):
        """save_config应调用repository的save_config方法"""
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.save_config({"key": "value"})

            assert result == {"status": "ok"}
            mock_repository.save_config.assert_called_with({"key": "value"})

    def test_get_by_case_id(self, mock_repository):
        """get_by_case_id应返回指定case_id的记录"""
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.get_by_case_id("CASE_001")

            assert result == {"id": 1, "case_id": "CASE_001"}

    def test_get_by_case_id_not_found(self, mock_repository):
        """get_by_case_id未找到应返回None"""
        mock_repository.search.return_value = []
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.get_by_case_id("CASE_NOT_FOUND")

            assert result is None

    def test_delete_by_case_id(self, mock_repository):
        """delete_by_case_id应删除指定case_id的记录"""
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.delete_by_case_id("CASE_001")

            assert result == 1

    def test_delete_by_case_id_not_found(self, mock_repository):
        """delete_by_case_id未找到应返回0"""
        mock_repository.search.return_value = []
        with patch("src.services.data_svc.EvaluationRepository", return_value=mock_repository):
            service = EvaluationDataService()
            result = service.delete_by_case_id("CASE_NOT_FOUND")

            assert result == 0

    def test_get_data_service_singleton(self):
        """get_data_service应返回单例实例"""
        global _data_service
        _data_service = None

        with patch("src.services.data_svc.EvaluationRepository"):
            service1 = get_data_service()
            service2 = get_data_service()

            assert service1 is service2


class TestEvaluatorService:
    """EvaluatorService评估服务测试"""

    def test_normalize_raw_data_with_payload(self):
        """已有payload时应返回原始数据"""
        raw_data = {"id": "1", "type": "test", "payload": {"key": "value"}}
        result = _normalize_raw_data(raw_data)

        assert result == raw_data

    def test_normalize_raw_data_without_payload(self):
        """无payload时应重新组织数据"""
        raw_data = {"id": "1", "type": "test", "actual_output": "hello", "expected_output": "world"}
        result = _normalize_raw_data(raw_data)

        assert "payload" in result
        assert result["payload"]["actual_output"] == "hello"
        assert result["payload"]["expected_output"] == "world"

    def test_normalize_raw_data_with_metadata(self):
        """包含metadata时应保留"""
        raw_data = {
            "id": "1",
            "type": "test",
            "actual_output": "hello",
            "metadata": {"key": "value"},
        }
        result = _normalize_raw_data(raw_data)

        assert result["metadata"] == {"key": "value"}

    def test_service_exception_handler_base_platform_error(self):
        """应捕获BasePlatformError"""

        @service_exception_handler
        def raise_error():
            raise DomainLogicError("test error")

        result = raise_error()

        assert result["status"] == "error"
        assert result["code"] == "E2005"

    def test_service_exception_handler_validation_error(self):
        """应捕获ValidationError"""

        class ValidationError(Exception):
            pass

        @service_exception_handler
        def raise_error():
            raise ValidationError("validation failed")

        result = raise_error()

        assert result["status"] == "error"
        assert result["code"] == "CONTRACT_ERROR"

    def test_service_exception_handler_generic_error(self):
        """应捕获通用异常"""

        @service_exception_handler
        def raise_error():
            raise ValueError("generic error")

        result = raise_error()

        assert result["status"] == "error"
        assert result["code"] == "INTERNAL_ERROR"
