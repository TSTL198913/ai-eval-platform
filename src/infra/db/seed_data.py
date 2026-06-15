import random

from src.infra.db.models import EvaluationResultModel
from src.infra.db.session import SessionLocal


def seed_db():
    """生成测试种子数据（非安全用途）"""
    with SessionLocal() as db:
        for i in range(10):
            record = EvaluationResultModel(
                case_id=f"CASE_{i}",
                status=random.choice(["PASSED", "FAILED"]),  # nosec B311 - 测试数据生成，非安全用途
                latency_ms=random.uniform(100.0, 1000.0),  # nosec B311 - 测试数据生成，非安全用途
                model_name="deepseek-chat",
            )
            db.add(record)
        db.commit()
    print("已成功插入 10 条模拟评测记录。")


if __name__ == "__main__":
    seed_db()
