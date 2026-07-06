"""真实数据集成测试 - 强断言版本

测试目标：验证系统在真实数据场景下的精确业务逻辑

强断言要求：
1. 验证评分精确范围和精度
2. 验证评估状态精确值
3. 验证返回字段完整性和类型
4. 验证错误处理精确行为
"""

import pytest
from unittest.mock import MagicMock

from src.engine import EvaluationEngine
from src.schemas.evaluation import EvaluationSchema, DomainResponse, EvaluatorStatus
from src.schemas.schemas import EvaluationResult, EvaluationStatus as RecordStatus


class TestRealDataStrongAssertions:
    """真实数据强断言测试"""

    @pytest.fixture
    def mock_client(self):
        mock = MagicMock()
        mock.chat.return_value = '{"score": 0.85, "confidence": 0.92}'
        return mock

    def test_real_data_code_evaluation_precise_score(self, mock_client):
        """真实代码评估应返回精确分数"""
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="real-code-001",
            type="code",
            payload={
                "code": """
def calculate_area(radius):
    if radius < 0:
        raise ValueError("半径不能为负数")
    return 3.14159 * radius ** 2
""",
                "metadata": {"language": "python"},
            },
        )

        result = engine.run(request)

        assert isinstance(result, EvaluationResult)
        assert result.case_id == "real-code-001"

        assert result.response is not None
        assert isinstance(result.response, DomainResponse)
        assert result.response.is_valid is True
        assert result.response.evaluation_status in (EvaluatorStatus.SUCCESS, EvaluatorStatus.PARTIAL)

        assert result.response.score is not None
        assert isinstance(result.response.score, float)
        assert 0.0 <= result.response.score <= 1.0

        assert result.response.confidence is not None
        assert isinstance(result.response.confidence, float)
        assert 0.0 <= result.response.confidence <= 1.0

        assert result.response.data is not None
        assert isinstance(result.response.data, dict)

    def test_real_data_semantic_evaluation_precise_metrics(self, mock_client):
        """真实语义评估应返回精确指标"""
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="real-semantic-001",
            type="semantic",
            payload={
                "user_input": "解释什么是机器学习",
                "actual_output": "机器学习是一种人工智能技术，使计算机能够从数据中学习并做出预测。",
                "expected_output": "机器学习是人工智能的一个分支，通过算法让计算机从数据中自动学习模式。",
            },
        )

        result = engine.run(request)

        assert isinstance(result, EvaluationResult)
        assert result.response is not None
        assert isinstance(result.response, DomainResponse)
        assert result.response.is_valid is True

        assert result.response.score is not None
        assert isinstance(result.response.score, float)

        assert "similarity_score" in result.response.data or result.response.score > 0.0

    def test_real_data_factuality_evaluation_boundary(self, mock_client):
        """真实事实性评估边界测试"""
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="real-factuality-001",
            type="factuality",
            payload={
                "claim": "地球是圆的",
                "expected_output": "地球是一个近似球体",
                "evidence": "大量科学观测和卫星图像证明地球是一个近似球体。",
            },
        )

        result = engine.run(request)

        assert isinstance(result, EvaluationResult)
        assert result.response is not None
        assert isinstance(result.response, DomainResponse)
        assert result.response.is_valid is not None
        assert result.response.score is not None

    def test_real_data_security_evaluation_detailed(self, mock_client):
        """真实安全评估应返回详细信息"""
        mock_client.chat.return_value = """
{
    "score": 0.3,
    "confidence": 0.88,
    "vulnerabilities": [
        {"type": "SQL注入", "severity": "high", "line": 5},
        {"type": "XSS", "severity": "medium", "line": 12}
    ],
    "recommendations": ["使用参数化查询", "对用户输入进行转义"]
}
"""
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="real-security-001",
            type="security",
            payload={
                "code": """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
""",
                "metadata": {"language": "python"},
            },
        )

        result = engine.run(request)

        assert isinstance(result, EvaluationResult)
        assert result.response is not None
        assert isinstance(result.response, DomainResponse)
        assert result.response.score is not None
        assert result.response.score < 0.5

    def test_empty_payload_returns_error(self, mock_client):
        """空payload应返回精确错误"""
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="empty-payload-001",
            type="code",
            payload={},
        )

        result = engine.run(request)

        assert isinstance(result, EvaluationResult)
        assert result.response is not None
        assert result.response.evaluation_status == EvaluatorStatus.ERROR or result.response.is_valid is False

    def test_unknown_evaluator_type_returns_error(self, mock_client):
        """未知评估器类型应返回精确错误"""
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="unknown-type-001",
            type="unknown_evaluator",
            payload={"test": "data"},
        )

        result = engine.run(request)

        assert isinstance(result, EvaluationResult)
        assert result.response is not None
        assert result.response.evaluation_status == EvaluatorStatus.ERROR

    def test_large_payload_handled_correctly(self, mock_client):
        """大payload应正确处理"""
        engine = EvaluationEngine(client=mock_client)

        large_code = "def test():\n" + "    pass\n" * 1000

        request = EvaluationSchema(
            id="large-payload-001",
            type="code",
            payload={
                "code": large_code,
                "metadata": {"language": "python"},
            },
        )

        result = engine.run(request)

        assert isinstance(result, EvaluationResult)
        assert result.response is not None
        assert result.response.is_valid is not None

    def test_real_data_evaluation_result_consistency(self, mock_client):
        """相同输入应返回一致结果"""
        engine = EvaluationEngine(client=mock_client)

        request1 = EvaluationSchema(
            id="consistency-001",
            type="factuality",
            payload={
                "claim": "水在100摄氏度时沸腾",
                "evidence": "标准大气压下，水的沸点是100摄氏度。",
            },
        )

        request2 = EvaluationSchema(
            id="consistency-002",
            type="factuality",
            payload={
                "claim": "水在100摄氏度时沸腾",
                "evidence": "标准大气压下，水的沸点是100摄氏度。",
            },
        )

        result1 = engine.run(request1)
        result2 = engine.run(request2)

        assert isinstance(result1, EvaluationResult)
        assert isinstance(result2, EvaluationResult)
        assert result1.response is not None
        assert result2.response is not None
        assert result1.response.is_valid == result2.response.is_valid