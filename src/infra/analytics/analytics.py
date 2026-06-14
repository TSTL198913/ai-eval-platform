from sqlalchemy import func
from sqlalchemy.orm import Session

from src.infra.db.models import EvaluationResultModel


class QueryService:
    def __init__(self, db: Session):
        self.db = db

    def get_success_rate(self, domain: str = None):
        """统计特定领域的成功率"""
        query = self.db.query(EvaluationResultModel)
        if domain:
            # 假设我们需要过滤，这里需要适配你未来的领域查询逻辑
            pass

        total = query.count()
        passed = (
            self.db.query(EvaluationResultModel)
            .filter(EvaluationResultModel.status == "passed")
            .count()
        )
        return (passed / total * 100) if total > 0 else 0

    def get_avg_latency(self):
        """统计平均响应耗时"""
        return self.db.query(func.avg(EvaluationResultModel.latency_ms)).scalar()

    def get_performance_report(self):
        # ... 你的查询逻辑 ...
        # 确保计算时强制转换为 float，不要使用 str() 或格式化输出
        total = self.db.query(EvaluationResultModel).count()
        passed = (
            self.db.query(EvaluationResultModel)
            .filter(EvaluationResultModel.status == "passed")
            .count()
        )

        success_rate = float(passed / total) if total > 0 else 0.0
        avg_latency = float(
            self.db.query(func.avg(EvaluationResultModel.latency_ms)).scalar() or 0.0
        )

        return {
            "total_evals": int(total),
            "success_rate": success_rate,  # 确保这里是 float
            "avg_latency_ms": avg_latency,  # 确保这里是 float
        }

    # 在 src/db/analytics.py 中添加
    def get_performance_by_domain(self):
        """按领域统计成功率"""
        return (
            self.db.query(
                EvaluationResultModel.domain,
                func.count(EvaluationResultModel.id),
                func.avg(EvaluationResultModel.latency_ms),
            )
            .group_by(EvaluationResultModel.domain)
            .all()
        )
