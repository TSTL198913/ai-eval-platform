"""
事实核查评估器 - 2026 工业级标准重构版

用于检测文本中的幻觉、造假或不实信息，包括：
- 事实一致性核查
- 幻觉检测
- 信息真实性验证

工业级特性：
- 二分类输出（true/false）
- 完整类型注解
- 结构化异常处理
- 方法拆分（≤50行）
"""

import logging
from typing import Any

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)


@EvaluatorFactory.register("fact_check")
class FactCheckEvaluator(BaseEvaluator):
    """事实核查评估器（二分类输出）"""

    def __init__(self, client: Any | None = None) -> None:
        """初始化事实核查评估器

        Args:
            client: LLM 客户端实例（可选）
        """
        super().__init__(client, require_input=True)

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """执行事实核查

        Args:
            request: 评估请求

        Returns:
            DomainResponse: 评估结果（score: 1.0=true, 0.0=false）
        """
        # 1. 输入验证
        if error := self.validate_input(request):
            return error
        if error := self.require_client_with_error():
            return error

        # 2. 提取数据
        actual_output = self._extract_actual_output(request)
        context = self._extract_context(request)

        # 3. 构建 Prompt
        prompt = self._build_prompt(actual_output, context)

        # 4. 调用 LLM 并解析结果
        try:
            llm_output = self.client.chat(prompt)
            category = self.safe_parse_category(llm_output, allowed_categories=["true", "false"])

            if not category:
                logger.error(f"事实核查标签提取失败: '{llm_output}'")
                return self.create_error_response(
                    error_message=f"无法解析标签: {llm_output[:100]}",
                    error_code="CATEGORY_PARSE_ERROR",
                )

            # 二分类评分：true=1.0, false=0.0
            score = 1.0 if category == "true" else 0.0

            return self.create_success_response(
                text=actual_output,
                score=score,
                data={
                    "fact_check_label": category,
                    "has_hallucination": category == "false",
                    "context": context,
                    "raw_output": llm_output,
                    "evaluator": "fact_check",
                },
            )

        except Exception as e:
            logger.exception(f"事实核查评估器 LLM 调用失败: {e}")
            return self.create_error_response(
                error_message=f"LLM 调用异常: {str(e)}", error_code="LLM_CALL_ERROR"
            )

    def _extract_actual_output(self, request: EvaluationSchema) -> str:
        """提取实际输出

        Args:
            request: 评估请求

        Returns:
            str: 实际输出文本
        """
        return self.get_payload_data(request, "actual_output", default="")

    def _extract_context(self, request: EvaluationSchema) -> str:
        """提取上下文

        Args:
            request: 评估请求

        Returns:
            str: 上下文文本
        """
        return self.get_payload_data(request, "context", default="无上下文背景")

    def _build_prompt(self, actual_output: str, context: str) -> str:
        """构建评估 Prompt

        Args:
            actual_output: 实际输出
            context: 上下文

        Returns:
            str: 构建的 Prompt
        """
        return (
            "你是一个严谨的事实核查员(Fact Checker)。请结合给定的背景上下文，核验实际输出中是否存在幻觉、造假或不实信息。\n"
            "你必须在 [true, false] 中选择一个标签做出果断裁判。\n"
            "- 如果完全符合事实，输出: true\n"
            "- 如果存在任何造假、捏造、捏造事实，输出: false\n\n"
            f"【背景上下文】：{context}\n"
            f"【待核验文本】：{actual_output}\n\n"
            "结论（仅输出 true 或 false）："
        )


## 自检清单
# - [x] 死代码检查：所有 return 语句都在可达路径
# - [x] 类型注解：所有方法都有类型注解
# - [x] 安全扫描：无敏感操作
# - [x] 复杂度：每个方法不超过 50 行
# - [x] 异常处理：包含堆栈追踪，返回明确错误响应
# - [x] 依赖验证：调用的是 BaseEvaluator 的方法
# - [x] 线程安全：无共享状态修改
