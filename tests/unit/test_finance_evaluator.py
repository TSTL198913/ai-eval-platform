"""
金融评估器专项测试 - 覆盖金融评估流程和评分逻辑
测试目标：验证FinanceEvaluator的LLM调用流程、评分逻辑、错误处理
关键发现：FinanceEvaluator依赖LLM客户端，使用score_numeric_match评分
"""
import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.finance import FinanceEvaluator
from src.domain.evaluators.scoring import score_numeric_match, is_passing
from src.schemas.evaluation import EvaluationSchema


class TestFinanceEvaluatorLLMClientDependency:
    """LLM客户端依赖测试 - 验证评估器对LLM的正确使用"""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM客户端"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        # 关键：必须设置return_value，否则返回MagicMock对象
        client.chat.return_value = "营收100万元"
        return client

    @pytest.fixture
    def evaluator_with_client(self, mock_llm_client):
        """带LLM客户端的评估器"""
        return FinanceEvaluator(client=mock_llm_client)

    @pytest.fixture
    def evaluator_without_client(self):
        """无LLM客户端的评估器"""
        return FinanceEvaluator(client=None)

    def test_llm_client_required(self, evaluator_without_client):
        """无LLM客户端时应返回错误"""
        request = EvaluationSchema(
            id="fin_001",
            type="finance",
            payload={"text": "分析财报", "expected_output": "100万元"},
        )
        result = evaluator_without_client.evaluate(request)
        assert result.is_valid is False
        assert "LLM client 未配置" in result.error

    def test_llm_client_called_with_correct_params(self, evaluator_with_client, mock_llm_client):
        """验证LLM客户端被正确调用"""
        request = EvaluationSchema(
            id="fin_002",
            type="finance",
            payload={
                "text": "请分析公司营收情况",
                "expected_output": "100万元",
                "system_prompt": "你是金融分析师",
            },
        )
        result = evaluator_with_client.evaluate(request)
        # 验证LLM客户端被调用，且参数正确
        mock_llm_client.chat.assert_called_once()
        call_args = mock_llm_client.chat.call_args
        assert call_args[0][0] == "请分析公司营收情况"
        assert call_args[1]["system_prompt"] == "你是金融分析师"
        # 验证返回结果正确
        assert result.text == "营收100万元"

    def test_llm_client_called_with_default_prompt(self, evaluator_with_client, mock_llm_client):
        """无system_prompt时使用默认提示"""
        request = EvaluationSchema(
            id="fin_003",
            type="finance",
            payload={"text": "分析财报", "expected_output": "100万元"},
        )
        result = evaluator_with_client.evaluate(request)
        call_args = mock_llm_client.chat.call_args
        # 默认金融提示应被使用
        assert "金融分析师" in call_args[1]["system_prompt"]
        assert result.text == "营收100万元"


