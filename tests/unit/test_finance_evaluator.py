from unittest.mock import MagicMock

from src.domain.evaluators.finance import FinanceEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestFinanceEvaluator:
    """金融评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_with_client(self):
        """测试有客户端评估"""
        self.mock_client.chat.return_value = "1000元"

        evaluator = FinanceEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_finance",
            type="finance",
            payload={"user_input": "计算收益"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_evaluate_with_expected_output(self):
        """测试包含期望输出"""
        self.mock_client.chat.return_value = "1000元"

        evaluator = FinanceEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_expected",
            type="finance",
            payload={
                "user_input": "计算收益",
                "expected_output": "1000元",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_evaluate_without_client(self):
        """测试无客户端模式"""
        evaluator = FinanceEvaluator(None)
        request = EvaluationSchema(
            id="test_no_client",
            type="finance",
            payload={"user_input": "计算收益"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "未配置" in result.error

    def test_evaluate_missing_user_input(self):
        """测试缺少输入"""
        evaluator = FinanceEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_missing",
            type="finance",
            payload={},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_evaluate_custom_system_prompt(self):
        """测试自定义系统提示"""
        self.mock_client.chat.return_value = "专业金融分析"

        evaluator = FinanceEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_custom_prompt",
            type="finance",
            payload={
                "user_input": "分析投资组合",
                "system_prompt": "你是投资顾问",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True