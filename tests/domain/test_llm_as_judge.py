"""
LLM-as-Judge 评估器专项测试
测试目标：验证 LLMAJudgeEvaluator 的多维度评估能力
关键发现：
- 支持正确性、完整性、相关性、简洁性、安全性、创造性等维度
- 自动降级解析机制保证鲁棒性
- 证据归因机制提供可解释性
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.domain.evaluators.llm_as_judge import LLMAJudgeEvaluator
from src.schemas.evaluation import EvaluationSchema


# ============================================================
# 测试夹具
# ============================================================
@pytest.fixture
def mock_llm_client():
    """Mock LLM客户端"""
    client = MagicMock()
    client.chat.return_value = json.dumps({
        "scores": {
            "correctness": {
                "score": 85,
                "reason": "回答准确，符合预期",
                "evidence": ["回答内容准确"],
                "citation": "无"
            },
            "relevance": {
                "score": 90,
                "reason": "回答与问题高度相关",
                "evidence": ["直接回答了问题"],
                "citation": "无"
            }
        },
        "total_score": 87,
        "confidence": 0.85,
        "conflict_detected": False
    })
    return client


@pytest.fixture
def evaluator_with_client(mock_llm_client):
    """带LLM客户端的评估器"""
    return LLMAJudgeEvaluator(client=mock_llm_client)


@pytest.fixture
def evaluator_without_client():
    """不带LLM客户端的评估器（使用Mock结果）"""
    return LLMAJudgeEvaluator(client=None)


@pytest.fixture
def basic_request():
    """基础评估请求"""
    return EvaluationSchema(
        id="test-001",
        type="llm_as_judge",
        payload={
            "user_input": "什么是机器学习？",
            "actual_output": "机器学习是人工智能的一个分支，它使计算机能够从数据中学习并做出决策。"
        }
    )


# ============================================================
# Part 1: 正向测试 - 正常输入
# ============================================================
class TestLLMAJudgeEvaluatorPositiveCases:
    """正向测试 - 正常输入应返回预期输出"""

    def test_evaluate_with_llm_client_returns_valid_response(self, evaluator_with_client, basic_request):
        """有LLM客户端时应正常评估并返回有效响应"""
        # Act
        result = evaluator_with_client.evaluate(basic_request)

        # Assert - 强断言验证业务逻辑
        assert result.is_valid is True
        assert result.score is not None
        assert 0.0 <= result.score <= 1.0
        assert result.data is not None
        assert "llm_judge_scores" in result.data
        assert "total_score" in result.data
        assert "confidence" in result.data

    def test_evaluate_without_llm_client_uses_mock_result(self, evaluator_without_client, basic_request):
        """无LLM客户端时应使用Mock结果"""
        # Act
        result = evaluator_without_client.evaluate(basic_request)

        # Assert - 验证Mock结果
        assert result.is_valid is True
        assert result.score == 0.87  # Mock返回87分
        assert result.data["total_score"] == 87
        assert "correctness" in result.data["llm_judge_scores"]
        assert "relevance" in result.data["llm_judge_scores"]

    def test_evaluate_with_multiple_dimensions(self, evaluator_with_client, basic_request):
        """多维度评估应正确计算分数"""
        # Arrange
        basic_request.payload["dimensions"] = ["correctness", "completeness", "relevance"]

        # Act
        result = evaluator_with_client.evaluate(basic_request)

        # Assert
        assert result.is_valid is True
        assert result.data["confidence"] > 0.0
        assert isinstance(result.data["llm_judge_scores"], dict)

    def test_evaluate_with_expected_output(self, evaluator_with_client, mock_llm_client):
        """包含期望输出时应构建包含期望输出的提示词"""
        # Arrange
        request = EvaluationSchema(
            id="test-002",
            type="llm_as_judge",
            payload={
                "user_input": "如何退款？",
                "actual_output": "您可以在订单页面申请退款",
                "expected_output": "在订单详情页点击退款按钮"
            }
        )

        # Act
        evaluator_with_client.evaluate(request)

        # Assert - 验证LLM客户端被调用
        assert mock_llm_client.chat.called
        call_args = mock_llm_client.chat.call_args[0][0]
        assert "期望输出" in call_args
        assert "在订单详情页点击退款按钮" in call_args

    def test_evaluate_with_criteria(self, evaluator_with_client, mock_llm_client):
        """包含额外评估标准时应构建包含标准的提示词"""
        # Arrange
        request = EvaluationSchema(
            id="test-003",
            type="llm_as_judge",
            payload={
                "user_input": "解释量子计算",
                "actual_output": "量子计算利用量子力学原理...",
                "criteria": "回答必须包含专业术语，且通俗易懂"
            }
        )

        # Act
        evaluator_with_client.evaluate(request)

        # Assert - 验证标准被包含在提示词中
        call_args = mock_llm_client.chat.call_args[0][0]
        assert "额外评估标准" in call_args
        assert "专业术语" in call_args

    def test_evaluate_with_golden_dataset_id(self, evaluator_with_client, mock_llm_client):
        """包含黄金数据集ID时应尝试获取Few-shot示例"""
        # Arrange
        request = EvaluationSchema(
            id="test-004",
            type="llm_as_judge",
            payload={
                "user_input": "测试问题",
                "actual_output": "测试回答",
                "golden_dataset_id": "dataset-001",
                "few_shot_limit": 3
            }
        )

        # Act
        with patch('src.domain.golden_dataset.golden_dataset_manager') as mock_manager:
            mock_manager.get_few_shot_examples.return_value = ["示例1", "示例2"]
            result = evaluator_with_client.evaluate(request)

        # Assert
        assert result.is_valid is True
        mock_manager.get_few_shot_examples.assert_called_once_with(
            "dataset-001", limit=3, dimensions=["correctness", "relevance"]
        )

    def test_evaluate_extracts_attribution_data(self, evaluator_with_client, basic_request):
        """评估应提取证据归因数据"""
        # Act
        result = evaluator_with_client.evaluate(basic_request)

        # Assert - 验证归因数据结构
        assert "attribution" in result.data
        assert isinstance(result.data["attribution"], dict)
        for _dim, attr_data in result.data["attribution"].items():
            assert "evidence" in attr_data
            assert "citation" in attr_data
            assert isinstance(attr_data["evidence"], list)

    def test_evaluate_with_text_field_as_input(self, evaluator_without_client):
        """使用text字段作为输入时应正常工作"""
        # Arrange
        request = EvaluationSchema(
            id="test-005",
            type="llm_as_judge",
            payload={
                "text": "这是一个问题",
                "actual_output": "这是一个回答"
            }
        )

        # Act
        result = evaluator_without_client.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score is not None

    def test_evaluate_with_conflict_detection(self, mock_llm_client):
        """检测到评分冲突时应标记conflict_detected"""
        # Arrange
        mock_llm_client.chat.return_value = json.dumps({
            "scores": {
                "correctness": {"score": 90, "reason": "高分", "evidence": [], "citation": "无"}
            },
            "total_score": 90,
            "confidence": 0.7,
            "conflict_detected": True
        })
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-006",
            type="llm_as_judge",
            payload={"user_input": "问题", "actual_output": "回答"}
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.data["conflict_detected"] is True

    def test_evaluate_with_custom_dimensions(self, mock_llm_client):
        """自定义维度评估应正确处理"""
        # Arrange
        mock_llm_client.chat.return_value = json.dumps({
            "scores": {
                "creativity": {"score": 95, "reason": "创新性强", "evidence": [], "citation": "无"}
            },
            "total_score": 95,
            "confidence": 0.9,
            "conflict_detected": False
        })
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-007",
            type="llm_as_judge",
            payload={
                "user_input": "创作一首诗",
                "actual_output": "春眠不觉晓...",
                "dimensions": ["creativity"]
            }
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert "creativity" in result.data["llm_judge_scores"]


# ============================================================
# Part 2: 负向测试 - 错误输入
# ============================================================
class TestLLMAJudgeEvaluatorNegativeCases:
    """负向测试 - 错误输入应返回错误"""

    def test_evaluate_with_empty_user_input_returns_error(self, evaluator_without_client):
        """user_input和text都为空时应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="test-008",
            type="llm_as_judge",
            payload={
                "actual_output": "这是一个回答"
            }
        )

        # Act
        result = evaluator_without_client.evaluate(request)

        # Assert - 强断言验证错误信息
        assert result.is_valid is False
        assert "不能为空" in result.error
        assert "user_input" in result.error or "text" in result.error

    def test_evaluate_with_empty_actual_output_returns_error(self, evaluator_without_client):
        """actual_output为空时应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="test-009",
            type="llm_as_judge",
            payload={
                "user_input": "这是一个问题",
                "actual_output": ""
            }
        )

        # Act
        result = evaluator_without_client.evaluate(request)

        # Assert
        assert result.is_valid is False
        assert "actual_output" in result.error
        assert "不能为空" in result.error

    def test_evaluate_with_none_actual_output_returns_error(self, evaluator_without_client):
        """actual_output为None时应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="test-010",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": None
            }
        )

        # Act
        result = evaluator_without_client.evaluate(request)

        # Assert
        assert result.is_valid is False
        assert "actual_output" in result.error

    def test_evaluate_with_whitespace_only_input_returns_valid(self, evaluator_without_client):
        """仅包含空白字符的输入会被视为有效（源代码不检查空白字符）"""
        # Arrange
        request = EvaluationSchema(
            id="test-011",
            type="llm_as_judge",
            payload={
                "user_input": "   ",
                "actual_output": "回答"
            }
        )

        # Act
        result = evaluator_without_client.evaluate(request)

        # Assert - 源代码不检查空白字符，空白字符串被视为有效
        assert result.is_valid is True

    def test_evaluate_llm_returns_invalid_json(self, mock_llm_client):
        """LLM返回无效JSON时应使用降级解析"""
        # Arrange
        mock_llm_client.chat.return_value = "这不是一个有效的JSON"
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-012",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答",
                "dimensions": ["correctness"]
            }
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 降级解析应返回默认分数
        assert result.is_valid is True
        assert result.score == 0.5  # 降级解析默认50分

    def test_evaluate_llm_returns_partial_json(self, mock_llm_client):
        """LLM返回包含JSON的文本时应提取JSON部分"""
        # Arrange
        mock_llm_client.chat.return_value = "这是评估结果：{\"scores\": {\"correctness\": {\"score\": 80}}, \"total_score\": 80, \"confidence\": 0.8}"
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-013",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答",
                "dimensions": ["correctness"]
            }
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["total_score"] == 80


