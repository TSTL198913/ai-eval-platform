"""数据库会话管理简化测试"""

import os

from src.infra.db.session import (
    ConnectionLeakDetector,
    ConnectionPoolConfig,
    _get_env_bool,
    _get_env_int,
    get_leak_detector,
    get_pool_config,
)


class TestEnvHelpers:
    """环境变量辅助函数测试"""

    def test_get_env_int_default(self):
        """默认值应正确返回"""
        result = _get_env_int("NON_EXISTENT_VAR", 42)
        assert result == 42

    def test_get_env_int_valid(self):
        """有效整数值应正确解析"""
        os.environ["TEST_INT_VAR"] = "123"
        result = _get_env_int("TEST_INT_VAR", 42)
        assert result == 123
        del os.environ["TEST_INT_VAR"]

    def test_get_env_bool_default(self):
        """默认布尔值应正确返回"""
        result = _get_env_bool("NON_EXISTENT_VAR", True)
        assert result is True


class TestConnectionPoolConfig:
    """连接池配置测试"""

    def test_default_config(self):
        """默认配置应正确"""
        config = ConnectionPoolConfig()
        assert config.pool_size == 20
        assert config.max_overflow == 40

    def test_to_dict(self):
        """配置应能转换为字典"""
        config = ConnectionPoolConfig()
        data = config.to_dict()
        assert data["pool_size"] == 20


class TestConnectionLeakDetector:
    """连接泄漏检测器测试"""

    def test_track_checkout(self):
        """跟踪连接检出应正确"""
        detector = ConnectionLeakDetector(leak_threshold_seconds=0.1)
        conn_id = detector.track_checkout("fake_conn")
        assert conn_id == 0

    def test_track_checkin(self):
        """跟踪连接归还应正确"""
        detector = ConnectionLeakDetector(leak_threshold_seconds=0.1)
        detector.track_checkout("fake_conn")
        info = detector.track_checkin("fake_conn")
        assert info is not None


class TestPoolConfigManagement:
    """连接池配置管理测试"""

    def test_get_pool_config(self):
        """获取配置应正确"""
        config = get_pool_config()
        assert isinstance(config, ConnectionPoolConfig)


class TestLeakDetectorManagement:
    """泄漏检测器管理测试"""

    def test_get_leak_detector(self):
        """获取泄漏检测器应正确"""
        detector = get_leak_detector()
        assert isinstance(detector, ConnectionLeakDetector)
