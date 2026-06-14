"""
高可用架构组件

包含：
1. 多活部署管理
2. 故障检测与恢复
3. 健康检查机制
4. 服务发现与负载均衡
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """节点状态"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


@dataclass
class NodeInfo:
    """节点信息"""

    id: str
    host: str
    port: int
    region: str
    status: NodeStatus = NodeStatus.HEALTHY
    weight: float = 1.0
    last_check: float = 0.0
    latency_ms: float = 0.0
    error_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "host": self.host,
            "port": self.port,
            "region": self.region,
            "status": self.status.value,
            "weight": self.weight,
            "latency_ms": self.latency_ms,
            "error_count": self.error_count,
        }


@dataclass
class HealthCheckConfig:
    """健康检查配置"""

    interval_seconds: float = 10.0
    timeout_seconds: float = 5.0
    unhealthy_threshold: int = 3
    healthy_threshold: int = 2
    degraded_threshold_ms: float = 500.0


class HealthChecker:
    """
    健康检查器

    定期检查节点健康状态，自动标记故障节点。
    """

    def __init__(self, config: HealthCheckConfig | None = None):
        self._config = config or HealthCheckConfig()
        self._nodes: dict[str, NodeInfo] = {}
        self._check_task: asyncio.Task | None = None
        self._callbacks: list[callable] = []

    def register_node(self, node: NodeInfo):
        """注册节点"""
        self._nodes[node.id] = node
        logger.info(f"Registered node: {node.id} @ {node.host}:{node.port}")

    def unregister_node(self, node_id: str):
        """注销节点"""
        if node_id in self._nodes:
            del self._nodes[node_id]
            logger.info(f"Unregistered node: {node_id}")

    def add_status_callback(self, callback: callable):
        """添加状态变更回调"""
        self._callbacks.append(callback)

    async def start(self):
        """启动健康检查"""
        self._check_task = asyncio.create_task(self._run_health_checks())
        logger.info("Health checker started")

    async def stop(self):
        """停止健康检查"""
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        logger.info("Health checker stopped")

    async def _run_health_checks(self):
        """定期执行健康检查"""
        while True:
            await asyncio.sleep(self._config.interval_seconds)
            await self._check_all_nodes()

    async def _check_all_nodes(self):
        """检查所有节点"""
        for node_id, node in self._nodes.items():
            if node.status == NodeStatus.OFFLINE:
                continue

            try:
                # 执行健康检查
                start_time = time.time()
                is_healthy = await self._check_node_health(node)
                latency = (time.time() - start_time) * 1000

                # 更新节点状态
                await self._update_node_status(node, is_healthy, latency)

            except Exception as e:
                logger.error(f"Health check failed for {node_id}: {e}")
                node.error_count += 1
                if node.error_count >= self._config.unhealthy_threshold:
                    await self._set_node_status(node, NodeStatus.UNHEALTHY)

    async def _check_node_health(self, node: NodeInfo) -> bool:
        """检查单个节点健康状态"""
        # 这里可以替换为实际的 HTTP/TCP 检查
        # 示例：模拟检查
        await asyncio.sleep(0.01)  # 模拟网络延迟
        return True  # 模拟健康

    async def _update_node_status(self, node: NodeInfo, is_healthy: bool, latency: float):
        """更新节点状态"""
        node.last_check = time.time()
        node.latency_ms = latency

        # 根据延迟判断是否降级
        if latency > self._config.degraded_threshold_ms:
            if node.status == NodeStatus.HEALTHY:
                await self._set_node_status(node, NodeStatus.DEGRADED)
        elif is_healthy:
            if node.status in [NodeStatus.UNHEALTHY, NodeStatus.DEGRADED]:
                node.error_count = 0
                await self._set_node_status(node, NodeStatus.HEALTHY)

    async def _set_node_status(self, node: NodeInfo, new_status: NodeStatus):
        """设置节点状态"""
        old_status = node.status
        if old_status != new_status:
            node.status = new_status
            logger.warning(
                f"Node {node.id} status changed: {old_status.value} -> {new_status.value}"
            )

            # 触发回调
            for callback in self._callbacks:
                try:
                    await callback(node, old_status, new_status)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

    def get_healthy_nodes(self) -> list[NodeInfo]:
        """获取健康节点列表"""
        return [
            node
            for node in self._nodes.values()
            if node.status in [NodeStatus.HEALTHY, NodeStatus.DEGRADED]
        ]

    def get_all_nodes(self) -> dict[str, NodeInfo]:
        """获取所有节点"""
        return self._nodes