# ============================================================
# Part 3: 边界测试 - 边界值
# ============================================================
class TestLLMAJudgeEvaluatorBoundaryCases:
    """边界测试 - 边界值处理"""

    def test_evaluate_with_empty_dimensions_uses_default(self, evaluator_without_client):
        """dimensions为空列表时应使用默认维度"""
        # Arrange
        request = EvaluationSchema(
            id="test-014",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答",
                "dimensions": []
            }
        )

        # Act
        result = evaluator_without_client.evaluate(request)

        # Assert - 应使用默认维度或正常处理
        assert result.is_valid is True

    def test_evaluate_with_unknown_dimension(self, mock_llm_client):
        """未知维度应被正确处理"""
        # Arrange
        mock_llm_client.chat.return_value = json.dumps({
            "scores": {
                "unknown_dim": {"score": 75, "reason": "自定义维度", "evidence": [], "citation": "无"}
            },
            "total_score": 75,
            "confidence": 0.75,
            "conflict_detected": False
        })
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-015",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答",
                "dimensions": ["unknown_dim"]
            }
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert "unknown_dim" in result.data["llm_judge_scores"]

    def test_evaluate_with_minimal_score(self, mock_llm_client):
        """最小分数0分应正确处理"""
        # Arrange
        mock_llm_client.chat.return_value = json.dumps({
            "scores": {
                "correctness": {"score": 0, "reason": "完全错误", "evidence": [], "citation": "无"}
            },
            "total_score": 0,
            "confidence": 0.9,
            "conflict_detected": False
        })
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-016",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答"
            }
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score == 0.0
        assert result.data["total_score"] == 0

    def test_evaluate_with_maximal_score(self, mock_llm_client):
        """最大分数100分应正确处理"""
        # Arrange
        mock_llm_client.chat.return_value = json.dumps({
            "scores": {
                "correctness": {"score": 100, "reason": "完美回答", "evidence": [], "citation": "无"}
            },
            "total_score": 100,
            "confidence": 1.0,
            "conflict_detected": False
        })
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-017",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答"
            }
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score == 1.0
        assert result.data["total_score"] == 100

    def test_evaluate_with_confidence_zero(self, mock_llm_client):
        """置信度为0时应正确处理"""
        # Arrange
        mock_llm_client.chat.return_value = json.dumps({
            "scores": {
                "correctness": {"score": 50, "reason": "不确定", "evidence": [], "citation": "无"}
            },
            "total_score": 50,
            "confidence": 0.0,
            "conflict_detected": False
        })
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-018",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答"
            }
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["confidence"] == 0.0

    def test_evaluate_with_confidence_one(self, mock_llm_client):
        """置信度为1时应正确处理"""
        # Arrange
        mock_llm_client.chat.return_value = json.dumps({
            "scores": {
                "correctness": {"score": 100, "reason": "非常确定", "evidence": [], "citation": "无"}
            },
            "total_score": 100,
            "confidence": 1.0,
            "conflict_detected": False
        })
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-019",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答"
            }
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["confidence"] == 1.0

    def test_evaluate_with_few_shot_limit_boundary(self, mock_llm_client):
        """few_shot_limit边界值应正确处理"""
        # Arrange
        request = EvaluationSchema(
            id="test-020",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答",
                "golden_dataset_id": "dataset-001",
                "few_shot_limit": 0  # 边界值
            }
        )

        # Act
        with patch('src.domain.golden_dataset.golden_dataset_manager') as mock_manager:
            mock_manager.get_few_shot_examples.return_value = []
            result = LLMAJudgeEvaluator(client=mock_llm_client).evaluate(request)

        # Assert
        assert result.is_valid is True

    def test_evaluate_with_very_long_input(self, mock_llm_client):
        """超长输入应正常处理"""
        # Arrange
        long_text = "测试内容" * 1000
        request = EvaluationSchema(
            id="test-021",
            type="llm_as_judge",
            payload={
                "user_input": long_text,
                "actual_output": "回答"
            }
        )

        # Act
        result = LLMAJudgeEvaluator(client=mock_llm_client).evaluate(request)

        # Assert
        assert result.is_valid is True
        assert mock_llm_client.chat.called


