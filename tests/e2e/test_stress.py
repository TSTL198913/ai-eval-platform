import os
import sys
import time
from datetime import datetime

# 1. 动态添加路径，确保正确定位到 src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# 2. 闭环核心：引入系统统一的数据契约
from src.schemas.evaluation import EvaluationSchema  # noqa: E402
from src.workers.tasks import eval_case_task  # noqa: E402


def run_stress_test(task_count=100):
    print(
        f"[{datetime.now()}] 🚀 开始全链路闭环压测：提交 {task_count} 个标准契约任务..."
    )
    start_time = time.time()

    for i in range(task_count):
        # 交替测试 text 和 code 等已注册的领域算子
        eval_type = "text" if i % 2 == 0 else "code"

        # 3. 放弃原本盲目造数据的 EvalCaseModel
        # 4. 直接使用标准 EvaluationSchema 构造强类型对象，确保源头数据 100% 合规
        mock_schema_obj = EvaluationSchema(
            id=f"STRESS_TEST_{i}_{int(time.time())}",
            type=eval_type,
            payload={
                "case_id": f"c_{i}",
                "user_input": f"高并发测试输入 - 编号 {i}",
                "domain": eval_type,
            },
            metadata={"batch": "stress_2026_06"},
        )

        # 5. 将 Pydantic 对象序列化为 dict 灌入 Celery 异步队列
        # 这保证了传给 eval_case_task.delay 的每一条数据，都在出厂前通过了安全整形
        eval_case_task.delay(mock_schema_obj.model_dump())

    end_time = time.time()
    total_duration = end_time - start_time
    tps = task_count / total_duration

    print(f"[{datetime.now()}] ✅ 强契约任务全部安全提交！")
    print("--- 压测统计 ---")
    print(f"总提交任务数: {task_count}")
    print(f"提交总耗时: {total_duration:.2f} 秒")
    print(f"提交吞吐量 (TPS): {tps:.2f} 任务/秒")
    print("建议：请观察 watcher.log 查看 Worker 的消费速度。")


if __name__ == "__main__":
    run_stress_test(100)
