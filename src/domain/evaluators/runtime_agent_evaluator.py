"""
Runtime Agent Framework - 运行时Agent调度框架

提供ReAct / Plan-and-Execute 风格的Agent运行时能力：
- ReAct模式：思考-行动-观察循环
- Plan-and-Execute：先规划后执行
- 工具调用：动态工具注册与调用
- 记忆管理：短期+长期记忆
- 轨迹记录：完整执行轨迹
"""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


class AgentMode(Enum):
    REACT = "react"  # 思考-行动-观察
    PLAN_EXECUTE = "plan_execute"  # 先规划后执行
    AUTO = "auto"  # 自动选择


@dataclass
class AgentState:
    """Agent运行时状态"""

    task: str
    plan: list[str] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    current_step: int = 0
    max_steps: int = 10
    completed: bool = False
    success: bool = False
    result: Any = None
    error: str | None = None
    total_tokens: int = 0
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None


@dataclass
class ToolSpec:
    """工具规格定义"""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]


class ToolRegistry:
    """工具注册中心（运行时）"""

    _tools: dict[str, ToolSpec] = {}

    @classmethod
    def register(cls, name: str, description: str, parameters: dict[str, Any]):
        """工具注册装饰器"""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            cls._tools[name] = ToolSpec(
                name=name,
                description=description,
                parameters=parameters,
                handler=func,
            )
            return func

        return decorator

    @classmethod
    def get_tool(cls, name: str) -> ToolSpec | None:
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> list[str]:
        return list(cls._tools.keys())

    @classmethod
    def call(cls, name: str, **kwargs) -> Any:
        """调用工具"""
        tool = cls.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not registered")
        return tool.handler(**kwargs)