# ============================================================
# Part 4: 异常测试 - 异常情况处理
# ============================================================
class TestLLMAJudgeEvaluatorExceptionCases:
    """异常测试 - 异常情况处理"""

    def test_evaluate_json_decode_error_uses_fallback(self, mock_llm_client):
        """JSON解析失败时应使用降级解析"""
        # Arrange
        mock_llm_client.chat.return_value = "{invalid json"
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-022",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答",
                "dimensions": ["correctness"]
            }
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 降级解析应返回默认分数
        assert result.is_valid is True
        assert result.score == 0.5
        assert result.data["confidence"] == 0.5

    def test_evaluate_golden_dataset_exception_handled(self, mock_llm_client):
        """黄金数据集异常应被捕获并忽略"""
        # Arrange
        request = EvaluationSchema(
            id="test-023",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答",
                "golden_dataset_id": "invalid-id"
            }
        )

        # Act
        with patch('src.domain.golden_dataset.golden_dataset_manager') as mock_manager:
            mock_manager.get_few_shot_examples.side_effect = Exception("Dataset not found")
            result = LLMAJudgeEvaluator(client=mock_llm_client).evaluate(request)

        # Assert - 异常应被捕获，评估继续进行
        assert result.is_valid is True

    def test_evaluate_llm_client_exception_propagates(self, mock_llm_client):
        """LLM客户端异常应传播"""
        # Arrange
        mock_llm_client.chat.side_effect = Exception("LLM service unavailable")
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-024",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答"
            }
        )

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            evaluator.evaluate(request)
        assert "LLM service unavailable" in str(exc_info.value)

    def test_evaluate_missing_total_score_in_response(self, mock_llm_client):
        """响应中缺少total_score时应使用默认值"""
        # Arrange
        mock_llm_client.chat.return_value = json.dumps({
            "scores": {
                "correctness": {"score": 80, "reason": "良好", "evidence": [], "citation": "无"}
            },
            "confidence": 0.8
        })
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-025",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答"
            }
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["total_score"] == 0  # 默认值

    def test_evaluate_missing_confidence_in_response(self, mock_llm_client):
        """响应中缺少confidence时应使用默认值"""
        # Arrange
        mock_llm_client.chat.return_value = json.dumps({
            "scores": {
                "correctness": {"score": 80, "reason": "良好", "evidence": [], "citation": "无"}
            },
            "total_score": 80
        })
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-026",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答"
            }
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["confidence"] == 0.8  # 默认值

    def test_evaluate_malformed_score_data(self, mock_llm_client):
        """分数数据格式错误时应正确处理"""
        # Arrange
        mock_llm_client.chat.return_value = json.dumps({
            "scores": {
                "correctness": "invalid_score_format"  # 应该是dict
            },
            "total_score": 80,
            "confidence": 0.8
        })
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-027",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答"
            }
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 应正常处理，attribution可能为空
        assert result.is_valid is True


