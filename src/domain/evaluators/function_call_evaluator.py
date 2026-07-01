"""
🛠️ Function Calling (工具调用) 评估器
用于精确审计和评测大模型在复杂决策、多工具路由、参数提取、及结果一致性上的表现。
升级 2026 标准：全链路滚动数组优化（LCS/Levenshtein 空间压缩）、同步/异步双轨引擎、动态权重风控。
"""

import asyncio
import logging
from typing import Any

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus

logger = logging.getLogger(__name__)

# 📌 2026 默认评测权重系数（支持动态覆盖）
DEFAULT_TOOL_WEIGHT = 0.40
DEFAULT_PARAM_WEIGHT = 0.35
DEFAULT_RESULT_WEIGHT = 0.25

MAX_STRING_LENGTH = 10000  # 防御长文本内存溢出的安全截断阈值


@EvaluatorFactory.register("function_call")
class FunctionCallEvaluator(BaseEvaluator):
    """Function Calling 评估器（2026 高并发、极致低内存版）"""

    def __init__(self, client: Any | None = None):
        super().__init__(client)

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """[同步轨] 执行同步工具调用评测流"""
        action = self.get_payload_data(request, "action", "evaluate")

        # 架构防御：先统一提取 payload
        if action == "validate_params":
            return self._validate_params_flow(request)
        elif action == "compare_tools":
            return self._compare_tools_flow(request)
        elif action == "validate_result":
            return self._validate_result_flow(request)
        else:
            return self._full_evaluate_flow(request)

    async def evaluate_async(self, request: EvaluationSchema) -> DomainResponse:
        """🚀 [异步轨] 高性能非阻塞入口
        由于 Function Call 涉及密集的 CPU 文本和矩阵相似度计算，
        通过 asyncio.to_thread 将计算密集型任务卸载到专门的 Worker 线程池，避免阻塞异步主事件循环。
        """
        return await asyncio.to_thread(self.evaluate, request)

    def _full_evaluate_flow(self, request: EvaluationSchema) -> DomainResponse:
        """完整级联审计：工具路由(40%) + 参数拟合(35%) + 结果单步验证(25%)"""
        expected_tools = self.get_payload_data(request, "expected_tools", [])
        actual_tools = self.get_payload_data(request, "actual_tools", [])
        expected_params = self.get_payload_data(request, "expected_params", {})
        actual_params = self.get_payload_data(request, "actual_params", {})
        expected_results = self.get_payload_data(request, "expected_results", {})
        actual_results = self.get_payload_data(request, "actual_results", {})
        tool_definitions = self.get_payload_data(request, "tool_definitions", [])

        # 🧠 2026 架构升级：无评估依据时应返回 CANNOT_EVALUATE，而非"无数据=满分"
        # 这是状态机设计的核心原则：明确区分"表现差"和"无法评估"
        if not expected_tools and not actual_tools:
            return self.create_cannot_evaluate_response(
                reason="缺少评估依据：期望和实际工具列表均为空，无法进行工具选择评估",
                dimensions_skipped=["tool_selection", "param_validation", "result_validation"],
                metadata={
                    "expected_tools_count": 0,
                    "actual_tools_count": 0,
                },
            )

        # 1. 工具选择路由评估
        tool_score, tool_details = self._evaluate_tool_selection(expected_tools, actual_tools)

        # 2. 细粒度参数类型与值审计
        param_score, param_details = self._evaluate_params(
            expected_params, actual_params, tool_definitions
        )

        # 3. 动态执行结果语义相似度验证
        result_score, result_details = self._evaluate_results(expected_results, actual_results)

        # 4. 动态读取控制权重（容许从 metadata 中覆盖）
        meta = request.metadata or {}
        w_tool = meta.get("weight_tool", DEFAULT_TOOL_WEIGHT)
        w_param = meta.get("weight_param", DEFAULT_PARAM_WEIGHT)
        w_result = meta.get("weight_result", DEFAULT_RESULT_WEIGHT)

        # 归一化权重防御
        total_w = w_tool + w_param + w_result
        if total_w > 0:
            w_tool, w_param, w_result = w_tool / total_w, w_param / total_w, w_result / total_w

        overall_score = (tool_score * w_tool) + (param_score * w_param) + (result_score * w_result)
        overall_score = round(min(max(overall_score, 0.0), 1.0), 4)

        evaluated_dims = []
        skipped_dims = []
        if expected_tools:
            evaluated_dims.append("tool_selection")
        if expected_params:
            evaluated_dims.append("param_validation")
        if expected_results:
            evaluated_dims.append("result_validation")

        if not expected_params:
            skipped_dims.append("param_validation")
        if not expected_results:
            skipped_dims.append("result_validation")

        if skipped_dims:
            return self.create_partial_response(
                text=f"Function Calling 综合审计完成（部分维度），最终评测得分: {overall_score:.2f}",
                score=overall_score,
                dimensions_evaluated=evaluated_dims,
                dimensions_skipped=skipped_dims,
                skip_reasons={
                    "param_validation": "缺少 expected_params" if "param_validation" in skipped_dims else None,
                    "result_validation": "缺少 expected_results" if "result_validation" in skipped_dims else None,
                },
                data={
                    "passed": overall_score >= meta.get("passing_threshold", 0.6),
                    "tool_selection": {"score": round(tool_score, 4), "details": tool_details},
                    "param_validation": {"score": round(param_score, 4), "details": param_details},
                    "result_validation": {"score": round(result_score, 4), "details": result_details},
                    "weights_applied": {"tool": w_tool, "param": w_param, "result": w_result},
                },
            )

        return self.create_success_response(
            text=f"Function Calling 综合审计完成，最终评测得分: {overall_score:.2f}",
            score=overall_score,
            data={
                "passed": overall_score >= meta.get("passing_threshold", 0.6),
                "tool_selection": {"score": round(tool_score, 4), "details": tool_details},
                "param_validation": {"score": round(param_score, 4), "details": param_details},
                "result_validation": {"score": round(result_score, 4), "details": result_details},
                "weights_applied": {"tool": w_tool, "param": w_param, "result": w_result},
            },
        )

    def _compare_tools_flow(self, request: EvaluationSchema) -> DomainResponse:
        """独立切片：工具选择正确性评估"""
        expected_tools = self.get_payload_data(request, "expected_tools", [])
        actual_tools = self.get_payload_data(request, "actual_tools", [])

        score, details = self._evaluate_tool_selection(expected_tools, actual_tools)
        return self.create_success_response(
            text=f"工具路由选择评估完成，得分: {score:.2f}",
            score=round(score, 4),
            data={
                "expected_tools": expected_tools,
                "actual_tools": actual_tools,
                "details": details,
            },
        )

    def _validate_params_flow(self, request: EvaluationSchema) -> DomainResponse:
        """独立切片：参数提取完整性与强类型校验"""
        expected_params = self.get_payload_data(request, "expected_params", {})
        actual_params = self.get_payload_data(request, "actual_params", {})
        tool_definitions = self.get_payload_data(request, "tool_definitions", [])

        score, details = self._evaluate_params(expected_params, actual_params, tool_definitions)
        return self.create_success_response(
            text=f"工具参数拟合验证完成，得分: {score:.2f}",
            score=round(score, 4),
            data={
                "expected_params": expected_params,
                "actual_params": actual_params,
                "details": details,
            },
        )

    def _validate_result_flow(self, request: EvaluationSchema) -> DomainResponse:
        """独立切片：模型执行结果语义相似度对齐校验"""
        expected_results = self.get_payload_data(request, "expected_results", {})
        actual_results = self.get_payload_data(request, "actual_results", {})

        score, details = self._evaluate_results(expected_results, actual_results)
        return self.create_success_response(
            text=f"执行结果一致性比对完成，得分: {score:.2f}",
            score=round(score, 4),
            data={
                "expected_results": expected_results,
                "actual_results": actual_results,
                "details": details,
            },
        )

    # --------------------------------------------------------------------------
    # 核心算法算力层
    # --------------------------------------------------------------------------

    def _evaluate_tool_selection(
        self, expected_tools: list, actual_tools: list
    ) -> tuple[float, dict]:
        """计算工具路由的 Precision / Recall / F1 矩阵并施加幻觉惩罚"""
        if not expected_tools:
            return (
                (0.0, {"error": "期望工具列表为空"})
                if actual_tools
                else (1.0, {"message": "皆为空，完全匹配"})
            )

        expected_set = set(expected_tools)
        actual_set = set(actual_tools)

        correct_selections = expected_set & actual_set
        incorrect_selections = actual_set - expected_set
        missed_selections = expected_set - actual_set

        precision = len(correct_selections) / len(actual_set) if actual_set else 0.0
        recall = len(correct_selections) / len(expected_set)

        f1_score = (
            (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        )

        # 模型产生幻觉滥用无关工具时触发相对惩罚（上限0.3）
        total_count = len(expected_set)
        penalty = min(0.3, len(incorrect_selections) / total_count) if total_count > 0 else 0.0
        final_score = max(0.0, f1_score - penalty)

        return final_score, {
            "correct_selections": list(correct_selections),
            "incorrect_selections": list(incorrect_selections),
            "missed_selections": list(missed_selections),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1_score, 4),
            "penalty": round(penalty, 4),
        }

    def _evaluate_params(
        self, expected_params: dict, actual_params: dict, tool_definitions: list
    ) -> tuple[float, dict]:
        """评估多工具参数对齐状态"""
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
        return avg_score, {"per_tool_scores": param_details, "average_score": round(avg_score, 4)}

    def _validate_tool_params(
        self, expected: dict, actual: dict, tool_def: dict | None
    ) -> tuple[float, dict]:
        """单工具内部参数与 JSON Schema 规则校验"""
        if not expected:
            return 1.0, {"message": "当前工具无期望参数"}

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

            # A. 值完全一致（或弱字符串对齐）
            if self._compare_values(expected_value, actual_value):
                correct_params += 1
                param_results[param_name] = {
                    "status": "correct",
                    "expected": expected_value,
                    "actual": actual_value,
                }
            else:
                # B. 值虽不一致，但如果类型契合 JSON Schema，给与 0.5 的参数类型正确鼓励分
                if tool_def:
                    param_schema = self._get_param_schema(param_name, tool_def)
                    if param_schema and self._validate_param_type(actual_value, param_schema):
                        correct_params += 0.5
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
        """多维异构执行结果混合审计"""
        if not expected_results:
            return 1.0, {"message": "无执行结果需要比对"}

        total_score = 0.0
        result_count = 0
        result_details = {}

        for tool_name, expected_result in expected_results.items():
            actual_result = actual_results.get(tool_name)

            if actual_result is None:
                result_details[tool_name] = {"status": "missing", "score": 0.0}
            elif self._compare_values(expected_result, actual_result):
                result_details[tool_name] = {"status": "correct", "score": 1.0}
                total_score += 1.0
            else:
                # 针对非完全一致的结果启动弹性距离相似度度量（支持数字、对象、数组与复杂串）
                similarity = self._calculate_similarity(expected_result, actual_result)
                result_details[tool_name] = {
                    "status": "partial",
                    "similarity": round(similarity, 4),
                    "score": round(similarity, 4),
                }
                total_score += similarity

            result_count += 1

        avg_score = total_score / result_count if result_count > 0 else 1.0
        return avg_score, {"per_tool_results": result_details, "average_score": round(avg_score, 4)}

    # --------------------------------------------------------------------------
    # 高性能核心基础匹配算法（2026 滚动内存空间优化版）
    # --------------------------------------------------------------------------

    def _string_similarity(self, s1: str, s2: str) -> float:
        """[空间优化型] Levenshtein 编辑距离算法 - 空间复杂度降为 O(min(N, M))"""
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        # 高并发引擎防御：截断极端文本，防止恶意长文本撑爆堆栈
        if len(s1) > MAX_STRING_LENGTH:
            s1 = s1[:MAX_STRING_LENGTH]
        if len(s2) > MAX_STRING_LENGTH:
            s2 = s2[:MAX_STRING_LENGTH]

        len1, len2 = len(s1), len(s2)
        if len1 > len2:
            s1, s2 = s2, s1
            len1, len2 = len2, len1

        prev_row = list(range(len2 + 1))
        curr_row = [0] * (len2 + 1)

        for i in range(1, len1 + 1):
            curr_row[0] = i
            for j in range(1, len2 + 1):
                if s1[i - 1] == s2[j - 1]:
                    curr_row[j] = prev_row[j - 1]
                else:
                    curr_row[j] = min(
                        prev_row[j] + 1,  # Delete
                        curr_row[j - 1] + 1,  # Insert
                        prev_row[j - 1] + 1,  # Replace
                    )
            prev_row, curr_row = curr_row, prev_row

        distance = prev_row[len2]
        return 1.0 - (distance / max(len1, len2))

    def _longest_common_subsequence_length(self, l1: list, l2: list) -> int:
        """🚀 [2026 极致内存重构] LCS 最长公共子序列 - 空间复杂度从 O(M*N) 锐减至 O(min(M, N))
        彻底解决上游输入超长复杂结构列表时，由于开辟巨型二维矩阵导致的内存颠簸。
        """
        m, n = len(l1), len(l2)
        if m > n:
            l1, l2 = l2, l1
            m, n = n, m

        # 仅使用两行一维滚动数组完成状态转换
        prev_row = [0] * (n + 1)
        curr_row = [0] * (n + 1)

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if l1[i - 1] == l2[j - 1]:
                    curr_row[j] = prev_row[j - 1] + 1
                else:
                    curr_row[j] = max(prev_row[j], curr_row[j - 1])
            # 同步更新滚动基线（利用高效的切片拷贝）
            prev_row[:] = curr_row[:]

        return prev_row[n]

    def _list_similarity(self, l1: list, l2: list) -> float:
        """基于高性能新版 LCS 比例计算列表结构相似度"""
        if not l1 and not l2:
            return 1.0
        if not l1 or not l2:
            return 0.0

        lcs_len = self._longest_common_subsequence_length(l1, l2)
        return lcs_len / max(len(l1), len(l2))

    def _dict_similarity(self, d1: dict, d2: dict) -> float:
        """递归审计键值对字典结构的加权关联相似度"""
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

    def _calculate_similarity(self, expected: Any, actual: Any) -> float:
        """动态多态分流：选择契合底层数据类型的相似度量矩阵"""
        if expected == actual:
            return 1.0

        if isinstance(expected, str) and isinstance(actual, str):
            return self._string_similarity(expected, actual)

        if isinstance(expected, dict) and isinstance(actual, dict):
            return self._dict_similarity(expected, actual)

        if isinstance(expected, list) and isinstance(actual, list):
            return self._list_similarity(expected, actual)

        if isinstance(expected, int | float) and isinstance(actual, int | float):
            if expected == 0:
                return 1.0 if actual == 0 else 0.0
            return max(0.0, 1.0 - abs(expected - actual) / abs(expected))

        return 0.0

    def _compare_values(self, expected: Any, actual: Any) -> bool:
        """深度断言两个嵌套异构数据实体是否强等值"""
        if expected == actual:
            return True

        if isinstance(expected, dict) and isinstance(actual, dict):
            if set(expected.keys()) != set(actual.keys()):
                return False
            return all(self._compare_values(expected[k], actual[k]) for k in expected.keys())

        if isinstance(expected, list) and isinstance(actual, list):
            if len(expected) != len(actual):
                return False
            return all(self._compare_values(e, a) for e, a in zip(expected, actual, strict=False))

        if isinstance(expected, str) and isinstance(actual, str):
            return expected.strip().lower() == actual.strip().lower()

        return False

    def _find_tool_definition(self, tool_name: str, definitions: list) -> dict | None:
        return next((d for d in definitions if d.get("name") == tool_name), None)

    def _get_param_schema(self, param_name: str, tool_def: dict) -> dict | None:
        return tool_def.get("parameters", {}).get("properties", {}).get(param_name)

    def _validate_param_type(self, value: Any, schema: dict) -> bool:
        """检查提取的参数类型是否完全贴合标准 JSON Schema 类型契约"""
        expected_type = schema.get("type")
        type_map = {
            "string": lambda v: isinstance(v, str),
            "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
            "null": lambda v: v is None,
        }
        return type_map.get(expected_type, lambda v: True)(value)
