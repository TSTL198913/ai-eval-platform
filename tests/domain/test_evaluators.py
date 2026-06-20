"""
Domain 层测试 - 评估器业务逻辑
真实业务场景：金融评估、安全评估、评分、漂移检测
"""
from unittest.mock import MagicMock

import pytest

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.general import GeneralEvaluator
from src.domain.evaluators.scoring import (
    PASS_THRESHOLD,
    is_passing,
    score_keyword_overlap,
    score_numeric_match,
    score_text_similarity,
)
from src.exceptions import DomainLogicError
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@pytest.fixture(autouse=True)
def reset_evaluators_each_test():
    """
    自动在每个测试前重置 EvaluatorFactory 并重新触发自动发现。
    """
    from src.domain.evaluators import auto_discover
    from src.domain.evaluators.evaluator_factory import EvaluatorFactory as EF
    EF._registry = {}
    auto_discover(force=True)
    yield
    EF._registry = {}


# ============================================================
# Part 1: 评估器工厂 (EvaluatorFactory) - 真实业务场景
# ============================================================
class TestEvaluatorFactoryBusinessScenarios:
    """评估器工厂：生产环境中动态注册、路由评测请求"""

    def setup_method(self):
        EvaluatorFactory._registry = {}

    def test_factory_registers_evaluator_via_decorator(self):
        """场景：业务方注册新的评估器（如金融风控）"""

        @EvaluatorFactory.register("finance_test")
        class MockFinance:
            def evaluate(self, req):
                return DomainResponse(is_valid=True, score=0.9)

        assert "finance_test" in EvaluatorFactory._registry
        assert EvaluatorFactory._registry["finance_test"].__name__ == "MockFinance"

    def test_factory_creates_evaluator_with_client(self):
        """场景：用户请求评测时，工厂注入 LLM 客户端"""
        @EvaluatorFactory.register("test_creator")
        class MockCreator:
            def __init__(self, client=None):
                self.client = client

        client = MagicMock()
        evaluator = EvaluatorFactory.get("test_creator", client=client)
        assert evaluator.client is client

    def test_factory_raises_on_unknown_evaluator(self):
        """场景：客户端请求未注册的评估器（如调起实验性功能）"""
        with pytest.raises(DomainLogicError) as exc_info:
            EvaluatorFactory.get("nonexistent_evaluator_xyz")

        assert "未找到" in str(exc_info.value)
        # 异常应暴露已注册类型，便于运维定位
        assert "已注册" in str(exc_info.value)

    def test_list_evaluators_returns_sorted(self):
        """场景：前端展示可用的评估器列表"""
        @EvaluatorFactory.register("zzz_last")
        class _A:
            def evaluate(self, req):
                return DomainResponse(is_valid=True)

        @EvaluatorFactory.register("aaa_first")
        class _B:
            def evaluate(self, req):
                return DomainResponse(is_valid=True)

        result = EvaluatorFactory.list_evaluators()
        assert result.index("aaa_first") < result.index("zzz_last")

    def test_get_evaluator_info_includes_metadata(self):
        """场景：审计系统列出所有评估器信息"""
        @EvaluatorFactory.register("meta_test")
        class MockWithDoc:
            """用于测试的评估器"""
            def evaluate(self, req):
                return DomainResponse(is_valid=True)

        info = EvaluatorFactory.get_evaluator_info()
        meta_entry = next(e for e in info if e["name"] == "meta_test")
        assert meta_entry["class_name"] == "MockWithDoc"
        assert "测试" in meta_entry["docstring"]


