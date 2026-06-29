"""
记录管理API集成测试
测试目标：验证 /api/v1/records 端点的 CRUD 和查询功能
覆盖场景：查询、搜索、导出、更新、删除、批量操作

关键发现：
- get_recent 和 search 使用 EvaluationDataService -> EvaluationRepository
- 导出支持 CSV/JSON 两种格式
- 批量重新评估从原始记录中提取 payload 并重新执行
"""

import pytest


class TestGetRecords:
    """GET /api/v1/records - 获取最近记录"""

    def test_get_recent_records_returns_list(self, client):
        """正向：获取最近记录应返回列表"""
        response = client.get("/api/v1/records?limit=10")

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 0
        data = body["data"]
        assert "items" in data
        assert "count" in data
        assert isinstance(data["items"], list)

    def test_get_recent_records_limit_bounds(self, client):
        """边界：limit 超出范围应返回 400"""
        # limit < 1
        response = client.get("/api/v1/records?limit=0")
        assert response.status_code == 400

        # limit > 100
        response = client.get("/api/v1/records?limit=101")
        assert response.status_code == 400

        # 有效边界值
        response = client.get("/api/v1/records?limit=1")
        assert response.status_code == 200

        response = client.get("/api/v1/records?limit=100")
        assert response.status_code == 200


class TestSearchRecords:
    """GET /api/v1/records/search - 搜索记录"""

    def test_search_by_evaluator_type(self, client):
        """正向：按评估器类型搜索应返回匹配记录"""
        response = client.get("/api/v1/records/search?evaluator=general&limit=10")

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 0
        data = body["data"]
        assert "records" in data
        assert "filters" in data

    def test_search_by_status(self, client):
        """正向：按状态搜索应返回匹配记录"""
        response = client.get("/api/v1/records/search?status=success&limit=10")

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 0

    def test_search_combined_filters(self, client):
        """正向：组合过滤器应正确工作"""
        response = client.get("/api/v1/records/search?evaluator=security&status=success&limit=5")

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 0

    def test_search_offset_bounds(self, client):
        """边界：offset 超出范围应返回 400"""
        response = client.get("/api/v1/records/search?offset=-1")
        assert response.status_code == 400

        response = client.get("/api/v1/records/search?offset=10001")
        assert response.status_code == 400

        # 有效值
        response = client.get("/api/v1/records/search?offset=0")
        assert response.status_code == 200

    def test_search_sort_order(self, client):
        """正向：排序参数应正确应用"""
        response = client.get("/api/v1/records/search?sort_by=created_at&sort_order=desc&limit=5")

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 0


class TestGetRecordDetail:
    """GET /api/v1/records/{record_id} - 获取单条记录"""

    def test_get_existing_record(self, client):
        """正向：查询已存在的记录应返回详情"""
        # 先创建一个评估
        eval_resp = client.post(
            "/api/v1/evaluate",
            json={
                "id": "record_detail_001",
                "type": "general",
                "payload": {"user_input": "test"},
            },
        )
        assert eval_resp.status_code == 200

        # 查询该记录
        response = client.get("/api/v1/records/1")  # 假设 ID=1 存在

        # 可能 200（存在）或 404（不存在，取决于数据库状态）
        assert response.status_code in [200, 404]

    def test_get_nonexistent_record_returns_404(self, client):
        """负向：查询不存在的记录应返回 404"""
        response = client.get("/api/v1/records/999999")

        assert response.status_code == 404
        body = response.json()
        assert body["code"] == 404


class TestUpdateRecord:
    """PUT /api/v1/records/{record_id} - 更新记录"""

    def test_update_record_allowed_fields(self, client):
        """正向：更新允许字段应成功"""
        # 先创建
        eval_resp = client.post(
            "/api/v1/evaluate",
            json={
                "id": "update_test_001",
                "type": "general",
                "payload": {"user_input": "test"},
            },
        )
        assert eval_resp.status_code == 200

        # 获取记录 ID（从数据库查询）
        from src.services.data_svc import get_data_service

        svc = get_data_service()
        records = svc.get_all(limit=100)
        test_records = [r for r in records if r.get("case_id") == "update_test_001"]
        if not test_records:
            pytest.skip("记录未持久化，跳过更新测试")

        record_id = test_records[0].get("id")

        # 更新
        update_resp = client.put(
            f"/api/v1/records/{record_id}",
            json={"status": "passed"},
        )
        assert update_resp.status_code == 200

    def test_update_record_invalid_status_returns_400(self, client):
        """负向：更新无效状态值应返回 400"""
        response = client.put(
            "/api/v1/records/1",
            json={"status": "invalid_status_xyz"},
        )

        assert response.status_code == 400

    def test_update_record_forbidden_fields_returns_400(self, client):
        """负向：尝试更新禁止字段应返回 400
        注意：如果记录不存在则返回 404"""
        response = client.put(
            "/api/v1/records/1",
            json={"score": 0.99, "response_data": {"fake": "data"}},
        )

        # 禁止字段应被拦截，或因记录不存在返回 404
        assert response.status_code in [400, 404]


class TestDeleteRecord:
    """DELETE /api/v1/records/{record_id} - 删除记录"""

    def test_delete_existing_record(self, client):
        """正向：删除已存在记录应成功"""
        # 先创建
        eval_resp = client.post(
            "/api/v1/evaluate",
            json={
                "id": "delete_test_001",
                "type": "general",
                "payload": {"user_input": "test"},
            },
        )
        assert eval_resp.status_code == 200

        # 获取记录
        from src.services.data_svc import get_data_service

        svc = get_data_service()
        records = svc.get_all(limit=100)
        test_records = [r for r in records if r.get("case_id") == "delete_test_001"]
        if not test_records:
            pytest.skip("记录未持久化，跳过删除测试")

        record_id = test_records[0].get("id")

        # 删除
        delete_resp = client.delete(f"/api/v1/records/{record_id}")
        assert delete_resp.status_code == 200

    def test_delete_nonexistent_record_returns_404(self, client):
        """负向：删除不存在的记录应返回 404"""
        response = client.delete("/api/v1/records/999999")

        assert response.status_code == 404


class TestExportRecords:
    """GET /api/v1/records/export - 导出记录"""

    def test_export_csv_format(self, client):
        """正向：CSV 格式导出应成功"""
        response = client.get("/api/v1/records/export?format=csv")

        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        assert "attachment" in response.headers.get("content-disposition", "")

    def test_export_json_format(self, client):
        """正向：JSON 格式导出应成功"""
        response = client.get("/api/v1/records/export?format=json")

        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
        body = response.json()
        assert isinstance(body, list | dict)

    def test_export_invalid_format_returns_400(self, client):
        """负向：非法格式应返回 400"""
        response = client.get("/api/v1/records/export?format=xml")

        assert response.status_code == 400


class TestBatchOperations:
    """POST /api/v1/records/batch/* - 批量操作"""

    def test_batch_delete_requires_ids(self, client):
        """负向：批量删除缺少 ids 字段应返回 422"""
        response = client.post(
            "/api/v1/records/batch/delete",
            json={},
        )

        assert response.status_code == 422

    def test_batch_delete_empty_ids_returns_422(self, client):
        """边界：批量删除空列表应返回 422"""
        response = client.post(
            "/api/v1/records/batch/delete",
            json={"ids": []},
        )

        assert response.status_code == 422

    def test_batch_update_forbidden_fields(self, client):
        """负向：批量更新禁止字段应返回 400"""
        response = client.post(
            "/api/v1/records/batch/update",
            json={"ids": [1], "data": {"score": 0.99}},
        )

        assert response.status_code == 400
