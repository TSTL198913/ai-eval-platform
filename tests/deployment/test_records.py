"""
记录管理部署测试 - 验证评测记录CRUD功能
场景覆盖: C-001, C-002, C-003, C-004
"""

import pytest
import requests


@pytest.mark.api
class TestRecords:
    """记录管理测试"""

    def test_list_records(self, api_url, session_token):
        """场景C-001: 查询评测记录列表"""
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(f"{api_url}/api/v1/records", headers=headers, timeout=10)

        assert response.status_code == 200, f"查询记录列表失败: {response.status_code}"
        data = response.json()
        assert data["code"] == 0, f"响应code错误: {data.get('code')}"
        assert isinstance(data["data"], list), "data应是列表"

    def test_list_records_with_pagination(self, api_url, session_token):
        """场景C-001扩展: 分页查询"""
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(
            f"{api_url}/api/v1/records?limit=5&offset=0", headers=headers, timeout=10
        )

        assert response.status_code == 200, f"分页查询失败: {response.status_code}"
        data = response.json()
        assert data["code"] == 0, f"响应code错误: {data.get('code')}"

    def test_list_records_limit_validation(self, api_url, session_token):
        """场景C-001扩展: limit越界验证"""
        headers = {"Authorization": f"Bearer {session_token}"}

        response = requests.get(f"{api_url}/api/v1/records?limit=0", headers=headers, timeout=10)
        assert response.status_code == 400, f"limit=0应返回400，实际返回: {response.status_code}"

        response = requests.get(f"{api_url}/api/v1/records?limit=101", headers=headers, timeout=10)
        assert response.status_code == 400, f"limit=101应返回400，实际返回: {response.status_code}"

    def test_get_record_detail(self, api_url, session_token):
        """场景C-002: 查询单条记录"""
        headers = {"Authorization": f"Bearer {session_token}"}

        list_response = requests.get(
            f"{api_url}/api/v1/records?limit=1", headers=headers, timeout=10
        )
        assert list_response.status_code == 200
        list_data = list_response.json()

        if list_data["data"]:
            record_id = list_data["data"][0]["id"]
            response = requests.get(
                f"{api_url}/api/v1/records/{record_id}", headers=headers, timeout=10
            )
            assert response.status_code == 200, f"查询记录详情失败: {response.status_code}"
            data = response.json()
            assert data["code"] == 0, f"响应code错误: {data.get('code')}"
            assert data["data"]["id"] == record_id, f"记录ID不匹配: {data['data'].get('id')}"

    def test_get_nonexistent_record(self, api_url, session_token):
        """场景C-004: 查询不存在记录"""
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(
            f"{api_url}/api/v1/records/nonexistent_record_id_xyz", headers=headers, timeout=10
        )

        assert response.status_code == 404, (
            f"查询不存在记录应返回404，实际返回: {response.status_code}"
        )
        data = response.json()
        assert data["code"] == 404, f"响应code错误: {data.get('code')}"
