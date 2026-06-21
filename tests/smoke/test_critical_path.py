"""
冒烟测试 - 关键路径验证
覆盖: P0 级别核心功能
执行时间: < 5s
"""

import pytest

from src.schemas.evaluation import EvaluationSchema, DomainResponse


@pytest.mark.smoke
class TestCriticalPathSmoke:
    """关键路径冒烟测试"""

    def test_evaluation_schema_validation(self):
        """验证评估请求可以正确创建"""
        request = EvaluationSchema(
            id="smoke_test_001",
            type="code",
            payload={"user_input": "test", "expected_output": "test"},
        )
        assert request.id == "smoke_test_001"
        assert request.type == "code"

    def test_success_response_creation(self):
        """验证成功响应可以正确创建"""
        response = DomainResponse.success(data={"result": "test"})
        assert response.is_valid is True
        assert response.data["result"] == "test"

    def test_error_response_creation(self):
        """验证错误响应可以正确创建"""
        response = DomainResponse.error(message="Test error", code=400)
        assert response.is_valid is False
        assert response.error == "Test error"
