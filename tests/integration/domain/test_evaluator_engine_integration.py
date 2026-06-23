"""
Evaluator-Engine 集成测试
测试目标：验证 Engine 与各类评估器的完整集成流程
关键发现：
- Engine 负责 actual_output 生成与注入
- 评估器仅负责打分，不负责生成
- 支持在线实时评测和离线批量评测双模式
"""

from unittest.mock import MagicMock

import pytest

from src.engine import EvaluationEngine
from src.schemas.evaluation import EvaluationSchema
from src.schemas.schemas import EvaluationStatus


@pytest.fixture
def mock_llm_client():
    """Mock LLM客户端"""
    client = MagicMock()
    client.config = MagicMock()
    client.config.model_name = "test-model"
    client.chat.return_value = "模型生成的实际回答"
    return client


@pytest.fixture
def engine(mock_llm_client):
    """评估引擎实例"""
    return EvaluationEngine(mock_llm_client)


# ============================================================
# Part 1: 在线实时评测模式 - Engine 生成 actual_output
# ============================================================
class TestOnlineEvaluationMode:
    """在线实时评测 - Engine自动生成actual_output"""

    def test_engine_generates_actual_output_when_missing(self, engine, mock_llm_client):
        """缺少actual_output时Engine应调用LLM生成"""
        request = EvaluationSchema(
            id="online_001",
            type="semantic",
            payload={
                "prompt": "如何重置密码？",
                "expected_output": "点击右上角头像，进入设置-安全-重置密码。",
            },
        )

        engine.run(request)

        assert mock_llm_client.chat.called
        call_args = mock_llm_client.chat.call_args[0][0]
        assert "如何重置密码？" in call_args
        assert "actual_output" in request.payload
        assert request.payload["actual_output"] == "模型生成的实际回答"

    def test_engine_prefers_existing_actual_output(self, engine, mock_llm_client):
        """已有actual_output时Engine不应调用LLM"""
        request = EvaluationSchema(
            id="online_002",
            type="semantic",
            payload={
                "prompt": "如何重置密码？",
                "actual_output": "已有的实际回答",
                "expected_output": "期望输出",
            },
        )

        engine.run(request)

        assert not mock_llm_client.chat.called
        assert request.payload["actual_output"] == "已有的实际回答"

    def test_semantic_evaluator_with_engine_generated_output(self, engine):
        """语义评估器应能处理Engine生成的actual_output"""
        request = EvaluationSchema(
            id="online_003",
            type="semantic",
            payload={
                "prompt": "测试问题",
                "expected_output": "期望的标准答案",
            },
        )

        result = engine.run(request)

        assert result.status == EvaluationStatus.PASSED
        assert result.response.is_valid is True
        assert result.response.score is not None
        assert 0.0 <= result.response.score <= 1.0

    def test_grammar_evaluator_with_engine_generated_output(self, engine):
        """语法评估器应能处理Engine生成的actual_output"""
        request = EvaluationSchema(
            id="online_004",
            type="grammar",
            payload={
                "prompt": "请写一个正确的句子",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score is not None

    def test_text_evaluator_with_engine_generated_output(self, engine):
        """文本匹配评估器应能处理Engine生成的actual_output"""
        request = EvaluationSchema(
            id="online_005",
            type="text",
            payload={
                "prompt": "测试输入",
                "expected_output": "期望输出",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score is not None

    def test_translation_evaluator_with_engine_generated_output(self, engine):
        """翻译评估器应能处理Engine生成的actual_output"""
        request = EvaluationSchema(
            id="online_006",
            type="translation",
            payload={
                "prompt": "Hello, world!",
                "expected_output": "你好，世界！",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score is not None

    def test_summary_evaluator_with_engine_generated_output(self, engine):
        """摘要评估器应能处理Engine生成的actual_output"""
        request = EvaluationSchema(
            id="online_007",
            type="summary",
            payload={
                "prompt": "长文本内容需要摘要",
                "expected_output": "期望的摘要",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score is not None

    def test_qa_evaluator_with_engine_generated_output(self, engine):
        """问答评估器应能处理Engine生成的actual_output"""
        request = EvaluationSchema(
            id="online_008",
            type="qa",
            payload={
                "prompt": "中国的首都是什么？",
                "expected_output": "北京",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score is not None


# ============================================================
# Part 2: 离线批量评测模式 - 直接传入 actual_output
# ============================================================
class TestOfflineBatchEvaluationMode:
    """离线批量评测 - 直接传入actual_output"""

    def test_offline_mode_with_semantic_evaluator(self, engine):
        """语义评估器离线模式"""
        request = EvaluationSchema(
            id="offline_001",
            type="semantic",
            payload={
                "prompt": "如何重置密码？",
                "actual_output": "请进入设置页面点击重置。",
                "expected_output": "点击右上角头像，进入设置-安全-重置密码。",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score is not None
        assert result.response.text == "请进入设置页面点击重置。"

    def test_offline_mode_with_grammar_evaluator(self, engine):
        """语法评估器离线模式"""
        request = EvaluationSchema(
            id="offline_002",
            type="grammar",
            payload={
                "actual_output": "这是一个正确的句子。",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score == 1.0

    def test_offline_mode_with_text_evaluator(self, engine):
        """文本匹配评估器离线模式"""
        request = EvaluationSchema(
            id="offline_003",
            type="text",
            payload={
                "actual_output": "AI是人工智能的缩写",
                "expected_output": "AI是人工智能的缩写",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score == 1.0

    def test_offline_mode_with_translation_evaluator(self, engine):
        """翻译评估器离线模式"""
        request = EvaluationSchema(
            id="offline_004",
            type="translation",
            payload={
                "actual_output": "你好，世界！",
                "expected_output": "你好，世界！",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score == 1.0

    def test_offline_mode_with_summary_evaluator(self, engine):
        """摘要评估器离线模式"""
        request = EvaluationSchema(
            id="offline_005",
            type="summary",
            payload={
                "actual_output": "完全相同的摘要",
                "expected_output": "完全相同的摘要",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score == 1.0

    def test_offline_mode_with_qa_evaluator(self, engine):
        """问答评估器离线模式"""
        request = EvaluationSchema(
            id="offline_006",
            type="qa",
            payload={
                "actual_output": "北京是中国的首都",
                "expected_output": "北京是中国的首都",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score == 1.0

    def test_offline_mode_without_prompt(self, engine):
        """离线模式可以没有prompt"""
        request = EvaluationSchema(
            id="offline_007",
            type="semantic",
            payload={
                "actual_output": "实际输出内容",
                "expected_output": "期望输出内容",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score is not None


# ============================================================
# Part 3: 数据契约验证
# ============================================================
class TestPayloadContractValidation:
    """数据契约验证"""

    def test_missing_actual_output_and_prompt(self, engine):
        """缺少actual_output和prompt时应返回错误"""
        request = EvaluationSchema(
            id="contract_001",
            type="semantic",
            payload={
                "expected_output": "期望输出",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is False
        assert "actual_output" in result.response.error

    def test_missing_expected_output_for_comparison_evaluators(self, engine):
        """比较型评估器缺少expected_output时应返回错误"""
        request = EvaluationSchema(
            id="contract_002",
            type="semantic",
            payload={
                "actual_output": "实际输出",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is False
        assert "expected_output" in result.response.error

    def test_empty_actual_output(self, engine):
        """空actual_output应返回错误"""
        request = EvaluationSchema(
            id="contract_003",
            type="semantic",
            payload={
                "actual_output": "",
                "expected_output": "期望输出",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is False
        assert "actual_output" in result.response.error

    def test_empty_expected_output(self, engine):
        """空expected_output应返回错误"""
        request = EvaluationSchema(
            id="contract_004",
            type="semantic",
            payload={
                "actual_output": "实际输出",
                "expected_output": "",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is False
        assert "expected_output" in result.response.error

    def test_none_actual_output(self, engine):
        """None actual_output应返回错误"""
        request = EvaluationSchema(
            id="contract_005",
            type="semantic",
            payload={
                "actual_output": None,
                "expected_output": "期望输出",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is False

    def test_full_payload_contract(self, engine):
        """完整payload契约应正常工作"""
        request = EvaluationSchema(
            id="contract_006",
            type="semantic",
            payload={
                "prompt": "用户原始问题",
                "actual_output": "大模型的实际回答",
                "expected_output": "黄金标准/参考答案",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.text == "大模型的实际回答"


# ============================================================
# Part 4: 评估器类型兼容性
# ============================================================
class TestEvaluatorTypeCompatibility:
    """评估器类型兼容性"""

    def test_all_camp_b_evaluators_accept_actual_output(self, engine):
        """所有阵营B评估器应接受actual_output"""
        evaluator_types = ["semantic", "grammar", "text", "translation", "summary", "qa"]

        for eval_type in evaluator_types:
            request = EvaluationSchema(
                id=f"compat_{eval_type}",
                type=eval_type,
                payload={
                    "actual_output": "测试输出",
                    **({"expected_output": "测试期望"} if eval_type != "grammar" else {}),
                },
            )

            result = engine.run(request)

            assert result.response.is_valid is True, f"{eval_type} 评估器验证失败"
            assert result.response.score is not None, f"{eval_type} 评估器分数为空"

    def test_llm_as_judge_evaluator_with_actual_output(self, engine):
        """LLM-as-Judge评估器应能处理actual_output"""
        request = EvaluationSchema(
            id="compat_llm_judge",
            type="llm_as_judge",
            payload={
                "user_input": "测试问题",
                "actual_output": "测试回答",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score is not None


# ============================================================
# Part 5: 完整业务流程
# ============================================================
class TestFullBusinessWorkflow:
    """完整业务流程测试"""

    def test_customer_service_evaluation_flow(self, engine):
        """客服场景完整评测流程"""
        request = EvaluationSchema(
            id="workflow_001",
            type="semantic",
            payload={
                "prompt": "如何申请退款？",
                "actual_output": "您可以在订单页面申请退款",
                "expected_output": "在订单详情页点击退款按钮，填写退款原因后提交。",
            },
        )

        result = engine.run(request)

        assert result.case_id == "workflow_001"
        assert result.status in [EvaluationStatus.PASSED, EvaluationStatus.FAILED]
        assert result.model_name == "test-model"
        assert result.adapter_name == "SemanticEvaluator"
        assert result.response.is_valid is True
        assert result.response.score is not None
        assert result.latency_ms >= 0

    def test_multiple_evaluators_in_sequence(self, engine):
        """多评估器顺序评测"""
        requests = [
            EvaluationSchema(
                id="seq_001",
                type="semantic",
                payload={
                    "actual_output": "AI是人工智能",
                    "expected_output": "AI是人工智能的缩写",
                },
            ),
            EvaluationSchema(
                id="seq_002",
                type="grammar",
                payload={
                    "actual_output": "正确的句子。",
                },
            ),
            EvaluationSchema(
                id="seq_003",
                type="text",
                payload={
                    "actual_output": "完全匹配",
                    "expected_output": "完全匹配",
                },
            ),
        ]

        for req in requests:
            result = engine.run(req)
            assert result.response.is_valid is True
            assert result.case_id == req.id

    def test_real_world_chinese_scenario(self, engine):
        """真实中文场景评测"""
        request = EvaluationSchema(
            id="workflow_002",
            type="semantic",
            payload={
                "prompt": "解释什么是机器学习",
                "actual_output": "机器学习是人工智能的一个分支，它使计算机能够从数据中学习并做出决策，而无需明确编程。",
                "expected_output": "机器学习是人工智能的分支，通过算法让计算机从数据中学习模式和规律。",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score is not None
        assert 0.0 <= result.response.score <= 1.0
        assert "机器学习" in result.response.text


# ============================================================
# Part 6: 性能与边界测试
# ============================================================
class TestPerformanceAndBoundary:
    """性能与边界测试"""

    def test_latency_is_measured(self, engine):
        """延迟应被正确测量"""
        request = EvaluationSchema(
            id="perf_001",
            type="semantic",
            payload={
                "actual_output": "测试输出",
                "expected_output": "期望输出",
            },
        )

        result = engine.run(request)

        assert result.latency_ms >= 0
        assert isinstance(result.latency_ms, float)

    def test_very_long_text_input(self, engine):
        """超长文本输入应被正确处理"""
        long_text = "测试内容" * 1000
        request = EvaluationSchema(
            id="perf_002",
            type="semantic",
            payload={
                "actual_output": long_text,
                "expected_output": long_text,
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score == 1.0

    def test_unicode_chinese_input(self, engine):
        """Unicode中文输入应被正确处理"""
        request = EvaluationSchema(
            id="perf_003",
            type="semantic",
            payload={
                "actual_output": "你好，世界！这是一个中文测试。",
                "expected_output": "你好，世界！这是一个中文测试。",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score == 1.0

    def test_mixed_language_input(self, engine):
        """混合语言输入应被正确处理"""
        request = EvaluationSchema(
            id="perf_004",
            type="semantic",
            payload={
                "actual_output": "Hello世界，AI人工智能。",
                "expected_output": "Hello世界，AI人工智能。",
            },
        )

        result = engine.run(request)

        assert result.response.is_valid is True
        assert result.response.score == 1.0
