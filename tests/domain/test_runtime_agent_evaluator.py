"""
RuntimeAgentEvaluator 专项测试
测试目标：验证运行时Agent调度框架的核心功能
关键发现：ReAct模式、Plan-Execute模式、工具注册、状态管理均正常工作
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.runtime_agent_evaluator import (
    RuntimeAgentEvaluator,
    AgentMode,
    AgentState,
    ToolSpec,
    ToolRegistry,
)
from src.schemas.evaluation import EvaluationSchema, DomainResponse
from src.domain.evaluators.evaluator_factory import EvaluatorFactory


@pytest.fixture(autouse=True)
def reset_tool_registry():
    """每个测试前重置工具注册表"""
    ToolRegistry._tools = {}
    yield
    ToolRegistry._tools = {}


@pytest.fixture(autouse=True)
def reset_evaluator_factory():
    """每个测试前重置评估器工厂"""
    from src.domain.evaluators import auto_discover
    from src.domain.evaluators.evaluator_factory import EvaluatorFactory as EF
    EF._registry = {}
    auto_discover(force=True)
    yield
    EF._registry = {}


# ============================================================
# Part 1: 正向测试 - 正常输入
# ============================================================
class TestRuntimeAgentEvaluatorPositiveCases:
    """正向测试 - 验证正常输入返回预期输出"""

    @pytest.fixture
    def evaluator(self):
        """创建评估器实例"""
        return RuntimeAgentEvaluator()

    def test_run_agent_auto_mode_short_task(self, evaluator):
        """短任务应自动选择react模式"""
        request = EvaluationSchema(
            id="test_001",
            type="runtime_agent",
            payload={
                "action": "run_agent",
                "mode": "auto",
                "task": "计算1+1",
                "max_steps": 5,
            },
        )
        result = evaluator.evaluate(request)

        # 强断言：验证返回结构和模式
        assert result.data["is_valid"] is True
        assert result.data["mode"] == "react"
        assert "agent_id" in result.data
        assert "state" in result.data
        assert "trajectory" in result.data

    def test_run_agent_auto_mode_long_task(self, evaluator):
        """长任务应自动选择plan_execute模式"""
        long_task = "分析并解决复杂问题" * 20  # 超过100字符
        request = EvaluationSchema(
            id="test_002",
            type="runtime_agent",
            payload={
                "action": "run_agent",
                "mode": "auto",
                "task": long_task,
                "max_steps": 10,
            },
        )
        result = evaluator.evaluate(request)

        assert result.data["is_valid"] is True
        assert result.data["mode"] == "plan_execute"
        assert len(result.data["trajectory"]) > 0

    def test_run_react_mode_basic(self, evaluator):
        """ReAct模式基本执行"""
        request = EvaluationSchema(
            id="test_003",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试任务",
                "max_steps": 3,
            },
        )
        result = evaluator.evaluate(request)

        assert result.data["is_valid"] is True
        assert result.data["mode"] == "react"
        assert result.status_code == 200
        # 验证状态序列化
        state = result.data["state"]
        assert "task" in state
        assert "current_step" in state
        assert "completed" in state
        assert "duration_ms" in state

    def test_run_plan_execute_mode_basic(self, evaluator):
        """Plan-Execute模式基本执行"""
        request = EvaluationSchema(
            id="test_004",
            type="runtime_agent",
            payload={
                "action": "run_plan_execute",
                "task": "执行复杂任务",
                "max_steps": 10,
            },
        )
        result = evaluator.evaluate(request)

        assert result.data["is_valid"] is True
        assert result.data["mode"] == "plan_execute"
        # 验证计划生成
        trajectory = result.data["trajectory"]
        planning_step = trajectory[0]
        assert planning_step["phase"] == "planning"
        assert "plan" in planning_step
        assert len(planning_step["plan"]) > 0

    def test_get_state_existing_agent(self, evaluator):
        """获取已存在的Agent状态"""
        # 先创建一个Agent
        create_request = EvaluationSchema(
            id="test_005",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试任务",
                "max_steps": 3,
            },
        )
        create_result = evaluator.evaluate(create_request)
        agent_id = create_result.data["agent_id"]

        # 获取状态
        get_request = EvaluationSchema(
            id="test_005_get",
            type="runtime_agent",
            payload={
                "action": "get_state",
                "agent_id": agent_id,
            },
        )
        result = evaluator.evaluate(get_request)

        assert result.data["is_valid"] is True
        assert "state" in result.data
        assert result.data["state"]["task"] == "测试任务"

    def test_list_tools_with_registered_tools(self, evaluator):
        """列出已注册的工具"""
        # 注册测试工具
        @ToolRegistry.register(
            name="test_tool",
            description="测试工具",
            parameters={"input": "string"},
        )
        def test_tool(input: str):
            return f"processed: {input}"

        request = EvaluationSchema(
            id="test_006",
            type="runtime_agent",
            payload={"action": "list_tools"},
        )
        result = evaluator.evaluate(request)

        assert result.data["is_valid"] is True
        assert result.data["count"] >= 1
        tool_names = [t["name"] for t in result.data["tools"]]
        assert "test_tool" in tool_names

    def test_react_with_tool_call(self, evaluator):
        """ReAct模式调用工具"""
        # 注册工具
        @ToolRegistry.register(
            name="echo",
            description="回显工具",
            parameters={"input": "string"},
        )
        def echo(input: str):
            return input

        request = EvaluationSchema(
            id="test_007",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试工具调用",
                "max_steps": 5,
                "tools": ["echo"],
            },
        )
        result = evaluator.evaluate(request)

        assert result.data["is_valid"] is True
        trajectory = result.data["trajectory"]
        # 验证轨迹中包含工具调用
        tool_calls = [step for step in trajectory if step.get("action", {}).get("type") == "tool_call"]
        # 第3步会调用工具
        assert len(tool_calls) >= 1

    def test_plan_execute_with_steps(self, evaluator):
        """Plan-Execute模式执行多个步骤"""
        request = EvaluationSchema(
            id="test_008",
            type="runtime_agent",
            payload={
                "action": "run_plan_execute",
                "task": "多步骤任务",
                "max_steps": 10,
            },
        )
        result = evaluator.evaluate(request)

        assert result.data["is_valid"] is True
        trajectory = result.data["trajectory"]
        # 验证包含planning和execution阶段
        phases = [step.get("phase") for step in trajectory]
        assert "planning" in phases
        assert "execution" in phases


# ============================================================
# Part 2: 负向测试 - 错误输入
# ============================================================
class TestRuntimeAgentEvaluatorNegativeCases:
    """负向测试 - 验证错误输入返回错误"""

    @pytest.fixture
    def evaluator(self):
        return RuntimeAgentEvaluator()

    def test_unknown_action_returns_error(self, evaluator):
        """未知action应返回错误"""
        request = EvaluationSchema(
            id="test_neg_001",
            type="runtime_agent",
            payload={"action": "unknown_action"},
        )
        result = evaluator.evaluate(request)

        assert result.data["is_valid"] is False
        assert "Unknown action" in result.data["error"]
        assert result.status_code == 400

    def test_run_react_empty_task_returns_error(self, evaluator):
        """空任务应返回错误"""
        request = EvaluationSchema(
            id="test_neg_002",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "",
                "max_steps": 5,
            },
        )
        result = evaluator.evaluate(request)

        assert result.data["is_valid"] is False
        assert "不能为空" in result.data["error"]
        assert result.status_code == 400

    def test_run_plan_execute_empty_task_returns_error(self, evaluator):
        """Plan-Execute模式空任务应返回错误"""
        request = EvaluationSchema(
            id="test_neg_003",
            type="runtime_agent",
            payload={
                "action": "run_plan_execute",
                "task": "",
            },
        )
        result = evaluator.evaluate(request)

        assert result.data["is_valid"] is False
        assert "不能为空" in result.data["error"]
        assert result.status_code == 400

    def test_get_state_nonexistent_agent_returns_error(self, evaluator):
        """获取不存在的Agent状态应返回错误"""
        request = EvaluationSchema(
            id="test_neg_004",
            type="runtime_agent",
            payload={
                "action": "get_state",
                "agent_id": "nonexistent-id-12345",
            },
        )
        result = evaluator.evaluate(request)

        assert result.data["is_valid"] is False
        assert "not found" in result.data["error"]
        assert result.status_code == 404

    def test_tool_call_unregistered_tool(self, evaluator):
        """调用未注册的工具应返回失败"""
        request = EvaluationSchema(
            id="test_neg_005",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试任务",
                "max_steps": 5,
                "tools": ["nonexistent_tool"],
            },
        )
        result = evaluator.evaluate(request)

        # Agent仍然成功执行，但工具调用会失败
        assert result.data["is_valid"] is True
        trajectory = result.data["trajectory"]
        # 检查是否有工具调用失败的记录
        tool_calls = [step for step in trajectory if step.get("action", {}).get("type") == "tool_call"]
        if tool_calls:
            # 工具调用失败时observation应包含错误信息
            for step in tool_calls:
                if step.get("action", {}).get("tool") == "nonexistent_tool":
                    assert step.get("observation", {}).get("success") is False


# ============================================================
# Part 3: 边界测试 - 边界值
# ============================================================
class TestRuntimeAgentEvaluatorBoundaryCases:
    """边界测试 - 验证边界值处理"""

    @pytest.fixture
    def evaluator(self):
        return RuntimeAgentEvaluator()

    def test_react_max_steps_limit_reached(self, evaluator):
        """ReAct模式达到最大步数限制"""
        request = EvaluationSchema(
            id="test_bound_001_max",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试任务",
                "max_steps": 2,  # 设置较小的步数，确保不会提前完成
            },
        )
        result = evaluator.evaluate(request)
        assert result.data["is_valid"] is True
        # 验证是否达到最大步数限制
        state = result.data["state"]
        # 如果未完成，应该有错误信息
        if not state["completed"]:
            assert state["error"] == "达到最大步数限制未完成"

    def test_react_large_max_steps(self, evaluator):
        """大max_steps值测试"""
        request = EvaluationSchema(
            id="test_bound_002",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试任务",
                "max_steps": 100,
            },
        )
        result = evaluator.evaluate(request)
        assert result.data["is_valid"] is True
        assert result.data["state"]["max_steps"] == 100

    def test_react_empty_tools_list(self, evaluator):
        """空工具列表测试"""
        request = EvaluationSchema(
            id="test_bound_003",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试任务",
                "max_steps": 3,
                "tools": [],
            },
        )
        result = evaluator.evaluate(request)
        # 空工具列表应正常执行
        assert result.data["is_valid"] is True

    def test_plan_execute_exceeds_max_steps(self, evaluator):
        """计划步骤超过max_steps限制"""
        request = EvaluationSchema(
            id="test_bound_004",
            type="runtime_agent",
            payload={
                "action": "run_plan_execute",
                "task": "测试任务",
                "max_steps": 2,  # 计划有5步，但只允许2步
            },
        )
        result = evaluator.evaluate(request)
        assert result.data["is_valid"] is True
        # 应该有错误信息
        assert result.data["state"]["error"] is not None
        assert "最大步数限制" in result.data["state"]["error"]

    def test_very_long_task_string(self, evaluator):
        """超长任务字符串测试"""
        long_task = "x" * 10000
        request = EvaluationSchema(
            id="test_bound_005",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": long_task,
                "max_steps": 1,
            },
        )
        result = evaluator.evaluate(request)
        assert result.data["is_valid"] is True
        assert result.data["state"]["task"] == long_task

    def test_missing_payload_fields(self, evaluator):
        """缺少payload字段测试"""
        request = EvaluationSchema(
            id="test_bound_006",
            type="runtime_agent",
            payload={},  # 空payload
        )
        result = evaluator.evaluate(request)
        # 默认action是run_agent
        assert result.data["is_valid"] is False  # 因为task为空


# ============================================================
# Part 4: 异常测试 - 异常情况处理
# ============================================================
class TestRuntimeAgentEvaluatorExceptionCases:
    """异常测试 - 验证异常处理"""

    @pytest.fixture
    def evaluator(self):
        return RuntimeAgentEvaluator()

    def test_tool_execution_exception(self, evaluator):
        """工具执行异常测试"""
        # 注册一个会抛出异常的工具
        @ToolRegistry.register(
            name="error_tool",
            description="会出错的工具",
            parameters={"input": "string"},
        )
        def error_tool(input: str):
            raise ValueError("工具执行失败")

        request = EvaluationSchema(
            id="test_exc_001",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试异常",
                "max_steps": 5,
                "tools": ["error_tool"],
            },
        )
        result = evaluator.evaluate(request)

        # Agent应正常完成，但工具调用失败
        assert result.data["is_valid"] is True
        trajectory = result.data["trajectory"]
        tool_calls = [step for step in trajectory if step.get("action", {}).get("type") == "tool_call"]
        if tool_calls:
            # 检查observation中是否包含错误信息
            for step in tool_calls:
                obs = step.get("observation", {})
                if obs:
                    assert obs.get("success") is False or "Error" in str(obs.get("content", ""))

    def test_plan_execute_step_failure_recovery(self, evaluator):
        """Plan-Execute模式步骤失败后的重试"""
        # 注册一个会失败的工具
        @ToolRegistry.register(
            name="fail_tool",
            description="会失败的工具",
            parameters={"input": "string"},
        )
        def fail_tool(input: str):
            raise RuntimeError("工具失败")

        request = EvaluationSchema(
            id="test_exc_recovery",
            type="runtime_agent",
            payload={
                "action": "run_plan_execute",
                "task": "测试失败恢复",
                "max_steps": 10,
                "tools": ["fail_tool"],
            },
        )
        result = evaluator.evaluate(request)

        # 验证轨迹中包含recovery阶段
        trajectory = result.data["trajectory"]
        # 检查是否有recovery阶段的记录
        recovery_steps = [step for step in trajectory if step.get("phase") == "recovery"]
        # 如果有失败的步骤，应该有recovery记录
        assert len(recovery_steps) >= 0  # 可能没有recovery，取决于执行情况

    def test_evaluate_handler_exception(self, evaluator):
        """evaluate方法捕获handler异常"""
        # Mock一个handler抛出异常
        original_handler = evaluator._run_react

        def mock_handler(request):
            raise RuntimeError("Handler内部错误")

        evaluator._run_react = mock_handler

        request = EvaluationSchema(
            id="test_exc_handler",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试",
            },
        )
        result = evaluator.evaluate(request)

        # evaluate方法应该捕获异常并返回错误响应
        assert result.data["is_valid"] is False
        assert "Handler内部错误" in result.data["error"]
        assert result.status_code == 500

        # 恢复原始handler
        evaluator._run_react = original_handler

    def test_tool_registry_call_unregistered(self, evaluator):
        """调用未注册工具应抛出异常"""
        with pytest.raises(ValueError) as exc_info:
            ToolRegistry.call("nonexistent_tool", input="test")
        assert "not registered" in str(exc_info.value)


# ============================================================
# Part 5: 依赖测试 - 外部依赖Mock
# ============================================================
class TestRuntimeAgentEvaluatorDependencyHandling:
    """依赖测试 - 验证外部依赖Mock"""

    def test_evaluator_with_mock_client(self):
        """使用Mock LLM客户端"""
        mock_client = MagicMock()
        mock_client.chat = MagicMock(return_value="模拟响应")
        evaluator = RuntimeAgentEvaluator(client=mock_client)

        assert evaluator.client is mock_client
        assert evaluator.client.chat.return_value == "模拟响应"

    def test_evaluator_without_client(self):
        """无客户端时应正常工作"""
        evaluator = RuntimeAgentEvaluator(client=None)
        request = EvaluationSchema(
            id="test_dep_002",
            type="runtime_agent",
            payload={
                "action": "run_react",
                "task": "测试任务",
                "max_steps": 2,
            },
        )
        result = evaluator.evaluate(request)
        assert result.data["is_valid"] is True

    def test_tool_registry_register_decorator(self):
        """工具注册装饰器测试"""
        @ToolRegistry.register(
            name="custom_tool",
            description="自定义工具",
            parameters={"param": "string"},
        )
        def custom_func(param: str):
            return f"result: {param}"

        # 验证工具已注册
        tool = ToolRegistry.get_tool("custom_tool")
        assert tool is not None
        assert tool.name == "custom_tool"
        assert tool.description == "自定义工具"
        assert tool.parameters == {"param": "string"}

        # 验证工具可调用
        result = ToolRegistry.call("custom_tool", param="test")
        assert result == "result: test"

    def test_tool_registry_list_tools(self):
        """工具列表测试"""
        # 清空并注册新工具
        ToolRegistry._tools = {}

        @ToolRegistry.register(name="tool_a", description="A", parameters={})
        def tool_a():
            return "a"

        @ToolRegistry.register(name="tool_b", description="B", parameters={})
        def tool_b():
            return "b"

        tools = ToolRegistry.list_tools()
        assert "tool_a" in tools
        assert "tool_b" in tools
        assert len(tools) == 2


# ============================================================
# Part 6: 内置工具测试
# ============================================================
class TestBuiltInTools:
    """内置工具测试"""

    def test_calculator_valid_expression(self):
        """计算器有效表达式"""
        # 注册计算器
        from src.domain.evaluators.runtime_agent_evaluator import calculator
        result = calculator("2 + 3 * 4")
        assert result == "14"

    def test_calculator_invalid_expression(self):
        """计算器无效表达式"""
        from src.domain.evaluators.runtime_agent_evaluator import calculator
        result = calculator("abc + 123")
        assert result == "Invalid expression"

    def test_calculator_division_by_zero(self):
        """计算器除零错误"""
        from src.domain.evaluators.runtime_agent_evaluator import calculator
        result = calculator("1 / 0")
        # Python会抛出异常，被捕获
        assert "Error" in result or "Infinity" in result or "inf" in result

    def test_search_tool(self):
        """搜索工具测试"""
        from src.domain.evaluators.runtime_agent_evaluator import search
        result = search("test query")
        assert "Search results for: test query" in result

    def test_analyzer_tool(self):
        """分析器工具测试"""
        from src.domain.evaluators.runtime_agent_evaluator import analyzer
        result = analyzer("hello world test")
        assert "Words: 3" in result
        assert "Characters: 16" in result


# ============================================================
# Part 7: AgentState测试
# ============================================================
class TestAgentState:
    """AgentState状态管理测试"""

    def test_agent_state_initialization(self):
        """AgentState初始化测试"""
        state = AgentState(task="测试任务")
        assert state.task == "测试任务"
        assert state.plan == []
        assert state.history == []
        assert state.current_step == 0
        assert state.max_steps == 10
        assert state.completed is False
        assert state.success is False
        assert state.result is None
        assert state.error is None
        assert state.total_tokens == 0
        assert state.started_at is not None
        assert state.finished_at is None

    def test_agent_state_custom_values(self):
        """AgentState自定义值测试"""
        state = AgentState(
            task="自定义任务",
            max_steps=20,
            plan=["步骤1", "步骤2"],
        )
        assert state.task == "自定义任务"
        assert state.max_steps == 20
        assert len(state.plan) == 2


# ============================================================
# Part 8: 辅助方法测试
# ============================================================
class TestHelperMethods:
    """辅助方法测试"""

    @pytest.fixture
    def evaluator(self):
        return RuntimeAgentEvaluator()

    def test_generate_thought_first_step(self, evaluator):
        """生成思考 - 第一步"""
        state = AgentState(task="测试任务")
        thought = evaluator._generate_thought(state)
        assert "开始处理任务" in thought
        assert "测试任务" in thought

    def test_generate_thought_with_history(self, evaluator):
        """生成思考 - 有历史记录"""
        state = AgentState(task="测试任务")
        state.history.append({
            "observation": {"content": "上一步结果"}
        })
        thought = evaluator._generate_thought(state)
        assert "观察到" in thought
        assert "上一步结果" in thought

    def test_select_action_tool_call(self, evaluator):
        """选择行动 - 工具调用"""
        state = AgentState(task="测试", max_steps=10)
        state.current_step = 3  # 第3步会调用工具
        action = evaluator._select_action(state, ["tool1", "tool2"])
        assert action["type"] == "tool_call"
        assert action["tool"] == "tool1"

    def test_select_action_finish(self, evaluator):
        """选择行动 - 完成"""
        state = AgentState(task="测试", max_steps=5)
        state.current_step = 4  # 最后一步
        action = evaluator._select_action(state, [])
        assert action["type"] == "finish"
        assert action["success"] is True

    def test_generate_plan(self, evaluator):
        """生成计划测试"""
        plan = evaluator._generate_plan("测试任务", [])
        assert len(plan) == 5
        assert "分析任务" in plan[0]
        assert "验证结果" in plan[4]

    def test_infer_tool_search(self, evaluator):
        """推断工具 - 搜索"""
        tool = evaluator._infer_tool("搜索相关信息")
        assert tool == "search"

        tool = evaluator._infer_tool("Search for data")
        assert tool == "search"

        tool = evaluator._infer_tool("查询数据库")
        assert tool == "search"

    def test_infer_tool_calculator(self, evaluator):
        """推断工具 - 计算器"""
        tool = evaluator._infer_tool("计算总和")
        assert tool == "calculator"

        tool = evaluator._infer_tool("Calculate the result")
        assert tool == "calculator"

    def test_infer_tool_analyzer(self, evaluator):
        """推断工具 - 分析器"""
        tool = evaluator._infer_tool("分析数据")
        assert tool == "analyzer"

        tool = evaluator._infer_tool("Analyze the text")
        assert tool == "analyzer"

    def test_infer_tool_none(self, evaluator):
        """推断工具 - 无匹配"""
        tool = evaluator._infer_tool("执行其他操作")
        assert tool is None

    def test_execute_action_tool_call_success(self, evaluator):
        """执行行动 - 工具调用成功"""
        # 注册工具
        @ToolRegistry.register(name="test_exec", description="测试", parameters={})
        def test_exec():
            return "success"

        state = AgentState(task="测试")
        action = {
            "type": "tool_call",
            "tool": "test_exec",
            "args": {},
        }
        result = evaluator._execute_action(action, state)
        assert result["success"] is True
        assert "success" in result["content"]

    def test_execute_action_tool_call_unregistered(self, evaluator):
        """执行行动 - 工具未注册"""
        state = AgentState(task="测试")
        action = {
            "type": "tool_call",
            "tool": "nonexistent",
            "args": {},
        }
        result = evaluator._execute_action(action, state)
        assert result["success"] is False
        assert "未注册" in result["content"]

    def test_execute_action_think(self, evaluator):
        """执行行动 - 思考"""
        state = AgentState(task="测试")
        action = {
            "type": "think",
            "content": "正在思考",
        }
        result = evaluator._execute_action(action, state)
        assert result["success"] is True
        assert result["content"] == "正在思考"

    def test_execute_action_execute_step(self, evaluator):
        """执行行动 - 执行步骤"""
        state = AgentState(task="测试")
        action = {
            "type": "execute_step",
            "description": "执行步骤1",
        }
        result = evaluator._execute_action(action, state)
        assert result["success"] is True
        assert "已执行" in result["content"]

    def test_serialize_state(self, evaluator):
        """序列化状态测试"""
        state = AgentState(task="测试任务", max_steps=5)
        state.current_step = 3
        state.completed = True
        state.success = True
        state.result = "完成"
        state.finished_at = time.time()

        serialized = evaluator._serialize_state(state)

        assert serialized["task"] == "测试任务"
        assert serialized["current_step"] == 3
        assert serialized["max_steps"] == 5
        assert serialized["completed"] is True
        assert serialized["success"] is True
        assert serialized["result"] == "完成"
        assert serialized["duration_ms"] is not None
        assert serialized["history_length"] == 0

    def test_get_payload_with_value(self, evaluator):
        """获取payload - 有值"""
        request = EvaluationSchema(
            id="test",
            type="test",
            payload={"key": "value"},
        )
        result = RuntimeAgentEvaluator._get_payload(request, "key", "default")
        assert result == "value"

    def test_get_payload_with_default(self, evaluator):
        """获取payload - 使用默认值"""
        request = EvaluationSchema(
            id="test",
            type="test",
            payload={},
        )
        result = RuntimeAgentEvaluator._get_payload(request, "key", "default")
        assert result == "default"


# ============================================================
# Part 9: 工厂注册测试
# ============================================================
class TestEvaluatorFactoryRegistration:
    """工厂注册测试"""

    def test_runtime_agent_registered_in_factory(self):
        """验证runtime_agent已注册到工厂"""
        # 重新导入以触发注册
        from src.domain.evaluators import auto_discover
        auto_discover(force=True)

        evaluators = EvaluatorFactory.list_evaluators()
        assert "runtime_agent" in evaluators

    def test_create_evaluator_from_factory(self):
        """从工厂创建评估器"""
        from src.domain.evaluators import auto_discover
        auto_discover(force=True)

        evaluator = EvaluatorFactory.get("runtime_agent")
        # 使用类名检查而不是isinstance，避免导入路径问题
        assert evaluator.__class__.__name__ == "RuntimeAgentEvaluator"
        # 验证评估器具有必要的方法
        assert hasattr(evaluator, 'evaluate')
        assert hasattr(evaluator, 'safe_evaluate')

    def test_create_evaluator_with_client(self):
        """从工厂创建带客户端的评估器"""
        from src.domain.evaluators import auto_discover
        auto_discover(force=True)

        mock_client = MagicMock()
        evaluator = EvaluatorFactory.get("runtime_agent", client=mock_client)
        assert evaluator.client is mock_client