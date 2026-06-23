"""
Workers模块专项测试
测试目标：验证Worker模块的核心功能
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.workers.monitor_queue import check_backlog


class TestMonitorQueue:
    """MonitorQueue队列监控测试"""

    def test_check_backlog_normal(self):
        """队列正常时应输出正常信息"""
        with patch("src.workers.monitor_queue.redis.Redis") as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            mock_client.llen.return_value = 500

            with patch("builtins.print") as mock_print:
                check_backlog()

                mock_print.assert_called_once()
                assert "正常" in mock_print.call_args[0][0]

    def test_check_backlog_high(self):
        """队列积压严重时应输出警告"""
        with patch("src.workers.monitor_queue.redis.Redis") as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            mock_client.llen.return_value = 1500

            with patch("builtins.print") as mock_print:
                check_backlog()

                mock_print.assert_called_once()
                assert "警告" in mock_print.call_args[0][0]
                assert "1500" in mock_print.call_args[0][0]

    def test_check_backlog_with_custom_params(self):
        """使用自定义参数连接Redis"""
        with patch("src.workers.monitor_queue.redis.Redis") as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            mock_client.llen.return_value = 100

            with patch("builtins.print"):
                check_backlog(host="127.0.0.1", port=6380, db=1)

            mock_redis.assert_called_with(host="127.0.0.1", port=6380, db=1)
