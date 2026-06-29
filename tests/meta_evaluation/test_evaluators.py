"""
元评估（Meta-Evaluation）测试基准
================================

测试目标：校准 LLMAJudgeEvaluator 的"度量衡"，确保评估器自身在
面对 LLM 裁判返回的异常输入时仍然具备防御性。

4 大"毒药 Case"（Poison Cases）：

  1. 【类型投毒 Case】 - LLM 返回 "score": "85%" / "90" 等字符串
     预期：评估器必须强转 float 并完成数学计算，is_valid=True

  2. 【格式崩坏 Case】 - LLM 返回 "Internal Server Error" 等纯文本
     预期：必须返回 is_valid=False, score=0.0，绝不能静默通过

  3. 【语义冲突 Case】 - 阿司匹林医疗场景：实际输出与期望输出严重冲突
     预期：accuracy < 40 分，conflict_detected=True

  4. 【客服废话 Case】 - 用户问"什么时候到账"，答非所问的长篇套话
     预期：relevance < 50，conciseness < 50

关键发现：
  - 评估器必须对 LLM 返回的字段做防御性类型强转（_coerce_score）
  - 解析失败不能默认 0.5 分通过，必须 is_valid=False 暴露问题
  - 字符串百分号"85%"和字符串数字"90"必须被识别为有效数值
"""

import json
from unittest.mock import MagicMock

import pytest

from src.domain.evaluators.llm_as_judge import LLMAJudgeEvaluator
from src.schemas.evaluation import EvaluationSchema

# ============================================================
# 共享 Fixtures
# ============================================================


@pytest.fixture
def evaluator():
    """提供 LLMAJudgeEvaluator 实例（无 client，使用 mock）"""
    return LLMAJudgeEvaluator()


def _make_mock_client(return_value):
    """构造一个返回指定值的 mock LLM client"""
    client = MagicMock()
    client.config = MagicMock()
    client.config.model_name = "mock-judge"
    client.chat = MagicMock(return_value=return_value)
    return client


# ============================================================
# 毒药 Case 1: 类型投毒
# ============================================================


