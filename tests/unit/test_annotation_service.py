"""
🧪 tests/unit/test_annotation_service.py
人工标注服务单元测试

依赖：使用 SQLite 内存数据库避免污染
"""

import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infra.db.models import (
    Base,
)

# ==================== Fixtures ====================


@pytest.fixture
def temp_db():
    """创建临时 SQLite 数据库"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    yield SessionLocal
    # 显式释放资源（Windows 兼容）
    engine.dispose()
    try:
        os.unlink(path)
    except (PermissionError, FileNotFoundError):
        pass  # Windows 上偶发文件被占用，跳过即可


@pytest.fixture
def service(temp_db):
    """注入测试数据库会话"""
    from src.services.annotation_svc import AnnotationService

    db = temp_db()
    svc = AnnotationService(db=db)
    yield svc
    db.close()


# ==================== 任务管理测试 ====================


class TestTaskManagementPositiveCases:
    """正向测试 - 任务管理"""

    def test_create_task(self, service):
        """创建任务"""
        task = service.create_task(
            case_id="case_001",
            evaluator_type="standard_metric",
            question="什么是 Python?",
            actual_output="Python 是一种编程语言",
            expected_output="Python 是解释型编程语言",
        )
        assert task.id is not None
        assert task.status == "pending"
        assert task.case_id == "case_001"

    def test_bulk_create_tasks(self, service):
        """批量创建"""
        cases = [
            {"case_id": "c1", "evaluator_type": "ragas", "question": "q1"},
            {"case_id": "c2", "evaluator_type": "deepeval", "question": "q2"},
        ]
        tasks = service.bulk_create_tasks(cases)
        assert len(tasks) == 2
        assert all(t.id is not None for t in tasks)

    def test_list_tasks_with_filters(self, service):
        """带过滤的列表查询"""
        service.create_task("c1", "ragas")
        service.create_task("c2", "deepeval")
        tasks = service.list_tasks(evaluator_type="ragas")
        assert len(tasks) == 1
        assert tasks[0].evaluator_type == "ragas"

    def test_get_task(self, service):
        """获取任务详情"""
        task = service.create_task("c1", "ragas", question="q")
        fetched = service.get_task(task.id)
        assert fetched.id == task.id


class TestTaskManagementNegativeCases:
    """负向测试 - 任务管理"""

    def test_get_nonexistent_task_raises(self, service):
        """查询不存在任务"""
        from src.services.annotation_svc import TaskNotFoundError

        with pytest.raises(TaskNotFoundError):
            service.get_task(99999)

    def test_update_invalid_status_raises(self, service):
        """非法状态更新"""
        task = service.create_task("c1", "ragas")
        with pytest.raises(ValueError, match="非法状态"):
            service.update_task_status(task.id, "invalid_state")


# ==================== 标注提交测试 ====================


class TestAnnotationSubmitPositiveCases:
    """正向测试 - 标注提交"""

    def test_submit_result(self, service):
        """提交标注"""
        task = service.create_task("c1", "ragas")
        result = service.submit_result(
            task_id=task.id,
            annotator_id="ann_1",
            score=0.85,
            comment="回答准确",
        )
        assert result.id is not None
        assert result.score == 0.85
        # 单标注员任务应自动完成
        assert task.status == "completed" or service.get_task(task.id).status == "completed"

    def test_submit_with_dimensions(self, service):
        """带多维度评分"""
        task = service.create_task("c1", "ragas")
        result = service.submit_result(
            task_id=task.id,
            annotator_id="ann_1",
            score=0.9,
            dimensions={"准确性": 0.9, "安全性": 0.95},
        )
        assert result.dimensions["准确性"] == 0.9

    def test_multi_annotator_advances_status(self, service):
        """多标注员推进任务状态"""
        task = service.create_task("c1", "ragas", required_annotators=2)
        service.submit_result(task.id, "ann_1", 0.8)
        # 第一次提交后任务应处于 in_progress
        assert service.get_task(task.id).status == "in_progress"
        service.submit_result(task.id, "ann_2", 0.9)
        # 第二次提交后应完成
        assert service.get_task(task.id).status == "completed"


class TestAnnotationSubmitNegativeCases:
    """负向测试 - 标注提交"""

    def test_duplicate_annotator_raises(self, service):
        """同一标注员重复标注应抛出"""
        from src.services.annotation_svc import DuplicateAnnotationError

        task = service.create_task("c1", "ragas")
        service.submit_result(task.id, "ann_1", 0.8)
        with pytest.raises(DuplicateAnnotationError):
            service.submit_result(task.id, "ann_1", 0.9)

    def test_invalid_score_raises(self, service):
        """非法分数应抛出"""
        from src.services.annotation_svc import InvalidScoreError

        task = service.create_task("c1", "ragas")
        with pytest.raises(InvalidScoreError):
            service.submit_result(task.id, "ann_1", 1.5)
        with pytest.raises(InvalidScoreError):
            service.submit_result(task.id, "ann_1", -0.1)

    def test_submit_to_nonexistent_task(self, service):
        """向不存在任务提交"""
        from src.services.annotation_svc import TaskNotFoundError

        with pytest.raises(TaskNotFoundError):
            service.submit_result(99999, "ann_1", 0.5)


# ==================== 一致性测试 ====================


class TestAgreementPositiveCases:
    """正向测试 - 一致性"""

    def test_cohens_kappa_perfect(self):
        """完全一致"""
        from src.services.annotation_svc import AnnotationService

        kappa = AnnotationService._cohens_kappa([1, 2, 3, 4], [1, 2, 3, 4])
        assert kappa == 1.0

    def test_cohens_kappa_random(self):
        """随机一致性"""
        from src.services.annotation_svc import AnnotationService

        kappa = AnnotationService._cohens_kappa([1, 1, 2, 2], [2, 2, 1, 1])
        # 完全相反，应为负
        assert kappa < 0

    def test_compute_agreement_with_data(self, service):
        """完整一致性计算"""
        # 创建并完成几个任务
        for i in range(5):
            task = service.create_task(f"c{i}", "ragas", required_annotators=2)
            service.submit_result(task.id, "ann_1", 0.7 + i * 0.05)
            service.submit_result(task.id, "ann_2", 0.75 + i * 0.04)

        agreement = service.compute_agreement("ragas")
        assert agreement is not None
        assert 0.0 <= agreement.kappa_score <= 1.0
        assert agreement.agreement_level in {
            "poor",
            "fair",
            "moderate",
            "substantial",
            "almost_perfect",
        }


class TestAgreementNegativeCases:
    """负向测试 - 一致性"""

    def test_compute_agreement_no_data(self, service):
        """无数据时返回 None"""
        result = service.compute_agreement("nonexistent_type")
        assert result is None

    def test_cohens_kappa_different_length(self):
        """长度不一致返回 None"""
        from src.services.annotation_svc import AnnotationService

        assert AnnotationService._cohens_kappa([1, 2], [1, 2, 3]) is None
        assert AnnotationService._cohens_kappa([], []) is None


# ==================== 黄金样本测试 ====================


class TestGoldenSamplePositiveCases:
    """正向测试 - 黄金样本"""

    def test_submit_golden_sample_passes(self, service):
        """黄金样本通过"""
        task = service.create_task("golden_1", "ragas", expected_output="0.9")
        result = service.submit_golden_sample(
            task_id=task.id,
            annotator_id="ann_1",
            golden_score=0.9,
        )
        assert result["pass"] is True
        assert result["needs_retraining"] is False

    def test_submit_golden_sample_fails(self, service):
        """黄金样本偏差过大"""
        task = service.create_task("golden_2", "ragas", expected_output="0.9")
        result = service.submit_golden_sample(
            task_id=task.id,
            annotator_id="ann_1",
            golden_score=0.3,
        )
        assert result["pass"] is False
        assert result["needs_retraining"] is True


# ==================== 标注员绩效测试 ====================


class TestAnnotatorStatsPositiveCases:
    """正向测试 - 标注员绩效"""

    def test_stats_for_active_annotator(self, service):
        """活跃标注员统计"""
        for i in range(3):
            task = service.create_task(f"c{i}", "ragas")
            service.submit_result(task.id, "ann_1", 0.7 + i * 0.1, time_spent_seconds=60)
        stats = service.get_annotator_stats("ann_1")
        assert stats["total_annotations"] == 3
        assert 0.7 < stats["avg_score"] < 0.9
        assert stats["avg_time_seconds"] == 60.0

    def test_stats_for_nonexistent_annotator(self, service):
        """不存在的标注员"""
        stats = service.get_annotator_stats("nonexistent")
        assert stats["total_annotations"] == 0


# ==================== 审核测试 ====================


class TestReviewPositiveCases:
    """正向测试 - 审核"""

    def test_review_result_approve(self, service):
        """审核通过"""
        task = service.create_task("c1", "ragas")
        result = service.submit_result(task.id, "ann_1", 0.8)
        reviewed = service.review_result(
            result_id=result.id,
            reviewer_id="rev_1",
            review_comment="标注准确",
            is_valid=True,
        )
        assert reviewed.is_valid is True
        assert reviewed.reviewer_id == "rev_1"


# ==================== 异常处理测试 ====================


class TestExceptionHandling:
    """异常处理测试"""

    def test_review_nonexistent_result(self, service):
        """审核不存在的标注"""
        from src.services.annotation_svc import AnnotationServiceError

        with pytest.raises(AnnotationServiceError):
            service.review_result(99999, "rev_1")
