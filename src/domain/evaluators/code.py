"""
代码评估器

对代码进行语法检查、安全审计和执行验证。
"""

import ast
import asyncio
import logging
import multiprocessing
import os
import re
import sys
import traceback

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.metadata import CodeMetadata
from src.domain.evaluators.scoring import score_keyword_overlap
from src.domain.evaluators.scoring import score_text_similarity
from src.domain.evaluators.security_rules import SAFE_BUILTINS
from src.domain.evaluators.security_rules import detect_security_vulnerabilities
from src.domain.evaluators.security_rules import format_security_report
from src.domain.evaluators.security_rules import validate_code_safety
from src.schemas.evaluation import DomainResponse

logger = logging.getLogger(__name__)

DEFAULT_SYNTAX_WEIGHT = 0.15
DEFAULT_EXECUTION_WEIGHT = 0.40
DEFAULT_SEMANTIC_WEIGHT = 0.15
DEFAULT_QUALITY_WEIGHT = 0.25
DEFAULT_SECURITY_WEIGHT = 0.05

# 🧠 2026 架构：沙箱执行超时配置
# Windows 下 multiprocessing 使用 spawn 模式，启动开销较大，需要更长超时
EXECUTION_TIMEOUT = 5.0 if sys.platform != "win32" else 15.0  # Windows: 15秒
MAX_MEMORY_MB = 256

DEFAULT_CODE_PROMPT = (
    "你是一个资深代码审查工程师。请审查代码的语法、潜在 bug 和可读性，并给出简洁的审查结论。"
)


def _safe_exec_batch_worker(
    code: str, func_name: str, test_cases: list, max_memory_mb: int, queue: multiprocessing.Queue
):
    """在隔离的子进程中安全执行测试用例"""
    try:
        if sys.platform != "win32":
            import resource

            mem_limit_bytes = max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_limit_bytes, mem_limit_bytes))

        sys.path.insert(0, os.getcwd())
        exec_globals = {"__builtins__": SAFE_BUILTINS.copy()}

        exec(code, exec_globals)

        if func_name not in exec_globals:
            queue.put(
                {"success": False, "error": f"目标函数 {func_name} 未定义或被沙箱安全策略拦截"}
            )
            return

        func = exec_globals[func_name]
        batch_results = []

        for idx, case in enumerate(test_cases):
            inputs = case.get("input", [])
            expected = case.get("expected")
            case_res = {
                "case_id": idx,
                "input": inputs,
                "expected": expected,
                "passed": False,
                "actual": None,
                "error": None,
            }

            try:
                actual = func(*inputs)
                case_res["actual"] = actual
                case_res["passed"] = actual == expected
            except Exception as case_exc:
                case_res["error"] = str(case_exc)

            batch_results.append(case_res)

        queue.put({"success": True, "results": batch_results})

    except Exception as global_exc:
        queue.put(
            {
                "success": False,
                "error": f"沙箱运行时异常: {str(global_exc)}",
                "traceback": traceback.format_exc(),
            }
        )