class TestTypePoisoning:
    """【类型投毒 Case】

    LLM 裁判返回的 score 字段是字符串（带百分号或纯数字），
    评估器必须用防御性代码将其强转为 float，且不抛异常。
    """

    @pytest.fixture
    def poisoned_payload(self):
        """构造 LLM 返回字符串类型评分的恶意 JSON"""
        return json.dumps(
            {
                "scores": {
                    "accuracy": {
                        "score": "85%",  # 毒：带百分号的字符串
                        "level": "good",
                        "reason": "事实基本正确",
                        "evidence": ["原文引用1"],
                        "citation": "无",
                    },
                    "relevance": {
                        "score": "90",  # 毒：纯数字字符串
                        "level": "excellent",
                        "reason": "回答了用户问题",
                        "evidence": ["原文引用2"],
                        "citation": "无",
                    },
                    "safety": {
                        "score": 100,  # 正常 int
                        "level": "excellent",
                        "reason": "无有害内容",
                        "evidence": ["原文引用3"],
                        "citation": "无",
                    },
                    "coherence": {
                        "score": "75.5 ",  # 毒：含空白的数字字符串
                        "level": "good",
                        "reason": "逻辑清晰",
                        "evidence": ["原文引用4"],
                        "citation": "无",
                    },
                    "completeness": {
                        "score": 80,  # 正常 int
                        "level": "good",
                        "reason": "覆盖主要要点",
                        "evidence": ["原文引用5"],
                        "citation": "无",
                    },
                    "conciseness": {
                        "score": "82",  # 毒：字符串
                        "level": "good",
                        "reason": "简洁明了",
                        "evidence": ["原文引用6"],
                        "citation": "无",
                    },
                },
                "total_score": "84.5",  # 毒：total_score 也是字符串
                "confidence": "0.85",  # 毒：confidence 是字符串
                "conflict_detected": False,
                "summary": "整体质量良好（字符串类型评分测试）",
                "improvement_suggestions": ["可补充更多细节"],
            },
            ensure_ascii=False,
        )

    def test_string_percent_score_is_coerced_to_float(self, evaluator, poisoned_payload):
        """【核心断言1】带百分号的字符串 score 字段必须被强转为 float

        不允许：抛出 TypeError: can't multiply sequence by non-int
        """
        evaluator.client = _make_mock_client(poisoned_payload)
        request = EvaluationSchema(
            id="poison-type-1",
            type="llm_as_judge",
            payload={
                "user_input": "商品多久发货？",
                "actual_output": "您好，将在3个工作日内发货，请耐心等待。",
                "expected_output": "3个工作日内发货",
            },
        )

        # 必须不抛任何异常
        result = evaluator.evaluate(request)

        # 强断言：评估器必须识别为有效评估
        assert result.is_valid is True, (
            f"类型投毒场景下评估器不应拒绝评估，实际 error={result.error}"
        )
        # score 字段必须存在且为 float，不能为 None
        assert result.score is not None, "score 不能为 None"
        assert isinstance(result.score, int | float), (
            f"score 必须是数值类型，实际类型={type(result.score).__name__}"
        )
        assert 0.0 <= result.score <= 1.0, f"score 必须在 [0, 1] 区间，实际={result.score}"

    def test_string_score_math_actually_works(self, evaluator, poisoned_payload):
        """【核心断言2】加权计算必须真的用了被强转后的 float"""
        evaluator.client = _make_mock_client(poisoned_payload)
        request = EvaluationSchema(
            id="poison-type-2",
            type="llm_as_judge",
            payload={
                "user_input": "商品多久发货？",
                "actual_output": "您好，将在3个工作日内发货。",
            },
        )

        result = evaluator.evaluate(request)

        # 强断言：data 中的 weighted_total_score 必须存在且合法
        assert "weighted_total_score" in result.data
        weighted = result.data["weighted_total_score"]
        assert isinstance(weighted, int | float), (
            f"weighted_total_score 必须是数值，实际类型={type(weighted).__name__}"
        )
        assert 0.0 <= weighted <= 100.0, (
            f"weighted_total_score 必须在 [0, 100] 区间，实际={weighted}"
        )
        # 由于 scores 范围在 75-100 之间，加权分必须高于 50
        assert weighted > 50, (
            f"加权分应反映 LLM 给出的高分（>50），实际={weighted}，说明字符串评分未被正确强转"
        )

    def test_coerce_score_helper_handles_all_poison_types(self, evaluator):
        """【单元断言】_coerce_score 必须能处理所有毒类型"""
        # 字符串百分号
        assert evaluator._coerce_score("85%") == 85.0
        # 纯数字字符串
        assert evaluator._coerce_score("90") == 90.0
        # 含空白字符串
        assert evaluator._coerce_score(" 75.5 ") == 75.5
        # 正常 int / float
        assert evaluator._coerce_score(100) == 100.0
        assert evaluator._coerce_score(85.5) == 85.5
        # 非法值必须规整为 0.0
        assert evaluator._coerce_score(None) == 0.0
        assert evaluator._coerce_score("") == 0.0
        assert evaluator._coerce_score("N/A") == 0.0
        assert evaluator._coerce_score("abc") == 0.0
        # 超界值必须 clamp 到 [0, 100]
        assert evaluator._coerce_score(150) == 100.0
        assert evaluator._coerce_score(-10) == 0.0
        assert evaluator._coerce_score("200%") == 100.0
        # bool 被视为非法（避免 True/False 被当 1/0）
        assert evaluator._coerce_score(True) == 0.0
        assert evaluator._coerce_score(False) == 0.0


# ============================================================
# 毒药 Case 2: 格式崩坏
# ============================================================


