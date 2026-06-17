from unittest.mock import MagicMock, patch

import pytest

from src.infra.db.repository import (
    BaseRepository,
    EvaluationRepository,
    SQLiteRepository,
    TrajectoryRepository,
)
from src.schemas.evaluation import DomainResponse
from src.schemas.schemas import EvaluationResult


def _make_result(case_id: str = "c1", status: str = "passed") -> EvaluationResult:
    return EvaluationResult(
        case_id=case_id,
        model_name="gpt-4",
        adapter_name="default",
        status=status,
        response=DomainResponse(is_valid=True, score=1.0),
        latency_ms=100.0,
    )


class TestBaseRepository:
    """仓储基类测试"""

    def test_base_repository_is_abstract(self):
        """测试基类是抽象类"""

        with pytest.raises(TypeError):
            BaseRepository()


class TestEvaluationRepository:
    """评估仓储测试"""

    def setup_method(self):
        self.repo = EvaluationRepository()

    @patch("src.infra.db.repository.get_db_session")
    def test_save_success(self, mock_get_session):
        """测试保存成功"""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        result = _make_result()

        record_id = self.repo.save(result)

        # 验证 session.add 被调用，且添加的记录有正确的 case_id
        assert mock_session.add.call_count == 1
        added_record = mock_session.add.call_args[0][0]
        assert added_record.case_id == "c1"
        assert added_record.model_name == "gpt-4"
        mock_session.commit.assert_called_once()

    def test_save_missing_case_id(self):
        """测试缺少case_id"""
        result = _make_result(case_id="")

        with pytest.raises(ValueError, match="case_id"):
            self.repo.save(result)

    def test_save_whitespace_case_id(self):
        """测试空白case_id"""
        result = _make_result(case_id="   ")

        with pytest.raises(ValueError, match="case_id"):
            self.repo.save(result)

    @patch("src.infra.db.repository.get_db_session")
    def test_count(self, mock_get_session):
        """测试计数"""
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = (100,)
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        count = self.repo.count()

        assert count == 100

    @patch("src.infra.db.repository.get_db_session")
    def test_count_none_result(self, mock_get_session):
        """测试计数无结果"""
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = None
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        count = self.repo.count()

        assert count == 0

    @patch("src.infra.db.repository.get_db_session")
    def test_get_recent(self, mock_get_session):
        """测试获取最近记录"""
        from datetime import datetime

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [
            (1, "c1", "gpt-4", "default", "passed", 100.0, datetime.now()),
        ]
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        records = self.repo.get_recent(limit=10)

        assert len(records) == 1
        assert records[0]["case_id"] == "c1"

    @patch("src.infra.db.repository.get_db_session")
    def test_get_recent_empty(self, mock_get_session):
        """测试获取最近记录为空"""
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = []
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        records = self.repo.get_recent(limit=10)

        assert records == []

    @patch("src.infra.db.repository.get_db_session")
    def test_get_recent_none_timestamp(self, mock_get_session):
        """测试获取最近记录无时间戳"""
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [
            (1, "c1", "gpt-4", "default", "passed", 100.0, None),
        ]
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        records = self.repo.get_recent(limit=10)

        assert len(records) == 1
        assert records[0]["created_at"] is None

    @patch("src.infra.db.repository.get_db_session")
    def test_search_by_evaluator(self, mock_get_session):
        """测试按评估器搜索"""
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [
            (1, "c1", "gpt-4", "finance", "passed", 100.0, None),
        ]
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        records = self.repo.search(evaluator="finance")

        assert len(records) == 1
        assert records[0]["adapter_name"] == "finance"

    @patch("src.infra.db.repository.get_db_session")
    def test_search_by_status(self, mock_get_session):
        """测试按状态搜索"""
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [
            (1, "c1", "gpt-4", "default", "failed", 100.0, None),
        ]
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        records = self.repo.search(status="failed")

        assert len(records) == 1
        assert records[0]["status"] == "failed"

    @patch("src.infra.db.repository.get_db_session")
    def test_search_by_evaluator_and_status(self, mock_get_session):
        """测试按评估器和状态组合搜索"""
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [
            (1, "c1", "gpt-4", "finance", "passed", 100.0, None),
        ]
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        records = self.repo.search(evaluator="finance", status="passed")

        assert len(records) == 1

    @patch("src.infra.db.repository.get_db_session")
    def test_search_empty(self, mock_get_session):
        """测试搜索无结果"""
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = []
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        records = self.repo.search(evaluator="nonexistent")

        assert records == []


