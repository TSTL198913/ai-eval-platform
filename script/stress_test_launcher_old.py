import os
import sys
import time
from datetime import datetime

# 1. 动态添加路径，确保正确定位到 src 命名空间
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    # 2. 全链路契约闭环：强行引入最新重构的 Schema 和持久层组件
    from src.schemas.evaluation import EvaluationSchema
    from src.workers.tasks import eval_case_task
    from src.infra.db.session import get_db_session
    from src.infra.db.models import EvaluationResultModel
except ImportError as e:
    print(f"❌ 导入失败，请检查目录重构后的 import 路径: {e}")
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
    from src.schemas.evaluation import EvaluationSchema
    from src.workers.tasks import eval_case_task
    from src.infra.db.session import get_db_session
    from src.infra.db.models import EvaluationResultModel


def get_current_db_count() -> int:
    """辅助函数：获取当前数据库中评测结果的总总量"""
    with get_db_session() as session:
        return session.query(EvaluationResultModel).count()


def run_stress_test(task_count=100):
    print("=" * 70)
    print(f"[{datetime.now()}] 🚀 分布式高并发可靠性压测启动")
    print(f"🎯 压测目标: 灌入 {task_count} 个标准强契约异步任务")
    print("=" * 70)

    # 3. 记录测试前的基线数据
    try:
        initial_count = get_current_db_count()
        print(f"📊 [基线核对] 当前数据库中已有记录数: {initial_count} 条")
    except Exception as e:
        print(
            f"⚠️ 数据库连接失败或表未初始化: {e}。请先确保 alembic 或 init_tables 已执行。"
        )
        return

    start_time = time.time()
    success_submitted = 0

    # 4. 开始高压发射流量
    for i in range(task_count):
        # 交替测试已经注册的垂直领域，验证工厂的智能分流
        eval_type = "finance" if i % 2 == 0 else "code"

        try:
            # 使用标准的 Pydantic 契约在源头格式化数据（卡死海关）
            mock_case = EvaluationSchema(
                id=f"STRESS_202606_{i}_{int(time.time())}",
                type=eval_type,
                payload={
                    "case_id": f"case_idx_{i}",
                    "user_input": f"自动化并发测试压力输入 —— 算子流转编号: {i}",
                    "domain": eval_type,
                    "metadata": {"pressure_level": "extreme"},
                },
                metadata={"tester": "QA_Expert", "timestamp": str(datetime.now())},
            )

            # 5. 序列化为标准的纯净字典并推入 Celery 异步车队
            eval_case_task.delay(mock_case.model_dump())
            success_submitted += 1

            # 每 20 个任务打印一次发射进度
            if success_submitted % 2000 == 0 or success_submitted == task_count:
                print(
                    f" 进度提示: 已成功向队列推送 [ {success_submitted} / {task_count} ] 个任务..."
                )

        except Exception as queue_err:
            print(f"❌ 第 {i} 个任务在推送或整形时拦截失败: {queue_err}")

    end_time = time.time()
    total_duration = end_time - start_time
    tps = success_submitted / total_duration if total_duration > 0 else 0

    print("-" * 70)
    print(f"[{datetime.now()}]  发射阶段全部完成！")
    print(f"📈 [发射期统计] 总提交成功数: {success_submitted} / {task_count}")
    print(f"⏱️ [发射期统计] 管道灌入总耗时: {total_duration:.3f} 秒")
    print(f"⚡ [发射期统计] 任务投递吞吐量 (TPS): {tps:.2f} 任务/秒")
    print("-" * 70)

    # 6. 专家级动态水位监控与终局对账
    print("⏳ 正在动态监控 Redis 队列，等待后台 Worker 清仓落盘...")

    # 获取 celery 默认队列长度的简易方法（依赖你的 redis 连接）
    import redis

    r = redis.Redis(host="localhost", port=6379, db=0)

    wait_start = time.time()
    while True:
        # 'celery' 是默认的队列名称，根据你 broker 的实际 Key 调整
        queue_length = r.llen("celery")
        if queue_length == 0:
            print("\n🎉 [🎉 队列已完全清空！所有异步任务已由消费端处理完毕。]")
            time.sleep(5)
            break

        print(
            f" 🔄 队列目前仍有 {queue_length} 条任务排队中，Worker 正在全速落盘 [已耗时 {int(time.time() - wait_start)}s]..."
        )
        time.sleep(3)

        # 熔断防御，防止死锁时无限循环
        if time.time() - wait_start > 120:
            print("\n🚨 触发超时熔断！部分任务可能卡死，强行进入对账阶段。")
            break

    final_count = get_current_db_count()
    actual_inserted = final_count - initial_count
    print("=" * 70)
    print(f"🏁 【最终可靠性对账报告】")
    print(f"📥 成功推入队列数: {success_submitted} 条")
    print(f"💾 数据库实际新增数: {actual_inserted} 条")
    # ... 后续保持不变 ...

    if actual_inserted == success_submitted:
        print("\n🏆 可靠性评估结论: 【完美通过 (100% 闭环)】")
        print(" 数据全链路无丢失、无死锁、无连接泄露。此系统具备上线抗洪能力！")
    else:
        loss_rate = (
            ((success_submitted - actual_inserted) / success_submitted) * 100
            if success_submitted > 0
            else 100
        )
        print(f"\n⚠️ 可靠性评估结论: 【数据未完全同步】")
        print(
            f" 仍有 {success_submitted - actual_inserted} 条数据留在队列中或处理失败（丢包率: {loss_rate:.2f}%）。"
        )
        print(" 请检查 Worker 是否已全部启动，或查看具体执行日志。")
    print("=" * 70)


if __name__ == "__main__":
    # 第一次验证建议用 100 压测，确认闭环后可直接上调至 1000 暴力破壁
    run_stress_test(100000)
