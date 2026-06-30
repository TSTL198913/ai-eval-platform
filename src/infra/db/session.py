"""数据库会话管理模块 - 支持连接池优化和监控"""

import logging
import os
import threading
import time
import traceback
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from src.distributed.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerError,
    global_registry,
)
from src.exceptions import InfrastructureError

logger = logging.getLogger(__name__)


def _get_env_int(key: str, default: int) -> int:
    """从环境变量读取整数值"""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _get_env_bool(key: str, default: bool) -> bool:
    """从环境变量读取布尔值"""
    val = os.getenv(key, "").lower()
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    return default


@dataclass
class ConnectionPoolConfig:
    """连接池配置 - 支持从环境变量动态读取"""

    pool_size: int = field(default_factory=lambda: _get_env_int("DB_POOL_SIZE", 20))
    max_overflow: int = field(default_factory=lambda: _get_env_int("DB_MAX_OVERFLOW", 40))
    pool_timeout: int = field(default_factory=lambda: _get_env_int("DB_POOL_TIMEOUT", 30))
    pool_recycle: int = field(default_factory=lambda: _get_env_int("DB_POOL_RECYCLE", 300))
    pool_pre_ping: bool = field(default_factory=lambda: _get_env_bool("DB_POOL_PRE_PING", True))
    pool_use_lifo: bool = field(default_factory=lambda: _get_env_bool("DB_POOL_USE_LIFO", True))

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": self.pool_pre_ping,
            "pool_use_lifo": self.pool_use_lifo,
        }


@dataclass
class ConnectionPoolMetrics:
    """连接池监控指标"""

    pool_size: int = 0
    checked_in: int = 0
    checked_out: int = 0
    overflow: int = 0
    queue_size: int = 0
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    last_update_time: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool_size": self.pool_size,
            "checked_in": self.checked_in,
            "checked_out": self.checked_out,
            "overflow": self.overflow,
            "queue_size": self.queue_size,
            "total_connections": self.total_connections,
            "active_connections": self.active_connections,
            "idle_connections": self.idle_connections,
            "last_update_time": self.last_update_time,
        }


@dataclass
class ConnectionLeakInfo:
    """连接泄漏信息"""

    connection_id: int
    checkout_time: float
    thread_id: int
    stack_trace: str
    duration: float = 0.0


