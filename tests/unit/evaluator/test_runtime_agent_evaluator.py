"""
RuntimeAgentEvaluator 专项测试
测试目标：验证 RuntimeAgentEvaluator 的ReAct和Plan-and-Execute模式
关键发现：评估器支持运行时Agent执行，ReAct模式每3步调用一次工具，Plan-and-Execute先规划后执行
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.agents.runtime_framework import AgentState
from src.domain.evaluators.runtime_agent_evaluator import RuntimeAgentEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestRuntimeAgentEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def target(self):
        return RuntimeAgentEvaluator()

    def test_run_agent_success(self, target):
        """运行Agent应成功"""
        request = EvaluationSchema(
            id="test_001",
            type="runtime_agent",
            payload={
                "action": "run_agent",
                "task": "简单的搜索任务",
                "mode": "react",
                "max_steps": 5,
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert "agent_id" in result.data
        assert "trajectory" in result.data
        
        # 强断言：验证评分、置信度和状态
        assert result.score is not None, "score不应为None"
        assert 0.0 <= result.score <= 1.0, f"score应在0-1之间，实际为{result.score}"
        assert result.confidence is not None, "confidence不应为None"
        assert result.evaluation_status.value == "success", f"evaluation_status应为success"

    def test_run_react_mode_success(self, target):
        """ReAct模式应正确执行"""
        request = EvaluationSchema(
            id="test_002",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "分析数据并给出建议",
                "max_steps": 10,
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["mode"] == "react"
        assert "trajectory" in result.data
        assert len(result.data["trajectory"]) > 0
        
        # 强断言：验证评分、置信度和状态
        assert result.score is not None, "score不应为None"
        assert result.confidence is not None, "confidence不应为None"

    def test_run_plan_execute_mode_success(self, target):
        """Plan-and-Execute模式应正确执行"""
        request = EvaluationSchema(
            id="test_003",
            type="runtime_agent",
            payload={
                "action": "run_plan_execute",
                "task": "完成复杂的数据分析任务",
                "max_steps": 10,
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["mode"] == "plan_execute"
        assert "trajectory" in result.data
        
        # 强断言：验证评分、置信度和状态
        assert result.score is not None, "score不应为None"
        assert result.confidence is not None, "confidence不应为None"

    def test_get_state_existing_agent(self, target):
        """获取已存在Agent状态应成功"""
        # 先运行agent
        run_request = EvaluationSchema(
            id="test_state_run",
            type="runtime_agent",
            payload={
                "action": "run_agent",
                "task": "测试任务",
                "max_steps": 3,
            },
        )
        run_result = target.evaluate(run_request)
        agent_id = run_result.data["agent_id"]

        # 获取状态
        state_request = EvaluationSchema(
            id="test_state",
            type="runtime_agent",
            payload={
                "action": "get_state",
                "agent_id": agent_id,
            },
        )

        result = target.evaluate(state_request)

        assert result.is_valid is True
        assert result.data["state"]["task"] == "测试任务"

    def test_list_tools_success(self, target):
        """列出工具应成功"""
        request = EvaluationSchema(
            id="test_005",
            type="runtime_agent",
            payload={
                "action": "list_tools",
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert "tools" in result.data
        assert result.data["count"] >= 0


class TestRuntimeAgentEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def target(self):
        return RuntimeAgentEvaluator()

    def test_run_agent_empty_task_returns_error(self, target):
        """空task应返回错误"""
        request = EvaluationSchema(
            id="test_006",
            type="runtime_agent",
            payload={
                "action": "run_agent",
                "task": "",
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is False
        assert "task" in result.error.lower()

    def test_run_react_empty_task_returns_error(self, target):
        """ReAct模式空task应返回错误"""
        request = EvaluationSchema(
            id="test_007",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "",
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is False
        assert "task" in result.error.lower()

    def test_run_plan_execute_empty_task_returns_error(self, target):
        """Plan-and-Execute模式空task应返回错误"""
        request = EvaluationSchema(
            id="test_008",
            type="runtime_agent",
            payload={
                "action": "run_plan_execute",
                "task": "",
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is False
        assert "task" in result.error.lower()

    def test_get_state_nonexistent_agent_returns_error(self, target):
        """获取不存在Agent状态应返回错误"""
        request = EvaluationSchema(
            id="test_009",
            type="runtime_agent",
            payload={
                "action": "get_state",
                "agent_id": "nonexistent_agent_id",
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is False
        assert "未找到" in result.error or "not found" in result.error.lower()

    def test_unknown_action_returns_error(self, target):
        """未知action应返回错误"""
        request = EvaluationSchema(
            id="test_010",
            type="runtime_agent",
            payload={
                "action": "unknown_action",
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is False
        assert "action" in result.error.lower()


class TestRuntimeAgentEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def target(self):
        return RuntimeAgentEvaluator()

    def test_max_steps_limit_reached(self, target):
        """达到最大步数应正确处理"""
        request = EvaluationSchema(
            id="test_011",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "需要很多步骤的任务",
                "max_steps": 3,
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        runtime_state = result.data.get("runtime_state", {})
        assert runtime_state.get("current_step") <= 3

    def test_auto_mode_selects_react_for_short_task(self, target):
        """auto模式对短任务应选择react"""
        request = EvaluationSchema(
            id="test_012",
            type="runtime_agent",
            payload={
                "action": "run_agent",
                "task": "简短任务",
                "mode": "auto",
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["mode"] == "react"

    def test_auto_mode_selects_plan_for_long_task(self, target):
        """auto模式对长任务应选择plan_execute"""
        long_task = "a" * 150
        request = EvaluationSchema(
            id="test_013",
            type="runtime_agent",
            payload={
                "action": "run_agent",
                "task": long_task,
                "mode": "auto",
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["mode"] == "plan_execute"

    def test_zero_max_steps_handled(self, target):
        """max_steps为0应正常处理"""
        request = EvaluationSchema(
            id="test_014",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试任务",
                "max_steps": 0,
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True


class TestRuntimeAgentEvaluatorAlgorithmTests:
    """评分算法测试"""

    @pytest.fixture
    def target(self):
        return RuntimeAgentEvaluator()

    def test_react_loop_calls_tool_every_three_steps(self, target):
        """ReAct循环应每3步调用一次工具"""
        request = EvaluationSchema(
            id="test_015",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试任务",
                "max_steps": 10,  # 改为10步，这样step 9可以调用tool
                "tools": ["calculator"],
            },
        )

        result = target.evaluate(request)

        trajectory = result.data["trajectory"]
        tool_calls = [t for t in trajectory if t.get("action", {}).get("type") == "tool_call"]
        # 10步：step 3, 6, 9调用工具 (step 10会检查>=max_steps-1=9而返回finish)
        # 所以应该是3次工具调用
        assert len(tool_calls) == 3

    def test_react_finishes_on_last_step(self, target):
        """ReAct循环应在最后一步返回finish"""
        request = EvaluationSchema(
            id="test_016",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试",
                "max_steps": 5,
            },
        )

        result = target.evaluate(request)

        state = result.data["runtime_state"]
        # 达到最大步数，应标记completed
        if state["current_step"] >= state["max_steps"]:
            assert state["completed"] is True
            assert state["error"] is not None or state["success"] is not None

    def test_plan_execute_generates_plan_first(self, target):
        """Plan-and-Execute应先生成计划"""
        request = EvaluationSchema(
            id="test_017",
            type="runtime_agent",
            payload={
                "action": "run_plan_execute",
                "task": "复杂任务",
                "max_steps": 10,
            },
        )

        result = target.evaluate(request)

        trajectory = result.data["trajectory"]
        # 第一步应是planning阶段
        assert trajectory[0]["phase"] == "planning"
        assert "plan" in trajectory[0]

    def test_state_serialization(self, target):
        """状态序列化应正确"""
        state = AgentState(
            task="测试任务",
            max_steps=5,
        )

        serialized = target._serialize_state(state)

        assert serialized["task"] == "测试任务"
        assert serialized["max_steps"] == 5
        assert "history_length" in serialized

    def test_tool_registry_call_registered_tool(self, target):
        """调用已注册工具应成功"""
        from src.domain.agents.runtime_framework import get_global_tool_registry

        tool_registry = get_global_tool_registry()
        result = tool_registry.call("calculator", input="2+2")

        assert result == "4"

    def test_tool_registry_call_unregistered_tool_returns_error(self, target):
        """调用未注册工具应抛出异常"""
        from src.domain.agents.runtime_framework import get_global_tool_registry

        tool_registry = get_global_tool_registry()
        with pytest.raises(ValueError) as exc_info:
            tool_registry.call("nonexistent_tool", input="test")

        assert "未注册" in str(exc_info.value) or "not registered" in str(exc_info.value)

    def test_select_action_react_logic(self, target):
        """ReAct动作选择逻辑"""
        state = AgentState(task="test", max_steps=10)
        state.current_step = 3

        action = target._select_action(state, ["calculator"])

        assert action["type"] == "tool_call"
        assert action["tool"] == "calculator"

    def test_generate_plan_returns_steps(self, target):
        """生成计划应返回步骤列表"""
        plan = target._generate_plan("分析销售数据", ["search", "calculator"])

        assert len(plan) > 0
        assert isinstance(plan, list)
        assert all(isinstance(step, str) for step in plan)

    def test_infer_tool_from_plan_step(self, target):
        """从计划步骤推断工具"""
        assert target._infer_tool("搜索相关信息") == "search"
        assert target._infer_tool("calculator the result") == "calculator"
        assert target._infer_tool("分析数据") == "analyzer"
        assert target._infer_tool("其他操作") is None
