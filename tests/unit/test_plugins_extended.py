import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.infra.plugins import (
    CustomAccuracyMetric,
    CustomDataset,
    PluginInfo,
    PluginManager,
    PluginRegistry,
    get_plugin_manager,
)


class TestPluginInfo:
    """插件信息测试"""

    def test_plugin_info_defaults(self):
        """测试默认值"""
        info = PluginInfo(
            plugin_id="test",
            name="Test Plugin",
            version="1.0.0",
            author="tester",
            description="A test plugin",
            plugin_type="evaluator",
            entry_point="main",
        )

        assert info.dependencies == []
        assert info.config_schema == {}
        assert info.is_enabled is True


class TestCustomAccuracyMetric:
    """自定义准确率指标测试"""

    def test_calculate_accuracy(self):
        """测试准确率计算"""
        metric = CustomAccuracyMetric()
        predictions = ["A", "B", "C"]
        references = ["A", "b", "D"]

        accuracy = metric.calculate(predictions, references)

        assert accuracy == 2 / 3

    def test_calculate_empty(self):
        """测试空列表"""
        metric = CustomAccuracyMetric()
        accuracy = metric.calculate([], [])

        assert accuracy == 0.0

    def test_calculate_mismatch_length(self):
        """测试长度不匹配"""
        metric = CustomAccuracyMetric()

        with pytest.raises(ValueError):
            metric.calculate(["A"], ["A", "B"])

    def test_get_name(self):
        """测试名称"""
        metric = CustomAccuracyMetric()
        assert metric.get_name() == "custom_accuracy"

    def test_get_description(self):
        """测试描述"""
        metric = CustomAccuracyMetric()
        assert "准确率" in metric.get_description()


class TestCustomDataset:
    """自定义数据集测试"""

    def test_get_name(self):
        """测试名称"""
        dataset = CustomDataset()
        assert dataset.get_name() == "custom_dataset"

    def test_get_size_empty(self):
        """测试空数据集大小"""
        dataset = CustomDataset()
        assert dataset.get_size() == 0

    def test_load_data(self):
        """测试加载数据"""
        dataset = CustomDataset()
        data = asyncio.run(dataset.load_data())

        assert len(data) == 2
        assert "question" in data[0]

    def test_get_size_after_load(self):
        """测试加载后大小"""
        dataset = CustomDataset()
        asyncio.run(dataset.load_data())

        assert dataset.get_size() == 2


