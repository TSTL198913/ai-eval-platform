"""多Agent协作评估器测试"""

import pytest
from unittest.mock import MagicMock

from src.domain.evaluators.multi_agent_evaluator import (
    MultiAgentEvaluator,
    MessageType,
    ConflictType,
    TaskStatus,
    AgentMessage,
    AgentTask,
    Conflict,
    AgentInfo,
)
from src.schemas.evaluation import EvaluationSchema


class TestMultiAgentEvaluator:
    """多Agent协作评估器测试"""

    def setup_method(self):
        """测试前初始化"""
        self.mock_client = MagicMock()
        self.evaluator = MultiAgentEvaluator(self.mock_client)

    def test_init(self):
        """测试初始化"""
        assert self.evaluator.agents == {}
        assert self.evaluator.messages == []
        assert self.evaluator.tasks == {}
        assert self.evaluator.conflicts == []
        assert self.evaluator.collaboration_sessions == {}

    def test_register_agent_success(self):
        """测试成功注册Agent"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "register_agent",
                "agent_id": "agent_001",
                "role": "coordinator",
                "capabilities": ["planning", "communication"],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert "agent_001" in result.data["agent_id"]
        assert result.data["role"] == "coordinator"
        assert "planning" in result.data["capabilities"]

    def test_register_agent_without_id(self):
        """测试注册Agent时缺少agent_id"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "register_agent",
                "role": "worker",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "agent_id" in result.error

    def test_register_agent_default_values(self):
        """测试注册Agent使用默认值"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "register_agent",
                "agent_id": "agent_002",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["role"] == "worker"
        assert result.data["capabilities"] == []

    def test_record_message_success(self):
        """测试成功记录消息"""
        # 先注册Agent
        self._register_agent("agent_001")
        self._register_agent("agent_002")

        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "record_message",
                "message_id": "msg_001",
                "sender_id": "agent_001",
                "receiver_id": "agent_002",
                "message_type": "request",
                "content": "请处理任务A",
                "latency_ms": 50.0,
                "is_delivered": True,
                "is_acknowledged": True,
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["message_id"] == "msg_001"
        assert result.data["sender_id"] == "agent_001"
        assert self.evaluator.agents["agent_001"].message_count == 1

    def test_record_message_without_sender(self):
        """测试记录消息时缺少sender_id"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "record_message",
                "receiver_id": "agent_002",
                "message_type": "request",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "sender_id" in result.error

    def test_record_message_without_receiver(self):
        """测试记录消息时缺少receiver_id"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "record_message",
                "sender_id": "agent_001",
                "message_type": "request",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "receiver_id" in result.error

    def test_record_message_auto_id(self):
        """测试记录消息自动生成ID"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "record_message",
                "sender_id": "agent_001",
                "receiver_id": "agent_002",
                "message_type": "broadcast",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert "msg-" in result.data["message_id"]

    def test_assign_task_success(self):
        """测试成功分配任务"""
        self._register_agent("agent_001")

        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "assign_task",
                "task_id": "task_001",
                "agent_id": "agent_001",
                "description": "处理数据",
                "priority": 2,
                "dependencies": ["task_000"],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["task_id"] == "task_001"
        assert result.data["agent_id"] == "agent_001"
        assert result.data["status"] == "assigned"
        assert "task_001" in self.evaluator.agents["agent_001"].current_tasks

    def test_assign_task_without_task_id(self):
        """测试分配任务时缺少task_id"""
        self._register_agent("agent_001")

        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "assign_task",
                "agent_id": "agent_001",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "task_id" in result.error

    def test_assign_task_to_unregistered_agent(self):
        """测试分配任务给未注册的Agent"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "assign_task",
                "task_id": "task_001",
                "agent_id": "agent_unknown",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "未注册" in result.error

    def test_update_task_completed(self):
        """测试更新任务状态为完成"""
        self._register_agent("agent_001")
        self._assign_task("task_001", "agent_001")

        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "update_task",
                "task_id": "task_001",
                "status": "completed",
                "result": "处理完成",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["new_status"] == "completed"
        assert self.evaluator.tasks["task_001"].status == TaskStatus.COMPLETED
        assert self.evaluator.agents["agent_001"].completed_tasks == 1
        assert "task_001" not in self.evaluator.agents["agent_001"].current_tasks

    def test_update_task_failed(self):
        """测试更新任务状态为失败"""
        self._register_agent("agent_001")
        self._assign_task("task_001", "agent_001")

        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "update_task",
                "task_id": "task_001",
                "status": "failed",
                "error": "处理失败",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert self.evaluator.tasks["task_001"].status == TaskStatus.FAILED
        assert self.evaluator.agents["agent_001"].failed_tasks == 1

    def test_update_task_not_found(self):
        """测试更新不存在的任务"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "update_task",
                "task_id": "task_unknown",
                "status": "completed",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不存在" in result.error

    def test_record_conflict_success(self):
        """测试成功记录冲突"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "record_conflict",
                "conflict_id": "conflict_001",
                "conflict_type": "task",
                "agent_ids": ["agent_001", "agent_002"],
                "description": "任务分配冲突",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["conflict_id"] == "conflict_001"
        assert result.data["conflict_type"] == "task"

    def test_record_conflict_without_agent_ids(self):
        """测试记录冲突时缺少agent_ids"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "record_conflict",
                "conflict_type": "resource",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "agent_ids" in result.error

    def test_resolve_conflict_success(self):
        """测试成功解决冲突"""
        self._record_conflict("conflict_001", "task", ["agent_001", "agent_002"])

        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "resolve_conflict",
                "conflict_id": "conflict_001",
                "resolution": "重新分配任务",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["resolution"] == "重新分配任务"
        conflict = self.evaluator.get_conflict_info("conflict_001")
        assert conflict.resolved is True

    def test_resolve_conflict_not_found(self):
        """测试解决不存在的冲突"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "resolve_conflict",
                "conflict_id": "conflict_unknown",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不存在" in result.error

    def test_start_collaboration_session_success(self):
        """测试成功开始协作会话"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "start_session",
                "session_id": "session_001",
                "agent_ids": ["agent_001", "agent_002", "agent_003"],
                "goal": "完成项目开发",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["session_id"] == "session_001"
        assert "session_001" in self.evaluator.collaboration_sessions

    def test_start_collaboration_session_without_id(self):
        """测试开始协作会话时缺少session_id"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "start_session",
                "agent_ids": ["agent_001"],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "session_id" in result.error

    def test_end_collaboration_session_success(self):
        """测试成功结束协作会话"""
        self._start_session("session_001")

        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "end_session",
                "session_id": "session_001",
                "status": "completed",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["status"] == "completed"
        assert "duration_seconds" in result.data

    def test_end_collaboration_session_not_found(self):
        """测试结束不存在的协作会话"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "end_session",
                "session_id": "session_unknown",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不存在" in result.error

    def test_analyze_collaboration_overall(self):
        """测试整体协作分析"""
        self._setup_collaboration_data()

        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "analyze",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert "overall_score" in result.data
        assert "communication" in result.data
        assert "tasks" in result.data
        assert "conflicts" in result.data
        assert "collaboration" in result.data

    def test_analyze_collaboration_session(self):
        """测试会话协作分析"""
        self._setup_collaboration_data()
        self._start_session("session_001", ["agent_001", "agent_002"])

        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "analyze",
                "session_id": "session_001",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["session_id"] == "session_001"
        assert "duration_seconds" in result.data

    def test_analyze_collaboration_session_not_found(self):
        """测试分析不存在的会话 - 会执行整体分析"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "analyze",
                "session_id": "session_unknown",
            },
        )

        result = self.evaluator.evaluate(request)

        # 当session_id不存在时，会执行整体分析而不是返回错误
        assert result.is_valid is True
        assert "overall_score" in result.data

    def test_evaluate_collaboration_default(self):
        """测试默认协作评估"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "agents": [
                    {"agent_id": "agent_001", "role": "coordinator", "completed_tasks": 5},
                    {"agent_id": "agent_002", "role": "worker", "completed_tasks": 3},
                ],
                "messages": [
                    {"sender_id": "agent_001", "receiver_id": "agent_002", "message_type": "request", "is_delivered": True},
                    {"sender_id": "agent_002", "receiver_id": "agent_001", "message_type": "response", "is_delivered": True},
                ],
                "tasks": [
                    {"task_id": "task_001", "agent_id": "agent_001", "status": "completed"},
                    {"task_id": "task_002", "agent_id": "agent_002", "status": "completed"},
                ],
                "conflicts": [],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert "overall_score" in result.data
        assert result.data["agents_count"] == 2

    def test_analyze_communication_empty(self):
        """测试分析空通信数据"""
        analysis = self.evaluator._analyze_communication([])

        assert analysis["total_messages"] == 0
        assert analysis["communication_score"] == 0.5

    def test_analyze_communication_with_data(self):
        """测试分析有数据的通信"""
        messages = [
            AgentMessage(
                message_id="msg_001",
                sender_id="agent_001",
                receiver_id="agent_002",
                message_type=MessageType.REQUEST,
                content="test",
                timestamp=1000.0,
                latency_ms=100.0,
                is_delivered=True,
                is_acknowledged=True,
            ),
            AgentMessage(
                message_id="msg_002",
                sender_id="agent_002",
                receiver_id="agent_001",
                message_type=MessageType.RESPONSE,
                content="test",
                timestamp=1001.0,
                latency_ms=200.0,
                is_delivered=True,
                is_acknowledged=False,
            ),
        ]

        analysis = self.evaluator._analyze_communication(messages)

        assert analysis["total_messages"] == 2
        assert analysis["delivered_messages"] == 2
        assert analysis["acknowledged_messages"] == 1
        assert analysis["delivery_rate"] == 1.0
        assert analysis["acknowledgment_rate"] == 0.5
        assert analysis["avg_latency_ms"] == 150.0
        assert "request" in analysis["message_type_distribution"]
        assert "response" in analysis["message_type_distribution"]

    def test_analyze_tasks_empty(self):
        """测试分析空任务数据"""
        analysis = self.evaluator._analyze_tasks([])

        assert analysis["total_tasks"] == 0
        assert analysis["task_efficiency_score"] == 0.5

    def test_analyze_tasks_with_data(self):
        """测试分析有数据的任务"""
        tasks = [
            AgentTask(
                task_id="task_001",
                agent_id="agent_001",
                description="test",
                status=TaskStatus.COMPLETED,
                assigned_at=1000.0,
                completed_at=1010.0,
            ),
            AgentTask(
                task_id="task_002",
                agent_id="agent_002",
                description="test",
                status=TaskStatus.FAILED,
            ),
            AgentTask(
                task_id="task_003",
                agent_id="agent_001",
                description="test",
                status=TaskStatus.PENDING,
            ),
        ]

        analysis = self.evaluator._analyze_tasks(tasks)

        assert analysis["total_tasks"] == 3
        assert analysis["completed_tasks"] == 1
        assert analysis["failed_tasks"] == 1
        assert analysis["pending_tasks"] == 1
        assert analysis["completion_rate"] == pytest.approx(1/3, 0.01)
        assert analysis["failure_rate"] == pytest.approx(1/3, 0.01)

    def test_analyze_conflicts_empty(self):
        """测试分析空冲突数据"""
        analysis = self.evaluator._analyze_conflicts()

        assert analysis["total_conflicts"] == 0
        assert analysis["conflict_resolution_score"] == 1.0

    def test_analyze_conflicts_with_data(self):
        """测试分析有数据的冲突"""
        conflicts = [
            Conflict(
                conflict_id="conflict_001",
                conflict_type=ConflictType.TASK,
                agent_ids=["agent_001", "agent_002"],
                description="test",
                timestamp=1000.0,
                resolved=True,
            ),
            Conflict(
                conflict_id="conflict_002",
                conflict_type=ConflictType.RESOURCE,
                agent_ids=["agent_002", "agent_003"],
                description="test",
                timestamp=1001.0,
                resolved=False,
            ),
        ]
        self.evaluator.conflicts = conflicts

        analysis = self.evaluator._analyze_conflicts()

        assert analysis["total_conflicts"] == 2
        assert analysis["resolved_conflicts"] == 1
        assert analysis["unresolved_conflicts"] == 1
        assert analysis["resolution_rate"] == 0.5
        assert "task" in analysis["conflict_type_distribution"]
        assert "resource" in analysis["conflict_type_distribution"]

    def test_analyze_conflicts_for_agents(self):
        """测试分析特定Agent的冲突"""
        conflicts = [
            Conflict(
                conflict_id="conflict_001",
                conflict_type=ConflictType.TASK,
                agent_ids=["agent_001", "agent_002"],
                description="test",
                timestamp=1000.0,
                resolved=True,
            ),
            Conflict(
                conflict_id="conflict_002",
                conflict_type=ConflictType.RESOURCE,
                agent_ids=["agent_003", "agent_004"],
                description="test",
                timestamp=1001.0,
                resolved=False,
            ),
        ]
        self.evaluator.conflicts = conflicts

        analysis = self.evaluator._analyze_conflicts_for_agents(["agent_001"])

        assert analysis["total_conflicts"] == 1
        assert analysis["resolved_conflicts"] == 1

    def test_analyze_collaboration_quality_empty(self):
        """测试分析空协作质量"""
        analysis = self.evaluator._analyze_collaboration_quality()

        assert analysis["active_agents"] == 0
        assert analysis["collaboration_score"] == 0.5

    def test_analyze_collaboration_quality_with_data(self):
        """测试分析有数据的协作质量"""
        self.evaluator.agents = {
            "agent_001": AgentInfo(
                agent_id="agent_001",
                role="coordinator",
                status="active",
                completed_tasks=5,
                current_tasks=["task_001"],
            ),
            "agent_002": AgentInfo(
                agent_id="agent_002",
                role="worker",
                status="active",
                completed_tasks=3,
                current_tasks=["task_002"],
            ),
            "agent_003": AgentInfo(
                agent_id="agent_003",
                role="worker",
                status="inactive",
                completed_tasks=0,
                current_tasks=[],
            ),
        }
        self.evaluator.tasks = {
            "task_001": AgentTask(task_id="task_001", agent_id="agent_001", description="", status=TaskStatus.IN_PROGRESS),
            "task_002": AgentTask(task_id="task_002", agent_id="agent_002", description="", status=TaskStatus.IN_PROGRESS),
        }
        self.evaluator.messages = [
            AgentMessage(message_id="msg_001", sender_id="agent_001", receiver_id="agent_002", message_type=MessageType.REQUEST, content="", timestamp=1000.0),
        ]

        analysis = self.evaluator._analyze_collaboration_quality()

        assert analysis["total_agents"] == 3
        assert analysis["active_agents"] == 2
        assert analysis["agents_with_tasks"] == 2
        assert analysis["agent_utilization_rate"] == pytest.approx(2/3, 0.01)

    def test_get_agent_info(self):
        """测试获取Agent信息"""
        self._register_agent("agent_001")

        agent = self.evaluator.get_agent_info("agent_001")

        assert agent is not None
        assert agent.agent_id == "agent_001"

    def test_get_agent_info_not_found(self):
        """测试获取不存在的Agent信息"""
        agent = self.evaluator.get_agent_info("agent_unknown")

        assert agent is None

    def test_get_task_info(self):
        """测试获取任务信息"""
        self._register_agent("agent_001")
        self._assign_task("task_001", "agent_001")

        task = self.evaluator.get_task_info("task_001")

        assert task is not None
        assert task.task_id == "task_001"

    def test_get_task_info_not_found(self):
        """测试获取不存在的任务信息"""
        task = self.evaluator.get_task_info("task_unknown")

        assert task is None

    def test_get_conflict_info(self):
        """测试获取冲突信息"""
        self._record_conflict("conflict_001", "task", ["agent_001"])

        conflict = self.evaluator.get_conflict_info("conflict_001")

        assert conflict is not None
        assert conflict.conflict_id == "conflict_001"

    def test_get_conflict_info_not_found(self):
        """测试获取不存在的冲突信息"""
        conflict = self.evaluator.get_conflict_info("conflict_unknown")

        assert conflict is None

    def test_list_agents(self):
        """测试列出所有Agent"""
        self._register_agent("agent_001")
        self._register_agent("agent_002")

        agents = self.evaluator.list_agents()

        assert len(agents) == 2
        assert "agent_001" in agents
        assert "agent_002" in agents

    def test_list_tasks(self):
        """测试列出所有任务"""
        self._register_agent("agent_001")
        self._assign_task("task_001", "agent_001")
        self._assign_task("task_002", "agent_001")

        tasks = self.evaluator.list_tasks()

        assert len(tasks) == 2
        assert "task_001" in tasks
        assert "task_002" in tasks

    def test_list_conflicts(self):
        """测试列出所有冲突"""
        self._record_conflict("conflict_001", "task", ["agent_001"])
        self._record_conflict("conflict_002", "resource", ["agent_002"])

        conflicts = self.evaluator.list_conflicts()

        assert len(conflicts) == 2
        assert "conflict_001" in conflicts
        assert "conflict_002" in conflicts

    def test_clear_data(self):
        """测试清空所有数据"""
        self._setup_collaboration_data()

        self.evaluator.clear_data()

        assert self.evaluator.agents == {}
        assert self.evaluator.messages == []
        assert self.evaluator.tasks == {}
        assert self.evaluator.conflicts == []
        assert self.evaluator.collaboration_sessions == {}

    def test_import_collaboration_data(self):
        """测试导入协作数据"""
        agents_data = [
            {"agent_id": "agent_001", "role": "coordinator", "completed_tasks": 5},
        ]
        messages_data = [
            {"sender_id": "agent_001", "receiver_id": "agent_002", "message_type": "request"},
        ]
        tasks_data = [
            {"task_id": "task_001", "agent_id": "agent_001", "status": "completed"},
        ]
        conflicts_data = [
            {"conflict_id": "conflict_001", "conflict_type": "task", "agent_ids": ["agent_001"], "resolved": True},
        ]

        self.evaluator._import_collaboration_data(agents_data, messages_data, tasks_data, conflicts_data)

        assert len(self.evaluator.agents) == 1
        assert len(self.evaluator.messages) == 1
        assert len(self.evaluator.tasks) == 1
        assert len(self.evaluator.conflicts) == 1

    def test_message_type_enum(self):
        """测试消息类型枚举"""
        assert MessageType.REQUEST.value == "request"
        assert MessageType.RESPONSE.value == "response"
        assert MessageType.BROADCAST.value == "broadcast"
        assert MessageType.NOTIFICATION.value == "notification"
        assert MessageType.ERROR.value == "error"

    def test_conflict_type_enum(self):
        """测试冲突类型枚举"""
        assert ConflictType.RESOURCE.value == "resource"
        assert ConflictType.TASK.value == "task"
        assert ConflictType.COMMUNICATION.value == "communication"
        assert ConflictType.PRIORITY.value == "priority"
        assert ConflictType.DATA.value == "data"

    def test_task_status_enum(self):
        """测试任务状态枚举"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.ASSIGNED.value == "assigned"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"

    def test_agent_message_dataclass(self):
        """测试Agent消息数据类"""
        message = AgentMessage(
            message_id="msg_001",
            sender_id="agent_001",
            receiver_id="agent_002",
            message_type=MessageType.REQUEST,
            content="test content",
            timestamp=1000.0,
            latency_ms=50.0,
            is_delivered=True,
            is_acknowledged=False,
            metadata={"key": "value"},
        )

        assert message.message_id == "msg_001"
        assert message.sender_id == "agent_001"
        assert message.receiver_id == "agent_002"
        assert message.message_type == MessageType.REQUEST
        assert message.content == "test content"
        assert message.latency_ms == 50.0
        assert message.is_delivered is True
        assert message.is_acknowledged is False
        assert message.metadata == {"key": "value"}

    def test_agent_task_dataclass(self):
        """测试Agent任务数据类"""
        task = AgentTask(
            task_id="task_001",
            agent_id="agent_001",
            description="test task",
            status=TaskStatus.IN_PROGRESS,
            priority=2,
            assigned_at=1000.0,
            completed_at=0.0,
            dependencies=["task_000"],
            result=None,
            error=None,
        )

        assert task.task_id == "task_001"
        assert task.agent_id == "agent_001"
        assert task.description == "test task"
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.priority == 2
        assert task.dependencies == ["task_000"]

    def test_conflict_dataclass(self):
        """测试冲突数据类"""
        conflict = Conflict(
            conflict_id="conflict_001",
            conflict_type=ConflictType.TASK,
            agent_ids=["agent_001", "agent_002"],
            description="task conflict",
            timestamp=1000.0,
            resolved=False,
            resolution=None,
        )

        assert conflict.conflict_id == "conflict_001"
        assert conflict.conflict_type == ConflictType.TASK
        assert conflict.agent_ids == ["agent_001", "agent_002"]
        assert conflict.resolved is False

    def test_agent_info_dataclass(self):
        """测试Agent信息数据类"""
        agent = AgentInfo(
            agent_id="agent_001",
            role="coordinator",
            capabilities=["planning", "communication"],
            status="active",
            current_tasks=["task_001"],
            message_count=10,
            completed_tasks=5,
            failed_tasks=1,
        )

        assert agent.agent_id == "agent_001"
        assert agent.role == "coordinator"
        assert agent.capabilities == ["planning", "communication"]
        assert agent.status == "active"
        assert agent.message_count == 10
        assert agent.completed_tasks == 5
        assert agent.failed_tasks == 1

    def test_analyze_overall_empty(self):
        """测试整体分析空数据"""
        analysis = self.evaluator._analyze_overall()

        assert analysis["agents_count"] == 0
        assert analysis["messages_count"] == 0
        assert analysis["tasks_count"] == 0
        assert analysis["conflicts_count"] == 0
        assert "overall_score" in analysis

    def test_analyze_session_empty(self):
        """测试分析空会话"""
        analysis = self.evaluator._analyze_session("session_unknown")

        assert "error" in analysis

    def test_evaluate_with_high_latency(self):
        """测试高延迟通信评估"""
        messages = [
            AgentMessage(
                message_id="msg_001",
                sender_id="agent_001",
                receiver_id="agent_002",
                message_type=MessageType.REQUEST,
                content="test",
                timestamp=1000.0,
                latency_ms=2000.0,  # 高延迟
                is_delivered=True,
                is_acknowledged=True,
            ),
        ]

        analysis = self.evaluator._analyze_communication(messages)

        # 高延迟应该降低通信分数
        assert analysis["communication_score"] < 1.0

    def test_evaluate_with_many_conflicts(self):
        """测试多冲突评估"""
        # 创建多个冲突
        for i in range(15):
            self._record_conflict(f"conflict_{i}", "task", ["agent_001", "agent_002"])

        analysis = self.evaluator._analyze_conflicts()

        # 多冲突应该降低分数
        assert analysis["conflict_resolution_score"] < 1.0

    def test_load_balance_score(self):
        """测试负载均衡分数"""
        # 不均衡的任务分配
        self.evaluator.agents = {
            "agent_001": AgentInfo(agent_id="agent_001", role="worker", completed_tasks=10, current_tasks=[]),
            "agent_002": AgentInfo(agent_id="agent_002", role="worker", completed_tasks=0, current_tasks=[]),
        }

        analysis = self.evaluator._analyze_collaboration_quality()

        # 不均衡分配应该降低负载均衡分数
        assert analysis["load_balance_score"] < 1.0

    def test_factory_registration(self):
        """测试工厂注册"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        evaluator = EvaluatorFactory.get("multi_agent")

        assert isinstance(evaluator, MultiAgentEvaluator)

    # 辅助方法
    def _register_agent(self, agent_id: str, role: str = "worker"):
        """辅助方法：注册Agent"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "register_agent",
                "agent_id": agent_id,
                "role": role,
            },
        )
        self.evaluator.evaluate(request)

    def _assign_task(self, task_id: str, agent_id: str):
        """辅助方法：分配任务"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "assign_task",
                "task_id": task_id,
                "agent_id": agent_id,
            },
        )
        self.evaluator.evaluate(request)

    def _record_conflict(self, conflict_id: str, conflict_type: str, agent_ids: list):
        """辅助方法：记录冲突"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "record_conflict",
                "conflict_id": conflict_id,
                "conflict_type": conflict_type,
                "agent_ids": agent_ids,
            },
        )
        self.evaluator.evaluate(request)

    def _start_session(self, session_id: str, agent_ids: list = None):
        """辅助方法：开始会话"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "start_session",
                "session_id": session_id,
                "agent_ids": agent_ids or ["agent_001"],
            },
        )
        self.evaluator.evaluate(request)

    def _setup_collaboration_data(self):
        """辅助方法：设置协作数据"""
        self._register_agent("agent_001", "coordinator")
        self._register_agent("agent_002", "worker")
        self._assign_task("task_001", "agent_001")
        self._assign_task("task_002", "agent_002")

        # 记录消息
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "record_message",
                "sender_id": "agent_001",
                "receiver_id": "agent_002",
                "message_type": "request",
                "content": "请处理任务",
                "is_delivered": True,
                "is_acknowledged": True,
            },
        )
        self.evaluator.evaluate(request)


