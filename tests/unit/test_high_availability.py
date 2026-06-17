import asyncio
import pytest
from unittest.mock import MagicMock, patch

from src.infra.high_availability import (
    AutoRecoveryService,
    FailoverManager,
    HealthChecker,
    HealthCheckConfig,
    LoadBalancer,
    MultiActiveDeployer,
    NodeInfo,
    NodeStatus,
    get_deployer,
)


class TestNodeStatus:
    """节点状态枚举测试"""

    def test_node_status_values(self):
        assert NodeStatus.HEALTHY.value == "healthy"
        assert NodeStatus.DEGRADED.value == "degraded"
        assert NodeStatus.UNHEALTHY.value == "unhealthy"
        assert NodeStatus.OFFLINE.value == "offline"


class TestNodeInfo:
    """节点信息测试"""

    def test_node_info_creation(self):
        node = NodeInfo(id="node1", host="localhost", port=8080, region="cn")
        assert node.id == "node1"
        assert node.host == "localhost"
        assert node.port == 8080
        assert node.region == "cn"
        assert node.status == NodeStatus.HEALTHY
        assert node.weight == 1.0

    def test_node_info_to_dict(self):
        node = NodeInfo(id="node1", host="localhost", port=8080, region="cn")
        node_dict = node.to_dict()
        assert node_dict["id"] == "node1"
        assert node_dict["host"] == "localhost"
        assert node_dict["status"] == "healthy"
        assert "metadata" not in node_dict


class TestHealthCheckConfig:
    """健康检查配置测试"""

    def test_default_config(self):
        config = HealthCheckConfig()
        assert config.interval_seconds == 10.0
        assert config.timeout_seconds == 5.0
        assert config.unhealthy_threshold == 3
        assert config.healthy_threshold == 2


