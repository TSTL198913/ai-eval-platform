"""数据库会话管理测试"""

import os
from unittest.mock import patch

import pytest

from src.infra.db.session import (
    ConnectionLeakDetector,
    ConnectionPoolConfig,
    ConnectionPoolMetrics,
    _get_env_bool,
    _get_env_int,
    detect_connection_leaks,
    get_db,
    get_db_session,
    get_engine,
    get_leak_detector,
    get_pool_config,
    get_pool_status,
    get_session_local,
    init_tables,
    invalidate_pool,
    register_checkin_hook,
    register_checkout_hook,
    reset_pool_metrics,
    set_leak_detector,
    set_pool_config,
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

    def test_get_env_int_invalid(self):
        """无效值应返回默认值"""
        os.environ["TEST_INT_VAR"] = "invalid"
        result = _get_env_int("TEST_INT_VAR", 42)
        assert result == 42
        del os.environ["TEST_INT_VAR"]

    def test_get_env_bool_default(self):
        """默认布尔值应正确返回"""
        result = _get_env_bool("NON_EXISTENT_VAR", True)
        assert result is True

    def test_get_env_bool_true_values(self):
        """各种真值应正确解析"""
        for val in ["true", "1", "yes"]:
            os.environ["TEST_BOOL_VAR"] = val
            assert _get_env_bool("TEST_BOOL_VAR", False) is True
        del os.environ["TEST_BOOL_VAR"]

    def test_get_env_bool_false_values(self):
        """各种假值应正确解析"""
        for val in ["false", "0", "no"]:
            os.environ["TEST_BOOL_VAR"] = val
            assert _get_env_bool("TEST_BOOL_VAR", True) is False
        del os.environ["TEST_BOOL_VAR"]


class TestConnectionPoolConfig:
    """连接池配置测试"""

    def test_default_config(self):
        """默认配置应正确"""
        config = ConnectionPoolConfig()
        assert config.pool_size == 20
        assert config.max_overflow == 40
        assert config.pool_timeout == 30
        assert config.pool_recycle == 300
        assert config.pool_pre_ping is True
        assert config.pool_use_lifo is True

    def test_to_dict(self):
        """配置应能转换为字典"""
        config = ConnectionPoolConfig()
        data = config.to_dict()
        assert data["pool_size"] == 20
        assert data["max_overflow"] == 40
        assert "pool_pre_ping" in data


class TestConnectionPoolMetrics:
    """连接池指标测试"""

    def test_default_metrics(self):
        """默认指标应正确"""
        metrics = ConnectionPoolMetrics()
        assert metrics.pool_size == 0
        assert metrics.checked_in == 0
        assert metrics.checked_out == 0
        assert metrics.overflow == 0

    def test_to_dict(self):
        """指标应能转换为字典"""
        metrics = ConnectionPoolMetrics()
        data = metrics.to_dict()
        assert "pool_size" in data
        assert "active_connections" in data


class TestConnectionLeakDetector:
    """连接泄漏检测器测试"""

    @pytest.fixture
    def detector(self):
        return ConnectionLeakDetector(leak_threshold_seconds=0.1)

    def test_track_checkout(self, detector):
        """跟踪连接检出应正确"""
        conn_id = detector.track_checkout("fake_conn")
        assert conn_id == 0
        active = detector.get_active_connections()
        assert len(active) == 1

    def test_track_checkin(self, detector):
        """跟踪连接归还应正确"""
        conn_id = detector.track_checkout("fake_conn")
        info = detector.track_checkin("fake_conn")
        assert info is not None
        assert info.connection_id == conn_id
        active = detector.get_active_connections()
        assert len(active) == 0

    def test_detect_leaks_no_leaks(self, detector):
        """无泄漏时应返回空列表"""
        detector.track_checkout("fake_conn")
        detector.track_checkin("fake_conn")
        leaks = detector.detect_leaks()
        assert len(leaks) == 0

    def test_detect_leaks_with_leak(self, detector):
        """有泄漏时应检测到"""
        import time

        detector.track_checkout("fake_conn")
        time.sleep(0.15)
        leaks = detector.detect_leaks()
        assert len(leaks) == 1
        assert leaks[0].duration > 0.1

    def test_get_leak_report(self, detector):
        """泄漏报告应正确"""
        report = detector.get_leak_report()
        assert "total_active_connections" in report
        assert "potential_leaks" in report

    def test_register_leak_detected_hook(self, detector):
        """注册泄漏检测钩子应正确"""
        hook_called = []

        def test_hook(leaks):
            hook_called.append(leaks)

        detector.register_leak_detected_hook(test_hook)
        detector.track_checkout("fake_conn")

        import time

        time.sleep(0.15)
        detector.detect_leaks()

        assert len(hook_called) == 1

    def test_clear(self, detector):
        """清除跟踪应正确"""
        detector.track_checkout("fake_conn")
        detector.clear()
        active = detector.get_active_connections()
        assert len(active) == 0


class TestPoolConfigManagement:
    """连接池配置管理测试"""

    def test_get_pool_config_default(self):
        """获取默认配置应正确"""
        config = get_pool_config()
        assert isinstance(config, ConnectionPoolConfig)

    def test_set_pool_config(self):
        """设置自定义配置应正确"""
        custom_config = ConnectionPoolConfig(pool_size=10, max_overflow=20)
        set_pool_config(custom_config)
        config = get_pool_config()
        assert config.pool_size == 10
        assert config.max_overflow == 20


class TestLeakDetectorManagement:
    """泄漏检测器管理测试"""

    def test_get_leak_detector(self):
        """获取泄漏检测器应正确"""
        detector = get_leak_detector()
        assert isinstance(detector, ConnectionLeakDetector)

    def test_set_leak_detector(self):
        """设置自定义泄漏检测器应正确"""
        custom_detector = ConnectionLeakDetector(leak_threshold_seconds=30)
        set_leak_detector(custom_detector)
        detector = get_leak_detector()
        assert detector.leak_threshold_seconds == 30


class TestDatabaseSession:
    """数据库会话测试"""

    def test_get_engine(self):
        """获取引擎应正确"""
        with patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"}):
            engine = get_engine()
            assert engine is not None

    def test_get_session_local(self):
        """获取SessionLocal应正确"""
        with patch.dict(os.environ, {"TESTING": "1"}):
            session_local = get_session_local()
            assert session_local is not None

    def test_get_db_session_context_manager(self):
        """上下文管理器应正确工作"""
        with patch.dict(os.environ, {"TESTING": "1"}):
            with get_db_session() as db:
                assert db is not None

    def test_get_db_generator(self):
        """生成器应正确工作"""
        with patch.dict(os.environ, {"TESTING": "1"}):
            for session in get_db():
                assert session is not None
                break


class TestPoolStatus:
    """连接池状态测试"""

    def test_get_pool_status(self):
        """获取连接池状态应正确"""
        with patch.dict(os.environ, {"TESTING": "1"}):
            status = get_pool_status()
            assert "pool_size" in status
            assert "active" in status
            assert "leak_detection" in status

    def test_detect_connection_leaks(self):
        """检测连接泄漏应正确"""
        leaks = detect_connection_leaks()
        assert isinstance(leaks, list)

    def test_reset_pool_metrics(self):
        """重置连接池指标应正确"""
        reset_pool_metrics()


class TestHooks:
    """钩子注册测试"""

    def test_register_checkout_hook(self):
        """注册检出钩子应正确"""

        def test_hook(conn):
            pass

        register_checkout_hook(test_hook)

    def test_register_checkin_hook(self):
        """注册归还钩子应正确"""

        def test_hook(conn):
            pass

        register_checkin_hook(test_hook)


class TestPoolManagement:
    """连接池管理测试"""

    def test_invalidate_pool(self):
        """使连接池失效应正确"""
        with patch.dict(os.environ, {"TESTING": "1"}):
            get_engine()
            invalidate_pool()

    def test_init_tables(self):
        """初始化表结构应正确"""
        with patch.dict(os.environ, {"TESTING": "1"}):
            invalidate_pool()
            init_tables()
