"""
导出服务性能测试

验证 EvaluationExportService 的大数据量处理能力，包括：
- 大数据量导出性能
- 内存使用情况
- 导出时间统计

注意：本测试会生成较大的测试数据，请确保系统有足够的内存
"""

import os
import time
import pytest


@pytest.mark.performance
class TestExportPerformance:
    """导出服务性能测试"""

    def test_large_dataset_csv_export(self):
        """测试大数据量 CSV 导出性能"""
        from src.domain.services.evaluation_export_service import EvaluationExportService
        from unittest.mock import MagicMock, patch

        with patch("src.domain.services.evaluation_export_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            
            large_data = [
                {
                    "id": i,
                    "case_id": f"case-{i}",
                    "model_name": "gpt-4",
                    "adapter_name": "general",
                    "status": "SUCCESS",
                    "latency_ms": 1000.0 + i,
                    "score": 0.7 + (i % 30) * 0.01,
                    "created_at": f"2024-01-01T00:00:{i:02d}",
                }
                for i in range(10000)
            ]
            
            mock_repo_instance.search.return_value = large_data
            mock_repo.return_value = mock_repo_instance

            service = EvaluationExportService()

            start_time = time.time()
            filepath = service.export("csv")
            elapsed_time = time.time() - start_time

            assert os.path.exists(filepath)

            file_size = os.path.getsize(filepath)
            os.remove(filepath)

            print(f"\nCSV 导出性能测试:")
            print(f"  数据量: 10000 条")
            print(f"  文件大小: {file_size / 1024 / 1024:.2f} MB")
            print(f"  耗时: {elapsed_time:.2f} 秒")
            print(f"  吞吐量: {len(large_data) / elapsed_time:.2f} 条/秒")

            assert elapsed_time < 30
            assert file_size > 0

    def test_large_dataset_json_export(self):
        """测试大数据量 JSON 导出性能"""
        from src.domain.services.evaluation_export_service import EvaluationExportService
        from unittest.mock import MagicMock, patch

        with patch("src.domain.services.evaluation_export_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            
            large_data = [
                {
                    "id": i,
                    "case_id": f"case-{i}",
                    "model_name": "gpt-4",
                    "adapter_name": "general",
                    "status": "SUCCESS",
                    "latency_ms": 1000.0 + i,
                    "score": 0.7 + (i % 30) * 0.01,
                    "created_at": f"2024-01-01T00:00:{i:02d}",
                }
                for i in range(5000)
            ]
            
            mock_repo_instance.search.return_value = large_data
            mock_repo.return_value = mock_repo_instance

            service = EvaluationExportService()

            start_time = time.time()
            filepath = service.export("json")
            elapsed_time = time.time() - start_time

            assert os.path.exists(filepath)

            file_size = os.path.getsize(filepath)
            os.remove(filepath)

            print(f"\nJSON 导出性能测试:")
            print(f"  数据量: 5000 条")
            print(f"  文件大小: {file_size / 1024 / 1024:.2f} MB")
            print(f"  耗时: {elapsed_time:.2f} 秒")
            print(f"  吞吐量: {len(large_data) / elapsed_time:.2f} 条/秒")

            assert elapsed_time < 30
            assert file_size > 0

    def test_medium_dataset_export_time(self):
        """测试中等数据量导出时间"""
        from src.domain.services.evaluation_export_service import EvaluationExportService
        from unittest.mock import MagicMock, patch

        with patch("src.domain.services.evaluation_export_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            
            medium_data = [
                {
                    "id": i,
                    "case_id": f"case-{i}",
                    "model_name": f"model-{i % 5}",
                    "adapter_name": f"evaluator-{i % 10}",
                    "status": "SUCCESS" if i % 2 == 0 else "ERROR",
                    "latency_ms": 500.0 + (i % 100) * 10,
                    "score": 0.5 + (i % 50) * 0.01,
                    "created_at": f"2024-01-{i % 31 + 1:02d}T{i % 24:02d}:00:00",
                }
                for i in range(1000)
            ]
            
            mock_repo_instance.search.return_value = medium_data
            mock_repo.return_value = mock_repo_instance

            service = EvaluationExportService()

            for format in ["csv", "json"]:
                start_time = time.time()
                filepath = service.export(format)
                elapsed_time = time.time() - start_time

                assert os.path.exists(filepath)
                os.remove(filepath)

                print(f"\n{format.upper()} 导出测试 (1000条):")
                print(f"  耗时: {elapsed_time:.2f} 秒")

                assert elapsed_time < 5

    def test_empty_dataset_export(self):
        """测试空数据集导出"""
        from src.domain.services.evaluation_export_service import EvaluationExportService
        from unittest.mock import MagicMock, patch

        with patch("src.domain.services.evaluation_export_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.search.return_value = []
            mock_repo.return_value = mock_repo_instance

            service = EvaluationExportService()

            for format in ["csv", "json"]:
                start_time = time.time()
                filepath = service.export(format)
                elapsed_time = time.time() - start_time

                assert filepath.endswith(f".{format}")
                assert elapsed_time < 1

    def test_report_generation_performance(self):
        """测试报表生成性能"""
        from src.domain.services.evaluation_report_service import EvaluationReportService
        from unittest.mock import MagicMock, patch

        with patch("src.domain.services.evaluation_report_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            
            report_data = [
                {
                    "id": i,
                    "case_id": f"case-{i}",
                    "model_name": f"model-{i % 10}",
                    "adapter_name": f"evaluator-{i % 20}",
                    "status": "SUCCESS",
                    "latency_ms": 1000.0 + i,
                    "score": 0.7 + (i % 30) * 0.01,
                    "created_at": f"2024-01-01T00:00:{i:02d}",
                }
                for i in range(5000)
            ]
            
            mock_repo_instance.search.return_value = report_data
            mock_repo.return_value = mock_repo_instance

            service = EvaluationReportService()

            start_time = time.time()
            report = service.generate_report("summary")
            elapsed_time = time.time() - start_time

            print(f"\n报表生成性能测试:")
            print(f"  数据量: 5000 条")
            print(f"  耗时: {elapsed_time:.2f} 秒")
            print(f"  报表类型: {report['report_type']}")
            print(f"  总评估数: {report['summary']['total_evaluations']}")

            assert report["summary"]["total_evaluations"] == 5000
            assert elapsed_time < 10