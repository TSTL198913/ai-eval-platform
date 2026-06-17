"""Function Calling 评估器测试"""

from unittest.mock import MagicMock

import pytest

from src.domain.evaluators.function_call_evaluator import FunctionCallEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestFunctionCallEvaluator:
    """Function Calling 评估器测试类"""

    def setup_method(self):
        """每个测试方法前的初始化"""
        self.mock_client = MagicMock()
        self.evaluator = FunctionCallEvaluator(self.mock_client)

    # ==================== 工具选择评估测试 ====================

    def test_tool_selection_exact_match(self):
        """测试工具选择完全匹配"""
        request = EvaluationSchema(
            id="test_001",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["search", "calculator"],
                "actual_tools": ["search", "calculator"],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert "correct_selections" in result.data["details"]
        assert set(result.data["details"]["correct_selections"]) == {"search", "calculator"}

    def test_tool_selection_partial_match(self):
        """测试工具选择部分匹配"""
        request = EvaluationSchema(
            id="test_002",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["search", "calculator", "weather"],
                "actual_tools": ["search", "calculator"],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert 0 < result.score < 1
        assert "missed_selections" in result.data["details"]
        assert "weather" in result.data["details"]["missed_selections"]

    def test_tool_selection_incorrect_selection(self):
        """测试工具选择包含错误选择"""
        request = EvaluationSchema(
            id="test_003",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["search"],
                "actual_tools": ["search", "calculator", "weather"],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert "incorrect_selections" in result.data["details"]
        assert set(result.data["details"]["incorrect_selections"]) == {"calculator", "weather"}

    def test_tool_selection_no_match(self):
        """测试工具选择完全不匹配"""
        request = EvaluationSchema(
            id="test_004",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["search", "calculator"],
                "actual_tools": ["weather", "translate"],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.0

    def test_tool_selection_empty_expected(self):
        """测试期望工具列表为空"""
        request = EvaluationSchema(
            id="test_005",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": [],
                "actual_tools": ["search"],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "expected_tools" in result.error

    def test_tool_selection_empty_actual(self):
        """测试实际工具列表为空"""
        request = EvaluationSchema(
            id="test_006",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["search"],
                "actual_tools": [],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.0

    # ==================== 参数验证评估测试 ====================

    def test_param_validation_exact_match(self):
        """测试参数验证完全匹配"""
        request = EvaluationSchema(
            id="test_007",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "search": {"query": "AI技术", "limit": 10},
                },
                "actual_params": {
                    "search": {"query": "AI技术", "limit": 10},
                },
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_param_validation_partial_match(self):
        """测试参数验证部分匹配"""
        request = EvaluationSchema(
            id="test_008",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "search": {"query": "AI技术", "limit": 10},
                },
                "actual_params": {
                    "search": {"query": "AI技术", "limit": 5},
                },
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert 0 < result.score < 1

    def test_param_validation_missing_param(self):
        """测试参数验证缺少参数"""
        request = EvaluationSchema(
            id="test_009",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "search": {"query": "AI技术", "limit": 10},
                },
                "actual_params": {
                    "search": {"query": "AI技术"},
                },
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score < 1.0

    def test_param_validation_missing_tool(self):
        """测试参数验证缺少工具"""
        request = EvaluationSchema(
            id="test_010",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "search": {"query": "AI技术"},
                },
                "actual_params": {},
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score < 1.0

    def test_param_validation_empty_expected(self):
        """测试期望参数为空"""
        request = EvaluationSchema(
            id="test_011",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {},
                "actual_params": {"search": {"query": "test"}},
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_param_validation_with_tool_definition(self):
        """测试带工具定义的参数验证"""
        request = EvaluationSchema(
            id="test_012",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "calculator": {"expression": "2+2"},
                },
                "actual_params": {
                    "calculator": {"expression": "3+3"},
                },
                "tool_definitions": [
                    {
                        "name": "calculator",
                        "parameters": {
                            "properties": {
                                "expression": {"type": "string"},
                            },
                        },
                    },
                ],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        # 类型正确但值不正确，应该给部分分数
        assert result.score > 0

    def test_param_validation_type_check_string(self):
        """测试字符串类型参数验证"""
        request = EvaluationSchema(
            id="test_013",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "search": {"query": "test"},
                },
                "actual_params": {
                    "search": {"query": 123},
                },
                "tool_definitions": [
                    {
                        "name": "search",
                        "parameters": {
                            "properties": {
                                "query": {"type": "string"},
                            },
                        },
                    },
                ],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True

    def test_param_validation_type_check_integer(self):
        """测试整数类型参数验证"""
        request = EvaluationSchema(
            id="test_014",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "search": {"limit": 10},
                },
                "actual_params": {
                    "search": {"limit": "10"},
                },
                "tool_definitions": [
                    {
                        "name": "search",
                        "parameters": {
                            "properties": {
                                "limit": {"type": "integer"},
                            },
                        },
                    },
                ],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True

    def test_param_validation_nested_dict(self):
        """测试嵌套字典参数验证"""
        request = EvaluationSchema(
            id="test_015",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "api": {"config": {"timeout": 30, "retries": 3}},
                },
                "actual_params": {
                    "api": {"config": {"timeout": 30, "retries": 3}},
                },
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_param_validation_list(self):
        """测试列表参数验证"""
        request = EvaluationSchema(
            id="test_016",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "search": {"tags": ["ai", "ml"]},
                },
                "actual_params": {
                    "search": {"tags": ["ai", "ml"]},
                },
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    # ==================== 结果验证评估测试 ====================

    def test_result_validation_exact_match(self):
        """测试结果验证完全匹配"""
        request = EvaluationSchema(
            id="test_017",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {
                    "calculator": {"result": 4},
                },
                "actual_results": {
                    "calculator": {"result": 4},
                },
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_result_validation_partial_match(self):
        """测试结果验证部分匹配"""
        request = EvaluationSchema(
            id="test_018",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {
                    "search": {"results": ["doc1", "doc2", "doc3"]},
                },
                "actual_results": {
                    "search": {"results": ["doc1", "doc2"]},
                },
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert 0 < result.score < 1

    def test_result_validation_missing_result(self):
        """测试结果验证缺少结果"""
        request = EvaluationSchema(
            id="test_019",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {
                    "search": {"results": ["doc1"]},
                },
                "actual_results": {},
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score < 1.0

    def test_result_validation_empty_expected(self):
        """测试期望结果为空"""
        request = EvaluationSchema(
            id="test_020",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {},
                "actual_results": {"search": {"results": ["doc1"]}},
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_result_validation_string_similarity(self):
        """测试字符串相似度计算"""
        request = EvaluationSchema(
            id="test_021",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {
                    "translate": {"text": "Hello World"},
                },
                "actual_results": {
                    "translate": {"text": "Hello Word"},
                },
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        # 相似度应该很高但不是1
        assert 0.8 < result.score < 1.0

    def test_result_validation_number_similarity(self):
        """测试数值相似度计算"""
        request = EvaluationSchema(
            id="test_022",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {
                    "calculator": {"result": 100},
                },
                "actual_results": {
                    "calculator": {"result": 95},
                },
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        # 95/100 = 0.95 相似度
        assert 0.9 < result.score < 1.0

    # ==================== 完整评估测试 ====================

    def test_full_evaluate_success(self):
        """测试完整评估成功"""
        request = EvaluationSchema(
            id="test_023",
            type="function_call",
            payload={
                "expected_tools": ["search", "calculator"],
                "actual_tools": ["search", "calculator"],
                "expected_params": {
                    "search": {"query": "AI"},
                    "calculator": {"expression": "2+2"},
                },
                "actual_params": {
                    "search": {"query": "AI"},
                    "calculator": {"expression": "2+2"},
                },
                "expected_results": {
                    "search": {"count": 10},
                    "calculator": {"result": 4},
                },
                "actual_results": {
                    "search": {"count": 10},
                    "calculator": {"result": 4},
                },
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert "tool_selection" in result.data
        assert "param_validation" in result.data
        assert "result_validation" in result.data

    def test_full_evaluate_partial(self):
        """测试完整评估部分成功"""
        request = EvaluationSchema(
            id="test_024",
            type="function_call",
            payload={
                "expected_tools": ["search", "calculator"],
                "actual_tools": ["search"],
                "expected_params": {
                    "search": {"query": "AI", "limit": 10},
                },
                "actual_params": {
                    "search": {"query": "AI", "limit": 5},
                },
                "expected_results": {
                    "search": {"count": 100},
                },
                "actual_results": {
                    "search": {"count": 50},
                },
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert 0 < result.score < 1

    def test_full_evaluate_empty_expected_tools(self):
        """测试完整评估缺少期望工具"""
        request = EvaluationSchema(
            id="test_025",
            type="function_call",
            payload={
                "expected_tools": [],
                "actual_tools": ["search"],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "expected_tools" in result.error

    # ==================== 辅助方法测试 ====================

    def test_compare_values_strings(self):
        """测试字符串值比较"""
        # 完全匹配
        assert self.evaluator._compare_values("hello", "hello") is True
        # 忽略大小写
        assert self.evaluator._compare_values("Hello", "hello") is True
        # 忽略首尾空格
        assert self.evaluator._compare_values(" hello ", "hello") is True
        # 不匹配
        assert self.evaluator._compare_values("hello", "world") is False

    def test_compare_values_dicts(self):
        """测试字典值比较"""
        # 完全匹配
        assert self.evaluator._compare_values({"a": 1}, {"a": 1}) is True
        # 嵌套字典
        assert self.evaluator._compare_values(
            {"a": {"b": 1}}, {"a": {"b": 1}}
        ) is True
        # 键不同
        assert self.evaluator._compare_values({"a": 1}, {"b": 1}) is False
        # 值不同
        assert self.evaluator._compare_values({"a": 1}, {"a": 2}) is False

    def test_compare_values_lists(self):
        """测试列表值比较"""
        # 完全匹配
        assert self.evaluator._compare_values([1, 2, 3], [1, 2, 3]) is True
        # 长度不同
        assert self.evaluator._compare_values([1, 2], [1, 2, 3]) is False
        # 顺序不同
        assert self.evaluator._compare_values([1, 2], [2, 1]) is False

    def test_compare_values_numbers(self):
        """测试数值比较"""
        assert self.evaluator._compare_values(1, 1) is True
        assert self.evaluator._compare_values(1.0, 1) is True
        assert self.evaluator._compare_values(1, 2) is False

    def test_calculate_similarity_strings(self):
        """测试字符串相似度计算"""
        # 完全相同
        assert self.evaluator._calculate_similarity("hello", "hello") == 1.0
        # 完全不同
        assert self.evaluator._calculate_similarity("abc", "xyz") < 0.5
        # 部分相同
        sim = self.evaluator._calculate_similarity("hello", "hallo")
        assert 0.5 < sim < 1.0

    def test_calculate_similarity_dicts(self):
        """测试字典相似度计算"""
        # 完全相同
        assert self.evaluator._calculate_similarity({"a": 1}, {"a": 1}) == 1.0
        # 部分相同
        sim = self.evaluator._calculate_similarity({"a": 1, "b": 2}, {"a": 1, "b": 3})
        assert 0.5 <= sim < 1.0

    def test_calculate_similarity_lists(self):
        """测试列表相似度计算"""
        # 完全相同
        assert self.evaluator._calculate_similarity([1, 2, 3], [1, 2, 3]) == 1.0
        # 部分相同
        sim = self.evaluator._calculate_similarity([1, 2, 3], [1, 2, 4])
        assert 0 < sim < 1.0

    def test_calculate_similarity_numbers(self):
        """测试数值相似度计算"""
        # 完全相同
        assert self.evaluator._calculate_similarity(100, 100) == 1.0
        # 接近
        sim = self.evaluator._calculate_similarity(100, 90)
        assert 0.8 < sim < 1.0
        # 零值处理
        assert self.evaluator._calculate_similarity(0, 0) == 1.0

    def test_string_similarity_empty(self):
        """测试空字符串相似度"""
        assert self.evaluator._string_similarity("", "") == 1.0
        assert self.evaluator._string_similarity("", "a") == 0.0
        assert self.evaluator._string_similarity("a", "") == 0.0

    def test_dict_similarity_empty(self):
        """测试空字典相似度"""
        assert self.evaluator._dict_similarity({}, {}) == 1.0

    def test_list_similarity_empty(self):
        """测试空列表相似度"""
        assert self.evaluator._list_similarity([], []) == 1.0
        assert self.evaluator._list_similarity([], [1]) == 0.0

    def test_longest_common_subsequence(self):
        """测试最长公共子序列"""
        assert self.evaluator._longest_common_subsequence_length([1, 2, 3], [1, 2, 3]) == 3
        assert self.evaluator._longest_common_subsequence_length([1, 2, 3], [1, 3]) == 2
        assert self.evaluator._longest_common_subsequence_length([1, 2], [3, 4]) == 0

    # ==================== 类型验证测试 ====================

    def test_validate_param_type_string(self):
        """测试字符串类型验证"""
        schema = {"type": "string"}
        assert self.evaluator._validate_param_type("hello", schema) is True
        assert self.evaluator._validate_param_type(123, schema) is False

    def test_validate_param_type_integer(self):
        """测试整数类型验证"""
        schema = {"type": "integer"}
        assert self.evaluator._validate_param_type(123, schema) is True
        assert self.evaluator._validate_param_type(123.5, schema) is False
        assert self.evaluator._validate_param_type("123", schema) is False
        assert self.evaluator._validate_param_type(True, schema) is False

    def test_validate_param_type_number(self):
        """测试数值类型验证"""
        schema = {"type": "number"}
        assert self.evaluator._validate_param_type(123, schema) is True
        assert self.evaluator._validate_param_type(123.5, schema) is True
        assert self.evaluator._validate_param_type("123", schema) is False

    def test_validate_param_type_boolean(self):
        """测试布尔类型验证"""
        schema = {"type": "boolean"}
        assert self.evaluator._validate_param_type(True, schema) is True
        assert self.evaluator._validate_param_type(False, schema) is True
        assert self.evaluator._validate_param_type(1, schema) is False
        assert self.evaluator._validate_param_type("true", schema) is False

    def test_validate_param_type_array(self):
        """测试数组类型验证"""
        schema = {"type": "array"}
        assert self.evaluator._validate_param_type([1, 2, 3], schema) is True
        assert self.evaluator._validate_param_type((1, 2), schema) is False
        assert self.evaluator._validate_param_type("array", schema) is False

    def test_validate_param_type_object(self):
        """测试对象类型验证"""
        schema = {"type": "object"}
        assert self.evaluator._validate_param_type({"a": 1}, schema) is True
        assert self.evaluator._validate_param_type([1, 2], schema) is False

    def test_validate_param_type_null(self):
        """测试null类型验证"""
        schema = {"type": "null"}
        assert self.evaluator._validate_param_type(None, schema) is True
        assert self.evaluator._validate_param_type(0, schema) is False

    def test_validate_param_type_unknown(self):
        """测试未知类型验证"""
        schema = {"type": "unknown"}
        assert self.evaluator._validate_param_type("anything", schema) is True

    # ==================== 工具定义查找测试 ====================

    def test_find_tool_definition(self):
        """测试查找工具定义"""
        definitions = [
            {"name": "search", "parameters": {}},
            {"name": "calculator", "parameters": {}},
        ]

        result = self.evaluator._find_tool_definition("search", definitions)
        assert result is not None
        assert result["name"] == "search"

        result = self.evaluator._find_tool_definition("unknown", definitions)
        assert result is None

    def test_get_param_schema(self):
        """测试获取参数 schema"""
        tool_def = {
            "name": "search",
            "parameters": {
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        }

        result = self.evaluator._get_param_schema("query", tool_def)
        assert result is not None
        assert result["type"] == "string"

        result = self.evaluator._get_param_schema("unknown", tool_def)
        assert result is None

    # ==================== 边界情况测试 ====================

    def test_evaluate_without_client(self):
        """测试无客户端评估"""
        evaluator = FunctionCallEvaluator(None)
        request = EvaluationSchema(
            id="test_026",
            type="function_call",
            payload={
                "expected_tools": ["search"],
                "actual_tools": ["search"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_multiple_tools_param_validation(self):
        """测试多工具参数验证"""
        request = EvaluationSchema(
            id="test_027",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "search": {"query": "AI"},
                    "calculator": {"expression": "2+2"},
                    "translate": {"text": "hello"},
                },
                "actual_params": {
                    "search": {"query": "AI"},
                    "calculator": {"expression": "3+3"},
                    "translate": {"text": "world"},
                },
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert "per_tool_scores" in result.data["details"]

    def test_complex_nested_params(self):
        """测试复杂嵌套参数"""
        request = EvaluationSchema(
            id="test_028",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "api": {
                        "config": {
                            "nested": {
                                "deep": {"value": 42},
                            },
                        },
                    },
                },
                "actual_params": {
                    "api": {
                        "config": {
                            "nested": {
                                "deep": {"value": 42},
                            },
                        },
                    },
                },
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_result_validation_dict_similarity(self):
        """测试结果验证字典相似度"""
        request = EvaluationSchema(
            id="test_029",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {
                    "api": {
                        "data": {"users": [{"id": 1}, {"id": 2}]},
                    },
                },
                "actual_results": {
                    "api": {
                        "data": {"users": [{"id": 1}]},
                    },
                },
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert 0 < result.score < 1

    def test_result_validation_list_similarity(self):
        """测试结果验证列表相似度"""
        request = EvaluationSchema(
            id="test_030",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {
                    "search": ["result1", "result2", "result3"],
                },
                "actual_results": {
                    "search": ["result1", "result2"],
                },
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert 0 < result.score < 1

    def test_tool_selection_precision_recall(self):
        """测试工具选择的精确率和召回率"""
        request = EvaluationSchema(
            id="test_031",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["search", "calculator", "weather"],
                "actual_tools": ["search", "calculator", "translate"],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        details = result.data["details"]
        assert "precision" in details
        assert "recall" in details
        assert "f1_score" in details
        # 精确率 = 2/3 (search, calculator 正确，translate 错误)
        assert details["precision"] == 2 / 3
        # 召回率 = 2/3 (search, calculator 正确，weather 漏选)
        assert details["recall"] == 2 / 3

    def test_calculate_similarity_different_types(self):
        """测试不同类型值的相似度"""
        # 字符串和数字
        assert self.evaluator._calculate_similarity("hello", 123) == 0.0
        # None 和其他
        assert self.evaluator._calculate_similarity(None, "test") == 0.0

    def test_compare_values_case_insensitive(self):
        """测试大小写不敏感比较"""
        assert self.evaluator._compare_values("Hello World", "hello world") is True
        assert self.evaluator._compare_values("HELLO", "hello") is True

    def test_compare_values_with_whitespace(self):
        """测试带空格的字符串比较"""
        assert self.evaluator._compare_values("  hello  ", "hello") is True
        assert self.evaluator._compare_values("\thello\n", "hello") is True

    def test_validate_tool_params_empty_expected(self):
        """测试空期望参数的工具参数验证"""
        score, details = self.evaluator._validate_tool_params({}, {"query": "test"}, None)
        assert score == 1.0
        assert details["message"] == "无参数"

    def test_validate_tool_params_missing_param(self):
        """测试缺少参数的工具参数验证"""
        score, details = self.evaluator._validate_tool_params(
            {"query": "test", "limit": 10},
            {"query": "test"},
            None,
        )
        assert score < 1.0
        assert "limit" in details
        assert details["limit"]["status"] == "missing"

    def test_validate_tool_params_with_type_validation(self):
        """测试带类型验证的工具参数验证"""
        tool_def = {
            "name": "search",
            "parameters": {
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        }

        # 类型正确但值不同
        score, details = self.evaluator._validate_tool_params(
            {"query": "test"},
            {"query": "other"},
            tool_def,
        )
        # 类型正确应该给部分分数
        assert score > 0

    def test_full_evaluate_with_tool_definitions(self):
        """测试带工具定义的完整评估"""
        request = EvaluationSchema(
            id="test_032",
            type="function_call",
            payload={
                "expected_tools": ["search"],
                "actual_tools": ["search"],
                "expected_params": {
                    "search": {"query": "AI", "limit": 10},
                },
                "actual_params": {
                    "search": {"query": "AI", "limit": 5},
                },
                "expected_results": {},
                "actual_results": {},
                "tool_definitions": [
                    {
                        "name": "search",
                        "parameters": {
                            "properties": {
                                "query": {"type": "string"},
                                "limit": {"type": "integer"},
                            },
                        },
                    },
                ],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True

    def test_evaluate_tool_selection_with_penalty(self):
        """测试带惩罚的工具选择评估"""
        # 多个错误选择应该有惩罚
        request = EvaluationSchema(
            id="test_033",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["search"],
                "actual_tools": ["search", "tool1", "tool2", "tool3", "tool4"],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        # 4个错误选择，惩罚0.4
        assert result.data["details"]["penalty"] == 0.4

    def test_evaluate_tool_selection_empty_expected_direct(self):
        """测试直接调用_evaluate_tool_selection时期望为空"""
        score, details = self.evaluator._evaluate_tool_selection([], ["search"])
        assert score == 0.0
        assert "error" in details

    def test_calculate_similarity_zero_expected(self):
        """测试期望值为0时的数值相似度计算"""
        # 期望值为0，实际值也为0
        assert self.evaluator._calculate_similarity(0, 0) == 1.0
        # 期望值为0，实际值不为0
        assert self.evaluator._calculate_similarity(0, 5) == 0.0

    def test_dict_similarity_missing_keys(self):
        """测试字典中键只存在于一个字典的情况"""
        # 键只存在于第一个字典
        sim = self.evaluator._dict_similarity({"a": 1, "b": 2}, {"a": 1})
        assert 0 < sim < 1.0
        # 键只存在于第二个字典
        sim = self.evaluator._dict_similarity({"a": 1}, {"a": 1, "c": 3})
        assert 0 < sim < 1.0