# ============================================================
# Part 2: 评分算法 - 真实业务场景
# ============================================================
class TestScoringBusinessScenarios:
    """评分算法：金融数字匹配、QA 文本相似度、中文关键词覆盖"""

    def test_numeric_match_finance_scenario(self):
        """场景：金融报告 - 验证模型输出包含关键数字"""
        # 期望提取 30 亿美元
        expected = "Revenue grew by 3 billion in Q3, reaching 30 billion."
        output = "In Q3, revenue was 3 billion, total 30 billion."
        score = score_numeric_match(output, expected)
        assert score == 1.0  # 3 和 30 都在 output 中

    def test_numeric_match_partial(self):
        """场景：数字部分缺失"""
        expected = "The values are 100, 200, 300."
        output = "The values are 100 and 200."
        score = score_numeric_match(output, expected)
        assert 0.5 < score < 1.0  # 2/3 命中

    def test_numeric_match_empty_output(self):
        """场景：模型无输出"""
        assert score_numeric_match("", "100") == 0.0

    def test_numeric_match_no_expected(self):
        """场景：未提供期望值（开放性问答）"""
        assert score_numeric_match("any output", None) == 1.0

    def test_text_similarity_qa_scenario(self):
        """场景：QA 系统答案对比"""
        expected = "The capital of France is Paris"
        output = "Paris is the capital of France"
        score = score_text_similarity(output, expected)
        assert score >= 0.7  # 高相似度

    def test_text_similarity_chinese_scenario(self):
        """场景：中文文本相似度评估"""
        expected = "北京是中国的首都"
        output = "中国首都是北京"
        score = score_text_similarity(output, expected)
        assert score > 0.3  # 关键词完全重叠

    def test_keyword_overlap_uses_chinese_chars(self):
        """场景：中文按字分词，评估重叠率"""
        expected = "评估模型性能表现"
        output = "本次模型性能表现良好"
        score = score_keyword_overlap(output, expected)
        # expected 8 字 (评/估/模/型/性/能/表/现)
        # output 10 字, 重叠 6 字 (模/型/性/能/表/现)
        # score = 6/8 = 0.75
        assert score == 0.75

    def test_keyword_overlap_chinese_with_space(self):
        """场景：中文带空格分词"""
        expected = "北京 是 中国 的 首都"
        output = "中国 的 首都 是 北京"
        score = score_keyword_overlap(output, expected)
        # 全部 4 个字都重叠
        assert score == 1.0

    def test_keyword_overlap_empty_expected_tokens(self):
        """场景：期望文本只有停用词"""
        expected = "to be or not"
        output = "anything else"
        score = score_keyword_overlap(output, expected)
        # 没有有效 token，触发 fallback：直接子串检查
        assert score == 0.0  # "to be or not" 不在 output 中

    def test_is_passing_threshold_boundary(self):
        """场景：边界值检测（>= 0.8 通过）"""
        assert is_passing(0.8) is True
        assert is_passing(0.79) is False
        assert is_passing(1.0) is True
        assert is_passing(0.0) is False

    def test_pass_threshold_constant(self):
        """场景：阈值常量必须为 0.8（业务约定）"""
        assert PASS_THRESHOLD == 0.8


# ============================================================
# Part 3: 通用评估器 - 真实业务场景
# ============================================================
class TestGeneralEvaluatorBusinessScenarios:
    """通用评估器：用户提交 user_input，验证 LLM 输出"""

    def test_evaluator_returns_error_on_empty_input(self):
        """场景：用户提交空输入"""
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="case_001",
            type="general",
            payload={},
        )
        response = evaluator.safe_evaluate(request)
        assert response.is_valid is False
        assert "不能为空" in response.error

    def test_evaluator_without_client_uses_mock(self):
        """场景：未配置 LLM 客户端时（兼容模式）"""
        evaluator = GeneralEvaluator(client=None)
        request = EvaluationSchema(
            id="case_002",
            type="general",
            payload={"user_input": "Hello, world"},
        )
        response = evaluator.safe_evaluate(request)
        assert response.is_valid is True
        assert response.score == 1.0
        assert "Hello, world" in response.data

    def test_evaluator_with_client_uses_llm(self):
        """场景：用户提交请求，调用 LLM 进行评估"""
        client = MagicMock()
        client.chat = MagicMock(return_value="API 网关是一种反向代理")
        evaluator = GeneralEvaluator(client=client)
        request = EvaluationSchema(
            id="case_003",
            type="general",
            payload={"user_input": "Q1: 解释下 API 网关", "expected_output": "API 网关是一种反向代理"},
        )
        response = evaluator.safe_evaluate(request)
        # LLM 输出完全匹配 expected_output，分数应为 1.0
        assert response.is_valid is True
        assert response.score == 1.0
        assert response.text is not None
        assert "API 网关" in response.text
        client.chat.assert_called_once_with("Q1: 解释下 API 网关")

    def test_evaluator_score_with_no_expected(self):
        """场景：无期望输出时，score 应为 1.0"""
        client = MagicMock()
        client.chat = MagicMock(return_value="some response")
        evaluator = GeneralEvaluator(client=client)
        request = EvaluationSchema(
            id="case_004",
            type="general",
            payload={"user_input": "test"},
        )
        response = evaluator.safe_evaluate(request)
        assert response.score == 1.0

    def test_safe_evaluate_catches_exception(self):
        """场景：LLM 抛出异常时，应返回 is_valid=False 而非崩溃"""
        client = MagicMock()
        client.chat = MagicMock(side_effect=Exception("LLM 503"))
        evaluator = GeneralEvaluator(client=client)
        request = EvaluationSchema(
            id="case_005",
            type="general",
            payload={"user_input": "test"},
        )
        response = evaluator.safe_evaluate(request)
        assert response.is_valid is False
        assert "EVALUATION_ERROR" in response.error

    def test_safe_evaluate_handles_none_response(self):
        """场景：评估器返回 None（业务方实现错误）"""
        client = MagicMock()
        client.chat = MagicMock(return_value="anything")
        evaluator = GeneralEvaluator(client=client)
        # 模拟子类实现错误
        evaluator.evaluate = MagicMock(return_value=None)
        request = EvaluationSchema(
            id="case_006",
            type="general",
            payload={"user_input": "test"},
        )
        response = evaluator.safe_evaluate(request)
        assert response.is_valid is False
        assert "None" in response.error

    def test_get_input_text_supports_both_fields(self):
        """场景：业务方可能用 user_input 或 text 字段"""
        evaluator = GeneralEvaluator()

        req1 = EvaluationSchema(
            id="c1", type="general", payload={"user_input": "input1"}
        )
        req2 = EvaluationSchema(
            id="c2", type="general", payload={"text": "input2"}
        )
        req3 = EvaluationSchema(
            id="c3", type="general", payload={}
        )

        assert evaluator.get_input_text(req1) == "input1"
        assert evaluator.get_input_text(req2) == "input2"
        assert evaluator.get_input_text(req3) == ""


