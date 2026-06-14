"""
边缘评测原型

实现边缘节点评测能力，降低延迟，支持离线评测。
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EdgeNode:
    """边缘节点"""

    node_id: str
    location: str  # 地理位置
    region: str
    capacity: int  # 最大并发评测数
    current_load: int = 0
    latency_to_origin_ms: float = 50.0
    is_online: bool = True
    last_sync: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def can_accept(self) -> bool:
        """是否可以接受新评测"""
        return self.is_online and self.current_load < self.capacity

    def get_load_ratio(self) -> float:
        """获取负载比例"""
        return self.current_load / self.capacity if self.capacity > 0 else 0


@dataclass
class EdgeEvaluation:
    """边缘评测任务"""

    task_id: str
    model: str
    dataset: str
    metrics: list[str]
    edge_node_id: str
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: dict[str, Any] | None = None
    latency_ms: float | None = None


class EdgeEvaluator:
    """
    边缘评测器

    在边缘节点执行评测，降低延迟。
    """

    def __init__(self, edge_nodes: list[EdgeNode]):
        self._nodes = {node.node_id: node for node in edge_nodes}
        self._pending_tasks: dict[str, EdgeEvaluation] = {}
        self._completed_tasks: dict[str, EdgeEvaluation] = {}
        self._sync_interval = 60.0  # 同步间隔

    def select_best_node(self, user_location: str | None = None) -> EdgeNode | None:
        """选择最佳边缘节点"""
        available_nodes = [n for n in self._nodes.values() if n.can_accept()]

        if not available_nodes:
            return None

        # 如果有用户位置，优先选择就近节点
        if user_location:
            # 简化：按位置匹配
            matching_nodes = [n for n in available_nodes if n.location == user_location]
            if matching_nodes:
                return min(matching_nodes, key=lambda n: n.current_load)

        # 否则选择负载最低的节点
        return min(available_nodes, key=lambda n: n.get_load_ratio())

    async def submit_evaluation(
        self,
        model: str,
        dataset: str,
        metrics: list[str],
        user_location: str | None = None,
    ) -> EdgeEvaluation | None:
        """提交边缘评测"""
        import uuid

        # 选择边缘节点
        node = self.select_best_node(user_location)
        if not node:
            logger.warning("No available edge node")
            return None

        # 创建任务
        task_id = str(uuid.uuid4())
        task = EdgeEvaluation(
            task_id=task_id,
            model=model,
            dataset=dataset,
            metrics=metrics,
            edge_node_id=node.node_id,
        )

        # 增加节点负载
        node.current_load += 1

        # 添加到待处理队列
        self._pending_tasks[task_id] = task

        logger.info(
            f"Submitted edge evaluation {task_id} to node {node.node_id} at {node.location}"
        )

        # 异步执行评测
        asyncio.create_task(self._execute_evaluation(task))

        return task

    async def _execute_evaluation(self, task: EdgeEvaluation):
        """执行边缘评测"""
        node = self._nodes.get(task.edge_node_id)
        if not node:
            logger.error(f"Edge node {task.edge_node_id} not found")
            return

        task.status = "running"
        task.started_at = time.time()

        try:
            # 模拟边缘评测（实际会调用本地模型）
            start_time = time.time()

            # 执行评测
            result = await self._run_local_evaluation(task)

            # 记录延迟
            task.latency_ms = (time.time() - start_time) * 1000
            task.result = result
            task.status = "completed"
            task.completed_at = time.time()

            # 移到已完成队列
            self._completed_tasks[task.task_id] = task
            if task.task_id in self._pending_tasks:
                del self._pending_tasks[task.task_id]

            logger.info(f"Edge evaluation {task.task_id} completed in {task.latency_ms:.1f}ms")

        except Exception as e:
            logger.error(f"Edge evaluation failed: {e}")
            task.status = "failed"
            task.result = {"error": str(e)}

        finally:
            # 减少节点负载
            node.current_load -= 1

    async def _run_local_evaluation(self, task: EdgeEvaluation) -> dict:
        """运行本地评测（模拟）"""
        # 模拟评测延迟（边缘节点延迟更低）
        await asyncio.sleep(0.05)  # 50ms

        # 返回模拟结果
        return {
            "model": task.model,
            "dataset": task.dataset,
            "metrics": {
                "accuracy": 0.85 + (hash(task.model) % 10) / 100,
                "latency": task.latency_ms or 50.0,
            },
        }

    async def get_result(self, task_id: str) -> EdgeEvaluation | None:
        """获取评测结果"""
        if task_id in self._completed_tasks:
            return self._completed_tasks[task_id]

        if task_id in self._pending_tasks:
            return self._pending_tasks[task_id]

        return None

    async def sync_with_origin(self):
        """与中心节点同步"""
        for node in self._nodes.values():
            node.last_sync = time.time()
            logger.debug(f"Synced edge node {node.node_id}")

    def get_edge_stats(self) -> dict:
        """获取边缘节点统计"""
        return {
            "total_nodes": len(self._nodes),
            "online_nodes": sum(1 for n in self._nodes.values() if n.is_online),
            "pending_tasks": len(self._pending_tasks),
            "completed_tasks": len(self._completed_tasks),
            "nodes": [
                {
                    "node_id": n.node_id,
                    "location": n.location,
                    "load": n.current_load,
                    "capacity": n.capacity,
                    "load_ratio": n.get_load_ratio(),
                }
                for n in self._nodes.values()
            ],
        }


class EdgeNetwork:
    """
    边缘网络管理

    管理多个边缘节点组成的评测网络。
    """

    def __init__(self):
        self._evaluators: dict[str, EdgeEvaluator] = {}
        self._global_nodes: list[EdgeNode] = []

    def add_region(self, region: str, nodes: list[EdgeNode]):
        """添加区域边缘节点"""
        self._global_nodes.extend(nodes)
        self._evaluators[region] = EdgeEvaluator(nodes)
        logger.info(f"Added edge region {region} with {len(nodes)} nodes")

    async def submit_evaluation(
        self,
        model: str,
        dataset: str,
        metrics: list[str],
        region: str | None = None,
        user_location: str | None = None,
    ) -> EdgeEvaluation | None:
        """提交评测到边缘网络"""
        # 选择区域
        if region and region in self._evaluators:
            evaluator = self._evaluators[region]
        else:
            # 选择最佳区域
            evaluator = self._select_best_region(user_location)

        if not evaluator:
            return None

        return await evaluator.submit_evaluation(model, dataset, metrics, user_location)

    def _select_best_region(self, user_location: str | None = None) -> EdgeEvaluator | None:
        """选择最佳区域"""
        if not self._evaluators:
            return None

        # 简化：选择负载最低的区域
        best_region = min(
            self._evaluators.keys(),
            key=lambda r: sum(n.current_load for n in self._evaluators[r]._nodes.values()),
        )
        return self._evaluators[best_region]

    async def sync_all(self):
        """同步所有边缘节点"""
        for evaluator in self._evaluators.values():
            await evaluator.sync_with_origin()

    def get_network_stats(self) -> dict:
        """获取网络统计"""
        region_stats = {}
        for region, evaluator in self._evaluators.items():
            region_stats[region] = evaluator.get_edge_stats()

        return {
            "total_regions": len(self._evaluators),
            "total_nodes": len(self._global_nodes),
            "regions": region_stats,
        }


# 示例：创建全球边缘网络
def create_global_edge_network() -> EdgeNetwork:
    """创建全球边缘网络"""
    network = EdgeNetwork()

    # 北美节点
    network.add_region(
        "north_america",
        [
            EdgeNode(
                node_id="na-west-1",
                location="us-west",
                region="north_america",
                capacity=100,
                latency_to_origin_ms=30,
            ),
            EdgeNode(
                node_id="na-east-1",
                location="us-east",
                region="north_america",
                capacity=100,
                latency_to_origin_ms=25,
            ),
        ],
    )

    # 欧洲节点
    network.add_region(
        "europe",
        [
            EdgeNode(
                node_id="eu-west-1",
                location="eu-west",
                region="europe",
                capacity=80,
                latency_to_origin_ms=40,
            ),
            EdgeNode(
                node_id="eu-central-1",
                location="eu-central",
                region="europe",
                capacity=80,
                latency_to_origin_ms=35,
            ),
        ],
    )

    # 亚太节点
    network.add_region(
        "asia_pacific",
        [
            EdgeNode(
                node_id="ap-east-1",
                location="ap-east",
                region="asia_pacific",
                capacity=120,
                latency_to_origin_ms=50,
            ),
            EdgeNode(
                node_id="ap-south-1",
                location="ap-south",
                region="asia_pacific",
                capacity=120,
                latency_to_origin_ms=55,
            ),
        ],
    )

    return network
