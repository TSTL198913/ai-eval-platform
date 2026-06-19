"""
数据仓储层单元测试 - 带有效断言
覆盖: CRUD、批量操作、字段白名单、空值处理
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from src.infra.db.session import init_tables
init_tables()

from src.infra.db.repository import EvaluationRepository, TrajectoryRepository
from src.schemas.schemas import EvaluationResult, EvaluationStatus
from src.schemas.evaluation import DomainResponse


@pytest.fixture
def repo():
    """提供干净的仓储实例"""
    return EvaluationRepository()


@pytest.fixture
def sample_result():
    """提供样本评估结果"""
    return EvaluationResult(
        case_id="unit_test_case_001",
        status=EvaluationStatus.PASSED,
        model_name="gpt-4",
        adapter_name="GeneralEvaluator",
        response=DomainResponse(is_valid=True, score=0.95, text="good result"),
        latency_ms=150.5,
    )


class TestRepositorySave:
    """保存操作单元测试"""

    def test_save_returns_positive_id(self, repo, sample_result):
        """保存应返回正整数 ID"""
        db_id = repo.save(sample_result)
        assert isinstance(db_id, int)
        assert db_id > 0

    def test_save_increments_id(self, repo, sample_result):
        """多次保存 ID 应递增"""
        id1 = repo.save(sample_result)
        sample_result.case_id = "unit_test_case_002"
        id2 = repo.save(sample_result)
        assert id2 > id1

    def test_save_empty_case_id_raises(self, repo):
        """空 case_id 应抛出 ValueError"""
        result = EvaluationResult(
            case_id="",
            status=EvaluationStatus.PASSED,
            model_name="test",
            adapter_name="test",
            response=DomainResponse(is_valid=True),
            latency_ms=0.0,
        )
        with pytest.raises(ValueError) as exc_info:
            repo.save(result)
        assert "case_id" in str(exc_info.value)

    def test_save_whitespace_case_id_raises(self, repo):
        """纯空白 case_id 应抛出 ValueError"""
        result = EvaluationResult(
            case_id="   ",
            status=EvaluationStatus.PASSED,
            model_name="test",
            adapter_name="test",
            response=DomainResponse(is_valid=True),
            latency_ms=0.0,
        )
        with pytest.raises(ValueError) as exc_info:
            repo.save(result)
        assert "case_id" in str(exc_info.value)

class TestRepositoryGetById:
    """按 ID 查询单元测试"""

    def test_get_by_id_existing_record(self, repo, sample_result):
        """存在的记录应能查询到"""
        db_id = repo.save(sample_result)
        record = repo.get_by_id(db_id)
        assert record is not None
        assert record["id"] == db_id
        assert record["case_id"] == "unit_test_case_001"
        assert record["model_name"] == "gpt-4"
        assert record["status"] == "passed"
        assert record["latency_ms"] == 150.5

    def test_get_by_id_nonexistent_returns_none(self, repo):
        """不存在的 ID 应返回 None"""
        record = repo.get_by_id(999999)
        assert record is None

    def test_get_by_id_negative_id_returns_none(self, repo):
        """负 ID 应返回 None"""
        record = repo.get_by_id(-1)
        assert record is None


class TestRepositoryGetRecent:
    """最近记录查询单元测试"""

    def test_get_recent_returns_list(self, repo, sample_result):
        """应返回列表"""
        repo.save(sample_result)
        records = repo.get_recent(limit=5)
        assert isinstance(records, list)
        assert len(records) >= 1

    def test_get_recent_respects_limit(self, repo, sample_result):
        """limit 参数应生效"""
        for i in range(5):
            sample_result.case_id = f"batch_{i}"
            repo.save(sample_result)
        records = repo.get_recent(limit=3)
        assert len(records) == 3

    def test_get_recent_returns_required_fields(self, repo, sample_result):
        """返回的记录应包含必要字段"""
        repo.save(sample_result)
        records = repo.get_recent(limit=1)
        record = records[0]
        required_fields = {"id", "case_id", "model_name", "adapter_name", "status", "latency_ms", "created_at"}
        assert required_fields.issubset(set(record.keys()))

    def test_get_recent_ordered_by_created_at_desc(self, repo, sample_result):
        """应按 created_at 降序排列"""
        import time
        for i in range(3):
            sample_result.case_id = f"order_test_{i}"
            repo.save(sample_result)
            time.sleep(0.01)  # 确保 created_at 有差异
        records = repo.get_recent(limit=3)
        # 最新的应在最前面
        assert records[0]["case_id"] == "order_test_2"


class TestRepositoryCount:
    """计数单元测试"""

    def test_count_increases_after_save(self, repo, sample_result):
        """保存后计数应增加"""
        initial = repo.count()
        repo.save(sample_result)
        final = repo.count()
        assert final == initial + 1

    def test_count_returns_integer(self, repo):
        """计数应返回整数"""
        count = repo.count()
        assert isinstance(count, int)
        assert count >= 0


class TestRepositoryUpdate:
    """更新操作单元测试"""

    def test_update_allowed_fields(self, repo, sample_result):
        """允许更新的字段应生效"""
        db_id = repo.save(sample_result)
        success = repo.update(db_id, {"model_name": "gpt-3.5-turbo", "status": "failed"})
        assert success is True
        record = repo.get_by_id(db_id)
        assert record["model_name"] == "gpt-3.5-turbo"
        assert record["status"] == "failed"

    def test_update_disallowed_fields_ignored(self, repo, sample_result):
        """不允许的字段应被忽略"""
        db_id = repo.save(sample_result)
        original_case_id = sample_result.case_id
        success = repo.update(db_id, {"case_id": "hacked", "model_name": "new-model"})
        assert success is True  # model_name 被更新
        record = repo.get_by_id(db_id)
        assert record["case_id"] == original_case_id  # case_id 不应被修改
        assert record["model_name"] == "new-model"

    def test_update_empty_data_returns_false(self, repo, sample_result):
        """空更新数据应返回 False"""
        db_id = repo.save(sample_result)
        success = repo.update(db_id, {})
        assert success is False

    def test_update_nonexistent_returns_false(self, repo):
        """更新不存在的记录应返回 False"""
        success = repo.update(999999, {"model_name": "test"})
        assert success is False


class TestRepositoryDelete:
    """删除操作单元测试"""

    def test_delete_existing_record(self, repo, sample_result):
        """删除存在的记录应成功"""
        db_id = repo.save(sample_result)
        success = repo.delete(db_id)
        assert success is True
        assert repo.get_by_id(db_id) is None

    def test_delete_nonexistent_returns_false(self, repo):
        """删除不存在的记录应返回 False"""
        success = repo.delete(999999)
        assert success is False


class TestRepositoryBatchOperations:
    """批量操作单元测试"""

    def test_batch_delete(self, repo, sample_result):
        """批量删除应生效"""
        ids = []
        for i in range(5):
            sample_result.case_id = f"batch_del_{i}"
            ids.append(repo.save(sample_result))
        deleted_count = repo.batch_delete(ids[:3])
        assert deleted_count == 3
        # 验证被删除的记录确实不存在了
        for db_id in ids[:3]:
            assert repo.get_by_id(db_id) is None

    def test_batch_delete_empty_list_returns_zero(self, repo):
        """空列表批量删除应返回 0"""
        count = repo.batch_delete([])
        assert count == 0

    def test_batch_update(self, repo, sample_result):
        """批量更新应生效"""
        ids = []
        for i in range(3):
            sample_result.case_id = f"batch_upd_{i}"
            ids.append(repo.save(sample_result))
        updated = repo.batch_update(ids, {"status": "error"})
        assert updated == 3
        for db_id in ids:
            record = repo.get_by_id(db_id)
            assert record["status"] == "error"

    def test_batch_update_empty_list_returns_zero(self, repo):
        """空列表批量更新应返回 0"""
        count = repo.batch_update([], {"status": "error"})
        assert count == 0

    def test_batch_update_empty_data_returns_zero(self, repo, sample_result):
        """空数据批量更新应返回 0"""
        db_id = repo.save(sample_result)
        count = repo.batch_update([db_id], {})
        assert count == 0


class TestRepositorySearch:
    """搜索操作单元测试"""

    def test_search_by_status(self, repo, sample_result):
        """按状态搜索应生效"""
        repo.save(sample_result)
        results = repo.search(status="passed", limit=10)
        assert len(results) >= 1
        for r in results:
            assert r["status"] == "passed"

    def test_search_by_evaluator(self, repo, sample_result):
        """按评估器搜索应生效"""
        repo.save(sample_result)
        results = repo.search(evaluator="GeneralEvaluator", limit=10)
        assert len(results) >= 1
        for r in results:
            assert r["adapter_name"] == "GeneralEvaluator"

    def test_search_offset(self, repo, sample_result):
        """offset 应生效"""
        for i in range(5):
            sample_result.case_id = f"search_off_{i}"
            repo.save(sample_result)
        results = repo.search(limit=2, offset=2)
        assert len(results) == 2

    def test_search_sort_order(self, repo, sample_result):
        """排序应生效"""
        for i in range(3):
            sample_result.case_id = f"sort_{i}"
            repo.save(sample_result)
        results_asc = repo.search(limit=3, sort_order="asc")
        results_desc = repo.search(limit=3, sort_order="desc")
        assert results_asc[0]["id"] <= results_asc[-1]["id"]
        assert results_desc[0]["id"] >= results_desc[-1]["id"]


class TestRepositoryCreate:
    """创建操作单元测试"""

    def test_create_with_dict(self, repo):
        """用字典创建应成功"""
        db_id = repo.create({
            "case_id": "create_test",
            "model_name": "test-model",
            "adapter_name": "TestAdapter",
            "status": "passed",
            "latency_ms": 100.0,
            "response_data": {"score": 0.9},
        })
        assert db_id > 0
        record = repo.get_by_id(db_id)
        assert record["case_id"] == "create_test"

    def test_create_with_string_response_data(self, repo):
        """response_data 为字符串时应被解析"""
        db_id = repo.create({
            "case_id": "create_str_test",
            "model_name": "test",
            "adapter_name": "test",
            "status": "passed",
            "response_data": '{"score": 0.8}',
        })
        assert db_id > 0


class TestTrajectoryRepository:
    """轨迹仓储单元测试"""

    def test_save_step_returns_id(self):
        """保存步骤应返回 ID"""
        traj_repo = TrajectoryRepository()
        step_id = traj_repo.save_step(
            task_id="task_001",
            step_index=0,
            step_type="llm_call",
            prompt="hello",
            response="world",
        )
        assert isinstance(step_id, int)
        assert step_id > 0

    def test_save_step_empty_task_id_raises(self):
        """空 task_id 应抛出 ValueError"""
        traj_repo = TrajectoryRepository()
        with pytest.raises(ValueError) as exc_info:
            traj_repo.save_step(task_id="", step_index=0, step_type="test", prompt="p", response="r")
        assert "task_id" in str(exc_info.value)

    def test_get_trajectory(self):
        """获取轨迹应返回正确步骤"""
        traj_repo = TrajectoryRepository()
        traj_repo.save_step("task_002", 0, "llm", "prompt1", "resp1")
        traj_repo.save_step("task_002", 1, "tool", "prompt2", "resp2", tool_name="search")
        steps = traj_repo.get_trajectory("task_002")
        assert len(steps) == 2
        assert steps[0]["step_index"] == 0
        assert steps[1]["step_index"] == 1
        assert steps[1]["tool_name"] == "search"

    def test_delete_trajectory(self):
        """删除轨迹应生效"""
        traj_repo = TrajectoryRepository()
        traj_repo.save_step("task_003", 0, "llm", "p", "r")
        count = traj_repo.delete_trajectory("task_003")
        assert count == 1
        steps = traj_repo.get_trajectory("task_003")
        assert len(steps) == 0
