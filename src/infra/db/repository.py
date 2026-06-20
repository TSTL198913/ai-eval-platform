from abc import ABC, abstractmethod

from sqlalchemy import bindparam, text

from src.exceptions import InfrastructureError
from src.infra.db.models import EvaluationResultModel, TrajectoryModel
from src.infra.db.session import get_db_session
from src.schemas.schemas import EvaluationResult


# 1. 统一的仓储基类（规范接口）
class BaseRepository(ABC):
    @abstractmethod
    def save(self, result: EvaluationResult) -> int:
        """持久化评估结果，返回入库后的自增 ID"""
        pass


# 2. 完美的工业级 Postgres/SQLAlchemy 仓储实现
class EvaluationRepository(BaseRepository):
    def save(self, result: EvaluationResult) -> int:
        if not result.case_id or not result.case_id.strip():
            raise InfrastructureError("持久化失败：评估结果缺少核心 case_id")

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
            result = session.execute(text("SELECT COUNT(*) FROM eval_results")).fetchone()
            return result[0] if result else 0

    def get_recent(self, limit: int = 10) -> list[dict]:
        """获取最近的评估记录"""
        with get_db_session() as session:
            results = session.execute(
                text(
                    """
                    SELECT id, case_id, model_name, adapter_name, status, latency_ms, created_at
                    FROM eval_results
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
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
                    "created_at": row[6].isoformat() if row[6] and hasattr(row[6], 'isoformat') else row[6],
                }
                for row in results
            ]

    def search(
        self,
        evaluator: str | None = None,
        status: str | None = None,
        limit: int = 10,
        type: str | None = None,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[dict]:
        """搜索评估记录，支持按评估器类型和状态过滤"""
        with get_db_session() as session:
            query_parts = [
                "SELECT id, case_id, model_name, adapter_name, status, latency_ms, created_at",
                "FROM eval_results",
                "WHERE 1=1",
            ]
            params = {}

            if evaluator:
                query_parts.append("AND adapter_name = :evaluator")
                params["evaluator"] = evaluator
            elif type:
                query_parts.append("AND adapter_name = :type")
                params["type"] = type

            if status:
                query_parts.append("AND status = :status")
                params["status"] = status

            allowed_sort_fields = ["id", "case_id", "model_name", "adapter_name", "status", "latency_ms", "created_at"]
            if sort_by not in allowed_sort_fields:
                sort_by = "created_at"

            sort_order = sort_order.upper()
            if sort_order not in ["ASC", "DESC"]:
                sort_order = "DESC"

            query_parts.append(f"ORDER BY {sort_by} {sort_order}")
            query_parts.append("LIMIT :limit OFFSET :offset")
            params["limit"] = limit
            params["offset"] = offset

            results = session.execute(text(" ".join(query_parts)), params).fetchall()

            return [
                {
                    "id": row[0],
                    "case_id": row[1],
                    "model_name": row[2],
                    "adapter_name": row[3],
                    "status": row[4],
                    "latency_ms": row[5],
                    "created_at": row[6].isoformat() if row[6] and hasattr(row[6], 'isoformat') else row[6],
                }
                for row in results
            ]

    def get_by_id(self, record_id: int) -> dict | None:
        """根据ID获取评估记录详情"""
        with get_db_session() as session:
            result = session.execute(
                text(
                    """
                    SELECT id, case_id, model_name, adapter_name, status, latency_ms, response_data, created_at
                    FROM eval_results
                    WHERE id = :id
                    """
                ),
                {"id": record_id},
            ).fetchone()

            if result:
                return {
                    "id": result[0],
                    "case_id": result[1],
                    "model_name": result[2],
                    "adapter_name": result[3],
                    "status": result[4],
                    "latency_ms": result[5],
                    "response_data": result[6],
                    "created_at": result[7].isoformat() if result[7] and hasattr(result[7], 'isoformat') else result[7],
                }
            return None

    def update(self, record_id: int, update_data: dict) -> bool:
        """更新评估记录"""
        with get_db_session() as session:
            allowed_fields = ["model_name", "adapter_name", "status"]
            set_parts = []
            params = {"id": record_id}

            for field in allowed_fields:
                if field in update_data:
                    set_parts.append(f"{field} = :{field}")
                    params[field] = update_data[field]

            if not set_parts:
                return False

            query = f"UPDATE eval_results SET {', '.join(set_parts)} WHERE id = :id"
            result = session.execute(text(query), params)
            session.commit()
            return result.rowcount > 0

    def delete(self, record_id: int) -> bool:
        """删除评估记录"""
        with get_db_session() as session:
            result = session.execute(
                text("DELETE FROM eval_results WHERE id = :id"),
                {"id": record_id},
            )
            session.commit()
            return result.rowcount > 0

    def batch_delete(self, record_ids: list[int]) -> int:
        """批量删除评估记录"""
        if not record_ids:
            return 0
        with get_db_session() as session:
            result = session.execute(
                text("DELETE FROM eval_results WHERE id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": list(record_ids)}
            )
            session.commit()
            return result.rowcount

    def batch_update(self, record_ids: list[int], update_data: dict) -> int:
        """批量更新评估记录"""
        if not record_ids or not update_data:
            return 0
        with get_db_session() as session:
            allowed_fields = ["model_name", "adapter_name", "status"]
            set_parts = []
            params = {"ids": list(record_ids)}

            for field in allowed_fields:
                if field in update_data:
                    set_parts.append(f"{field} = :{field}")
                    params[field] = update_data[field]

            if not set_parts:
                return 0

            query = text(f"UPDATE eval_results SET {', '.join(set_parts)} WHERE id IN :ids").bindparams(
                bindparam("ids", expanding=True)
            )
            result = session.execute(query, params)
            session.commit()
            return result.rowcount

    def create(self, data: dict) -> int:
        """创建评估记录（用于配置管理等场景）"""
        import json
        with get_db_session() as session:
            response_data = data.get("response_data", {})
            # 确保response_data是字典或可JSON序列化的
            if not isinstance(response_data, dict):
                try:
                    response_data = json.loads(str(response_data))
                except Exception:
                    response_data = {}

            record = EvaluationResultModel(
                case_id=data.get("case_id", ""),
                model_name=data.get("model_name", "default"),
                adapter_name=data.get("adapter_name", "default"),
                status=data.get("status", "unknown"),
                latency_ms=float(data.get("latency_ms", 0.0)),
                response_data=response_data,
            )
            session.add(record)
            session.flush()
            session.commit()
            return record.id

    def get_all(self, limit: int = 100) -> list[dict]:
        """获取所有评估记录"""
        import json
        with get_db_session() as session:
            results = session.execute(
                text(
                    """
                    SELECT id, case_id, model_name, adapter_name, status, latency_ms, response_data, created_at
                    FROM eval_results
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).fetchall()

            records = []
            for row in results:
                response_data = row[6]
                # 如果是字符串，尝试解析为JSON
                if isinstance(response_data, str):
                    try:
                        response_data = json.loads(response_data)
                    except Exception:
                        pass
                records.append({
                    "id": row[0],
                    "case_id": row[1],
                    "model_name": row[2],
                    "adapter_name": row[3],
                    "status": row[4],
                    "latency_ms": row[5],
                    "response_data": response_data,
                    "created_at": row[7].isoformat() if row[7] and hasattr(row[7], 'isoformat') else row[7],
                })
            return records

    def get_all_for_export(self) -> list[dict]:
        """获取所有评估记录用于导出"""
        with get_db_session() as session:
            results = session.execute(
                text(
                    """
                    SELECT id, case_id, model_name, adapter_name, status, latency_ms, response_data, created_at
                    FROM eval_results
                    ORDER BY created_at DESC
                    """
                )
            ).fetchall()

            return [
                {
                    "id": row[0],
                    "case_id": row[1],
                    "model_name": row[2],
                    "adapter_name": row[3],
                    "status": row[4],
                    "latency_ms": row[5],
                    "response_data": row[6],
                    "created_at": row[7].isoformat() if row[7] and hasattr(row[7], 'isoformat') else row[7],
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
        tool_name: str | None = None,
        tool_params: dict[str, object] | None = None,
        is_correct: bool = False,
    ) -> int:
        if not task_id or not task_id.strip():
            raise InfrastructureError("持久化失败：轨迹缺少核心 task_id")

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

    def save_steps(self, steps: list[dict[str, object]]) -> list[int]:
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

    def get_trajectory(self, task_id: str) -> list[dict[str, object]]:
        with get_db_session() as session:
            results = session.query(TrajectoryModel)\
                .filter(TrajectoryModel.task_id == task_id)\
                .order_by(TrajectoryModel.step_index)\
                .all()
            return [result.to_dict() for result in results]

    def get_recent_trajectories(self, limit: int = 10) -> list[dict[str, object]]:
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
            result = session.execute(text("SELECT COUNT(*) FROM trajectories")).fetchone()
            return result[0] if result else 0