class TestFinanceEvaluatorScoringLogic:
    """评分逻辑测试 - 验证score_numeric_match集成
    
    关键发现：score_numeric_match只支持精确数字匹配，不支持部分匹配
    例如：expected="100万元"，output="95万元"，score=0.0（因为100不在95中）
    """

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM客户端 - 返回包含数字的响应"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        return client

    @pytest.fixture
    def evaluator(self, mock_llm_client):
        return FinanceEvaluator(client=mock_llm_client)

    def test_exact_match_returns_high_score(self, evaluator, mock_llm_client):
        """LLM输出与期望完全匹配时应高分"""
        mock_llm_client.chat.return_value = "营收为100万元"
        request = EvaluationSchema(
            id="fin_004",
            type="finance",
            payload={"text": "分析营收", "expected_output": "100万元"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score >= 0.8
        assert result.text == "营收为100万元"

    def test_different_number_returns_zero_score(self, evaluator, mock_llm_client):
        """不同数字应返回0分（score_numeric_match只支持精确匹配）"""
        mock_llm_client.chat.return_value = "营收约为95万元"
        request = EvaluationSchema(
            id="fin_005",
            type="finance",
            payload={"text": "分析营收", "expected_output": "100万元"},
        )
        result = evaluator.evaluate(request)
        # score_numeric_match只检查精确数字匹配
        # expected_nums=['100'], '100'不在"营收约为95万元"中
        assert result.score == 0.0

    def test_no_numbers_in_response_returns_zero_score(self, evaluator, mock_llm_client):
        """响应无数字时应0分"""
        mock_llm_client.chat.return_value = "公司经营良好，无具体数据"
        request = EvaluationSchema(
            id="fin_006",
            type="finance",
            payload={"text": "分析营收", "expected_output": "100万元"},
        )
        result = evaluator.evaluate(request)
        # 无数字匹配
        assert result.score == 0.0

    def test_multiple_numbers_all_match(self, evaluator, mock_llm_client):
        """多个数字全部匹配时应高分"""
        mock_llm_client.chat.return_value = "营收100万元，成本80万元，利润20万元"
        request = EvaluationSchema(
            id="fin_007",
            type="finance",
            payload={
                "text": "分析财务",
                "expected_output": "100万元 80万元 20万元",
            },
        )
        result = evaluator.evaluate(request)
        # 所有数字精确匹配
        assert result.score == 1.0

    def test_multiple_numbers_partial_exact_match(self, evaluator, mock_llm_client):
        """多个数字部分精确匹配"""
        mock_llm_client.chat.return_value = "营收100万元，成本50万元"
        request = EvaluationSchema(
            id="fin_008",
            type="finance",
            payload={
                "text": "分析财务",
                "expected_output": "100万元 80万元",  # 期望80但实际50
            },
        )
        result = evaluator.evaluate(request)
        # 1个匹配(100)，1个不匹配(期望80实际50)
        assert result.score == 0.5


class TestFinanceEvaluatorInputValidation:
    """输入验证测试"""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM客户端 - 必须配置return_value"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "营收100万元"  # 必须设置return_value
        return client

    @pytest.fixture
    def evaluator(self, mock_llm_client):
        return FinanceEvaluator(client=mock_llm_client)

    def test_empty_input_returns_error(self, evaluator):
        """空输入应返回错误"""
        request = EvaluationSchema(
            id="fin_008",
            type="finance",
            payload={"text": "", "expected_output": "100万元"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_missing_expected_output_handled(self, evaluator):
        """无expected_output时应正常处理"""
        request = EvaluationSchema(
            id="fin_009",
            type="finance",
            payload={"text": "分析财报"},
        )
        result = evaluator.evaluate(request)
        # 无expected_output时，score_numeric_match返回1.0
        assert result.is_valid is True
        assert result.score == 1.0


class TestFinanceEvaluatorMetadataHandling:
    """元数据处理测试
    
    关键发现：FinanceMetadata.target是字符串类型，不是整数
    """

    @pytest.fixture
    def mock_llm_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "营收100万元"
        return client

    @pytest.fixture
    def evaluator(self, mock_llm_client):
        return FinanceEvaluator(client=mock_llm_client)

    def test_metadata_rate_included_in_response(self, evaluator):
        """rate应在metadata中返回"""
        request = EvaluationSchema(
            id="fin_010",
            type="finance",
            payload={"text": "分析营收", "expected_output": "100万元"},
            metadata={"rate": 0.05, "target": "growth"},  # target是字符串
        )
        result = evaluator.evaluate(request)
        assert result.metadata["rate"] == 0.05
        assert result.metadata["target"] == "growth"

    def test_empty_metadata_handled(self, evaluator):
        """空metadata应正常处理"""
        request = EvaluationSchema(
            id="fin_011",
            type="finance",
            payload={"text": "分析营收", "expected_output": "100万元"},
            metadata={},
        )
        result = evaluator.evaluate(request)
        # metadata应包含默认值
        assert result.metadata is not None
        assert result.metadata["rate"] == 0.0  # 默认值
        assert result.metadata["target"] == "general"  # 默认值


class TestFinanceEvaluatorEdgeCases:
    """边界场景测试"""

    @pytest.fixture
    def mock_llm_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        return client

    @pytest.fixture
    def evaluator(self, mock_llm_client):
        return FinanceEvaluator(client=mock_llm_client)

    def test_llm_returns_empty_response(self, evaluator, mock_llm_client):
        """LLM返回空响应"""
        mock_llm_client.chat.return_value = ""
        request = EvaluationSchema(
            id="fin_012",
            type="finance",
            payload={"text": "分析营收", "expected_output": "100万元"},
        )
        result = evaluator.evaluate(request)
        # 空响应应被正确处理
        assert result.text == ""
        assert result.score == 0.0  # 空响应无数字匹配

    def test_llm_returns_very_long_response(self, evaluator, mock_llm_client):
        """LLM返回超长响应"""
        mock_llm_client.chat.return_value = "营收" + "100万元 " * 1000
        request = EvaluationSchema(
            id="fin_013",
            type="finance",
            payload={"text": "分析营收", "expected_output": "100万元"},
        )
        result = evaluator.evaluate(request)
        # 超长响应不应崩溃
        assert result.is_valid is True

    def test_llm_returns_special_characters(self, evaluator, mock_llm_client):
        """LLM返回特殊字符"""
        mock_llm_client.chat.return_value = "营收¥100万元，增长↑15%"
        request = EvaluationSchema(
            id="fin_014",
            type="finance",
            payload={"text": "分析营收", "expected_output": "100万元"},
        )
        result = evaluator.evaluate(request)
        # 特殊字符应被正确处理
        assert result.text is not None


class TestScoreNumericMatchIntegration:
    """score_numeric_match集成测试 - 验证评分算法
    
    关键发现：score_numeric_match只支持精确数字匹配
    - expected_nums = re.findall(r"-?\d+\.?\d*", expected)
    - matched = sum(1 for num in expected_nums if num in output)
    - 不支持部分匹配（如95和100）
    """

    def test_exact_match_score_1(self):
        """完全匹配分数为1"""
        score = score_numeric_match("营收100万元", "100万元")
        assert score == 1.0

    def test_different_number_score_0(self):
        """不同数字分数为0（精确匹配限制）"""
        score = score_numeric_match("营收95万元", "100万元")
        # '100'不在"营收95万元"中
        assert score == 0.0

    def test_no_numbers_in_output(self):
        """输出无数字"""
        score = score_numeric_match("公司经营良好", "100万元")
        assert score == 0.0

    def test_multiple_numbers_all_match(self):
        """多个数字全部匹配"""
        score = score_numeric_match("营收100万元 成本80万元", "100万元 80万元")
        assert score == 1.0

    def test_multiple_numbers_partial_match(self):
        """多个数字部分匹配"""
        score = score_numeric_match("营收100万元 成本50万元", "100万元 80万元")
        # 1个匹配(100)，1个不匹配(期望80实际50)
        assert score == 0.5

    def test_is_passing_threshold(self):
        """通过阈值验证"""
        assert is_passing(0.8) is True
        assert is_passing(0.79) is False
        assert is_passing(1.0) is True
        assert is_passing(0.0) is False

    def test_empty_output_returns_zero(self):
        """空输出返回0"""
        score = score_numeric_match("", "100万元")
        assert score == 0.0

    def test_empty_expected_returns_one(self):
        """空期望返回1"""
        score = score_numeric_match("营收100万元", "")
        assert score == 1.0