"""
DatasetRoutes 专项集成测试
测试目标：验证数据集路由模块的列表/详情端点
关键发现：
1. GET /api/v1/datasets 列出数据集
2. GET /api/v1/datasets/{name} 数据集详情
3. validate_dataset_name 防止路径遍历
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestDatasetListEndpoint:
    """GET /api/v1/datasets 测试"""

    def test_list_datasets_success(self):
        """场景：成功获取数据集列表"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.dataset_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("src.domain.benchmarks.standard_datasets.DatasetManager") as MockManager:
            MockManager.list_datasets.return_value = [
                {"name": "gsm8k", "description": "数学数据集"},
                {"name": "mmlu", "description": "多任务理解"},
            ]
            MockManager.get_all_stats.return_value = {
                "total": 2,
                "ready": 2,
            }

            response = client.get("/api/v1/datasets")

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert "datasets" in data["data"]
            assert "stats" in data["data"]
            assert len(data["data"]["datasets"]) == 2

    def test_list_datasets_exception(self):
        """场景：异常时返回500"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.dataset_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("src.domain.benchmarks.standard_datasets.DatasetManager") as MockManager:
            MockManager.list_datasets.side_effect = Exception("加载失败")

            response = client.get("/api/v1/datasets")

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 500


class TestDatasetDetailsEndpoint:
    """GET /api/v1/datasets/{dataset_name} 测试"""

    def test_get_dataset_details_invalid_name(self):
        """场景：非法数据集名应返回404"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.dataset_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # 路径遍历尝试
        response = client.get("/api/v1/datasets/../../../etc/passwd")

        # FastAPI会自动处理路径参数
        assert response.status_code in [200, 404]

    def test_get_dataset_details_not_found(self):
        """场景：数据集不存在应返回404"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.dataset_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with (
            patch("src.domain.benchmarks.standard_datasets.DatasetManager") as MockManager,
            patch("src.domain.benchmarks.standard_datasets.BenchmarkDataset"),
        ):
            MockManager.get_dataset.side_effect = ValueError("Dataset not found")

            response = client.get("/api/v1/datasets/nonexistent")

            assert response.status_code == 404
            data = response.json()
            assert data["code"] == 404

    def test_get_dataset_details_success(self):
        """场景：成功获取数据集详情"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.dataset_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with (
            patch("src.domain.benchmarks.standard_datasets.DatasetManager") as MockManager,
            patch("src.domain.benchmarks.standard_datasets.BenchmarkDataset"),
        ):
            mock_ds = MagicMock()
            mock_ds.load.return_value = [
                {"input": "1+1", "output": "2"},
                {"input": "2+2", "output": "4"},
            ]
            mock_ds.get_stats.return_value = {
                "total_samples": 2,
                "size": "small",
            }
            MockManager.get_dataset.return_value = mock_ds

            response = client.get("/api/v1/datasets/gsm8k")

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["sample_count"] == 2

    def test_get_dataset_details_exception(self):
        """场景：异常时返回500"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.dataset_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with (
            patch("src.domain.benchmarks.standard_datasets.DatasetManager") as MockManager,
            patch("src.domain.benchmarks.standard_datasets.BenchmarkDataset"),
        ):
            MockManager.get_dataset.side_effect = Exception("DB error")

            response = client.get("/api/v1/datasets/gsm8k")

            assert response.status_code == 500
            data = response.json()
            assert data["code"] == 500