class TestPluginManager:
    """插件管理器测试"""

    def setup_method(self):
        self.manager = PluginManager(plugin_dir="/tmp/nonexistent_plugins")

    def test_discover_plugins_no_dir(self):
        """测试无插件目录"""
        plugins = self.manager.discover_plugins()
        assert plugins == []

    @patch("src.infra.plugins.Path.exists")
    @patch("src.infra.plugins.Path.iterdir")
    def test_discover_plugins_with_valid_plugin(self, mock_iterdir, mock_exists):
        """测试发现有效插件"""
        mock_exists.return_value = True

        mock_plugin_dir = MagicMock()
        mock_plugin_dir.is_dir.return_value = True
        mock_plugin_dir.name = "test_plugin"

        mock_config_file = MagicMock()
        mock_config_file.exists.return_value = True
        mock_plugin_dir.__truediv__ = MagicMock(return_value=mock_config_file)

        mock_config_file.open = MagicMock()
        mock_config_file.open.return_value.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value='{"plugin_id": "test", "name": "Test"}')))
        mock_config_file.open.return_value.__exit__ = MagicMock(return_value=False)

        mock_iterdir.return_value = [mock_plugin_dir]

        plugins = self.manager.discover_plugins()
        assert isinstance(plugins, list)

    def test_load_plugin_not_found(self):
        """测试加载不存在的插件"""
        result = self.manager.load_plugin("nonexistent")
        assert result is False

    def test_unload_plugin_not_found(self):
        """测试卸载不存在的插件"""
        result = self.manager.unload_plugin("nonexistent")
        assert result is False

    def test_get_evaluator_none(self):
        """测试获取不存在的评估器"""
        assert self.manager.get_evaluator("nonexistent") is None

    def test_get_dataset_none(self):
        """测试获取不存在的数据集"""
        assert self.manager.get_dataset("nonexistent") is None

    def test_get_metric_none(self):
        """测试获取不存在的指标"""
        assert self.manager.get_metric("nonexistent") is None

    def test_list_evaluators_empty(self):
        """测试空评估器列表"""
        assert self.manager.list_evaluators() == []

    def test_list_datasets_empty(self):
        """测试空数据集列表"""
        assert self.manager.list_datasets() == []

    def test_list_metrics_empty(self):
        """测试空指标列表"""
        assert self.manager.list_metrics() == []

    def test_enable_plugin_not_found(self):
        """测试启用不存在的插件"""
        assert self.manager.enable_plugin("nonexistent") is False

    def test_disable_plugin_not_found(self):
        """测试禁用不存在的插件"""
        assert self.manager.disable_plugin("nonexistent") is False

    def test_get_plugin_info_none(self):
        """测试获取不存在的插件信息"""
        assert self.manager.get_plugin_info("nonexistent") is None

    def test_get_all_plugins_empty(self):
        """测试空插件列表"""
        assert self.manager.get_all_plugins() == []

    def test_enable_disable_plugin(self):
        """测试启用禁用插件"""
        info = PluginInfo(
            plugin_id="test",
            name="Test",
            version="1.0",
            author="a",
            description="d",
            plugin_type="evaluator",
            entry_point="main",
        )
        self.manager._plugins["test"] = info

        assert self.manager.enable_plugin("test") is True
        assert info.is_enabled is True

        assert self.manager.disable_plugin("test") is True
        assert info.is_enabled is False

    @patch("src.infra.plugins.importlib.import_module")
    def test_load_plugin_evaluator(self, mock_import):
        """测试加载评估器插件"""
        mock_module = MagicMock()
        mock_evaluator = MagicMock()
        mock_module.Evaluator = mock_evaluator
        mock_import.return_value = mock_module

        info = PluginInfo(
            plugin_id="test_eval",
            name="TestEval",
            version="1.0",
            author="a",
            description="d",
            plugin_type="evaluator",
            entry_point="main",
        )
        self.manager._plugins["test_eval"] = info

        result = self.manager.load_plugin("test_eval")
        assert result is True
        assert "TestEval" in self.manager._evaluators

    @patch("src.infra.plugins.importlib.import_module")
    def test_load_plugin_dataset(self, mock_import):
        """测试加载数据集插件"""
        mock_module = MagicMock()
        mock_dataset = MagicMock()
        mock_module.Dataset = mock_dataset
        mock_import.return_value = mock_module

        info = PluginInfo(
            plugin_id="test_dataset",
            name="TestDataset",
            version="1.0",
            author="a",
            description="d",
            plugin_type="dataset",
            entry_point="main",
        )
        self.manager._plugins["test_dataset"] = info

        result = self.manager.load_plugin("test_dataset")
        assert result is True
        assert "TestDataset" in self.manager._datasets

    @patch("src.infra.plugins.importlib.import_module")
    def test_load_plugin_metric(self, mock_import):
        """测试加载指标插件"""
        mock_module = MagicMock()
        mock_metric = MagicMock()
        mock_module.Metric = mock_metric
        mock_import.return_value = mock_module

        info = PluginInfo(
            plugin_id="test_metric",
            name="TestMetric",
            version="1.0",
            author="a",
            description="d",
            plugin_type="metric",
            entry_point="main",
        )
        self.manager._plugins["test_metric"] = info

        result = self.manager.load_plugin("test_metric")
        assert result is True
        assert "TestMetric" in self.manager._metrics

    @patch("src.infra.plugins.importlib.import_module")
    def test_load_plugin_exception(self, mock_import):
        """测试加载插件异常"""
        mock_import.side_effect = ImportError("Module not found")

        info = PluginInfo(
            plugin_id="test_err",
            name="TestErr",
            version="1.0",
            author="a",
            description="d",
            plugin_type="evaluator",
            entry_point="main",
        )
        self.manager._plugins["test_err"] = info

        result = self.manager.load_plugin("test_err")
        assert result is False

    def test_unload_plugin_evaluator(self):
        """测试卸载评估器插件"""
        info = PluginInfo(
            plugin_id="test_eval",
            name="TestEval",
            version="1.0",
            author="a",
            description="d",
            plugin_type="evaluator",
            entry_point="main",
        )
        self.manager._plugins["test_eval"] = info
        self.manager._evaluators["TestEval"] = MagicMock()

        result = self.manager.unload_plugin("test_eval")
        assert result is True
        assert "TestEval" not in self.manager._evaluators

    def test_unload_plugin_dataset(self):
        """测试卸载数据集插件"""
        info = PluginInfo(
            plugin_id="test_dataset",
            name="TestDataset",
            version="1.0",
            author="a",
            description="d",
            plugin_type="dataset",
            entry_point="main",
        )
        self.manager._plugins["test_dataset"] = info
        self.manager._datasets["TestDataset"] = MagicMock()

        result = self.manager.unload_plugin("test_dataset")
        assert result is True
        assert "TestDataset" not in self.manager._datasets

    def test_unload_plugin_metric(self):
        """测试卸载指标插件"""
        info = PluginInfo(
            plugin_id="test_metric",
            name="TestMetric",
            version="1.0",
            author="a",
            description="d",
            plugin_type="metric",
            entry_point="main",
        )
        self.manager._plugins["test_metric"] = info
        self.manager._metrics["TestMetric"] = MagicMock()

        result = self.manager.unload_plugin("test_metric")
        assert result is True
        assert "TestMetric" not in self.manager._metrics


