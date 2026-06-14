import os
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.infra.db.models import EvaluationResultModel  # noqa: E402
from src.infra.db.session import SessionLocal  # noqa: E402
from src.workers.tasks import buffer_service  # noqa: E402


def clear_db():
    db = SessionLocal()
    db.query(EvaluationResultModel).delete()
    db.commit()
    db.close()


def visual_demo():
    print("--- 🚀 开始演示：高并发缓存与泄洪机制 ---")
    service = buffer_service
    service.buffer.clear()  # 确保缓冲区干净

    # 1. 模拟瞬间涌入 2500 个任务 (远超 Batch_size=1000)
    print("模拟涌入 2500 个任务...")
    for i in range(2500):
        service.add(EvaluationResultModel(case_id=f"TEST_{i}", status=1))

    print(f"当前缓存队列长度: {len(service.buffer)}")
    print("【观察点】：批量触发了 2 次自动 Flush (1000, 1000)，剩余 500 在缓存中。")

    # 2. 手动强制泄洪剩余的 500 个
    time.sleep(1)
    print("执行强制泄洪剩余数据...")
    service.flush()
    print("所有数据已完成落盘。")

    # 3. 结果核对
    db = SessionLocal()
    count = db.query(EvaluationResultModel).count()
    print(f"--- 🏁 数据库最终记录数: {count} ---")
    db.close()


if __name__ == "__main__":
    clear_db()
    visual_demo()
