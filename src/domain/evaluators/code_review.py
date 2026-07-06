"""
代码审查评估器

综合评估代码的安全漏洞和质量。
"""

import ast
import asyncio
import re

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.code import CodeEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.security_rules import detect_security_vulnerabilities
from src.domain.evaluators.security_rules import format_security_report
from src.schemas.evaluation import DomainResponse

DEFAULT_SECURITY_WEIGHT = 0.55
DEFAULT_QUALITY_WEIGHT = 0.25
DEFAULT_COMPLEXITY_WEIGHT = 0.12
DEFAULT_MAINTAINABILITY_WEIGHT = 0.08


@EvaluatorFactory.register("code_review")
class CodeReviewEvaluator(BaseEvaluator):
    """综合代码审查评估器"""

    def __init__(self, client=None):
        super().__init__(client=client)
        self._delegate = CodeEvaluator(client=client)

    def _do_evaluate(self, request) -> DomainResponse:
        """执行安全扫描与代码质量评估"""
        code = self.get_payload_data(request, "code") or self.get_input_text(request)
        if not code:
            return self.create_error_response(
                error_message="评测代码不能为空",
                error_code="MISSING_CODE",
            )

        security_result = detect_security_vulnerabilities(code)
        quality_response = self._delegate._do_evaluate(request)

        security_score = security_result["score"]
        quality_score = quality_response.score

        complexity_score = self._evaluate_complexity(code)
        maintainability_score = self._evaluate_maintainability(code)

        request_meta = request.metadata or {}
        w_security = request_meta.get("weight_security", DEFAULT_SECURITY_WEIGHT)
        w_quality = request_meta.get("weight_quality", DEFAULT_QUALITY_WEIGHT)
        w_complexity = request_meta.get("weight_complexity", DEFAULT_COMPLEXITY_WEIGHT)
        w_maintainability = request_meta.get("weight_maintainability", DEFAULT_MAINTAINABILITY_WEIGHT)

        critical_count = sum(1 for v in security_result["vulnerabilities"] if v["severity"] == "critical")
        high_count = sum(1 for v in security_result["vulnerabilities"] if v["severity"] == "high")
        medium_count = sum(1 for v in security_result["vulnerabilities"] if v["severity"] == "medium")
        low_count = sum(1 for v in security_result["vulnerabilities"] if v["severity"] == "low")

        security_penalty = critical_count * 0.3 + high_count * 0.15 + medium_count * 0.05 + low_count * 0.02
        security_score = max(0.0, security_score - security_penalty)

        if critical_count >= 2:
            security_score *= 0.3
        elif critical_count >= 1:
            security_score *= 0.5
        elif high_count >= 2:
            security_score *= 0.6

        has_critical_or_high = critical_count > 0 or high_count > 0
        if has_critical_or_high:
            w_security = 0.6
            w_quality = 0.2
            w_complexity = 0.1
            w_maintainability = 0.1
        else:
            total_w = w_security + w_quality + w_complexity + w_maintainability
            if total_w > 0:
                w_security = w_security / total_w
                w_quality = w_quality / total_w
                w_complexity = w_complexity / total_w
                w_maintainability = w_maintainability / total_w

        expected_output = self.get_payload_data(request, "expected_output")
        similarity_score = 0.0
        if expected_output:
            from src.domain.evaluators.scoring import score_text_similarity
            similarity_score = score_text_similarity(code, expected_output)

        if expected_output:
            w_similarity = 0.30
            remaining = 1.0 - w_similarity
            total_score = (
                security_score * w_security * remaining * 0.85
                + quality_score * w_quality * remaining * 0.85
                + complexity_score * w_complexity * remaining * 0.8
                + maintainability_score * w_maintainability * remaining * 0.8
                + similarity_score * w_similarity
            )
        else:
            total_score = (
                security_score * w_security * 0.80
                + quality_score * w_quality * 0.80
                + complexity_score * w_complexity * 0.75
                + maintainability_score * w_maintainability * 0.75
            )
        
        if security_score < 0.4:
            total_score *= 0.5
        elif security_score < 0.6:
            total_score *= 0.7
        elif security_score < 0.8:
            total_score *= 0.9
            
        if complexity_score < 0.5:
            total_score *= 0.85
            
        total_score = round(min(max(total_score, 0.0), 1.0), 4)

        response_parts = []
        if security_result["vulnerabilities"]:
            response_parts.append(format_security_report(security_result))
        if quality_response.text:
            response_parts.append(quality_response.text)

        return self.create_success_response(
            text=" | ".join(response_parts) if response_parts else "代码综合审查安全通过",
            score=total_score,
            data={
                **(quality_response.data or {}),
                "security_score": security_score,
                "security_summary": security_result["summary"],
                "security_vulnerabilities": security_result["vulnerabilities"],
                "complexity_score": complexity_score,
                "maintainability_score": maintainability_score,
                "weights_applied": {
                    "security": round(w_security, 2),
                    "quality": round(w_quality, 2),
                    "complexity": round(w_complexity, 2),
                    "maintainability": round(w_maintainability, 2),
                },
            },
        )

    def _evaluate_complexity(self, code: str) -> float:
        """评估代码复杂度（基于圈复杂度的连续函数）

        圈复杂度 = 1 + 分支数 + 循环数 + 异常处理数 + 逻辑运算符数
        复杂度评分使用分段线性函数，更精细地区分不同复杂度级别：
        - 圈复杂度 <= 5: 满分
        - 圈复杂度 6-10: 轻微扣分
        - 圈复杂度 11-15: 中等扣分
        - 圈复杂度 16-20: 严重扣分
        - 圈复杂度 > 20: 极低分
        """
        try:
            tree = ast.parse(code)
            
            cyclomatic_complexity = 1
            max_depth = 0
            func_count = 0
            total_branches = 0
            
            def analyze_node(node, depth=0):
                nonlocal cyclomatic_complexity, max_depth, func_count, total_branches
                max_depth = max(max_depth, depth)
                
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_count += 1
                    cyclomatic_complexity += 1
                elif isinstance(node, ast.If):
                    cyclomatic_complexity += 1
                    total_branches += 1
                elif isinstance(node, (ast.For, ast.While)):
                    cyclomatic_complexity += 1
                    total_branches += 1
                elif isinstance(node, ast.Try):
                    cyclomatic_complexity += 1
                    total_branches += 1
                elif isinstance(node, (ast.And, ast.Or)):
                    cyclomatic_complexity += 1
                
                for child in ast.iter_child_nodes(node):
                    analyze_node(child, depth + 1)
            
            analyze_node(tree)
            
            if cyclomatic_complexity <= 5:
                complexity_score = 1.0
            elif cyclomatic_complexity <= 10:
                complexity_score = 1.0 - (cyclomatic_complexity - 5) * 0.04
            elif cyclomatic_complexity <= 15:
                complexity_score = 0.80 - (cyclomatic_complexity - 10) * 0.06
            elif cyclomatic_complexity <= 20:
                complexity_score = 0.50 - (cyclomatic_complexity - 15) * 0.08
            else:
                complexity_score = max(0.1, 0.10 - (cyclomatic_complexity - 20) * 0.01)
            
            depth_penalty = 1.0
            if max_depth > 8:
                depth_penalty = 0.4
            elif max_depth > 6:
                depth_penalty = 0.6
            elif max_depth > 4:
                depth_penalty = 0.8
            elif max_depth > 3:
                depth_penalty = 0.95
            
            function_bonus = 1.0
            if func_count >= 3:
                function_bonus = 1.05
            elif func_count >= 1:
                function_bonus = 1.0
            else:
                function_bonus = 0.75
            
            score = complexity_score * depth_penalty * function_bonus
            
            return round(max(0.0, min(1.0, score)), 4)
        except SyntaxError:
            return 0.3

    def _evaluate_maintainability(self, code: str) -> float:
        """评估代码可维护性"""
        lines = code.split('\n')
        total_lines = len(lines)
        
        if total_lines == 0:
            return 0.0

        score = 0.75

        comment_lines = sum(1 for line in lines if line.strip().startswith(('#', '//', '/*', '*')))
        if total_lines > 10:
            comment_ratio = comment_lines / total_lines
            if comment_ratio < 0.03:
                score -= 0.10
            elif comment_ratio < 0.08:
                score -= 0.03

        magic_numbers = []
        for line in lines:
            numbers = re.findall(r'\b([2-9]\d*)\b', line.strip())
            for num in numbers:
                if num not in ('10', '100', '1000', '25', '50'):
                    magic_numbers.append(num)
        
        if len(magic_numbers) > 8:
            score -= 0.10
        elif len(magic_numbers) > 3:
            score -= 0.03

        unique_lines = set(lines)
        duplicate_ratio = 1 - (len(unique_lines) / total_lines)
        if duplicate_ratio > 0.4:
            score -= 0.15
        elif duplicate_ratio > 0.15:
            score -= 0.05

        long_lines = sum(1 for line in lines if len(line) > 120)
        if long_lines > 8:
            score -= 0.08
        elif long_lines > 3:
            score -= 0.03

        return round(max(0.0, min(1.0, score)), 4)

    async def evaluate_async(self, request) -> DomainResponse:
        """异步评估入口"""
        return await asyncio.to_thread(self.evaluate, request)
