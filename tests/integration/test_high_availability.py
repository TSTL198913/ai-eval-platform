"""
高可用架构组件集成测试
覆盖健康检查、负载均衡、故障转移、多活部署
"""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from src.infra.high_availability import (
    NodeStatus,
    NodeInfo,
    HealthCheckConfig,
    HealthChecker,
    LoadBalancer,
    FailoverManager,
    MultiActiveDeployer,
)


class TestNodeStatus:
    """节点状态枚举测试"""

    def test_node_status_values(self):
        """测试节点状态值"""
        assert NodeStatus.HEALTHY.value == "healthy"
        assert NodeStatus.DEGRADED.value == "degraded"
        assert NodeStatus.UNHEALTHY.value == "unhealthy"
        assert NodeStatus.OFFLINE.value == "offline"


class TestNodeInfo:
    """节点信息数据类测试"""

    def test_node_info_basic(self):
        """测试节点信息基本属性"""
        node = NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north")
        assert node.id == "node_001"
        assert node.host == "localhost"
        assert node.port == 8080
        assert node.region == "cn-north"
        assert node.status == NodeStatus.HEALTHY
        assert node.weight == 1.0

    def test_node_info_to_dict(self):
        """测试节点信息转换为字典"""
        node = NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north")
        node_dict = node.to_dict()
        assert node_dict["id"] == "node_001"
        assert node_dict["host"] == "localhost"
        assert node_dict["port"] == 8080
        assert node_dict["region"] == "cn-north"
        assert node_dict["status"] == "healthy"

    def test_node_info_with_metadata(self):
        """测试带元数据的节点"""
        node = NodeInfo(
            id="node_001",
            host="localhost",
            port=8080,
            region="cn-north",
            metadata={"zone": "zone-a", "instance_type": "c5.large"},
        )
        assert node.metadata["zone"] == "zone-a"
        assert node.metadata["instance_type"] == "c5.large"


