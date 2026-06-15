"""测试仓储层功能"""

import pytest
from unittest.mock import Mock, patch

from src.infra.db.repository import EvaluationRepository, SQLiteRepository
from src.schemas.schemas import EvaluationResult, EvaluationStatus
from src.schemas.evaluation import DomainResponse


class TestEvaluationRepository:
    """测试评估结果仓储"""

    def test_save_with_valid_result(self):
        """测试保存有效评估结果"""
        with patch('src.infra.db.repository.get_db_session') as mock_get_session:
            mock_session = Mock()
            mock_get_session.return_value.__enter__.return_value = mock_session
            
            repo = EvaluationRepository()
            result = EvaluationResult(
                case_id="test_case_001",
                model_name="test_model",
                adapter_name="test_adapter",
                status=EvaluationStatus.PASSED,
                latency_ms=100.0,
                response=DomainResponse(text="test output", score=1.0)
            )
            
            # Mock 数据库操作
            mock_session.add = Mock()
            mock_session.flush = Mock()
            mock_session.commit = Mock()
            
            # 创建一个模拟的数据库记录
            mock_record = Mock()
            mock_record.id = 123
            
            # 通过 side_effect 来捕获添加的对象并设置其 id
            def capture_record(record):
                record.id = 123
            
            mock_session.add.side_effect = capture_record
            
            saved_id = repo.save(result)
            
            assert saved_id == 123
            mock_session.add.assert_called_once()
            mock_session.flush.assert_called_once()
            mock_session.commit.assert_called_once()

    def test_save_with_empty_case_id_raises_error(self):
        """测试保存空 case_id 时抛出异常"""
        repo = EvaluationRepository()
        result = EvaluationResult(
            case_id="",
            model_name="test_model",
            adapter_name="test_adapter",
            status=EvaluationStatus.PASSED,
            latency_ms=100.0,
            response=DomainResponse(text="test output", score=1.0)
        )
        
        with pytest.raises(ValueError, match="持久化失败：评估结果缺少核心 case_id"):
            repo.save(result)

    def test_save_with_whitespace_case_id_raises_error(self):
        """测试保存空白字符 case_id 时抛出异常"""
        repo = EvaluationRepository()
        result = EvaluationResult(
            case_id="   ",
            model_name="test_model",
            adapter_name="test_adapter",
            status=EvaluationStatus.PASSED,
            latency_ms=100.0,
            response=DomainResponse(text="test output", score=1.0)
        )
        
        with pytest.raises(ValueError, match="持久化失败：评估结果缺少核心 case_id"):
            repo.save(result)


class TestSQLiteRepository:
    """测试 SQLite 仓储（兼容层）"""

    def test_save_returns_zero(self):
        """测试 SQLite 仓储返回 0（模拟实现）"""
        repo = SQLiteRepository(db_path=":memory:")
        result = EvaluationResult(
            case_id="test_case_003",
            model_name="test_model",
            adapter_name="test_adapter",
            status=EvaluationStatus.PASSED,
            latency_ms=75.0,
            response=DomainResponse(text="test", score=0.5)
        )
        
        saved_id = repo.save(result)
        assert saved_id == 0

    def test_init_with_db_path(self):
        """测试初始化时设置数据库路径"""
        repo = SQLiteRepository(db_path="/tmp/test.db")
        assert repo.db_path == "/tmp/test.db"