# ============================================================
# Part 5: 依赖测试 - Mock外部依赖
# ============================================================
class TestLLMAJudgeEvaluatorDependencyHandling:
    """依赖测试 - 外部依赖Mock验证"""

    def test_llm_client_called_with_correct_prompt(self, mock_llm_client):
        """LLM客户端应被正确调用"""
        # Arrange
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-028",
            type="llm_as_judge",
            payload={
                "user_input": "什么是AI？",
                "actual_output": "AI是人工智能的缩写",
                "dimensions": ["correctness", "relevance"]
            }
        )

        # Act
        evaluator.evaluate(request)

        # Assert - 验证LLM客户端被调用
        assert mock_llm_client.chat.called
        call_args = mock_llm_client.chat.call_args[0][0]
        assert "什么是AI？" in call_args
        assert "AI是人工智能的缩写" in call_args
        assert "正确性" in call_args
        assert "相关性" in call_args

    def test_llm_client_not_called_when_using_mock(self, evaluator_without_client, basic_request):
        """无LLM客户端时不应调用chat方法"""
        # Act
        result = evaluator_without_client.evaluate(basic_request)

        # Assert - 验证返回Mock结果
        assert result.is_valid is True
        assert result.data["total_score"] == 87

    def test_golden_dataset_manager_called_correctly(self, mock_llm_client):
        """黄金数据集管理器应被正确调用"""
        # Arrange
        request = EvaluationSchema(
            id="test-029",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答",
                "golden_dataset_id": "dataset-123",
                "few_shot_limit": 5,
                "dimensions": ["correctness", "safety"]
            }
        )

        # Act
        with patch('src.domain.golden_dataset.golden_dataset_manager') as mock_manager:
            mock_manager.get_few_shot_examples.return_value = ["示例1", "示例2", "示例3"]
            evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
            result = evaluator.evaluate(request)

        # Assert - 验证调用参数
        assert result.is_valid is True
        mock_manager.get_few_shot_examples.assert_called_once_with(
            "dataset-123", limit=5, dimensions=["correctness", "safety"]
        )

    def test_prompt_includes_all_sections(self, mock_llm_client):
        """提示词应包含所有必要部分"""
        # Arrange
        request = EvaluationSchema(
            id="test-030",
            type="llm_as_judge",
            payload={
                "user_input": "用户问题",
                "actual_output": "模型输出",
                "expected_output": "期望输出",
                "criteria": "评估标准",
                "dimensions": ["correctness", "completeness"]
            }
        )

        # Act
        LLMAJudgeEvaluator(client=mock_llm_client).evaluate(request)

        # Assert - 验证提示词结构
        call_args = mock_llm_client.chat.call_args[0][0]
        assert "用户问题" in call_args
        assert "模型输出" in call_args
        assert "期望输出" in call_args
        assert "评估标准" in call_args
        assert "正确性" in call_args
        assert "完整性" in call_args
        assert "评分规则" in call_args
        assert "JSON" in call_args

    def test_prompt_format_with_evidence_requirements(self, mock_llm_client):
        """提示词应包含证据引用要求"""
        # Arrange
        request = EvaluationSchema(
            id="test-031",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答"
            }
        )

        # Act
        LLMAJudgeEvaluator(client=mock_llm_client).evaluate(request)

        # Assert - 验证证据要求
        call_args = mock_llm_client.chat.call_args[0][0]
        assert "evidence" in call_args
        assert "引用" in call_args
        assert "citation" in call_args


