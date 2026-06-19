"""
FunctionCallEvaluator 专项测试
测试目标：验证工具调用评估器的功能完整性和正确性
关键发现：
1. 评估器支持四种评估模式：完整评估、工具选择对比、参数验证、结果验证
2. 综合评分权重：工具选择(40%) + 参数验证(35%) + 结果验证(25%)
3. 参数验证支持类型检查，类型正确但值错误可获50%分数
4. 相似度计算支持字符串(Levenshtein)、字典、列表(LCS)、数值
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.function_call_evaluator import FunctionCallEvaluator
from src.schemas.evaluation import DomainResponse, EvaluationSchema


class TestFunctionCallEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def evaluator(self):
        """创建评估器实例"""
        return FunctionCallEvaluator()

    @pytest.fixture
    def tool_definitions(self):
        """工具定义fixture"""
        return [
            {
                "name": "get_weather",
                "parameters": {
                    "properties": {
                        "city": {"type": "string"},
                        "unit": {"type": "string"},
                    }
                },
            },
            {
                "name": "send_email",
                "parameters": {
                    "properties": {
                        "to": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                    }
                },
            },
        ]

    def test_full_evaluate_all_correct(self, evaluator, tool_definitions):
        """完整评估：所有工具正确选择、参数正确、结果正确"""
        request = EvaluationSchema(
            id="test_001",
            type="function_call",
            payload={
                "expected_tools": ["get_weather", "send_email"],
                "actual_tools": ["get_weather", "send_email"],
                "expected_params": {
                    "get_weather": {"city": "Beijing", "unit": "celsius"},
                    "send_email": {"to": "user@example.com", "subject": "Test", "body": "Hello"},
                },
                "actual_params": {
                    "get_weather": {"city": "Beijing", "unit": "celsius"},
                    "send_email": {"to": "user@example.com", "subject": "Test", "body": "Hello"},
                },
                "expected_results": {
                    "get_weather": {"temperature": 25, "condition": "sunny"},
                    "send_email": {"status": "sent"},
                },
                "actual_results": {
                    "get_weather": {"temperature": 25, "condition": "sunny"},
                    "send_email": {"status": "sent"},
                },
                "tool_definitions": tool_definitions,
            },
        )

        result = evaluator.evaluate(request)

        # 强断言：验证业务逻辑
        assert result.is_valid is True
        assert result.score >= 0.95  # 应该接近满分
        assert result.data["tool_selection"]["score"] == 1.0
        assert result.data["param_validation"]["score"] == 1.0
        assert result.data["result_validation"]["score"] == 1.0
        assert "get_weather" in result.data["tool_selection"]["details"]["correct_selections"]
        assert "send_email" in result.data["tool_selection"]["details"]["correct_selections"]

    def test_compare_tools_exact_match(self, evaluator):
        """工具选择对比：精确匹配"""
        request = EvaluationSchema(
            id="test_002",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["tool_a", "tool_b", "tool_c"],
                "actual_tools": ["tool_a", "tool_b", "tool_c"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert result.data["details"]["precision"] == 1.0
        assert result.data["details"]["recall"] == 1.0
        assert result.data["details"]["f1_score"] == 1.0
        assert len(result.data["details"]["correct_selections"]) == 3
        assert len(result.data["details"]["incorrect_selections"]) == 0
        assert len(result.data["details"]["missed_selections"]) == 0

    def test_validate_params_all_match(self, evaluator, tool_definitions):
        """参数验证：参数完全匹配"""
        request = EvaluationSchema(
            id="test_003",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "get_weather": {"city": "Shanghai", "unit": "fahrenheit"}
                },
                "actual_params": {
                    "get_weather": {"city": "Shanghai", "unit": "fahrenheit"}
                },
                "tool_definitions": tool_definitions,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert result.data["details"]["average_score"] == 1.0
        assert result.data["details"]["per_tool_scores"]["get_weather"]["city"]["status"] == "correct"
        assert result.data["details"]["per_tool_scores"]["get_weather"]["unit"]["status"] == "correct"

    def test_validate_result_exact_match(self, evaluator):
        """结果验证：结果完全匹配"""
        request = EvaluationSchema(
            id="test_004",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {
                    "get_weather": {"temperature": 30, "humidity": 60},
                },
                "actual_results": {
                    "get_weather": {"temperature": 30, "humidity": 60},
                },
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert result.data["details"]["per_tool_results"]["get_weather"]["status"] == "correct"
        assert result.data["details"]["per_tool_results"]["get_weather"]["score"] == 1.0

    def test_partial_tool_selection(self, evaluator):
        """部分工具选择：部分工具正确"""
        request = EvaluationSchema(
            id="test_005",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["tool_a", "tool_b", "tool_c"],
                "actual_tools": ["tool_a", "tool_d"],  # tool_a正确，tool_d错误，漏选tool_b和tool_c
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 精确率：1/2 = 0.5，召回率：1/3 = 0.333，F1 = 2*0.5*0.333/(0.5+0.333) ≈ 0.4
        # 惩罚：1个错误选择 * 0.1 = 0.1
        # 最终分数：max(0, 0.4 - 0.1) = 0.3
        assert result.score == pytest.approx(0.3, abs=0.01)
        assert result.data["details"]["precision"] == pytest.approx(0.5, abs=0.01)
        assert result.data["details"]["recall"] == pytest.approx(0.333, abs=0.01)
        assert "tool_a" in result.data["details"]["correct_selections"]
        assert "tool_d" in result.data["details"]["incorrect_selections"]
        assert "tool_b" in result.data["details"]["missed_selections"]

    def test_param_type_correct_value_wrong(self, evaluator, tool_definitions):
        """参数类型正确但值不正确：应获得50%分数"""
        request = EvaluationSchema(
            id="test_006",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "get_weather": {"city": "Beijing", "unit": "celsius"}
                },
                "actual_params": {
                    "get_weather": {"city": "Shanghai", "unit": "fahrenheit"}  # 类型正确但值错误
                },
                "tool_definitions": tool_definitions,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 每个参数类型正确但值错误，应得0.5分，平均分 = (0.5 + 0.5) / 2 = 0.5
        assert result.score == pytest.approx(0.5, abs=0.01)
        assert result.data["details"]["per_tool_scores"]["get_weather"]["city"]["status"] == "type_correct_value_wrong"
        assert result.data["details"]["per_tool_scores"]["get_weather"]["unit"]["status"] == "type_correct_value_wrong"


class TestFunctionCallEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def evaluator(self):
        return FunctionCallEvaluator()

    def test_empty_expected_tools_returns_error(self, evaluator):
        """空期望工具列表应返回错误"""
        request = EvaluationSchema(
            id="test_007",
            type="function_call",
            payload={
                "expected_tools": [],
                "actual_tools": ["tool_a"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "expected_tools 不能为空" in result.error

    def test_empty_expected_tools_in_compare_tools(self, evaluator):
        """工具选择对比时空期望工具列表应返回错误"""
        request = EvaluationSchema(
            id="test_008",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": [],
                "actual_tools": ["tool_a"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "expected_tools 不能为空" in result.error

    def test_incorrect_tool_selection(self, evaluator):
        """错误工具选择：所有工具都选错"""
        request = EvaluationSchema(
            id="test_009",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["tool_a", "tool_b"],
                "actual_tools": ["tool_c", "tool_d"],  # 完全错误
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.0  # F1=0，惩罚0.2，最终为0
        assert result.data["details"]["precision"] == 0.0
        assert result.data["details"]["recall"] == 0.0
        assert len(result.data["details"]["correct_selections"]) == 0
        assert len(result.data["details"]["incorrect_selections"]) == 2
        assert len(result.data["details"]["missed_selections"]) == 2

    def test_missing_params(self, evaluator):
        """参数缺失：应得0分"""
        request = EvaluationSchema(
            id="test_010",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "get_weather": {"city": "Beijing", "unit": "celsius"}
                },
                "actual_params": {
                    "get_weather": {}  # 参数完全缺失
                },
                "tool_definitions": [],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.0
        assert result.data["details"]["per_tool_scores"]["get_weather"]["city"]["status"] == "missing"
        assert result.data["details"]["per_tool_scores"]["get_weather"]["unit"]["status"] == "missing"

    def test_incorrect_result(self, evaluator):
        """结果不匹配：应得0分"""
        request = EvaluationSchema(
            id="test_011",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {
                    "get_weather": {"temperature": 25},
                },
                "actual_results": {
                    "get_weather": {"temperature": 100},  # 完全不同的结果
                },
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 数值相似度：max(0, 1 - |25-100|/25) = max(0, 1-3) = 0
        assert result.score == 0.0
        assert result.data["details"]["per_tool_results"]["get_weather"]["status"] == "partial"

    def test_missing_result(self, evaluator):
        """结果缺失：应得0分"""
        request = EvaluationSchema(
            id="test_012",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {
                    "get_weather": {"temperature": 25},
                },
                "actual_results": {},  # 结果缺失
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.0
        assert result.data["details"]["per_tool_results"]["get_weather"]["status"] == "missing"


class TestFunctionCallEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def evaluator(self):
        return FunctionCallEvaluator()

    def test_empty_params_validation(self, evaluator):
        """空参数验证：应返回满分"""
        request = EvaluationSchema(
            id="test_013",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {},  # 无参数需要验证
                "actual_params": {},
                "tool_definitions": [],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert result.data["details"]["message"] == "无参数需要验证"

    def test_empty_results_validation(self, evaluator):
        """空结果验证：应返回满分"""
        request = EvaluationSchema(
            id="test_014",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {},  # 无结果需要验证
                "actual_results": {},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert result.data["details"]["message"] == "无结果需要验证"

    def test_single_tool_selection(self, evaluator):
        """单个工具选择"""
        request = EvaluationSchema(
            id="test_015",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["tool_a"],
                "actual_tools": ["tool_a"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert len(result.data["details"]["correct_selections"]) == 1

    def test_multiple_tools_selection(self, evaluator):
        """多个工具选择（10个工具）"""
        expected = [f"tool_{i}" for i in range(10)]
        actual = [f"tool_{i}" for i in range(10)]

        request = EvaluationSchema(
            id="test_016",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": expected,
                "actual_tools": actual,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert len(result.data["details"]["correct_selections"]) == 10

    def test_complex_nested_params(self, evaluator):
        """复杂嵌套参数"""
        request = EvaluationSchema(
            id="test_017",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "complex_tool": {
                        "nested": {
                            "deep": {
                                "value": "test",
                                "numbers": [1, 2, 3]
                            }
                        }
                    }
                },
                "actual_params": {
                    "complex_tool": {
                        "nested": {
                            "deep": {
                                "value": "test",
                                "numbers": [1, 2, 3]
                            }
                        }
                    }
                },
                "tool_definitions": [],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_large_dataset(self, evaluator):
        """大型数据集测试（100个工具）"""
        expected = [f"tool_{i}" for i in range(100)]
        # 前50个正确，后50个错误
        actual = [f"tool_{i}" for i in range(50)] + [f"wrong_{i}" for i in range(50)]

        request = EvaluationSchema(
            id="test_018",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": expected,
                "actual_tools": actual,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 精确率：50/100 = 0.5，召回率：50/100 = 0.5，F1 = 0.5
        # 惩罚：50个错误选择 * 0.1 = 5.0
        # 最终分数：max(0, 0.5 - 5.0) = 0.0
        assert result.score == 0.0
        assert len(result.data["details"]["correct_selections"]) == 50


class TestFunctionCallEvaluatorExceptionCases:
    """异常测试 - 异常情况"""

    @pytest.fixture
    def evaluator(self):
        return FunctionCallEvaluator()

    def test_invalid_action_defaults_to_full_evaluate(self, evaluator):
        """无效的action参数应默认执行完整评估"""
        request = EvaluationSchema(
            id="test_019",
            type="function_call",
            payload={
                "action": "invalid_action",  # 无效的action
                "expected_tools": ["tool_a"],
                "actual_tools": ["tool_a"],
            },
        )

        result = evaluator.evaluate(request)

        # 应该执行_full_evaluate
        assert result.is_valid is True
        assert "综合得分" in result.text

    def test_none_payload_values(self, evaluator):
        """None值处理"""
        request = EvaluationSchema(
            id="test_020",
            type="function_call",
            payload={
                "expected_tools": ["tool_a"],
                "actual_tools": ["tool_a"],
                "expected_params": None,  # None值
                "actual_params": None,
                "expected_results": None,
                "actual_results": None,
            },
        )

        result = evaluator.evaluate(request)

        # None值应被get_payload_data的默认值处理
        assert result.is_valid is True
        assert result.score >= 0.0

    def test_empty_dict_payload_values(self, evaluator):
        """空字典处理"""
        request = EvaluationSchema(
            id="test_021",
            type="function_call",
            payload={
                "expected_tools": ["tool_a"],
                "actual_tools": ["tool_a"],
                "expected_params": {},  # 空字典
                "actual_params": {},
                "expected_results": {},
                "actual_results": {},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 工具选择得分1.0，参数验证得分1.0（无参数），结果验证得分1.0（无结果）
        # 综合得分 = 1.0*0.4 + 1.0*0.35 + 1.0*0.25 = 1.0
        assert result.score == 1.0


class TestFunctionCallEvaluatorDependencyHandling:
    """依赖测试 - 外部依赖Mock"""

    @pytest.fixture
    def evaluator(self):
        return FunctionCallEvaluator()

    def test_without_llm_client_works(self, evaluator):
        """无LLM客户端时应正常工作（FunctionCallEvaluator不需要LLM）"""
        # FunctionCallEvaluator不需要LLM客户端
        request = EvaluationSchema(
            id="test_022",
            type="function_call",
            payload={
                "expected_tools": ["tool_a"],
                "actual_tools": ["tool_a"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_missing_tool_definition(self, evaluator):
        """工具定义缺失：应正常工作（仅影响类型验证）"""
        request = EvaluationSchema(
            id="test_023",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "unknown_tool": {"param": "value"}
                },
                "actual_params": {
                    "unknown_tool": {"param": "different_value"}
                },
                "tool_definitions": [],  # 工具定义缺失
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 无工具定义时，无法进行类型验证，值不匹配得0分
        assert result.score == 0.0


class TestFunctionCallEvaluatorSpecialCases:
    """特殊场景测试"""

    @pytest.fixture
    def evaluator(self):
        return FunctionCallEvaluator()

    def test_string_similarity_levenshtein(self, evaluator):
        """字符串相似度：Levenshtein距离计算"""
        request = EvaluationSchema(
            id="test_024",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {
                    "tool": "hello world"
                },
                "actual_results": {
                    "tool": "hello word"  # 一个字符差异
                },
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # Levenshtein距离：1，最大长度：11，相似度：1 - 1/11 ≈ 0.91
        assert result.score == pytest.approx(0.91, abs=0.01)
        assert result.data["details"]["per_tool_results"]["tool"]["status"] == "partial"

    def test_dict_similarity(self, evaluator):
        """字典相似度计算"""
        request = EvaluationSchema(
            id="test_025",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {
                    "tool": {"a": 1, "b": 2, "c": 3}
                },
                "actual_results": {
                    "tool": {"a": 1, "b": 2, "d": 4}  # c缺失，d新增
                },
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 字典相似度：all_keys = {a, b, c, d}
        # a: 1.0, b: 1.0, c: 0.0(缺失), d: 0.0(新增)
        # 总相似度 = (1.0 + 1.0 + 0.0 + 0.0) / 4 = 0.5
        assert result.score == pytest.approx(0.5, abs=0.01)

    def test_list_similarity_lcs(self, evaluator):
        """列表相似度：最长公共子序列"""
        request = EvaluationSchema(
            id="test_026",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {
                    "tool": [1, 2, 3, 4, 5]
                },
                "actual_results": {
                    "tool": [1, 3, 5, 7, 9]  # LCS: [1, 3, 5]
                },
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # LCS长度：3，最大长度：5，相似度：3/5 = 0.6
        assert result.score == pytest.approx(0.6, abs=0.01)

    def test_numeric_similarity(self, evaluator):
        """数值相似度计算"""
        request = EvaluationSchema(
            id="test_027",
            type="function_call",
            payload={
                "action": "validate_result",
                "expected_results": {
                    "tool": 100
                },
                "actual_results": {
                    "tool": 90  # 差异10%
                },
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 数值相似度：max(0, 1 - |100-90|/100) = 0.9
        assert result.score == pytest.approx(0.9, abs=0.01)

    def test_case_insensitive_string_comparison(self, evaluator):
        """字符串比较：忽略大小写和首尾空格"""
        request = EvaluationSchema(
            id="test_028",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "tool": {"param": "  HELLO  "}
                },
                "actual_params": {
                    "tool": {"param": "hello"}  # 大小写和空格不同
                },
                "tool_definitions": [],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 字符串比较忽略大小写和首尾空格
        assert result.score == 1.0

    def test_param_type_validation(self, evaluator):
        """参数类型验证"""
        tool_definitions = [
            {
                "name": "typed_tool",
                "parameters": {
                    "properties": {
                        "string_param": {"type": "string"},
                        "number_param": {"type": "number"},
                        "integer_param": {"type": "integer"},
                        "boolean_param": {"type": "boolean"},
                        "array_param": {"type": "array"},
                        "object_param": {"type": "object"},
                    }
                },
            }
        ]

        request = EvaluationSchema(
            id="test_029",
            type="function_call",
            payload={
                "action": "validate_params",
                "expected_params": {
                    "typed_tool": {
                        "string_param": "expected",
                        "number_param": 10.5,
                        "integer_param": 42,
                        "boolean_param": True,
                        "array_param": [1, 2, 3],
                        "object_param": {"key": "value"},
                    }
                },
                "actual_params": {
                    "typed_tool": {
                        "string_param": "actual",  # 类型正确但值错误
                        "number_param": 20.5,  # 类型正确但值错误
                        "integer_param": 99,  # 类型正确但值错误
                        "boolean_param": False,  # 类型正确但值错误
                        "array_param": [4, 5, 6],  # 类型正确但值错误
                        "object_param": {"key": "other"},  # 类型正确但值错误
                    }
                },
                "tool_definitions": tool_definitions,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 所有参数类型正确但值错误，每个得0.5分
        assert result.score == pytest.approx(0.5, abs=0.01)

    def test_penalty_for_incorrect_selections(self, evaluator):
        """错误工具选择的惩罚机制"""
        request = EvaluationSchema(
            id="test_030",
            type="function_call",
            payload={
                "action": "compare_tools",
                "expected_tools": ["tool_a"],
                "actual_tools": ["tool_a", "tool_b", "tool_c", "tool_d", "tool_e"],  # 4个错误选择
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 精确率：1/5 = 0.2，召回率：1/1 = 1.0，F1 = 2*0.2*1.0/(0.2+1.0) ≈ 0.333
        # 惩罚：4个错误选择 * 0.1 = 0.4
        # 最终分数：max(0, 0.333 - 0.4) = 0.0
        assert result.score == 0.0
        assert result.data["details"]["penalty"] == 0.4


class TestFunctionCallEvaluatorIntegrationScenarios:
    """集成场景测试"""

    @pytest.fixture
    def evaluator(self):
        return FunctionCallEvaluator()

    def test_real_world_weather_scenario(self, evaluator):
        """真实场景：天气查询工具调用"""
        tool_definitions = [
            {
                "name": "get_weather",
                "parameters": {
                    "properties": {
                        "city": {"type": "string", "description": "城市名称"},
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    }
                },
            }
        ]

        request = EvaluationSchema(
            id="test_031",
            type="function_call",
            payload={
                "expected_tools": ["get_weather"],
                "actual_tools": ["get_weather"],
                "expected_params": {
                    "get_weather": {"city": "北京", "unit": "celsius"}
                },
                "actual_params": {
                    "get_weather": {"city": "北京", "unit": "celsius"}
                },
                "expected_results": {
                    "get_weather": {
                        "temperature": 25,
                        "humidity": 60,
                        "condition": "晴",
                        "wind_speed": 3.5
                    }
                },
                "actual_results": {
                    "get_weather": {
                        "temperature": 25,
                        "humidity": 60,
                        "condition": "晴",
                        "wind_speed": 3.5
                    }
                },
                "tool_definitions": tool_definitions,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert "Function Calling 评估完成" in result.text

    def test_real_world_multi_tool_scenario(self, evaluator):
        """真实场景：多工具协同调用"""
        tool_definitions = [
            {
                "name": "search_products",
                "parameters": {
                    "properties": {
                        "query": {"type": "string"},
                        "category": {"type": "string"},
                    }
                },
            },
            {
                "name": "add_to_cart",
                "parameters": {
                    "properties": {
                        "product_id": {"type": "string"},
                        "quantity": {"type": "integer"},
                    }
                },
            },
            {
                "name": "checkout",
                "parameters": {
                    "properties": {
                        "payment_method": {"type": "string"},
                    }
                },
            },
        ]

        request = EvaluationSchema(
            id="test_032",
            type="function_call",
            payload={
                "expected_tools": ["search_products", "add_to_cart", "checkout"],
                "actual_tools": ["search_products", "add_to_cart", "checkout"],
                "expected_params": {
                    "search_products": {"query": "iPhone", "category": "electronics"},
                    "add_to_cart": {"product_id": "12345", "quantity": 2},
                    "checkout": {"payment_method": "credit_card"},
                },
                "actual_params": {
                    "search_products": {"query": "iPhone", "category": "electronics"},
                    "add_to_cart": {"product_id": "12345", "quantity": 2},
                    "checkout": {"payment_method": "credit_card"},
                },
                "expected_results": {
                    "search_products": {"status": "success", "count": 10},
                    "add_to_cart": {"status": "added"},
                    "checkout": {"status": "completed"},
                },
                "actual_results": {
                    "search_products": {"status": "success", "count": 10},
                    "add_to_cart": {"status": "added"},
                    "checkout": {"status": "completed"},
                },
                "tool_definitions": tool_definitions,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert result.data["tool_selection"]["score"] == 1.0
        assert result.data["param_validation"]["score"] == 1.0
        assert result.data["result_validation"]["score"] == 1.0