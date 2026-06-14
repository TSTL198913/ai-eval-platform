import os
import sys
import time
from datetime import datetime

# 注入项目根目录
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.infra.db.models import EvaluationResultModel
from src.workers.tasks import buffer_service


def stress_test_25m():
    TOTAL_COUNT = 25_000_000
    BATCH_SIZE = 100_000  # 压测脚本采用 10 万作为提交批次

    print(f"[{datetime.now()}] 🚀 开始 2500 万条数据抗压测试")
    start_time = time.time()

    for i in range(0, TOTAL_COUNT, BATCH_SIZE):
        # 批量构建数据
        results = [EvaluationResultModel(case_id=f"T_{i + j}", status=1) for j in range(BATCH_SIZE)]

        # 直接调用底层的 engine 模拟高性能写入
        buffer_service.buffer.extend(results)
        buffer_service.flush()

        if (i + BATCH_SIZE) % 1_000_000 == 0:
            elapsed = time.time() - start_time
            print(
                f"✅ 已完成: {i + BATCH_SIZE} 条 | 累计耗时: {elapsed:.2f}s | 预估剩余: {((TOTAL_COUNT - (i + BATCH_SIZE)) / (i + BATCH_SIZE) * elapsed):.2f}s"
            )

    print(f"🏁 测试完成！总耗时: {time.time() - start_time:.2f} 秒")


if __name__ == "__main__":
    stress_test_25m()
