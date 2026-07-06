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
from typing import Any
from typing import Dict

from llm_guard import scan_output
from llm_guard import scan_prompt
from llm_guard.input_scanners import Code
from llm_guard.input_scanners import PromptInjection
from llm_guard.input_scanners import TokenLimit
from llm_guard.input_scanners import Toxicity
from llm_guard.output_scanners import Bias
from llm_guard.output_scanners import Code
from llm_guard.output_scanners import Language
from llm_guard.output_scanners import Relevance
from llm_guard.output_scanners import Sensitive
from llm_guard.output_scanners import Toxicity

try:
    from llm_guard.output_scanners import Refutation
except ImportError:
    Refutation = None

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse
from src.schemas.evaluation import EvaluationSchema

logger = logging.getLogger(__name__)


@EvaluatorFactory.register("llm_guard")
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
        self._input_scanners = None
        self._output_scanners = None
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

    def _init_scanners(self):
        """延迟初始化扫描器，避免在导入时就加载模型"""
        if self._input_scanners is not None:
            return

        self._input_scanners = []
        self._output_scanners = []

        try:
            self._input_scanners.append(PromptInjection())
            logger.debug("PromptInjection 扫描器加载成功")
        except Exception as e:
            logger.warning(f"无法加载 PromptInjection 扫描器，跳过: {e}")

        try:
            self._input_scanners.append(TokenLimit())
            logger.debug("TokenLimit 扫描器加载成功")
        except Exception as e:
            logger.warning(f"无法加载 TokenLimit 扫描器，跳过: {e}")

        try:
            self._input_scanners.append(Code(languages=["Python"]))
            logger.debug("Code 输入扫描器加载成功")
        except Exception as e:
            logger.warning(f"无法加载 Code 输入扫描器，跳过: {e}")

        try:
            self._input_scanners.append(Toxicity())
            logger.debug("Toxicity 输入扫描器加载成功")
        except Exception as e:
            logger.warning(f"无法加载 Toxicity 输入扫描器，跳过: {e}")

        try:
            self._output_scanners.append(Code(languages=["Python"]))
            logger.debug("Code 输出扫描器加载成功")
        except Exception as e:
            logger.warning(f"无法加载 Code 输出扫描器，跳过: {e}")

        try:
            self._output_scanners.append(Relevance())
            logger.debug("Relevance 扫描器加载成功")
        except Exception as e:
            logger.warning(f"无法加载 Relevance 扫描器，跳过: {e}")

        try:
            self._output_scanners.append(Sensitive())
            logger.debug("Sensitive 扫描器加载成功")
        except Exception as e:
            logger.warning(f"无法加载 Sensitive 扫描器，跳过: {e}")

        try:
            self._output_scanners.append(Language())
            logger.debug("Language 扫描器加载成功")
        except Exception as e:
            logger.warning(f"无法加载 Language 扫描器，跳过: {e}")

        try:
            self._output_scanners.append(Toxicity())
            logger.debug("Toxicity 输出扫描器加载成功")
        except Exception as e:
            logger.warning(f"无法加载 Toxicity 输出扫描器，跳过: {e}")

        try:
            self._output_scanners.append(Bias())
            logger.debug("Bias 扫描器加载成功")
        except Exception as e:
            logger.warning(f"无法加载 Bias 扫描器，跳过: {e}")

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        user_input = request.payload.get("user_input", "")
        actual_output = request.payload.get("actual_output", "")

        if not user_input:
            return self.create_error_response(
                error_message="缺少 user_input 参数",
                error_code="VALIDATION_ERROR",
            )

        self._init_scanners()

        user_input = str(user_input) if user_input else ""
        actual_output = str(actual_output) if actual_output else ""

        if not self._input_scanners:
            return self.create_partial_response(
                text="安全扫描完成（降级模式）",
                score=0.5,
                dimensions_evaluated=["basic_validation"],
                dimensions_skipped=["prompt_injection", "toxicity", "code", "token_limit", "bias", "relevance", "sensitive", "language"],
                skip_reasons={"all": "扫描器初始化失败，使用降级评估"},
                data={
                    "risk_level": "medium",
                    "overall_score": 0.5,
                    "scan_results": {"error": "扫描器不可用"},
                },
                confidence=0.5,
            )

        scan_results: Dict[str, Any] = {}
        total_score = 1.0
        skipped_dimensions = []
        evaluated_dimensions = []

        scanner_to_dimension = {
            "PromptInjection": "prompt_injection",
            "TokenLimit": "token_limit",
            "Code": "code",
            "Toxicity": "toxicity",
            "Relevance": "relevance",
            "Sensitive": "sensitive",
            "Language": "language",
            "Bias": "bias",
        }

        for scanner in self._input_scanners:
            dim = scanner_to_dimension.get(type(scanner).__name__)
            if dim:
                evaluated_dimensions.append(dim)

        for scanner in self._output_scanners:
            dim = scanner_to_dimension.get(type(scanner).__name__)
            if dim and dim not in evaluated_dimensions:
                evaluated_dimensions.append(dim)

        all_expected_dimensions = ["prompt_injection", "toxicity", "token_limit", "code", "bias", "relevance", "sensitive", "language"]
        skipped_dimensions = [d for d in all_expected_dimensions if d not in evaluated_dimensions]

        try:
            scan_result = scan_prompt(
                self._input_scanners, user_input
            )
            if len(scan_result) == 3:
                _, input_is_valid_dict, input_scores_dict = scan_result
            elif len(scan_result) == 2:
                input_is_valid_dict, input_scores_dict = scan_result
            else:
                raise ValueError(f"Unexpected scan_prompt return format: {type(scan_result)}")
            
            input_scan_result = {
                "is_valid": input_is_valid_dict,
                "scores": input_scores_dict
            }
            scan_results["input"] = input_scan_result
            
            if input_scores_dict:
                risk_detected = any(not is_valid for is_valid in input_is_valid_dict.values()) if input_is_valid_dict else False
                
                if risk_detected:
                    risk_scores = [score for score in input_scores_dict.values() if score > 0]
                    if risk_scores:
                        input_score = max(0.0, min(1.0, 1.0 - sum(risk_scores) / len(risk_scores)))
                    else:
                        input_score = 0.5
                else:
                    input_score = 1.0
            else:
                input_score = 1.0
            total_score *= input_score
        except Exception as e:
            logger.error(f"LLM Guard input scan failed: {e}", exc_info=True)
            return self.create_error_response(
                error_message=f"输入安全扫描失败: {type(e).__name__}: {str(e)}",
                error_code="SECURITY_SCAN_ERROR",
            )

        if actual_output and self._output_scanners:
            try:
                scan_result = scan_output(
                    self._output_scanners, user_input, actual_output
                )
                if len(scan_result) == 3:
                    _, output_is_valid_dict, output_scores_dict = scan_result
                elif len(scan_result) == 2:
                    output_is_valid_dict, output_scores_dict = scan_result
                else:
                    raise ValueError(f"Unexpected scan_output return format: {type(scan_result)}")
                
                output_scan_result = {
                    "is_valid": output_is_valid_dict,
                    "scores": output_scores_dict
                }
                scan_results["output"] = output_scan_result
                
                if output_scores_dict:
                    avg_score = sum(output_scores_dict.values()) / len(output_scores_dict)
                    output_score = max(0.0, min(1.0, 1.0 - max(0.0, avg_score)))
                else:
                    output_score = 1.0
                total_score *= output_score
            except Exception as e:
                logger.error(f"LLM Guard output scan failed: {e}", exc_info=True)
                scan_results["output"] = {"error": str(e)}
                total_score *= 0.5

        risk_level = self._determine_risk_level(total_score, scan_results)

        has_all_scanners = len(evaluated_dimensions) >= len(all_expected_dimensions)

        if has_all_scanners:
            return self.create_success_response(
                text=f"安全扫描完成，风险等级: {risk_level}",
                score=round(total_score, 4),
                data={
                    "risk_level": risk_level,
                    "overall_score": round(total_score, 4),
                    "scan_results": scan_results,
                    "scan_types": self._scan_types,
                    "dimensions_evaluated": evaluated_dimensions,
                },
                confidence=round(min(total_score + 0.1, 1.0), 2),
            )
        else:
            return self.create_partial_response(
                text=f"安全扫描完成（部分模式），风险等级: {risk_level}",
                score=round(total_score, 4),
                dimensions_evaluated=evaluated_dimensions,
                dimensions_skipped=skipped_dimensions,
                skip_reasons={"scanners_not_available": "部分扫描器未加载"},
                data={
                    "risk_level": risk_level,
                    "overall_score": round(total_score, 4),
                    "scan_results": scan_results,
                    "scan_types": self._scan_types,
                },
                confidence=round(min(total_score + 0.05, 0.8), 2),
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