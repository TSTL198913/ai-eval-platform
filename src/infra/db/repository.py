from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.infra.db.models import EvaluationResultModel, TrajectoryModel
from src.infra.db.session import get_db_session
from src.schemas.schemas import EvaluationResult  # 确保引入你的强类型契约


# 1. 统一的仓储基类（规范接口）
class BaseRepository(ABC):
    @abstractmethod
    def save(self, result: EvaluationResult) -> int:
        """持久化评估结果，返回入库后的自增 ID"""
        pass


# 2. 完美的工业级 Postgres/SQLAlchemy 仓储实现
class EvaluationRepository(BaseRepository):
    def save(self, result: EvaluationResult) -> int:
        # 1. 安全校验：防止漏掉关键键（包括空白字符）
        if not result.case_id or not result.case_id.strip():
            raise ValueError("持久化失败：评估结果缺少核心 case_id")

        db_record = EvaluationResultModel(
            case_id=result.case_id,
            model_name=result.model_name or "default",
            adapter_name=result.adapter_name or "default",
            status=result.status.value,
            latency_ms=result.latency_ms or 0.0,
            response_data=result.response.model_dump() if result.response else {},
        )

        # 4. 使用全新的上下文管理器进行事务安全的持久化
        with get_db_session() as session:
            session.add(db_record)
            session.flush()  # 刷新以获取数据库生成的自增 ID (id)
            session.commit()  # 显式提交事务
            return db_record.id

    def count(self) -> int:
        """获取评估记录总数"""
        with get_db_session() as session:
            result = session.execute("SELECT COUNT(*) FROM eval_results").fetchone()
            return result[0] if result else 0

    def get_recent(self, limit: int = 10) -> list[dict]:
        """获取最近的评估记录"""
        with get_db_session() as session:
            results = session.execute(
                """
                SELECT id, case_id, model_name, adapter_name, status, latency_ms, created_at
                FROM eval_results
                ORDER BY created_at DESC
                LIMIT :limit
                """,
                {"limit": limit},
            ).fetchall()

            return [
                {
                    "id": row[0],
                    "case_id": row[1],
                    "model_name": row[2],
                    "adapter_name": row[3],
                    "status": row[4],
                    "latency_ms": row[5],
                    "created_at": row[6].isoformat() if row[6] else None,
                }
                for row in results
            ]

    def search(
        self,
        evaluator: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """搜索评估记录，支持按评估器类型和状态过滤"""
        with get_db_session() as session:
            query = """
                SELECT id, case_id, model_name, adapter_name, status, latency_ms, created_at
                FROM eval_results
                WHERE 1=1
            """
            params = {}

            if evaluator:
                query += " AND adapter_name = :evaluator"
                params["evaluator"] = evaluator

            if status:
                query += " AND status = :status"
                params["status"] = status

            query += " ORDER BY created_at DESC LIMIT :limit"
            params["limit"] = limit

            results = session.execute(query, params).fetchall()

            return [
                {
                    "id": row[0],
                    "case_id": row[1],
                    "model_name": row[2],
                    "adapter_name": row[3],
                    "status": row[4],
                    "latency_ms": row[5],
                    "created_at": row[6].isoformat() if row[6] else None,
                }
                for row in results
            ]


# 3. 如果你的旧测试还需要原 SQLiteRepository，可以暂时保留在这里做兼容
class SQLiteRepository(BaseRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def save(self, result: EvaluationResult) -> int:
        print(f"【测试模拟】数据已持久化至 SQLite: {result.case_id}")
        return 0


class TrajectoryRepository:
    def save_step(
        self,
        task_id: str,
        step_index: int,
        step_type: str,
        prompt: str,
        response: str,
        tool_name: Optional[str] = None,
        tool_params: Optional[Dict[str, Any]] = None,
        is_correct: bool = False,
    ) -> int:
        if not task_id or not task_id.strip():
            raise ValueError("持久化失败：轨迹缺少核心 task_id")

        db_record = TrajectoryModel(
            task_id=task_id,
            step_index=step_index,
            step_type=step_type,
            prompt=prompt,
            response=response,
            tool_name=tool_name,
            tool_params=tool_params,
            is_correct=int(is_correct),
        )

        with get_db_session() as session:
            session.add(db_record)
            session.flush()
            session.commit()
            return db_record.id

    def save_steps(self, steps: List[Dict[str, Any]]) -> List[int]:
        ids = []
        for step in steps:
            step_id = self.save_step(
                task_id=step.get("task_id"),
                step_index=step.get("step_index"),
                step_type=step.get("step_type"),
                prompt=step.get("prompt"),
                response=step.get("response"),
                tool_name=step.get("tool_name"),
                tool_params=step.get("tool_params"),
                is_correct=step.get("is_correct", False),
            )
            ids.append(step_id)
        return ids

    def get_trajectory(self, task_id: str) -> List[Dict[str, Any]]:
        with get_db_session() as session:
            results = session.query(TrajectoryModel)\
                .filter(TrajectoryModel.task_id == task_id)\
                .order_by(TrajectoryModel.step_index)\
                .all()
            return [result.to_dict() for result in results]

    def get_recent_trajectories(self, limit: int = 10) -> List[Dict[str, Any]]:
        with get_db_session() as session:
            results = session.query(TrajectoryModel)\
                .order_by(TrajectoryModel.created_at.desc())\
                .limit(limit)\
                .all()
            return [result.to_dict() for result in results]

    def delete_trajectory(self, task_id: str) -> int:
        with get_db_session() as session:
            count = session.query(TrajectoryModel)\
                .filter(TrajectoryModel.task_id == task_id)\
                .delete()
            session.commit()
            return count

    def count(self) -> int:
        with get_db_session() as session:
            result = session.execute("SELECT COUNT(*) FROM trajectories").fetchone()
            return result[0] if result else 0
