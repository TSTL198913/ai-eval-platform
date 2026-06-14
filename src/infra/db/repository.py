from abc import ABC, abstractmethod

from src.infra.db.models import EvaluationResultModel
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
        # 1. 安全校验：防止漏掉关键键
        if not result.case_id:
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
            session.flush()          # 刷新以获取数据库生成的自增 ID (id)
            session.commit()         # 显式提交事务
            return db_record.id

# 3. 如果你的旧测试还需要原 SQLiteRepository，可以暂时保留在这里做兼容
class SQLiteRepository(BaseRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def save(self, result: EvaluationResult) -> int:
        print(f"【测试模拟】数据已持久化至 SQLite: {result.case_id}")
        return 0
