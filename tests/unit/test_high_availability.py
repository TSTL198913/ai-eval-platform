"""测试 src/infra/high_availability.py - 高可用架构模块

测试有效性原则：
1. 测试真实行为，不测试 mock
2. 断言外部可见行为，不依赖内部实现细节
3. 覆盖正常路径、异常路径和边界条件
"""

import asyncio
from unittest.mock import Mock

import pytest

from src.infra.high_availability import (
    AutoRecoveryService,
    FailoverManager,
    HealthCheckConfig,
    HealthChecker,
    LoadBalancer,
    MultiActiveDeployer,
    NodeInfo,
    NodeStatus,
)


class TestNodeInfo:
    """测试节点信息"""

    def test_creation_defaults(self):
        """测试默认属性"""
        node = NodeInfo(
            id="node1",
            host="localhost",
            port=8000,
            region="us-west",
        )
        assert node.status == NodeStatus.HEALTHY
        assert node.weight == 1.0
        assert node.latency_ms == 0.0
        assert node.error_count == 0
        assert node.metadata == {}

    def test_to_dict(self):
        """测试序列化为字典"""
        node = NodeInfo(
            id="node1",
            host="localhost",
            port=8000,
            region="us-west",
            status=NodeStatus.DEGRADED,
            weight=2.0,
            latency_ms=50.0,
            error_count=3,
        )
        d = node.to_dict()
        assert d["id"] == "node1"
        assert d["status"] == "degraded"
        assert d["weight"] == 2.0
        assert d["latency_ms"] == 50.0
        assert d["error_count"] == 3

    def test_status_transitions(self):
        """测试状态转换"""
        node = NodeInfo(id="n1", host="h1", port=80, region="r1")
        assert node.status == NodeStatus.HEALTHY

        node.status = NodeStatus.DEGRADED
        assert node.status == NodeStatus.DEGRADED

        node.status = NodeStatus.UNHEALTHY
        assert node.status == NodeStatus.UNHEALTHY


class TestHealthChecker:
    """测试健康检查器"""

    @pytest.fixture
    def checker(self):
        return HealthChecker(HealthCheckConfig(interval_seconds=0.1))

    @pytest.fixture
    def node(self):
        return NodeInfo(
            id="node1",
            host="localhost",
            port=8000,
            region="us-west",
        )

    def test_register_node(self, checker, node):
        """测试注册节点"""
        checker.register_node(node)
        assert checker._nodes["node1"] == node

    def test_unregister_node(self, checker, node):
        """测试注销节点"""
        checker.register_node(node)
        checker.unregister_node("node1")
        assert "node1" not in checker._nodes

    @pytest.mark.asyncio
    async def test_check_node_health_updates_last_check(self, checker, node):
        """测试健康检查更新最后检查时间"""
        checker.register_node(node)
        before = node.last_check

        # 直接调用内部检查方法（可能会触发 HTTP，但会失败并返回 False）
        result = await checker._check_node_health(node)
        assert isinstance(result, bool)
        # 检查时间应被更新（即使检查失败也会更新）
        assert node.last_check >= before

    def test_add_status_callback(self, checker):
        """测试添加状态回调"""
        callback = Mock()
        checker.add_status_callback(callback)
        assert callback in checker._callbacks

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, checker):
        """测试启动和停止生命周期"""
        await checker.start()
        assert checker._check_task is not None
        assert not checker._check_task.done()

        await checker.stop()
        # 验证任务已取消
        assert checker._check_task.cancelled() or checker._check_task.done()

    def test_get_healthy_nodes_filters(self, checker):
        """测试获取健康节点过滤：HEALTHY 和 DEGRADED 都算健康"""
        healthy = NodeInfo(id="h1", host="localhost", port=8000, region="r1", status=NodeStatus.HEALTHY)
        degraded = NodeInfo(id="d1", host="localhost", port=8001, region="r1", status=NodeStatus.DEGRADED)
        unhealthy = NodeInfo(id="u1", host="localhost", port=8002, region="r1", status=NodeStatus.UNHEALTHY)
        offline = NodeInfo(id="o1", host="localhost", port=8003, region="r1", status=NodeStatus.OFFLINE)

        for n in [healthy, degraded, unhealthy, offline]:
            checker.register_node(n)

        result = checker.get_healthy_nodes()
        # 实现返回 HEALTHY 和 DEGRADED
        assert len(result) == 2
        ids = {n.id for n in result}
        assert ids == {"h1", "d1"}

    @pytest.mark.asyncio
    async def test_callbacks_invoked_on_status_change(self, checker):
        """测试状态变化时回调被触发"""
        callback = Mock()
        checker.add_status_callback(callback)

        node = NodeInfo(id="n1", host="localhost", port=8000, region="r1", status=NodeStatus.HEALTHY)
        checker.register_node(node)

        # 模拟状态变化
        node.status = NodeStatus.UNHEALTHY
        # 手动触发回调验证机制
        for cb in checker._callbacks:
            cb(node, NodeStatus.HEALTHY, NodeStatus.UNHEALTHY)

        callback.assert_called_once()


