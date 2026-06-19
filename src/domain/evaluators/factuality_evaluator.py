"""
Factuality Evaluator - 幻觉率独立评估器

提供LLM输出的事实性/真实性评估：
- 事实一致性：与参考信息的事实匹配度
- 幻觉检测：识别无中生有的内容
- 实体验证：人物/地点/数字等实体验证
- 引用追溯：信息来源可追溯性
"""
from typing import Any, Dict, List, Optional
import re

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import EvaluationSchema, DomainResponse


@EvaluatorFactory.register("factuality")
class FactualityEvaluator:
    """事实性评估器

    输入payload格式:
    {
        "action": "evaluate_factuality",
        "response": "LLM生成的回复",
        "reference": ["参考事实1", "参考事实2", ...],  # 可选参考信息
        "context": "对话上下文",                          # 可选上下文
        "strict_mode": False                              # 严格模式（开启后更敏感）
    }
    """

    def __init__(self, client: Optional[Any] = None):
        self.client = client

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        action = request.payload.get("action", "evaluate_factuality")
        handler = {
            "evaluate_factuality": self._evaluate_factuality,
            "detect_hallucination": self._detect_hallucination,
            "verify_entities": self._verify_entities,
            "check_consistency": self._check_consistency,
        }.get(action)
        if handler is None:
            return DomainResponse(
                data={"is_valid": False, "error": f"Unknown action: {action}"},
                status_code=400,
            )
        try:
            return handler(request)
        except Exception as e:
            return DomainResponse(
                data={"is_valid": False, "error": str(e)},
                status_code=500,
            )

    def safe_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        return self.evaluate(request)

    # ===================== 核心评估方法 =====================

    def _evaluate_factuality(self, request: EvaluationSchema) -> DomainResponse:
        """综合评估事实性"""
        response = self._get_payload(request, "response", "")
        reference = self._get_payload(request, "reference", [])
        context = self._get_payload(request, "context", "")
        strict_mode = self._get_payload(request, "strict_mode", False)

        if not response:
            return DomainResponse(
                data={"is_valid": False, "error": "response不能为空"},
                status_code=400,
            )

        # 提取回复中的事实声明
        claims = self._extract_claims(response)
        # 提取实体
        entities = self._extract_entities(response)
        # 提取数字
        numbers = self._extract_numbers(response)

        # 事实一致性评分
        if reference:
            consistency_score = self._score_against_reference(claims, reference)
        else:
            consistency_score = None  # 无参考时无法评估一致性

        # 幻觉检测
        hallucination_result = self._detect_hallucination_internals(response, reference, context, strict_mode)
        # 实体一致性
        entity_consistency = self._check_entity_consistency(entities, reference)
        # 数字一致性
        number_consistency = self._check_number_consistency(numbers, reference)

        # 综合评分
        sub_scores = {
            "consistency": consistency_score,
            "hallucination_score": hallucination_result["hallucination_score"],
            "entity_consistency": entity_consistency,
            "number_consistency": number_consistency,
        }
        # 过滤None
        valid_scores = [v for v in sub_scores.values() if v is not None]
        if valid_scores:
            overall = sum(valid_scores) / len(valid_scores)
        else:
            overall = 0.5  # 默认中性评分

        # 幻觉率
        hallucination_rate = 1.0 - hallucination_result["hallucination_score"]

        return DomainResponse(
            data={
                "is_valid": True,
                "overall_factuality_score": round(overall, 4),
                "hallucination_rate": round(hallucination_rate, 4),
                "dimension_scores": {k: round(v, 4) if v is not None else None for k, v in sub_scores.items()},
                "claims_count": len(claims),
                "entities_count": len(entities),
                "numbers_count": len(numbers),
                "hallucination_details": hallucination_result,
            },
            status_code=200,
        )

    def _detect_hallucination(self, request: EvaluationSchema) -> DomainResponse:
        """专门的幻觉检测"""
        response = self._get_payload(request, "response", "")
        reference = self._get_payload(request, "reference", [])
        context = self._get_payload(request, "context", "")
        strict_mode = self._get_payload(request, "strict_mode", False)

        result = self._detect_hallucination_internals(response, reference, context, strict_mode)

        return DomainResponse(
            data={
                "is_valid": True,
                "hallucination_score": round(result["hallucination_score"], 4),
                "hallucination_rate": round(1.0 - result["hallucination_score"], 4),
                "detected_issues": result.get("issues", []),
                "details": result,
            },
            status_code=200,
        )

    def _verify_entities(self, request: EvaluationSchema) -> DomainResponse:
        """实体验证"""
        response = self._get_payload(request, "response", "")
        reference = self._get_payload(request, "reference", [])

        entities = self._extract_entities(response)
        entity_score = self._check_entity_consistency(entities, reference)

        return DomainResponse(
            data={
                "is_valid": True,
                "entity_consistency_score": round(entity_score, 4),
                "entities": entities,
                "reference_count": len(reference),
            },
            status_code=200,
        )

    def _check_consistency(self, request: EvaluationSchema) -> DomainResponse:
        """检查内部一致性"""
        response = self._get_payload(request, "response", "")
        claims = self._extract_claims(response)
        contradictions = self._find_contradictions(claims)

        consistency_score = 1.0 - (len(contradictions) / max(len(claims), 1))

        return DomainResponse(
            data={
                "is_valid": True,
                "internal_consistency_score": round(consistency_score, 4),
                "claims_count": len(claims),
                "contradictions_count": len(contradictions),
                "contradictions": contradictions[:5],
            },
            status_code=200,
        )

    # ===================== 内部算法 =====================

    def _detect_hallucination_internals(
        self, response: str, reference: List[str], context: str, strict_mode: bool
    ) -> Dict[str, Any]:
        """内部幻觉检测实现"""
        issues = []

        # 1. 检测与参考信息的冲突
        if reference:
            ref_text = " ".join(reference).lower()
            response_lower = response.lower()
            # 提取关键数字
            response_numbers = self._extract_numbers(response)
            ref_numbers = self._extract_numbers(" ".join(reference))
            conflicting_numbers = []
            for n in response_numbers:
                if str(n["value"]) not in ref_text:
                    conflicting_numbers.append(n)
            if conflicting_numbers and strict_mode:
                issues.append({
                    "type": "unsupported_numbers",
                    "count": len(conflicting_numbers),
                    "examples": conflicting_numbers[:3],
                })

        # 2. 检测过度自信的语言（无依据的断言）
        overconfident_patterns = [
            r"据我了解",
            r"根据我的信息",
            r"可以肯定的是",
            r"毫无疑问",
            r"事实上是",
        ]
        overconfident_count = 0
        for pattern in overconfident_patterns:
            overconfident_count += len(re.findall(pattern, response))

        # 3. 检测无法验证的具体声明
        # 提取时间声明
        time_claims = re.findall(r"\d{4}年", response)
        unsupported_time_claims = []
        if reference:
            ref_text = " ".join(reference)
            for tc in time_claims:
                if tc not in ref_text:
                    unsupported_time_claims.append(tc)
        if unsupported_time_claims and strict_mode:
            issues.append({
                "type": "unsupported_time_claims",
                "claims": unsupported_time_claims[:3],
            })

        # 4. 计算幻觉分数
        if not reference:
            # 无参考信息时，给予中性评分
            hallucination_score = max(0.0, 1.0 - overconfident_count * 0.1)
        else:
            # 有参考时，根据冲突数量计算
            ref_text = " ".join(reference).lower()
            response_lower = response.lower()
            # 简单的事实对齐：检查关键词覆盖率
            ref_words = set(self._tokenize(" ".join(reference)))
            response_words = set(self._tokenize(response))
            if ref_words:
                coverage = len(ref_words & response_words) / len(ref_words)
            else:
                coverage = 0.0
            # 冲突惩罚
            penalty = len(issues) * 0.1 + overconfident_count * 0.05
            hallucination_score = max(0.0, coverage - penalty)

        return {
            "hallucination_score": hallucination_score,
            "issues": issues,
            "overconfident_count": overconfident_count,
            "has_reference": bool(reference),
        }

    def _score_against_reference(self, claims: List[str], reference: List[str]) -> float:
        """与参考信息对齐评分"""
        if not reference or not claims:
            return 0.0
        ref_text = " ".join(reference).lower()
        ref_words = set(self._tokenize(ref_text))
        if not ref_words:
            return 0.0
        matched = 0
        for claim in claims:
            claim_words = set(self._tokenize(claim))
            if claim_words & ref_words:
                matched += 1
        return matched / len(claims)

    def _check_entity_consistency(self, entities: List[Dict], reference: List[str]) -> float:
        """检查实体一致性"""
        if not reference or not entities:
            return 1.0
        ref_text = " ".join(reference)
        matched = 0
        for ent in entities:
            if ent["text"] in ref_text:
                matched += 1
        return matched / len(entities)

    def _check_number_consistency(self, numbers: List[Dict], reference: List[str]) -> float:
        """检查数字一致性"""
        if not reference or not numbers:
            return 1.0
        ref_text = " ".join(reference)
        matched = 0
        for n in numbers:
            if str(n["value"]) in ref_text:
                matched += 1
        return matched / len(numbers)

    def _find_contradictions(self, claims: List[str]) -> List[Dict[str, Any]]:
        """查找内部矛盾（简化版）"""
        contradictions = []
        # 简单的矛盾检测：如果两个claim包含相反的含义
        contradiction_pairs = [
            ("是", "不是"),
            ("有", "没有"),
            ("会", "不会"),
            ("能", "不能"),
            ("true", "false"),
            ("yes", "no"),
        ]
        for i, c1 in enumerate(claims):
            for j, c2 in enumerate(claims):
                if i >= j:
                    continue
                for pos, neg in contradiction_pairs:
                    if pos in c1 and neg in c2:
                        # 检查是否关于同一主题
                        words1 = set(self._tokenize(c1))
                        words2 = set(self._tokenize(c2))
                        if len(words1 & words2) >= 2:
                            contradictions.append({
                                "claim1": c1,
                                "claim2": c2,
                                "type": f"{pos}_vs_{neg}",
                            })
        return contradictions

    def _extract_claims(self, text: str) -> List[str]:
        """提取事实声明（按句子分割）"""
        # 按句号、问号、感叹号分句
        sentences = re.split(r"[。！？.!?]", text)
        return [s.strip() for s in sentences if len(s.strip()) > 5]

    def _extract_entities(self, text: str) -> List[Dict[str, str]]:
        """提取实体（简化版：人名、地名、组织等）"""
        entities = []
        # 提取大写开头的英文词组（可能是人名/组织名）
        for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text):
            entities.append({"text": match.group(1), "type": "proper_noun"})
        # 提取中文人名（简化：2-4字中文，前后不是汉字）
        for match in re.finditer(r"(?<![\u4e00-\u9fff])([\u4e00-\u9fff]{2,4})(?![\u4e00-\u9fff])", text):
            word = match.group(1)
            # 简单启发：包含"先生"/"女士"等称呼的更可能是人名
            if any(suffix in text for suffix in ["先生", "女士", "教授", "博士", "总裁"]):
                entities.append({"text": word, "type": "person"})
        return entities

    def _extract_numbers(self, text: str) -> List[Dict[str, Any]]:
        """提取数字"""
        numbers = []
        # 阿拉伯数字
        for match in re.finditer(r"\b(\d+(?:\.\d+)?)\b", text):
            value = match.group(1)
            try:
                numbers.append({"value": float(value), "text": value, "type": "arabic"})
            except ValueError:
                pass
        # 百分数
        for match in re.finditer(r"(\d+(?:\.\d+)?)%", text):
            value = match.group(1)
            try:
                numbers.append({"value": float(value) / 100, "text": match.group(0), "type": "percentage"})
            except ValueError:
                pass
        return numbers

    def _tokenize(self, text: str) -> List[str]:
        """分词"""
        # 简单的分词：英文按空格，中文按字
        words = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
        return [w for w in words if len(w) > 1]

    @staticmethod
    def _get_payload(request: EvaluationSchema, key: str, default: Any = None) -> Any:
        if hasattr(request, "payload") and request.payload:
            return request.payload.get(key, default)
        return default