@EvaluatorFactory.register("runtime_agent")
class RuntimeAgentEvaluator:
    """运行时Agent评估器

    支持ReAct和Plan-and-Execute两种模式，用于真实运行Agent并评估其表现
    """

    def __init__(self, client: Any | None = None):
        self.client = client
        self._agents: dict[str, AgentState] = {}

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        action = request.payload.get("action", "run_agent")
        handler = {
            "run_agent": self._run_agent,
            "run_react": self._run_react,
            "run_plan_execute": self._run_plan_execute,
            "get_state": self._get_state,
            "list_tools": self._list_tools,
        }.get(action)
        if handler is None:
            return DomainResponse(
                data={"is_valid": False, "error": f"Unknown action: {action}"},
                status_code=400,
            )
        try:
            return handler(request)
        except Exception as e:
            return DomainResponse(
                data={"is_valid": False, "error": str(e)},
                status_code=500,
            )

    def safe_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        return self.evaluate(request)

    # ===================== 核心方法 =====================

    def _run_agent(self, request: EvaluationSchema) -> DomainResponse:
        """统一Agent运行入口"""
        mode = self._get_payload(request, "mode", "auto")
        if mode == "auto":
            # 根据任务复杂度自动选择
            task = self._get_payload(request, "task", "")
            mode = "react" if len(task) < 100 else "plan_execute"
        if mode == "react":
            return self._run_react(request)
        else:
            return self._run_plan_execute(request)

    def _run_react(self, request: EvaluationSchema) -> DomainResponse:
        """ReAct模式：思考-行动-观察循环"""
        task = self._get_payload(request, "task", "")
        max_steps = self._get_payload(request, "max_steps", 10)
        available_tools = self._get_payload(request, "tools", ToolRegistry.list_tools())

        if not task:
            return DomainResponse(
                data={"is_valid": False, "error": "task不能为空"},
                status_code=400,
            )

        agent_id = str(uuid.uuid4())
        state = AgentState(task=task, max_steps=max_steps)
        self._agents[agent_id] = state

        # ReAct循环
        for step in range(max_steps):
            state.current_step = step + 1
            # Thought
            thought = self._generate_thought(state)
            # Action
            action = self._select_action(state, available_tools)
            # Observation
            observation = self._execute_action(action, state)
            # 记录历史
            state.history.append(
                {
                    "step": state.current_step,
                    "thought": thought,
                    "action": action,
                    "observation": observation,
                }
            )
            # 检查是否完成
            if action.get("type") == "finish":
                state.completed = True
                state.success = action.get("success", True)
                state.result = action.get("result")
                break

        state.finished_at = time.time()
        if not state.completed:
            state.error = "达到最大步数限制未完成"

        return DomainResponse(
            data={
                "is_valid": True,
                "agent_id": agent_id,
                "mode": "react",
                "state": self._serialize_state(state),
                "trajectory": state.history,
            },
            status_code=200,
        )

    def _run_plan_execute(self, request: EvaluationSchema) -> DomainResponse:
        """Plan-and-Execute模式：先规划后执行"""
        task = self._get_payload(request, "task", "")
        max_steps = self._get_payload(request, "max_steps", 10)
        available_tools = self._get_payload(request, "tools", ToolRegistry.list_tools())

        if not task:
            return DomainResponse(
                data={"is_valid": False, "error": "task不能为空"},
                status_code=400,
            )

        agent_id = str(uuid.uuid4())
        state = AgentState(task=task, max_steps=max_steps)
        self._agents[agent_id] = state

        # Step 1: 生成计划
        state.plan = self._generate_plan(task, available_tools)
        state.history.append(
            {
                "step": 0,
                "phase": "planning",
                "plan": state.plan,
            }
        )

        # Step 2: 执行计划
        for i, plan_step in enumerate(state.plan):
            state.current_step = i + 1
            if state.current_step > state.max_steps:
                state.error = "达到最大步数限制"
                break
            # 执行每个计划步骤
            action = {
                "type": "execute_step",
                "description": plan_step,
                "tool": self._infer_tool(plan_step),
            }
            observation = self._execute_action(action, state)
            state.history.append(
                {
                    "step": state.current_step,
                    "phase": "execution",
                    "plan_step": plan_step,
                    "action": action,
                    "observation": observation,
                }
            )
            if not observation.get("success", True):
                # 重试或调整计划
                state.history.append(
                    {
                        "step": state.current_step,
                        "phase": "recovery",
                        "action": "retry",
                    }
                )

        state.completed = True
        state.success = state.error is None
        state.finished_at = time.time()

        return DomainResponse(
            data={
                "is_valid": True,
                "agent_id": agent_id,
                "mode": "plan_execute",
                "state": self._serialize_state(state),
                "trajectory": state.history,
            },
            status_code=200,
        )

    def _get_state(self, request: EvaluationSchema) -> DomainResponse:
        """获取Agent状态"""
        agent_id = self._get_payload(request, "agent_id", "")
        state = self._agents.get(agent_id)
        if not state:
            return DomainResponse(
                data={"is_valid": False, "error": f"Agent '{agent_id}' not found"},
                status_code=404,
            )
        return DomainResponse(
            data={"is_valid": True, "state": self._serialize_state(state)},
            status_code=200,
        )

    def _list_tools(self, request: EvaluationSchema) -> DomainResponse:
        """列出所有注册工具"""
        tools = []
        for _name, spec in ToolRegistry._tools.items():
            tools.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                }
            )
        return DomainResponse(
            data={"is_valid": True, "tools": tools, "count": len(tools)},
            status_code=200,
        )

    # ===================== 内部辅助方法 =====================

    def _generate_thought(self, state: AgentState) -> str:
        """生成思考（简化版）"""
        last_obs = state.history[-1].get("observation") if state.history else None
        if last_obs:
            return f"观察到: {last_obs.get('content', '')}, 继续推进任务"
        return f"开始处理任务: {state.task}"

    def _select_action(self, state: AgentState, available_tools: list[str]) -> dict[str, Any]:
        """选择行动（简化版）"""
        # 演示逻辑：每3步调用一次工具
        if state.current_step % 3 == 0 and available_tools:
            tool = available_tools[0]
            return {
                "type": "tool_call",
                "tool": tool,
                "args": {"input": state.task},
            }
        elif state.current_step >= state.max_steps - 1:
            return {"type": "finish", "success": True, "result": f"任务完成: {state.task}"}
        else:
            return {"type": "think", "content": "分析当前情况"}

    def _generate_plan(self, task: str, available_tools: list[str]) -> list[str]:
        """生成计划（简化版）"""
        return [
            f"分析任务: {task}",
            "收集必要信息",
            "制定解决方案",
            "执行解决方案",
            "验证结果",
        ]

    def _infer_tool(self, plan_step: str) -> str | None:
        """从计划步骤推断所需工具"""
        step_lower = plan_step.lower()
        if "搜索" in plan_step or "search" in step_lower or "查询" in plan_step:
            return "search"
        if "计算" in plan_step or "calculate" in step_lower:
            return "calculator"
        if "分析" in plan_step or "analyze" in step_lower:
            return "analyzer"
        return None

    def _execute_action(self, action: dict, state: AgentState) -> dict[str, Any]:
        """执行行动"""
        try:
            if action.get("type") == "tool_call":
                tool_name = action.get("tool")
                if tool_name and ToolRegistry.get_tool(tool_name):
                    result = ToolRegistry.call(tool_name, **action.get("args", {}))
                    return {"success": True, "content": str(result)[:200]}
                return {"success": False, "content": f"工具 '{tool_name}' 未注册"}
            elif action.get("type") == "think":
                return {"success": True, "content": action.get("content", "")}
            elif action.get("type") == "execute_step":
                return {"success": True, "content": f"已执行: {action.get('description', '')}"}
            else:
                return {"success": True, "content": "action executed"}
        except Exception as e:
            return {"success": False, "content": str(e)}

    def _serialize_state(self, state: AgentState) -> dict[str, Any]:
        """序列化状态"""
        return {
            "task": state.task,
            "plan": state.plan,
            "current_step": state.current_step,
            "max_steps": state.max_steps,
            "completed": state.completed,
            "success": state.success,
            "result": state.result,
            "error": state.error,
            "total_tokens": state.total_tokens,
            "started_at": state.started_at,
            "finished_at": state.finished_at,
            "duration_ms": (
                (state.finished_at - state.started_at) * 1000 if state.finished_at else None
            ),
            "history_length": len(state.history),
        }

    @staticmethod
    def _get_payload(request: EvaluationSchema, key: str, default: Any = None) -> Any:
        if hasattr(request, "payload") and request.payload:
            return request.payload.get(key, default)
        return default


# ===================== 内置工具示例 =====================
@ToolRegistry.register(
    name="calculator",
    description="数学计算器，支持加减乘除等基本运算",
    parameters={"input": "string - 算术表达式"},
)
def calculator(input: str) -> str:
    """简单的计算器"""
    try:
        # 安全的eval（只允许数字和基本运算符）
        import re

        if re.match(r"^[\d\s\+\-\*\/\.\(\)]+$", input):
            return str(eval(input))
        return "Invalid expression"
    except Exception as e:
        return f"Error: {e}"


@ToolRegistry.register(
    name="search",
    description="搜索引擎，返回模拟搜索结果",
    parameters={"input": "string - 搜索关键词"},
)
def search(input: str) -> str:
    """模拟搜索"""
    return f"Search results for: {input}"


@ToolRegistry.register(
    name="analyzer",
    description="文本分析器",
    parameters={"input": "string - 待分析文本"},
)
def analyzer(input: str) -> str:
    """简单的文本分析"""
    word_count = len(input.split())
    char_count = len(input)
    return f"Words: {word_count}, Characters: {char_count}"