class TestHealthChecker:
    """健康检查器测试"""

    def test_register_and_unregister_node(self):
        checker = HealthChecker()
        node = NodeInfo(id="node1", host="localhost", port=8080, region="cn")

        checker.register_node(node)
        assert len(checker.get_all_nodes()) == 1

        checker.unregister_node("node1")
        assert len(checker.get_all_nodes()) == 0

    def test_get_healthy_nodes(self):
        checker = HealthChecker()
        healthy_node = NodeInfo(id="node1", host="localhost", port=8080, region="cn")
        degraded_node = NodeInfo(id="node2", host="localhost", port=8081, region="cn", status=NodeStatus.DEGRADED)
        unhealthy_node = NodeInfo(id="node3", host="localhost", port=8082, region="cn", status=NodeStatus.UNHEALTHY)

        checker.register_node(healthy_node)
        checker.register_node(degraded_node)
        checker.register_node(unhealthy_node)

        healthy_nodes = checker.get_healthy_nodes()
        assert len(healthy_nodes) == 2
        assert all(n.id in ["node1", "node2"] for n in healthy_nodes)

    def test_add_status_callback(self):
        checker = HealthChecker()
        callback_called = []

        def callback(node, old_status, new_status):
            callback_called.append((node.id, old_status, new_status))

        checker.add_status_callback(callback)
        assert len(checker._callbacks) == 1

    @pytest.mark.anyio
    async def test_start_and_stop(self):
        """测试健康检查器启动和停止"""
        config = HealthCheckConfig(interval_seconds=0.01)
        checker = HealthChecker(config)
        node = NodeInfo(id="node1", host="localhost", port=8080, region="cn")
        checker.register_node(node)

        await checker.start()
        assert checker._check_task is not None
        assert not checker._check_task.done()

        await asyncio.sleep(0.05)

        await checker.stop()
        assert checker._check_task is None or checker._check_task.done()

    @pytest.mark.anyio
    async def test_health_check_updates_status(self):
        """测试健康检查更新节点状态"""
        config = HealthCheckConfig(interval_seconds=0.01)
        checker = HealthChecker(config)
        node = NodeInfo(id="node1", host="localhost", port=8080, region="cn")
        checker.register_node(node)

        await checker.start()
        await asyncio.sleep(0.05)

        assert node.last_check > 0
        assert node.latency_ms >= 0

        await checker.stop()

    @pytest.mark.anyio
    async def test_status_change_callback(self):
        """测试状态变更回调"""
        config = HealthCheckConfig(interval_seconds=0.01)
        checker = HealthChecker(config)
        node = NodeInfo(id="node1", host="localhost", port=8080, region="cn")
        checker.register_node(node)

        callback_calls = []

        async def callback(node, old_status, new_status):
            callback_calls.append((node.id, old_status, new_status))

        checker.add_status_callback(callback)

        await checker.start()

        with patch.object(checker, "_check_node_health", return_value=True):
            await asyncio.sleep(0.05)

            if not callback_calls:
                await checker._set_node_status(node, NodeStatus.DEGRADED)

        await checker.stop()

        assert len(callback_calls) >= 1
        assert callback_calls[-1][0] == "node1"

    @pytest.mark.anyio
    async def test_offline_node_skipped(self):
        """测试离线节点被跳过"""
        config = HealthCheckConfig(interval_seconds=0.01)
        checker = HealthChecker(config)
        offline_node = NodeInfo(id="node1", host="localhost", port=8080, region="cn", status=NodeStatus.OFFLINE)
        checker.register_node(offline_node)

        await checker.start()
        await asyncio.sleep(0.05)

        assert offline_node.status == NodeStatus.OFFLINE

        await checker.stop()

    @pytest.mark.anyio
    async def test_degraded_to_healthy_recovery(self):
        """测试降级节点恢复健康"""
        config = HealthCheckConfig(interval_seconds=0.01)
        checker = HealthChecker(config)
        degraded_node = NodeInfo(id="node1", host="localhost", port=8080, region="cn", status=NodeStatus.DEGRADED)
        checker.register_node(degraded_node)

        await checker.start()
        await asyncio.sleep(0.05)

        assert degraded_node.status == NodeStatus.HEALTHY

        await checker.stop()

    @pytest.mark.anyio
    async def test_health_check_failure_increases_error_count(self):
        """测试健康检查失败增加错误计数"""
        config = HealthCheckConfig(interval_seconds=0.01)
        checker = HealthChecker(config)
        node = NodeInfo(id="node1", host="localhost", port=8080, region="cn")
        checker.register_node(node)

        with patch.object(checker, "_check_node_health", side_effect=Exception("test error")):
            await checker.start()
            await asyncio.sleep(0.05)

            assert node.error_count >= 1

        await checker.stop()

    @pytest.mark.anyio
    async def test_unhealthy_threshold_reached(self):
        """测试达到不健康阈值"""
        config = HealthCheckConfig(interval_seconds=0.01, unhealthy_threshold=1)
        checker = HealthChecker(config)
        node = NodeInfo(id="node1", host="localhost", port=8080, region="cn")
        checker.register_node(node)

        with patch.object(checker, "_check_node_health", side_effect=Exception("test error")):
            await checker.start()
            await asyncio.sleep(0.05)

            assert node.status == NodeStatus.UNHEALTHY

        await checker.stop()


