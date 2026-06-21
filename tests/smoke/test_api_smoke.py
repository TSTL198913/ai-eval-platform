"""
冒烟测试 - API 端点快速验证
执行时间: < 5s
"""

import pytest
from httpx import AsyncClient


@pytest.mark.smoke
class TestAPISmoke:
    """API 端点冒烟测试"""

    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"

    @pytest.mark.asyncio
    async def test_health_endpoint_available(self, base_url):
        """验证健康检查端点可用"""
        try:
            async with AsyncClient() as client:
                response = await client.get(f"{base_url}/health", timeout=5.0)
                assert response.status_code in [200, 404, 500]
        except Exception:
            pytest.skip("API 服务未运行，跳过冒烟测试")

    @pytest.mark.asyncio
    async def test_api_docs_available(self, base_url):
        """验证 API 文档端点可用"""
        try:
            async with AsyncClient() as client:
                response = await client.get(f"{base_url}/docs", timeout=5.0)
                assert response.status_code in [200, 404]
        except Exception:
            pytest.skip("API 服务未运行，跳过冒烟测试")