class ConnectionLeakDetector:
    """连接泄漏检测器"""

    def __init__(self, leak_threshold_seconds: float = 60.0):
        """
        初始化连接泄漏检测器

        Args:
            leak_threshold_seconds: 连接泄漏阈值（秒），超过此时间未归还视为潜在泄漏
        """
        self.leak_threshold_seconds = leak_threshold_seconds
        self._connections: dict[int, ConnectionLeakInfo] = {}
        self._lock = threading.Lock()
        self._next_connection_id = 0
        self._leak_detected_hooks: list = []

    def register_leak_detected_hook(self, hook: callable) -> None:
        """注册泄漏检测钩子"""
        self._leak_detected_hooks.append(hook)

    def track_checkout(self, dbapi_conn: Any) -> int:
        """
        跟踪连接检出

        Returns:
            连接ID
        """
        with self._lock:
            conn_id = self._next_connection_id
            self._next_connection_id += 1

            # 性能优化：仅在检测到潜在泄漏时才采集stack trace，
            # 避免每次checkout都执行昂贵的 traceback.extract_stack
            checkout_time = time.time()
            stack_trace = ""
            if checkout_time - getattr(self, "_last_leak_check_time", 0) > 30:
                # 周期性（每30s）采样一次用于调试
                self._last_leak_check_time = checkout_time
                stack = traceback.extract_stack()
                relevant_frames = [frame for frame in stack if "session.py" not in frame.filename]
                stack_trace = "".join(traceback.format_list(relevant_frames[-5:]))

            self._connections[conn_id] = ConnectionLeakInfo(
                connection_id=conn_id,
                checkout_time=checkout_time,
                thread_id=threading.get_ident(),
                stack_trace=stack_trace,
            )
            return conn_id

    def track_checkin(self, dbapi_conn: Any) -> ConnectionLeakInfo | None:
        """
        跟踪连接归还

        Returns:
            如果连接存在则返回连接信息，否则返回 None
        """
        with self._lock:
            # 找到对应的连接（通过线程ID匹配）
            thread_id = threading.get_ident()
            conn_id_to_remove = None
            conn_info = None

            for conn_id, info in self._connections.items():
                if info.thread_id == thread_id:
                    conn_id_to_remove = conn_id
                    conn_info = info
                    break

            if conn_id_to_remove is not None:
                del self._connections[conn_id_to_remove]

            return conn_info

    def detect_leaks(self) -> list[ConnectionLeakInfo]:
        """
        检测潜在的连接泄漏

        Returns:
            泄漏的连接信息列表
        """
        current_time = time.time()
        leaks = []

        with self._lock:
            for conn_info in self._connections.values():
                duration = current_time - conn_info.checkout_time
                if duration > self.leak_threshold_seconds:
                    conn_info.duration = duration
                    leaks.append(conn_info)

        # 触发泄漏检测钩子
        if leaks:
            for hook in self._leak_detected_hooks:
                try:
                    hook(leaks)
                except Exception as e:
                    logger.warning(f"Leak detection hook failed: {e}")

        return leaks

    def get_active_connections(self) -> dict[int, ConnectionLeakInfo]:
        """获取所有活动连接"""
        with self._lock:
            return dict(self._connections)

    def get_leak_report(self) -> dict[str, Any]:
        """
        获取连接泄漏报告

        Returns:
            包含泄漏统计和详情的字典
        """
        leaks = self.detect_leaks()
        active = self.get_active_connections()

        return {
            "total_active_connections": len(active),
            "potential_leaks": len(leaks),
            "leak_threshold_seconds": self.leak_threshold_seconds,
            "leaks": [
                {
                    "connection_id": leak.connection_id,
                    "duration_seconds": round(leak.duration, 2),
                    "thread_id": leak.thread_id,
                    "stack_trace": leak.stack_trace,
                }
                for leak in leaks
            ],
        }

    def clear(self) -> None:
        """清除所有跟踪的连接"""
        with self._lock:
            self._connections.clear()


class Base(DeclarativeBase):
    pass


# 全局连接池配置（可自定义）
_pool_config: ConnectionPoolConfig | None = None
_config_lock = threading.Lock()


def set_pool_config(config: ConnectionPoolConfig) -> None:
    """设置全局连接池配置（必须在首次获取引擎前调用）"""
    global _pool_config
    with _config_lock:
        _pool_config = config


def get_pool_config() -> ConnectionPoolConfig:
    """获取当前连接池配置"""
    global _pool_config
    if _pool_config is None:
        _pool_config = ConnectionPoolConfig()
    return _pool_config


def _get_database_url() -> str:
    """延迟获取数据库 URL，确保环境变量已设置"""
    if os.getenv("TESTING") == "1":
        # 使用文件型 SQLite 而非内存型，避免连接池问题
        return os.getenv(
            "TEST_DATABASE_URL",
            "sqlite:///./test.db?check_same_thread=False",
        )
    try:
        from src.config import settings

        return settings.database_url
    except Exception:
        return os.getenv(
            "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/eval_platform"
        )


def _create_engine() -> Engine:
    """延迟创建引擎函数"""
    database_url = _get_database_url()
    config = get_pool_config()

    if database_url.startswith("sqlite"):
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
        )
    else:
        return create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_timeout=config.pool_timeout,
            pool_recycle=config.pool_recycle,
            pool_pre_ping=config.pool_pre_ping,
            pool_use_lifo=config.pool_use_lifo,
        )


