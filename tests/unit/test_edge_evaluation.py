"""测试 src/infra/edge_evaluation.py - 边缘评测模块"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.infra.edge_evaluation import (
    EdgeEvaluation,
    EdgeEvaluator,
    EdgeNode,
)


class TestEdgeNode:
    """测试边缘节点"""

    def test_creation_defaults(self):
        """测试默认属性"""
        node = EdgeNode(
            node_id="edge-1",
            location="beijing",
            region="cn-north",
            capacity=10,
        )
        assert node.current_load == 0
        assert node.latency_to_origin_ms == 50.0
        assert node.is_online is True
        assert node.last_sync == 0.0
        assert node.metadata == {}

    def test_can_accept_online_under_capacity(self):
        """测试在线且未满时可以接受"""
        node = EdgeNode(
            node_id="edge-1", location="beijing", region="cn-north", capacity=10, current_load=5
        )
        assert node.can_accept() is True

    def test_can_accept_full_capacity(self):
        """测试满载时不能接受"""
        node = EdgeNode(
            node_id="edge-1", location="beijing", region="cn-north", capacity=10, current_load=10
        )
        assert node.can_accept() is False

    def test_can_accept_offline(self):
        """测试离线时不能接受"""
        node = EdgeNode(
            node_id="edge-1",
            location="beijing",
            region="cn-north",
            capacity=10,
            is_online=False,
        )
        assert node.can_accept() is False

    def test_get_load_ratio_normal(self):
        """测试正常负载比例"""
        node = EdgeNode(
            node_id="edge-1", location="beijing", region="cn-north", capacity=10, current_load=5
        )
        assert node.get_load_ratio() == 0.5

    def test_get_load_ratio_zero_capacity(self):
        """测试容量为0时返回0"""
        node = EdgeNode(
            node_id="edge-1", location="beijing", region="cn-north", capacity=0, current_load=0
        )
        assert node.get_load_ratio() == 0.0


class TestEdgeEvaluation:
    """测试边缘评测任务"""

    def test_creation_defaults(self):
        """测试默认属性"""
        task = EdgeEvaluation(
            task_id="task-1",
            model="gpt-4",
            dataset="mmlu",
            metrics=["accuracy"],
            edge_node_id="edge-1",
        )
        assert task.status == "pending"
        assert task.started_at is None
        assert task.completed_at is None
        assert task.result is None
        assert task.latency_ms is None
        assert task.created_at > 0

    def test_creation_with_result(self):
        """测试带结果的创建"""
        task = EdgeEvaluation(
            task_id="task-1",
            model="gpt-4",
            dataset="mmlu",
            metrics=["accuracy"],
            edge_node_id="edge-1",
            status="completed",
            result={"accuracy": 0.95},
            latency_ms=120.0,
        )
        assert task.status == "completed"
        assert task.result["accuracy"] == 0.95
        assert task.latency_ms == 120.0


class TestEdgeEvaluator:
    """测试边缘评测器"""

    @pytest.fixture
    def nodes(self):
        return [
            EdgeNode(node_id="edge-1", location="beijing", region="cn-north", capacity=10),
            EdgeNode(node_id="edge-2", location="shanghai", region="cn-east", capacity=5),
            EdgeNode(node_id="edge-3", location="beijing", region="cn-north", capacity=8),
        ]

    @pytest.fixture
    def evaluator(self, nodes):
        return EdgeEvaluator(nodes)

    def test_select_best_node_with_location(self, evaluator):
        """测试按位置选择最佳节点"""
        node = evaluator.select_best_node(user_location="beijing")
        assert node is not None
        assert node.location == "beijing"

    def test_select_best_node_without_location(self, evaluator):
        """测试无位置时选择负载最低"""
        # edge-1: load=0, edge-2: load=0, edge-3: load=0
        # 先增加一些负载
        evaluator._nodes["edge-1"].current_load = 5
        evaluator._nodes["edge-2"].current_load = 1
        evaluator._nodes["edge-3"].current_load = 8

        node = evaluator.select_best_node()
        assert node is not None
        # edge-2 负载比例最低 1/5=0.2
        assert node.node_id == "edge-2"

    def test_select_best_node_no_available(self, evaluator):
        """测试无可用节点时返回 None"""
        for n in evaluator._nodes.values():
            n.is_online = False

        assert evaluator.select_best_node() is None

    def test_select_best_node_all_full(self, evaluator):
        """测试全部满载时返回 None"""
        for n in evaluator._nodes.values():
            n.current_load = n.capacity

        assert evaluator.select_best_node() is None

    @pytest.mark.asyncio
    async def test_submit_evaluation_success(self, evaluator):
        """测试成功提交评测"""
        with patch.object(evaluator, "_run_local_evaluation", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = {"accuracy": 0.95}

            task = await evaluator.submit_evaluation(
                model="gpt-4",
                dataset="mmlu",
                metrics=["accuracy"],
                user_location="beijing",
            )

            assert task is not None
            assert task.model == "gpt-4"
            assert task.dataset == "mmlu"
            assert task.edge_node_id in ["edge-1", "edge-3"]  # beijing 节点
            assert evaluator._nodes[task.edge_node_id].current_load >= 1

    @pytest.mark.asyncio
    async def test_submit_evaluation_no_nodes(self, evaluator):
        """测试无可用节点时返回 None"""
        for n in evaluator._nodes.values():
            n.is_online = False

        task = await evaluator.submit_evaluation(
            model="gpt-4",
            dataset="mmlu",
            metrics=["accuracy"],
        )

        assert task is None

    @pytest.mark.asyncio
    async def test_get_result_completed(self, evaluator):
        """测试获取已完成任务结果"""
        with patch.object(evaluator, "_run_local_evaluation", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = {"score": 0.9}

            task = await evaluator.submit_evaluation(
                model="gpt-4",
                dataset="mmlu",
                metrics=["accuracy"],
            )

            # 等待异步任务完成
            await asyncio.sleep(0.1)

            # 已完成任务应能获取
            result = await evaluator.get_result(task.task_id)
            assert result is not None
            assert result.task_id == task.task_id

    @pytest.mark.asyncio
    async def test_get_result_not_found(self, evaluator):
        """测试获取不存在的任务"""
        result = await evaluator.get_result("non-existent")
        assert result is None

    def test_get_edge_stats(self, evaluator):
        """测试获取边缘节点统计"""
        stats = evaluator.get_edge_stats()

        assert "total_nodes" in stats
        assert stats["total_nodes"] == 3
        assert "online_nodes" in stats
        assert "pending_tasks" in stats
        assert "completed_tasks" in stats
        assert "nodes" in stats
        assert len(stats["nodes"]) == 3

    def test_get_edge_stats_after_load_change(self, evaluator):
        """测试负载变化后统计更新"""
        evaluator._nodes["edge-1"].current_load = 5
        evaluator._nodes["edge-1"].is_online = False

        stats = evaluator.get_edge_stats()
        assert stats["total_nodes"] == 3
        assert stats["online_nodes"] == 2
        node_stats = next(n for n in stats["nodes"] if n["node_id"] == "edge-1")
        assert node_stats["load"] == 5
        assert node_stats["load_ratio"] == 0.5

    @pytest.mark.asyncio
    async def test_execute_evaluation_completes(self, evaluator):
        """测试评测执行完成"""
        with patch.object(evaluator, "_run_local_evaluation", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = {"score": 0.88}

            task = EdgeEvaluation(
                task_id="test-task",
                model="gpt-4",
                dataset="mmlu",
                metrics=["accuracy"],
                edge_node_id="edge-1",
            )

            await evaluator._execute_evaluation(task)

            assert task.status == "completed"
            assert task.result == {"score": 0.88}
            assert task.latency_ms is not None
            assert task.completed_at is not None
            assert "test-task" in evaluator._completed_tasks
            assert "test-task" not in evaluator._pending_tasks

    @pytest.mark.asyncio
    async def test_execute_evaluation_failure(self, evaluator):
        """测试评测执行失败：结果包含错误信息"""
        with patch.object(evaluator, "_run_local_evaluation", new_callable=AsyncMock) as mock_eval:
            mock_eval.side_effect = Exception("evaluation error")

            task = EdgeEvaluation(
                task_id="test-task",
                model="gpt-4",
                dataset="mmlu",
                metrics=["accuracy"],
                edge_node_id="edge-1",
            )

            await evaluator._execute_evaluation(task)

            # 实现将错误放入 result
            assert task.result is not None
            assert "error" in task.result
            assert "evaluation error" in task.result["error"]
            assert task.status == "failed"

    @pytest.mark.asyncio
    async def test_execute_evaluation_node_not_found(self, evaluator):
        """测试节点不存在时评测失败"""
        task = EdgeEvaluation(
            task_id="test-task",
            model="gpt-4",
            dataset="mmlu",
            metrics=["accuracy"],
            edge_node_id="non-existent",
        )

        await evaluator._execute_evaluation(task)
        # 应直接返回，不改变状态
        assert task.status == "pending"
