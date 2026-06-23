"""
🧪 tests/integration/api/test_annotation_api_integration.py
人工标注 API 端到端集成测试

测试范围：
- 任务 CRUD 端点
- 标注结果提交/审核端点
- 一致性计算端点
- 黄金样本端点
- 标注员绩效端点
- 异常处理（404/409/400/422）

依赖：使用 SQLite 内存数据库避免污染主库
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infra.db.models import Base
from src.infra.db.session import get_db

# ==================== Fixtures ====================


@pytest.fixture
def temp_db_engine():
    """创建临时 SQLite 数据库引擎"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine, path
    engine.dispose()
    try:
        os.unlink(path)
    except (PermissionError, FileNotFoundError):
        pass


@pytest.fixture
def client(temp_db_engine):
    """FastAPI 测试客户端 + 隔离的 SQLite 数据库"""
    engine, _ = temp_db_engine
    TestingSessionLocal = sessionmaker(bind=engine)

    # 在 app/server 加载前 patch SessionLocal，避免 lifespan 拉起生产 DB
    from src.infra.db import session as db_session_module
    from src.services import annotation_svc

    original_session_local = db_session_module.SessionLocal
    db_session_module.SessionLocal = TestingSessionLocal
    annotation_svc.SessionLocal = TestingSessionLocal

    # 推迟 import 以避免 lifespan 中的 init_tables 干扰
    from src.api.server import app

    app.dependency_overrides[get_db] = lambda: (yield TestingSessionLocal())

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    db_session_module.SessionLocal = original_session_local
    annotation_svc.SessionLocal = original_session_local


# ==================== 任务管理端点测试 ====================


