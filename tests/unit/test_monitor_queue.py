"""测试 workers/monitor_queue.py"""

from unittest.mock import Mock, patch


class TestMonitorQueue:
    """测试队列监控模块"""

    @patch("src.workers.monitor_queue.redis.Redis")
    def test_check_backlog_low(self, mock_redis):
        from src.workers.monitor_queue import check_backlog

        mock_r = Mock()
        mock_redis.return_value = mock_r
        mock_r.llen.return_value = 500

        check_backlog()
        mock_r.llen.assert_called_once_with("celery")

    @patch("src.workers.monitor_queue.redis.Redis")
    def test_check_backlog_high(self, mock_redis):
        from src.workers.monitor_queue import check_backlog

        mock_r = Mock()
        mock_redis.return_value = mock_r
        mock_r.llen.return_value = 1500

        check_backlog()
        mock_r.llen.assert_called_once_with("celery")
