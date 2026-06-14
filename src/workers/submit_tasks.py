import os
import sys

# 获取当前脚本所在目录的父目录（即根目录）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workers.tasks import eval_case_task

# 批量提交 10 个任务到队列
for i in range(10):
    eval_case_task.delay({"id": f"TASK_{i}"})
    print(f"任务 {i} 已提交至队列")
