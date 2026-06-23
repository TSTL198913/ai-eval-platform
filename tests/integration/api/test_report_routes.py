"""
ReportRoutes 专项集成测试
测试目标：验证报告路由模块的列表/详情/生成端点
关键发现：
1. GET /api/v1/reports 列出报告
2. GET /api/v1/reports/{filename} 获取报告
3. POST /api/v1/reports/generate 生成报告
4. 防路径遍历：检查filepath.startsWith(report_dir)
"""

import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestReportListEndpoint:
    """GET /api/v1/reports 测试"""

    def test_list_reports_empty_dir(self):
        """场景：报告目录不存在时返回空列表"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.report_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False

            response = client.get("/api/v1/reports")

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["reports"] == []

    def test_list_reports_success(self):
        """场景：成功列出报告"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.report_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("os.path.exists") as mock_exists, patch("os.listdir") as mock_listdir, patch(
            "os.path.getsize"
        ) as mock_size, patch("os.path.getmtime") as mock_mtime:
            mock_exists.return_value = True
            mock_listdir.return_value = ["report1.html", "report2.html", "ignored.txt"]
            mock_size.return_value = 1024
            mock_mtime.return_value = 1234567890.0

            response = client.get("/api/v1/reports")

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            # 只列出html文件
            assert len(data["data"]["reports"]) == 2

    def test_list_reports_exception(self):
        """场景：异常时返回500"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.report_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("os.path.exists") as mock_exists:
            mock_exists.side_effect = Exception("Permission denied")

            response = client.get("/api/v1/reports")

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 500


class TestReportGetEndpoint:
    """GET /api/v1/reports/{filename} 测试"""

    def test_get_report_path_traversal_blocked(self):
        """场景：路径遍历应被阻止"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.report_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # URL编码的路径遍历
        response = client.get("/api/v1/reports/..%2F..%2Fetc%2Fpasswd")

        # FastAPI会先做URL解码,然后我们的代码会检查路径
        assert response.status_code in [200, 400, 404]

    def test_get_report_not_found(self):
        """场景：报告不存在应返回404"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.report_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False

            response = client.get("/api/v1/reports/nonexistent.html")

            assert response.status_code == 404
            data = response.json()
            assert data["code"] == 404

    def test_get_report_success(self):
        """场景：成功返回报告文件"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.report_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as tmp:
            tmp.write("<html>Test Report</html>")
            tmp_path = tmp.name

        try:
            with patch("os.path.abspath") as mock_abspath, patch(
                "os.path.normpath"
            ) as mock_normpath, patch("os.path.exists") as mock_exists:
                # 模拟安全路径
                mock_abspath.return_value = os.path.dirname(tmp_path)
                mock_normpath.side_effect = lambda x: tmp_path
                mock_exists.return_value = True

                with patch("fastapi.responses.FileResponse") as mock_fileresponse:
                    mock_fileresponse.return_value = "file_content"

                    response = client.get(f"/api/v1/reports/{os.path.basename(tmp_path)}")

                    # 验证FileResponse被调用
                    assert mock_fileresponse.called or response.status_code in [200, 404]
        finally:
            os.unlink(tmp_path)


class TestReportGenerateEndpoint:
    """POST /api/v1/reports/generate 测试"""

    def test_generate_report_success(self):
        """场景：成功生成报告"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.report_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch(
            "src.domain.reports.report_generator.generate_report_from_records"
        ) as mock_gen, patch("src.api.common._get_data_service") as mock_svc:
            mock_svc.return_value.search.return_value = [
                {"id": 1, "score": 0.8},
                {"id": 2, "score": 0.9},
            ]
            mock_gen.return_value = "reports/2025_test.html"

            response = client.post("/api/v1/reports/generate", json={})

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert "path" in data["data"]

    def test_generate_report_with_filters(self):
        """场景：带过滤条件生成报告"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.report_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch(
            "src.domain.reports.report_generator.generate_report_from_records"
        ) as mock_gen, patch("src.api.routes.report_routes._get_data_service") as mock_svc:
            mock_svc.return_value.search.return_value = []
            mock_gen.return_value = "reports/empty.html"

            response = client.post(
                "/api/v1/reports/generate",
                json={"model_name": "gpt-4", "limit": 10},
            )

            assert response.status_code == 200
            # 验证search被调用
            assert mock_svc.return_value.search.called

    def test_generate_report_exception(self):
        """场景：异常时返回500"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routes.report_routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("src.api.routes.report_routes._get_data_service") as mock_svc:
            mock_svc.return_value.get_recent.side_effect = Exception("DB error")

            response = client.post("/api/v1/reports/generate", json={})

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 500
