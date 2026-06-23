from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

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
    score = Column(Float, nullable=True)
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


# ==================== 🏷️ 人工标注数据模型（2026 工业级） ====================


class AnnotationTaskModel(Base):
    """标注任务表 - 存储需要人工标注的评估用例"""

    __tablename__ = "annotation_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(100), nullable=False, index=True, comment="评估用例ID")
    evaluator_type = Column(String(50), nullable=False, index=True, comment="关联的评估器类型")
    question = Column(Text, comment="待评估的问题")
    actual_output = Column(Text, comment="模型实际输出")
    expected_output = Column(Text, comment="期望输出（标准答案）")
    context = Column(Text, comment="上下文信息（可选）")
    metadata_json = Column("metadata", JSON, comment="扩展元数据")
    status = Column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
        comment="任务状态: pending / in_progress / completed / cancelled",
    )
    priority = Column(Integer, default=5, comment="优先级 1-10，数字越大越优先")
    required_annotators = Column(Integer, default=1, comment="需要的标注员数量（双盲标注）")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    due_at = Column(DateTime, comment="截止时间（可选）")

    # 关联
    results = relationship(
        "AnnotationResultModel", back_populates="task", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "case_id": self.case_id,
            "evaluator_type": self.evaluator_type,
            "question": self.question,
            "actual_output": self.actual_output,
            "expected_output": self.expected_output,
            "context": self.context,
            "metadata": self.metadata_json,
            "status": self.status,
            "priority": self.priority,
            "required_annotators": self.required_annotators,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "result_count": len(self.results) if self.results else 0,
        }


class AnnotationResultModel(Base):
    """标注结果表 - 存储每个标注员的具体评分与反馈"""

    __tablename__ = "annotation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(
        Integer,
        ForeignKey("annotation_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    annotator_id = Column(String(100), nullable=False, index=True, comment="标注员ID")
    annotator_name = Column(String(100), comment="标注员姓名")
    score = Column(Float, nullable=False, comment="标注分数 0.0 - 1.0")
    label = Column(String(50), comment="分类标签（可选，如 'good' / 'bad'）")
    comment = Column(Text, comment="标注员文字评论")
    tags = Column(JSON, comment="标签集合，如 ['安全', '流畅']")
    dimensions = Column(JSON, comment="多维度评分 {维度: 分数}")
    is_golden = Column(Boolean, default=False, comment="是否为黄金样本（用于标注员校准）")
    is_valid = Column(Boolean, default=True, comment="是否有效（审核后）")
    reviewer_id = Column(String(100), comment="审核员ID")
    review_comment = Column(Text, comment="审核评论")
    time_spent_seconds = Column(Integer, comment="标注耗时（秒）")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 关联
    task = relationship("AnnotationTaskModel", back_populates="results")

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "annotator_id": self.annotator_id,
            "annotator_name": self.annotator_name,
            "score": self.score,
            "label": self.label,
            "comment": self.comment,
            "tags": self.tags,
            "dimensions": self.dimensions,
            "is_golden": self.is_golden,
            "is_valid": self.is_valid,
            "reviewer_id": self.reviewer_id,
            "review_comment": self.review_comment,
            "time_spent_seconds": self.time_spent_seconds,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AnnotationAgreementModel(Base):
    """标注一致性统计表 - Cohen's Kappa / Fleiss' Kappa 等"""

    __tablename__ = "annotation_agreements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    evaluator_type = Column(String(50), nullable=False, index=True)
    sample_size = Column(Integer, nullable=False, comment="样本量")
    kappa_score = Column(Float, comment="Cohen's / Fleiss' Kappa 系数")
    agreement_level = Column(
        String(20), comment="一致性等级: poor / fair / moderate / substantial / almost_perfect"
    )
    annotator_count = Column(Integer, comment="参与标注的标注员数")
    metric_payload = Column(JSON, comment="原始统计指标")
    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "evaluator_type": self.evaluator_type,
            "sample_size": self.sample_size,
            "kappa_score": round(self.kappa_score, 4) if self.kappa_score else None,
            "agreement_level": self.agreement_level,
            "annotator_count": self.annotator_count,
            "metric_payload": self.metric_payload,
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
        }
