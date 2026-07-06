import re

from loguru import logger

from src.domain.evaluators.strategies.score_parsing import DEFAULT_PARSER
from src.schemas.evaluation import DomainResponse


class ScoreParsingMixin:
    def safe_parse_score(self, llm_output: str) -> float | None:
        result = DEFAULT_PARSER.parse(llm_output)
        if result is not None:
            return result.score
        return None

    def safe_parse_score_with_ci(self, llm_output: str) -> dict | None:
        return DEFAULT_PARSER.parse_with_ci(llm_output)

    def safe_parse_category(self, llm_output: str, allowed_categories: list[str]) -> str | None:
        if not llm_output:
            return None
        cleaned = llm_output.strip().lower().rstrip(".。")
        if cleaned in allowed_categories:
            return cleaned
        pattern = r"\b(" + "|".join(map(re.escape, allowed_categories)) + r")\b"
        match = re.search(pattern, cleaned)
        if match:
            return match.group(1)
        return None

    def _extract_score_by_regex(self, llm_output: str) -> float | None:
        if not llm_output:
            return None
        candidates = re.findall(r"\d+\.?\d*", llm_output)
        for candidate in candidates:
            try:
                value = float(candidate)
                if 0.0 <= value <= 1.0:
                    return value
            except ValueError:
                continue
        return None

    def _evaluate_with_llm(
        self,
        prompt: str,
        fallback_fn=None,
        score_postprocessor=None,
        data_builder=None,
        evaluator_name: str | None = None,
        text: str = "评估完成",
    ) -> DomainResponse:
        eval_name = evaluator_name or type(self).__name__

        try:
            llm_output = self.client.chat(prompt)
            score = self.safe_parse_score(llm_output)

            if score is None:
                score = self._extract_score_by_regex(llm_output)

            if score is None:
                logger.error(f"{eval_name} 响应数字提取失败: '{llm_output}'")
                if fallback_fn:
                    return fallback_fn(f"LLM 响应无法解析为合法分数: '{llm_output}'")
                raise ValueError(f"LLM 响应无法解析为合法分数: '{llm_output}'")

            if score_postprocessor:
                score = score_postprocessor(score)

            data = data_builder(score, llm_output) if data_builder else {"raw_llm_judgment": llm_output}

            return self.create_success_response(text=text, score=score, data=data)

        except Exception as e:
            logger.exception(f"{eval_name} LLM 调用失败，将触发降级评估: {e}")
            if fallback_fn:
                return fallback_fn(str(e))
            raise
