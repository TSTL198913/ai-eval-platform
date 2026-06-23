"""
运行时 Agent 评估器

评估 Agent 的任务完成度、步骤效率和工具使用精准度。
"""

import asyncio
import logging
import threading
import time
import uuid
from typing import Any

from src.domain.agents.runtime_framework import (
    AgentState,
    get_global_tool_registry,
)
from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)

DEFAULT_W_COMPLETION = 0.50
DEFAULT_W_EFFICIENCY = 0.25
DEFAULT_W_TOOL = 0.25


@EvaluatorFactory.register("runtime_agent")
class RuntimeAgentEvaluator(BaseEvaluator):
    """运行时 Agent 评估器"""

    def __init__(self, client: Any | None = None) -> None:
        super().__init__(client=client)
        self._agents: dict[str, AgentState] = {}
        self._agents_lock = threading.Lock()
        self._tool_registry = get_global_tool_registry()
        self._max_cache_size = 2000

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """执行 Agent 评估"""
        action = self.get_payload_data(request, "action") or "run_agent"

        with self._agents_lock:
            if len(self._agents) > self._max_cache_size:
                self._agents.clear()

        handler = {
            "run_agent": self._run_agent,
            "run_react": self._run_react,
            "run_plan_execute": self._run_plan_execute,
            "get_state": self._get_state,
            "list_tools": self._list_tools,
        }.get(action)

        if handler is None:
            return self.create_error_response(
                error_message=f"未知的评测Action指令: {action}",
                error_code="INVALID_ACTION",
            )

        try:
            return handler(request)
        except Exception as e:
            logger.exception(f"Agent运行时评测发生错误: {e}")
            return self.create_error_response(
                error_message=f"Agent运行时评测发生错误: {str(e)}",
                error_code="AGENT_RUNTIME_ERROR",
            )

    async def evaluate_async(self, request: EvaluationSchema) -> DomainResponse:
        """异步评估入口"""
        return await asyncio.to_thread(self.evaluate, request)

    def _run_agent(self, request: EvaluationSchema) -> DomainResponse:
        mode = self.get_payload_data(request, "mode") or "auto"
        if mode == "auto":
            task = self.get_payload_data(request, "task") or ""
            mode = "react" if len(task) < 100 else "plan_execute"

        if mode == "react":
            return self._run_react(request)
        return self._run_plan_execute(request)

    def _run_react(self, request: EvaluationSchema) -> DomainResponse:
        """模拟并评估 ReAct 表现"""
        task = self.get_payload_data(request, "task") or ""
        max_steps = self.get_payload_data(request, "max_steps") or 10
        available_tools = (
            self.get_payload_data(request, "tools") or self._tool_registry.list_tools()
        )

        if not task:
            return self.create_error_response(
                error_message="评测核心任务(task)不能为空",
                error_code="MISSING_TASK",
            )

        agent_id = str(uuid.uuid4())
        state = AgentState(task=task, max_steps=max_steps)

        with self._agents_lock:
            self._agents[agent_id] = state

        for step in range(max_steps):
            state.current_step = step + 1
            thought = self._generate_thought(state)
            action = self._select_action(state, available_tools)
            observation = self._execute_action(action, state)

            state.history.append(
                {
                    "step": state.current_step,
                    "thought": thought,
                    "action": action,
                    "observation": observation,
                }
            )

            if action.get("type") == "finish":
                state.completed = True
                state.success = action.get("success", True)
                state.result = action.get("result")
                break

        state.finished_at = time.time()
        if not state.completed:
            state.error = "触及最大边界步数强行熔断"

        return self._calculate_score(agent_id, state, "react", request)

    def _run_plan_execute(self, request: EvaluationSchema) -> DomainResponse:
        """模拟并评估 Plan-and-Execute 表现"""
        task = self.get_payload_data(request, "task") or ""
        max_steps = self.get_payload_data(request, "max_steps") or 10
        available_tools = (
            self.get_payload_data(request, "tools") or self._tool_registry.list_tools()
        )

        if not task:
            return self.create_error_response(
                error_message="评测核心任务(task)不能为空",
                error_code="MISSING_TASK",
            )

        agent_id = str(uuid.uuid4())
        state = AgentState(task=task, max_steps=max_steps)

        with self._agents_lock:
            self._agents[agent_id] = state

        state.plan = self._generate_plan(task, available_tools)
        state.history.append({"step": 0, "phase": "planning", "plan": state.plan})

        for i, plan_step in enumerate(state.plan):
            state.current_step = i + 1
            if state.current_step > state.max_steps:
                state.error = "执行链条触及步数阈值上限"
                break

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

        state.completed = True
        state.success = state.error is None
        state.finished_at = time.time()

        return self._calculate_score(agent_id, state, "plan_execute", request)

    def _calculate_score(
        self, agent_id: str, state: AgentState, mode: str, request: EvaluationSchema
    ) -> DomainResponse:
        """计算 Agent 运行时得分"""
        request_meta = request.metadata or {}
        w_completion = request_meta.get("weight_completion", DEFAULT_W_COMPLETION)
        w_efficiency = request_meta.get("weight_efficiency", DEFAULT_W_EFFICIENCY)
        w_tool = request_meta.get("weight_tool", DEFAULT_W_TOOL)

        total_w = w_completion + w_efficiency + w_tool
        if total_w > 0:
            w_completion, w_efficiency, w_tool = (
                w_completion / total_w,
                w_efficiency / total_w,
                w_tool / total_w,
            )

        score_completion = 1.0 if (state.completed and state.success) else 0.0

        if state.success and state.max_steps > 0:
            score_efficiency = max(0.0, 1.0 - (state.current_step / state.max_steps))
        else:
            score_efficiency = 0.0

        tool_calls = 0
        tool_successes = 0
        for h in state.history:
            act = h.get("action", {})
            obs = h.get("observation", {})
            if act and act.get("type") == "tool_call":
                tool_calls += 1
                if obs and obs.get("success", False):
                    tool_successes += 1

        score_tool = (tool_successes / tool_calls) if tool_calls > 0 else 1.0

        final_score = (
            (score_completion * w_completion)
            + (score_efficiency * w_efficiency)
            + (score_tool * w_tool)
        )
        final_score = round(min(max(final_score, 0.0), 1.0), 4)

        serialized_state = self._serialize_state(state)
        report_text = (
            f"Agent评测 模式:{mode.upper()} | 状态:{'SUCCESS' if state.success else 'FAILED'} | "
            f"步数:{state.current_step}/{state.max_steps} | 得分:{final_score}"
        )

        return self.create_success_response(
            text=report_text,
            score=final_score,
            data={
                "agent_id": agent_id,
                "mode": mode,
                "metrics_breakdown": {
                    "completion_score": score_completion,
                    "efficiency_score": score_efficiency,
                    "tool_reliability_score": score_tool,
                },
                "weights_applied": {
                    "completion": round(w_completion, 2),
                    "efficiency": round(w_efficiency, 2),
                    "tool": round(w_tool, 2),
                },
                "runtime_state": serialized_state,
                "trajectory": state.history,
            },
        )

    def _get_state(self, request: EvaluationSchema) -> DomainResponse:
        agent_id = self.get_payload_data(request, "agent_id") or ""
        with self._agents_lock:
            state = self._agents.get(agent_id)

        if not state:
            return self.create_error_response(
                error_message=f"未找到指定的Agent状态: '{agent_id}'",
                error_code="AGENT_NOT_FOUND",
            )

        return self.create_success_response(
            text=f"成功获取 Agent '{agent_id}' 的状态",
            score=1.0,
            data={"state": self._serialize_state(state)},
        )

    def _list_tools(self, request: EvaluationSchema) -> DomainResponse:
        tools = self._tool_registry.get_all_tools()
        return self.create_success_response(
            text=f"系统当前注册了 {len(tools)} 个工具",
            score=1.0,
            data={"tools": tools, "count": len(tools)},
        )

    def _generate_thought(self, state: AgentState) -> str:
        last_obs = state.history[-1].get("observation") if state.history else None
        if last_obs:
            return f"依据最新观测：{last_obs.get('content', '')}，决定推进下一步。"
        return f"感知到新任务: {state.task}，确立思考主线。"

    def _select_action(self, state: AgentState, available_tools: list[str]) -> dict[str, Any]:
        if state.current_step % 3 == 0 and available_tools:
            return {"type": "tool_call", "tool": available_tools[0], "args": {"input": "2 ** 10"}}
        elif state.current_step >= state.max_steps - 1:
            return {"type": "finish", "success": True, "result": f"仿真成功收尾: {state.task}"}
        else:
            return {"type": "think", "content": "进行内部状态演进"}

    def _generate_plan(self, task: str, available_tools: list[str]) -> list[str]:
        return [f"理解指令: {task}", "指派工具执行", "封装并校验交付物"]

    def _infer_tool(self, plan_step: str) -> str | None:
        step_lower = plan_step.lower()
        if any(kw in plan_step for kw in ["搜索", "查询"]) or "search" in step_lower:
            return "search"
        if any(kw in plan_step for kw in ["计算", "测算"]) or "calculator" in step_lower:
            return "calculator"
        if "分析" in plan_step or "analyze" in step_lower:
            return "analyzer"
        return None

    def _execute_action(self, action: dict, state: AgentState) -> dict[str, Any]:
        try:
            if action.get("type") == "tool_call":
                tool_name = action.get("tool")
                if tool_name and self._tool_registry.get_tool(tool_name):
                    result = self._tool_registry.call(tool_name, **action.get("args", {}))
                    return {"success": True, "content": str(result)[:200]}
                return {"success": False, "content": f"工具 '{tool_name}' 未注册"}
            elif action.get("type") == "think":
                return {"success": True, "content": action.get("content", "")}
            elif action.get("type") == "execute_step":
                return {"success": True, "content": f"执行完成: {action.get('description', '')}"}
            return {"success": True, "content": "默认行动流正常执行"}
        except Exception as e:
            return {"success": False, "content": f"工具执行异常: {str(e)}"}

    def _serialize_state(self, state: AgentState) -> dict[str, Any]:
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
            "duration_ms": round((state.finished_at - state.started_at) * 1000, 2)
            if state.finished_at
            else None,
            "history_length": len(state.history),
        }
