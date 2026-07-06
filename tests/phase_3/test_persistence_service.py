"""Phase 3: 持久化服务测试"""
import pytest
from unittest.mock import Mock, patch

from src.domain.services.persistence_service import PersistenceService
from src.schemas.schemas import EvaluationStatus, EvaluationResult


class TestPersistenceService:
    def test_save_evaluation_success(self):
        mock_repository = Mock()
        mock_repository.save.return_value = 123

        service = PersistenceService(repository=mock_repository)

        mock_result = Mock(spec=EvaluationResult)
        mock_result.case_id = "test-case-001"
        mock_result.status = EvaluationStatus.SUCCESS

        result = service.save_evaluation(mock_result)

        assert result["success"] is True
        assert result["db_id"] == 123
        assert result["error"] is None
        mock_repository.save.assert_called_once_with(mock_result)

    def test_save_evaluation_failure(self):
        mock_repository = Mock()
        mock_repository.save.side_effect = Exception("Database connection failed")

        service = PersistenceService(repository=mock_repository)

        mock_result = Mock(spec=EvaluationResult)
        mock_result.case_id = "test-case-001"
        mock_result.status = EvaluationStatus.SUCCESS

        result = service.save_evaluation(mock_result)

        assert result["success"] is False
        assert result["db_id"] is None
        assert "Database connection failed" in result["error"]

    def test_default_repository(self):
        service = PersistenceService()
        assert service.repository is not None