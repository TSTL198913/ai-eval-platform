"""
仓储层测试用例
"""

import pytest

from src.infra.db.repository import EvaluationRepository, SQLiteRepository
from src.infra.db.session import init_tables
from src.schemas.evaluation import DomainResponse
from src.schemas.schemas import EvaluationResult, EvaluationStatus


@pytest.fixture(autouse=True)
def clean_global_db():
    init_tables()
    yield


class TestEvaluationRepository:
    """测试 EvaluationRepository"""

    def test_save_success(self, clean_global_db):
        """测试成功保存评估结果"""
        # 创建测试数据
        response = DomainResponse(
            score=0.85,
            feedback="测试反馈",
            details={"key": "value"},
            error=None,
        )

        result = EvaluationResult(
            case_id="TEST_CASE_001",
            status=EvaluationStatus.SUCCESS,
            model_name="test-model",
            adapter_name="test-adapter",
            response=response,
            latency_ms=123.45,
        )

        repository = EvaluationRepository()
        saved_id = repository.save(result)

        # 验证返回值
        assert saved_id is not None
        assert isinstance(saved_id, int)
        assert saved_id > 0

    def test_save_whitespace_case_id_raises_error(self):
        """测试空白字符 case_id 时抛出异常"""
        response = DomainResponse(
            score=0.85,
            feedback="测试反馈",
            details={},
            error=None,
        )

        result = EvaluationResult(
            case_id="   ",  # 空白字符
            status=EvaluationStatus.SUCCESS,
            model_name="test-model",
            adapter_name="test-adapter",
            response=response,
            latency_ms=123.45,
        )

        repository = EvaluationRepository()

        with pytest.raises(ValueError) as exc_info:
            repository.save(result)

        assert "持久化失败：评估结果缺少核心 case_id" in str(exc_info.value)

    def test_save_empty_case_id_raises_error(self):
        """测试空字符串 case_id 时抛出异常"""
        response = DomainResponse(
            score=0.85,
            feedback="测试反馈",
            details={},
            error=None,
        )

        result = EvaluationResult(
            case_id="",
            status=EvaluationStatus.SUCCESS,
            model_name="test-model",
            adapter_name="test-adapter",
            response=response,
            latency_ms=123.45,
        )

        repository = EvaluationRepository()

        with pytest.raises(ValueError) as exc_info:
            repository.save(result)

        assert "持久化失败：评估结果缺少核心 case_id" in str(exc_info.value)

    def test_save_with_default_values(self, clean_global_db):
        """测试使用默认值保存"""
        response = DomainResponse(
            score=0.70,
            feedback="",
            details={},
            error=None,
        )

        result = EvaluationResult(
            case_id="TEST_CASE_002",
            status=EvaluationStatus.PENDING,
            model_name="",
            adapter_name="",
            response=response,
            latency_ms=0.0,
        )

        repository = EvaluationRepository()
        saved_id = repository.save(result)

        assert saved_id is not None
        assert saved_id > 0

    def test_save_multiple_results(self, clean_global_db):
        """测试保存多个评估结果"""
        repository = EvaluationRepository()
        saved_ids = []

        for i in range(5):
            response = DomainResponse(
                score=0.8 + i * 0.02,
                feedback=f"测试反馈 {i}",
                details={"index": i},
                error=None,
            )

            result = EvaluationResult(
                case_id=f"TEST_CASE_{i:03d}",
                status=EvaluationStatus.SUCCESS,
                model_name="test-model",
                adapter_name="test-adapter",
                response=response,
                latency_ms=100.0 + i * 10.0,
            )

            saved_id = repository.save(result)
            saved_ids.append(saved_id)

        # 验证所有 ID 都是唯一且递增的
        assert len(saved_ids) == 5
        assert len(set(saved_ids)) == 5  # 所有 ID 唯一
        assert sorted(saved_ids) == list(range(saved_ids[0], saved_ids[0] + 5))  # 连续递增


class TestSQLiteRepository:
    """测试 SQLiteRepository（兼容层）"""

    def test_save_returns_zero(self):
        """测试 SQLiteRepository 的 save 方法返回 0"""
        response = DomainResponse(
            score=0.85,
            feedback="测试反馈",
            details={},
            error=None,
        )

        result = EvaluationResult(
            case_id="TEST_CASE_SQLITE",
            status=EvaluationStatus.SUCCESS,
            model_name="test-model",
            adapter_name="test-adapter",
            response=response,
            latency_ms=123.45,
        )

        repository = SQLiteRepository(db_path=":memory:")
        saved_id = repository.save(result)

        # SQLiteRepository 是测试模拟，返回 0
        assert saved_id == 0

    def test_init_with_db_path(self):
        """测试初始化时设置数据库路径"""
        repository = SQLiteRepository(db_path="/tmp/test.db")
        assert repository.db_path == "/tmp/test.db"