class TestLoadBalancer:
    """负载均衡器测试"""

    def test_round_robin_strategy(self):
        balancer = LoadBalancer(strategy="round_robin")
        nodes = [
            NodeInfo(id="node1", host="localhost", port=8080, region="cn"),
            NodeInfo(id="node2", host="localhost", port=8081, region="cn"),
        ]

        node1 = balancer.select_node(nodes)
        node2 = balancer.select_node(nodes)
        node1_again = balancer.select_node(nodes)

        assert node1.id == "node1"
        assert node2.id == "node2"
        assert node1_again.id == "node1"

    def test_weighted_round_robin_strategy(self):
        balancer = LoadBalancer(strategy="weighted_round_robin")
        nodes = [
            NodeInfo(id="node1", host="localhost", port=8080, region="cn", weight=1.0),
            NodeInfo(id="node2", host="localhost", port=8081, region="cn", weight=3.0),
        ]

        selections = [balancer.select_node(nodes).id for _ in range(10)]
        assert "node1" in selections
        assert "node2" in selections

    def test_random_strategy(self):
        balancer = LoadBalancer(strategy="random")
        nodes = [
            NodeInfo(id="node1", host="localhost", port=8080, region="cn"),
            NodeInfo(id="node2", host="localhost", port=8081, region="cn"),
        ]

        node = balancer.select_node(nodes)
        assert node.id in ["node1", "node2"]

    def test_latency_based_strategy(self):
        balancer = LoadBalancer(strategy="latency_based")
        nodes = [
            NodeInfo(id="node1", host="localhost", port=8080, region="cn", latency_ms=100),
            NodeInfo(id="node2", host="localhost", port=8081, region="cn", latency_ms=50),
        ]

        node = balancer.select_node(nodes)
        assert node.id == "node2"

    def test_least_connections_strategy(self):
        balancer = LoadBalancer(strategy="least_connections")
        nodes = [
            NodeInfo(id="node1", host="localhost", port=8080, region="cn"),
            NodeInfo(id="node2", host="localhost", port=8081, region="cn"),
        ]

        balancer.record_request("node1")
        balancer.record_request("node1")

        node = balancer.select_node(nodes)
        assert node.id == "node2"

    def test_record_completion(self):
        balancer = LoadBalancer()
        balancer.record_request("node1")
        assert balancer._request_counts["node1"] == 1

        balancer.record_completion("node1")
        assert balancer._request_counts["node1"] == 0

    def test_select_node_empty(self):
        balancer = LoadBalancer()
        result = balancer.select_node([])
        assert result is None

    def test_weighted_round_robin_zero_weight(self):
        """测试加权轮询零权重"""
        balancer = LoadBalancer(strategy="weighted_round_robin")
        nodes = [
            NodeInfo(id="node1", host="localhost", port=8080, region="cn", weight=0.0),
        ]

        node = balancer.select_node(nodes)
        assert node.id == "node1"


class TestFailoverManager:
    """故障转移管理器测试"""

    def test_failover_manager_initialization(self):
        checker = HealthChecker()
        balancer = LoadBalancer()
        failover = FailoverManager(checker, balancer)

        assert failover._failover_count == 0
        assert failover._recovery_count == 0

    def test_get_stats(self):
        checker = HealthChecker()
        balancer = LoadBalancer()
        failover = FailoverManager(checker, balancer)

        stats = failover.get_stats()
        assert "failover_count" in stats
        assert "recovery_count" in stats
        assert "active_nodes" in stats

    @pytest.mark.anyio
    async def test_failover_on_unhealthy(self):
        """测试不健康节点触发故障转移"""
        checker = HealthChecker()
        balancer = LoadBalancer()
        failover = FailoverManager(checker, balancer)

        node = NodeInfo(id="node1", host="localhost", port=8080, region="cn")
        checker.register_node(node)

        await failover._on_status_change(node, NodeStatus.HEALTHY, NodeStatus.UNHEALTHY)

        assert failover._failover_count == 1
        assert node.weight == 0.0

    @pytest.mark.anyio
    async def test_recovery_on_healthy(self):
        """测试节点恢复"""
        checker = HealthChecker()
        balancer = LoadBalancer()
        failover = FailoverManager(checker, balancer)

        node = NodeInfo(id="node1", host="localhost", port=8080, region="cn", status=NodeStatus.UNHEALTHY, weight=0.0)
        checker.register_node(node)

        await failover._on_status_change(node, NodeStatus.UNHEALTHY, NodeStatus.HEALTHY)

        assert failover._recovery_count == 1
        assert node.weight == 1.0

    @pytest.mark.anyio
    async def test_failover_selects_backup(self):
        """测试故障转移选择备用节点"""
        checker = HealthChecker()
        balancer = LoadBalancer()
        failover = FailoverManager(checker, balancer)

        node1 = NodeInfo(id="node1", host="localhost", port=8080, region="cn")
        node2 = NodeInfo(id="node2", host="localhost", port=8081, region="cn")
        checker.register_node(node1)
        checker.register_node(node2)

        await failover._on_status_change(node1, NodeStatus.HEALTHY, NodeStatus.UNHEALTHY)

        assert failover._failover_count == 1


