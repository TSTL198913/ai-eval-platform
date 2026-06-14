"""测试 infra/db/session.py - 数据库会话管理"""

import os
from unittest.mock import Mock, patch

import pytest


class TestSessionModule:
    """测试会话模块"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_testing_mode(self):
        import importlib
        from src.infra.db import session as session_module

        importlib.reload(session_module)
        assert session_module.DATABASE_URL == "sqlite:///:memory:"

    @patch.dict(os.environ, {"TESTING": "1"}, clear=True)
    def test_testing_default(self):
        import importlib
        from src.infra.db import session as session_module

        importlib.reload(session_module)
        assert ":memory:" in session_module.DATABASE_URL

    @patch.dict(os.environ, {}, clear=True)
    def test_production_default(self):
        import importlib
        from src.infra.db import session as session_module

        importlib.reload(session_module)
        assert "postgresql" in session_module.DATABASE_URL

    @patch.dict(os.environ, {"DATABASE_URL": "sqlite:///test.db"})
    def test_sqlite_engine_config(self):
        import importlib
        from src.infra.db import session as session_module

        importlib.reload(session_module)
        assert session_module.engine is not None
        assert session_module.SessionLocal is not None


class TestGetDbSession:
    """测试数据库会话上下文管理器"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_session_commit(self):
        import importlib
        from src.infra.db import session as session_module

        importlib.reload(session_module)
        with session_module.get_db_session() as db:
            assert db is not None

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_session_rollback(self):
        import importlib
        from src.infra.db import session as session_module

        importlib.reload(session_module)
        try:
            with session_module.get_db_session() as db:
                assert db is not None
                raise ValueError("Test error")
        except ValueError:
            pass

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_session_close(self):
        import importlib
        from src.infra.db import session as session_module

        importlib.reload(session_module)
        with session_module.get_db_session() as db:
            pass


class TestGetDb:
    """测试 get_db 生成器"""

    @patch.dict(os.environ, {"TESTING": "1", "TEST_DATABASE_URL": "sqlite:///:memory:"})
    def test_get_db(self):
        import importlib
        from src.infra.db import session as session_module

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
        import importlib
        from src.infra.db import session as session_module

        importlib.reload(session_module)

        # Patch after reload to ensure we patch the reloaded Base
        with patch.object(session_module.Base.metadata, "create_all") as mock_create_all:
            session_module.init_tables()
            mock_create_all.assert_called_once()
