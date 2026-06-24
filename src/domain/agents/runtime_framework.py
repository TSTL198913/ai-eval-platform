"""
Agent 运行时框架

提供 Agent 状态管理、工具注册、安全表达式求值等核心能力。
"""

import ast
import operator
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentMode(Enum):
    REACT = "react"
    PLAN_EXECUTE = "plan_execute"
    AUTO = "auto"


@dataclass
class AgentState:
    """Agent 运行时状态"""

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
    """线程安全的工具注册中心"""

    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}
        self._lock = threading.Lock()

    def register(self, name: str, description: str, parameters: dict[str, Any]):
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            with self._lock:
                self._tools[name] = ToolSpec(
                    name=name, description=description, parameters=parameters, handler=func
                )
            return func

        return decorator

    def get_tool(self, name: str) -> ToolSpec | None:
        with self._lock:
            return self._tools.get(name)

    def list_tools(self) -> list[str]:
        with self._lock:
            return list(self._tools.keys())

    def call(self, name: str, **kwargs) -> Any:
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"工具 '{name}' 未注册")
        return tool.handler(**kwargs)

    def get_all_tools(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": s.name, "description": s.description, "parameters": s.parameters}
                for s in self._tools.values()
            ]


def safe_eval_math(expression: str) -> float | int:
    """安全的数学表达式求值"""
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }
    safe_functions = {"abs": abs, "round": round, "min": min, "max": max, "pow": pow}

    def eval_node(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, int | float):
                return node.value
            raise ValueError("禁止解析非数值常量")
        elif isinstance(node, ast.BinOp):
            left = eval_node(node.left)
            right = eval_node(node.right)
            op_type = type(node.op)
            if op_type in operators:
                return operators[op_type](left, right)
            raise ValueError(f"不支持的二元运算符 {op_type}")
        elif isinstance(node, ast.UnaryOp):
            operand = eval_node(node.operand)
            op_type = type(node.op)
            if op_type in operators:
                return operators[op_type](operand)
            raise ValueError(f"不支持的一元操作符 {op_type}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name in safe_functions:
                    args = [eval_node(arg) for arg in node.args]
                    return safe_functions[func_name](*args)
                raise ValueError(f"函数 '{func_name}' 未在安全白名单中")
            raise ValueError("拒绝解析复杂的复合函数调用")
        else:
            raise ValueError(f"不允许执行非数学语法的 AST 节点 {type(node)}")

    try:
        tree = ast.parse(expression, mode="eval")
        return eval_node(tree.body)
    except Exception as e:
        raise ValueError(f"数学表达式解析失败: {str(e)}")


_global_tool_registry = ToolRegistry()


def get_global_tool_registry() -> ToolRegistry:
    """获取全局工具注册中心"""
    return _global_tool_registry


@_global_tool_registry.register(
    name="calculator",
    description="安全的数学计算器",
    parameters={"input": "string - 算术表达式"},
)
def calculator(input: str) -> str:
    try:
        return str(safe_eval_math(input))
    except Exception as e:
        return f"计算失败: {str(e)}"


@_global_tool_registry.register(
    name="search", description="搜索引擎仿真", parameters={"input": "string"}
)
def search(input: str) -> str:
    return f"Mock search content for: {input}"


@_global_tool_registry.register(
    name="analyzer", description="文本分析模拟", parameters={"input": "string"}
)
def analyzer(input: str) -> str:
    return f"Words: {len(input.split())}, Chars: {len(input)}"
