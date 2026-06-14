import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def _get_database_url() -> str:
    """延迟获取数据库 URL，确保环境变量已设置"""
    if os.getenv("TESTING") == "1":
        return os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    return os.getenv("DATABASE_URL", "postgresql://postgres:tiger13@localhost:5432/eval_db")


def _create_engine():
    """延迟创建引擎函数"""
    database_url = _get_database_url()

    if database_url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        return create_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
            pool_pre_ping=True,
        )


# 使用惰性初始化模式，避免模块导入时创建引擎
_engine = None
_session_local = None


def get_engine():
    """获取数据库引擎（惰性初始化）"""
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def get_session_local():
    """获取 SessionLocal（惰性初始化）"""
    global _session_local, SessionLocal
    if _session_local is None:
        _session_local = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
        # 同步更新 SessionLocal 变量（向后兼容）
        SessionLocal = _session_local
    return _session_local


# 为了保持向后兼容，提供可调用的 SessionLocal
SessionLocal = None  # 占位符，将在首次调用时初始化


# 3. 继承 db.py 的增强版上下文管理器：彻底解决大模型报错时的事务回滚与连接泄露
@contextmanager
def get_db_session():
    db = get_session_local()()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# 4. 完美兼容老代码或旧测试的普通生成器函数
def get_db():
    with get_db_session() as session:
        yield session


# 5. 【关键！】吸取自 session.py 的建表冷启动函数
def init_tables():
    from src.infra.db import models  # noqa: F401  确保模型注册到 metadata

    Base.metadata.create_all(bind=get_engine())
    print("【系统通知】表结构已在 eval_db 中创建成功！")


# 提供 engine 属性访问（惰性）
class _LazyEngine:
    """惰性引擎包装器，支持属性访问"""

    def __getattr__(self, name):
        return getattr(get_engine(), name)


engine = _LazyEngine()


if __name__ == "__main__":
    init_tables()