class LoadBalancer:
    """
    负载均衡器

    支持多种负载均衡策略。
    """

    def __init__(self, strategy: str = "weighted_round_robin"):
        self._strategy = strategy
        self._current_index = 0
        self._request_counts: dict[str, int] = {}

    def select_node(self, nodes: list[NodeInfo]) -> NodeInfo | None:
        """选择节点"""
        if not nodes:
            return None

        if self._strategy == "round_robin":
            return self._round_robin(nodes)
        elif self._strategy == "weighted_round_robin":
            return self._weighted_round_robin(nodes)
        elif self._strategy == "least_connections":
            return self._least_connections(nodes)
        elif self._strategy == "random":
            return self._random(nodes)
        elif self._strategy == "latency_based":
            return self._latency_based(nodes)
        else:
            return nodes[0]

    def _round_robin(self, nodes: list[NodeInfo]) -> NodeInfo:
        """轮询"""
        node = nodes[self._current_index % len(nodes)]
        self._current_index += 1
        return node

    def _weighted_round_robin(self, nodes: list[NodeInfo]) -> NodeInfo:
        """加权轮询"""
        total_weight = sum(n.weight for n in nodes)
        if total_weight == 0:
            return nodes[0]

        # 根据权重选择
        r = random.uniform(0, total_weight)
        current_weight = 0
        for node in nodes:
            current_weight += node.weight
            if r <= current_weight:
                return node

        return nodes[-1]

    def _least_connections(self, nodes: list[NodeInfo]) -> NodeInfo:
        """最少连接"""
        return min(nodes, key=lambda n: self._request_counts.get(n.id, 0))

    def _random(self, nodes: list[NodeInfo]) -> NodeInfo:
        """随机选择"""
        return random.choice(nodes)

    def _latency_based(self, nodes: list[NodeInfo]) -> NodeInfo:
        """基于延迟选择"""
        return min(nodes, key=lambda n: n.latency_ms)

    def record_request(self, node_id: str):
        """记录请求"""
        self._request_counts[node_id] = self._request_counts.get(node_id, 0) + 1

    def record_completion(self, node_id: str):
        """记录完成"""
        if node_id in self._request_counts:
            self._request_counts[node_id] -= 1


class FailoverManager:
    """
    故障转移管理器

    自动处理节点故障，切换到备用节点。
    """

    def __init__(self, health_checker: HealthChecker, load_balancer: LoadBalancer):
        self._health_checker = health_checker
        self._load_balancer = load_balancer
        self._failover_count = 0
        self._recovery_count = 0

        # 注册状态变更回调
        self._health_checker.add_status_callback(self._on_status_change)

    async def _on_status_change(
        self, node: NodeInfo, old_status: NodeStatus, new_status: NodeStatus
    ):
        """处理状态变更"""
        if new_status == NodeStatus.UNHEALTHY:
            await self._handle_failover(node)
        elif old_status == NodeStatus.UNHEALTHY and new_status == NodeStatus.HEALTHY:
            await self._handle_recovery(node)

    async def _handle_failover(self, node: NodeInfo):
        """处理故障转移"""
        self._failover_count += 1
        logger.warning(
            f"Failover triggered for node {node.id}, total failovers: {self._failover_count}"
        )

        # 降低故障节点权重
        node.weight = 0.0

        # 选择备用节点
        healthy_nodes = self._health_checker.get_healthy_nodes()
        if healthy_nodes:
            backup = self._load_balancer.select_node(healthy_nodes)
            logger.info(f"Switched to backup node: {backup.id}")

    async def _handle_recovery(self, node: NodeInfo):
        """处理节点恢复"""
        self._recovery_count += 1
        logger.info(f"Node {node.id} recovered, total recoveries: {self._recovery_count}")

        # 恢复节点权重
        node.weight = 1.0

    def get_stats(self) -> dict:
        """获取故障转移统计"""
        return {
            "failover_count": self._failover_count,
            "recovery_count": self._recovery_count,
            "active_nodes": len(self._health_checker.get_healthy_nodes()),
            "total_nodes": len(self._health_checker.get_all_nodes()),
        }