@EvaluatorFactory.register("code")
class CodeEvaluator(BaseEvaluator):
    """代码综合能力评估器"""

    def __init__(self, client=None, fallback_policy=None):
        super().__init__(
            client=client,
            fallback_policy=fallback_policy,
            require_input=True,
            require_expected=False,
        )

    def validate_input(self, request) -> DomainResponse | None:
        """验证代码输入是否有效

        重写基类方法：CodeEvaluator 的输入字段是 code，而不是 user_input/text。
        """
        code = self.get_payload_data(request, "code") or self.get_payload_data(request, "actual_output") or self.get_input_text(request)
        if not code or (isinstance(code, str) and not code.strip()):
            return self.create_cannot_evaluate_response(
                reason="code/actual_output/user_input/text 不能为空",
                dimensions_skipped=["code_evaluation"],
            )
        return None

    def _do_evaluate(self, request) -> DomainResponse:
        """执行代码评估"""
        if error := self.validate_input(request):
            return error

        code = self.get_payload_data(request, "code") or self.get_payload_data(request, "actual_output") or self.get_input_text(request)
        expected_output = self.get_payload_data(request, "expected_output")
        test_cases = self.get_payload_data(request, "test_cases")
        system_prompt = self.get_payload_data(request, "system_prompt") or DEFAULT_CODE_PROMPT
        meta = CodeMetadata.model_validate(request.metadata or {})

        syntax_ok, syntax_error = self._check_syntax(code)
        if not syntax_ok:
            return self.create_success_response(
                text=f"代码静态语法检查未通过: {syntax_error}",
                score=0.0,
                metadata={
                    "language": meta.language,
                    "syntax_valid": False,
                },
            )

        structure_ok, structure_error = self._check_code_structure(code)
        if not structure_ok:
            return self.create_success_response(
                text=f"代码结构校验未通过: {structure_error}",
                score=0.3,
                metadata={
                    "language": meta.language,
                    "syntax_valid": True,
                    "structure_valid": False,
                },
            )

        safety_ok, safety_error = validate_code_safety(code)
        security_vulns = detect_security_vulnerabilities(code)
        has_critical_vuln = security_vulns["summary"]["critical"] > 0
        has_high_vuln = security_vulns["summary"]["high"] > 0
        execution_details = {}
        
        if not safety_ok:
            return self.create_success_response(
                text=f"代码安全合规性审计未通过拦截: {safety_error}",
                score=0.2,
                metadata={
                    "language": meta.language,
                    "safety_valid": False,
                    "security_violation": True,
                },
            )
        
        if has_high_vuln or has_critical_vuln:
            report = format_security_report(security_vulns)
            vuln_score = security_vulns["score"]
            final_score = max(0.0, vuln_score * 0.5)
            return self.create_success_response(
                text=f"代码存在安全漏洞: {report}",
                score=final_score,
                data={
                    "security_vulnerabilities": security_vulns,
                    "execution_details": execution_details,
                    "confidence_components": {
                        "evaluation_method": "static_analysis",
                        "security_scan": "vulnerabilities_found",
                        "confidence_breakdown": {"security": vuln_score},
                    },
                },
                metadata={
                    "language": meta.language,
                    "safety_valid": False,
                    "security_vulnerabilities": security_vulns,
                },
            )

        execution_results = []
        execution_details = {}

        if test_cases and meta.language == "python":
            execution_results = self._execute_test_cases_sandboxed(code, test_cases)
            passed_count = sum(1 for r in execution_results if r["passed"])
            total_count = len(execution_results)
            raw_execution_rate = (passed_count / total_count) if total_count > 0 else 0.0
            execution_details = {
                "passed": passed_count,
                "total": total_count,
                "results": execution_results,
            }
        else:
            raw_execution_rate = 0.0

        llm_score = 0.0
        llm_output = None
        
        if self.client:
            review_prompt = (
                f"请审查以下 {meta.language} 代码，指出问题与改进建议：\n"
                f"```{meta.language}\n{code}\n```"
            )
            llm_output = self.client.chat(review_prompt, system_prompt=system_prompt)
            llm_score = self._parse_llm_score(llm_output)
        else:
            llm_output = None
            llm_score = 0.0

        code_quality_score = self._evaluate_code_quality(code)
        text_similarity_score = 0.0
        if expected_output:
            if expected_output == code:
                text_similarity_score = 1.0
            else:
                text_similarity_score = self._calculate_text_similarity(code, expected_output)

        has_execution_capability = bool(test_cases and meta.language == "python")
        has_semantic_capability = bool(self.client)
        has_text_similarity = bool(expected_output)

        if not has_execution_capability and not has_semantic_capability and not has_text_similarity:
            security_vulns = detect_security_vulnerabilities(code)
            security_score = security_vulns["score"]
            has_vulns = security_vulns["summary"]["total"] > 0
            
            if has_vulns:
                degraded_score = max(0.3, security_score * 0.8)
            else:
                degraded_score = 0.9 * code_quality_score
            
            return self.create_partial_response(
                text=f"代码语法检查通过（{meta.language}），安全扫描{'' if has_vulns else '未'}发现漏洞，但缺少测试用例、LLM客户端和期望输出，无法进行完整评估",
                score=round(degraded_score, 4),
                dimensions_evaluated=["syntax", "security", "quality"],
                dimensions_skipped=["execution", "semantic", "similarity"],
                skip_reasons={
                    "execution": "缺少测试用例或非Python语言",
                    "semantic": "缺少LLM客户端",
                    "similarity": "缺少期望输出",
                },
                data={
                    "language": meta.language,
                    "style_guide": meta.style_guide,
                    "syntax_valid": True,
                    "security_vulnerabilities": security_vulns,
                    "code_quality_score": code_quality_score,
                    "scores_breakdown": {
                        "syntax": 0.3,
                        "security": 0.4 * security_score,
                        "quality": 0.3 * code_quality_score,
                        "execution": 0.0,
                        "semantic": 0.0,
                        "similarity": 0.0,
                    },
                },
            )

        request_meta = request.metadata or {}
        w_syntax = request_meta.get("weight_syntax", DEFAULT_SYNTAX_WEIGHT)
        w_exec = request_meta.get("weight_execution", DEFAULT_EXECUTION_WEIGHT)
        w_semantic = request_meta.get("weight_semantic", DEFAULT_SEMANTIC_WEIGHT)
        w_quality = request_meta.get("weight_quality", DEFAULT_QUALITY_WEIGHT)
        w_security = request_meta.get("weight_security", DEFAULT_SECURITY_WEIGHT)
        w_similarity = 0.10

        if not has_execution_capability:
            w_syntax += w_exec * 0.20
            w_semantic += w_exec * 0.30
            w_quality += w_exec * 0.35
            w_similarity += w_exec * 0.15
            w_exec = 0.0

        if not has_semantic_capability:
            w_syntax += w_semantic * 0.20
            w_exec += w_semantic * 0.25
            w_quality += w_semantic * 0.35
            w_similarity += w_semantic * 0.20
            w_semantic = 0.0

        if not has_text_similarity:
            w_quality += w_similarity * 0.6
            w_syntax += w_similarity * 0.4
            w_similarity = 0.0

        total_w = w_syntax + w_exec + w_semantic + w_quality + w_security + w_similarity
        if total_w > 0:
            w_syntax, w_exec, w_semantic, w_quality, w_security, w_similarity = (
                w_syntax / total_w,
                w_exec / total_w,
                w_semantic / total_w,
                w_quality / total_w,
                w_security / total_w,
                w_similarity / total_w,
            )

        security_vulns = detect_security_vulnerabilities(code)
        security_score = security_vulns["score"]

        syntax_score_part = w_syntax if syntax_ok else 0.0
        execution_score_part = raw_execution_rate * w_exec
        semantic_score_part = llm_score * w_semantic
        quality_score_part = code_quality_score * w_quality
        security_score_part = security_score * w_security
        similarity_score_part = text_similarity_score * w_similarity

        total_score = (
            syntax_score_part
            + execution_score_part
            + semantic_score_part
            + quality_score_part
            + security_score_part
            + similarity_score_part
        )
        
        if has_critical_vuln:
            total_score *= 0.3
        elif has_high_vuln:
            total_score *= 0.5
            
        total_score = round(min(max(total_score, 0.0), 1.0), 4)

        response_text = self._build_response_text(llm_output, execution_details)

        evaluated_dims = ["syntax", "quality"]
        skipped_dims = []
        if has_execution_capability:
            evaluated_dims.append("execution")
        else:
            skipped_dims.append("execution")
        if has_semantic_capability:
            evaluated_dims.append("semantic")
        else:
            skipped_dims.append("semantic")
        if has_text_similarity:
            evaluated_dims.append("similarity")
        else:
            skipped_dims.append("similarity")

        if skipped_dims:
            return self.create_partial_response(
                text=response_text,
                score=total_score,
                dimensions_evaluated=evaluated_dims,
                dimensions_skipped=skipped_dims,
                skip_reasons={
                    "execution": "缺少测试用例或非Python语言" if "execution" in skipped_dims else None,
                    "semantic": "缺少LLM客户端" if "semantic" in skipped_dims else None,
                    "similarity": "缺少期望输出" if "similarity" in skipped_dims else None,
                },
                data={
                    "language": meta.language,
                    "style_guide": meta.style_guide,
                    "syntax_valid": syntax_ok,
                    "code_quality_score": code_quality_score,
                    "text_similarity_score": text_similarity_score,
                    "scores_breakdown": {
                        "syntax": round(syntax_score_part, 4),
                        "execution": round(execution_score_part, 4),
                        "semantic": round(semantic_score_part, 4),
                        "quality": round(quality_score_part, 4),
                        "similarity": round(similarity_score_part, 4),
                    },
                    "execution_details": execution_details,
                },
            )

        return self.create_success_response(
            text=response_text,
            score=total_score,
            data={
                "language": meta.language,
                "style_guide": meta.style_guide,
                "syntax_valid": syntax_ok,
                "code_quality_score": code_quality_score,
                "text_similarity_score": text_similarity_score,
                "scores_breakdown": {
                    "syntax": round(syntax_score_part, 4),
                    "execution": round(execution_score_part, 4),
                    "semantic": round(semantic_score_part, 4),
                    "quality": round(quality_score_part, 4),
                    "similarity": round(similarity_score_part, 4),
                },
                "execution_details": execution_details,
            },
        )

    async def evaluate_async(self, request) -> DomainResponse:
        """异步评估入口"""
        return await asyncio.to_thread(self.evaluate, request)

    def _evaluate_code_quality(self, code: str) -> float:
        """评估代码质量（基于静态分析指标）

        评分模式：基础分0.60，通过正向特征加分，负向特征扣分

        评分维度：
        正向特征（加分）：
        1. 函数/类定义：+0.10
        2. 多个函数或类：+0.05
        3. 错误处理（try/except）：+0.08
        4. 类型注解：+0.05
        5. 文档字符串：+0.05
        6. 参数验证（assert/raise）：+0.05
        7. 合理代码结构（深度<=2）：+0.05
        8. 适当注释（>8%）：+0.02
        9. 代码行数适中（5-200行）：+0.05

        负向特征（扣分）：
        1. 魔法数字：-0.05 ~ -0.15
        2. 重复代码：-0.08 ~ -0.20
        3. 过长行：-0.05 ~ -0.10
        4. 无函数定义（纯脚本）：-0.10
        5. 无注释（<1%）：-0.05
        6. 代码过短（<3行）：-0.05
        7. 嵌套过深（>5层）：-0.05
        """
        lines = code.split('\n')
        total_lines = len(lines)
        
        if total_lines == 0:
            return 0.0

        score = 0.60

        has_functions_or_classes = False
        has_error_handling = False
        has_type_annotations = False
        has_docstrings = False
        has_param_validation = False
        has_imports = False

        try:
            tree = ast.parse(code)
            max_depth = 0
            func_count = 0
            class_count = 0
            total_nodes = 0
            
            def count_depth(node, depth=0):
                nonlocal max_depth, func_count, class_count, total_nodes, has_functions_or_classes, has_error_handling, has_type_annotations, has_docstrings, has_imports
                max_depth = max(max_depth, depth)
                total_nodes += 1
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            func_count += 1
                            has_functions_or_classes = True
                            if child.args.args:
                                for arg in child.args.args:
                                    if arg.annotation:
                                        has_type_annotations = True
                            if child.body and isinstance(child.body[0], (ast.Expr,)):
                                if isinstance(child.body[0].value, (ast.Constant,)):
                                    if isinstance(child.body[0].value.value, str) and len(child.body[0].value.value) > 10:
                                        has_docstrings = True
                        elif isinstance(child, ast.ClassDef):
                            class_count += 1
                            has_functions_or_classes = True
                            if child.body and isinstance(child.body[0], (ast.Expr,)):
                                if isinstance(child.body[0].value, (ast.Constant,)):
                                    if isinstance(child.body[0].value.value, str) and len(child.body[0].value.value) > 10:
                                        has_docstrings = True
                        elif isinstance(child, ast.Try):
                            has_error_handling = True
                        count_depth(child, depth + 1)
                    elif isinstance(child, (ast.Import, ast.ImportFrom)):
                        has_imports = True
            
            count_depth(tree)

            if has_functions_or_classes:
                score += 0.10
                if func_count >= 2 or class_count >= 1:
                    score += 0.05
            else:
                score -= 0.10

            if has_error_handling:
                score += 0.08
            if has_type_annotations:
                score += 0.05
            if has_docstrings:
                score += 0.05
            if has_imports:
                score += 0.02

            if max_depth <= 2:
                score += 0.05
            elif max_depth <= 4:
                score += 0.02
            elif max_depth > 5:
                score -= 0.05

            for node in ast.walk(tree):
                if isinstance(node, ast.Assert) or isinstance(node, ast.Raise):
                    has_param_validation = True
                    break
            if has_param_validation:
                score += 0.05

        except SyntaxError:
            pass

        comment_lines = sum(1 for line in lines if line.strip().startswith(('#', '//', '/*', '*')))
        if total_lines > 10:
            comment_ratio = comment_lines / total_lines
            if comment_ratio >= 0.08:
                score += 0.03
            elif comment_ratio >= 0.03:
                score += 0.01
            elif comment_ratio < 0.01:
                score -= 0.05

        if total_lines >= 5 and total_lines <= 200:
            score += 0.05
        elif total_lines >= 3 and total_lines <= 500:
            score += 0.02
        elif total_lines < 3:
            score -= 0.05

        magic_numbers = []
        for line in lines:
            numbers = re.findall(r'\b([2-9]\d*)\b', line.strip())
            for num in numbers:
                if num not in ('10', '100', '1000', '25', '50', '0', '1'):
                    magic_numbers.append(num)
        
        magic_count = len(magic_numbers)
        if magic_count > 8:
            score -= 0.15
        elif magic_count > 5:
            score -= 0.10
        elif magic_count > 3:
            score -= 0.05

        unique_lines = set(lines)
        duplicate_ratio = 1 - (len(unique_lines) / total_lines)
        if duplicate_ratio > 0.4:
            score -= 0.20
        elif duplicate_ratio > 0.25:
            score -= 0.12
        elif duplicate_ratio > 0.15:
            score -= 0.06

        long_lines = sum(1 for line in lines if len(line) > 120)
        if long_lines > 8:
            score -= 0.10
        elif long_lines > 5:
            score -= 0.07
        elif long_lines > 3:
            score -= 0.04

        return round(max(0.0, min(1.0, score)), 4)

    def _check_syntax(self, code: str) -> tuple[bool, str]:
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as exc:
            return False, f"语法错误: {exc.msg} (第 {exc.lineno} 行)"

    def _check_code_structure(self, code: str) -> tuple[bool, str | None]:
        """检查代码是否包含有效的代码结构（而非纯文本/简单表达式）

        Python 3 支持 Unicode 标识符，纯文本（如"写一个Python函数"）也能通过
        ast.parse() 语法检查（被解析为一个 Name 表达式）。此方法验证代码是否
        包含真实的代码结构元素（函数、类、控制流、函数调用等），防止纯文本被误判为有效代码。
        """
        try:
            tree = ast.parse(code)
            has_structure = any(
                isinstance(node, (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                    ast.If,
                    ast.For,
                    ast.AsyncFor,
                    ast.While,
                    ast.Try,
                    ast.With,
                    ast.AsyncWith,
                    ast.Import,
                    ast.ImportFrom,
                    ast.Assign,
                    ast.AugAssign,
                    ast.AnnAssign,
                    ast.Return,
                    ast.Yield,
                    ast.YieldFrom,
                    ast.Raise,
                    ast.Assert,
                    ast.Global,
                    ast.Nonlocal,
                    ast.Pass,
                    ast.Break,
                    ast.Continue,
                    ast.Delete,
                    ast.Call,
                ))
                for node in ast.walk(tree)
            )
            if not has_structure:
                return False, "代码缺少有效结构（无函数、类、控制流、函数调用等），可能不是有效代码"
            return True, None
        except SyntaxError:
            return True, None

    def _execute_test_cases_sandboxed(self, code: str, test_cases: list) -> list:
        """使用沙箱执行测试用例"""
        func_match = None
        try:
            for node in ast.walk(ast.parse(code)):
                if isinstance(node, ast.FunctionDef):
                    func_match = node.name
                    break
        except Exception as e:
            logger.warning(f"AST 解析失败，无法定位顶层函数: {e}")

        if not func_match:
            return [
                {
                    "case_id": i,
                    "input": c.get("input", []),
                    "expected": c.get("expected"),
                    "passed": False,
                    "actual": None,
                    "error": "无法在评测代码中定位到有效的顶层函数定义",
                }
                for i, c in enumerate(test_cases)
            ]

        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()

        process = ctx.Process(
            target=_safe_exec_batch_worker,
            args=(code, func_match, test_cases, MAX_MEMORY_MB, queue),
            daemon=True,
        )

        results = []
        try:
            process.start()
            process.join(timeout=EXECUTION_TIMEOUT)

            if process.is_alive():
                process.terminate()
                process.join(timeout=1.0)
                if process.is_alive():
                    process.kill()
                raise TimeoutError(f"沙箱执行超时，超过限制的 {EXECUTION_TIMEOUT} 秒（平台: {sys.platform}）")

            if queue.empty():
                raise RuntimeError("沙箱进程异常失联，未能返回评测结果")

            worker_result = queue.get()
            if worker_result.get("success"):
                results = worker_result.get("results", [])
            else:
                raise RuntimeError(worker_result.get("error", "沙箱内部未知崩溃"))

        except TimeoutError as te:
            logger.warning(f"Code sandbox timeout: {str(te)}")
            results = [
                {
                    "case_id": i,
                    "input": c.get("input", []),
                    "expected": c.get("expected"),
                    "passed": False,
                    "actual": None,
                    "error": f"Execution Timeout: {str(te)}",
                }
                for i, c in enumerate(test_cases)
            ]
        except Exception as ge:
            logger.error(f"Code sandbox runtime crash: {str(ge)}")
            results = [
                {
                    "case_id": i,
                    "input": c.get("input", []),
                    "expected": c.get("expected"),
                    "passed": False,
                    "actual": None,
                    "error": f"Sandbox Error: {str(ge)}",
                }
                for i, c in enumerate(test_cases)
            ]

        return results

    def _score_semantic(self, llm_output: str | None, expected_output: str | None) -> float:
        if not llm_output or not expected_output:
            return 0.0
        similarity = score_text_similarity(llm_output, expected_output)
        keyword = score_keyword_overlap(llm_output, expected_output)
        return max(similarity, keyword)

    def _parse_llm_score(self, llm_output: str | None) -> float:
        """解析LLM返回的评分字符串为浮点数

        LocalScoringClient返回的是评分字符串（如"0.85"），
        直接解析为浮点数作为语义分。
        """
        if not llm_output:
            return 0.0
        try:
            # 尝试直接解析为浮点数
            score = float(llm_output.strip())
            return max(0.0, min(1.0, score))
        except (ValueError, AttributeError):
            # 如果解析失败，尝试从字符串中提取数字
            import re
            match = re.search(r'(\d+\.?\d*)', llm_output)
            if match:
                try:
                    score = float(match.group(1))
                    return max(0.0, min(1.0, score))
                except ValueError:
                    pass
            return 0.0

    def _build_response_text(self, llm_output: str | None, execution_details: dict) -> str:
        parts = []
        if execution_details:
            passed = execution_details.get("passed", 0)
            total = execution_details.get("total", 0)
            parts.append(f"安全沙箱用例通过率: {passed}/{total}")

        if llm_output:
            parts.append(f"智能审查结论: {llm_output}")
        elif not execution_details:
            parts.append("静态语法与合规性审查安全通过")

        return " | ".join(parts) if parts else "代码评测流正常完成"
