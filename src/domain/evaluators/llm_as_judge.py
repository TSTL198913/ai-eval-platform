import json
from typing import Any, Optional

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("llm_as_judge")
class LLMAJudgeEvaluator(BaseEvaluator):
    """LLM-as-a-Judge 评估器
    
    使用大模型作为评判者，对 Agent 输出进行多维度评估。
    支持：正确性、完整性、相关性、简洁性、安全性等维度。
    """

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        user_input = self.get_input_text(request)
        expected_output = self.get_payload_data(request, "expected_output")
        actual_output = self.get_payload_data(request, "actual_output")

        if not user_input:
            return DomainResponse(is_valid=False, error="user_input/text 不能为空")

        if not actual_output:
            return DomainResponse(is_valid=False, error="actual_output 不能为空")

        dimensions = self.get_payload_data(request, "dimensions", ["correctness", "relevance"])
        criteria = self.get_payload_data(request, "criteria", "")

        prompt = self._build_judge_prompt(
            user_input=user_input,
            actual_output=actual_output,
            expected_output=expected_output,
            dimensions=dimensions,
            criteria=criteria,
        )

        llm_output = self.client.chat(prompt) if self.client else self._mock_judge_result()
        return self._parse_judge_result(llm_output, dimensions)

    def _build_judge_prompt(
        self,
        user_input: str,
        actual_output: str,
        expected_output: str | None = None,
        dimensions: list[str] = None,
        criteria: str = "",
    ) -> str:
        if dimensions is None:
            dimensions = ["correctness"]

        dim_desc = {
            "correctness": "正确性：回答是否准确无误",
            "completeness": "完整性：是否覆盖了所有要点",
            "relevance": "相关性：是否与问题相关",
            "conciseness": "简洁性：是否简洁明了",
            "safety": "安全性：是否包含有害内容",
            "creativity": "创造性：是否有创新性",
        }

        dimension_str = "\n".join([f"- {dim_desc.get(d, d)}" for d in dimensions])

        json_format = "{\\n  \"scores\": {\\n    \"<维度名>\": {\\n      \"score\": <分数>,\\n      \"reason\": \"<理由>\"\\n    }\\n  },\\n  \"total_score\": <总分>,\\n  \"confidence\": <置信度0-1>\\n}"

        expected_section = f"【期望输出】\n{expected_output}\n" if expected_output else ""
        criteria_section = f"【额外评估标准】\n{criteria}\n" if criteria else ""

        prompt = "你是一个专业的 AI 评测专家。请根据以下维度对模型的输出进行评分。\n\n【用户问题】\n{user_input}\n\n【模型输出】\n{actual_output}\n\n{expected_section}\n{criteria_section}\n【评估维度】\n{dimension_str}\n\n【评分规则】\n- 每个维度评分范围：0-100分\n- 请提供简洁的评分理由\n- 最终输出为 JSON 格式，包含各维度得分和总分\n\n【输出格式】\n{json_format}".format(
            user_input=user_input,
            actual_output=actual_output,
            expected_section=expected_section,
            criteria_section=criteria_section,
            dimension_str=dimension_str,
            json_format=json_format,
        )

        return prompt

    def _parse_judge_result(self, llm_output: str, dimensions: list[str]) -> DomainResponse:
        try:
            start = llm_output.find("{")
            end = llm_output.rfind("}") + 1
            if start != -1 and end != -1:
                json_str = llm_output[start:end]
                result = json.loads(json_str)
            else:
                result = self._fallback_parse(llm_output, dimensions)

            total_score = result.get("total_score", 0)
            scores = result.get("scores", {})

            return DomainResponse(
                is_valid=True,
                text=str(total_score),
                score=total_score / 100.0,
                data={
                    "llm_judge_scores": scores,
                    "total_score": total_score,
                    "confidence": result.get("confidence", 0.8),
                },
            )
        except json.JSONDecodeError:
            return self._fallback_parse_response(llm_output, dimensions)

    def _fallback_parse(self, llm_output: str, dimensions: list[str]) -> dict:
        scores = {}
        total_score = 0
        for dim in dimensions:
            if dim.lower() in llm_output.lower():
                import re

                match = re.search(rf"{dim.lower()}[\s:]+(\d+)", llm_output.lower())
                score = int(match.group(1)) if match else 50
            else:
                score = 50
            scores[dim] = {"score": score, "reason": "解析结果"}
            total_score += score

        return {
            "scores": scores,
            "total_score": total_score // len(dimensions),
            "confidence": 0.6,
        }

    def _fallback_parse_response(self, llm_output: str, dimensions: list[str]) -> DomainResponse:
        scores = {}
        total_score = 0
        for dim in dimensions:
            scores[dim] = {"score": 50, "reason": "解析失败，使用默认值"}
            total_score += 50

        return DomainResponse(
            is_valid=True,
            text=str(total_score // len(dimensions)),
            score=0.5,
            data={
                "llm_judge_scores": scores,
                "total_score": total_score // len(dimensions),
                "confidence": 0.5,
            },
        )

    def _mock_judge_result(self) -> str:
        return json.dumps({
            "scores": {
                "correctness": {"score": 85, "reason": "回答基本正确"},
                "relevance": {"score": 90, "reason": "与问题高度相关"},
            },
            "total_score": 87,
            "confidence": 0.85,
        })
