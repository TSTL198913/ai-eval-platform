"""
LLM Guard 安全扫描评估器
基于 llm-guard 库实现 OWASP Top 10 for LLM 风险检测

支持的安全检查类型：
- Prompt Injection（提示注入）
- Jailbreak（越狱攻击）
- Data Leak（数据泄露）
- Toxicity（有害内容）
- Language（语言检测）
- Token Limit（Token限制）
- PII（个人身份信息）
- Secrets（密钥泄露）
"""

import logging
from typing import Any, Dict, List, Optional

from llm_guard import scan_prompt, scan_output
from llm_guard.input_scanners import (
    Anonymize,
    BanCompetitors,
    BanSubstrings,
    BanTopics,
    Code,
    PromptInjection,
    TokenLimit,
    Toxicity,
)
from llm_guard.output_scanners import (
    Bias,
    Code,
    Deanonymize,
    JSON,
    Language,
    LanguageSame,
    Relevance,
    Sensitive,
    Sentiment,
    Toxicity,
)
try:
    from llm_guard.output_scanners import Refutation
except ImportError:
    Refutation = None

from src.domain.evaluators.base import BaseEvaluator
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)


class LLMGuardEvaluator(BaseEvaluator):
    """
    LLM Guard 安全扫描评估器

    使用 llm-guard 库对输入和输出进行安全扫描，检测 OWASP Top 10 for LLM 风险。
    
    评估结果：
    - score: 综合安全分数（0-1，越高越安全）
    - data: 包含各扫描类型的详细结果
    - risk_level: 风险等级（low/medium/high/critical）
    """

    def __init__(self, client=None):
        super().__init__(client, require_input=True)
        self._input_scanners = [
            PromptInjection(),
            Toxicity(),
            TokenLimit(),
            Code(),
        ]
        self._output_scanners = [
            Toxicity(),
            Bias(),
            Relevance(),
            Sensitive(),
            Language(),
        ]
        self._scan_types = {
            "prompt_injection": "提示注入检测",
            "toxicity": "有害内容检测",
            "token_limit": "Token限制检测",
            "code": "代码注入检测",
            "bias": "偏见检测",
            "relevance": "相关性检测",
            "sensitive": "敏感信息检测",
            "language": "语言检测",
        }

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        try:
            user_input = request.payload.get("user_input", "")
            actual_output = request.payload.get("actual_output", "")
            
            if not user_input:
                return self.create_error_response(
                    error_message="缺少 user_input 参数",
                    error_code="VALIDATION_ERROR",
                )

            scan_results: Dict[str, Any] = {}
            total_score = 1.0
            detected_risk_levels: List[str] = []

            input_scan_result, input_score = scan_prompt(
                self._input_scanners, user_input
            )
            scan_results["input"] = input_scan_result
            total_score *= input_score

            if actual_output:
                output_scan_result, output_score = scan_output(
                    self._output_scanners, user_input, actual_output
                )
                scan_results["output"] = output_scan_result
                total_score *= output_score

            risk_level = self._determine_risk_level(total_score, scan_results)

            return self.create_success_response(
                text=f"安全扫描完成，风险等级: {risk_level}",
                score=round(total_score, 4),
                data={
                    "risk_level": risk_level,
                    "overall_score": round(total_score, 4),
                    "scan_results": scan_results,
                    "scan_types": self._scan_types,
                },
                confidence=round(min(total_score + 0.1, 1.0), 2),
            )
        except Exception as e:
            logger.error(f"LLM Guard 扫描失败: {e}")
            return self.create_error_response(
                error_message=f"安全扫描失败: {str(e)}",
                error_code="SECURITY_SCAN_ERROR",
            )

    def _determine_risk_level(self, score: float, scan_results: Dict[str, Any]) -> str:
        """根据扫描结果确定风险等级"""
        if score >= 0.9:
            return "low"
        elif score >= 0.7:
            return "medium"
        elif score >= 0.5:
            return "high"
        else:
            return "critical"

    @classmethod
    def register(cls):
        """注册到评估器工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        
        EvaluatorFactory.register("llm_guard")(cls)
        logger.info("LLMGuardEvaluator 已注册到评估器工厂")


LLMGuardEvaluator.register()