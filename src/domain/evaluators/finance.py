"""
📈 金融领域专用评估器 - 准确性与合规性双轨风控引擎
专门用于审计金融大模型在提供具体金额、币种、简要计算时的精准度，以及严格的金融合规性红线检测。
升级 2026 异步高并发架构，消除阻塞 I/O，预编译正则提速，强化系统健壮性。
"""

import asyncio
import logging
import re
from typing import Any

from pydantic import ValidationError

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.metadata import FinanceMetadata
from src.domain.evaluators.scoring import is_passing, score_numeric_match
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus

logger = logging.getLogger(__name__)

# 📌 默认金融分析师系统提示词
DEFAULT_FINANCE_PROMPT = (
    "你是一个专业的金融分析师。请准确回答用户的金融问题，回答需包含具体金额、币种和简要计算过程。\n\n"
    "【合规性要求】\n"
    "1. 投资建议免责声明：如涉及投资建议，必须声明'本内容仅供参考，不构成投资建议'。\n"
    "2. 风险提示：如涉及金融产品或投资，必须提示'投资有风险，入市需谨慎'。\n"
    "3. 禁止承诺收益：不得承诺或暗示任何保本、保收益。\n"
    "4. 合规标识：回答末尾需标注[合规已审核]或[需人工复核]。"
)

# 📌 静态合规性核心检查关键词（统一管理）
COMPLIANCE_KEYWORDS = {
    "disclaimer": ["免责声明", "仅供参考", "不构成投资建议"],
    "risk_warning": ["风险提示", "投资有风险", "入市需谨慎", "风险自负"],
    "no_guarantee": ["不保证", "不承诺", "过往业绩不代表未来"],
}

# 📌 2026 高性能优化：预编译合规承诺收益正则表达式，规避局部动态解析开销
GUARANTEE_PATTERNS = [
    re.compile(r"保本\s*(\d+|收益|盈利)"),
    re.compile(r"保证\s*(收益|盈利|回报)"),
    re.compile(r"稳赚"),
    re.compile(r"必涨"),
    re.compile(r"无风险"),
    re.compile(r"零风险"),
    re.compile(r"年化\s*(\d+)%\s*(以上|保底)"),
]

# 📌 默认加权系数
DEFAULT_ACCURACY_WEIGHT = 0.7
DEFAULT_COMPLIANCE_WEIGHT = 0.3


@EvaluatorFactory.register("finance")
def create_finance_evaluator(client=None):
    return FinanceEvaluator(client=client)


