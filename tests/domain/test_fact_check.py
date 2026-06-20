"""
FactCheckEvaluator 专项测试
测试目标：验证事实核查评估器的核心功能和边界处理
关键发现：
- 评估器支持 user_input 和 text 两种字段命名
- 无LLM客户端时使用默认值 "结果: true\n理由: 无法验证"
- 通过检测输出中是否包含 "true" 来判断真实性
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.fact_check import FactCheckEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestFactCheckEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM客户端 - 必须设置return_value"""
        client = MagicMock()
        client.chat.return_value = "结果: true\n理由: 该陈述经过验证是真实的"
        return client

    @pytest.fixture
    def evaluator_with_client(self, mock_llm_client):
        """带LLM客户端的评估器"""
        return FactCheckEvaluator(client=mock_llm_client)

    def test_valid_input_returns_true_score_1_0(self, evaluator_with_client, mock_llm_client):
        """合法输入且LLM返回true时应得1.0分"""
        # Arrange
        request = EvaluationSchema(
            id="test_001",
            type="fact_check",
            payload={"user_input": "地球是圆的"},
        )

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert - 强断言验证业务逻辑
        assert result.is_valid is True
        assert result.score == 1.0
        assert "true" in result.text.lower()
        assert "事实核查" in result.data
        mock_llm_client.chat.assert_called_once()

    def test_valid_input_returns_false_score_0_0(self, mock_llm_client):
        """合法输入且LLM返回false时应得0.0分"""
        # Arrange
        mock_llm_client.chat.return_value = "结果: false\n理由: 该陈述是虚假的"
        evaluator = FactCheckEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test_002",
            type="fact_check",
            payload={"user_input": "太阳从西边升起"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言验证业务逻辑
        assert result.is_valid is True
        assert result.score == 0.0
        assert "false" in result.text.lower()
        assert "事实核查" in result.data

    def test_user_input_field_works(self, evaluator_with_client, mock_llm_client):
        """使用user_input字段应正常工作"""
        # Arrange
        request = EvaluationSchema(
            id="test_003",
            type="fact_check",
            payload={"user_input": "水在100度沸腾"},
        )

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score is not None
        mock_llm_client.chat.assert_called_once()

    def test_text_field_works(self, mock_llm_client):
        """使用text字段应正常工作"""
        # Arrange
        mock_llm_client.chat.return_value = "结果: true\n理由: 验证通过"
        evaluator = FactCheckEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test_004",
            type="fact_check",
            payload={"text": "地球绕太阳公转"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score == 1.0


class TestFactCheckEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def evaluator(self):
        """无LLM客户端的评估器"""
        return FactCheckEvaluator()

    def test_empty_input_returns_error(self, evaluator):
        """空输入应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="test_005",
            type="fact_check",
            payload={"user_input": ""},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言验证错误处理
        assert result.is_valid is False
        assert "不能为空" in result.error
        assert result.score is None

    def test_missing_input_field_returns_error(self, evaluator):
        """缺少输入字段应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="test_006",
            type="fact_check",
            payload={"other_field": "some_value"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_empty_payload_returns_error(self, evaluator):
        """空payload应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="test_007",
            type="fact_check",
            payload={},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is False
        assert "不能为空" in result.error


class TestFactCheckEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM客户端"""
        client = MagicMock()
        client.chat.return_value = "结果: true\n理由: 默认验证"
        return client

    @pytest.fixture
    def evaluator_with_client(self, mock_llm_client):
        """带LLM客户端的评估器"""
        return FactCheckEvaluator(client=mock_llm_client)

    def test_none_input_handled_gracefully(self):
        """None输入应被正确处理"""
        # Arrange
        evaluator = FactCheckEvaluator()
        request = EvaluationSchema(
            id="test_008",
            type="fact_check",
            payload={"user_input": None},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 不崩溃，返回合理结果
        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_special_characters_handled(self, evaluator_with_client, mock_llm_client):
        """特殊字符应被正确处理"""
        # Arrange
        request = EvaluationSchema(
            id="test_009",
            type="fact_check",
            payload={"user_input": "<script>alert('XSS')</script>"},
        )

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score is not None
        # 验证特殊字符被传递给LLM
        call_args = mock_llm_client.chat.call_args[0][0]
        assert "<script>" in call_args

    def test_long_text_handled(self, mock_llm_client):
        """超长文本应被正确处理"""
        # Arrange
        long_text = "这是一个很长的陈述。" * 1000  # 约10000字符
        mock_llm_client.chat.return_value = "结果: true\n理由: 文本过长，无法完全验证"
        evaluator = FactCheckEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test_010",
            type="fact_check",
            payload={"user_input": long_text},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score == 1.0

    def test_uppercase_true_in_output(self, mock_llm_client):
        """LLM输出包含大写TRUE时应被识别为true"""
        # Arrange
        mock_llm_client.chat.return_value = "结果: TRUE\n理由: 该陈述是真实的"
        evaluator = FactCheckEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test_011",
            type="fact_check",
            payload={"user_input": "测试陈述"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 大写TRUE也应识别
        assert result.is_valid is True
        assert result.score == 1.0

    def test_true_in_sentence(self, mock_llm_client):
        """LLM输出中包含true单词（非结果字段）应被识别"""
        # Arrange
        mock_llm_client.chat.return_value = "这个陈述是true的，经过验证"
        evaluator = FactCheckEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test_012",
            type="fact_check",
            payload={"user_input": "测试陈述"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 只要包含true就识别为true
        assert result.is_valid is True
        assert result.score == 1.0

    def test_mixed_case_true_handled(self, mock_llm_client):
        """混合大小写的true应被识别"""
        # Arrange
        mock_llm_client.chat.return_value = "结果: TrUe\n理由: 验证通过"
        evaluator = FactCheckEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test_013",
            type="fact_check",
            payload={"user_input": "测试陈述"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score == 1.0


class TestFactCheckEvaluatorDependencyHandling:
    """依赖测试 - 外部依赖Mock"""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM客户端"""
        client = MagicMock()
        client.chat.return_value = "结果: true\n理由: Mock验证"
        return client

    def test_without_llm_client_uses_default(self):
        """无LLM客户端时应使用默认值"""
        # Arrange
        evaluator = FactCheckEvaluator(client=None)
        request = EvaluationSchema(
            id="test_014",
            type="fact_check",
            payload={"user_input": "测试陈述"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 无客户端时使用默认值 "结果: true\n理由: 无法验证"
        assert result.is_valid is True
        assert result.score == 1.0
        assert "无法验证" in result.text

    def test_with_mock_llm_client_calls_chat(self, mock_llm_client):
        """有LLM客户端时应调用chat方法"""
        # Arrange
        evaluator = FactCheckEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test_015",
            type="fact_check",
            payload={"user_input": "测试陈述"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        mock_llm_client.chat.assert_called_once()
        assert result.is_valid is True

    def test_llm_client_exception_handled(self, mock_llm_client):
        """LLM客户端抛出异常时应被处理"""
        # Arrange
        mock_llm_client.chat.side_effect = Exception("LLM服务不可用")
        evaluator = FactCheckEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test_016",
            type="fact_check",
            payload={"user_input": "测试陈述"},
        )

        # Act & Assert - 异常应向上传播（由safe_evaluate捕获）
        with pytest.raises(Exception) as exc_info:
            evaluator.evaluate(request)
        assert "LLM服务不可用" in str(exc_info.value)


class TestFactCheckEvaluatorEdgeCases:
    """边界场景测试 - 复杂场景"""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM客户端"""
        client = MagicMock()
        client.chat.return_value = "结果: true\n理由: 默认"
        return client

    def test_payload_with_extra_fields_ignored(self, mock_llm_client):
        """payload包含额外字段时应被忽略"""
        # Arrange
        evaluator = FactCheckEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test_017",
            type="fact_check",
            payload={
                "user_input": "测试陈述",
                "extra_field": "应被忽略",
                "another_field": 123,
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score is not None

    def test_user_input_priority_over_text(self, mock_llm_client):
        """user_input字段优先级高于text字段"""
        # Arrange
        evaluator = FactCheckEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test_018",
            type="fact_check",
            payload={
                "user_input": "优先使用这个",
                "text": "不应使用这个",
            },
        )

        # Act
        evaluator.evaluate(request)

        # Assert - 验证使用了user_input字段
        call_args = mock_llm_client.chat.call_args[0][0]
        assert "优先使用这个" in call_args
        assert "不应使用这个" not in call_args

    def test_chinese_characters_in_input(self, mock_llm_client):
        """中文字符输入应被正确处理"""
        # Arrange
        mock_llm_client.chat.return_value = "结果: true\n理由: 该陈述经过验证是真实的"
        evaluator = FactCheckEvaluator(client=mock_llm_client)
        request = EvaluationSchema(
            id="test_019",
            type="fact_check",
            payload={"user_input": "中华人民共和国成立于1949年"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score == 1.0
        call_args = mock_llm_client.chat.call_args[0][0]
        assert "中华人民共和国" in call_args

    def test_prompt_format_correct(self, mock_llm_client):
        """验证生成的prompt格式正确"""
        # Arrange
        evaluator = FactCheckEvaluator(client=mock_llm_client)
        test_input = "地球是圆的"
        request = EvaluationSchema(
            id="test_020",
            type="fact_check",
            payload={"user_input": test_input},
        )

        # Act
        evaluator.evaluate(request)

        # Assert - 验证prompt包含关键元素
        call_args = mock_llm_client.chat.call_args[0][0]
        assert "验证" in call_args
        assert "真实性" in call_args
        assert test_input in call_args
        assert "true" in call_args or "false" in call_args


class TestFactCheckEvaluatorFactoryRegistration:
    """工厂注册测试"""

    def test_evaluator_registered_in_factory(self):
        """评估器应在工厂中注册"""
        # Arrange & Act
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        # Assert - 使用类名比较而不是类对象比较
        # 因为 force=True 会创建新类对象，直接比较会失败
        assert "fact_check" in EvaluatorFactory._registry
        assert EvaluatorFactory._registry["fact_check"].__name__ == "FactCheckEvaluator"

    def test_factory_creates_evaluator_instance(self):
        """工厂应能创建评估器实例"""
        # Arrange
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        # Act
        evaluator = EvaluatorFactory.get("fact_check")

        # Assert - 使用类名比较而不是类对象比较
        assert evaluator.__class__.__name__ == "FactCheckEvaluator"
        assert evaluator.client is None

    def test_factory_creates_evaluator_with_client(self):
        """工厂应能创建带客户端的评估器实例"""
        # Arrange
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        mock_client = MagicMock()

        # Act
        evaluator = EvaluatorFactory.get("fact_check", client=mock_client)

        # Assert - 使用类名比较而不是类对象比较
        assert evaluator.__class__.__name__ == "FactCheckEvaluator"
        assert evaluator.client == mock_client