# 使用惰性初始化模式，避免模块导入时创建引擎
_engine: Engine | None = None
_session_local: sessionmaker | None = None
_pool_metrics = ConnectionPoolMetrics()
_metrics_lock = threading.Lock()

# 全局连接泄漏检测器
_leak_detector: ConnectionLeakDetector | None = None
_leak_detector_lock = threading.Lock()


def get_leak_detector() -> ConnectionLeakDetector:
    """获取连接泄漏检测器（惰性初始化）"""
    global _leak_detector
    if _leak_detector is None:
        with _leak_detector_lock:
            if _leak_detector is None:
                # 从环境变量读取泄漏阈值，默认60秒
                threshold = _get_env_int("DB_LEAK_THRESHOLD_SECONDS", 60)
                _leak_detector = ConnectionLeakDetector(leak_threshold_seconds=threshold)
    return _leak_detector


def set_leak_detector(detector: ConnectionLeakDetector) -> None:
    """设置自定义泄漏检测器"""
    global _leak_detector
    with _leak_detector_lock:
        _leak_detector = detector


def get_engine() -> Engine:
    """获取数据库引擎（惰性初始化）"""
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def get_session_local() -> sessionmaker:
    """获取 SessionLocal（惰性初始化）"""
    global _session_local
    if _session_local is None:
        _session_local = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _session_local


# 为了保持向后兼容，提供可调用的 SessionLocal
SessionLocal: sessionmaker | None = None  # 占位符，将在首次调用时初始化


def _update_pool_metrics() -> None:
    """更新连接池指标"""
    global _pool_metrics
    engine = get_engine()

    if hasattr(engine, "pool") and isinstance(engine.pool, QueuePool):
        qpool = engine.pool
        with _metrics_lock:
            _pool_metrics.pool_size = qpool.size()
            _pool_metrics.checked_in = qpool.checkedin()
            _pool_metrics.checked_out = qpool.checkedout()
            _pool_metrics.overflow = qpool.overflow()
            # queue_size 在某些 SQLAlchemy 版本中不存在，使用 getattr 安全获取
            _pool_metrics.queue_size = getattr(qpool, "queue_size", 0)
            _pool_metrics.total_connections = _pool_metrics.pool_size + _pool_metrics.overflow
            _pool_metrics.active_connections = _pool_metrics.checked_out
            _pool_metrics.idle_connections = _pool_metrics.checked_in
            _pool_metrics.last_update_time = time.time()


def get_pool_metrics() -> ConnectionPoolMetrics:
    """获取连接池监控指标"""
    _update_pool_metrics()
    return _pool_metrics


def get_pool_status() -> dict[str, Any]:
    """获取连接池状态摘要（包含泄漏检测信息）"""
    metrics = get_pool_metrics()
    leak_report = get_leak_detector().get_leak_report()
    return {
        "pool_size": metrics.pool_size,
        "checked_in": metrics.checked_in,
        "checked_out": metrics.checked_out,
        "overflow": metrics.overflow,
        "queue_size": metrics.queue_size,
        "total": metrics.total_connections,
        "active": metrics.active_connections,
        "idle": metrics.idle_connections,
        "utilization_rate": (
            f"{metrics.active_connections / metrics.pool_size * 100:.1f}%"
            if metrics.pool_size > 0
            else "N/A"
        ),
        "leak_detection": leak_report,
    }


def get_leak_report() -> dict[str, Any]:
    """获取连接泄漏报告"""
    return get_leak_detector().get_leak_report()


def detect_connection_leaks() -> list[ConnectionLeakInfo]:
    """检测潜在的连接泄漏"""
    return get_leak_detector().detect_leaks()


def reset_pool_metrics() -> None:
    """重置连接池指标统计"""
    global _pool_metrics
    with _metrics_lock:
        _pool_metrics = ConnectionPoolMetrics()


# 连接获取和释放钩子
_on_checkout_hooks: list = []
_on_checkin_hooks: list = []


