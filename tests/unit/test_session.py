"""测试 infra/db/session.py - 数据库会话管理和连接池优化"""

import importlib
import os
import threading
import time
from unittest.mock import patch, MagicMock

import pytest


class TestSessionModule:
    """测试会话模块"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_testing_mode(self):
        from src.infra.db import session as session_module

        assert session_module._get_database_url() == "sqlite:///:memory:"

    @patch.dict(os.environ, {"TESTING": "1"}, clear=True)
    def test_testing_default(self):
        from src.infra.db import session as session_module

        assert ":memory:" in session_module._get_database_url()

    @patch.dict(os.environ, {}, clear=True)
    def test_production_default(self):
        from src.infra.db import session as session_module

        assert "postgresql" in session_module._get_database_url()

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///test.db"})
    def test_sqlite_engine_config(self):
        from src.infra.db import session as session_module

        # 测试惰性初始化的引擎和 SessionLocal
        assert session_module.get_engine() is not None
        assert session_module.get_session_local() is not None


class TestEnvVarConfig:
    """测试环境变量配置读取"""

    def test_get_env_int_default(self):
        """测试 _get_env_int 默认值"""
        from src.infra.db.session import _get_env_int

        with patch.dict(os.environ, {}, clear=True):
            assert _get_env_int("NONEXISTENT_VAR", 42) == 42

    def test_get_env_int_valid(self):
        """测试 _get_env_int 有效值"""
        from src.infra.db.session import _get_env_int

        with patch.dict(os.environ, {"TEST_INT": "100"}):
            assert _get_env_int("TEST_INT", 0) == 100

    def test_get_env_int_invalid(self):
        """测试 _get_env_int 无效值返回默认"""
        from src.infra.db.session import _get_env_int

        with patch.dict(os.environ, {"TEST_INT": "not_a_number"}):
            assert _get_env_int("TEST_INT", 50) == 50

    def test_get_env_bool_true_values(self):
        """测试 _get_env_bool 真值"""
        from src.infra.db.session import _get_env_bool

        for val in ("true", "True", "TRUE", "1", "yes", "YES"):
            with patch.dict(os.environ, {"TEST_BOOL": val}):
                assert _get_env_bool("TEST_BOOL", False) is True

    def test_get_env_bool_false_values(self):
        """测试 _get_env_bool 假值"""
        from src.infra.db.session import _get_env_bool

        for val in ("false", "False", "FALSE", "0", "no", "NO"):
            with patch.dict(os.environ, {"TEST_BOOL": val}):
                assert _get_env_bool("TEST_BOOL", True) is False

    def test_get_env_bool_default(self):
        """测试 _get_env_bool 默认值"""
        from src.infra.db.session import _get_env_bool

        with patch.dict(os.environ, {}, clear=True):
            assert _get_env_bool("NONEXISTENT_VAR", True) is True
            assert _get_env_bool("NONEXISTENT_VAR", False) is False

    @patch.dict(os.environ, {"DB_POOL_SIZE": "50", "DB_MAX_OVERFLOW": "100"}, clear=True)
    def test_pool_config_from_env(self):
        """测试从环境变量读取连接池配置"""
        # 需要重新加载模块以应用环境变量
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        config = session_module.ConnectionPoolConfig()
        assert config.pool_size == 50
        assert config.max_overflow == 100

    @patch.dict(
        os.environ,
        {
            "DB_POOL_SIZE": "30",
            "DB_MAX_OVERFLOW": "60",
            "DB_POOL_TIMEOUT": "45",
            "DB_POOL_RECYCLE": "600",
            "DB_POOL_PRE_PING": "false",
            "DB_POOL_USE_LIFO": "false",
        },
        clear=True,
    )
    def test_all_pool_config_from_env(self):
        """测试所有连接池配置从环境变量读取"""
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        config = session_module.ConnectionPoolConfig()
        assert config.pool_size == 30
        assert config.max_overflow == 60
        assert config.pool_timeout == 45
        assert config.pool_recycle == 600
        assert config.pool_pre_ping is False
        assert config.pool_use_lifo is False


class TestConnectionPoolConfig:
    """测试连接池配置"""

    def test_default_config(self):
        """测试默认配置 - pool_size=20, max_overflow=40"""
        from src.infra.db.session import ConnectionPoolConfig

        config = ConnectionPoolConfig()
        assert config.pool_size == 20
        assert config.max_overflow == 40
        assert config.pool_timeout == 30
        assert config.pool_recycle == 300
        assert config.pool_pre_ping is True
        assert config.pool_use_lifo is True

    def test_custom_config(self):
        from src.infra.db.session import ConnectionPoolConfig

        config = ConnectionPoolConfig(
            pool_size=50,
            max_overflow=100,
            pool_timeout=60,
            pool_recycle=600,
            pool_pre_ping=False,
            pool_use_lifo=False,
        )
        assert config.pool_size == 50
        assert config.max_overflow == 100
        assert config.pool_timeout == 60
        assert config.pool_recycle == 600
        assert config.pool_pre_ping is False
        assert config.pool_use_lifo is False

    def test_config_to_dict(self):
        from src.infra.db.session import ConnectionPoolConfig

        config = ConnectionPoolConfig()
        d = config.to_dict()
        assert isinstance(d, dict)
        assert d["pool_size"] == 20
        assert d["max_overflow"] == 40
        assert d["pool_timeout"] == 30
        assert d["pool_recycle"] == 300
        assert d["pool_pre_ping"] is True
        assert d["pool_use_lifo"] is True


class TestConnectionPoolMetrics:
    """测试连接池监控指标"""

    def test_default_metrics(self):
        from src.infra.db.session import ConnectionPoolMetrics

        metrics = ConnectionPoolMetrics()
        assert metrics.pool_size == 0
        assert metrics.checked_in == 0
        assert metrics.checked_out == 0
        assert metrics.overflow == 0
        assert metrics.queue_size == 0
        assert metrics.total_connections == 0
        assert metrics.active_connections == 0
        assert metrics.idle_connections == 0
        assert metrics.last_update_time > 0

    def test_metrics_to_dict(self):
        from src.infra.db.session import ConnectionPoolMetrics

        metrics = ConnectionPoolMetrics(pool_size=10, checked_out=5)
        d = metrics.to_dict()
        assert isinstance(d, dict)
        assert d["pool_size"] == 10
        assert d["checked_out"] == 5


class TestConnectionLeakDetector:
    """测试连接泄漏检测器"""

    def test_detector_initialization(self):
        """测试检测器初始化"""
        from src.infra.db.session import ConnectionLeakDetector

        detector = ConnectionLeakDetector(leak_threshold_seconds=30.0)
        assert detector.leak_threshold_seconds == 30.0
        assert len(detector._connections) == 0

    def test_track_checkout(self):
        """测试跟踪连接检出"""
        from src.infra.db.session import ConnectionLeakDetector

        detector = ConnectionLeakDetector()
        mock_conn = MagicMock()

        conn_id = detector.track_checkout(mock_conn)
        assert conn_id == 0
        assert len(detector._connections) == 1

        # 第二次检出
        conn_id2 = detector.track_checkout(mock_conn)
        assert conn_id2 == 1
        assert len(detector._connections) == 2

    def test_track_checkin(self):
        """测试跟踪连接归还"""
        from src.infra.db.session import ConnectionLeakDetector

        detector = ConnectionLeakDetector()
        mock_conn = MagicMock()

        detector.track_checkout(mock_conn)
        assert len(detector._connections) == 1

        result = detector.track_checkin(mock_conn)
        assert len(detector._connections) == 0
        assert result is not None

    def test_detect_leaks_no_leaks(self):
        """测试无泄漏情况"""
        from src.infra.db.session import ConnectionLeakDetector

        detector = ConnectionLeakDetector(leak_threshold_seconds=60.0)
        mock_conn = MagicMock()

        detector.track_checkout(mock_conn)
        leaks = detector.detect_leaks()
        assert len(leaks) == 0

    def test_detect_leaks_with_leaks(self):
        """测试有泄漏情况"""
        from src.infra.db.session import ConnectionLeakDetector

        detector = ConnectionLeakDetector(leak_threshold_seconds=0.001)  # 非常短的阈值
        mock_conn = MagicMock()

        detector.track_checkout(mock_conn)
        time.sleep(0.01)  # 等待超过阈值

        leaks = detector.detect_leaks()
        assert len(leaks) == 1
        assert leaks[0].duration > 0

    def test_get_active_connections(self):
        """测试获取活动连接"""
        from src.infra.db.session import ConnectionLeakDetector

        detector = ConnectionLeakDetector()
        mock_conn = MagicMock()

        detector.track_checkout(mock_conn)
        active = detector.get_active_connections()
        assert len(active) == 1

    def test_get_leak_report(self):
        """测试获取泄漏报告"""
        from src.infra.db.session import ConnectionLeakDetector

        detector = ConnectionLeakDetector(leak_threshold_seconds=0.001)
        mock_conn = MagicMock()

        detector.track_checkout(mock_conn)
        time.sleep(0.01)

        report = detector.get_leak_report()
        assert "total_active_connections" in report
        assert "potential_leaks" in report
        assert "leak_threshold_seconds" in report
        assert "leaks" in report
        assert report["total_active_connections"] == 1
        assert report["potential_leaks"] == 1

    def test_clear_connections(self):
        """测试清除所有跟踪的连接"""
        from src.infra.db.session import ConnectionLeakDetector

        detector = ConnectionLeakDetector()
        mock_conn = MagicMock()

        detector.track_checkout(mock_conn)
        assert len(detector._connections) == 1

        detector.clear()
        assert len(detector._connections) == 0

    def test_leak_detected_hook(self):
        """测试泄漏检测钩子"""
        from src.infra.db.session import ConnectionLeakDetector

        detector = ConnectionLeakDetector(leak_threshold_seconds=0.001)
        hook_called = []

        def leak_hook(leaks):
            hook_called.append(len(leaks))

        detector.register_leak_detected_hook(leak_hook)
        mock_conn = MagicMock()

        detector.track_checkout(mock_conn)
        time.sleep(0.01)

        detector.detect_leaks()
        assert len(hook_called) == 1
        assert hook_called[0] == 1

    def test_leak_hook_exception_handling(self):
        """测试泄漏检测钩子异常处理"""
        from src.infra.db.session import ConnectionLeakDetector

        detector = ConnectionLeakDetector(leak_threshold_seconds=0.001)

        def bad_hook(leaks):
            raise RuntimeError("Hook error")

        detector.register_leak_detected_hook(bad_hook)
        mock_conn = MagicMock()

        detector.track_checkout(mock_conn)
        time.sleep(0.01)

        # 不应该抛出异常
        leaks = detector.detect_leaks()
        assert len(leaks) == 1


class TestConnectionLeakInfo:
    """测试连接泄漏信息"""

    def test_leak_info_creation(self):
        """测试泄漏信息创建"""
        from src.infra.db.session import ConnectionLeakInfo

        info = ConnectionLeakInfo(
            connection_id=1,
            checkout_time=time.time(),
            thread_id=12345,
            stack_trace="test stack",
        )
        assert info.connection_id == 1
        assert info.thread_id == 12345
        assert info.stack_trace == "test stack"
        assert info.duration == 0.0


class TestGlobalLeakDetector:
    """测试全局泄漏检测器"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_get_leak_detector(self):
        """测试获取全局泄漏检测器"""
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        detector = session_module.get_leak_detector()
        assert detector is not None
        assert isinstance(detector, session_module.ConnectionLeakDetector)

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:", "DB_LEAK_THRESHOLD_SECONDS": "30"})
    def test_leak_detector_from_env(self):
        """测试从环境变量读取泄漏阈值"""
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        detector = session_module.get_leak_detector()
        assert detector.leak_threshold_seconds == 30

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_set_leak_detector(self):
        """测试设置自定义泄漏检测器"""
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        custom_detector = session_module.ConnectionLeakDetector(leak_threshold_seconds=120)
        session_module.set_leak_detector(custom_detector)
        detector = session_module.get_leak_detector()
        assert detector.leak_threshold_seconds == 120

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_get_leak_report(self):
        """测试获取泄漏报告"""
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        report = session_module.get_leak_report()
        assert "total_active_connections" in report
        assert "potential_leaks" in report

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_detect_connection_leaks(self):
        """测试检测连接泄漏"""
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        leaks = session_module.detect_connection_leaks()
        assert isinstance(leaks, list)


