"""
SubmitTasks模块专项测试
测试目标：验证批量提交任务功能
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

os.environ["TESTING"] = "1"

from src.workers.submit_tasks import submit_batch_tasks


class TestSubmitTasks:
    """SubmitTasks测试"""

    def test_submit_batch_tasks_default(self):
        """使用默认参数提交任务"""
        with patch("src.workers.submit_tasks.eval_case_task") as mock_task:
            mock_task.delay.return_value = MagicMock()

            with patch("builtins.print") as mock_print:
                submit_batch_tasks()

                assert mock_task.delay.call_count == 10
                assert mock_print.call_count == 10

    def test_submit_batch_tasks_custom_count(self):
        """使用自定义数量提交任务"""
        with patch("src.workers.submit_tasks.eval_case_task") as mock_task:
            mock_task.delay.return_value = MagicMock()

            with patch("builtins.print") as mock_print:
                submit_batch_tasks(count=5)

                assert mock_task.delay.call_count == 5
                assert mock_print.call_count == 5
