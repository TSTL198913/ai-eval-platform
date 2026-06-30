"""
FunctionCallEvaluator 专项测试
测试目标：验证 FunctionCallEvaluator 的工具选择、参数验证、结果验证功能
关键发现：（测试过程中记录）
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.function_call_evaluator import FunctionCallEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestFunctionCallEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def target(self):
        return FunctionCallEvaluator()

    def test_full_evaluate_correct_tools_and_params_high_score(self, target):
        """正确工具选择+正确参数应得高分"""
        request = EvaluationSchema(
            id="fc_001",
            type="function_call",
            payload={
                "action": "evaluate",
                "expected_tools": ["weather", "news"],
                "actual_tools": ["weather", "news"],
                "expected_params": {"weather": {"city": "北京"}, "news": {"topic": "科技"}},
                "actual_params": {"weather": {"city": "北京"}, "news": {"topic": "科技"}},
                "expected_results": {"weather": {"temp": 25}, "news": {"count": 10}},
                "actual_results": {"weather": {"temp": 25}, "news": {"count": 10}},
            },
        )
        result = target.evaluate(request)

        # 强断言：验证业务逻辑 - 完美匹配应为满分
        assert result.is_valid is True
        assert result.score == 1.0, f"正确评估应得满分，实际得分: {result.score}"
        assert result.data["tool_selection"]["score"] == 1.0, "工具完全正确应为满分"
        assert result.data["param_validation"]["score"] == 1.0, "参数完全正确应为满分"
        assert result.data["result_validation"]["score"] == 1.0, "结果完全正确应为满分"

    def test_compare_tools_perfect_match(self, target):
        """工具完全匹配应得满分"""
        request = EvaluationSchema(
            id="fc_002",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["search", "translate"],
                "actual_tools": ["search", "translate"],
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0, "工具完全匹配应为满分"
        assert len(result.data["details"]["correct_selections"]) == 2

    def test_validate_params_all_correct(self, target):
        """参数全部正确应得满分"""
        request = EvaluationSchema(
            id="fc_003",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {"calculator": {"a": 10, "b": 5, "op": "add"}},
                "actual_params": {"calculator": {"a": 10, "b": 5, "op": "add"}},
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_validate_result_perfect_match(self, target):
        """结果完全匹配应得满分"""
        request = EvaluationSchema(
            id="fc_004",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {"search": {"results": ["a", "b"]}},
                "actual_results": {"search": {"results": ["a", "b"]}},
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_overall_score_calculation_with_weight(self, target):
        """综合评分应按权重计算: tool(0.4) + param(0.35) + result(0.25)"""
        request = EvaluationSchema(
            id="fc_005",
            type="function_call",
            payload={
                "action": "evaluate",
                "expected_tools": ["test_tool"],
                "actual_tools": ["test_tool"],
                "expected_params": {},
                "actual_params": {},
                "expected_results": {},
                "actual_results": {},
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        expected_score = 1.0 * 0.4 + 1.0 * 0.35 + 1.0 * 0.25
        assert abs(result.score - expected_score) < 0.01


class TestFunctionCallEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def target(self):
        return FunctionCallEvaluator()

    def test_evaluate_empty_expected_tools_with_actual_returns_zero_tool_score(self, target):
        """expected_tools为空但actual_tools不为空时工具选择得分为0"""
        request = EvaluationSchema(
            id="fc_n001",
            type="function_call",
            payload={
                "action": "evaluate",
                "expected_tools": [],
                "actual_tools": ["weather"],
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["tool_selection"]["score"] == 0.0

    def test_compare_tools_empty_expected_with_actual_returns_zero(self, target):
        """compare_tools时expected_tools为空但actual_tools不为空应返回0分"""
        request = EvaluationSchema(
            id="fc_n002",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": [],
                "actual_tools": ["weather"],
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.0

    def test_wrong_tool_selection_reduces_score(self, target):
        """错误工具选择应降低分数"""
        request = EvaluationSchema(
            id="fc_n003",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["weather"],
                "actual_tools": ["search"],  # 错误选择
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score < 1.0, "错误选择应有惩罚"
        assert "weather" in result.data["details"]["missed_selections"]
        assert "search" in result.data["details"]["incorrect_selections"]

    def test_partial_tool_match_reduces_score(self, target):
        """部分工具匹配应降低分数"""
        request = EvaluationSchema(
            id="fc_n004",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["weather", "news", "search"],
                "actual_tools": ["weather", "news"],  # 漏选一个
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        # precision=1.0, recall=2/3, f1约0.67, 再扣penalty
        assert result.score < 1.0, "部分匹配应有惩罚"

    def test_wrong_params_reduces_score(self, target):
        """错误参数应降低分数"""
        request = EvaluationSchema(
            id="fc_n005",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {"weather": {"city": "北京"}},
                "actual_params": {"weather": {"city": "上海"}},  # 错误值
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score < 1.0, "错误参数应有惩罚"

    def test_missing_param_reduces_score(self, target):
        """缺失参数应降低分数"""
        request = EvaluationSchema(
            id="fc_n006",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {"weather": {"city": "北京", "days": 3}},
                "actual_params": {"weather": {"city": "北京"}},  # 缺失days
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score < 1.0, "缺失参数应有惩罚"

    def test_wrong_result_reduces_score(self, target):
        """错误结果应降低分数"""
        request = EvaluationSchema(
            id="fc_n007",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {"search": {"count": 10}},
                "actual_results": {"search": {"count": 5}},  # 错误值
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score < 1.0, "错误结果应有惩罚"


class TestFunctionCallEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def target(self):
        return FunctionCallEvaluator()

    def test_empty_actual_tools_with_expected(self, target):
        """expected有值但actual为空应有惩罚"""
        request = EvaluationSchema(
            id="fc_b001",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["weather"],
                "actual_tools": [],
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.0, "完全未选择工具应得0分"

    def test_no_params_expected_and_provided(self, target):
        """无参数验证时应有默认满分"""
        request = EvaluationSchema(
            id="fc_b002",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {},
                "actual_params": {},
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0, "无参数时应得满分"

    def test_no_results_expected_and_provided(self, target):
        """无结果验证时应有默认满分"""
        request = EvaluationSchema(
            id="fc_b003",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {},
                "actual_results": {},
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0, "无结果时应得满分"

    def test_many_incorrect_tools_penalty_limit(self, target):
        """多个错误工具选择应有惩罚上限"""
        request = EvaluationSchema(
            id="fc_b004",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["weather"],
                "actual_tools": ["search", "news", "translate", "calculator"],  # 多个错误
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        # penalty = 4 * 0.1 = 0.4, f1=0, 最终score = max(0, 0-0.4) = 0
        assert result.score == 0.0, "错误过多应扣到0分"

    def test_similar_string_params_partial_score(self, target):
        """相似字符串参数应得部分分"""
        request = EvaluationSchema(
            id="fc_b005",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {"greet": {"name": "张三"}},
                "actual_params": {"greet": {"name": "李四"}},
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        # 字符串不匹配，且不是完全相同
        assert result.score < 1.0


class TestFunctionCallEvaluatorAlgorithmTests:
    """评分算法测试"""

    @pytest.fixture
    def target(self):
        return FunctionCallEvaluator()

    def test_tool_selection_precision_calculation(self, target):
        """工具选择精确率计算"""
        score, details = target._evaluate_tool_selection(["tool_a", "tool_b"], ["tool_a", "tool_c"])
        # correct = {tool_a}, actual = {tool_a, tool_c}
        # precision = 1/2 = 0.5, recall = 1/2 = 0.5, f1 = 0.5
        # penalty = 1 * 0.1 = 0.1, final = 0.5 - 0.1 = 0.4
        assert details["precision"] == 0.5
        assert details["recall"] == 0.5

    def test_tool_selection_recall_calculation(self, target):
        """工具选择召回率计算"""
        score, details = target._evaluate_tool_selection(
            ["tool_a", "tool_b", "tool_c"], ["tool_a", "tool_b"]
        )
        # correct = {tool_a, tool_b}, expected = {tool_a, tool_b, tool_c}
        # precision = 2/2 = 1.0, recall = 2/3 ≈ 0.67
        assert abs(details["recall"] - 2 / 3) < 0.001

    def test_tool_selection_f1_score_calculation(self, target):
        """工具选择F1分数计算"""
        score, details = target._evaluate_tool_selection(["tool_a", "tool_b"], ["tool_a", "tool_b"])
        # precision = 1.0, recall = 1.0, f1 = 1.0
        assert details["f1_score"] == 1.0

    def test_tool_selection_penalty_for_incorrect(self, target):
        """错误选择应有惩罚"""
        score, details = target._evaluate_tool_selection(["tool_a"], ["tool_a", "tool_b"])
        # penalty = min(0.3, len(incorrect)/total) = min(0.3, 1/1) = 0.3
        assert details["penalty"] == 0.3
        assert abs(score - (details["f1_score"] - 0.3)) < 0.001

    def test_compare_values_exact_match(self, target):
        """精确值比较"""
        assert target._compare_values("hello", "hello") is True
        assert target._compare_values(123, 123) is True
        assert target._compare_values({"a": 1}, {"a": 1}) is True

    def test_compare_values_dict_partial_match(self, target):
        """字典部分匹配"""
        assert target._compare_values({"a": 1, "b": 2}, {"a": 1}) is False

    def test_compare_values_list_order_matters(self, target):
        """列表比较需考虑顺序"""
        assert target._compare_values([1, 2], [1, 2]) is True
        assert target._compare_values([1, 2], [2, 1]) is False

    def test_compare_values_string_ignore_case(self, target):
        """字符串比较忽略大小写"""
        assert target._compare_values("Hello", "hello") is True
        assert target._compare_values("Hello ", "hello") is True

    def test_calculate_similarity_identical(self, target):
        """完全相同的值相似度为1.0"""
        assert target._calculate_similarity("test", "test") == 1.0
        assert target._calculate_similarity(100, 100) == 1.0

    def test_calculate_similarity_completely_different(self, target):
        """完全不同的值相似度为0.0"""
        assert target._calculate_similarity("abc", "xyz") == 0.0

    def test_calculate_similarity_string_similar(self, target):
        """相似字符串应有中间相似度"""
        similarity = target._calculate_similarity("hello", "hallo")
        assert 0.0 < similarity < 1.0

    def test_calculate_similarity_dict_overlap(self, target):
        """字典相似度按key交集计算"""
        similarity = target._calculate_similarity({"a": 1, "b": 2}, {"a": 1, "c": 3})
        # key 'a' 相似度1.0, key 'b'和'c'一个缺失计0
        # 应该是 (1.0 + 0 + 0) / 3 = 0.333
        assert 0.2 < similarity < 0.4

    def test_calculate_similarity_list_overlap(self, target):
        """列表相似度按LCS计算"""
        similarity = target._calculate_similarity([1, 2, 3], [1, 2, 4])
        # LCS = [1, 2], len=2, max_len=3, similarity = 2/3
        assert abs(similarity - 2 / 3) < 0.01

    def test_calculate_similarity_numeric_close(self, target):
        """数值相近应有高相似度"""
        similarity = target._calculate_similarity(100, 105)
        # |100-105| / |100| = 0.05, 1-0.05 = 0.95
        assert similarity == 0.95

    def test_calculate_similarity_numeric_zero_denominator(self, target):
        """除数为0时应正确处理"""
        similarity = target._calculate_similarity(0, 0)
        assert similarity == 1.0

    def test_string_similarity_calculation(self, target):
        """字符串相似度计算（Levenshtein距离）"""
        similarity = target._string_similarity("kitten", "sitting")
        # kitten -> sitten (1), sitten -> sittin (1), sittin -> sitting (1), distance=3
        # max_len=7, similarity = 1 - 3/7 ≈ 0.57
        assert 0.5 < similarity < 0.7

    def test_longest_common_subsequence_length(self, target):
        """最长公共子序列长度计算"""
        lcs_len = target._longest_common_subsequence_length([1, 2, 3], [1, 3, 5])
        assert lcs_len == 2  # [1,3] 或 [1,5]等

    def test_validate_param_type_string(self, target):
        """参数类型验证-字符串"""
        assert target._validate_param_type("hello", {"type": "string"}) is True
        assert target._validate_param_type(123, {"type": "string"}) is False

    def test_validate_param_type_number(self, target):
        """参数类型验证-数字"""
        assert target._validate_param_type(123, {"type": "number"}) is True
        assert target._validate_param_type(1.5, {"type": "number"}) is True
        assert target._validate_param_type("123", {"type": "number"}) is False

    def test_validate_param_type_integer(self, target):
        """参数类型验证-整数"""
        assert target._validate_param_type(123, {"type": "integer"}) is True
        assert target._validate_param_type(1.5, {"type": "integer"}) is False

    def test_validate_param_type_boolean(self, target):
        """参数类型验证-布尔"""
        assert target._validate_param_type(True, {"type": "boolean"}) is True
        assert target._validate_param_type(False, {"type": "boolean"}) is True
        assert target._validate_param_type("true", {"type": "boolean"}) is False

    def test_validate_param_type_array(self, target):
        """参数类型验证-数组"""
        assert target._validate_param_type([1, 2], {"type": "array"}) is True
        assert target._validate_param_type("array", {"type": "array"}) is False

    def test_validate_param_type_object(self, target):
        """参数类型验证-对象"""
        assert target._validate_param_type({"a": 1}, {"type": "object"}) is True
        assert target._validate_param_type("object", {"type": "object"}) is False

    def test_find_tool_definition_found(self, target):
        """查找工具定义-找到"""
        definitions = [{"name": "weather", "desc": "天气查询"}]
        found = target._find_tool_definition("weather", definitions)
        assert found is not None
        assert found["name"] == "weather"

    def test_find_tool_definition_not_found(self, target):
        """查找工具定义-未找到"""
        definitions = [{"name": "weather", "desc": "天气查询"}]
        found = target._find_tool_definition("search", definitions)
        assert found is None

    def test_get_param_schema_found(self, target):
        """获取参数schema-找到"""
        tool_def = {
            "name": "weather",
            "parameters": {"properties": {"city": {"type": "string"}, "days": {"type": "integer"}}},
        }
        schema = target._get_param_schema("city", tool_def)
        assert schema is not None
        assert schema["type"] == "string"

    def test_get_param_schema_not_found(self, target):
        """获取参数schema-未找到"""
        tool_def = {"name": "weather", "parameters": {"properties": {}}}
        schema = target._get_param_schema("city", tool_def)
        assert schema is None