class TestHealthCheckConfig:
    """健康检查配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = HealthCheckConfig()
        assert config.interval_seconds == 10.0
        assert config.timeout_seconds == 5.0
        assert config.unhealthy_threshold == 3
        assert config.healthy_threshold == 2
        assert config.degraded_threshold_ms == 500.0

    def test_custom_config(self):
        """测试自定义配置"""
        config = HealthCheckConfig(
            interval_seconds=5.0,
            timeout_seconds=3.0,
            unhealthy_threshold=5,
            healthy_threshold=3,
            degraded_threshold_ms=1000.0,
        )
        assert config.interval_seconds == 5.0
        assert config.unhealthy_threshold == 5
        assert config.degraded_threshold_ms == 1000.0


class TestHealthChecker:
    """健康检查器集成测试"""

    def test_register_node(self):
        """测试注册节点"""
        checker = HealthChecker()
        node = NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north")
        checker.register_node(node)

        nodes = checker.get_all_nodes()
        assert "node_001" in nodes

    def test_unregister_node(self):
        """测试注销节点"""
        checker = HealthChecker()
        node = NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north")
        checker.register_node(node)
        checker.unregister_node("node_001")

        nodes = checker.get_all_nodes()
        assert "node_001" not in nodes

    def test_get_healthy_nodes(self):
        """测试获取健康节点"""
        checker = HealthChecker()

        healthy_node = NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north")
        degraded_node = NodeInfo(id="node_002", host="localhost", port=8081, region="cn-north", status=NodeStatus.DEGRADED)
        unhealthy_node = NodeInfo(id="node_003", host="localhost", port=8082, region="cn-north", status=NodeStatus.UNHEALTHY)
        offline_node = NodeInfo(id="node_004", host="localhost", port=8083, region="cn-north", status=NodeStatus.OFFLINE)

        checker.register_node(healthy_node)
        checker.register_node(degraded_node)
        checker.register_node(unhealthy_node)
        checker.register_node(offline_node)

        healthy_nodes = checker.get_healthy_nodes()
        assert len(healthy_nodes) == 2
        assert healthy_node in healthy_nodes
        assert degraded_node in healthy_nodes

    def test_add_status_callback(self):
        """测试添加状态变更回调"""
        checker = HealthChecker()
        callback = MagicMock()
        checker.add_status_callback(callback)

        assert callback in checker._callbacks


class TestLoadBalancer:
    """负载均衡器集成测试"""

    def test_round_robin_strategy(self):
        """测试轮询策略"""
        lb = LoadBalancer(strategy="round_robin")
        nodes = [
            NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north"),
            NodeInfo(id="node_002", host="localhost", port=8081, region="cn-north"),
            NodeInfo(id="node_003", host="localhost", port=8082, region="cn-north"),
        ]

        node1 = lb.select_node(nodes)
        node2 = lb.select_node(nodes)
        node3 = lb.select_node(nodes)
        node4 = lb.select_node(nodes)

        assert node1.id == "node_001"
        assert node2.id == "node_002"
        assert node3.id == "node_003"
        assert node4.id == "node_001"

    def test_weighted_round_robin_strategy(self):
        """测试加权轮询策略"""
        lb = LoadBalancer(strategy="weighted_round_robin")
        nodes = [
            NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north", weight=3.0),
            NodeInfo(id="node_002", host="localhost", port=8081, region="cn-north", weight=2.0),
            NodeInfo(id="node_003", host="localhost", port=8082, region="cn-north", weight=1.0),
        ]

        # 多次选择验证权重分配
        selections = [lb.select_node(nodes).id for _ in range(100)]
        assert "node_001" in selections
        assert "node_002" in selections
        assert "node_003" in selections

    def test_least_connections_strategy(self):
        """测试最少连接策略"""
        lb = LoadBalancer(strategy="least_connections")
        nodes = [
            NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north"),
            NodeInfo(id="node_002", host="localhost", port=8081, region="cn-north"),
        ]

        # 模拟请求
        lb.record_request("node_001")
        lb.record_request("node_001")

        # 应该选择连接数最少的节点
        node = lb.select_node(nodes)
        assert node.id == "node_002"

    def test_random_strategy(self):
        """测试随机策略"""
        lb = LoadBalancer(strategy="random")
        nodes = [
            NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north"),
            NodeInfo(id="node_002", host="localhost", port=8081, region="cn-north"),
        ]

        selections = [lb.select_node(nodes).id for _ in range(10)]
        assert len(set(selections)) > 1

    def test_latency_based_strategy(self):
        """测试基于延迟策略"""
        lb = LoadBalancer(strategy="latency_based")
        nodes = [
            NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north", latency_ms=100.0),
            NodeInfo(id="node_002", host="localhost", port=8081, region="cn-north", latency_ms=50.0),
        ]

        node = lb.select_node(nodes)
        assert node.id == "node_002"

    def test_record_request_completion(self):
        """测试请求记录和完成"""
        lb = LoadBalancer()
        lb.record_request("node_001")
        lb.record_request("node_001")

        assert lb._request_counts["node_001"] == 2

        lb.record_completion("node_001")
        assert lb._request_counts["node_001"] == 1

    def test_empty_nodes(self):
        """测试空节点列表"""
        lb = LoadBalancer()
        result = lb.select_node([])
        assert result is None


class TestFailoverManager:
    """故障转移管理器集成测试"""

    def test_failover_count(self):
        """测试故障转移计数"""
        checker = HealthChecker()
        lb = LoadBalancer()
        failover = FailoverManager(checker, lb)

        stats = failover.get_stats()
        assert stats["failover_count"] == 0
        assert stats["recovery_count"] == 0

    def test_handle_failover(self):
        """测试处理故障转移"""
        checker = HealthChecker()
        lb = LoadBalancer()
        failover = FailoverManager(checker, lb)

        node = NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north")
        checker.register_node(node)

        # 触发故障转移
        asyncio.run(failover._handle_failover(node))

        stats = failover.get_stats()
        assert stats["failover_count"] == 1
        assert node.weight == 0.0

    def test_handle_recovery(self):
        """测试处理节点恢复"""
        checker = HealthChecker()
        lb = LoadBalancer()
        failover = FailoverManager(checker, lb)

        node = NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north", weight=0.0)
        checker.register_node(node)

        # 触发恢复
        asyncio.run(failover._handle_recovery(node))

        stats = failover.get_stats()
        assert stats["recovery_count"] == 1
        assert node.weight == 1.0


class TestMultiActiveDeployer:
    """多活部署管理器集成测试"""

    def test_add_region(self):
        """测试添加区域"""
        deployer = MultiActiveDeployer()
        nodes = [
            NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north"),
            NodeInfo(id="node_002", host="localhost", port=8081, region="cn-north"),
        ]

        deployer.add_region("cn-north", nodes)

        stats = deployer.get_deployment_stats()
        assert "cn-north" in stats["regions"]
        assert stats["regions"]["cn-north"]["total_nodes"] == 2

    def test_remove_region(self):
        """测试移除区域"""
        deployer = MultiActiveDeployer()
        nodes = [
            NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north"),
        ]

        deployer.add_region("cn-north", nodes)
        deployer.remove_region("cn-north")

        stats = deployer.get_deployment_stats()
        assert "cn-north" not in stats["regions"]

    def test_get_node_for_request(self):
        """测试获取处理请求的节点"""
        deployer = MultiActiveDeployer()
        nodes = [
            NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north"),
            NodeInfo(id="node_002", host="localhost", port=8081, region="cn-north"),
        ]

        deployer.add_region("cn-north", nodes)

        node = deployer.get_node_for_request("cn-north")
        assert node is not None
        assert node.id in ["node_001", "node_002"]

    def test_get_node_for_request_no_region(self):
        """测试不带区域获取节点"""
        deployer = MultiActiveDeployer()
        nodes = [
            NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north"),
        ]

        deployer.add_region("cn-north", nodes)

        node = deployer.get_node_for_request()
        assert node is not None

    def test_get_deployment_stats(self):
        """测试获取部署统计"""
        deployer = MultiActiveDeployer()
        nodes = [
            NodeInfo(id="node_001", host="localhost", port=8080, region="cn-north"),
            NodeInfo(id="node_002", host="localhost", port=8081, region="cn-north"),
        ]

        deployer.add_region("cn-north", nodes)

        stats = deployer.get_deployment_stats()
        assert "regions" in stats
        assert "failover" in stats
        assert stats["regions"]["cn-north"]["total_nodes"] == 2
        assert stats["regions"]["cn-north"]["healthy_nodes"] == 2