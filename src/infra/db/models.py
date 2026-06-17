from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String

from src.infra.db.session import Base

# 统一引入 infra 层定义的 Base，彻底解决循环依赖和警告


class EvaluationResultModel(Base):
    __tablename__ = "eval_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(50), nullable=False)
    model_name = Column(String(50))
    adapter_name = Column(String(50))
    status = Column(String(20))
    latency_ms = Column(Float)
    # JSON 类型在 PostgreSQL 中会自动映射为 JSONB，无需额外配置
    response_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        """
        建议：to_dict 方法最好保留在 Infra 层或 Model 自身中，
        注意这里的 'response' 字段引用，确保逻辑与你的业务字段一致
        """
        return {
            "id": self.id,
            "case_id": self.case_id,
            "status": self.status,
            "response_data": self.response_data,
        }


class TrajectoryModel(Base):
    __tablename__ = "trajectories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(50), nullable=False)
    step_index = Column(Integer, nullable=False)
    step_type = Column(String(30))
    prompt = Column(String(5000))
    response = Column(String(5000))
    tool_name = Column(String(100))
    tool_params = Column(JSON)
    is_correct = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "step_index": self.step_index,
            "step_type": self.step_type,
            "prompt": self.prompt,
            "response": self.response,
            "tool_name": self.tool_name,
            "tool_params": self.tool_params,
            "is_correct": bool(self.is_correct),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
