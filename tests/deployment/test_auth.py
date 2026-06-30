"""
认证授权部署测试 - 验证登录功能
场景覆盖: A-001, A-002, A-003, A-004, A-005, A-006, A-008
"""

import pytest
import requests


@pytest.mark.api
class TestAuthentication:
    """认证授权测试"""

    def test_admin_login_success(self, api_url, auth_credentials):
        """场景A-001: 管理员登录"""
        response = requests.post(
            f"{api_url}/api/v1/auth/login",
            json=auth_credentials["admin"],
            timeout=10,
        )

        assert response.status_code == 200, f"管理员登录失败: {response.status_code}"
        data = response.json()
        assert data["code"] == 0, f"响应code错误: {data.get('code')}"
        assert "access_token" in data["data"], "缺少access_token"
        assert "refresh_token" in data["data"], "缺少refresh_token"
        assert data["data"]["token_type"] == "bearer", (
            f"token_type错误: {data['data'].get('token_type')}"
        )
        assert data["data"]["expires_in"] > 0, f"expires_in无效: {data['data'].get('expires_in')}"

    def test_user_login_success(self, api_url, auth_credentials):
        """场景A-002: 普通用户登录"""
        response = requests.post(
            f"{api_url}/api/v1/auth/login",
            json=auth_credentials["user"],
            timeout=10,
        )

        assert response.status_code == 200, f"普通用户登录失败: {response.status_code}"
        data = response.json()
        assert data["code"] == 0, f"响应code错误: {data.get('code')}"
        assert "access_token" in data["data"], "缺少access_token"

    def test_login_wrong_password(self, api_url):
        """场景A-003: 错误密码登录"""
        response = requests.post(
            f"{api_url}/api/v1/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
            timeout=10,
        )

        assert response.status_code == 401, f"错误密码应返回401，实际返回: {response.status_code}"
        data = response.json()
        assert data["code"] == 401, f"响应code错误: {data.get('code')}"

    def test_login_nonexistent_user(self, api_url):
        """场景A-004: 不存在用户登录"""
        response = requests.post(
            f"{api_url}/api/v1/auth/login",
            json={"username": "nonexistent_user_xyz", "password": "anypassword"},
            timeout=10,
        )

        assert response.status_code == 401, f"不存在用户应返回401，实际返回: {response.status_code}"
        data = response.json()
        assert data["code"] == 401, f"响应code错误: {data.get('code')}"

    def test_login_empty_username_password(self, api_url):
        """场景A-005: 空用户名/密码"""
        response = requests.post(
            f"{api_url}/api/v1/auth/login",
            json={"username": "", "password": ""},
            timeout=10,
        )

        assert response.status_code == 422, f"空参数应返回422，实际返回: {response.status_code}"

        response = requests.post(
            f"{api_url}/api/v1/auth/login",
            json={"username": "admin"},
            timeout=10,
        )
        assert response.status_code == 422, (
            f"缺少password应返回422，实际返回: {response.status_code}"
        )

        response = requests.post(
            f"{api_url}/api/v1/auth/login",
            json={"password": "admin123"},
            timeout=10,
        )
        assert response.status_code == 422, (
            f"缺少username应返回422，实际返回: {response.status_code}"
        )

    def test_get_me_requires_login(self, api_url):
        """场景A-006: 访问/me需登录"""
        response = requests.get(f"{api_url}/api/v1/auth/me", timeout=10)

        assert response.status_code == 401, (
            f"未登录访问/me应返回401，实际返回: {response.status_code}"
        )

    def test_get_me_with_token(self, api_url, session_token):
        """场景A-006扩展: 使用token访问/me"""
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(f"{api_url}/api/v1/auth/me", headers=headers, timeout=10)

        assert response.status_code == 200, f"使用token访问/me失败: {response.status_code}"
        data = response.json()
        assert data["code"] == 0, f"响应code错误: {data.get('code')}"
        assert data["data"]["username"] == "admin", f"用户名错误: {data['data'].get('username')}"

    def test_refresh_token(self, api_url, auth_credentials):
        """场景A-008: 刷新token"""
        login_response = requests.post(
            f"{api_url}/api/v1/auth/login",
            json=auth_credentials["admin"],
            timeout=10,
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        refresh_token = login_data["data"]["refresh_token"]

        response = requests.post(
            f"{api_url}/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
            timeout=10,
        )

        assert response.status_code == 200, f"刷新token失败: {response.status_code}"
        data = response.json()
        assert data["code"] == 0, f"响应code错误: {data.get('code')}"
        assert "access_token" in data["data"], "缺少新access_token"
        assert "refresh_token" in data["data"], "缺少新refresh_token"
