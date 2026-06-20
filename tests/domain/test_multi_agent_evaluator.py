"""
MultiAgentEvaluator 专项测试
测试目标：验证多Agent协作评估器的功能完整性和正确性
关键发现：
1. 评估器支持9种操作：注册Agent、记录消息、分配任务、更新任务、记录冲突、解决冲突、会话管理、分析、评估
2. 通信质量评分权重：投递率(40%) + 确认率(30%) + 延迟评分(30%)
3. 任务效率评分权重：完成率(50%) + 失败率(30%) + 时间评分(20%)
4. 协作评分权重：活跃度(30%) + 利用率(40%) + 负载均衡(30%)
5. 输入清理函数支持XSS防护和长度限制
"""

import os
import sys
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.multi_agent_evaluator import (
    AgentInfo,
    AgentMessage,
    AgentTask,
    Conflict,
    ConflictType,
    MessageType,
    MultiAgentEvaluator,
    TaskStatus,
    sanitize_input,
)
from src.schemas.evaluation import EvaluationSchema


# ============================================================
# Part 1: 输入清理函数测试
# ============================================================
class TestSanitizeInput:
    """输入清理函数测试 - XSS防护和长度限制"""

    def test_empty_input_returns_empty(self):
        """空输入应返回空字符串"""
        result = sanitize_input("")
        assert result == ""

    def test_none_input_returns_empty(self):
        """None输入应返回空字符串"""
        result = sanitize_input(None)
        assert result == ""

    def test_normal_input_preserved(self):
        """正常输入应保持不变"""
        result = sanitize_input("Hello World")
        assert result == "Hello World"

    def test_script_tags_removed(self):
        """脚本标签应被移除"""
        malicious_input = "<script>alert('XSS')</script>Hello"
        result = sanitize_input(malicious_input)
        assert "<script>" not in result
        assert "alert" not in result
        assert "Hello" in result

    def test_html_tags_removed(self):
        """HTML标签应被移除"""
        html_input = "<div>Content</div><p>Paragraph</p>"
        result = sanitize_input(html_input)
        assert "<div>" not in result
        assert "<p>" not in result
        assert "Content" in result
        assert "Paragraph" in result

    def test_control_characters_removed(self):
        """控制字符应被移除"""
        control_chars = "Hello\x00\x01\x02World"
        result = sanitize_input(control_chars)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x02" not in result
        assert "HelloWorld" in result

    def test_max_length_enforced(self):
        """超过最大长度应被截断"""
        long_input = "A" * 2000
        result = sanitize_input(long_input, max_length=1000)
        assert len(result) == 1000

    def test_custom_max_length(self):
        """自定义最大长度应生效"""
        input_text = "Test content"
        result = sanitize_input(input_text, max_length=5)
        # 注意：sanitize_input截断后会调用strip()，末尾空格会被移除
        assert len(result) == 4
        assert result == "Test"


