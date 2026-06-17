import os

import pytest

from src.workers.celery_app import (
    BACKEND_URL,
    BROKER_URL,
    TASK_ACKS_LATE,
    TASK_REJECT_ON_WORKER_LOST,
    TASK_SOFT_TIME_LIMIT,
    TASK_TIME_LIMIT,
    WORKER_CONCURRENCY,
    WORKER_MAX_MEMORY_PER_CHILD,
    WORKER_MAX_TASKS_PER_CHILD,
    WORKER_PREFETCH_MULTIPLIER,
    get_celery_app,
)


class TestCeleryApp:
    """Celery应用测试"""

    def test_broker_url_default(self):
        """测试默认broker URL"""
        assert BROKER_URL == "redis://localhost:6379/0"

    def test_backend_url_default(self):
        """测试默认backend URL"""
        assert BACKEND_URL == "redis://localhost:6379/1"

    def test_worker_concurrency_default(self):
        """测试worker并发数默认值"""
        assert WORKER_CONCURRENCY == 4

    def test_worker_prefetch_multiplier_default(self):
        """测试worker预取倍数默认值（优化后为1，避免任务阻塞）"""
        assert WORKER_PREFETCH_MULTIPLIER == 1

    def test_task_time_limit_default(self):
        """测试任务硬超时默认值"""
        assert TASK_TIME_LIMIT == 60

    def test_task_soft_time_limit_default(self):
        """测试任务软超时默认值（优化后为240秒，给复杂任务更多时间）"""
        assert TASK_SOFT_TIME_LIMIT == 240

    def test_task_acks_late_default(self):
        """测试任务晚确认默认值"""
        assert TASK_ACKS_LATE is True

    def test_task_reject_on_worker_lost_default(self):
        """测试任务拒绝worker丢失默认值"""
        assert TASK_REJECT_ON_WORKER_LOST is True

    def test_worker_max_tasks_per_child_default(self):
        """测试worker最大任务数默认值"""
        assert WORKER_MAX_TASKS_PER_CHILD == 50

    def test_worker_max_memory_per_child_default(self):
        """测试worker最大内存默认值"""
        assert WORKER_MAX_MEMORY_PER_CHILD == 524288

    def test_get_celery_app_returns_same_instance(self):
        """测试get_celery_app返回同一实例"""
        app1 = get_celery_app()
        app2 = get_celery_app()
        assert app1 is app2

    def test_celery_app_name(self):
        """测试应用名称"""
        app = get_celery_app()
        assert app.main == "eval_platform"

    def test_celery_app_config(self):
        """测试配置"""
        app = get_celery_app()
        assert app.conf.task_serializer == "json"
        assert app.conf.accept_content == ["json"]
        assert app.conf.result_serializer == "json"
        assert app.conf.task_time_limit == TASK_TIME_LIMIT
        assert app.conf.task_soft_time_limit == TASK_SOFT_TIME_LIMIT
        assert app.conf.worker_max_tasks_per_child == WORKER_MAX_TASKS_PER_CHILD
        assert app.conf.worker_max_memory_per_child == WORKER_MAX_MEMORY_PER_CHILD
        assert app.conf.task_ignore_result is False
        assert app.conf.task_acks_late == TASK_ACKS_LATE
        assert app.conf.task_reject_on_worker_lost == TASK_REJECT_ON_WORKER_LOST
        assert app.conf.worker_prefetch_multiplier == WORKER_PREFETCH_MULTIPLIER

    def test_celery_app_broker_transport_options(self):
        """测试broker传输选项"""
        app = get_celery_app()
        assert app.conf.broker_transport_options.get("protocol") == 2

    def test_celery_app_backend_transport_options(self):
        """测试backend传输选项"""
        app = get_celery_app()
        assert app.conf.result_backend_transport_options.get("protocol") == 2

    def test_celery_app_includes_tasks(self):
        """测试包含任务模块"""
        app = get_celery_app()
        assert "src.workers.tasks" in app.conf.include