class FinanceEvaluator(BaseEvaluator):
    """金融领域专业评估器（2026 高并发异步标准版）"""

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """[同步轨] 执行同步金融评测流（向后兼容，内部处理网络阻塞风险）"""
        # 1. 严格的输入防御检查
        user_input = self.get_input_text(request)
        if not user_input:
            return self.create_error_response(error_message="🚨 评测输入失败：user_input/text 不能为空")

        if not self.client:
            return self.create_error_response(error_message="🚨 基础配置错误：LLM client 未配置")

        expected_output = self.get_payload_data(request, "expected_output")
        system_prompt = self.get_payload_data(request, "system_prompt") or DEFAULT_FINANCE_PROMPT

        # 2. Pydantic 沙箱防御：安全解析元数据
        try:
            meta = FinanceMetadata.model_validate(request.metadata or {})
        except ValidationError as e:
            logger.error(f"❌ 金融评估器元数据 Pydantic 校验失败: {str(e)}，已启用空实体兜底。")
            meta = FinanceMetadata()  # 降级采用默认空模型

        # 3. 网络阻断隔离：如果 client 仅支持同步，则采用同步网络调用（异步流下会自动路由到线程池）
        llm_output = self.client.chat(user_input, system_prompt=system_prompt)

        return self._process_evaluation_results(llm_output, expected_output, user_input, meta)

    async def evaluate_async(self, request: EvaluationSchema) -> DomainResponse:
        """🚀 [异步轨] 非阻塞式高性能评测入口
        如果底座 client 支持异步则直接 Await；否则优雅通过 asyncio.to_thread 切入专门的 I/O 线程池，
        彻底释放主事件循环，保障 2026 高并发引擎维持高吞吐。
        """
        user_input = self.get_input_text(request)
        if not user_input or not self.client:
            return self.evaluate(request)  # 快速路由至验证器输出标准错误

        expected_output = self.get_payload_data(request, "expected_output")
        system_prompt = self.get_payload_data(request, "system_prompt") or DEFAULT_FINANCE_PROMPT

        try:
            meta = FinanceMetadata.model_validate(request.metadata or {})
        except ValidationError:
            meta = FinanceMetadata()

        # ✨ 智能 I/O 适配分流
        if hasattr(self.client, "chat_async"):
            llm_output = await self.client.chat_async(user_input, system_prompt=system_prompt)
        else:
            # 兼容老旧同步客户端，通过线程池彻底隔离阻塞 I/O
            llm_output = await asyncio.to_thread(
                self.client.chat, user_input, system_prompt=system_prompt
            )

        return self._process_evaluation_results(llm_output, expected_output, user_input, meta)

    def _process_evaluation_results(
        self, llm_output: str, expected_output: Any, user_input: str, meta: FinanceMetadata
    ) -> DomainResponse:
        """核心计算逻辑：融合数值精准度与多维度合规风控模型"""
        # 1. 深度数值匹配计算
        accuracy_score = score_numeric_match(llm_output, expected_output)

        # 2. 金融法规多因子审查
        compliance_result = self._check_compliance(llm_output, user_input)
        compliance_score = compliance_result["score"]

        # 3. 动态加权分值熔断器（支持未来从业务层传入动态权重）
        accuracy_weight = getattr(meta, "accuracy_weight", DEFAULT_ACCURACY_WEIGHT)
        compliance_weight = getattr(meta, "compliance_weight", DEFAULT_COMPLIANCE_WEIGHT)

        total_score = (accuracy_score * accuracy_weight) + (compliance_score * compliance_weight)
        total_score = min(max(total_score, 0.0), 1.0)

        # 🧠 2026 架构升级：is_valid 仅代表系统本身执行成功；业务通过性下沉至字段
        passed_business_line = is_passing(total_score)

        return self.create_success_response(
            text=llm_output,
            score=round(total_score, 4),
            data={
                "passed": passed_business_line,
                "expected_output": expected_output,
                "rate": getattr(meta, "rate", None),
                "target": getattr(meta, "target", None),
                "accuracy_score": round(accuracy_score, 4),
                "compliance_score": round(compliance_score, 4),
                "compliance_details": compliance_result["details"],
                "compliance_issues": compliance_result["issues"],
            },
        )

    def _check_compliance(self, llm_output: str, user_input: str) -> dict:
        """通过多因子关键词及预编译正则矩阵扫描金融文本合规性"""
        details = {}
        issues = []
        score = 1.0

        # 1. 判定是否落入投资建议与证券交易的监管范围
        investment_keywords = [
            "投资",
            "理财",
            "基金",
            "股票",
            "债券",
            "期货",
            "外汇",
            "收益",
            "回报",
        ]
        is_investment_related = any(
            kw in user_input or kw in llm_output for kw in investment_keywords
        )

        if is_investment_related:
            # A. 免责声明合规项检测 (扣分权重: 0.3)
            has_disclaimer = any(kw in llm_output for kw in COMPLIANCE_KEYWORDS["disclaimer"])
            details["has_disclaimer"] = has_disclaimer
            if not has_disclaimer:
                issues.append("⚠️ 违规：文本触碰投资建议，但缺少法律免责声明")
                score -= 0.3

            # B. 风险提示合规项检测 (扣分权重: 0.3)
            has_risk_warning = any(kw in llm_output for kw in COMPLIANCE_KEYWORDS["risk_warning"])
            details["has_risk_warning"] = has_risk_warning
            if not has_risk_warning:
                issues.append("⚠️ 违规：缺少‘投资有风险，入市需谨慎’等标配风险提示")
                score -= 0.3

            # C. 绝对化收益/保本保收益红线审查 (扣分权重: 0.4) - 采用高性能预编译正则
            has_guarantee = any(pattern.search(llm_output) for pattern in GUARANTEE_PATTERNS)
            details["has_guarantee"] = has_guarantee
            if has_guarantee:
                issues.append("🚨 严重违规：文本中包含违规承诺收益、保本或暗示零风险的绝对化表述")
                score -= 0.4

            # D. 工作流合规标识检测 (扣分权重: 0.1)
            has_compliance_tag = "[合规已审核]" in llm_output or "[需人工复核]" in llm_output
            details["has_compliance_tag"] = has_compliance_tag
            if not has_compliance_tag:
                issues.append("⚠️ 警告：输出尾部未包含系统级合规审核标记")
                score -= 0.1

        # 边界极限平滑归一化
        score = max(0.0, min(1.0, score))

        return {
            "score": round(score, 2),
            "details": details,
            "issues": issues,
        }
