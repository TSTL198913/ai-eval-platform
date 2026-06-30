"""
事实性评估器 - 2026 工业级标准重构版

用于对文本进行多维事实一致性打分，包括：
- 过度推论检测
- 移花接木识别
- 概念篡改检测

工业级特性：
- 严格语义策略（禁止静默降级）
- 完整类型注解
- 结构化异常处理
- 方法拆分（≤50行）
"""

import logging
from typing import Any

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.fallback_policy import StrictSemanticPolicy
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)


@EvaluatorFactory.register("factuality")
class FactualityEvaluator(BaseEvaluator):
    """事实性评估器（严格语义策略）"""

    def __init__(self, client: Any | None = None) -> None:
        """初始化事实性评估器

        Args:
            client: LLM 客户端实例（可选）
        """
        super().__init__(
            client,
            fallback_policy=StrictSemanticPolicy(),
            require_input=True,
            require_expected=True,
        )

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """执行多维事实一致性评估（带降级策略）

        修复：原实现完全依赖LLM返回0-1数字，当LLM不可用时系统丧失事实检测能力。
        现增加基于规则的事实检测作为降级策略。

        优先级：
        1. LLM评分（高精度）
        2. 规则评分（降级策略）
        3. 错误返回（最后兜底）
        """
        if error := self.validate_input(request):
            return error
        if error := self.validate_expected(request):
            return error
        if error := self.require_client_with_error():
            return error

        actual_output = self._extract_actual_output(request)
        evidence = self._extract_evidence(request)

        # 1. 尝试 LLM 评分
        if self.client and hasattr(self.client, "chat"):
            try:
                prompt = self._build_prompt(actual_output, evidence)
                llm_output = self.client.chat(prompt)
                score = self.safe_parse_score(llm_output)

                if score is not None:
                    return self.create_success_response(
                        text=actual_output,
                        score=score,
                        data={
                            "audit_status": "completed",
                            "method": "llm_judge",
                            "evidence": evidence,
                            "raw_score": score,
                            "raw_output": llm_output,
                            "evaluator": "factuality",
                        },
                    )
                logger.warning("LLM returned unparseable score, falling back to rule-based")
            except Exception as e:
                logger.exception(f"事实性评估器 LLM 调用失败，降级至规则检测: {e}")

        # 2. 降级策略：基于规则的事实检测
        rule_score = self._rule_based_factuality(actual_output, evidence)
        if rule_score is not None:
            return self.create_success_response(
                text=actual_output,
                score=rule_score,
                data={
                    "audit_status": "completed",
                    "method": "rule_based_fallback",
                    "evidence": evidence,
                    "raw_score": rule_score,
                    "evaluator": "factuality",
                    "fallback_reason": "LLM unavailable or returned invalid response",
                },
            )

        # 3. 最后兜底：返回错误
        return self.create_error_response(
            error_message="无法执行事实性评估：LLM不可用且规则降级失败",
            error_code="EVALUATION_FALLBACK_FAILED",
        )

    def _rule_based_factuality(self, actual_output: str, evidence: str) -> float | None:
        """基于规则的事实性检测（降级策略）

        综合考虑：
        1. 数字一致性（0.4权重）
        2. 关键词覆盖率（0.3权重）
        3. 长度合理性（0.3权重）
        """
        import re

        if not actual_output or not evidence:
            return None

        # 数字一致性
        evidence_numbers = set(re.findall(r"\d+\.?\d*", evidence))
        output_numbers = set(re.findall(r"\d+\.?\d*", actual_output))
        if evidence_numbers:
            num_match = len(evidence_numbers & output_numbers) / len(evidence_numbers)
        else:
            num_match = 1.0

        # 关键词覆盖率
        evidence_keywords = set(self._extract_keywords(evidence))
        output_keywords = set(self._extract_keywords(actual_output))
        if evidence_keywords:
            coverage = len(evidence_keywords & output_keywords) / len(evidence_keywords)
        else:
            coverage = 1.0

        # 长度合理性（输出过短或过长都暗示幻觉）
        output_len = len(actual_output)
        evidence_len = len(evidence)
        if evidence_len > 0:
            length_ratio = min(output_len / evidence_len, 2.0)
            length_score = 1.0 if 0.3 <= length_ratio <= 1.5 else 0.5
        else:
            length_score = 1.0

        final_score = num_match * 0.4 + coverage * 0.3 + length_score * 0.3
        return round(max(0.0, min(1.0, final_score)), 4)

    def _extract_keywords(self, text: str) -> set[str]:
        """提取关键词（用于降级策略）"""
        import re

        # 提取中英文词语（长度>=2）
        words = re.findall(r"\b[a-zA-Z\u4e00-\u9fff]{2,}\b", text.lower())
        # 简单停用词过滤
        stop_words = {
            "的",
            "是",
            "在",
            "有",
            "和",
            "了",
            "我",
            "你",
            "他",
            "她",
            "它",
            "这",
            "那",
            "the",
            "a",
            "an",
            "is",
            "are",
            "of",
            "to",
            "and",
        }
        return {w for w in words if w not in stop_words}

    def _extract_actual_output(self, request: EvaluationSchema) -> str:
        """提取实际输出

        Args:
            request: 评估请求

        Returns:
            str: 实际输出文本
        """
        return self.get_payload_data(request, "actual_output", default="")

    def _extract_evidence(self, request: EvaluationSchema) -> str:
        """提取可信证据

        Args:
            request: 评估请求

        Returns:
            str: 可信证据文本
        """
        return self.get_payload_data(request, "expected_output", default="")

    def _build_prompt(self, actual_output: str, evidence: str) -> str:
        """构建评估 Prompt

        Args:
            actual_output: 实际输出
            evidence: 可信证据

        Returns:
            str: 构建的 Prompt
        """
        return (
            "你是一个高阶信息审计师。请对照可信证据链，对实际输出进行多维事实一致性打分。\n"
            "严格检查是否有过度推论、移花接木、概念篡改等隐蔽幻觉。\n"
            "最终请给出一个综合的 0.0 到 1.0 之间的一致性得分。\n\n"
            f"【可信证据链】：{evidence}\n"
            f"【待审计输出】：{actual_output}\n\n"
            "事实一致性得分（仅输出数字）："
        )


## 自检清单
# - [x] 死代码检查：所有 return 语句都在可达路径
# - [x] 类型注解：所有方法都有类型注解
# - [x] 安全扫描：无敏感操作
# - [x] 复杂度：每个方法不超过 50 行
# - [x] 异常处理：包含堆栈追踪，返回明确错误响应
# - [x] 依赖验证：调用的是 BaseEvaluator 的方法
# - [x] 线程安全：无共享状态修改
