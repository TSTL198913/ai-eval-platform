import json

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
        golden_dataset_id = self.get_payload_data(request, "golden_dataset_id")
        few_shot_limit = self.get_payload_data(request, "few_shot_limit", 3)

        prompt = self._build_judge_prompt(
            user_input=user_input,
            actual_output=actual_output,
            expected_output=expected_output,
            dimensions=dimensions,
            criteria=criteria,
            golden_dataset_id=golden_dataset_id,
            few_shot_limit=few_shot_limit,
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
        golden_dataset_id: str | None = None,
        few_shot_limit: int = 3,
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

        json_format = """{
  "scores": {
    "<维度名>": {
      "score": <分数>,
      "reason": "<评分理由，必须引用具体内容作为证据>",
      "evidence": ["<引用1：原文中支持该评分的关键语句>", "<引用2>"],
      "citation": "<参考来源编号，如[KB-001]，如无则填'无'>"
    }
  },
  "total_score": <总分>,
  "confidence": <置信度0-1>,
  "conflict_detected": <true/false，是否存在评分冲突>
}"""

        expected_section = f"【期望输出】\n{expected_output}\n" if expected_output else ""
        criteria_section = f"【额外评估标准】\n{criteria}\n" if criteria else ""

        few_shot_section = ""
        if golden_dataset_id:
            try:
                from src.domain.golden_dataset import golden_dataset_manager
                examples = golden_dataset_manager.get_few_shot_examples(
                    golden_dataset_id, limit=few_shot_limit, dimensions=dimensions
                )
                if examples:
                    few_shot_section = "【评分示例参考】\n" + "\n".join(examples)
            except Exception:
                pass

        prompt = f"""你是一个专业的 AI 评测专家。请根据以下维度对模型的输出进行评分。

【重要要求】
1. 每个维度的评分必须有具体的文本引用作为证据支撑
2. 在"evidence"字段中，引用原文中的关键语句
3. 如果发现评分存在矛盾（如高分但证据不支持），设置conflict_detected=true

{few_shot_section}【用户问题】
{user_input}

【模型输出】
{actual_output}

{expected_section}
{criteria_section}【评估维度】
{dimension_str}

【评分规则】
- 每个维度评分范围：0-100分
- reason必须引用原文中的具体语句作为证据
- 最终输出为 JSON 格式，包含各维度得分、总分和置信度

【输出格式】
{json_format}"""

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
            conflict_detected = result.get("conflict_detected", False)

            # 提取证据归因信息
            attribution_data = {}
            for dim, score_data in scores.items():
                if isinstance(score_data, dict):
                    attribution_data[dim] = {
                        "evidence": score_data.get("evidence", []),
                        "citation": score_data.get("citation", "无"),
                    }

            return DomainResponse(
                is_valid=True,
                text=str(total_score),
                score=total_score / 100.0,
                data={
                    "llm_judge_scores": scores,
                    "total_score": total_score,
                    "confidence": result.get("confidence", 0.8),
                    "conflict_detected": conflict_detected,
                    "attribution": attribution_data,
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
                "correctness": {
                    "score": 85,
                    "reason": "回答内容基本正确，体现了道歉和解决问题的态度",
                    "evidence": ["您好，非常抱歉给您带来不便", "预计3天内可以发出"],
                    "citation": "无"
                },
                "relevance": {
                    "score": 90,
                    "reason": "回答完全针对用户提出的发货和退款问题",
                    "evidence": ["联系物流催促发货", "退款将在1-3个工作日内到账"],
                    "citation": "无"
                },
            },
            "total_score": 87,
            "confidence": 0.85,
            "conflict_detected": False,
        })
