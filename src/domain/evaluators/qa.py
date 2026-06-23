"""
问答(QA)评估器 - 2026 工业级标准重构版

用于评估问答系统的输出质量，包括：
- 回答准确性评估
- 事实一致性检查
- 关键信息完整性验证

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


@EvaluatorFactory.register("qa")
class QAEvaluator(BaseEvaluator):
    """问答评估器（严格语义策略，禁止静默降级）"""

    def __init__(self, client: Any | None = None) -> None:
        """初始化问答评估器

        Args:
            client: LLM 客户端实例（可选）
        """
        super().__init__(client, fallback_policy=StrictSemanticPolicy())

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """评估问答质量

        Args:
            request: 评估请求

        Returns:
            DomainResponse: 评估结果

        Raises:
            无显式异常，所有错误通过 DomainResponse 返回
        """
        # 1. 输入验证
        if error := self.validate_input(request):
            return error
        if error := self.validate_expected(request):
            return error
        if error := self.require_client_with_error():
            return error

        # 2. 提取数据
        question = self._extract_question(request)
        actual_output = self._extract_actual_output(request)
        expected_output = self._extract_expected_output(request)

        # 3. 构建 Prompt
        prompt = self._build_prompt(question, actual_output, expected_output)

        # 4. 调用 LLM 并解析结果
        try:
            llm_output = self.client.chat(prompt)
            score = self.safe_parse_score(llm_output)

            if score is None:
                logger.error(f"QA 评测响应数字提取失败: '{llm_output}'")
                return self.create_error_response(
                    error_message=f"无法解析评分: {llm_output[:100]}",
                    error_code="SCORE_PARSE_ERROR",
                )

            return self.create_success_response(
                text=actual_output,
                score=score,
                data={
                    "question": question,
                    "expected_output": expected_output,
                    "raw_output": llm_output,
                    "evaluator": "qa",
                },
            )

        except Exception as e:
            logger.exception(f"QA 评估器 LLM 调用失败: {e}")
            return self.create_error_response(
                error_message=f"LLM 调用异常: {str(e)}", error_code="LLM_CALL_ERROR"
            )

    def _extract_question(self, request: EvaluationSchema) -> str:
        """提取问题文本

        Args:
            request: 评估请求

        Returns:
            str: 问题文本
        """
        return self.get_payload_data(request, "question", default="未知问题")

    def _extract_actual_output(self, request: EvaluationSchema) -> str:
        """提取实际输出

        Args:
            request: 评估请求

        Returns:
            str: 实际输出文本
        """
        return self.get_payload_data(request, "actual_output", default="")

    def _extract_expected_output(self, request: EvaluationSchema) -> str:
        """提取期望输出

        Args:
            request: 评估请求

        Returns:
            str: 期望输出文本
        """
        return self.get_payload_data(request, "expected_output", default="")

    def _build_prompt(self, question: str, actual_output: str, expected_output: str) -> str:
        """构建评估 Prompt

        Args:
            question: 问题文本
            actual_output: 实际输出
            expected_output: 期望输出

        Returns:
            str: 构建的 Prompt
        """
        return (
            "你是一个资深的问答(QA)质量评测专家。请结合原始问题和标准答案，评估实际回答的正确性。\n"
            "判断实际回答是否准确回答了问题，且没有事实性反常或关键信息缺失。\n"
            "输出一个 0.0 到 1.0 的分数。\n\n"
            f"【原始问题】：{question}\n"
            f"【标准答案】：{expected_output}\n"
            f"【实际回答】：{actual_output}\n\n"
            "最终评分（仅输出数字）："
        )


## 自检清单
# - [x] 死代码检查：所有 return 语句都在可达路径
# - [x] 类型注解：所有方法都有类型注解
# - [x] 安全扫描：无敏感操作
# - [x] 复杂度：每个方法不超过 50 行
# - [x] 异常处理：包含堆栈追踪，返回明确错误响应
# - [x] 依赖验证：调用的是 BaseEvaluator 的方法
# - [x] 线程安全：无共享状态修改