class TestAnnotationTaskEndpoints:
    """任务管理端点测试"""

    def test_create_task_returns_201(self, client):
        """创建任务 - 200 成功"""
        response = client.post(
            "/api/v1/annotations/tasks",
            json={
                "case_id": "case_001",
                "evaluator_type": "standard_metric",
                "question": "什么是 Python?",
                "actual_output": "Python 是一种编程语言",
                "expected_output": "Python 是解释型编程语言",
                "required_annotators": 1,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["case_id"] == "case_001"
        assert data["data"]["status"] == "pending"
        assert "id" in data["data"]

    def test_create_task_validation_error(self, client):
        """创建任务 - 422 验证错误（缺必填字段）"""
        response = client.post(
            "/api/v1/annotations/tasks",
            json={
                "question": "missing required fields",
            },
        )
        assert response.status_code == 422

    def test_bulk_create_tasks(self, client):
        """批量创建任务"""
        response = client.post(
            "/api/v1/annotations/tasks/bulk",
            json={
                "cases": [
                    {"case_id": "c1", "evaluator_type": "ragas"},
                    {"case_id": "c2", "evaluator_type": "deepeval"},
                ]
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["task_count"] == 2
        assert len(data["data"]["task_ids"]) == 2

    def test_list_tasks(self, client):
        """查询任务列表"""
        # 先创建两个任务
        for i in range(2):
            client.post(
                "/api/v1/annotations/tasks",
                json={"case_id": f"c{i}", "evaluator_type": "ragas"},
            )

        response = client.get("/api/v1/annotations/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] >= 2

    def test_list_tasks_with_status_filter(self, client):
        """按状态过滤"""
        client.post(
            "/api/v1/annotations/tasks",
            json={"case_id": "c1", "evaluator_type": "ragas"},
        )
        response = client.get("/api/v1/annotations/tasks?status=pending")
        assert response.status_code == 200

    def test_get_task_not_found(self, client):
        """查询不存在任务 - 404"""
        response = client.get("/api/v1/annotations/tasks/99999")
        assert response.status_code == 404

    def test_get_task_with_results(self, client):
        """查询任务详情（含结果）"""
        # 创建任务
        create_resp = client.post(
            "/api/v1/annotations/tasks",
            json={"case_id": "c1", "evaluator_type": "ragas"},
        )
        task_id = create_resp.json()["data"]["id"]

        # 提交结果
        client.post(
            f"/api/v1/annotations/tasks/{task_id}/results",
            json={"annotator_id": "ann_1", "score": 0.85, "comment": "good"},
        )

        # 查询详情
        response = client.get(f"/api/v1/annotations/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["results"]) == 1
        assert data["results"][0]["score"] == 0.85

    def test_update_task_status_invalid(self, client):
        """更新任务状态 - 422 Pydantic 验证错误（pattern 不匹配）"""
        create_resp = client.post(
            "/api/v1/annotations/tasks",
            json={"case_id": "c1", "evaluator_type": "ragas"},
        )
        task_id = create_resp.json()["data"]["id"]

        response = client.patch(
            f"/api/v1/annotations/tasks/{task_id}/status",
            json={"status": "invalid_state"},
        )
        # Pydantic 校验在 service 之前拦截，返回 422
        assert response.status_code == 422

    def test_update_task_status_success(self, client):
        """更新任务状态 - 200 成功"""
        create_resp = client.post(
            "/api/v1/annotations/tasks",
            json={"case_id": "c1", "evaluator_type": "ragas"},
        )
        task_id = create_resp.json()["data"]["id"]

        response = client.patch(
            f"/api/v1/annotations/tasks/{task_id}/status",
            json={"status": "cancelled"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "cancelled"


# ==================== 标注提交端点测试 ====================


class TestAnnotationResultEndpoints:
    """标注提交端点测试"""

    def test_submit_result_success(self, client):
        """提交标注 - 200 成功"""
        create_resp = client.post(
            "/api/v1/annotations/tasks",
            json={"case_id": "c1", "evaluator_type": "ragas"},
        )
        task_id = create_resp.json()["data"]["id"]

        response = client.post(
            f"/api/v1/annotations/tasks/{task_id}/results",
            json={"annotator_id": "ann_1", "score": 0.9, "comment": "准确"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["score"] == 0.9
        assert data["annotator_id"] == "ann_1"

    def test_submit_duplicate_annotator_returns_409(self, client):
        """同一标注员重复标注 - 409 Conflict"""
        create_resp = client.post(
            "/api/v1/annotations/tasks",
            json={"case_id": "c1", "evaluator_type": "ragas"},
        )
        task_id = create_resp.json()["data"]["id"]

        client.post(
            f"/api/v1/annotations/tasks/{task_id}/results",
            json={"annotator_id": "ann_1", "score": 0.9},
        )
        # 重复提交
        response = client.post(
            f"/api/v1/annotations/tasks/{task_id}/results",
            json={"annotator_id": "ann_1", "score": 0.8},
        )
        assert response.status_code == 409

    def test_submit_invalid_score_returns_422(self, client):
        """非法分数 - 422 验证错误"""
        create_resp = client.post(
            "/api/v1/annotations/tasks",
            json={"case_id": "c1", "evaluator_type": "ragas"},
        )
        task_id = create_resp.json()["data"]["id"]

        response = client.post(
            f"/api/v1/annotations/tasks/{task_id}/results",
            json={"annotator_id": "ann_1", "score": 1.5},  # 超出范围
        )
        assert response.status_code == 422

    def test_submit_to_nonexistent_task_returns_404(self, client):
        """向不存在任务提交 - 404"""
        response = client.post(
            "/api/v1/annotations/tasks/99999/results",
            json={"annotator_id": "ann_1", "score": 0.5},
        )
        assert response.status_code == 404

    def test_submit_with_dimensions(self, client):
        """带多维度评分"""
        create_resp = client.post(
            "/api/v1/annotations/tasks",
            json={"case_id": "c1", "evaluator_type": "ragas"},
        )
        task_id = create_resp.json()["data"]["id"]

        response = client.post(
            f"/api/v1/annotations/tasks/{task_id}/results",
            json={
                "annotator_id": "ann_1",
                "score": 0.85,
                "dimensions": {"准确性": 0.9, "安全性": 0.95},
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["dimensions"]["准确性"] == 0.9

    def test_submit_invalid_dimensions_returns_422(self, client):
        """非法维度分数 - 422"""
        create_resp = client.post(
            "/api/v1/annotations/tasks",
            json={"case_id": "c1", "evaluator_type": "ragas"},
        )
        task_id = create_resp.json()["data"]["id"]

        response = client.post(
            f"/api/v1/annotations/tasks/{task_id}/results",
            json={
                "annotator_id": "ann_1",
                "score": 0.85,
                "dimensions": {"bad": 1.5},  # 超出范围
            },
        )
        assert response.status_code == 422


# ==================== 审核端点测试 ====================


class TestReviewEndpoint:
    """审核端点测试"""

    def test_review_result_success(self, client):
        """审核结果 - 200"""
        create_resp = client.post(
            "/api/v1/annotations/tasks",
            json={"case_id": "c1", "evaluator_type": "ragas"},
        )
        task_id = create_resp.json()["data"]["id"]
        submit_resp = client.post(
            f"/api/v1/annotations/tasks/{task_id}/results",
            json={"annotator_id": "ann_1", "score": 0.8},
        )
        result_id = submit_resp.json()["data"]["id"]

        response = client.post(
            f"/api/v1/annotations/results/{result_id}/review",
            json={"reviewer_id": "rev_1", "review_comment": "通过", "is_valid": True},
        )
        assert response.status_code == 200
        assert response.json()["data"]["is_valid"] is True

    def test_review_nonexistent_result_returns_404(self, client):
        """审核不存在结果 - 404"""
        response = client.post(
            "/api/v1/annotations/results/99999/review",
            json={"reviewer_id": "rev_1", "is_valid": True},
        )
        assert response.status_code == 404


# ==================== 黄金样本端点测试 ====================


class TestGoldenSampleEndpoint:
    """黄金样本端点测试"""

    def test_submit_golden_sample_passes(self, client):
        """黄金样本通过"""
        create_resp = client.post(
            "/api/v1/annotations/tasks",
            json={"case_id": "golden_1", "evaluator_type": "ragas", "expected_output": "0.9"},
        )
        task_id = create_resp.json()["data"]["id"]

        response = client.post(
            f"/api/v1/annotations/tasks/{task_id}/golden",
            json={"annotator_id": "ann_1", "score": 0.9},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["pass"] is True
        assert data["needs_retraining"] is False

    def test_submit_golden_sample_fails(self, client):
        """黄金样本失败（偏差过大）"""
        create_resp = client.post(
            "/api/v1/annotations/tasks",
            json={"case_id": "golden_2", "evaluator_type": "ragas", "expected_output": "0.9"},
        )
        task_id = create_resp.json()["data"]["id"]

        response = client.post(
            f"/api/v1/annotations/tasks/{task_id}/golden",
            json={"annotator_id": "ann_1", "score": 0.3},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["pass"] is False
        assert data["needs_retraining"] is True


# ==================== 一致性端点测试 ====================


class TestAgreementEndpoint:
    """一致性端点测试"""

    def test_agreement_no_data(self, client):
        """无数据时返回说明"""
        response = client.get("/api/v1/annotations/agreement/nonexistent_type")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["sample_size"] == 0

    def test_agreement_with_data(self, client):
        """有数据时计算一致性"""
        # 创建并完成 5 个任务（每个 2 标注员）
        for i in range(5):
            create_resp = client.post(
                "/api/v1/annotations/tasks",
                json={"case_id": f"c{i}", "evaluator_type": "ragas", "required_annotators": 2},
            )
            task_id = create_resp.json()["data"]["id"]
            client.post(
                f"/api/v1/annotations/tasks/{task_id}/results",
                json={"annotator_id": "ann_1", "score": 0.7 + i * 0.05},
            )
            client.post(
                f"/api/v1/annotations/tasks/{task_id}/results",
                json={"annotator_id": "ann_2", "score": 0.75 + i * 0.04},
            )

        response = client.get("/api/v1/annotations/agreement/ragas")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data is not None
        assert 0.0 <= data["kappa_score"] <= 1.0
        assert data["agreement_level"] in {
            "poor",
            "fair",
            "moderate",
            "substantial",
            "almost_perfect",
        }


# ==================== 标注员绩效端点测试 ====================


class TestAnnotatorStatsEndpoint:
    """标注员绩效端点测试"""

    def test_stats_for_active_annotator(self, client):
        """活跃标注员统计"""
        for i in range(3):
            create_resp = client.post(
                "/api/v1/annotations/tasks",
                json={"case_id": f"c{i}", "evaluator_type": "ragas"},
            )
            task_id = create_resp.json()["data"]["id"]
            client.post(
                f"/api/v1/annotations/tasks/{task_id}/results",
                json={"annotator_id": "ann_1", "score": 0.7 + i * 0.1, "time_spent_seconds": 60},
            )

        response = client.get("/api/v1/annotations/annotators/ann_1/stats")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_annotations"] == 3
        assert 0.7 < data["avg_score"] < 0.9
        assert data["avg_time_seconds"] == 60.0

    def test_stats_for_nonexistent_annotator(self, client):
        """不存在的标注员 - 返回空统计"""
        response = client.get("/api/v1/annotations/annotators/nonexistent/stats")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_annotations"] == 0
