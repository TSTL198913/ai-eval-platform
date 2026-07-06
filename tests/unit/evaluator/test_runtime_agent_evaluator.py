"""RuntimeAgentEvaluator 单元测试"""

import pytest
from unittest.mock import MagicMock, patch

from src.domain.evaluators.runtime_agent_evaluator import RuntimeAgentEvaluator
from src.schemas.evaluation import EvaluationSchema
from src.schemas.evaluation import EvaluatorStatus


class TestRuntimeAgentEvaluatorPositiveCases:
    """正向测试用例"""

    def test_run_react_mode(self):
        """运行 ReAct 模式"""
        evaluator = RuntimeAgentEvaluator()
        request = EvaluationSchema(
            id="test_case_001",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "解决一个简单问题",
                "max_steps": 5,
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "metrics_breakdown" in response.data
        assert "mode" in response.data
        assert response.data["mode"] == "react"

    def test_run_plan_execute_mode(self):
        """运行 Plan-and-Execute 模式"""
        evaluator = RuntimeAgentEvaluator()
        request = EvaluationSchema(
            id="test_case_002",
            type="runtime_agent",
            payload={
                "action": "run_plan_execute",
                "task": "完成一个复杂任务",
                "max_steps": 5,
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.data["mode"] == "plan_execute"

    def test_run_agent_auto_mode_short_task(self):
        """自动模式 - 短任务使用 ReAct"""
        evaluator = RuntimeAgentEvaluator()
        request = EvaluationSchema(
            id="test_case_003",
            type="runtime_agent",
            payload={
                "action": "run_agent",
                "task": "简单任务",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.data["mode"] == "react"

    def test_run_agent_auto_mode_long_task(self):
        """自动模式 - 长任务使用 Plan-and-Execute"""
        evaluator = RuntimeAgentEvaluator()
        long_task = "这是一个非常长的任务描述，包含很多内容，需要详细的规划和执行步骤来完成这个复杂的任务。" * 3
        request = EvaluationSchema(
            id="test_case_004",
            type="runtime_agent",
            payload={
                "action": "run_agent",
                "task": long_task,
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.data["mode"] == "plan_execute"

    def test_get_agent_state(self):
        """获取 Agent 状态"""
        evaluator = RuntimeAgentEvaluator()
        from src.domain.agents.runtime_framework import AgentState
        test_state = AgentState(task="测试任务")
        evaluator._agents["test_agent"] = test_state

        request = EvaluationSchema(
            id="test_case_005",
            type="runtime_agent",
            payload={
                "action": "get_state",
                "agent_id": "test_agent",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "state" in response.data

    def test_list_tools(self):
        """列出工具"""
        evaluator = RuntimeAgentEvaluator()
        request = EvaluationSchema(
            id="test_case_006",
            type="runtime_agent",
            payload={
                "action": "list_tools",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "tools" in response.data
        assert "count" in response.data

    def test_custom_weights(self):
        """自定义权重"""
        evaluator = RuntimeAgentEvaluator()
        request = EvaluationSchema(
            id="test_case_007",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试任务",
                "max_steps": 5,
            },
            metadata={
                "weight_completion": 0.6,
                "weight_efficiency": 0.2,
                "weight_tool": 0.2,
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "weights_applied" in response.data


class TestRuntimeAgentEvaluatorNegativeCases:
    """负向测试用例"""

    def test_run_agent_without_task(self):
        """运行 Agent 缺少任务"""
        evaluator = RuntimeAgentEvaluator()
        request = EvaluationSchema(
            id="test_case_008",
            type="runtime_agent",
            payload={
                "action": "run_react",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.ERROR
        assert "task" in response.error

    def test_get_nonexistent_agent_state(self):
        """获取不存在的 Agent 状态"""
        evaluator = RuntimeAgentEvaluator()
        request = EvaluationSchema(
            id="test_case_009",
            type="runtime_agent",
            payload={
                "action": "get_state",
                "agent_id": "nonexistent",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.ERROR
        assert "未找到" in response.error

    def test_unknown_action(self):
        """未知动作"""
        evaluator = RuntimeAgentEvaluator()
        request = EvaluationSchema(
            id="test_case_010",
            type="runtime_agent",
            payload={
                "action": "unknown_action",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.ERROR
        assert "未知的评测Action指令" in response.error

    def test_run_react_max_steps_reached(self):
        """ReAct 模式达到最大步数"""
        evaluator = RuntimeAgentEvaluator()
        request = EvaluationSchema(
            id="test_case_011",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "长时间运行的任务",
                "max_steps": 2,
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "runtime_state" in response.data

    def test_run_plan_execute_without_task(self):
        """Plan-and-Execute 模式缺少任务"""
        evaluator = RuntimeAgentEvaluator()
        request = EvaluationSchema(
            id="test_case_012",
            type="runtime_agent",
            payload={
                "action": "run_plan_execute",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.ERROR


class TestRuntimeAgentEvaluatorBoundaryCases:
    """边界测试用例"""

    def test_empty_task(self):
        """空任务"""
        evaluator = RuntimeAgentEvaluator()
        request = EvaluationSchema(
            id="test_case_013",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.ERROR

    def test_single_step_agent(self):
        """单步 Agent"""
        evaluator = RuntimeAgentEvaluator()
        request = EvaluationSchema(
            id="test_case_014",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "简单任务",
                "max_steps": 1,
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.data["runtime_state"]["current_step"] == 1

    def test_zero_max_steps(self):
        """零步最大步数"""
        evaluator = RuntimeAgentEvaluator()
        request = EvaluationSchema(
            id="test_case_015",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "任务",
                "max_steps": 0,
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS

    def test_custom_tools(self):
        """自定义工具列表"""
        evaluator = RuntimeAgentEvaluator()
        request = EvaluationSchema(
            id="test_case_016",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "使用自定义工具",
                "tools": ["search", "calculator"],
                "max_steps": 3,
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "trajectory" in response.data


class TestRuntimeAgentEvaluatorIntegration:
    """集成测试用例"""

    def test_evaluator_registered_in_factory(self):
        """评估器应在工厂中注册"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        assert "runtime_agent" in EvaluatorFactory._registry

    def test_async_evaluate(self):
        """异步评估"""
        import asyncio

        evaluator = RuntimeAgentEvaluator()
        request = EvaluationSchema(
            id="test_case_017",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "异步测试任务",
            },
        )
        response = asyncio.run(evaluator.evaluate_async(request))

        assert response.evaluation_status == EvaluatorStatus.SUCCESS

    def test_cache_cleanup(self):
        """缓存清理"""
        evaluator = RuntimeAgentEvaluator()
        evaluator._max_cache_size = 2

        from src.domain.agents.runtime_framework import AgentState
        for i in range(5):
            evaluator._agents[f"agent_{i}"] = AgentState(task=f"任务{i}")
        
        request = EvaluationSchema(
            id="test_cache",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试任务",
            },
        )
        evaluator.safe_evaluate(request)

        assert len(evaluator._agents) <= evaluator._max_cache_size

    def test_tool_registry_integration(self):
        """工具注册集成"""
        evaluator = RuntimeAgentEvaluator()
        assert evaluator._tool_registry is not None

    def test_error_handling(self):
        """错误处理"""
        evaluator = RuntimeAgentEvaluator()
        evaluator._run_react = MagicMock(side_effect=Exception("测试异常"))
        request = EvaluationSchema(
            id="test_case_018",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试任务",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.ERROR
        assert "AGENT_RUNTIME_ERROR" in response.metadata.get("error_code", "")