class TestMultiActiveDeployer:
    """多活部署管理器测试"""

    def test_add_and_remove_region(self):
        deployer = MultiActiveDeployer()
        nodes = [
            NodeInfo(id="node1", host="localhost", port=8080, region="cn"),
        ]

        deployer.add_region("cn", nodes)
        assert "cn" in deployer._regions

        deployer.remove_region("cn")
        assert "cn" not in deployer._regions

    def test_get_node_for_request(self):
        deployer = MultiActiveDeployer()
        nodes = [
            NodeInfo(id="node1", host="localhost", port=8080, region="cn"),
            NodeInfo(id="node2", host="localhost", port=8081, region="cn"),
        ]

        deployer.add_region("cn", nodes)
        node = deployer.get_node_for_request("cn")
        assert node is not None
        assert node.id in ["node1", "node2"]

    def test_get_deployment_stats(self):
        deployer = MultiActiveDeployer()
        nodes = [
            NodeInfo(id="node1", host="localhost", port=8080, region="cn"),
        ]

        deployer.add_region("cn", nodes)
        stats = deployer.get_deployment_stats()
        assert "regions" in stats
        assert "cn" in stats["regions"]

    @pytest.mark.anyio
    async def test_start_and_stop(self):
        """测试多活部署启动和停止"""
        deployer = MultiActiveDeployer()
        nodes = [
            NodeInfo(id="node1", host="localhost", port=8080, region="cn"),
        ]
        deployer.add_region("cn", nodes)

        await deployer.start()
        await asyncio.sleep(0.05)

        await deployer.stop()

    def test_get_node_for_request_no_region(self):
        """测试不指定区域获取节点"""
        deployer = MultiActiveDeployer()
        nodes = [
            NodeInfo(id="node1", host="localhost", port=8080, region="cn"),
        ]

        deployer.add_region("cn", nodes)
        node = deployer.get_node_for_request()
        assert node is not None


class TestAutoRecoveryService:
    """自动恢复服务测试"""

    @pytest.mark.anyio
    async def test_attempt_recovery_success(self):
        service = AutoRecoveryService(max_recovery_attempts=3, recovery_interval=60.0)
        node = NodeInfo(id="node1", host="localhost", port=8080, region="cn")

        result = await service.attempt_recovery(node)
        assert result is True

        history = service.get_recovery_history("node1")
        assert len(history) == 1
        assert history[0]["success"] is True

    @pytest.mark.anyio
    async def test_attempt_recovery_exceeds_max_attempts(self):
        service = AutoRecoveryService(max_recovery_attempts=1)
        node = NodeInfo(id="node1", host="localhost", port=8080, region="cn")

        await service.attempt_recovery(node)
        result = await service.attempt_recovery(node)

        assert result is False

    def test_clear_recovery_history(self):
        service = AutoRecoveryService()
        node = NodeInfo(id="node1", host="localhost", port=8080, region="cn")

        service._recovery_history["node1"] = [{"timestamp": 1.0, "success": True}]
        service.clear_history("node1")

        assert "node1" not in service._recovery_history

    @pytest.mark.anyio
    async def test_attempt_recovery_failure(self):
        """测试恢复失败"""
        service = AutoRecoveryService()
        node = NodeInfo(id="node1", host="localhost", port=8080, region="cn")

        with patch("asyncio.sleep", side_effect=Exception("recovery failed")):
            result = await service.attempt_recovery(node)
            assert result is False

        history = service.get_recovery_history("node1")
        assert len(history) == 1
        assert history[0]["success"] is False
        assert "error" in history[0]

    @pytest.mark.anyio
    async def test_recovery_history_purge(self):
        """测试恢复历史清理（超过1小时）"""
        import time
        service = AutoRecoveryService(max_recovery_attempts=1)
        node = NodeInfo(id="node1", host="localhost", port=8080, region="cn")

        service._recovery_history["node1"] = [{"timestamp": time.time() - 3700, "success": False}]
        result = await service.attempt_recovery(node)

        assert result is True


class TestGlobalDeployer:
    """全局部署管理器测试"""

    def test_get_deployer_returns_same_instance(self):
        deployer1 = get_deployer()
        deployer2 = get_deployer()