class TestMultiAgentEvaluatorEdgeCases:
    """多Agent协作评估器边界情况测试"""

    def setup_method(self):
        """测试前初始化"""
        self.evaluator = MultiAgentEvaluator()

    def test_empty_payload(self):
        """测试空payload"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={},
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert "overall_score" in result.data

    def test_invalid_message_type(self):
        """测试无效消息类型 - 应抛出异常"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "record_message",
                "sender_id": "agent_001",
                "receiver_id": "agent_002",
                "message_type": "invalid_type",
            },
        )

        # 无效枚举值会抛出ValueError异常
        with pytest.raises(ValueError):
            self.evaluator.evaluate(request)

    def test_invalid_task_status(self):
        """测试无效任务状态 - 应抛出异常"""
        self.evaluator._register_agent(
            EvaluationSchema(
                id="case_001",
                type="multi_agent",
                payload={"action": "register_agent", "agent_id": "agent_001"},
            )
        )
        self.evaluator._assign_task(
            EvaluationSchema(
                id="case_001",
                type="multi_agent",
                payload={"action": "assign_task", "task_id": "task_001", "agent_id": "agent_001"},
            )
        )

        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "update_task",
                "task_id": "task_001",
                "status": "invalid_status",
            },
        )

        # 无效枚举值会抛出ValueError异常
        with pytest.raises(ValueError):
            self.evaluator.evaluate(request)

    def test_invalid_conflict_type(self):
        """测试无效冲突类型 - 应抛出异常"""
        request = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "record_conflict",
                "conflict_type": "invalid_type",
                "agent_ids": ["agent_001"],
            },
        )

        # 无效枚举值会抛出ValueError异常
        with pytest.raises(ValueError):
            self.evaluator.evaluate(request)

    def test_multiple_agents_same_id(self):
        """测试注册相同ID的Agent"""
        request1 = EvaluationSchema(
            id="case_001",
            type="multi_agent",
            payload={
                "action": "register_agent",
                "agent_id": "agent_001",
                "role": "worker",
            },
        )
        request2 = EvaluationSchema(
            id="case_002",
            type="multi_agent",
            payload={
                "action": "register_agent",
                "agent_id": "agent_001",
                "role": "coordinator",
            },
        )

        result1 = self.evaluator.evaluate(request1)
        result2 = self.evaluator.evaluate(request2)

        # 第二次注册应该覆盖第一次
        assert result1.is_valid is True
        assert result2.is_valid is True
        assert self.evaluator.agents["agent_001"].role == "coordinator"

    def test_task_reassignment(self):
        """测试任务重新分配"""
        # 注册两个Agent
        self.evaluator._register_agent(
            EvaluationSchema(
                id="case_001",
                type="multi_agent",
                payload={"action": "register_agent", "agent_id": "agent_001"},
            )
        )
        self.evaluator._register_agent(
            EvaluationSchema(
                id="case_002",
                type="multi_agent",
                payload={"action": "register_agent", "agent_id": "agent_002"},
            )
        )

        # 分配任务给agent_001
        self.evaluator._assign_task(
            EvaluationSchema(
                id="case_001",
                type="multi_agent",
                payload={"action": "assign_task", "task_id": "task_001", "agent_id": "agent_001"},
            )
        )

        # 再次分配相同任务给agent_002
        request = EvaluationSchema(
            id="case_003",
            type="multi_agent",
            payload={"action": "assign_task", "task_id": "task_001", "agent_id": "agent_002"},
        )

        result = self.evaluator.evaluate(request)

        # 任务应该被重新分配
        assert result.is_valid is True
        assert self.evaluator.tasks["task_001"].agent_id == "agent_002"

    def test_zero_latency_messages(self):
        """测试零延迟消息"""
        messages = [
            AgentMessage(
                message_id="msg_001",
                sender_id="agent_001",
                receiver_id="agent_002",
                message_type=MessageType.REQUEST,
                content="test",
                timestamp=1000.0,
                latency_ms=0.0,
                is_delivered=True,
                is_acknowledged=True,
            ),
        ]

        analysis = self.evaluator._analyze_communication(messages)

        # 零延迟应该不影响分数
        assert analysis["avg_latency_ms"] == 0.0
        assert analysis["communication_score"] > 0.5

    def test_all_messages_undelivered(self):
        """测试所有消息未投递"""
        messages = [
            AgentMessage(
                message_id="msg_001",
                sender_id="agent_001",
                receiver_id="agent_002",
                message_type=MessageType.REQUEST,
                content="test",
                timestamp=1000.0,
                latency_ms=100.0,
                is_delivered=False,
                is_acknowledged=False,
            ),
        ]

        analysis = self.evaluator._analyze_communication(messages)

        assert analysis["delivery_rate"] == 0.0
        assert analysis["communication_score"] < 0.5

    def test_all_tasks_failed(self):
        """测试所有任务失败"""
        tasks = [
            AgentTask(task_id="task_001", agent_id="agent_001", description="", status=TaskStatus.FAILED),
            AgentTask(task_id="task_002", agent_id="agent_002", description="", status=TaskStatus.FAILED),
        ]

        analysis = self.evaluator._analyze_tasks(tasks)

        assert analysis["completion_rate"] == 0.0
        assert analysis["failure_rate"] == 1.0
        assert analysis["task_efficiency_score"] < 0.5

    def test_all_conflicts_unresolved(self):
        """测试所有冲突未解决"""
        conflicts = [
            Conflict(conflict_id="c1", conflict_type=ConflictType.TASK, agent_ids=["a1"], description="", timestamp=1000.0, resolved=False),
            Conflict(conflict_id="c2", conflict_type=ConflictType.TASK, agent_ids=["a2"], description="", timestamp=1001.0, resolved=False),
        ]
        self.evaluator.conflicts = conflicts

        analysis = self.evaluator._analyze_conflicts()

        assert analysis["resolution_rate"] == 0.0
        assert analysis["conflict_resolution_score"] < 0.5