# ============================================================
# Part 6: 集成测试 - 完整流程
# ============================================================
class TestLLMAJudgeEvaluatorIntegration:
    """集成测试 - 完整业务流程"""

    def test_full_evaluation_workflow(self, mock_llm_client):
        """完整评估流程应正常工作"""
        # Arrange
        mock_llm_client.chat.return_value = json.dumps({
            "scores": {
                "correctness": {
                    "score": 92,
                    "reason": "回答准确，逻辑清晰",
                    "evidence": ["回答准确", "逻辑清晰"],
                    "citation": "[KB-001]"
                },
                "relevance": {
                    "score": 88,
                    "reason": "与问题高度相关",
                    "evidence": ["直接回答了问题"],
                    "citation": "无"
                }
            },
            "total_score": 90,
            "confidence": 0.9,
            "conflict_detected": False
        })
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-032",
            type="llm_as_judge",
            payload={
                "user_input": "解释机器学习的基本概念",
                "actual_output": "机器学习是人工智能的一个分支，通过算法让计算机从数据中学习模式。",
                "expected_output": "机器学习是一种数据驱动的方法",
                "criteria": "回答应简洁明了",
                "dimensions": ["correctness", "relevance"]
            }
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 验证完整响应
        assert result.is_valid is True
        assert result.score == 0.9
        assert result.data["total_score"] == 90
        assert result.data["confidence"] == 0.9
        assert result.data["conflict_detected"] is False
        assert "correctness" in result.data["llm_judge_scores"]
        assert "relevance" in result.data["llm_judge_scores"]
        assert "correctness" in result.data["attribution"]
        assert result.data["attribution"]["correctness"]["citation"] == "[KB-001]"

    def test_fallback_parse_workflow(self, mock_llm_client):
        """降级解析流程应正常工作"""
        # Arrange
        mock_llm_client.chat.return_value = "correctness: 75, relevance: 80"
        evaluator = LLMAJudgeEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test-033",
            type="llm_as_judge",
            payload={
                "user_input": "问题",
                "actual_output": "回答",
                "dimensions": ["correctness", "relevance"]
            }
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 降级解析应提取分数
        assert result.is_valid is True
        assert result.data["confidence"] == 0.6  # 降级解析的置信度
        assert "correctness" in result.data["llm_judge_scores"]
        assert "relevance" in result.data["llm_judge_scores"]


# ============================================================
# Part 7: 工厂注册测试
# ============================================================
class TestLLMAJudgeEvaluatorFactory:
    """工厂注册测试"""

    def test_evaluator_registered_in_factory(self):
        """评估器应正确注册到工厂"""
        # Arrange & Act
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        # Assert
        assert "llm_as_judge" in EvaluatorFactory._registry
        assert EvaluatorFactory._registry["llm_as_judge"].__name__ == "LLMAJudgeEvaluator"

    def test_factory_creates_evaluator_instance(self):
        """工厂应能创建评估器实例"""
        # Arrange
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        # Act
        evaluator = EvaluatorFactory.get("llm_as_judge")

        # Assert
        assert evaluator.__class__.__name__ == "LLMAJudgeEvaluator"

    def test_factory_creates_evaluator_with_client(self):
        """工厂应能创建带客户端的评估器实例"""
        # Arrange
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        mock_client = MagicMock()

        # Act
        evaluator = EvaluatorFactory.get("llm_as_judge", client=mock_client)

        # Assert
        assert evaluator.__class__.__name__ == "LLMAJudgeEvaluator"
        assert evaluator.client is mock_client
