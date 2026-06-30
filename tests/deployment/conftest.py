"""
部署测试配置 - 针对服务器环境的测试夹具
"""

import os

import pytest

API_BASE_URL = os.environ.get("API_BASE_URL", "http://192.168.30.134:8000")


@pytest.fixture(scope="module")
def api_url():
    """API基础URL"""
    return API_BASE_URL


@pytest.fixture(scope="module")
def auth_credentials():
    """认证凭证"""
    return {
        "admin": {"username": "admin", "password": "admin123"},
        "user": {"username": "user", "password": "user123"},
    }


@pytest.fixture(scope="module")
def session_token(api_url, auth_credentials):
    """获取管理员token用于后续测试"""
    import requests

    try:
        response = requests.post(
            f"{api_url}/api/v1/auth/login",
            json=auth_credentials["admin"],
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            return data["data"]["access_token"]
    except Exception:
        pass
    pytest.skip("无法获取认证token")
    return None
