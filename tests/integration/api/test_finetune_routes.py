"""
FinetuneRoutes 专项集成测试
测试目标：验证微调路由模块的导出/模型管理/评估等端点
关键发现：
1. /api/v1/finetune/export/datasets 列出可导出数据集
2. /api/v1/finetune/export 导出训练数据
3. /api/v1/finetune/export/db 从数据库导出
4. /api/v1/finetune/quality-report 质量报告
5. /api/v1/finetune/models 模型管理
6. /api/v1/finetune/evaluate 评估端点
7. /api/v1/finetune/guide 操作指南
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestFinetuneExportDatasetsEndpoint:
    """GET /api/v1/finetune/export/datasets 测试"""

    def test_list_exportable_datasets(self):
        """场景：列出可导出数据集"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("src.domain.golden_dataset.golden_dataset_manager") as mock_manager:
            # Mock样本数据
            sample1 = MagicMock()
            sample1.human_corrected = True
            sample1.scores = {"correctness": 80, "completeness": 75}

            sample2 = MagicMock()
            sample2.human_corrected = False
            sample2.scores = {"correctness": 60}

            dataset = MagicMock()
            dataset.id = "ds_001"
            dataset.name = "测试数据集"
            dataset.description = "测试描述"
            dataset.samples = [sample1, sample2]

            mock_manager.list_datasets.return_value = [dataset]

            response = client.get("/api/v1/finetune/export/datasets")

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert "datasets" in data["data"]
            assert len(data["data"]["datasets"]) == 1

    def test_list_datasets_exception_handling(self):
        """场景：异常时返回500"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("src.domain.golden_dataset.golden_dataset_manager") as mock_manager:
            mock_manager.list_datasets.side_effect = Exception("数据库错误")

            response = client.get("/api/v1/finetune/export/datasets")

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 500


class TestFinetuneExportEndpoint:
    """POST /api/v1/finetune/export 测试"""

    def test_export_training_data_missing_dataset_id(self):
        """场景：缺少dataset_id应返回400"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post("/api/v1/finetune/export", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 400
        assert "dataset_id" in data["message"]

    def test_export_training_data_success(self):
        """场景：成功导出训练数据"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("src.domain.fine_tune_exporter.fine_tune_exporter") as mock_exporter:
            mock_exporter.export_from_golden_dataset.return_value = "/data/test.jsonl"
            mock_exporter.get_stats.return_value = {"total_samples": 100}

            response = client.post(
                "/api/v1/finetune/export",
                json={"dataset_id": "ds_001", "format": "openai"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert "file_path" in data["data"]

    def test_export_invalid_format_returns_400(self):
        """场景：无效格式应返回400"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("src.domain.fine_tune_exporter.fine_tune_exporter") as mock_exporter:
            mock_exporter.export_from_golden_dataset.side_effect = ValueError("invalid format")

            response = client.post(
                "/api/v1/finetune/export",
                json={"dataset_id": "ds_001", "format": "invalid"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 400


class TestFinetuneExportDBEndpoint:
    """POST /api/v1/finetune/export/db 测试"""

    def test_export_from_db_success(self):
        """场景：从数据库导出成功"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("src.domain.fine_tune_exporter.fine_tune_exporter") as mock_exporter:
            mock_exporter.export_from_db.return_value = "/data/db_export.jsonl"
            mock_exporter.get_stats.return_value = {"total_samples": 50}

            response = client.post("/api/v1/finetune/export/db", json={})

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert "file_path" in data["data"]

    def test_export_from_db_exception(self):
        """场景：异常时返回500"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("src.domain.fine_tune_exporter.fine_tune_exporter") as mock_exporter:
            mock_exporter.export_from_db.side_effect = Exception("DB error")

            response = client.post("/api/v1/finetune/export/db", json={})

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 500


class TestFinetuneQualityReportEndpoint:
    """GET /api/v1/finetune/quality-report 测试"""

    def test_quality_report_success(self):
        """场景：成功返回质量报告"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with (
            patch("src.domain.fine_tune_exporter.fine_tune_exporter") as mock_exporter,
            patch("src.domain.golden_dataset.golden_dataset_manager") as mock_manager,
        ):
            mock_exporter.generate_quality_report.return_value = {
                "total_samples": 100,
                "avg_score": 75.5,
            }

            sample = MagicMock()
            sample.id = "s_001"
            sample.scores = {"correctness": 80}
            dataset = MagicMock()
            dataset.id = "ds_001"
            dataset.samples = [sample]
            mock_manager.list_datasets.return_value = [dataset]

            response = client.get("/api/v1/finetune/quality-report")

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0

    def test_quality_report_with_specific_dataset_not_found(self):
        """场景：指定数据集不存在应返回404"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("src.domain.golden_dataset.golden_dataset_manager") as mock_manager:
            mock_manager.get_dataset.return_value = None

            response = client.get("/api/v1/finetune/quality-report?dataset_id=nonexistent")

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 404


class TestFinetuneModelsEndpoints:
    """/api/v1/finetune/models 测试"""

    def test_list_fine_tuned_models(self):
        """场景：列出微调模型"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("src.domain.fine_tuned_evaluator.model_manager") as mock_manager:
            mock_manager.list_models.return_value = [
                {"name": "model_a", "path": "/path/a"},
                {"name": "model_b", "path": "/path/b"},
            ]
            mock_manager._default_model = "model_a"

            response = client.get("/api/v1/finetune/models")

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert len(data["data"]["models"]) == 2

    def test_register_model_missing_fields(self):
        """场景：缺少name或model_path应返回400"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post("/api/v1/finetune/models", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 400

    def test_register_model_success(self):
        """场景：成功注册模型"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("src.domain.fine_tuned_evaluator.model_manager") as mock_manager:
            mock_manager.register_model.return_value = True

            response = client.post(
                "/api/v1/finetune/models",
                json={"name": "new_model", "model_path": "/path/to/model"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0

    def test_register_model_path_not_exists(self):
        """场景：模型路径不存在应返回400"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("src.domain.fine_tuned_evaluator.model_manager") as mock_manager:
            mock_manager.register_model.return_value = False

            response = client.post(
                "/api/v1/finetune/models",
                json={"name": "m", "model_path": "/invalid/path"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 400


class TestFinetuneEvaluateEndpoint:
    """POST /api/v1/finetune/evaluate 测试"""

    def test_evaluate_missing_fields(self):
        """场景：缺少user_input或actual_output应返回400"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post("/api/v1/finetune/evaluate", json={"model_name": "m"})

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 400

    def test_evaluate_model_not_found(self):
        """场景：模型未找到应返回404"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("src.domain.fine_tuned_evaluator.model_manager") as mock_manager:
            mock_manager.get_evaluator.return_value = None

            response = client.post(
                "/api/v1/finetune/evaluate",
                json={
                    "model_name": "nonexistent",
                    "user_input": "测试",
                    "actual_output": "输出",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 404

    def test_evaluate_success(self):
        """场景：评估成功"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("src.domain.fine_tuned_evaluator.model_manager") as mock_manager:
            mock_evaluator = MagicMock()
            mock_result = MagicMock()
            mock_result.data = {"score": 0.85}
            mock_evaluator.evaluate.return_value = mock_result
            mock_evaluator.model_info.status.value = "ready"
            mock_manager.get_evaluator.return_value = mock_evaluator

            response = client.post(
                "/api/v1/finetune/evaluate",
                json={
                    "model_name": "test_model",
                    "user_input": "测试问题",
                    "actual_output": "测试回答",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert "result" in data["data"]


class TestFinetuneGuideEndpoint:
    """GET /api/v1/finetune/guide 测试"""

    def test_get_guide(self):
        """场景：获取操作指南"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.finetune_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/v1/finetune/guide")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "steps" in data["data"]
        assert "recommended_models" in data["data"]
        assert "expected_improvement" in data["data"]
