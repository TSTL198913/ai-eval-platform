"""
评估器 Payload Schema 定义

为每个评估器定义正式的输入契约，确保：
1. 字段名、类型、是否必填有明确定义
2. API 层可以统一校验
3. 调用方有明确的文档参考
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


# ==================== 基础通用 Schema ====================


class BasePayloadSchema(BaseModel):
    """所有 Payload Schema 的基类"""

    class Config:
        extra = "allow"  # 允许额外字段（前向兼容）


# ==================== Code 评估器 Schema ====================


class CodeMetadata(BaseModel):
    """Code 评估器的 metadata"""
    language: str = Field(default="python", description="编程语言")
    style_guide: str | None = Field(default=None, description="代码风格指南")


class CodePayloadSchema(BasePayloadSchema):
    """Code 评估器 Payload Schema

    必填字段：
    - code: 待评估的代码（字符串或从 actual_output/user_input/text 自动映射）

    可选字段：
    - test_cases: 测试用例列表 [{"input": [...], "expected": ...}]
    - expected_output: 期望输出（用于 LLM 语义审查）
    - system_prompt: 自定义代码审查提示词
    - language: 编程语言（会自动映射到 metadata.language）

    可选字段（已废弃，请使用 code 字段）：
    - actual_output: 已被 Engine 层自动映射为 code
    - user_input: 已被 Engine 层自动映射为 code
    - text: 已被 Engine 层自动映射为 code

    自动映射规则（Engine 层处理）：
    - actual_output/user_input/text → code
    - language → metadata.language
    """

    code: str | None = Field(default=None, description="待评估的代码")
    test_cases: list[dict[str, Any]] | None = Field(default=None, description="测试用例列表")
    expected_output: str | None = Field(default=None, description="期望输出")
    system_prompt: str | None = Field(default=None, description="自定义代码审查提示词")
    language: str | None = Field(default=None, description="编程语言")
    actual_output: str | None = Field(default=None, description="代码（已废弃，请使用 code）")
    user_input: str | None = Field(default=None, description="代码输入（已废弃，请使用 code）")
    text: str | None = Field(default=None, description="代码文本（已废弃，请使用 code）")


# ==================== Semantic 评估器 Schema ====================


class SemanticPayloadSchema(BasePayloadSchema):
    """Semantic 评估器 Payload Schema

    必填字段：
    - actual_output: 实际输出
    - expected_output: 期望输出
    - user_input/text: 用户输入（用于语义理解上下文）

    可选字段：
    - criteria: 自定义评估标准
    """

    actual_output: str = Field(..., description="实际输出")
    expected_output: str = Field(..., description="期望输出")
    user_input: str | None = Field(default=None, description="用户输入")
    text: str | None = Field(default=None, description="用户输入文本")
    criteria: str | None = Field(default=None, description="自定义评估标准")


# ==================== Security 评估器 Schema ====================


class SecurityPayloadSchema(BasePayloadSchema):
    """Security 评估器 Payload Schema

    必填字段：
    - user_input/text: 用户输入（检测 prompt injection）
    - actual_output: 模型输出（检测数据泄露）

    可选字段：
    - tests: 检测项列表 ["injection", "jailbreak", "data_leak", "tool_abuse"]
    - code: 代码（可选，用于代码安全检测）
    """

    user_input: str | None = Field(default=None, description="用户输入")
    text: str | None = Field(default=None, description="用户输入文本")
    actual_output: str | None = Field(default=None, description="模型输出")
    tests: list[str] | None = Field(
        default_factory=lambda: ["injection", "jailbreak", "data_leak", "tool_abuse"],
        description="检测项列表"
    )
    code: str | None = Field(default=None, description="代码（可选）")


# ==================== LLM-as-Judge 评估器 Schema ====================


class LLMJudgePayloadSchema(BasePayloadSchema):
    """LLM-as-Judge 评估器 Payload Schema

    必填字段：
    - user_input/text: 用户输入
    - actual_output: 模型输出

    可选字段：
    - expected_output: 期望输出（用于对比）
    - dimensions: 评估维度列表
    - criteria: 自定义评估标准
    - golden_dataset_id: 黄金数据集 ID
    - few_shot_limit: Few-shot 示例数量限制
    - judge_mode: 裁判模式
    """

    user_input: str | None = Field(default=None, description="用户输入")
    text: str | None = Field(default=None, description="用户输入文本")
    actual_output: str = Field(..., description="模型输出")
    expected_output: str | None = Field(default=None, description="期望输出")
    dimensions: list[str] | None = Field(
        default=None,
        description="评估维度列表，默认使用全部六维度"
    )
    criteria: str | None = Field(default=None, description="自定义评估标准")
    golden_dataset_id: str | None = Field(default=None, description="黄金数据集 ID")
    few_shot_limit: int = Field(default=3, description="Few-shot 示例数量限制")
    judge_mode: str = Field(default="standard", description="裁判模式")


# ==================== Memory 评估器 Schema ====================


class MemoryPayloadSchema(BasePayloadSchema):
    """Memory 评估器 Payload Schema

    必填字段：
    - query/user_input/text: 检索查询

    可选字段：
    - action: 评估动作 ["evaluate_retrieval", "evaluate_consistency", "evaluate_forgetting"]
    - retrieved_context: 检索到的上下文
    - expected_context: 期望的上下文
    - ground_truth: 真实答案
    - memory_content: 记忆内容（用于一致性/遗忘评估）
    - sequence: 记忆序列（用于遗忘评估）
    """

    query: str | None = Field(default=None, description="检索查询")
    user_input: str | None = Field(default=None, description="检索查询")
    text: str | None = Field(default=None, description="检索查询")
    action: str = Field(default="evaluate_retrieval", description="评估动作")
    retrieved_context: str | None = Field(default=None, description="检索到的上下文")
    expected_context: str | None = Field(default=None, description="期望的上下文")
    ground_truth: str | None = Field(default=None, description="真实答案")
    memory_content: str | None = Field(default=None, description="记忆内容")
    sequence: list[str] | None = Field(default=None, description="记忆序列")


# ==================== FunctionCall 评估器 Schema ====================


class FunctionCallPayloadSchema(BasePayloadSchema):
    """FunctionCall 评估器 Payload Schema

    必填字段：
    - 无（但建议提供 expected_tools 和 actual_tools）

    可选字段：
    - action: 评估动作 ["evaluate", "validate_params", "compare_tools", "validate_result"]
    - expected_tools: 期望调用的工具列表
    - actual_tools: 实际调用的工具列表
    - expected_params: 期望的参数
    - actual_params: 实际的参数
    - expected_results: 期望的结果
    - actual_results: 实际的结果
    - tool_definitions: 工具定义列表
    """

    action: str = Field(default="evaluate", description="评估动作")
    expected_tools: list[str] | None = Field(default=None, description="期望调用的工具列表")
    actual_tools: list[str] | None = Field(default=None, description="实际调用的工具列表")
    expected_params: dict[str, Any] | None = Field(default=None, description="期望的参数")
    actual_params: dict[str, Any] | None = Field(default=None, description="实际的参数")
    expected_results: dict[str, Any] | None = Field(default=None, description="期望的结果")
    actual_results: dict[str, Any] | None = Field(default=None, description="实际的结果")
    tool_definitions: list[dict[str, Any]] | None = Field(default=None, description="工具定义列表")


# ==================== Classification 评估器 Schema ====================


class ClassificationPayloadSchema(BasePayloadSchema):
    """Classification 评估器 Payload Schema

    必填字段：
    - user_input/text: 待分类文本
    - expected_label: 期望的标签

    可选字段：
    - actual_label: 实际分类结果
    - labels: 可选标签列表
    """

    user_input: str | None = Field(default=None, description="待分类文本")
    text: str | None = Field(default=None, description="待分类文本")
    expected_label: str = Field(..., description="期望的标签")
    actual_label: str | None = Field(default=None, description="实际分类结果")
    labels: list[str] | None = Field(default=None, description="可选标签列表")


# ==================== General 评估器 Schema ====================


class GeneralPayloadSchema(BasePayloadSchema):
    """General 评估器 Payload Schema

    必填字段：
    - user_input/text: 用户输入
    - expected_output: 期望输出

    可选字段：
    - actual_output: 实际输出（如果未提供，Engine 会自动生成）
    - criteria: 自定义评估标准
    """

    user_input: str | None = Field(default=None, description="用户输入")
    text: str | None = Field(default=None, description="用户输入文本")
    expected_output: str = Field(..., description="期望输出")
    actual_output: str | None = Field(default=None, description="实际输出")
    criteria: str | None = Field(default=None, description="自定义评估标准")


# ==================== QA 评估器 Schema ====================


class QAPayloadSchema(BasePayloadSchema):
    """QA 评估器 Payload Schema

    必填字段：
    - question/user_input/text: 问题
    - expected_answer: 期望答案
    - actual_answer: 实际答案
    """

    question: str | None = Field(default=None, description="问题")
    user_input: str | None = Field(default=None, description="问题")
    text: str | None = Field(default=None, description="问题")
    expected_answer: str = Field(..., description="期望答案")
    actual_answer: str = Field(..., description="实际答案")


# ==================== Factuality 评估器 Schema ====================


class FactualityPayloadSchema(BasePayloadSchema):
    """Factuality 评估器 Payload Schema

    必填字段：
    - user_input/text: 用户输入
    - expected_output: 期望输出

    可选字段：
    - actual_output: 实际输出
    - reference_text: 参考文本
    """

    user_input: str | None = Field(default=None, description="用户输入")
    text: str | None = Field(default=None, description="用户输入文本")
    expected_output: str = Field(..., description="期望输出")
    actual_output: str | None = Field(default=None, description="实际输出")
    reference_text: str | None = Field(default=None, description="参考文本")


# ==================== Schema 注册表 ====================


# 评估器类型到 Payload Schema 的映射
EVALUATOR_PAYLOAD_SCHEMAS: dict[str, type[BasePayloadSchema]] = {
    "code": CodePayloadSchema,
    "semantic": SemanticPayloadSchema,
    "security": SecurityPayloadSchema,
    "llm_as_judge": LLMJudgePayloadSchema,
    "memory": MemoryPayloadSchema,
    "function_call": FunctionCallPayloadSchema,
    "classification": ClassificationPayloadSchema,
    "general": GeneralPayloadSchema,
    "qa": QAPayloadSchema,
    "factuality": FactualityPayloadSchema,
}


def get_payload_schema(evaluator_type: str) -> type[BasePayloadSchema] | None:
    """获取指定评估器类型的 Payload Schema

    Args:
        evaluator_type: 评估器类型

    Returns:
        Payload Schema 类，如果不存在则返回 None
    """
    return EVALUATOR_PAYLOAD_SCHEMAS.get(evaluator_type)


def validate_payload(evaluator_type: str, payload: dict[str, Any]) -> tuple[bool, str | None, dict[str, Any] | None]:
    """校验 payload 是否符合指定评估器的 Schema

    Args:
        evaluator_type: 评估器类型
        payload: 待校验的 payload 数据

    Returns:
        (是否有效, 错误信息, 校验后的 payload)
        如果 Schema 不存在，返回 (True, None, payload)
    """
    schema_class = get_payload_schema(evaluator_type)
    if schema_class is None:
        return True, None, payload

    try:
        validated = schema_class(**payload)
        return True, None, validated.model_dump()
    except Exception as e:
        return False, str(e), None
