import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


if os.getenv("TESTING") == "1":
    DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
else:
    DATABASE_URL = os.getenv(
        "DATABASE_URL", "postgresql://postgres:tiger13@localhost:5432/eval_db"
    )

if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# 3. 继承 db.py 的增强版上下文管理器：彻底解决大模型报错时的事务回滚与连接泄露
@contextmanager
def get_db_session():
    db = SessionLocal()
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

    Base.metadata.create_all(bind=engine)
    print("【系统通知】表结构已在 eval_db 中创建成功！")


if __name__ == "__main__":
    init_tables()