class MultiActiveDeployer:
    """
    多活部署管理器

    管理多区域、多节点的部署配置。
    """

    def __init__(self):
        self._regions: dict[str, list[NodeInfo]] = {}
        self._health_checker = HealthChecker()
        self._load_balancer = LoadBalancer(strategy="weighted_round_robin")
        self._failover_manager = FailoverManager(self._health_checker, self._load_balancer)

    def add_region(self, region: str, nodes: list[NodeInfo]):
        """添加区域"""
        self._regions[region] = nodes
        for node in nodes:
            self._health_checker.register_node(node)
        logger.info(f"Added region {region} with {len(nodes)} nodes")

    def remove_region(self, region: str):
        """移除区域"""
        if region in self._regions:
            for node in self._regions[region]:
                self._health_checker.unregister_node(node.id)
            del self._regions[region]
            logger.info(f"Removed region {region}")

    async def start(self):
        """启动多活部署"""
        await self._health_checker.start()
        logger.info("Multi-active deployer started")

    async def stop(self):
        """停止多活部署"""
        await self._health_checker.stop()
        logger.info("Multi-active deployer stopped")

    def get_node_for_request(self, region: str | None = None) -> NodeInfo | None:
        """获取处理请求的节点"""
        if region and region in self._regions:
            nodes = [
                n
                for n in self._regions[region]
                if n.status in [NodeStatus.HEALTHY, NodeStatus.DEGRADED]
            ]
        else:
            nodes = self._health_checker.get_healthy_nodes()

        node = self._load_balancer.select_node(nodes)
        if node:
            self._load_balancer.record_request(node.id)
        return node

    def get_deployment_stats(self) -> dict:
        """获取部署统计"""
        stats = {
            "regions": {},
            "failover": self._failover_manager.get_stats(),
        }

        for region, nodes in self._regions.items():
            healthy_count = sum(1 for n in nodes if n.status == NodeStatus.HEALTHY)
            stats["regions"][region] = {
                "total_nodes": len(nodes),
                "healthy_nodes": healthy_count,
                "avg_latency_ms": sum(n.latency_ms for n in nodes) / len(nodes),
            }

        return stats


class AutoRecoveryService:
    """
    自动恢复服务

    监控并自动恢复故障服务。
    """

    def __init__(self, max_recovery_attempts: int = 3, recovery_interval: float = 60.0):
        self._max_attempts = max_recovery_attempts
        self._interval = recovery_interval
        self._recovery_tasks: dict[str, asyncio.Task] = {}
        self._recovery_history: dict[str, list[dict]] = {}

    async def attempt_recovery(self, node: NodeInfo) -> bool:
        """尝试恢复节点"""
        node_id = node.id
        history = self._recovery_history.get(node_id, [])

        # 检查恢复历史
        recent_failures = [h for h in history if time.time() - h["timestamp"] < 3600]
        if len(recent_failures) >= self._max_attempts:
            logger.warning(f"Node {node_id} exceeded max recovery attempts")
            return False

        # 执行恢复操作
        try:
            logger.info(f"Attempting recovery for node {node_id}")

            # 模拟恢复操作（实际可以是重启服务、清理缓存等）
            await asyncio.sleep(1)

            # 记录恢复历史
            history.append({"timestamp": time.time(), "success": True})
            self._recovery_history[node_id] = history

            logger.info(f"Node {node_id} recovered successfully")
            return True

        except Exception as e:
            logger.error(f"Recovery failed for node {node_id}: {e}")
            history.append({"timestamp": time.time(), "success": False, "error": str(e)})
            self._recovery_history[node_id] = history
            return False

    def get_recovery_history(self, node_id: str) -> list[dict]:
        """获取恢复历史"""
        return self._recovery_history.get(node_id, [])

    def clear_history(self, node_id: str):
        """清除历史"""
        if node_id in self._recovery_history:
            del self._recovery_history[node_id]


# 全局高可用管理器
_global_deployer: MultiActiveDeployer | None = None


def get_deployer() -> MultiActiveDeployer:
    """获取全局部署管理器"""
    global _global_deployer
    if _global_deployer is None:
        _global_deployer = MultiActiveDeployer()
    return _global_deployer