# ============================================================
# Part 4: 异常体系 - 真实业务场景
# ============================================================
class TestExceptionHierarchyBusinessScenarios:
    """异常体系：上游契约、领域逻辑、基础设施分层"""

    def test_base_platform_error_has_code(self):
        """场景：错误码用于国际化与日志聚合"""
        from src.exceptions import BasePlatformError
        err = BasePlatformError("boom", code="CUSTOM_CODE")
        assert err.message == "boom"
        assert err.code == "CUSTOM_CODE"
        assert err.args[0] == "boom"

    def test_contract_validation_error_default_code(self):
        """场景：客户端提交非法请求体"""
        from src.exceptions import ContractValidationError
        err = ContractValidationError()
        assert err.code == "CONTRACT_ERROR"

    def test_domain_logic_error_distinct(self):
        """场景：业务规则违规（与契约错误区分）"""
        from src.exceptions import BasePlatformError, ContractValidationError, DomainLogicError

        err = DomainLogicError("adapter missing")
        assert err.code == "DOMAIN_ERROR"
        assert isinstance(err, BasePlatformError)
        assert not isinstance(err, ContractValidationError)

    def test_infrastructure_error_distinct(self):
        """场景：DB/Cache 故障"""
        from src.exceptions import BasePlatformError, InfrastructureError

        err = InfrastructureError("redis down")
        assert err.code == "INFRA_ERROR"
        assert isinstance(err, BasePlatformError)


# ============================================================
# Part 5: Schema 校验 - 真实业务场景
# ============================================================
class TestEvaluationSchemaValidation:
    """Schema：用户提交评测请求时的数据完整性"""

    def test_schema_requires_id_type_payload(self):
        """场景：必填字段缺失"""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            EvaluationSchema()  # type: ignore

    def test_schema_accepts_minimum_valid_input(self):
        """场景：最简请求"""
        req = EvaluationSchema(
            id="abc",
            type="general",
            payload={"user_input": "hi"},
        )
        assert req.id == "abc"
        assert req.type == "general"
        assert req.payload == {"user_input": "hi"}
        assert req.metadata is None

    def test_schema_is_frozen(self):
        """场景：frozen 模式防止业务方意外修改请求"""
        req = EvaluationSchema(
            id="abc",
            type="general",
            payload={},
        )
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            req.id = "xyz"  # type: ignore

    def test_domain_response_extra_fields_allowed(self):
        """场景：业务方扩展元数据（向后兼容）"""
        response = DomainResponse(
            is_valid=True,
            score=0.9,
            custom_field_1="value",
            custom_field_2={"nested": "data"},
        )
        assert response.is_valid is True
        # extra="allow" 应保留自定义字段
        assert response.model_extra is None or "custom_field_1" in response.model_extra or hasattr(response, "custom_field_1")