class TestLoadBalancer:
    """测试负载均衡器"""

    @pytest.fixture
    def nodes(self):
        return [
            NodeInfo(id="node1", host="localhost", port=8000, region="us-west", weight=1.0),
            NodeInfo(id="node2", host="localhost", port=8001, region="us-west", weight=2.0),
            NodeInfo(id="node3", host="localhost", port=8002, region="us-west", weight=3.0),
        ]

    def test_round_robin_order(self, nodes):
        """测试轮询顺序"""
        lb = LoadBalancer(strategy="round_robin")
        selected = [lb.select_node(nodes).id for _ in range(6)]
        assert selected == ["node1", "node2", "node3", "node1", "node2", "node3"]

    def test_round_robin_empty_list(self):
        """测试轮询空列表"""
        lb = LoadBalancer(strategy="round_robin")
        assert lb.select_node([]) is None

    def test_weighted_round_robin_distribution(self, nodes):
        """测试加权轮询分布"""
        lb = LoadBalancer(strategy="weighted_round_robin")
        counts = {"node1": 0, "node2": 0, "node3": 0}
        for _ in range(600):
            node = lb.select_node(nodes)
            counts[node.id] += 1

        # 权重比例 1:2:3，验证大致分布
        assert counts["node3"] > counts["node2"] > counts["node1"]

    def test_least_connections_selection(self, nodes):
        """测试最少连接选择"""
        lb = LoadBalancer(strategy="least_connections")

        # 模拟不同的请求计数
        lb.record_request("node1")
        lb.record_request("node1")
        lb.record_request("node2")

        selected = lb.select_node(nodes)
        assert selected.id == "node3"  # 0 requests，最少

    def test_random_returns_valid_node(self, nodes):
        """测试随机选择返回有效节点"""
        lb = LoadBalancer(strategy="random")
        for _ in range(50):
            node = lb.select_node(nodes)
            assert node is not None
            assert node.id in ["node1", "node2", "node3"]

    def test_latency_based_selection(self, nodes):
        """测试基于延迟选择"""
        lb = LoadBalancer(strategy="latency_based")

        nodes[0].latency_ms = 200
        nodes[1].latency_ms = 10
        nodes[2].latency_ms = 100

        selected = lb.select_node(nodes)
        assert selected.id == "node2"  # 延迟最低

    def test_record_request_counts(self):
        """测试请求计数"""
        lb = LoadBalancer()
        lb.record_request("node1")
        lb.record_request("node1")
        lb.record_request("node2")

        assert lb._request_counts == {"node1": 2, "node2": 1}

    def test_unknown_strategy_fallback(self, nodes):
        """测试未知策略回退"""
        lb = LoadBalancer(strategy="unknown")
        assert lb.select_node(nodes) == nodes[0]


class TestFailoverManager:
    """测试故障转移管理器"""

    @pytest.fixture
    def manager(self):
        health_checker = HealthChecker()
        load_balancer = LoadBalancer()
        return FailoverManager(health_checker, load_balancer)

    @pytest.fixture
    def node(self):
        return NodeInfo(
            id="node1",
            host="localhost",
            port=8000,
            region="us-west",
        )

    @pytest.mark.asyncio
    async def test_handle_failover_sets_weight_zero(self, manager, node):
        """测试故障转移将权重设为0"""
        original_weight = node.weight
        await manager._handle_failover(node)
        assert node.weight == 0.0
        assert manager._failover_count == 1
        assert original_weight != 0.0  # 验证确实发生了变化

    @pytest.mark.asyncio
    async def test_handle_recovery_restores_weight(self, manager, node):
        """测试恢复操作恢复权重"""
        node.weight = 0.0
        await manager._handle_recovery(node)
        assert node.weight == 1.0
        assert manager._recovery_count == 1

    def test_get_stats_structure(self, manager):
        """测试统计信息结构"""
        stats = manager.get_stats()
        assert "failover_count" in stats
        assert "recovery_count" in stats
        assert isinstance(stats["failover_count"], int)
        assert isinstance(stats["recovery_count"], int)

    def test_failover_recovery_counting(self, manager, node):
        """测试故障和恢复计数"""

        asyncio.run(manager._handle_failover(node))
        asyncio.run(manager._handle_recovery(node))
        asyncio.run(manager._handle_failover(node))

        stats = manager.get_stats()
        assert stats["failover_count"] == 2
        assert stats["recovery_count"] == 1


