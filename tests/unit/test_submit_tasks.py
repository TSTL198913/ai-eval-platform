"""测试 workers/submit_tasks.py"""

from unittest.mock import Mock, patch

import pytest


class TestSubmitTasks:
    """测试任务提交模块"""

    @patch("src.workers.submit_tasks.eval_case_task")
    def test_submit_batch_tasks(self, mock_task):
        from src.workers.submit_tasks import submit_batch_tasks

        mock_task.delay.return_value = Mock()

        submit_batch_tasks(count=5)
        assert mock_task.delay.call_count == 5
