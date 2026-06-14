"""
插件系统

支持自定义评测器、数据集、指标等扩展。
"""

import importlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    """插件信息"""

    plugin_id: str
    name: str
    version: str
    author: str
    description: str
    plugin_type: str  # evaluator, dataset, metric
    entry_point: str
    dependencies: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)
    is_enabled: bool = True


class BaseEvaluatorPlugin(ABC):
    """评测器插件基类"""

    @abstractmethod
    async def evaluate(
        self,
        model: str,
        prompts: list[str],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行评测"""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """获取评测器名称"""
        pass

    @abstractmethod
    def get_supported_metrics(self) -> list[str]:
        """获取支持的指标"""
        pass


class BaseDatasetPlugin(ABC):
    """数据集插件基类"""

    @abstractmethod
    async def load_data(self, config: dict[str, Any] | None = None) -> list[dict]:
        """加载数据集"""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """获取数据集名称"""
        pass

    @abstractmethod
    def get_size(self) -> int:
        """获取数据集大小"""
        pass


class BaseMetricPlugin(ABC):
    """指标插件基类"""

    @abstractmethod
    def calculate(
        self,
        predictions: list[str],
        references: list[str],
        config: dict[str, Any] | None = None,
    ) -> float:
        """计算指标"""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """获取指标名称"""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """获取指标描述"""
        pass


class PluginManager:
    """
    插件管理器

    管理评测器、数据集、指标等插件。
    """

    def __init__(self, plugin_dir: str = "plugins"):
        self._plugin_dir = Path(plugin_dir)
        self._plugins: dict[str, PluginInfo] = {}
        self._evaluators: dict[str, BaseEvaluatorPlugin] = {}
        self._datasets: dict[str, BaseDatasetPlugin] = {}
        self._metrics: dict[str, BaseMetricPlugin] = {}

    def discover_plugins(self) -> list[PluginInfo]:
        """发现插件"""
        discovered = []

        if not self._plugin_dir.exists():
            logger.warning(f"Plugin directory {self._plugin_dir} not found")
            return discovered

        # 遍历插件目录
        for plugin_path in self._plugin_dir.iterdir():
            if plugin_path.is_dir():
                # 查找 plugin.json
                config_file = plugin_path / "plugin.json"
                if config_file.exists():
                    try:
                        with open(config_file) as f:
                            config = json.load(f)

                        plugin_info = PluginInfo(
                            plugin_id=config.get("plugin_id", plugin_path.name),
                            name=config.get("name", ""),
                            version=config.get("version", "1.0.0"),
                            author=config.get("author", ""),
                            description=config.get("description", ""),
                            plugin_type=config.get("type", "evaluator"),
                            entry_point=config.get("entry_point", "main"),
                            dependencies=config.get("dependencies", []),
                            config_schema=config.get("config_schema", {}),
                        )

                        discovered.append(plugin_info)
                        self._plugins[plugin_info.plugin_id] = plugin_info

                        logger.info(f"Discovered plugin: {plugin_info.name}")

                    except Exception as e:
                        logger.error(f"Failed to load plugin config: {e}")

        return discovered

    def load_plugin(self, plugin_id: str) -> bool:
        """加载插件"""
        plugin_info = self._plugins.get(plugin_id)
        if not plugin_info:
            logger.error(f"Plugin {plugin_id} not found")
            return False

        try:
            # 导入插件模块
            module_path = f"plugins.{plugin_id}.{plugin_info.entry_point}"
            module = importlib.import_module(module_path)

            # 根据类型加载
            if plugin_info.plugin_type == "evaluator":
                evaluator_class = getattr(module, "Evaluator", None)
                if evaluator_class:
                    evaluator = evaluator_class()
                    self._evaluators[plugin_info.name] = evaluator
                    logger.info(f"Loaded evaluator plugin: {plugin_info.name}")

            elif plugin_info.plugin_type == "dataset":
                dataset_class = getattr(module, "Dataset", None)
                if dataset_class:
                    dataset = dataset_class()
                    self._datasets[plugin_info.name] = dataset
                    logger.info(f"Loaded dataset plugin: {plugin_info.name}")

            elif plugin_info.plugin_type == "metric":
                metric_class = getattr(module, "Metric", None)
                if metric_class:
                    metric = metric_class()
                    self._metrics[plugin_info.name] = metric
                    logger.info(f"Loaded metric plugin: {plugin_info.name}")

            return True

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_id}: {e}")
            return False

    def unload_plugin(self, plugin_id: str) -> bool:
        """卸载插件"""
        plugin_info = self._plugins.get(plugin_id)
        if not plugin_info:
            return False

        # 从对应集合中移除
        if plugin_info.plugin_type == "evaluator":
            if plugin_info.name in self._evaluators:
                del self._evaluators[plugin_info.name]

        elif plugin_info.plugin_type == "dataset":
            if plugin_info.name in self._datasets:
                del self._datasets[plugin_info.name]

        elif plugin_info.plugin_type == "metric":
            if plugin_info.name in self._metrics:
                del self._metrics[plugin_info.name]

        logger.info(f"Unloaded plugin: {plugin_info.name}")
        return True

    def get_evaluator(self, name: str) -> BaseEvaluatorPlugin | None:
        """获取评测器"""
        return self._evaluators.get(name)

    def get_dataset(self, name: str) -> BaseDatasetPlugin | None:
        """获取数据集"""
        return self._datasets.get(name)

    def get_metric(self, name: str) -> BaseMetricPlugin | None:
        """获取指标"""
        return self._metrics.get(name)

    def list_evaluators(self) -> list[str]:
        """列出所有评测器"""
        return list(self._evaluators.keys())

    def list_datasets(self) -> list[str]:
        """列出所有数据集"""
        return list(self._datasets.keys())

    def list_metrics(self) -> list[str]:
        """列出所有指标"""
        return list(self._metrics.keys())

    def enable_plugin(self, plugin_id: str) -> bool:
        """启用插件"""
        if plugin_id in self._plugins:
            self._plugins[plugin_id].is_enabled = True
            return True
        return False

    def disable_plugin(self, plugin_id: str) -> bool:
        """禁用插件"""
        if plugin_id in self._plugins:
            self._plugins[plugin_id].is_enabled = False
            return True
        return False

    def get_plugin_info(self, plugin_id: str) -> PluginInfo | None:
        """获取插件信息"""
        return self._plugins.get(plugin_id)

    def get_all_plugins(self) -> list[PluginInfo]:
        """获取所有插件"""
        return list(self._plugins.values())


# 示例插件实现
class CustomAccuracyMetric(BaseMetricPlugin):
    """自定义准确率指标"""

    def calculate(
        self,
        predictions: list[str],
        references: list[str],
        config: dict[str, Any] | None = None,
    ) -> float:
        """计算准确率"""
        if len(predictions) != len(references):
            raise ValueError("Predictions and references must have same length")

        correct = 0
        for pred, ref in zip(predictions, references):
            if pred.strip().lower() == ref.strip().lower():
                correct += 1

        return correct / len(predictions) if predictions else 0.0

    def get_name(self) -> str:
        return "custom_accuracy"

    def get_description(self) -> str:
        return "自定义准确率计算，支持字符串匹配"


class CustomDataset(BaseDatasetPlugin):
    """自定义数据集"""

    def __init__(self, data_path: str | None = None):
        self._data_path = data_path
        self._data: list[dict] = []

    async def load_data(self, config: dict[str, Any] | None = None) -> list[dict]:
        """加载数据"""
        # 模拟加载
        if not self._data:
            self._data = [
                {"question": "What is AI?", "answer": "Artificial Intelligence"},
                {"question": "What is ML?", "answer": "Machine Learning"},
            ]
        return self._data

    def get_name(self) -> str:
        return "custom_dataset"

    def get_size(self) -> int:
        return len(self._data)


class PluginRegistry:
    """
    插件注册中心

    提供插件注册和查询功能。
    """

    def __init__(self):
        self._registry: dict[str, dict[str, Any]] = {}

    def register_plugin(self, plugin_info: PluginInfo):
        """注册插件"""
        self._registry[plugin_info.plugin_id] = {
            "info": plugin_info,
            "status": "registered",
            "registered_at": time.time(),
        }
        logger.info(f"Registered plugin: {plugin_info.plugin_id}")

    def unregister_plugin(self, plugin_id: str):
        """注销插件"""
        if plugin_id in self._registry:
            del self._registry[plugin_id]
            logger.info(f"Unregistered plugin: {plugin_id}")

    def search_plugins(
        self,
        plugin_type: str | None = None,
        name: str | None = None,
    ) -> list[PluginInfo]:
        """搜索插件"""
        results = []
        for entry in self._registry.values():
            info = entry["info"]
            if plugin_type and info.plugin_type != plugin_type:
                continue
            if name and name not in info.name:
                continue
            results.append(info)
        return results

    def get_plugin_status(self, plugin_id: str) -> str | None:
        """获取插件状态"""
        if plugin_id in self._registry:
            return self._registry[plugin_id]["status"]
        return None


# 全局插件管理器
_global_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """获取全局插件管理器"""
    if _global_plugin_manager is None:
        _global_plugin_manager = PluginManager()
    return _global_plugin_manager