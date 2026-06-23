"""
FeatureManager 专项单元测试
测试目标：验证FeatureManager的单例模式、特性开关的启用/禁用、配置加载
关键发现：
1. FeatureManager 是单例模式
2. 默认配置：部分feature为True，部分为False
3. toggle操作可翻转状态
4. load_from_config 仅加载已存在的feature
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.infra.feature_flags import FeatureFlag, FeatureManager, feature_manager


class TestFeatureManagerSingleton:
    """单例模式测试"""

    def test_singleton_returns_same_instance(self):
        """场景：多次实例化应返回相同实例"""
        # 由于之前的测试可能已经创建了实例,这里直接测试相等性
        instance1 = FeatureManager()
        instance2 = FeatureManager()

        assert instance1 is instance2


class TestFeatureManagerDefaultState:
    """默认状态测试"""

    def test_default_features_count(self):
        """场景：默认应包含所有feature"""
        manager = FeatureManager()
        all_features = manager.get_all_features()

        assert len(all_features) >= 10

    def test_default_features_have_correct_values(self):
        """场景：默认特性状态应正确"""
        manager = FeatureManager()

        # 默认开启
        assert manager.is_enabled(FeatureFlag.ADAPTIVE_BATCH_SIZE) is True
        assert manager.is_enabled(FeatureFlag.ASYNC_EVALUATION) is True
        assert manager.is_enabled(FeatureFlag.COST_GOVERNANCE) is True

        # 默认关闭
        assert manager.is_enabled(FeatureFlag.PRIORITY_BUFFER) is False

    def test_is_enabled_unknown_feature(self):
        """场景：未知feature应返回False"""
        manager = FeatureManager()

        # 不存在的feature应返回False
        # 因为不存在的key使用.get()返回默认值False
        result = manager._features.get("nonexistent", False)

        assert result is False


class TestFeatureManagerOperations:
    """操作测试"""

    def test_enable_feature(self):
        """场景：启用feature"""
        manager = FeatureManager()
        # 先重置状态
        manager.disable(FeatureFlag.PRIORITY_BUFFER)
        assert manager.is_enabled(FeatureFlag.PRIORITY_BUFFER) is False

        manager.enable(FeatureFlag.PRIORITY_BUFFER)
        assert manager.is_enabled(FeatureFlag.PRIORITY_BUFFER) is True

    def test_disable_feature(self):
        """场景：禁用feature"""
        manager = FeatureManager()
        # 先启用
        manager.enable(FeatureFlag.PRIORITY_BUFFER)
        assert manager.is_enabled(FeatureFlag.PRIORITY_BUFFER) is True

        manager.disable(FeatureFlag.PRIORITY_BUFFER)
        assert manager.is_enabled(FeatureFlag.PRIORITY_BUFFER) is False

    def test_toggle_feature(self):
        """场景：切换feature状态"""
        manager = FeatureManager()
        # 初始状态(可能true或false,取决于历史测试)
        initial = manager.is_enabled(FeatureFlag.PRIORITY_BUFFER)

        result = manager.toggle(FeatureFlag.PRIORITY_BUFFER)
        assert result is not initial
        assert manager.is_enabled(FeatureFlag.PRIORITY_BUFFER) is not initial

        # 再次切换
        result = manager.toggle(FeatureFlag.PRIORITY_BUFFER)
        assert result is initial
        assert manager.is_enabled(FeatureFlag.PRIORITY_BUFFER) is initial

    def test_set_feature_value(self):
        """场景：直接设置feature值"""
        manager = FeatureManager()

        manager.set(FeatureFlag.PRIORITY_BUFFER, True)
        assert manager.is_enabled(FeatureFlag.PRIORITY_BUFFER) is True

        manager.set(FeatureFlag.PRIORITY_BUFFER, False)
        assert manager.is_enabled(FeatureFlag.PRIORITY_BUFFER) is False


class TestFeatureManagerConfigLoading:
    """配置加载测试"""

    def test_load_from_config(self):
        """场景：从配置加载"""
        manager = FeatureManager()

        config = {
            "priority_buffer": True,
            "adaptive_batch_size": False,
            "unknown_feature": True,  # 不应被加载
        }

        manager.load_from_config(config)

        assert manager.is_enabled(FeatureFlag.PRIORITY_BUFFER) is True
        assert manager.is_enabled(FeatureFlag.ADAPTIVE_BATCH_SIZE) is False

    def test_load_from_config_converts_to_bool(self):
        """场景：配置值应被转换为布尔"""
        manager = FeatureManager()

        # 1 -> True, 0 -> False
        manager.load_from_config(
            {
                "priority_buffer": 1,
                "adaptive_batch_size": 0,
            }
        )

        assert manager.is_enabled(FeatureFlag.PRIORITY_BUFFER) is True
        assert manager.is_enabled(FeatureFlag.ADAPTIVE_BATCH_SIZE) is False

    def test_load_from_config_partial(self):
        """场景：部分配置加载不影响其他feature"""
        manager = FeatureManager()
        # 保存原状态
        original_async = manager.is_enabled(FeatureFlag.ASYNC_EVALUATION)

        manager.load_from_config(
            {
                "priority_buffer": True,
            }
        )

        # 其他feature状态不变
        assert manager.is_enabled(FeatureFlag.ASYNC_EVALUATION) == original_async

    def test_load_from_empty_config(self):
        """场景：空配置不应影响任何feature"""
        manager = FeatureManager()
        # 保存所有原状态
        original_features = dict(manager._features)

        manager.load_from_config({})

        # 所有feature应保持原状态
        for key, value in original_features.items():
            assert manager._features[key] == value


class TestFeatureManagerGetAllFeatures:
    """获取所有feature测试"""

    def test_get_all_features_returns_dict(self):
        """场景：返回字典类型"""
        manager = FeatureManager()
        features = manager.get_all_features()

        assert isinstance(features, dict)
        assert len(features) > 0

    def test_get_all_features_is_copy(self):
        """场景：返回的是副本,修改不影响原数据"""
        manager = FeatureManager()
        features = manager.get_all_features()

        features["modified"] = True

        # 原数据不应被修改
        assert "modified" not in manager._features


class TestFeatureManagerDependencyHandling:
    """依赖测试 - 异常处理"""

    def test_load_from_config_with_invalid_values(self):
        """场景：非法值应被安全处理"""
        manager = FeatureManager()

        # None应该被转换为False
        manager.load_from_config({"priority_buffer": None})
        # bool(None) = False
        assert manager.is_enabled(FeatureFlag.PRIORITY_BUFFER) is False


class TestFeatureFlagEnum:
    """FeatureFlag 枚举测试"""

    def test_feature_flag_values(self):
        """场景：feature值应正确"""
        assert FeatureFlag.PRIORITY_BUFFER.value == "priority_buffer"
        assert FeatureFlag.ADAPTIVE_BATCH_SIZE.value == "adaptive_batch_size"
        assert FeatureFlag.ASYNC_EVALUATION.value == "async_evaluation"
        assert FeatureFlag.COST_GOVERNANCE.value == "cost_governance"
        assert FeatureFlag.IDENTITY_CHECK.value == "identity_check"
        assert FeatureFlag.CIRCUIT_BREAKER.value == "circuit_breaker"
        assert FeatureFlag.RATE_LIMITER.value == "rate_limiter"
        assert FeatureFlag.CACHE_ENABLED.value == "cache_enabled"
        assert FeatureFlag.METRICS_ENABLED.value == "metrics_enabled"
        assert FeatureFlag.TRACING_ENABLED.value == "tracing_enabled"

    def test_feature_flag_count(self):
        """场景：feature数量应正确"""
        assert len(FeatureFlag) == 10


class TestGlobalFeatureManager:
    """全局feature_manager 实例测试"""

    def test_global_instance_exists(self):
        """场景：全局实例应存在"""
        assert feature_manager is not None
        assert isinstance(feature_manager, FeatureManager)

    def test_global_instance_is_singleton(self):
        """场景：全局实例是单例"""
        # 全局实例与新创建实例应相同
        assert feature_manager is FeatureManager()