class TestSQLiteRepository:
    """SQLite仓储测试"""

    def test_save(self):
        """测试保存"""
        repo = SQLiteRepository(":memory:")
        result = _make_result()

        record_id = repo.save(result)
        assert record_id == 0


class TestTrajectoryRepository:
    """轨迹仓储测试"""

    def setup_method(self):
        self.repo = TrajectoryRepository()

    @patch("src.infra.db.repository.get_db_session")
    def test_save_step_success(self, mock_get_session):
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        step_id = self.repo.save_step(
            task_id="task_001",
            step_index=1,
            step_type="thought",
            prompt="思考中...",
            response="我需要调用工具",
        )

        assert mock_session.add.call_count == 1
        mock_session.commit.assert_called_once()

    def test_save_step_missing_task_id(self):
        with pytest.raises(ValueError, match="task_id"):
            self.repo.save_step(
                task_id="",
                step_index=1,
                step_type="thought",
                prompt="思考中...",
                response="我需要调用工具",
            )

    def test_save_step_whitespace_task_id(self):
        with pytest.raises(ValueError, match="task_id"):
            self.repo.save_step(
                task_id="   ",
                step_index=1,
                step_type="thought",
                prompt="思考中...",
                response="我需要调用工具",
            )

    @patch("src.infra.db.repository.get_db_session")
    def test_save_step_with_tool(self, mock_get_session):
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        step_id = self.repo.save_step(
            task_id="task_001",
            step_index=2,
            step_type="tool_call",
            prompt="调用计算器",
            response="100",
            tool_name="calculator",
            tool_params={"expression": "50+50"},
            is_correct=True,
        )

        assert mock_session.add.call_count == 1
        added_record = mock_session.add.call_args[0][0]
        assert added_record.tool_name == "calculator"
        assert added_record.tool_params == {"expression": "50+50"}
        assert added_record.is_correct == 1

    @patch("src.infra.db.repository.get_db_session")
    def test_save_steps(self, mock_get_session):
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        steps = [
            {
                "task_id": "task_001",
                "step_index": 1,
                "step_type": "thought",
                "prompt": "思考1",
                "response": "响应1",
            },
            {
                "task_id": "task_001",
                "step_index": 2,
                "step_type": "tool_call",
                "prompt": "调用工具",
                "response": "结果",
                "tool_name": "calculator",
                "is_correct": True,
            },
        ]

        ids = self.repo.save_steps(steps)

        assert len(ids) == 2
        assert mock_session.add.call_count == 2

    @patch("src.infra.db.repository.get_db_session")
    def test_get_trajectory(self, mock_get_session):
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_result1 = MagicMock()
        mock_result1.to_dict.return_value = {"step_index": 1, "step_type": "thought"}
        mock_result2 = MagicMock()
        mock_result2.to_dict.return_value = {"step_index": 2, "step_type": "tool_call"}

        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_result1,
            mock_result2,
        ]

        trajectory = self.repo.get_trajectory("task_001")

        assert len(trajectory) == 2
        assert trajectory[0]["step_index"] == 1

    @patch("src.infra.db.repository.get_db_session")
    def test_get_trajectory_empty(self, mock_get_session):
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        trajectory = self.repo.get_trajectory("task_nonexistent")

        assert trajectory == []

    @patch("src.infra.db.repository.get_db_session")
    def test_get_recent_trajectories(self, mock_get_session):
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"task_id": "task_001"}
        mock_session.query.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_result,
        ]

        trajectories = self.repo.get_recent_trajectories(limit=5)

        assert len(trajectories) == 1

    @patch("src.infra.db.repository.get_db_session")
    def test_delete_trajectory(self, mock_get_session):
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.query.return_value.filter.return_value.delete.return_value = 3

        count = self.repo.delete_trajectory("task_001")

        assert count == 3
        mock_session.commit.assert_called_once()

    @patch("src.infra.db.repository.get_db_session")
    def test_delete_trajectory_nonexistent(self, mock_get_session):
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.query.return_value.filter.return_value.delete.return_value = 0

        count = self.repo.delete_trajectory("task_nonexistent")

        assert count == 0

    @patch("src.infra.db.repository.get_db_session")
    def test_count(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = (50,)
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        count = self.repo.count()

        assert count == 50

    @patch("src.infra.db.repository.get_db_session")
    def test_count_none_result(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = None
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        count = self.repo.count()

        assert count == 0