"""测试 src/infra/plugins.py - 插件系统模块"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.infra.plugins import (
    BaseDatasetPlugin,
    BaseEvaluatorPlugin,
    BaseMetricPlugin,
    PluginInfo,
    PluginManager,
)


class TestPluginInfo:
    """测试插件信息"""

    def test_creation_defaults(self):
        """测试默认属性"""
        info = PluginInfo(
            plugin_id="test-eval",
            name="Test Evaluator",
            version="1.0.0",
            author="tester",
            description="A test plugin",
            plugin_type="evaluator",
            entry_point="main",
        )
        assert info.dependencies == []
        assert info.config_schema == {}
        assert info.is_enabled is True

    def test_creation_with_options(self):
        """测试完整属性"""
        info = PluginInfo(
            plugin_id="test-eval",
            name="Test Evaluator",
            version="1.0.0",
            author="tester",
            description="A test plugin",
            plugin_type="evaluator",
            entry_point="main",
            dependencies=["numpy", "torch"],
            config_schema={"batch_size": {"type": "integer"}},
            is_enabled=False,
        )
        assert info.dependencies == ["numpy", "torch"]
        assert info.config_schema == {"batch_size": {"type": "integer"}}
        assert info.is_enabled is False


class MockEvaluatorPlugin(BaseEvaluatorPlugin):
    """模拟评测器插件"""

    async def evaluate(self, model, prompts, config=None):
        return {"score": 0.9}

    def get_name(self):
        return "MockEvaluator"

    def get_supported_metrics(self):
        return ["accuracy"]


class MockDatasetPlugin(BaseDatasetPlugin):
    """模拟数据集插件"""

    async def load_data(self, config=None):
        return [{"input": "hello", "output": "world"}]

    def get_name(self):
        return "MockDataset"

    def get_size(self):
        return 1


class MockMetricPlugin(BaseMetricPlugin):
    """模拟指标插件"""

    def calculate(self, predictions, references, config=None):
        return 0.95

    def get_name(self):
        return "MockMetric"

    def get_description(self):
        return "A mock metric"


class TestPluginManager:
    """测试插件管理器"""

    @pytest.fixture
    def manager(self, tmp_path):
        return PluginManager(plugin_dir=str(tmp_path / "plugins"))

    def test_init_default_dir(self):
        """测试默认目录初始化"""
        pm = PluginManager()
        assert pm._plugin_dir == Path("plugins")

    def test_discover_plugins_empty_dir(self, manager):
        """测试空目录返回空列表"""
        plugins = manager.discover_plugins()
        assert plugins == []

    def test_discover_plugins_with_valid_config(self, manager, tmp_path):
        """测试发现有效插件"""
        plugin_dir = tmp_path / "plugins" / "my-plugin"
        plugin_dir.mkdir(parents=True)

        config = {
            "plugin_id": "my-plugin",
            "name": "My Plugin",
            "version": "1.0.0",
            "author": "tester",
            "description": "A test plugin",
            "type": "evaluator",
            "entry_point": "main",
            "dependencies": ["numpy"],
        }
        (plugin_dir / "plugin.json").write_text(json.dumps(config))

        plugins = manager.discover_plugins()
        assert len(plugins) == 1
        assert plugins[0].plugin_id == "my-plugin"
        assert plugins[0].name == "My Plugin"
        assert plugins[0].dependencies == ["numpy"]

    def test_discover_plugins_invalid_json(self, manager, tmp_path):
        """测试无效 JSON 被跳过"""
        plugin_dir = tmp_path / "plugins" / "bad-plugin"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text("not valid json")

        plugins = manager.discover_plugins()
        assert plugins == []

    def test_discover_plugins_missing_config(self, manager, tmp_path):
        """测试缺少 plugin.json 的目录被忽略"""
        plugin_dir = tmp_path / "plugins" / "no-config"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "main.py").write_text("# empty")

        plugins = manager.discover_plugins()
        assert plugins == []

    def test_load_plugin_not_found(self, manager):
        """测试加载不存在的插件"""
        assert manager.load_plugin("non-existent") is False

    def test_unload_plugin_not_found(self, manager):
        """测试卸载不存在的插件"""
        assert manager.unload_plugin("non-existent") is False

    def test_enable_disable_plugin(self, manager):
        """测试启用和禁用插件"""
        info = PluginInfo(
            plugin_id="test-1",
            name="Test",
            version="1.0.0",
            author="a",
            description="d",
            plugin_type="evaluator",
            entry_point="main",
        )
        manager._plugins["test-1"] = info

        assert info.is_enabled is True
        manager.disable_plugin("test-1")
        assert info.is_enabled is False
        manager.enable_plugin("test-1")
        assert info.is_enabled is True

    def test_enable_disable_plugin_not_found(self, manager):
        """测试启用/禁用不存在的插件"""
        assert manager.enable_plugin("non-existent") is False
        assert manager.disable_plugin("non-existent") is False

    def test_get_plugin_info(self, manager):
        """测试获取插件信息"""
        info = PluginInfo(
            plugin_id="test-1",
            name="Test",
            version="1.0.0",
            author="a",
            description="d",
            plugin_type="evaluator",
            entry_point="main",
        )
        manager._plugins["test-1"] = info

        assert manager.get_plugin_info("test-1") == info
        assert manager.get_plugin_info("non-existent") is None

    def test_register_evaluator(self, manager):
        """测试注册评测器"""
        evaluator = MockEvaluatorPlugin()
        manager._evaluators["mock"] = evaluator

        assert manager.get_evaluator("mock") == evaluator
        assert manager.get_evaluator("non-existent") is None
        assert manager.list_evaluators() == ["mock"]

    def test_register_dataset(self, manager):
        """测试注册数据集"""
        dataset = MockDatasetPlugin()
        manager._datasets["mock"] = dataset

        assert manager.get_dataset("mock") == dataset
        assert manager.get_dataset("non-existent") is None
        assert manager.list_datasets() == ["mock"]

    def test_register_metric(self, manager):
        """测试注册指标"""
        metric = MockMetricPlugin()
        manager._metrics["mock"] = metric

        assert manager.get_metric("mock") == metric
        assert manager.get_metric("non-existent") is None
        assert manager.list_metrics() == ["mock"]

    def test_unload_evaluator(self, manager):
        """测试卸载评测器"""
        info = PluginInfo(
            plugin_id="test-eval",
            name="MyEval",
            version="1.0.0",
            author="a",
            description="d",
            plugin_type="evaluator",
            entry_point="main",
        )
        manager._plugins["test-eval"] = info
        manager._evaluators["MyEval"] = MockEvaluatorPlugin()

        assert manager.unload_plugin("test-eval") is True
        assert "MyEval" not in manager._evaluators

    def test_unload_dataset(self, manager):
        """测试卸载数据集"""
        info = PluginInfo(
            plugin_id="test-ds",
            name="MyDataset",
            version="1.0.0",
            author="a",
            description="d",
            plugin_type="dataset",
            entry_point="main",
        )
        manager._plugins["test-ds"] = info
        manager._datasets["MyDataset"] = MockDatasetPlugin()

        assert manager.unload_plugin("test-ds") is True
        assert "MyDataset" not in manager._datasets

    def test_unload_metric(self, manager):
        """测试卸载指标"""
        info = PluginInfo(
            plugin_id="test-metric",
            name="MyMetric",
            version="1.0.0",
            author="a",
            description="d",
            plugin_type="metric",
            entry_point="main",
        )
        manager._plugins["test-metric"] = info
        manager._metrics["MyMetric"] = MockMetricPlugin()

        assert manager.unload_plugin("test-metric") is True
        assert "MyMetric" not in manager._metrics

    def test_discover_plugins_default_values(self, manager, tmp_path):
        """测试 plugin.json 缺少字段时使用默认值"""
        plugin_dir = tmp_path / "plugins" / "minimal"
        plugin_dir.mkdir(parents=True)

        config = {"plugin_id": "minimal"}  # 仅提供必需字段
        (plugin_dir / "plugin.json").write_text(json.dumps(config))

        plugins = manager.discover_plugins()
        assert len(plugins) == 1
        assert plugins[0].name == ""
        assert plugins[0].version == "1.0.0"
        assert plugins[0].author == ""
        assert plugins[0].plugin_type == "evaluator"
        assert plugins[0].entry_point == "main"
        assert plugins[0].dependencies == []

    def test_discover_plugins_multiple(self, manager, tmp_path):
        """测试发现多个插件"""
        for name in ["plugin-a", "plugin-b"]:
            plugin_dir = tmp_path / "plugins" / name
            plugin_dir.mkdir(parents=True)
            config = {
                "plugin_id": name,
                "name": name.upper(),
                "version": "1.0.0",
                "author": "tester",
                "description": f"Plugin {name}",
                "type": "evaluator",
                "entry_point": "main",
            }
            (plugin_dir / "plugin.json").write_text(json.dumps(config))

        plugins = manager.discover_plugins()
        assert len(plugins) == 2
        ids = {p.plugin_id for p in plugins}
        assert ids == {"plugin-a", "plugin-b"}

    def test_load_plugin_import_error(self, manager):
        """测试插件导入失败"""
        info = PluginInfo(
            plugin_id="bad-plugin",
            name="BadPlugin",
            version="1.0.0",
            author="a",
            description="d",
            plugin_type="evaluator",
            entry_point="main",
        )
        manager._plugins["bad-plugin"] = info

        # 尝试导入不存在的模块会失败
        assert manager.load_plugin("bad-plugin") is False
