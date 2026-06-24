"""
语法(Grammar)评估器 - 2026 工业级标准重构版

用于评估文本的语法质量，包括：
- 语法正确性：句子结构、主谓一致、时态等
- 拼写正确性：单词拼写、标点使用
- 语句流畅性：表达自然、逻辑连贯

工业级特性：
- LLM-as-a-Judge 深度语法分析
- SemanticTaskPolicy 降级策略
- 完整类型注解
- 结构化异常处理
"""

import logging
import re

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.fallback_policy import SemanticTaskPolicy
from src.domain.evaluators.scoring import is_passing
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)


def _simple_grammar_check(text: str) -> tuple[int, list[str]]:
    """简单语法检查（降级策略）"""
    errors = []
    if not text:
        return 0, []

    first_char = text[0]
    if first_char.isalpha() and not first_char.isupper():
        if "\u4e00" <= first_char <= "\u9fff":
            pass
        else:
            errors.append("首字母应大写")

    if not text.endswith((".", "?", "!", "。", "？", "！")):
        errors.append("缺少句末标点")

    consecutive_spaces = re.findall(r" {2,}", text)
    if consecutive_spaces:
        errors.append(f"存在连续空格({len(consecutive_spaces)}处)")

    return len(errors), errors


@EvaluatorFactory.register("grammar")
class GrammarEvaluator(BaseEvaluator):
    def __init__(self, client=None):
        super().__init__(client, fallback_policy=SemanticTaskPolicy())

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        actual_output = self.get_payload_data(request, "actual_output")
        if not actual_output:
            return self.create_error_response(
                error_message="actual_output 不能为空",
                error_code="MISSING_ACTUAL_OUTPUT",
            )

        if self.client:
            return self._evaluate_with_llm(actual_output)
        else:
            return self._evaluate_with_simple_check(actual_output)

    def _evaluate_with_llm(self, actual_output: str) -> DomainResponse:
        """使用 LLM-as-a-Judge 进行深度语法分析"""
        try:
            prompt = self._build_evaluation_prompt(actual_output)
            llm_output = self.client.chat(prompt)

            score, errors = self._parse_grammar_score(llm_output)

            if score is None:
                logger.error(f"语法评估响应解析失败: '{llm_output}'")
                raise ValueError(f"无法解析评分: {llm_output}")

            return self.create_success_response(
                text=actual_output,
                score=score,
                data={
                    "actual_output": actual_output,
                    "raw_output": llm_output,
                    "errors": errors,
                    "evaluator": "grammar",
                },
                metadata={
                    "match_mode": "llm_as_judge",
                    "passed": is_passing(score),
                },
            )

        except Exception as e:
            logger.exception(f"语法评估器 LLM 调用失败: {e}")
            return self._evaluate_with_simple_check(actual_output)

    def _evaluate_with_simple_check(self, actual_output: str) -> DomainResponse:
        """使用简单语法检查进行降级评估"""
        error_count, error_details = _simple_grammar_check(actual_output)
        score = max(0, 1.0 - error_count * 0.2)

        return self.create_success_response(
            text=actual_output,
            score=score,
            data={
                "actual_output": actual_output,
                "error_count": error_count,
                "error_details": error_details,
                "evaluator": "grammar",
                "warning": "使用简单语法检查降级策略，结果可能不准确",
            },
            metadata={
                "match_mode": "simple_check",
                "passed": is_passing(score),
            },
        )

    def _build_evaluation_prompt(self, actual_output: str) -> str:
        """构建语法评估 Prompt"""
        return (
            "你是一个专业的语法和拼写检查专家。请评估以下文本的语法质量。\n"
            "评估维度：\n"
            "1. 语法正确性：句子结构、主谓一致、时态、语态等（权重0.5）\n"
            "2. 拼写正确性：单词拼写、标点使用（权重0.3）\n"
            "3. 语句流畅性：表达自然、逻辑连贯（权重0.2）\n"
            "请：\n"
            "1. 指出具体的语法错误和拼写错误\n"
            "2. 给出每个维度的分数（0.0-1.0）\n"
            "3. 给出加权总分\n"
            "输出格式：语法=X.XX,拼写=X.XX,流畅性=X.XX,总分=X.XX\n错误：[错误1];[错误2];\n\n"
            f"【待检查文本】：{actual_output}\n\n"
            "评估结果："
        )

    def _parse_grammar_score(self, llm_output: str) -> tuple[float | None, list[str]]:
        """解析语法评分"""
        try:
            score = None
            errors = []

            import re

            pattern = r"(语法|拼写|流畅性|总分)=([\d.]+)"
            matches = re.findall(pattern, llm_output)

            for key, value in matches:
                try:
                    if key == "总分":
                        score = float(value)
                        break
                except ValueError:
                    continue

            if score is None:
                total = []
                for key, value in matches:
                    if key in ["语法", "拼写", "流畅性"]:
                        try:
                            total.append(float(value))
                        except ValueError:
                            continue
                if total:
                    weights = [0.5, 0.3, 0.2]
                    score = sum(t * w for t, w in zip(total, weights, strict=False))

            error_pattern = r"错误：(.*)"
            error_match = re.search(error_pattern, llm_output)
            if error_match:
                error_str = error_match.group(1)
                errors = [e.strip() for e in error_str.split(";") if e.strip()]

            return score, errors

        except Exception as e:
            logger.error(f"语法评分解析失败: {e}")
            return None, []
