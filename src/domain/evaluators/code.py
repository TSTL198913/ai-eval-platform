import ast

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.metadata import CodeMetadata
from src.domain.evaluators.scoring import (
    is_passing,
    score_keyword_overlap,
    score_text_similarity,
)
from src.schemas.evaluation import DomainResponse

DEFAULT_CODE_PROMPT = (
    "你是一个资深代码审查工程师。请审查代码的语法、潜在 bug 和可读性，并给出简洁的审查结论。"
)

SYNTAX_WEIGHT = 0.3
SEMANTIC_WEIGHT = 0.7


@EvaluatorFactory.register("code")
def create_code_evaluator(client=None):
    return CodeEvaluator(client=client)


class CodeEvaluator(BaseEvaluator):
    def evaluate(self, request) -> DomainResponse:
        code = self.get_payload_data(request, "code") or self.get_input_text(request)
        expected_output = self.get_payload_data(request, "expected_output")
        system_prompt = self.get_payload_data(request, "system_prompt") or DEFAULT_CODE_PROMPT
        meta = CodeMetadata.model_validate(request.metadata or {})

        if not code:
            return DomainResponse(is_valid=False, error="code/text 不能为空")

        syntax_ok, syntax_error = self._check_syntax(code)
        if not syntax_ok:
            return DomainResponse(
                is_valid=False,
                error=syntax_error,
                score=0.0,
                metadata={"language": meta.language},
            )

        # 如果有LLM client，使用LLM审查
        if self.client:
            review_prompt = (
                f"请审查以下 {meta.language} 代码，指出问题与改进建议：\n"
                f"```{meta.language}\n{code}\n```"
            )
            llm_output = self.client.chat(review_prompt, system_prompt=system_prompt)
            score = self._score_review(llm_output, expected_output, syntax_ok)
        else:
            # 无LLM client时，仅基于语法检查评分
            llm_output = f"代码语法检查通过，语言: {meta.language}"
            score = 0.8  # 语法正确，视为通过

        return DomainResponse(
            is_valid=is_passing(score),
            text=llm_output,
            score=score,
            metadata={
                "language": meta.language,
                "style_guide": meta.style_guide,
                "syntax_valid": syntax_ok,
                "expected_output": expected_output,
            },
        )

    def _check_syntax(self, code: str) -> tuple[bool, str]:
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as exc:
            return False, f"语法错误: {exc.msg} (line {exc.lineno})"

    def _score_review(self, llm_output: str, expected_output: str | None, syntax_ok: bool) -> float:
        syntax_score = SYNTAX_WEIGHT if syntax_ok else 0.0

        if not expected_output:
            semantic_score = SEMANTIC_WEIGHT if llm_output.strip() else 0.0
        else:
            similarity = score_text_similarity(llm_output, expected_output)
            keyword = score_keyword_overlap(llm_output, expected_output)
            semantic_score = SEMANTIC_WEIGHT * max(similarity, keyword)

        return min(syntax_score + semantic_score, 1.0)
