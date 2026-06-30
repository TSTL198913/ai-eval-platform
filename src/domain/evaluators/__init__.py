import importlib
import os
import pkgutil
import sys
from typing import Any

from .evaluator_factory import EvaluatorFactory

_EVALUATOR_REGISTRY: dict[str, Any] | None = None

IS_TESTING = os.environ.get("TESTING", "0") == "1"

# 不应自动发现的子模块（工具/基类）
_SKIP_MODULES = {
    "base",
    "metadata",
    "evaluator_factory",
    "embedding_service",
    "logging_utils",
    "scoring",
    "scoring_utils",
    "strategies",
}

# 评估器精简策略（v2.0）
# 核心评估器（10个）：经过黄金数据集验证，Kappa≥0.6
# 扩展评估器（5个）：功能完善，测试覆盖完整
# 候选评估器（22个）：功能待完善，暂不启用
_EVALUATOR_BLACKLIST = {
    # 重复功能：与其他评估器重叠
    "text",  # 与semantic重复
    "text_similarity_base",  # 基类，不应直接使用
    "sentiment",  # 与classification重叠
    "grammar",  # 与code_review重叠
    "summary",  # 与general重叠
    "translation",  # 与general重叠
    "multilingual",  # 与translation重叠
    "fact_check",  # 与factuality重叠
    "finance",  # 与business_rubrics重叠
    # 功能待完善：缺少测试或实现不完整
    "drift",  # 漂移检测逻辑待完善
    "prompt_sensitivity",  # 提示词敏感度待完善
    "prompt_regression",  # 提示词回归测试待完善
    "judge_robustness",  # 评判器鲁棒性待完善
    "multi_judge_ensemble",  # 多评判器集成待完善
    "multi_metric",  # 多指标待完善
    "standard_metric",  # 标准指标待完善
    "ragas",  # 依赖未安装
    "deepeval",  # 依赖未安装
    # 元评估器：仅内部使用
    "meta_test",  # 元测试框架，不对外暴露
    # 高级评估器：需要更多业务场景验证
    "planning",  # 规划评估器
    "trajectory",  # 轨迹评估器
    "runtime_agent",  # 运行时代理评估器
    "tool_use",  # 工具使用评估器
}


def auto_discover(force: bool = False):
    """自动发现并注册所有评估器

    Args:
        force: 强制重新发现（清除 sys.modules 缓存后重新 import）
    """
    global _EVALUATOR_REGISTRY
    if force:
        to_remove = [
            name
            for name in list(sys.modules.keys())
            if name.startswith("src.domain.evaluators.")
            and name != "src.domain.evaluators"
            and name.split(".")[-1] not in _SKIP_MODULES
        ]
        for name in to_remove:
            del sys.modules[name]
        _EVALUATOR_REGISTRY = None

    if _EVALUATOR_REGISTRY is None:
        for _, name, _is_pkg in pkgutil.iter_modules(__path__):
            if name not in _SKIP_MODULES and name not in _EVALUATOR_BLACKLIST:
                importlib.import_module(f".{name}", package=__name__)
        _EVALUATOR_REGISTRY = EvaluatorFactory._registry
    return _EVALUATOR_REGISTRY


def list_core_evaluators() -> list[str]:
    """列出核心评估器（15个）"""
    return [
        "general",
        "code",
        "code_review",
        "security",
        "memory",
        "semantic",
        "qa",
        "factuality",
        "risk",
        "classification",
        "composite",
        "function_call",
        "multi_agent",
        "llm_as_judge",
        "robustness",
    ]


def lazy_discover():
    """延迟发现评估器，确保在测试环境下也能正常工作"""
    return auto_discover()


# 始终调用 auto_discover 以确保评估器已注册
EVALUATOR_REGISTRY = auto_discover()
