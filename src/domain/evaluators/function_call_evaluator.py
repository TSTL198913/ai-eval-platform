"""Function Calling 评估器

用于评估大模型的工具调用(Function Calling)能力，包括：
- 工具调用准确率评估
- 参数验证评估
- 工具选择正确性评估
- 执行结果验证
"""

from typing import Any

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("function_call")
class FunctionCallEvaluator(BaseEvaluator):
    """Function Calling 评估器

    评估大模型的工具调用能力，支持：
    - 工具名称匹配评估
    - 参数验证评估
    - 工具选择正确性评估
    - 执行结果验证
    """

    def __init__(self, client: Any | None = None):
        super().__init__(client)

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """评估工具调用结果

        Args:
            request: 评估请求，payload包含：
                - expected_tools: 期望调用的工具列表
                - actual_tools: 实际调用的工具列表
                - expected_params: 期望的参数
                - actual_params: 实际的参数
                - expected_results: 期望的执行结果
                - actual_results: 实际的执行结果
                - tool_definitions: 工具定义列表（用于参数验证）

        Returns:
            DomainResponse: 评估结果
        """
        action = self.get_payload_data(request, "action", "evaluate")

        if action == "validate_params":
            return self._validate_params(request)
        elif action == "compare_tools":
            return self._compare_tools(request)
        elif action == "validate_result":
            return self._validate_result(request)
        else:
            return self._full_evaluate(request)

    def _full_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """完整评估：工具选择 + 参数验证 + 结果验证"""
        expected_tools = self.get_payload_data(request, "expected_tools", [])
        actual_tools = self.get_payload_data(request, "actual_tools", [])
        expected_params = self.get_payload_data(request, "expected_params", {})
        actual_params = self.get_payload_data(request, "actual_params", {})
        expected_results = self.get_payload_data(request, "expected_results", {})
        actual_results = self.get_payload_data(request, "actual_results", {})
        tool_definitions = self.get_payload_data(request, "tool_definitions", [])

        if not expected_tools:
            return DomainResponse(
                is_valid=False,
                error="expected_tools 不能为空",
            )

        # 工具选择评估
        tool_score, tool_details = self._evaluate_tool_selection(expected_tools, actual_tools)

        # 参数验证评估
        param_score, param_details = self._evaluate_params(
            expected_params, actual_params, tool_definitions
        )

        # 执行结果验证
        result_score, result_details = self._evaluate_results(expected_results, actual_results)

        # 综合评分
        overall_score = tool_score * 0.4 + param_score * 0.35 + result_score * 0.25

        return DomainResponse(
            is_valid=True,
            text=f"Function Calling 评估完成，综合得分: {overall_score:.2f}",
            score=overall_score,
            data={
                "tool_selection": {
                    "score": tool_score,
                    "details": tool_details,
                },
                "param_validation": {
                    "score": param_score,
                    "details": param_details,
                },
                "result_validation": {
                    "score": result_score,
                    "details": result_details,
                },
                "overall_score": overall_score,
            },
        )

    def _compare_tools(self, request: EvaluationSchema) -> DomainResponse:
        """工具选择对比评估"""
        expected_tools = self.get_payload_data(request, "expected_tools", [])
        actual_tools = self.get_payload_data(request, "actual_tools", [])

        if not expected_tools:
            return DomainResponse(
                is_valid=False,
                error="expected_tools 不能为空",
            )

        score, details = self._evaluate_tool_selection(expected_tools, actual_tools)

        return DomainResponse(
            is_valid=True,
            text=f"工具选择评估完成，得分: {score:.2f}",
            score=score,
            data={
                "expected_tools": expected_tools,
                "actual_tools": actual_tools,
                "details": details,
            },
        )

    def _validate_params(self, request: EvaluationSchema) -> DomainResponse:
        """参数验证评估"""
        expected_params = self.get_payload_data(request, "expected_params", {})
        actual_params = self.get_payload_data(request, "actual_params", {})
        tool_definitions = self.get_payload_data(request, "tool_definitions", [])

        score, details = self._evaluate_params(expected_params, actual_params, tool_definitions)

        return DomainResponse(
            is_valid=True,
            text=f"参数验证完成，得分: {score:.2f}",
            score=score,
            data={
                "expected_params": expected_params,
                "actual_params": actual_params,
                "details": details,
            },
        )

    def _validate_result(self, request: EvaluationSchema) -> DomainResponse:
        """执行结果验证"""
        expected_results = self.get_payload_data(request, "expected_results", {})
        actual_results = self.get_payload_data(request, "actual_results", {})

        score, details = self._evaluate_results(expected_results, actual_results)

        return DomainResponse(
            is_valid=True,
            text=f"结果验证完成，得分: {score:.2f}",
            score=score,
            data={
                "expected_results": expected_results,
                "actual_results": actual_results,
                "details": details,
            },
        )

    def _evaluate_tool_selection(
        self, expected_tools: list, actual_tools: list
    ) -> tuple[float, dict]:
        """评估工具选择正确性

        Args:
            expected_tools: 期望调用的工具列表
            actual_tools: 实际调用的工具列表

        Returns:
            tuple[float, dict]: (得分, 详细信息)
        """
        if not expected_tools:
            return 0.0, {"error": "期望工具列表为空"}

        expected_set = set(expected_tools)
        actual_set = set(actual_tools)

        # 正确选择的工具
        correct_selections = expected_set & actual_set
        # 错误选择的工具（实际调用但不在期望中）
        incorrect_selections = actual_set - expected_set
        # 漏选的工具（期望调用但未调用）
        missed_selections = expected_set - actual_set

        # 计算精确匹配率
        precision = len(correct_selections) / len(actual_set) if actual_set else 0.0
        # 计算召回率
        recall = len(correct_selections) / len(expected_set) if expected_set else 0.0
        # F1 分数
        f1_score = (
            2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        )

        # 惩罚错误选择
        penalty = len(incorrect_selections) * 0.1
        final_score = max(0.0, f1_score - penalty)

        details = {
            "correct_selections": list(correct_selections),
            "incorrect_selections": list(incorrect_selections),
            "missed_selections": list(missed_selections),
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "penalty": penalty,
        }

        return final_score, details

    def _evaluate_params(
        self,
        expected_params: dict,
        actual_params: dict,
        tool_definitions: list,
    ) -> tuple[float, dict]:
        """评估参数正确性

        Args:
            expected_params: 期望的参数
            actual_params: 实际的参数
            tool_definitions: 工具定义列表

        Returns:
            tuple[float, dict]: (得分, 详细信息)
        """
        if not expected_params:
            return 1.0, {"message": "无参数需要验证"}

        total_score = 0.0
        param_count = 0
        param_details = {}

        for tool_name, expected_tool_params in expected_params.items():
            actual_tool_params = actual_params.get(tool_name, {})
            tool_def = self._find_tool_definition(tool_name, tool_definitions)

            tool_score, tool_details = self._validate_tool_params(
                expected_tool_params, actual_tool_params, tool_def
            )

            total_score += tool_score
            param_count += 1
            param_details[tool_name] = tool_details

        avg_score = total_score / param_count if param_count > 0 else 1.0

        return avg_score, {
            "per_tool_scores": param_details,
            "average_score": avg_score,
        }

    def _validate_tool_params(
        self,
        expected: dict,
        actual: dict,
        tool_def: dict | None,
    ) -> tuple[float, dict]:
        """验证单个工具的参数"""
        if not expected:
            return 1.0, {"message": "无参数"}

        correct_params = 0
        total_params = len(expected)
        param_results = {}

        for param_name, expected_value in expected.items():
            actual_value = actual.get(param_name)

            if actual_value is None:
                param_results[param_name] = {
                    "status": "missing",
                    "expected": expected_value,
                    "actual": None,
                }
                continue

            # 检查参数值是否匹配
            if self._compare_values(expected_value, actual_value):
                correct_params += 1
                param_results[param_name] = {
                    "status": "correct",
                    "expected": expected_value,
                    "actual": actual_value,
                }
            else:
                # 检查类型是否正确（如果有工具定义）
                if tool_def:
                    param_schema = self._get_param_schema(param_name, tool_def)
                    if param_schema:
                        type_valid = self._validate_param_type(actual_value, param_schema)
                        if type_valid:
                            correct_params += 0.5  # 类型正确但值不正确，给一半分
                            param_results[param_name] = {
                                "status": "type_correct_value_wrong",
                                "expected": expected_value,
                                "actual": actual_value,
                            }
                            continue

                param_results[param_name] = {
                    "status": "incorrect",
                    "expected": expected_value,
                    "actual": actual_value,
                }

        score = correct_params / total_params if total_params > 0 else 1.0
        return score, param_results

    def _evaluate_results(self, expected_results: dict, actual_results: dict) -> tuple[float, dict]:
        """评估执行结果

        Args:
            expected_results: 期望的执行结果
            actual_results: 实际的执行结果

        Returns:
            tuple[float, dict]: (得分, 详细信息)
        """
        if not expected_results:
            return 1.0, {"message": "无结果需要验证"}

        total_score = 0.0
        result_count = 0
        result_details = {}

        for tool_name, expected_result in expected_results.items():
            actual_result = actual_results.get(tool_name)

            if actual_result is None:
                result_details[tool_name] = {
                    "status": "missing",
                    "expected": expected_result,
                    "actual": None,
                    "score": 0.0,
                }
                total_score += 0.0
            elif self._compare_values(expected_result, actual_result):
                result_details[tool_name] = {
                    "status": "correct",
                    "expected": expected_result,
                    "actual": actual_result,
                    "score": 1.0,
                }
                total_score += 1.0
            else:
                # 部分匹配检查
                similarity = self._calculate_similarity(expected_result, actual_result)
                result_details[tool_name] = {
                    "status": "partial",
                    "expected": expected_result,
                    "actual": actual_result,
                    "similarity": similarity,
                    "score": similarity,
                }
                total_score += similarity

            result_count += 1

        avg_score = total_score / result_count if result_count > 0 else 1.0

        return avg_score, {
            "per_tool_results": result_details,
            "average_score": avg_score,
        }

    def _find_tool_definition(self, tool_name: str, definitions: list) -> dict | None:
        """查找工具定义"""
        for definition in definitions:
            if definition.get("name") == tool_name:
                return definition
        return None

    def _get_param_schema(self, param_name: str, tool_def: dict) -> dict | None:
        """获取参数的 schema 定义"""
        parameters = tool_def.get("parameters", {})
        properties = parameters.get("properties", {})
        return properties.get(param_name)

    def _validate_param_type(self, value: Any, schema: dict) -> bool:
        """验证参数类型"""
        expected_type = schema.get("type")

        if expected_type == "string":
            return isinstance(value, str)
        elif expected_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        elif expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        elif expected_type == "boolean":
            return isinstance(value, bool)
        elif expected_type == "array":
            return isinstance(value, list)
        elif expected_type == "object":
            return isinstance(value, dict)
        elif expected_type == "null":
            return value is None

        return True  # 未知类型，默认通过

    def _compare_values(self, expected: Any, actual: Any) -> bool:
        """比较两个值是否相等"""
        if expected == actual:
            return True

        # 处理字典比较
        if isinstance(expected, dict) and isinstance(actual, dict):
            if set(expected.keys()) != set(actual.keys()):
                return False
            return all(self._compare_values(expected[k], actual[k]) for k in expected.keys())

        # 处理列表比较
        if isinstance(expected, list) and isinstance(actual, list):
            if len(expected) != len(actual):
                return False
            return all(self._compare_values(e, a) for e, a in zip(expected, actual, strict=False))

        # 字符串比较（忽略大小写和首尾空格）
        if isinstance(expected, str) and isinstance(actual, str):
            return expected.strip().lower() == actual.strip().lower()

        return False

    def _calculate_similarity(self, expected: Any, actual: Any) -> float:
        """计算两个值的相似度"""
        if expected == actual:
            return 1.0

        # 字符串相似度
        if isinstance(expected, str) and isinstance(actual, str):
            return self._string_similarity(expected, actual)

        # 字典相似度
        if isinstance(expected, dict) and isinstance(actual, dict):
            return self._dict_similarity(expected, actual)

        # 列表相似度
        if isinstance(expected, list) and isinstance(actual, list):
            return self._list_similarity(expected, actual)

        # 数值相似度
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            if expected == 0:
                return 1.0 if actual == 0 else 0.0
            return max(0.0, 1.0 - abs(expected - actual) / abs(expected))

        return 0.0

    def _string_similarity(self, s1: str, s2: str) -> float:
        """计算字符串相似度（Levenshtein 距离）"""
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        len1, len2 = len(s1), len(s2)
        dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]

        for i in range(len1 + 1):
            dp[i][0] = i
        for j in range(len2 + 1):
            dp[0][j] = j

        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if s1[i - 1] == s2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = min(
                        dp[i - 1][j] + 1,
                        dp[i][j - 1] + 1,
                        dp[i - 1][j - 1] + 1,
                    )

        distance = dp[len1][len2]
        max_len = max(len1, len2)
        return 1.0 - distance / max_len

    def _dict_similarity(self, d1: dict, d2: dict) -> float:
        """计算字典相似度"""
        all_keys = set(d1.keys()) | set(d2.keys())
        if not all_keys:
            return 1.0

        similarities = []
        for key in all_keys:
            if key in d1 and key in d2:
                similarities.append(self._calculate_similarity(d1[key], d2[key]))
            else:
                similarities.append(0.0)

        return sum(similarities) / len(similarities)

    def _list_similarity(self, l1: list, l2: list) -> float:
        """计算列表相似度"""
        if not l1 and not l2:
            return 1.0
        if not l1 or not l2:
            return 0.0

        # 使用最长公共子序列比例
        lcs_len = self._longest_common_subsequence_length(l1, l2)
        max_len = max(len(l1), len(l2))
        return lcs_len / max_len

    def _longest_common_subsequence_length(self, l1: list, l2: list) -> int:
        """计算最长公共子序列长度"""
        m, n = len(l1), len(l2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if l1[i - 1] == l2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

        return dp[m][n]
