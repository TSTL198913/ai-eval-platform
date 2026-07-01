"""
评估阈值配置 - 2026工业级标准

每个评估器类型可以配置独立的通过阈值，而不是共用一个全局阈值。
配置路径：config/evaluation_thresholds.yaml
"""

from pathlib import Path
from typing import Any

import yaml

# 默认阈值配置（如果配置文件不存在或加载失败时使用）
DEFAULT_THRESHOLDS: dict[str, float] = {
    "code": 0.8,          # 代码评估
    "semantic": 0.8,      # 语义评估
    "security": 0.9,      # 安全评估（更严格）
    "llm_as_judge": 0.8,  # LLM裁判
    "memory": 0.75,        # 记忆评估
    "function_call": 0.8, # 函数调用
    "classification": 0.85,  # 分类评估
    "general": 0.8,        # 通用评估
    "qa": 0.8,             # 问答评估
    "factuality": 0.85,    # 事实性评估
    "default": 0.8,         # 默认阈值
}

# 全局默认值
DEFAULT_PASS_THRESHOLD = 0.8
DEFAULT_CONFIDENCE_THRESHOLD = 0.7  # 置信度阈值，低于此值不信任评估结果


class ThresholdConfig:
    """评估阈值配置管理器"""

    _instance = None
    _thresholds: dict[str, float] = {}
    _confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    _loaded: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, config_path: str | Path | None = None) -> None:
        """从配置文件加载阈值

        Args:
            config_path: 配置文件路径，默认为 config/evaluation_thresholds.yaml
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "evaluation_thresholds.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            self._thresholds = DEFAULT_THRESHOLDS.copy()
            self._loaded = True
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            self._thresholds = config.get("thresholds", DEFAULT_THRESHOLDS)
            self._confidence_threshold = config.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
            self._loaded = True
        except Exception as e:
            # 配置加载失败，使用默认值
            self._thresholds = DEFAULT_THRESHOLDS.copy()
            self._confidence_threshold = DEFAULT_CONFIDENCE_THRESHOLD
            self._loaded = True

    def get_threshold(self, evaluator_type: str) -> float:
        """获取指定评估器类型的通过阈值

        Args:
            evaluator_type: 评估器类型

        Returns:
            通过阈值
        """
        if not self._loaded:
            self.load()

        return self._thresholds.get(evaluator_type, self._thresholds.get("default", DEFAULT_PASS_THRESHOLD))

    def get_confidence_threshold(self) -> float:
        """获取置信度阈值

        Returns:
            置信度阈值，低于此值的评估结果应被标记为不可信
        """
        if not self._loaded:
            self.load()

        return self._confidence_threshold

    def is_trusted(self, confidence: float | None, evaluator_type: str) -> tuple[bool, str]:
        """判断评估结果是否可信

        Args:
            confidence: 评估置信度
            evaluator_type: 评估器类型

        Returns:
            (是否可信, 原因)
        """
        confidence_threshold = self.get_confidence_threshold()
        pass_threshold = self.get_threshold(evaluator_type)

        if confidence is None:
            return False, "无置信度信息，无法判断可信度"

        if confidence < confidence_threshold:
            return False, f"置信度 {confidence:.2f} 低于阈值 {confidence_threshold:.2f}"

        return True, f"置信度 {confidence:.2f} 高于阈值 {confidence_threshold:.2f}"


# 全局配置实例
_threshold_config: ThresholdConfig | None = None


def get_threshold_config() -> ThresholdConfig:
    """获取阈值配置实例（单例）"""
    global _threshold_config
    if _threshold_config is None:
        _threshold_config = ThresholdConfig()
        _threshold_config.load()
    return _threshold_config


def get_pass_threshold(evaluator_type: str) -> float:
    """获取指定评估器类型的通过阈值"""
    return get_threshold_config().get_threshold(evaluator_type)


def get_confidence_threshold() -> float:
    """获取置信度阈值"""
    return get_threshold_config().get_confidence_threshold()


def is_result_trusted(confidence: float | None, evaluator_type: str) -> tuple[bool, str]:
    """判断评估结果是否可信"""
    return get_threshold_config().is_trusted(confidence, evaluator_type)
