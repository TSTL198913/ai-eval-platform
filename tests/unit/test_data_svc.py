from unittest.mock import patch

from src.services.data_svc import EvaluationDataService, get_data_service


class TestEvaluationDataService:
    @patch("src.services.data_svc.EvaluationRepository")
    def test_count(self, mock_repo):
        mock_repo.return_value.count.return_value = 42
        service = EvaluationDataService()
        result = service.count()
        assert result == 42

    @patch("src.services.data_svc.EvaluationRepository")
    def test_get_recent(self, mock_repo):
        mock_repo.return_value.get_recent.return_value = [{"id": 1}, {"id": 2}]
        service = EvaluationDataService()
        result = service.get_recent(limit=2)
        assert len(result) == 2

    @patch("src.services.data_svc.EvaluationRepository")
    def test_search(self, mock_repo):
        mock_repo.return_value.search.return_value = []
        service = EvaluationDataService()
        service.search(evaluator="qa", status="success")
        mock_repo.return_value.search.assert_called_once()

    @patch("src.services.data_svc.EvaluationRepository")
    def test_get_by_id(self, mock_repo):
        mock_repo.return_value.get_by_id.return_value = {"id": 1, "case_id": "test123"}
        service = EvaluationDataService()
        result = service.get_by_id(1)
        assert result["case_id"] == "test123"

    @patch("src.services.data_svc.EvaluationRepository")
    def test_update(self, mock_repo):
        mock_repo.return_value.update.return_value = True
        service = EvaluationDataService()
        result = service.update(1, {"status": "updated"})
        assert result is True

    @patch("src.services.data_svc.EvaluationRepository")
    def test_delete(self, mock_repo):
        mock_repo.return_value.delete.return_value = True
        service = EvaluationDataService()
        result = service.delete(1)
        assert result is True

    @patch("src.services.data_svc.EvaluationRepository")
    def test_get_all_for_export(self, mock_repo):
        mock_repo.return_value.get_all_for_export.return_value = []
        service = EvaluationDataService()
        result = service.get_all_for_export()
        assert result == []

    @patch("src.services.data_svc.EvaluationRepository")
    def test_get_all(self, mock_repo):
        mock_repo.return_value.get_all.return_value = [{"id": 1}]
        service = EvaluationDataService()
        result = service.get_all(limit=10)
        assert len(result) == 1

    @patch("src.services.data_svc.EvaluationRepository")
    def test_batch_delete(self, mock_repo):
        mock_repo.return_value.batch_delete.return_value = 5
        service = EvaluationDataService()
        result = service.batch_delete([1, 2, 3])
        assert result == 5

    @patch("src.services.data_svc.EvaluationRepository")
    def test_batch_update(self, mock_repo):
        mock_repo.return_value.batch_update.return_value = 3
        service = EvaluationDataService()
        result = service.batch_update([1, 2, 3], {"status": "archived"})
        assert result == 3

    @patch("src.services.data_svc.EvaluationRepository")
    def test_save_config(self, mock_repo):
        mock_repo.return_value.save_config.return_value = True
        service = EvaluationDataService()
        result = service.save_config({"key": "value"})
        assert result is True

    @patch("src.services.data_svc.EvaluationRepository")
    def test_get_by_case_id(self, mock_repo):
        mock_repo.return_value.search.return_value = [
            {"id": 1, "case_id": "test123"},
            {"id": 2, "case_id": "other"},
        ]
        service = EvaluationDataService()
        result = service.get_by_case_id("test123")
        assert result["id"] == 1

    @patch("src.services.data_svc.EvaluationRepository")
    def test_get_by_case_id_not_found(self, mock_repo):
        mock_repo.return_value.search.return_value = []
        service = EvaluationDataService()
        result = service.get_by_case_id("not_found")
        assert result is None

    @patch("src.services.data_svc.EvaluationRepository")
    def test_delete_by_case_id(self, mock_repo):
        mock_repo.return_value.search.return_value = [
            {"id": 1, "case_id": "test123"},
            {"id": 2, "case_id": "test123"},
        ]
        mock_repo.return_value.delete.return_value = True
        service = EvaluationDataService()
        result = service.delete_by_case_id("test123")
        assert result == 2


class TestGetDataService:
    def test_singleton_pattern(self):
        service1 = get_data_service()
        service2 = get_data_service()
        assert service1 is service2