# ============================================================
# Part 2: Agent注册和管理测试
# ============================================================
class TestAgentRegistrationPositiveCases:
    """正向测试 - Agent注册成功场景"""

    @pytest.fixture
    def evaluator(self):
        """创建评估器实例"""
        return MultiAgentEvaluator()

    def test_register_agent_success(self, evaluator):
        """注册Agent应成功"""
        request = EvaluationSchema(
            id="test_001",
            type="multi_agent",
            payload={
                "action": "register_agent",
                "agent_id": "agent_001",
                "role": "worker",
                "capabilities": ["task_execution", "communication"],
            },
        )

        result = evaluator.evaluate(request)

        # 强断言：验证业务逻辑
        assert result.is_valid is True
        assert result.score == 1.0
        assert result.data["agent_id"] == "agent_001"
        assert result.data["role"] == "worker"
        assert "task_execution" in result.data["capabilities"]

        # 验证内部状态
        assert "agent_001" in evaluator.agents
        assert evaluator.agents["agent_001"].role == "worker"

    def test_register_agent_with_default_role(self, evaluator):
        """注册Agent时默认角色应为worker"""
        request = EvaluationSchema(
            id="test_002",
            type="multi_agent",
            payload={
                "action": "register_agent",
                "agent_id": "agent_002",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["role"] == "worker"
        assert result.data["capabilities"] == []

    def test_get_agent_info_success(self, evaluator):
        """获取Agent信息应成功"""
        # 先注册Agent
        evaluator.agents["agent_001"] = AgentInfo(
            agent_id="agent_001",
            role="coordinator",
            capabilities=["planning", "coordination"],
        )

        agent_info = evaluator.get_agent_info("agent_001")

        assert agent_info is not None
        assert agent_info.agent_id == "agent_001"
        assert agent_info.role == "coordinator"
        assert "planning" in agent_info.capabilities

    def test_list_agents_success(self, evaluator):
        """列出所有Agent应成功"""
        evaluator.agents["agent_001"] = AgentInfo(agent_id="agent_001", role="worker")
        evaluator.agents["agent_002"] = AgentInfo(agent_id="agent_002", role="coordinator")

        agent_list = evaluator.list_agents()

        assert len(agent_list) == 2
        assert "agent_001" in agent_list
        assert "agent_002" in agent_list


class TestAgentRegistrationNegativeCases:
    """负向测试 - Agent注册失败场景"""

    @pytest.fixture
    def evaluator(self):
        return MultiAgentEvaluator()

    def test_register_agent_without_id_fails(self, evaluator):
        """缺少agent_id应返回错误"""
        request = EvaluationSchema(
            id="test_003",
            type="multi_agent",
            payload={
                "action": "register_agent",
                "role": "worker",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "agent_id" in result.error
        assert "不能为空" in result.error

    def test_get_nonexistent_agent_returns_none(self, evaluator):
        """获取不存在的Agent应返回None"""
        agent_info = evaluator.get_agent_info("nonexistent_agent")
        assert agent_info is None


# ============================================================
# Part 3: 消息记录和通信分析测试
# ============================================================
class TestMessageRecordingPositiveCases:
    """正向测试 - 消息记录成功场景"""

    @pytest.fixture
    def evaluator(self):
        evaluator = MultiAgentEvaluator()
        # 注册两个Agent
        evaluator.agents["sender_001"] = AgentInfo(agent_id="sender_001", role="worker")
        evaluator.agents["receiver_001"] = AgentInfo(agent_id="receiver_001", role="worker")
        return evaluator

    def test_record_message_success(self, evaluator):
        """记录消息应成功"""
        request = EvaluationSchema(
            id="test_004",
            type="multi_agent",
            payload={
                "action": "record_message",
                "message_id": "msg_001",
                "sender_id": "sender_001",
                "receiver_id": "receiver_001",
                "message_type": "request",
                "content": "Task assignment",
                "latency_ms": 50.0,
                "is_delivered": True,
                "is_acknowledged": True,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert result.data["message_id"] == "msg_001"
        assert result.data["sender_id"] == "sender_001"
        assert result.data["message_type"] == "request"

        # 验证消息计数更新
        assert evaluator.agents["sender_001"].message_count == 1

    def test_record_message_with_default_id(self, evaluator):
        """未提供message_id时应自动生成"""
        request = EvaluationSchema(
            id="test_005",
            type="multi_agent",
            payload={
                "action": "record_message",
                "sender_id": "sender_001",
                "receiver_id": "receiver_001",
                "message_type": "response",
                "content": "Task completed",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["message_id"].startswith("msg-")

    def test_record_broadcast_message(self, evaluator):
        """广播消息应被正确记录"""
        request = EvaluationSchema(
            id="test_006",
            type="multi_agent",
            payload={
                "action": "record_message",
                "sender_id": "sender_001",
                "receiver_id": "all",
                "message_type": "broadcast",
                "content": "System update",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["message_type"] == "broadcast"


class TestMessageRecordingNegativeCases:
    """负向测试 - 消息记录失败场景"""

    @pytest.fixture
    def evaluator(self):
        return MultiAgentEvaluator()

    def test_record_message_without_sender_fails(self, evaluator):
        """缺少sender_id应返回错误"""
        request = EvaluationSchema(
            id="test_007",
            type="multi_agent",
            payload={
                "action": "record_message",
                "receiver_id": "receiver_001",
                "message_type": "request",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "sender_id" in result.error

    def test_record_message_without_receiver_fails(self, evaluator):
        """缺少receiver_id应返回错误"""
        request = EvaluationSchema(
            id="test_008",
            type="multi_agent",
            payload={
                "action": "record_message",
                "sender_id": "sender_001",
                "message_type": "request",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "receiver_id" in result.error

    def test_record_message_with_invalid_type_fails(self, evaluator):
        """无效消息类型应返回错误"""
        request = EvaluationSchema(
            id="test_009",
            type="multi_agent",
            payload={
                "action": "record_message",
                "sender_id": "sender_001",
                "receiver_id": "receiver_001",
                "message_type": "invalid_type",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "无效的message_type" in result.error


class TestCommunicationAnalysis:
    """通信质量分析测试"""

    @pytest.fixture
    def evaluator_with_messages(self):
        """创建包含消息的评估器"""
        evaluator = MultiAgentEvaluator()
        # 添加测试消息
        evaluator.messages = [
            AgentMessage(
                message_id="msg_001",
                sender_id="agent_001",
                receiver_id="agent_002",
                message_type=MessageType.REQUEST,
                content="Task request",
                timestamp=time.time(),
                latency_ms=50.0,
                is_delivered=True,
                is_acknowledged=True,
            ),
            AgentMessage(
                message_id="msg_002",
                sender_id="agent_002",
                receiver_id="agent_001",
                message_type=MessageType.RESPONSE,
                content="Task response",
                timestamp=time.time(),
                latency_ms=100.0,
                is_delivered=True,
                is_acknowledged=False,
            ),
            AgentMessage(
                message_id="msg_003",
                sender_id="agent_001",
                receiver_id="agent_003",
                message_type=MessageType.ERROR,
                content="Error message",
                timestamp=time.time(),
                latency_ms=0.0,
                is_delivered=False,
                is_acknowledged=False,
            ),
        ]
        return evaluator

    def test_analyze_communication_with_messages(self, evaluator_with_messages):
        """通信分析应正确计算各项指标"""
        analysis = evaluator_with_messages._analyze_communication(evaluator_with_messages.messages)

        # 强断言：验证业务逻辑
        assert analysis["total_messages"] == 3
        assert analysis["delivered_messages"] == 2
        assert analysis["acknowledged_messages"] == 1
        # 注意：代码中使用round(delivery_rate, 4)，所以值会被四舍五入
        assert abs(analysis["delivery_rate"] - 2 / 3) < 0.001
        assert abs(analysis["acknowledgment_rate"] - 1 / 3) < 0.001
        assert analysis["avg_latency_ms"] == 75.0  # (50 + 100) / 2
        assert "request" in analysis["message_type_distribution"]
        assert "response" in analysis["message_type_distribution"]
        assert analysis["communication_score"] > 0.0

    def test_analyze_communication_empty_messages(self):
        """空消息列表应返回默认值"""
        evaluator = MultiAgentEvaluator()
        analysis = evaluator._analyze_communication([])

        assert analysis["total_messages"] == 0
        assert analysis["delivery_rate"] == 0.0
        assert analysis["communication_score"] == 0.5


# ============================================================
# Part 4: 任务分配和状态更新测试
# ============================================================
class TestTaskAssignmentPositiveCases:
    """正向测试 - 任务分配成功场景"""

    @pytest.fixture
    def evaluator(self):
        evaluator = MultiAgentEvaluator()
        # 注册Agent
        evaluator.agents["agent_001"] = AgentInfo(agent_id="agent_001", role="worker")
        return evaluator

    def test_assign_task_success(self, evaluator):
        """分配任务应成功"""
        request = EvaluationSchema(
            id="test_010",
            type="multi_agent",
            payload={
                "action": "assign_task",
                "task_id": "task_001",
                "agent_id": "agent_001",
                "description": "Process data",
                "priority": 2,
                "dependencies": ["task_000"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert result.data["task_id"] == "task_001"
        assert result.data["agent_id"] == "agent_001"
        assert result.data["status"] == "assigned"

        # 验证内部状态
        assert "task_001" in evaluator.tasks
        assert evaluator.tasks["task_001"].status == TaskStatus.ASSIGNED
        assert "task_001" in evaluator.agents["agent_001"].current_tasks

    def test_update_task_to_completed(self, evaluator):
        """更新任务为已完成应成功"""
        # 先分配任务
        evaluator.tasks["task_001"] = AgentTask(
            task_id="task_001",
            agent_id="agent_001",
            description="Test task",
            status=TaskStatus.IN_PROGRESS,
            assigned_at=time.time(),
        )

        request = EvaluationSchema(
            id="test_011",
            type="multi_agent",
            payload={
                "action": "update_task",
                "task_id": "task_001",
                "status": "completed",
                "result": {"output": "success"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["new_status"] == "completed"
        assert evaluator.tasks["task_001"].status == TaskStatus.COMPLETED
        assert evaluator.tasks["task_001"].result == {"output": "success"}
        assert evaluator.agents["agent_001"].completed_tasks == 1

    def test_update_task_to_failed(self, evaluator):
        """更新任务为失败应成功"""
        evaluator.tasks["task_001"] = AgentTask(
            task_id="task_001",
            agent_id="agent_001",
            description="Test task",
            status=TaskStatus.IN_PROGRESS,
            assigned_at=time.time(),
        )

        request = EvaluationSchema(
            id="test_012",
            type="multi_agent",
            payload={
                "action": "update_task",
                "task_id": "task_001",
                "status": "failed",
                "error": "Connection timeout",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert evaluator.tasks["task_001"].status == TaskStatus.FAILED
        assert evaluator.tasks["task_001"].error == "Connection timeout"
        assert evaluator.agents["agent_001"].failed_tasks == 1


class TestTaskAssignmentNegativeCases:
    """负向测试 - 任务分配失败场景"""

    @pytest.fixture
    def evaluator(self):
        evaluator = MultiAgentEvaluator()
        evaluator.agents["agent_001"] = AgentInfo(agent_id="agent_001", role="worker")
        return evaluator

    def test_assign_task_without_id_fails(self, evaluator):
        """缺少task_id应返回错误"""
        request = EvaluationSchema(
            id="test_013",
            type="multi_agent",
            payload={
                "action": "assign_task",
                "agent_id": "agent_001",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "task_id" in result.error

    def test_assign_task_to_unregistered_agent_fails(self, evaluator):
        """分配给未注册Agent应返回错误"""
        request = EvaluationSchema(
            id="test_014",
            type="multi_agent",
            payload={
                "action": "assign_task",
                "task_id": "task_001",
                "agent_id": "unregistered_agent",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "未注册" in result.error

    def test_update_nonexistent_task_fails(self, evaluator):
        """更新不存在的任务应返回错误"""
        request = EvaluationSchema(
            id="test_015",
            type="multi_agent",
            payload={
                "action": "update_task",
                "task_id": "nonexistent_task",
                "status": "completed",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不存在" in result.error

    def test_update_task_with_invalid_status_fails(self, evaluator):
        """无效任务状态应返回错误"""
        evaluator.tasks["task_001"] = AgentTask(
            task_id="task_001",
            agent_id="agent_001",
            description="Test",
            status=TaskStatus.PENDING,
        )

        request = EvaluationSchema(
            id="test_016",
            type="multi_agent",
            payload={
                "action": "update_task",
                "task_id": "task_001",
                "status": "invalid_status",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "无效的status" in result.error


class TestTaskAnalysis:
    """任务效率分析测试"""

    @pytest.fixture
    def evaluator_with_tasks(self):
        """创建包含任务的评估器"""
        evaluator = MultiAgentEvaluator()
        current_time = time.time()
        evaluator.tasks = {
            "task_001": AgentTask(
                task_id="task_001",
                agent_id="agent_001",
                description="Task 1",
                status=TaskStatus.COMPLETED,
                assigned_at=current_time - 1.0,
                completed_at=current_time,
            ),
            "task_002": AgentTask(
                task_id="task_002",
                agent_id="agent_001",
                description="Task 2",
                status=TaskStatus.FAILED,
                assigned_at=current_time - 1.0,
                error="Error",
            ),
            "task_003": AgentTask(
                task_id="task_003",
                agent_id="agent_002",
                description="Task 3",
                status=TaskStatus.PENDING,
            ),
        }
        return evaluator

    def test_analyze_tasks_with_data(self, evaluator_with_tasks):
        """任务分析应正确计算各项指标"""
        analysis = evaluator_with_tasks._analyze_tasks(list(evaluator_with_tasks.tasks.values()))

        # 强断言：验证业务逻辑
        assert analysis["total_tasks"] == 3
        assert analysis["completed_tasks"] == 1
        assert analysis["failed_tasks"] == 1
        assert analysis["pending_tasks"] == 1
        # 注意：代码中使用round(completion_rate, 4)，所以值会被四舍五入
        assert abs(analysis["completion_rate"] - 1 / 3) < 0.001
        assert abs(analysis["failure_rate"] - 1 / 3) < 0.001
        assert analysis["avg_completion_time_ms"] == 1000.0  # 1秒 = 1000ms
        assert "agent_001" in analysis["agent_task_distribution"]
        assert analysis["task_efficiency_score"] > 0.0

    def test_analyze_tasks_empty(self):
        """空任务列表应返回默认值"""
        evaluator = MultiAgentEvaluator()
        analysis = evaluator._analyze_tasks([])

        assert analysis["total_tasks"] == 0
        assert analysis["completion_rate"] == 0.0
        assert analysis["task_efficiency_score"] == 0.5


# ============================================================
# Part 5: 冲突记录和解决测试
# ============================================================
class TestConflictManagementPositiveCases:
    """正向测试 - 冲突管理成功场景"""

    @pytest.fixture
    def evaluator(self):
        return MultiAgentEvaluator()

    def test_record_conflict_success(self, evaluator):
        """记录冲突应成功"""
        request = EvaluationSchema(
            id="test_017",
            type="multi_agent",
            payload={
                "action": "record_conflict",
                "conflict_id": "conflict_001",
                "conflict_type": "task",
                "agent_ids": ["agent_001", "agent_002"],
                "description": "Task assignment conflict",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert result.data["conflict_id"] == "conflict_001"
        assert result.data["conflict_type"] == "task"
        assert len(result.data["agent_ids"]) == 2

        # 验证内部状态
        assert len(evaluator.conflicts) == 1
        assert evaluator.conflicts[0].conflict_type == ConflictType.TASK

    def test_resolve_conflict_success(self, evaluator):
        """解决冲突应成功"""
        # 先记录冲突
        evaluator.conflicts.append(
            Conflict(
                conflict_id="conflict_001",
                conflict_type=ConflictType.TASK,
                agent_ids=["agent_001", "agent_002"],
                description="Test conflict",
                timestamp=time.time(),
                resolved=False,
            )
        )

        request = EvaluationSchema(
            id="test_018",
            type="multi_agent",
            payload={
                "action": "resolve_conflict",
                "conflict_id": "conflict_001",
                "resolution": "Priority-based assignment",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["resolution"] == "Priority-based assignment"
        assert evaluator.conflicts[0].resolved is True
        assert evaluator.conflicts[0].resolution == "Priority-based assignment"


class TestConflictManagementNegativeCases:
    """负向测试 - 冲突管理失败场景"""

    @pytest.fixture
    def evaluator(self):
        return MultiAgentEvaluator()

    def test_record_conflict_without_agent_ids_fails(self, evaluator):
        """缺少agent_ids应返回错误"""
        request = EvaluationSchema(
            id="test_019",
            type="multi_agent",
            payload={
                "action": "record_conflict",
                "conflict_type": "task",
                "description": "Test",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "agent_ids" in result.error

    def test_record_conflict_with_invalid_type_fails(self, evaluator):
        """无效冲突类型应返回错误"""
        request = EvaluationSchema(
            id="test_020",
            type="multi_agent",
            payload={
                "action": "record_conflict",
                "conflict_type": "invalid_type",
                "agent_ids": ["agent_001"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "无效的conflict_type" in result.error

    def test_resolve_nonexistent_conflict_fails(self, evaluator):
        """解决不存在的冲突应返回错误"""
        request = EvaluationSchema(
            id="test_021",
            type="multi_agent",
            payload={
                "action": "resolve_conflict",
                "conflict_id": "nonexistent_conflict",
                "resolution": "Test",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不存在" in result.error


class TestConflictAnalysis:
    """冲突分析测试"""

    @pytest.fixture
    def evaluator_with_conflicts(self):
        """创建包含冲突的评估器"""
        evaluator = MultiAgentEvaluator()
        evaluator.conflicts = [
            Conflict(
                conflict_id="conflict_001",
                conflict_type=ConflictType.TASK,
                agent_ids=["agent_001", "agent_002"],
                description="Task conflict",
                timestamp=time.time(),
                resolved=True,
                resolution="Priority-based",
            ),
            Conflict(
                conflict_id="conflict_002",
                conflict_type=ConflictType.RESOURCE,
                agent_ids=["agent_002", "agent_003"],
                description="Resource conflict",
                timestamp=time.time(),
                resolved=False,
            ),
        ]
        return evaluator

    def test_analyze_conflicts_with_data(self, evaluator_with_conflicts):
        """冲突分析应正确计算各项指标"""
        analysis = evaluator_with_conflicts._analyze_conflicts()

        # 强断言：验证业务逻辑
        assert analysis["total_conflicts"] == 2
        assert analysis["resolved_conflicts"] == 1
        assert analysis["unresolved_conflicts"] == 1
        assert analysis["resolution_rate"] == 0.5
        assert "task" in analysis["conflict_type_distribution"]
        assert "resource" in analysis["conflict_type_distribution"]
        assert analysis["conflict_resolution_score"] > 0.0

    def test_analyze_conflicts_empty(self):
        """空冲突列表应返回默认值"""
        evaluator = MultiAgentEvaluator()
        analysis = evaluator._analyze_conflicts()

        assert analysis["total_conflicts"] == 0
        assert analysis["resolution_rate"] == 0.0
        assert analysis["conflict_resolution_score"] == 1.0  # 无冲突时分数为1


# ============================================================
# Part 6: 协作会话管理测试
# ============================================================
class TestCollaborationSession:
    """协作会话管理测试"""

    @pytest.fixture
    def evaluator(self):
        return MultiAgentEvaluator()

    def test_start_session_success(self, evaluator):
        """开始协作会话应成功"""
        request = EvaluationSchema(
            id="test_022",
            type="multi_agent",
            payload={
                "action": "start_session",
                "session_id": "session_001",
                "agent_ids": ["agent_001", "agent_002", "agent_003"],
                "goal": "Complete data processing pipeline",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert result.data["session_id"] == "session_001"
        assert len(result.data["agent_ids"]) == 3
        assert result.data["goal"] == "Complete data processing pipeline"

        # 验证内部状态
        assert "session_001" in evaluator.collaboration_sessions
        assert evaluator.collaboration_sessions["session_001"]["status"] == "active"

    def test_start_session_without_id_fails(self, evaluator):
        """缺少session_id应返回错误"""
        request = EvaluationSchema(
            id="test_023",
            type="multi_agent",
            payload={
                "action": "start_session",
                "agent_ids": ["agent_001"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "session_id" in result.error

    def test_end_session_success(self, evaluator):
        """结束协作会话应成功"""
        # 先开始会话
        evaluator.collaboration_sessions["session_001"] = {
            "session_id": "session_001",
            "agent_ids": ["agent_001"],
            "goal": "Test",
            "start_time": time.time() - 5.0,
            "end_time": None,
            "status": "active",
        }

        request = EvaluationSchema(
            id="test_024",
            type="multi_agent",
            payload={
                "action": "end_session",
                "session_id": "session_001",
                "status": "completed",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["status"] == "completed"
        assert result.data["duration_seconds"] >= 5.0
        assert evaluator.collaboration_sessions["session_001"]["status"] == "completed"

    def test_end_nonexistent_session_fails(self, evaluator):
        """结束不存在的会话应返回错误"""
        request = EvaluationSchema(
            id="test_025",
            type="multi_agent",
            payload={
                "action": "end_session",
                "session_id": "nonexistent_session",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不存在" in result.error


# ============================================================
# Part 7: 协作分析和评估测试
# ============================================================
class TestCollaborationAnalysis:
    """协作分析测试"""

    @pytest.fixture
    def evaluator_with_full_data(self):
        """创建包含完整数据的评估器"""
        evaluator = MultiAgentEvaluator()
        current_time = time.time()

        # 注册Agents
        evaluator.agents = {
            "agent_001": AgentInfo(
                agent_id="agent_001",
                role="coordinator",
                capabilities=["planning"],
                status="active",
                message_count=5,
                completed_tasks=3,
                failed_tasks=1,
            ),
            "agent_002": AgentInfo(
                agent_id="agent_002",
                role="worker",
                capabilities=["execution"],
                status="active",
                message_count=3,
                completed_tasks=2,
                failed_tasks=0,
            ),
        }

        # 添加消息
        evaluator.messages = [
            AgentMessage(
                message_id="msg_001",
                sender_id="agent_001",
                receiver_id="agent_002",
                message_type=MessageType.REQUEST,
                content="Task assignment",
                timestamp=current_time,
                latency_ms=50.0,
                is_delivered=True,
                is_acknowledged=True,
            ),
        ]

        # 添加任务
        evaluator.tasks = {
            "task_001": AgentTask(
                task_id="task_001",
                agent_id="agent_002",
                description="Task 1",
                status=TaskStatus.COMPLETED,
                assigned_at=current_time - 1.0,
                completed_at=current_time,
            ),
        }

        # 添加冲突
        evaluator.conflicts = [
            Conflict(
                conflict_id="conflict_001",
                conflict_type=ConflictType.TASK,
                agent_ids=["agent_001", "agent_002"],
                description="Test",
                timestamp=current_time,
                resolved=True,
                resolution="Fixed",
            ),
        ]

        return evaluator

    def test_analyze_overall_success(self, evaluator_with_full_data):
        """整体协作分析应成功"""
        analysis = evaluator_with_full_data._analyze_overall()

        # 强断言：验证业务逻辑
        assert analysis["agents_count"] == 2
        assert analysis["messages_count"] == 1
        assert analysis["tasks_count"] == 1
        assert analysis["conflicts_count"] == 1
        assert "communication" in analysis
        assert "tasks" in analysis
        assert "conflicts" in analysis
        assert "collaboration" in analysis
        assert analysis["overall_score"] > 0.0
        assert analysis["overall_score"] <= 1.0

    def test_analyze_session_success(self, evaluator_with_full_data):
        """会话分析应成功"""
        # 创建会话
        evaluator_with_full_data.collaboration_sessions["session_001"] = {
            "session_id": "session_001",
            "agent_ids": ["agent_001", "agent_002"],
            "goal": "Test",
            "start_time": time.time() - 10.0,
            "end_time": None,
            "status": "active",
        }

        analysis = evaluator_with_full_data._analyze_session("session_001")

        assert analysis["session_id"] == "session_001"
        assert "communication" in analysis
        assert "tasks" in analysis
        assert "conflicts" in analysis
        assert analysis["overall_score"] > 0.0
        assert analysis["duration_seconds"] >= 10.0

    def test_analyze_collaboration_quality(self, evaluator_with_full_data):
        """协作质量分析应正确计算"""
        analysis = evaluator_with_full_data._analyze_collaboration_quality()

        assert analysis["total_agents"] == 2
        assert analysis["active_agents"] == 2
        assert analysis["agent_utilization_rate"] > 0.0
        assert "load_balance_score" in analysis
        assert analysis["collaboration_score"] > 0.0


class TestCollaborationEvaluation:
    """协作评估测试"""

    @pytest.fixture
    def evaluator(self):
        return MultiAgentEvaluator()

    def test_evaluate_collaboration_with_imported_data(self, evaluator):
        """评估协作应正确导入临时数据"""
        request = EvaluationSchema(
            id="test_026",
            type="multi_agent",
            payload={
                "action": "evaluate",
                "agents": [
                    {
                        "agent_id": "agent_001",
                        "role": "coordinator",
                        "completed_tasks": 5,
                        "failed_tasks": 1,
                    },
                ],
                "messages": [
                    {
                        "sender_id": "agent_001",
                        "receiver_id": "agent_002",
                        "message_type": "request",
                        "is_delivered": True,
                        "is_acknowledged": True,
                    },
                ],
                "tasks": [
                    {
                        "task_id": "task_001",
                        "agent_id": "agent_001",
                        "status": "completed",
                    },
                ],
                "conflicts": [],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score > 0.0
        assert "agents_count" in result.data
        assert "messages_count" in result.data

        # 验证临时数据导入不影响原数据
        assert len(evaluator.agents) == 0  # 原数据应保持为空

    def test_analyze_collaboration_action(self, evaluator):
        """分析协作action应正确路由"""
        request = EvaluationSchema(
            id="test_027",
            type="multi_agent",
            payload={
                "action": "analyze",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert "overall_score" in result.data


# ============================================================
# Part 8: 边界和异常场景测试
# ============================================================
class TestEdgeCases:
    """边界场景测试"""

    @pytest.fixture
    def evaluator(self):
        return MultiAgentEvaluator()

    def test_clear_data_success(self, evaluator):
        """清空数据应成功"""
        # 添加一些数据
        evaluator.agents["agent_001"] = AgentInfo(agent_id="agent_001", role="worker")
        evaluator.messages.append(
            AgentMessage(
                message_id="msg_001",
                sender_id="agent_001",
                receiver_id="agent_002",
                message_type=MessageType.REQUEST,
                content="Test",
                timestamp=time.time(),
            )
        )

        evaluator.clear_data()

        assert len(evaluator.agents) == 0
        assert len(evaluator.messages) == 0
        assert len(evaluator.tasks) == 0
        assert len(evaluator.conflicts) == 0
        assert len(evaluator.collaboration_sessions) == 0

    def test_message_with_malicious_content_sanitized(self, evaluator):
        """恶意内容消息应被清理"""
        request = EvaluationSchema(
            id="test_028",
            type="multi_agent",
            payload={
                "action": "record_message",
                "sender_id": "agent_001",
                "receiver_id": "agent_002",
                "message_type": "request",
                "content": "<script>alert('XSS')</script>Normal message",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 验证内容被清理
        stored_message = evaluator.messages[0]
        assert "<script>" not in stored_message.content
        assert "Normal message" in stored_message.content

    def test_task_with_malicious_description_sanitized(self, evaluator):
        """恶意任务描述应被清理"""
        evaluator.agents["agent_001"] = AgentInfo(agent_id="agent_001", role="worker")

        request = EvaluationSchema(
            id="test_029",
            type="multi_agent",
            payload={
                "action": "assign_task",
                "task_id": "task_001",
                "agent_id": "agent_001",
                "description": "<script>malicious</script>Valid task",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        stored_task = evaluator.tasks["task_001"]
        assert "<script>" not in stored_task.description
        assert "Valid task" in stored_task.description

    def test_unknown_action_returns_evaluation(self, evaluator):
        """未知action应返回评估结果"""
        request = EvaluationSchema(
            id="test_030",
            type="multi_agent",
            payload={
                "action": "unknown_action",
            },
        )

        result = evaluator.evaluate(request)

        # 未知action应默认执行evaluate
        assert result.is_valid is True


# ============================================================
# Part 9: 依赖和Mock测试
# ============================================================
class TestDependencyHandling:
    """依赖测试 - LLM客户端依赖"""

    def test_evaluator_without_llm_client_works(self):
        """无LLM客户端时评估器应正常工作"""
        evaluator = MultiAgentEvaluator(client=None)

        request = EvaluationSchema(
            id="test_031",
            type="multi_agent",
            payload={
                "action": "register_agent",
                "agent_id": "agent_001",
            },
        )

        result = evaluator.evaluate(request)

        # MultiAgentEvaluator不依赖LLM，应正常工作
        assert result.is_valid is True

    def test_evaluator_with_mock_client_works(self):
        """使用Mock客户端时应正常工作"""
        mock_client = MagicMock()
        mock_client.config = MagicMock()
        mock_client.config.model_name = "gpt-4"

        evaluator = MultiAgentEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="test_032",
            type="multi_agent",
            payload={
                "action": "analyze",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 验证client被正确注入
        assert evaluator.client is mock_client


# ============================================================
# Part 10: 工厂注册测试
# ============================================================
class TestEvaluatorFactoryRegistration:
    """评估器工厂注册测试"""

    def test_multi_agent_evaluator_registered(self):
        """MultiAgentEvaluator应已注册到工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        # 验证评估器已注册
        assert "multi_agent" in EvaluatorFactory._registry

        # 验证可以获取评估器
        evaluator = EvaluatorFactory.get("multi_agent")
        assert evaluator.__class__.__name__ == "MultiAgentEvaluator"

    def test_factory_creates_evaluator_with_client(self):
        """工厂应能创建带客户端的评估器"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        mock_client = MagicMock()
        evaluator = EvaluatorFactory.get("multi_agent", client=mock_client)

        assert evaluator.client is mock_client
