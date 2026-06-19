"""
Celery队列监控脚本

功能：
1. 定期检查队列深度
2. 监控Worker状态
3. 推送指标到Pushgateway（可选）
4. 记录任务执行统计

使用方法：
    python -m src.infra.monitoring.monitor_celery

环境变量：
    CELERY_BROKER_URL: Celery broker地址
    PUSHGATEWAY_URL: Pushgateway地址（可选）
    MONITOR_INTERVAL: 监控间隔（秒），默认10
"""

import os
import sys
import time
import logging
import threading
from typing import Optional

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CeleryQueueMonitor:
    """Celery队列监控器"""

    def __init__(
        self,
        broker_url: Optional[str] = None,
        pushgateway_url: Optional[str] = None,
        interval: int = 10,
    ):
        self.broker_url = broker_url or os.getenv(
            "CELERY_BROKER_URL", "filesystem:///tmp/celery_broker"
        )
        self.pushgateway_url = pushgateway_url or os.getenv("PUSHGATEWAY_URL")
        self.interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # 初始化Celery检查器
        self._inspect = None
        self._init_inspect()

    def _init_inspect(self):
        """初始化Celery检查器"""
        try:
            from celery.app.control import Inspect
            from src.workers.celery_app import get_celery_app

            app = get_celery_app()
            self._inspect = Inspect(app)
            logger.info(f"Celery inspector initialized with broker: {self.broker_url}")
        except Exception as e:
            logger.warning(f"Failed to initialize Celery inspector: {e}")
            self._inspect = None

    def get_active_tasks(self) -> dict:
        """获取当前正在执行的任务"""
        if self._inspect is None:
            return {}
        try:
            return self._inspect.active() or {}
        except Exception as e:
            logger.error(f"Failed to get active tasks: {e}")
            return {}

    def get_scheduled_tasks(self) -> dict:
        """获取已安排但未开始的任务"""
        if self._inspect is None:
            return {}
        try:
            return self._inspect.scheduled() or {}
        except Exception as e:
            logger.error(f"Failed to get scheduled tasks: {e}")
            return {}

    def get_reserved_tasks(self) -> dict:
        """获取预留的任务（已分配给Worker但未开始）"""
        if self._inspect is None:
            return {}
        try:
            return self._inspect.reserved() or {}
        except Exception as e:
            logger.error(f"Failed to get reserved tasks: {e}")
            return {}

    def get_worker_stats(self) -> dict:
        """获取Worker统计"""
        if self._inspect is None:
            return {}
        try:
            return self._inspect.stats() or {}
        except Exception as e:
            logger.error(f"Failed to get worker stats: {e}")
            return {}

    def get_worker_info(self) -> dict:
        """获取Worker详细信息"""
        if self._inspect is None:
            return {}
        try:
            return self._inspect.inspector.workers() or {}
        except Exception as e:
            logger.error(f"Failed to get worker info: {e}")
            return {}

    def estimate_queue_depth(self) -> dict:
        """估算队列深度（通过对比各状态任务数）"""
        active = len([t for v in self.get_active_tasks().values() for t in v])
        scheduled = len([t for v in self.get_scheduled_tasks().values() for t in v])
        reserved = len([t for v in self.get_reserved_tasks().values() for t in v])

        # 估算待处理任务数
        stats = self.get_worker_stats()
        total_workers = len(stats)
        concurrency = sum(
            s.get("pool", {}).get("max-concurrency", 1) or 1
            for s in stats.values()
        )

        # 正在运行的任务数
        running = active

        # 预估队列深度 = 已调度 + 预留 - (Worker容量 - 正在运行)
        estimated_queue = scheduled + reserved - (concurrency - running)
        estimated_queue = max(0, estimated_queue)  # 确保非负

        return {
            "active": active,
            "scheduled": scheduled,
            "reserved": reserved,
            "workers": total_workers,
            "concurrency": concurrency,
            "running": running,
            "estimated_queue_depth": estimated_queue,
        }

    def push_to_pushgateway(self, metrics: dict):
        """推送指标到Pushgateway"""
        if not self.pushgateway_url:
            return

        try:
            import httpx
            from prometheus_client import CollectorRegistry, Gauge

            registry = CollectorRegistry()

            # 创建指标
            queue_depth = Gauge(
                "celery_estimated_queue_depth",
                "Estimated celery queue depth",
                ["queue"],
                registry=registry,
            )
            active_tasks = Gauge(
                "celery_active_tasks",
                "Number of active tasks",
                registry=registry,
            )
            worker_count = Gauge(
                "celery_worker_count",
                "Number of celery workers",
                registry=registry,
            )

            # 设置值
            queue_depth.labels(queue="default").set(metrics["estimated_queue_depth"])
            active_tasks.set(metrics["active"])
            worker_count.set(metrics["workers"])

            # 推送
            from prometheus_client import generate_latest
            data = generate_latest(registry)
            response = httpx.post(
                f"{self.pushgateway_url}/metrics/job/celery_monitor",
                data=data,
                headers={"Content-Type": "text/plain"}
            )
            response.raise_for_status()
            logger.debug("Metrics pushed to Pushgateway")
        except Exception as e:
            logger.warning(f"Failed to push metrics to Pushgateway: {e}")

    def monitor_loop(self):
        """监控循环"""
        logger.info(f"Starting monitor loop (interval={self.interval}s)")

        while self._running:
            try:
                metrics = self.estimate_queue_depth()

                # 打印状态
                logger.info(
                    f"Queue Status: "
                    f"active={metrics['active']}, "
                    f"scheduled={metrics['scheduled']}, "
                    f"reserved={metrics['reserved']}, "
                    f"workers={metrics['workers']}, "
                    f"concurrency={metrics['concurrency']}, "
                    f"estimated_queue={metrics['estimated_queue_depth']}"
                )

                # 获取Worker详细信息
                worker_info = self.get_worker_info()
                for worker, info in worker_info.items():
                    status = info.get("status", "unknown")
                    logger.info(f"  Worker {worker}: status={status}")

                # 推送指标
                self.push_to_pushgateway(metrics)

            except Exception as e:
                logger.error(f"Monitor error: {e}")

            time.sleep(self.interval)

        logger.info("Monitor loop stopped")

    def start(self):
        """启动监控"""
        if self._running:
            logger.warning("Monitor already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Celery queue monitor started")

    def stop(self):
        """停止监控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Celery queue monitor stopped")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Celery Queue Monitor")
    parser.add_argument(
        "--interval", type=int, default=10,
        help="Monitoring interval in seconds (default: 10)"
    )
    parser.add_argument(
        "--broker-url", type=str,
        help="Celery broker URL (default: from CELERY_BROKER_URL env)"
    )
    parser.add_argument(
        "--pushgateway-url", type=str,
        help="Pushgateway URL (default: from PUSHGATEWAY_URL env)"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run once and exit (non-daemon mode)"
    )

    args = parser.parse_args()

    monitor = CeleryQueueMonitor(
        broker_url=args.broker_url,
        pushgateway_url=args.pushgateway_url,
        interval=args.interval,
    )

    if args.once:
        # 单次运行
        metrics = monitor.estimate_queue_depth()
        print(f"Estimated Queue Depth: {metrics['estimated_queue_depth']}")
        print(f"Active Tasks: {metrics['active']}")
        print(f"Workers: {metrics['workers']}")
        print(f"Concurrency: {metrics['concurrency']}")
    else:
        # 守护模式
        try:
            monitor.start()
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            monitor.stop()


if __name__ == "__main__":
    main()
