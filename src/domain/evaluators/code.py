"""
代码评估器

对代码进行语法检查、安全审计和执行验证。
"""

import ast
import asyncio
import logging
import multiprocessing
import os
import sys
import traceback

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.metadata import CodeMetadata
from src.domain.evaluators.scoring import score_keyword_overlap, score_text_similarity
from src.domain.evaluators.security_rules import SAFE_BUILTINS, validate_code_safety
from src.schemas.evaluation import DomainResponse

logger = logging.getLogger(__name__)

DEFAULT_SYNTAX_WEIGHT = 0.20
DEFAULT_EXECUTION_WEIGHT = 0.50
DEFAULT_SEMANTIC_WEIGHT = 0.30

EXECUTION_TIMEOUT = 5.0
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

    def _do_evaluate(self, request) -> DomainResponse:
        """执行代码评估"""
        code = self.get_payload_data(request, "code") or self.get_input_text(request)
        expected_output = self.get_payload_data(request, "expected_output")
        test_cases = self.get_payload_data(request, "test_cases")
        system_prompt = self.get_payload_data(request, "system_prompt") or DEFAULT_CODE_PROMPT
        meta = CodeMetadata.model_validate(request.metadata or {})

        if not code:
            return self.create_error_response(
                error_message="评测代码(code/text) 不能为空",
                error_code="MISSING_CODE",
            )

        syntax_ok, syntax_error = self._check_syntax(code)
        if not syntax_ok:
            return self.create_success_response(
                text=f"代码静态语法检查未通过: {syntax_error}",
                score=0.0,
                data={
                    "language": meta.language,
                    "syntax_valid": False,
                    "execution_score": 0.0,
                    "semantic_score": 0.0,
                },
            )

        safety_ok, safety_error = validate_code_safety(code)
        if not safety_ok:
            return self.create_success_response(
                text=f"代码安全合规性审计未通过拦截: {safety_error}",
                score=0.0,
                data={
                    "language": meta.language,
                    "safety_valid": False,
                    "security_violation": True,
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

        if self.client:
            review_prompt = (
                f"请审查以下 {meta.language} 代码，指出问题与改进建议：\n"
                f"```{meta.language}\n{code}\n```"
            )
            llm_output = self.client.chat(review_prompt, system_prompt=system_prompt)
            raw_semantic_score = self._score_semantic(llm_output, expected_output)
        else:
            llm_output = None
            raw_semantic_score = 0.0

        request_meta = request.metadata or {}
        w_syntax = request_meta.get("weight_syntax", DEFAULT_SYNTAX_WEIGHT)
        w_exec = request_meta.get("weight_execution", DEFAULT_EXECUTION_WEIGHT)
        w_semantic = request_meta.get("weight_semantic", DEFAULT_SEMANTIC_WEIGHT)

        total_w = w_syntax + w_exec + w_semantic
        if total_w > 0:
            w_syntax, w_exec, w_semantic = (
                w_syntax / total_w,
                w_exec / total_w,
                w_semantic / total_w,
            )

        syntax_score_part = w_syntax if syntax_ok else 0.0
        execution_score_part = raw_execution_rate * w_exec
        semantic_score_part = raw_semantic_score * w_semantic

        total_score = syntax_score_part + execution_score_part + semantic_score_part

        if not self.client and syntax_ok and not test_cases:
            total_score = 0.8

        total_score = round(min(max(total_score, 0.0), 1.0), 4)
        response_text = self._build_response_text(llm_output, execution_details)

        return self.create_success_response(
            text=response_text,
            score=total_score,
            data={
                "language": meta.language,
                "style_guide": meta.style_guide,
                "syntax_valid": syntax_ok,
                "scores_breakdown": {
                    "syntax": round(syntax_score_part, 4),
                    "execution": round(execution_score_part, 4),
                    "semantic": round(semantic_score_part, 4),
                },
                "execution_details": execution_details,
            },
        )

    async def evaluate_async(self, request) -> DomainResponse:
        """异步评估入口"""
        return await asyncio.to_thread(self.evaluate, request)

    def _check_syntax(self, code: str) -> tuple[bool, str]:
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as exc:
            return False, f"语法错误: {exc.msg} (第 {exc.lineno} 行)"

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
                raise TimeoutError(f"沙箱执行超时，超过限制的 {EXECUTION_TIMEOUT} 秒")

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