class TestFormatCorruption:
    """【格式崩坏 Case】

    LLM 返回完全无法解析的纯文本（如 "Internal Server Error"），
    评估器必须暴露此失败，绝不能静默通过返回 score=0.5。
    """

    @pytest.mark.parametrize(
        "garbage_text",
        [
            "Internal Server Error",
            "upstream connect error or disconnect/reset before headers",
            "抱歉，服务暂不可用，请稍后重试",
            "",  # 空字符串
            "   \n\t  ",  # 纯空白
            "Status code: 503",  # 数字也算
        ],
    )
    def test_unparseable_output_must_return_invalid(self, evaluator, garbage_text):
        """【核心断言】完全无法解析的输出必须返回 is_valid=False, score=0.0

        绝不能静默通过为 score=0.5 这种"看起来还行"的伪成功。
        """
        evaluator.client = _make_mock_client(garbage_text)
        request = EvaluationSchema(
            id="poison-format-1",
            type="llm_as_judge",
            payload={
                "user_input": "什么时候到账？",
                "actual_output": "您好，预计1-2个工作日到账。",
            },
        )

        result = evaluator.evaluate(request)

        # 强断言：必须显式标记为失败
        assert result.is_valid is False, (
            f"无法解析的 LLM 输出应导致 is_valid=False，"
            f"实际 is_valid={result.is_valid}, score={result.score}"
        )
        # 强断言：score 必须为 0.0（不是 0.5、不是 None）
        assert result.score == 0.0, (
            f"格式崩坏场景下 score 必须为 0.0，实际={result.score}（类型={type(result.score).__name__}）"
        )
        # 必须有 error 字段说明原因
        assert result.error is not None and len(result.error) > 0, (
            "失败时必须提供 error 字段说明失败原因"
        )

    def test_broken_json_with_no_recoverable_structure(self, evaluator):
        """【边界断言】包含 { } 但 JSON 损坏的情况也必须返回失败"""
        # 看起来像 JSON 但实际是损坏的
        broken = "{ this is not valid json, score: 'broken' }"
        evaluator.client = _make_mock_client(broken)
        request = EvaluationSchema(
            id="poison-format-2",
            type="llm_as_judge",
            payload={
                "user_input": "测试问题",
                "actual_output": "测试输出",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert result.score == 0.0

    def test_json_with_empty_scores_returns_zero_score(self, evaluator):
        """【边界断言】LLM 返回了合法 JSON 但 scores 字段为空 → 分数为 0.0

        注：空 scores 不算"格式崩坏"（JSON 本身合法），应视为有效评估
        得出 0 分。仅当 LLM 输出本身无法解析时才返回 is_valid=False。
        """
        empty_scores_json = json.dumps(
            {
                "scores": {},
                "total_score": 0,
                "confidence": 0,
                "conflict_detected": False,
                "summary": "",
                "improvement_suggestions": [],
            }
        )
        evaluator.client = _make_mock_client(empty_scores_json)
        request = EvaluationSchema(
            id="poison-format-3",
            type="llm_as_judge",
            payload={
                "user_input": "测试问题",
                "actual_output": "测试输出",
            },
        )

        result = evaluator.evaluate(request)

        # 空 scores → score 必须为 0.0（加权分无维度可计算）
        assert result.score == 0.0
        assert result.data["weighted_total_score"] == 0.0

    def test_fallback_response_data_structure_complete(self, evaluator):
        """【结构断言】失败响应的 data 字段必须包含完整的错误定位信息"""
        evaluator.client = _make_mock_client("Some unexpected error")
        request = EvaluationSchema(
            id="poison-format-4",
            type="llm_as_judge",
            payload={
                "user_input": "测试",
                "actual_output": "测试输出",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        # data 字段应保留原始输出的预览，便于排查
        assert "raw_output_preview" in result.data
        assert "weighted_total_score" in result.data
        assert result.data["weighted_total_score"] == 0.0


# ============================================================
# 毒药 Case 3: 语义冲突
# ============================================================


class TestSemanticConflict:
    """【语义冲突 Case】

    医疗场景：用户问"病人能吃阿司匹林吗？"
    - 期望输出：不能吃，过敏
    - 实际输出：可以放心服用

    评估器必须识别 accuracy 极低（<40）且存在冲突。
    """

    ASPIRIN_USER_INPUT = "病人能吃阿司匹林吗？"
    ASPIRIN_EXPECTED = "不能吃，会引起过敏反应"
    ASPIRIN_ACTUAL = "可以放心服用"

    @pytest.fixture
    def conflict_payload(self):
        """构造 LLM 识别出冲突并打低分的恶意/合理 JSON"""
        return json.dumps(
            {
                "scores": {
                    "accuracy": {
                        "score": 15,  # 极低分：实际输出与医学事实严重冲突
                        "level": "very_poor",
                        "reason": "实际输出与期望输出严重冲突：用户对阿司匹林过敏，实际输出却说可以放心服用，可能导致严重医疗事故",
                        "evidence": [
                            "期望：不能吃，会引起过敏反应",
                            "实际：可以放心服用",
                        ],
                        "citation": "医学常识",
                    },
                    "relevance": {
                        "score": 70,
                        "level": "acceptable",
                        "reason": "回答了用户问题，但方向错误",
                        "evidence": ["提到了阿司匹林"],
                        "citation": "无",
                    },
                    "safety": {
                        "score": 10,  # 医疗安全极低
                        "level": "very_poor",
                        "reason": "医疗建议存在严重安全风险，可能危及患者生命",
                        "evidence": ["实际：可以放心服用"],
                        "citation": "医疗安全规范",
                    },
                    "coherence": {
                        "score": 50,
                        "level": "acceptable",
                        "reason": "回答语句通顺但内容错误",
                        "evidence": ["可以放心服用"],
                        "citation": "无",
                    },
                    "completeness": {
                        "score": 30,
                        "level": "very_poor",
                        "reason": "未提及过敏禁忌",
                        "evidence": [],
                        "citation": "无",
                    },
                    "conciseness": {
                        "score": 85,
                        "level": "good",
                        "reason": "回答简洁",
                        "evidence": ["可以放心服用"],
                        "citation": "无",
                    },
                },
                "total_score": 38,
                "confidence": 0.92,
                "conflict_detected": True,  # 关键：LLM 必须识别出冲突
                "summary": "实际输出与期望输出存在严重语义冲突",
                "improvement_suggestions": [
                    "必须先确认患者过敏史",
                    "严禁对阿司匹林过敏者推荐服用",
                ],
            },
            ensure_ascii=False,
        )

    def test_accuracy_score_below_40(self, evaluator, conflict_payload):
        """【核心断言1】accuracy 分数必须 < 40"""
        evaluator.client = _make_mock_client(conflict_payload)
        request = EvaluationSchema(
            id="poison-semantic-1",
            type="llm_as_judge",
            payload={
                "user_input": self.ASPIRIN_USER_INPUT,
                "actual_output": self.ASPIRIN_ACTUAL,
                "expected_output": self.ASPIRIN_EXPECTED,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True, "评估器应能解析 LLM 输出"
        accuracy_score = result.data["llm_judge_scores"]["accuracy"]["score"]
        assert accuracy_score < 40, (
            f"语义冲突场景下 accuracy 必须 < 40，实际={accuracy_score}，说明评估器未识别出严重冲突"
        )

    def test_conflict_detected_must_be_true(self, evaluator, conflict_payload):
        """【核心断言2】data.conflict_detected 必须为 True"""
        evaluator.client = _make_mock_client(conflict_payload)
        request = EvaluationSchema(
            id="poison-semantic-2",
            type="llm_as_judge",
            payload={
                "user_input": self.ASPIRIN_USER_INPUT,
                "actual_output": self.ASPIRIN_ACTUAL,
                "expected_output": self.ASPIRIN_EXPECTED,
            },
        )

        result = evaluator.evaluate(request)

        assert result.data["conflict_detected"] is True, (
            f"语义冲突场景下 conflict_detected 必须为 True，"
            f"实际={result.data.get('conflict_detected')}"
        )

    def test_weighted_score_also_below_50(self, evaluator, conflict_payload):
        """【推论断言】由于 accuracy 极低且 safety 极低，加权分必须 < 50"""
        evaluator.client = _make_mock_client(conflict_payload)
        request = EvaluationSchema(
            id="poison-semantic-3",
            type="llm_as_judge",
            payload={
                "user_input": self.ASPIRIN_USER_INPUT,
                "actual_output": self.ASPIRIN_ACTUAL,
                "expected_output": self.ASPIRIN_EXPECTED,
            },
        )

        result = evaluator.evaluate(request)

        weighted = result.data["weighted_total_score"]
        # accuracy 权重 0.25 + safety 权重 0.20 = 0.45 占比
        # 15 * 0.25 + 10 * 0.20 + ... 必然导致总分 < 40
        assert weighted < 50, f"语义冲突场景下加权分应 < 50，实际={weighted}"

    def test_evaluator_propagates_conflict_flag_for_downstream_alerting(
        self, evaluator, conflict_payload
    ):
        """【集成断言】conflict_detected 字段必须能透传到 data 顶层

        下游告警系统依赖 data['conflict_detected'] 触发人工复核流程，
        评估器不能把这个标志位吞掉。
        """
        evaluator.client = _make_mock_client(conflict_payload)
        request = EvaluationSchema(
            id="poison-semantic-4",
            type="llm_as_judge",
            payload={
                "user_input": self.ASPIRIN_USER_INPUT,
                "actual_output": self.ASPIRIN_ACTUAL,
                "expected_output": self.ASPIRIN_EXPECTED,
            },
        )

        result = evaluator.evaluate(request)

        # 必须有 data 字段
        assert result.data is not None
        # conflict_detected 必须存在于顶层 data 中（不嵌套在子字典里）
        assert "conflict_detected" in result.data
        assert result.data["conflict_detected"] is True


# ============================================================
# 毒药 Case 4: 客服废话
# ============================================================


class TestCustomerServiceFluff:
    """【客服废话 Case】

    用户问"什么时候到账？"
    实际输出：长篇客服套话，唯独没有提及时间。
    预期：relevance < 50，conciseness < 50
    """

    @pytest.fixture
    def fluff_payload(self):
        """构造 LLM 识别出回答跑题且啰嗦的 JSON"""
        return json.dumps(
            {
                "scores": {
                    "accuracy": {
                        "score": 40,
                        "level": "poor",
                        "reason": "回答未提供具体到账时间",
                        "evidence": ["回答中没有任何时间信息"],
                        "citation": "无",
                    },
                    "relevance": {
                        "score": 30,  # 严重跑题
                        "level": "very_poor",
                        "reason": "用户问'什么时候到账'，回答全篇是感谢、道歉、品牌宣传，未提及到账时间",
                        "evidence": [
                            "非常感谢您的支持",
                            "我们会持续改进",
                            "我们的服务理念是",
                        ],
                        "citation": "无",
                    },
                    "safety": {
                        "score": 95,
                        "level": "excellent",
                        "reason": "无有害内容",
                        "evidence": [],
                        "citation": "无",
                    },
                    "coherence": {
                        "score": 60,
                        "level": "acceptable",
                        "reason": "语句通顺但内容冗余",
                        "evidence": [],
                        "citation": "无",
                    },
                    "completeness": {
                        "score": 20,  # 完全没回答时间问题
                        "level": "very_poor",
                        "reason": "完全未回答用户的核心问题：到账时间",
                        "evidence": [],
                        "citation": "无",
                    },
                    "conciseness": {
                        "score": 25,  # 严重啰嗦
                        "level": "very_poor",
                        "reason": "大段客套话，200字没有一句有效信息",
                        "evidence": [
                            "非常非常感谢您选择我们的平台",
                            "我们一直致力于",
                            "如有其他问题欢迎随时联系",
                        ],
                        "citation": "无",
                    },
                },
                "total_score": 45,
                "confidence": 0.88,
                "conflict_detected": False,
                "summary": "回答严重跑题且冗长，未提供用户所需的到账时间",
                "improvement_suggestions": [
                    "必须先直接回答用户问题",
                    "删减所有客套话",
                    "明确告知到账时间（如1-3个工作日）",
                ],
            },
            ensure_ascii=False,
        )

    USER_INPUT = "什么时候到账？"
    FLUFFY_OUTPUT = (
        "非常非常感谢您选择我们的平台！您的问题我们已收到，我们会尽快为您处理。"
        "我们一直致力于为每一位用户提供最优质的服务，您的满意是我们前进的动力。"
        "如您还有其他问题，欢迎随时联系我们的客服人员，我们将竭诚为您服务。"
        "再次感谢您的支持与信任！"
    )

    def test_relevance_below_50(self, evaluator, fluff_payload):
        """【核心断言1】relevance 分数必须 < 50"""
        evaluator.client = _make_mock_client(fluff_payload)
        request = EvaluationSchema(
            id="poison-fluff-1",
            type="llm_as_judge",
            payload={
                "user_input": self.USER_INPUT,
                "actual_output": self.FLUFFY_OUTPUT,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        relevance_score = result.data["llm_judge_scores"]["relevance"]["score"]
        assert relevance_score < 50, f"客服废话场景下 relevance 必须 < 50，实际={relevance_score}"

    def test_conciseness_below_50(self, evaluator, fluff_payload):
        """【核心断言2】conciseness 分数必须 < 50"""
        evaluator.client = _make_mock_client(fluff_payload)
        request = EvaluationSchema(
            id="poison-fluff-2",
            type="llm_as_judge",
            payload={
                "user_input": self.USER_INPUT,
                "actual_output": self.FLUFFY_OUTPUT,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        conciseness_score = result.data["llm_judge_scores"]["conciseness"]["score"]
        assert conciseness_score < 50, (
            f"客服废话场景下 conciseness 必须 < 50，实际={conciseness_score}"
        )

    def test_both_relevance_and_conciseness_below_50(self, evaluator, fluff_payload):
        """【组合断言】relevance 和 conciseness 必须同时 < 50"""
        evaluator.client = _make_mock_client(fluff_payload)
        request = EvaluationSchema(
            id="poison-fluff-3",
            type="llm_as_judge",
            payload={
                "user_input": self.USER_INPUT,
                "actual_output": self.FLUFFY_OUTPUT,
            },
        )

        result = evaluator.evaluate(request)

        scores = result.data["llm_judge_scores"]
        relevance = scores["relevance"]["score"]
        conciseness = scores["conciseness"]["score"]

        # 强断言：两个维度都必须低分
        assert relevance < 50 and conciseness < 50, (
            f"客服废话场景下 relevance 和 conciseness 都必须 < 50，"
            f"实际 relevance={relevance}, conciseness={conciseness}"
        )
        # 强断言：completeness 也要低（没回答问题）
        assert scores["completeness"]["score"] < 50, (
            f"客服废话场景下 completeness 应 < 50（没回答问题），"
            f"实际={scores['completeness']['score']}"
        )

    def test_safety_still_high_despite_fluff(self, evaluator, fluff_payload):
        """【对照断言】safety 仍然要高（废话≠有害），说明评估器能区分维度"""
        evaluator.client = _make_mock_client(fluff_payload)
        request = EvaluationSchema(
            id="poison-fluff-4",
            type="llm_as_judge",
            payload={
                "user_input": self.USER_INPUT,
                "actual_output": self.FLUFFY_OUTPUT,
            },
        )

        result = evaluator.evaluate(request)

        safety = result.data["llm_judge_scores"]["safety"]["score"]
        assert safety >= 80, (
            f"客服废话不涉及安全风险，safety 应保持高分（>=80），"
            f"实际={safety}，说明评估器把废话误判为安全风险"
        )


# ============================================================
# 元评估：使用评估器自身评估这 4 个毒药 Case
# ============================================================


class TestMetaEvaluationSummary:
    """元评估汇总：4 大毒药 Case 的端到端验证

    每个毒药 Case 都必须能被评估器自身正确识别为：
    - 类型投毒 → 评估有效
    - 格式崩坏 → 评估失败
    - 语义冲突 → 冲突被识别
    - 客服废话 → 低相关性、低简洁性
    """

    def test_all_poison_cases_handled_gracefully(self, evaluator):
        """【端到端】4 大毒药 Case 都必须被正确处理，无崩溃"""
        poison_payloads = [
            # 类型投毒：字符串评分
            json.dumps(
                {
                    "scores": {
                        "accuracy": {
                            "score": "85%",
                            "level": "good",
                            "reason": "r",
                            "evidence": [],
                            "citation": "无",
                        },
                        "relevance": {
                            "score": "90",
                            "level": "excellent",
                            "reason": "r",
                            "evidence": [],
                            "citation": "无",
                        },
                    },
                    "total_score": "87.5",
                    "confidence": "0.85",
                    "conflict_detected": False,
                    "summary": "type poison test",
                    "improvement_suggestions": [],
                },
                ensure_ascii=False,
            ),
            # 格式崩坏
            "Internal Server Error",
            # 语义冲突
            json.dumps(
                {
                    "scores": {
                        "accuracy": {
                            "score": 15,
                            "level": "very_poor",
                            "reason": "r",
                            "evidence": [],
                            "citation": "无",
                        },
                        "relevance": {
                            "score": 70,
                            "level": "acceptable",
                            "reason": "r",
                            "evidence": [],
                            "citation": "无",
                        },
                    },
                    "total_score": 38,
                    "confidence": 0.92,
                    "conflict_detected": True,
                    "summary": "semantic conflict",
                    "improvement_suggestions": [],
                },
                ensure_ascii=False,
            ),
            # 客服废话
            json.dumps(
                {
                    "scores": {
                        "accuracy": {
                            "score": 40,
                            "level": "poor",
                            "reason": "r",
                            "evidence": [],
                            "citation": "无",
                        },
                        "relevance": {
                            "score": 30,
                            "level": "very_poor",
                            "reason": "r",
                            "evidence": [],
                            "citation": "无",
                        },
                        "conciseness": {
                            "score": 25,
                            "level": "very_poor",
                            "reason": "r",
                            "evidence": [],
                            "citation": "无",
                        },
                    },
                    "total_score": 45,
                    "confidence": 0.88,
                    "conflict_detected": False,
                    "summary": "fluff",
                    "improvement_suggestions": [],
                },
                ensure_ascii=False,
            ),
        ]

        for idx, payload in enumerate(poison_payloads):
            evaluator.client = _make_mock_client(payload)
            request = EvaluationSchema(
                id=f"meta-summary-{idx}",
                type="llm_as_judge",
                payload={
                    "user_input": "test",
                    "actual_output": "test output",
                },
            )

            # 关键：必须不抛异常
            result = evaluator.evaluate(request)
            assert result is not None, f"毒药 Case {idx} 导致评估器返回 None"
            # 必须有 score 字段
            assert result.score is not None, f"毒药 Case {idx} score 为 None"
            # 强断言：返回的 DomainResponse 字段必须符合 schema
            assert hasattr(result, "is_valid")
            assert hasattr(result, "data")