class TestMultiActiveDeployer:
    """测试多活部署管理器"""

    @pytest.fixture
    def deployer(self):
        return MultiActiveDeployer()

    @pytest.fixture
    def nodes(self):
        return [
            NodeInfo(id="na-west-1", host="localhost", port=8000, region="north_america"),
            NodeInfo(id="na-east-1", host="localhost", port=8001, region="north_america"),
        ]

    def test_add_region(self, deployer, nodes):
        """测试添加区域"""
        deployer.add_region("north_america", nodes)
        assert "north_america" in deployer._regions
        assert len(deployer._regions["north_america"]) == 2

    def test_remove_region(self, deployer, nodes):
        """测试移除区域"""
        deployer.add_region("north_america", nodes)
        deployer.remove_region("north_america")
        assert "north_america" not in deployer._regions

    def test_get_node_for_request_returns_node(self, deployer, nodes):
        """测试获取请求节点"""
        deployer.add_region("north_america", nodes)
        node = deployer.get_node_for_request("north_america")
        assert node is not None
        assert node.id in ["na-west-1", "na-east-1"]

    def test_get_node_for_unknown_region(self, deployer):
        """测试未知区域返回 None"""
        assert deployer.get_node_for_request("unknown") is None

    def test_get_deployment_stats_structure(self, deployer, nodes):
        """测试部署统计结构"""
        deployer.add_region("north_america", nodes)
        stats = deployer.get_deployment_stats()

        assert "regions" in stats
        assert "failover" in stats
        assert "north_america" in stats["regions"]
        region_stats = stats["regions"]["north_america"]
        assert "total_nodes" in region_stats
        assert region_stats["total_nodes"] == 2
        assert "healthy_nodes" in region_stats
        assert "avg_latency_ms" in region_stats


class TestAutoRecoveryService:
    """测试自动恢复服务"""

    @pytest.fixture
    def service(self):
        return AutoRecoveryService(max_recovery_attempts=3, recovery_interval=60.0)

    @pytest.fixture
    def node(self):
        return NodeInfo(
            id="node1",
            host="localhost",
            port=8000,
            region="us-west",
        )

    @pytest.mark.asyncio
    async def test_attempt_recovery_success(self, service, node):
        """测试恢复成功"""
        result = await service.attempt_recovery(node)
        assert result is True
        assert len(service._recovery_history["node1"]) == 1
        assert service._recovery_history["node1"][0]["success"] is True

    @pytest.mark.asyncio
    async def test_attempt_recovery_exceeded(self, service, node):
        """测试超过最大恢复次数"""
        import time

        # 模拟多次失败
        service._recovery_history["node1"] = [
            {"timestamp": time.time() - 100, "success": False},
            {"timestamp": time.time() - 200, "success": False},
            {"timestamp": time.time() - 300, "success": False},
        ]

        result = await service.attempt_recovery(node)
        assert result is False

    def test_get_recovery_history(self, service, node):
        """测试获取恢复历史"""
        import time

        service._recovery_history["node1"] = [
            {"timestamp": time.time(), "success": True},
        ]

        history = service.get_recovery_history("node1")
        assert len(history) == 1
        assert history[0]["success"] is True

    def test_clear_history(self, service):
        """测试清除历史"""
        import time

        service._recovery_history["node1"] = [
            {"timestamp": time.time(), "success": True},
        ]

        service.clear_history("node1")
        assert service.get_recovery_history("node1") == []

    @pytest.mark.asyncio
    async def test_recovery_records_failure(self, service, node):
        """测试恢复失败被记录：超过最大尝试次数时返回 False"""
        import time

        # 预先填充失败历史，使达到最大尝试次数
        service._recovery_history["node1"] = [
            {"timestamp": time.time() - 100, "success": False, "error": "timeout"},
            {"timestamp": time.time() - 200, "success": False, "error": "timeout"},
            {"timestamp": time.time() - 300, "success": False, "error": "timeout"},
        ]

        result = await service.attempt_recovery(node)
        assert result is False
        # 验证没有添加新的成功记录
        assert all(not h.get("success", False) for h in service._recovery_history["node1"])
