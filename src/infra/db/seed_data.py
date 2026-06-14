import random

from infra.db.models import EvaluationResultModel
from infra.db.session import SessionLocal


def seed_db():
    with SessionLocal() as db:
        for i in range(10):
            record = EvaluationResultModel(
                case_id=f"CASE_{i}",
                status=random.choice(["PASSED", "FAILED"]),
                latency_ms=random.uniform(100.0, 1000.0),
                model_name="deepseek-chat",
            )
            db.add(record)
        db.commit()
    print("已成功插入 10 条模拟评测记录。")


if __name__ == "__main__":
    seed_db()