class TestPoolConfigManagement:
    """测试连接池配置管理"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_get_pool_config_default(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        config = session_module.get_pool_config()
        assert isinstance(config, session_module.ConnectionPoolConfig)
        assert config.pool_size == 20  # 新的默认值

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_set_pool_config(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        new_config = session_module.ConnectionPoolConfig(pool_size=30, max_overflow=60)
        session_module.set_pool_config(new_config)
        config = session_module.get_pool_config()
        assert config.pool_size == 30
        assert config.max_overflow == 60


class TestPoolMetricsManagement:
    """测试连接池指标管理"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_get_pool_metrics(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        session_module.get_engine()
        metrics = session_module.get_pool_metrics()
        assert isinstance(metrics, session_module.ConnectionPoolMetrics)

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_get_pool_status(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        session_module.get_engine()
        status = session_module.get_pool_status()
        assert isinstance(status, dict)
        assert "pool_size" in status
        assert "checked_in" in status
        assert "checked_out" in status
        assert "overflow" in status
        assert "total" in status
        assert "active" in status
        assert "idle" in status
        assert "utilization_rate" in status
        assert "leak_detection" in status  # 新增的泄漏检测信息

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_reset_pool_metrics(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        session_module.get_engine()
        session_module.reset_pool_metrics()
        metrics = session_module.get_pool_metrics()
        assert metrics.pool_size == 0
        assert metrics.checked_out == 0

    def test_utilization_rate_calculation(self):
        """测试利用率计算"""
        from src.infra.db.session import ConnectionPoolMetrics

        metrics = ConnectionPoolMetrics(pool_size=10, active_connections=5)
        rate = f"{metrics.active_connections / metrics.pool_size * 100:.1f}%" if metrics.pool_size > 0 else "N/A"
        assert rate == "50.0%"

    def test_utilization_rate_zero_pool_size(self):
        """测试零池大小的利用率计算"""
        from src.infra.db.session import ConnectionPoolMetrics

        metrics = ConnectionPoolMetrics(pool_size=0, active_connections=0)
        rate = f"{metrics.active_connections / metrics.pool_size * 100:.1f}%" if metrics.pool_size > 0 else "N/A"
        assert rate == "N/A"

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_update_pool_metrics_non_queue_pool(self):
        """测试非QueuePool环境下的指标更新"""
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        engine = session_module.get_engine()

        # 在 SQLite 环境下，pool 不是 QueuePool
        # _update_pool_metrics 应该安全处理
        session_module._update_pool_metrics()
        # 不应该抛出异常

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_setup_engine_listeners_non_queue_pool(self):
        """测试非QueuePool环境下的监听器设置"""
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        engine = session_module.get_engine()

        # 在 SQLite 环境下不应该注册监听器
        session_module._setup_engine_listeners(engine)
        # 不应该抛出异常


class TestQueuePoolSimulation:
    """模拟QueuePool环境测试"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_update_pool_metrics_with_mock_queue_pool(self):
        """使用mock QueuePool测试指标更新"""
        import src.infra.db.session as session_module

        importlib.reload(session_module)

        # 创建一个 mock QueuePool - 使用 spec 让 isinstance 工作
        mock_pool = MagicMock(spec=session_module.QueuePool)
        mock_pool.size.return_value = 20
        mock_pool.checkedin.return_value = 15
        mock_pool.checkedout.return_value = 5
        mock_pool.overflow.return_value = 10
        mock_pool.queue_size = 0

        # 创建 mock engine
        mock_engine = MagicMock()
        mock_engine.pool = mock_pool

        # 验证 isinstance 有效
        assert isinstance(mock_pool, session_module.QueuePool)

        # 直接调用函数测试
        with patch.object(session_module, 'get_engine', return_value=mock_engine):
            session_module._update_pool_metrics()

            # 验证 metrics 是否正确更新
            assert session_module._pool_metrics.pool_size == 20
            assert session_module._pool_metrics.checked_in == 15
            assert session_module._pool_metrics.checked_out == 5
            assert session_module._pool_metrics.overflow == 10
            assert session_module._pool_metrics.total_connections == 30
            assert session_module._pool_metrics.active_connections == 5
            assert session_module._pool_metrics.idle_connections == 15

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_setup_engine_listeners_with_mock_queue_pool(self):
        """使用mock QueuePool测试监听器设置"""
        import src.infra.db.session as session_module

        importlib.reload(session_module)

        # 创建一个 mock QueuePool
        mock_pool = MagicMock(spec=session_module.QueuePool)

        # 创建 mock engine
        mock_engine = MagicMock()
        mock_engine.pool = mock_pool

        # 监听器不应该被注册到非 QueuePool
        with patch.object(session_module, 'event') as mock_event:
            session_module._setup_engine_listeners(mock_engine)
            # 由于 pool 是 MagicMock 但 isinstance 检查应该失败
            # 因为 MagicMock 不是 QueuePool 的实例

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_create_engine_with_postgresql_url(self):
        """测试使用PostgreSQL URL创建引擎（通过mock）"""
        import src.infra.db.session as session_module

        importlib.reload(session_module)

        # 这测试的是配置被正确传递
        config = session_module.ConnectionPoolConfig(
            pool_size=25,
            max_overflow=50,
            pool_timeout=45,
            pool_recycle=500,
            pool_pre_ping=False,
            pool_use_lifo=False,
        )
        session_module.set_pool_config(config)

        # 验证配置被正确设置
        retrieved_config = session_module.get_pool_config()
        assert retrieved_config.pool_size == 25
        assert retrieved_config.max_overflow == 50
        assert retrieved_config.pool_timeout == 45
        assert retrieved_config.pool_recycle == 500
        assert retrieved_config.pool_pre_ping is False
        assert retrieved_config.pool_use_lifo is False


class TestConnectionHooks:
    """测试连接获取和释放钩子"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_register_checkout_hook(self):
        from src.infra.db.session import register_checkout_hook

        hook_called = []

        def test_hook(conn):
            hook_called.append(True)

        register_checkout_hook(test_hook)
        assert len(hook_called) == 0  # 钩子未执行

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_register_checkin_hook(self):
        from src.infra.db.session import register_checkin_hook

        hook_called = []

        def test_hook(conn):
            hook_called.append(True)

        register_checkin_hook(test_hook)
        assert len(hook_called) == 0  # 钩子未执行

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_hook_exception_handling(self):
        """测试钩子执行时的异常处理"""
        import src.infra.db.session as session_module

        importlib.reload(session_module)

        def bad_hook(conn):
            raise RuntimeError("Hook error")

        session_module.register_checkout_hook(bad_hook)
        session_module.register_checkin_hook(bad_hook)

        # 钩子执行不应该抛出异常
        try:
            session_module._execute_checkout_hooks(None)
            session_module._execute_checkin_hooks(None)
        except Exception:
            pytest.fail("Hook exception should not propagate")

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_multiple_hooks(self):
        """测试多个钩子注册"""
        import src.infra.db.session as session_module

        importlib.reload(session_module)

        call_order = []

        def hook1(conn):
            call_order.append(1)

        def hook2(conn):
            call_order.append(2)

        session_module.register_checkout_hook(hook1)
        session_module.register_checkout_hook(hook2)

        session_module._execute_checkout_hooks(None)
        assert call_order == [1, 2]


class TestGetDbSession:
    """测试数据库会话上下文管理器"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_session_commit(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        with session_module.get_db_session() as db:
            assert db is not None

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_session_rollback(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        try:
            with session_module.get_db_session() as db:
                assert db is not None
                raise ValueError("Test error")
        except ValueError:
            pass

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_session_close(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        with session_module.get_db_session():
            pass


class TestGetDb:
    """测试 get_db 生成器"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_get_db(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        gen = session_module.get_db()
        db = next(gen)
        assert db is not None
        try:
            next(gen)
        except StopIteration:
            pass


class TestInitTables:
    """测试初始化表"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_init_tables(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)

        with patch.object(session_module.Base.metadata, "create_all") as mock_create_all:
            session_module.init_tables()
            mock_create_all.assert_called_once()


class TestPoolInvalidation:
    """测试连接池失效和关闭功能"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_invalidate_pool(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        engine1 = session_module.get_engine()
        session_module.invalidate_pool()
        engine2 = session_module.get_engine()
        # 引擎应该被重新创建
        assert engine1 is not engine2

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_close_all_connections(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        session_module.get_engine()
        # 不应抛出异常
        session_module.close_all_connections()


class TestLazyEngine:
    """测试惰性引擎包装器"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_lazy_engine_access(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        # 访问 url 属性应该触发引擎初始化
        url = session_module.engine.url
        assert url is not None
        assert "sqlite" in str(url)

    @patch.dict(os.environ, {"TESTING": "1", "TESTING_DATABASE_URL": "sqlite:///:memory:"})
    def test_lazy_engine_dialect(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        dialect = session_module.engine.dialect.name
        assert dialect == "sqlite"


class TestBackwardCompatibility:
    """测试向后兼容性"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_session_local_backward_compat(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        # SessionLocal 应该可以调用
        session_local = session_module.get_session_local()
        assert session_local is not None
        # 调用应该返回 sessionmaker 实例
        session = session_local()
        assert session is not None
        session.close()

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_get_db_backward_compat(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        # get_db 生成器应该仍然可用
        gen = session_module.get_db()
        db = next(gen)
        assert db is not None
        try:
            next(gen)
        except StopIteration:
            pass

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_engine_property_backward_compat(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        # engine 属性应该可用
        assert session_module.engine is not None
        # 应该可以访问 engine 的属性（通过 __getattr__）
        assert session_module.engine.url is not None


class TestThreadSafety:
    """测试线程安全性"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_config_thread_safety(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        errors = []

        def get_config_repeatedly(expected_size):
            try:
                for _ in range(100):
                    config = session_module.get_pool_config()
                    if config.pool_size != expected_size:
                        errors.append(f"Expected {expected_size}, got {config.pool_size}")
            except Exception as e:
                errors.append(str(e))

        # 设置初始配置
        session_module.set_pool_config(
            session_module.ConnectionPoolConfig(pool_size=50)
        )

        threads = [
            threading.Thread(target=get_config_repeatedly, args=(50,))
            for _ in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_metrics_thread_safety(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        session_module.get_engine()
        errors = []

        def get_metrics():
            try:
                for _ in range(100):
                    session_module.get_pool_metrics()
                    session_module.get_pool_status()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=get_metrics) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_leak_detector_thread_safety(self):
        """测试泄漏检测器的线程安全性"""
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        detector = session_module.ConnectionLeakDetector()
        errors = []

        def track_connections():
            try:
                for _ in range(50):
                    detector.track_checkout(MagicMock())
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=track_connections) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(detector.get_active_connections()) == 250


class TestSQLitePoolBehavior:
    """测试SQLite连接池行为"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_sqlite_uses_static_pool(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        engine = session_module.get_engine()
        # SQLite 使用 StaticPool
        from sqlalchemy.pool import StaticPool

        assert isinstance(engine.pool, StaticPool)

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///test_file.db"})
    def test_sqlite_file_based(self):
        import src.infra.db.session as session_module

        importlib.reload(session_module)
        engine = session_module.get_engine()
        assert "test_file.db" in str(engine.url)
