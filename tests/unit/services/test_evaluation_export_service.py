"""测试 EvaluationExportService 评估结果导出服务"""

import pytest
import os
from unittest.mock import MagicMock, patch


class TestEvaluationExportService:
    """测试评估结果导出服务"""

    def test_get_export_formats(self):
        """获取支持的导出格式"""
        from src.domain.services.evaluation_export_service import evaluation_export_service

        formats = evaluation_export_service.get_export_formats()
        assert "csv" in formats
        assert "json" in formats
        assert "excel" in formats

    def test_get_available_fields(self):
        """获取可用的导出字段"""
        from src.domain.services.evaluation_export_service import evaluation_export_service

        fields = evaluation_export_service.get_available_fields()
        assert "id" in fields
        assert "case_id" in fields
        assert "score" in fields
        assert "created_at" in fields

    @patch("src.domain.services.evaluation_export_service.EvaluationRepository")
    def test_export_csv_with_empty_data(self, mock_repo):
        """导出空数据的 CSV"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = []
        mock_repo.return_value = mock_repo_instance

        from src.domain.services.evaluation_export_service import EvaluationExportService

        service = EvaluationExportService()
        filepath = service.export("csv")
        assert filepath.endswith(".csv")

    @patch("src.domain.services.evaluation_export_service.EvaluationRepository")
    def test_export_json_with_empty_data(self, mock_repo):
        """导出空数据的 JSON"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = []
        mock_repo.return_value = mock_repo_instance

        from src.domain.services.evaluation_export_service import EvaluationExportService

        service = EvaluationExportService()
        filepath = service.export("json")
        assert filepath.endswith(".json")

    @patch("src.domain.services.evaluation_export_service.EvaluationRepository")
    def test_export_csv_with_data(self, mock_repo):
        """导出有数据的 CSV"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = [
            {
                "id": 1,
                "case_id": "test-1",
                "model_name": "gpt-4",
                "adapter_name": "general",
                "status": "SUCCESS",
                "latency_ms": 1234.56,
                "score": 0.85,
                "created_at": "2024-01-01T00:00:00",
            }
        ]
        mock_repo.return_value = mock_repo_instance

        from src.domain.services.evaluation_export_service import EvaluationExportService

        service = EvaluationExportService()
        filepath = service.export("csv")
        assert os.path.exists(filepath)
        os.remove(filepath)

    @patch("src.domain.services.evaluation_export_service.EvaluationRepository")
    def test_export_json_with_data(self, mock_repo):
        """导出有数据的 JSON"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = [
            {
                "id": 1,
                "case_id": "test-1",
                "model_name": "gpt-4",
                "adapter_name": "general",
                "status": "SUCCESS",
                "latency_ms": 1234.56,
                "score": 0.85,
                "created_at": "2024-01-01T00:00:00",
            }
        ]
        mock_repo.return_value = mock_repo_instance

        from src.domain.services.evaluation_export_service import EvaluationExportService

        service = EvaluationExportService()
        filepath = service.export("json")
        assert os.path.exists(filepath)
        os.remove(filepath)

    @patch("src.domain.services.evaluation_export_service.EvaluationRepository")
    def test_export_with_filters(self, mock_repo):
        """使用过滤条件导出"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = []
        mock_repo.return_value = mock_repo_instance

        from src.domain.services.evaluation_export_service import EvaluationExportService

        service = EvaluationExportService()
        service.export("json", filters={"evaluator": "general", "status": "SUCCESS"})

        mock_repo_instance.search.assert_called_once()

    @patch("src.domain.services.evaluation_export_service.EvaluationRepository")
    def test_export_with_fields(self, mock_repo):
        """使用自定义字段导出"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = [
            {"id": 1, "case_id": "test-1", "score": 0.85}
        ]
        mock_repo.return_value = mock_repo_instance

        from src.domain.services.evaluation_export_service import EvaluationExportService

        service = EvaluationExportService()
        filepath = service.export("json", fields=["id", "score"])
        assert os.path.exists(filepath)

        import json

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert "id" in data[0]
            assert "score" in data[0]
            assert "case_id" not in data[0]

        os.remove(filepath)

    @patch("src.domain.services.evaluation_export_service.EvaluationRepository")
    def test_export_with_custom_filename(self, mock_repo):
        """使用自定义文件名导出"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = []
        mock_repo.return_value = mock_repo_instance

        from src.domain.services.evaluation_export_service import evaluation_export_service

        filepath = evaluation_export_service.export("json", filename="custom_export.json")
        assert "custom_export.json" in filepath

    def test_export_format_enum(self):
        """测试导出格式枚举"""
        from src.domain.services.evaluation_export_service import ExportFormat

        assert ExportFormat.CSV.value == "csv"
        assert ExportFormat.JSON.value == "json"
        assert ExportFormat.EXCEL.value == "excel"

    @patch("src.domain.services.evaluation_export_service.EvaluationRepository")
    def test_export_excel_fallback_to_csv(self, mock_repo):
        """Excel 导出回退到 CSV"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = [{"id": 1, "case_id": "test-1"}]
        mock_repo.return_value = mock_repo_instance

        import sys
        original_openpyxl = sys.modules.get('openpyxl')
        sys.modules['openpyxl'] = None

        try:
            from src.domain.services.evaluation_export_service import EvaluationExportService

            service = EvaluationExportService()
            filepath = service.export("excel")
            assert filepath.endswith(".csv")
        finally:
            if original_openpyxl is not None:
                sys.modules['openpyxl'] = original_openpyxl
            elif 'openpyxl' in sys.modules:
                del sys.modules['openpyxl']