def register_checkout_hook(hook: callable) -> None:
    """注册连接检出钩子"""
    _on_checkout_hooks.append(hook)


def register_checkin_hook(hook: callable) -> None:
    """注册连接归还钩子"""
    _on_checkin_hooks.append(hook)


def _execute_checkout_hooks(conn: Any) -> None:
    """执行所有连接检出钩子"""
    for hook in _on_checkout_hooks:
        try:
            hook(conn)
        except Exception:
            pass  # 钩子错误不应影响主流程


def _execute_checkin_hooks(conn: Any) -> None:
    """执行所有连接归还钩子"""
    for hook in _on_checkin_hooks:
        try:
            hook(conn)
        except Exception:
            pass  # 钩子错误不应影响主流程


# 为Engine添加连接监听器
def _setup_engine_listeners(engine: Engine) -> None:
    """设置引擎事件监听器"""
    if not hasattr(engine, "pool") or not isinstance(engine.pool, QueuePool):
        return

    @event.listens_for(engine, "checkout")
    def on_checkout(dbapi_conn: Any, connection_record: Any, proxy: Any) -> None:
        _update_pool_metrics()
        _execute_checkout_hooks(dbapi_conn)
        # 跟踪连接检出（泄漏检测）
        try:
            get_leak_detector().track_checkout(dbapi_conn)
        except Exception as e:
            logger.debug(f"Failed to track checkout: {e}")

    @event.listens_for(engine, "checkin")
    def on_checkin(dbapi_conn: Any, connection_record: Any) -> None:
        _update_pool_metrics()
        _execute_checkin_hooks(dbapi_conn)
        # 跟踪连接归还（泄漏检测）
        try:
            get_leak_detector().track_checkin(dbapi_conn)
        except Exception as e:
            logger.debug(f"Failed to track checkin: {e}")


_db_breaker = global_registry.get_or_create(
    "database",
    CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=10,
        half_open_max_calls=2,
    ),
)


# 继承 db.py 的增强版上下文管理器：彻底解决大模型报错时的事务回滚与连接泄露
@contextmanager
def get_db_session() -> Generator:
    """获取数据库会话上下文管理器（优化版）

    特性：
    - 自动管理事务提交/回滚
    - 连接泄露防护
    - 连接池监控指标更新
    - 可选的连接有效性预检
    - 熔断器保护（数据库故障降级）
    """

    def _create_and_validate_session():
        db = get_session_local()()
        try:
            db.execute(text("SELECT 1"))
        except Exception:
            db.close()
            raise
        return db

    try:
        db = _db_breaker.call_sync(_create_and_validate_session)
    except CircuitBreakerError:
        raise InfrastructureError("数据库暂时不可用，请稍后重试") from None

    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# 完美兼容老代码或旧测试的普通生成器函数
def get_db() -> Generator:
    """获取数据库会话生成器（保持向后兼容）"""
    with get_db_session() as session:
        yield session


# 【关键！】吸取自 session.py 的建表冷启动函数
def init_tables() -> None:
    # 导入所有模型以确保它们注册到 metadata
    from src.infra.db import models  # noqa: F401  确保模型注册到 metadata

    engine = get_engine()
    _setup_engine_listeners(engine)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    print("【系统通知】表结构已创建成功！")


# 提供 engine 属性访问（惰性）
class _LazyEngine:
    """惰性引擎包装器，支持属性访问"""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_engine(), name)


engine = _LazyEngine()


def invalidate_pool() -> None:
    """使当前连接池失效，强制重新创建（用于配置变更后）"""
    global _engine, _session_local
    if _engine is not None:
        _engine.dispose()
        _engine = None
    _session_local = None


def close_all_connections() -> None:
    """关闭所有连接池中的连接"""
    engine = get_engine()
    if hasattr(engine, "pool"):
        engine.pool.dispose()


if __name__ == "__main__":
    init_tables()