class TestPluginRegistry:
    """插件注册中心测试"""

    def setup_method(self):
        self.registry = PluginRegistry()

    def test_register_plugin(self):
        """测试注册插件"""
        info = PluginInfo(
            plugin_id="test",
            name="Test",
            version="1.0",
            author="a",
            description="d",
            plugin_type="evaluator",
            entry_point="main",
        )
        self.registry.register_plugin(info)

        assert "test" in self.registry._registry
        assert self.registry.get_plugin_status("test") == "registered"

    def test_unregister_plugin(self):
        """测试注销插件"""
        info = PluginInfo(
            plugin_id="test",
            name="Test",
            version="1.0",
            author="a",
            description="d",
            plugin_type="evaluator",
            entry_point="main",
        )
        self.registry.register_plugin(info)
        self.registry.unregister_plugin("test")

        assert "test" not in self.registry._registry

    def test_search_plugins_by_type(self):
        """测试按类型搜索"""
        info1 = PluginInfo(
            plugin_id="eval1",
            name="Eval1",
            version="1.0",
            author="a",
            description="d",
            plugin_type="evaluator",
            entry_point="main",
        )
        info2 = PluginInfo(
            plugin_id="dataset1",
            name="Dataset1",
            version="1.0",
            author="a",
            description="d",
            plugin_type="dataset",
            entry_point="main",
        )
        self.registry.register_plugin(info1)
        self.registry.register_plugin(info2)

        results = self.registry.search_plugins(plugin_type="evaluator")
        assert len(results) == 1
        assert results[0].plugin_id == "eval1"

    def test_search_plugins_by_name(self):
        """测试按名称搜索"""
        info = PluginInfo(
            plugin_id="test",
            name="MyPlugin",
            version="1.0",
            author="a",
            description="d",
            plugin_type="evaluator",
            entry_point="main",
        )
        self.registry.register_plugin(info)

        results = self.registry.search_plugins(name="My")
        assert len(results) == 1

    def test_get_plugin_status_none(self):
        """测试获取不存在插件状态"""
        assert self.registry.get_plugin_status("nonexistent") is None


class TestGetPluginManager:
    """全局插件管理器测试"""

    def test_get_plugin_manager_singleton(self):
        """测试单例模式"""
        manager1 = get_plugin_manager()
        manager2 = get_plugin_manager()

        assert manager1 is manager2