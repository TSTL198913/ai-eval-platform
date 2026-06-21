"""
冒烟测试 - 关键路径验证
覆盖: P0 级别核心功能
执行时间: < 5s
"""

import pytest

from src.schemas.evaluation import DomainResponse, EvaluationSchema


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

    def test_domain_response_valid(self):
        """验证成功响应可以正确创建"""
        response = DomainResponse(is_valid=True, score=1.0)
        assert response.is_valid is True
        assert response.score == 1.0

    def test_domain_response_invalid(self):
        """验证错误响应可以正确创建"""
        response = DomainResponse(is_valid=False, error="Test error")
        assert response.is_valid is False
        assert response.error == "Test error"

    def test_evaluation_schema_with_metadata(self):
        """验证带元数据的评估请求"""
        request = EvaluationSchema(
            id="smoke_test_002",
            type="security",
            payload={"user_input": "test"},
            metadata={"threshold": 0.8},
        )
        assert request.metadata is not None
        assert request.metadata["threshold"] == 0.8
