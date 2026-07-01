"""
破坏性和真实用户测试
目标：模拟极端场景和真实用户行为，验证系统的健壮性

测试场景分类：
1. 恶意输入攻击：SQL注入、XSS、超长文本、特殊字符
2. 边界条件：空输入、极端值、超大数组、嵌套结构
3. 并发竞争：多用户同时提交、资源争用、重复请求
4. 真实用户场景：QA问答、代码审查、风险评估、语义匹配
5. 异常输入组合：缺失字段、类型错误、格式错误
6. 性能压力：高频请求、大数据量、长时间运行
"""

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.domain.evaluators.code import CodeEvaluator
from src.domain.evaluators.risk import RiskEvaluator
from src.domain.evaluators.semantic import SemanticEvaluator
from src.engine import EvaluationEngine
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus


class TestMaliciousInputAttack:
    """恶意输入攻击测试"""

    def test_sql_injection_attempt(self):
        """验证系统能抵御 SQL 注入攻击"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "代码使用了不安全的字符串格式化方式，存在 SQL 注入风险"
        evaluator = CodeEvaluator(client=mock_client)
        malicious_code = """
def get_user(id):
    query = "SELECT * FROM users WHERE id = '{}'".format(id)
    return execute(query)
# SQL注入: id = ' OR '1'='1
"""
        request = EvaluationSchema(
            id="malicious_sql_001",
            type="code",
            payload={
                "code": malicious_code,
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["syntax_valid"] is True
        mock_client.chat.assert_called_once()

    def test_xss_attempt_in_code(self):
        """验证代码评估器能处理 XSS 攻击代码"""
        evaluator = CodeEvaluator(client=None)
        xss_code = """
def render(user_input):
    return "<script>alert('XSS')</script>" + user_input
"""
        request = EvaluationSchema(
            id="malicious_xss_001",
            type="code",
            payload={
                "code": xss_code,
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["syntax_valid"] is True

    def test_extremely_long_text_input(self):
        """验证系统能处理超长文本输入（拒绝服务攻击尝试）"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.5"
        evaluator = SemanticEvaluator(client=mock_client)

        long_text = "A" * 100000
        request = EvaluationSchema(
            id="long_text_001",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "actual_output": long_text,
                "expected_output": long_text,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.evaluation_status == EvaluatorStatus.SUCCESS

    def test_special_characters_bomb(self):
        """验证系统能处理特殊字符炸弹"""
        evaluator = CodeEvaluator(client=None)
        safe_chars = "!@#$%^&*()_+-=[]{}|;:.<>?"
        request = EvaluationSchema(
            id="special_chars_001",
            type="code",
            payload={
                "code": f'def test():\n    return "{safe_chars}"',
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["syntax_valid"] is True

    def test_unicode_bomb(self):
        """验证系统能处理 Unicode 炸弹"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"
        evaluator = SemanticEvaluator(client=mock_client)

        unicode_bomb = "".join(["\u200b" * 1000, "正常文本", "\u200b" * 1000])
        request = EvaluationSchema(
            id="unicode_bomb_001",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "actual_output": unicode_bomb,
                "expected_output": "正常文本",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None


class TestBoundaryConditions:
    """边界条件测试"""

    def test_empty_payload(self):
        """验证空 payload 的处理"""
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id="empty_payload_001",
            type="risk",
            payload={},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.evaluation_status == EvaluatorStatus.SUCCESS

    def test_all_none_values(self):
        """验证全 None 值的处理"""
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id="all_none_001",
            type="risk",
            payload={
                "action": "detect_all",
                "feature_complexity": None,
                "core_alignment": None,
                "overall_coverage": None,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None

    def test_zero_values_everywhere(self):
        """验证全零值的处理"""
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id="zero_values_001",
            type="risk",
            payload={
                "action": "detect_all",
                "feature_complexity": 0.0,
                "core_alignment": 0.0,
                "overall_coverage": 0.0,
                "test_pass_rate": 0.0,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["overall_risk_level"] == "high"

    def test_maximum_float_values(self):
        """验证最大浮点值的处理"""
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id="max_float_001",
            type="risk",
            payload={
                "action": "feature_creep",
                "feature_complexity": float("inf"),
                "core_alignment": float("inf"),
                "responsibility_blur": float("inf"),
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.0

    def test_negative_values(self):
        """验证负数输入的处理"""
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id="negative_values_001",
            type="risk",
            payload={
                "action": "test_coverage",
                "overall_coverage": -100.0,
                "new_code_coverage": -0.5,
                "critical_path_coverage": -0.1,
                "test_pass_rate": -1.0,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert 0.0 <= result.score <= 1.0


class TestConcurrencyAndRaceConditions:
    """并发竞争测试"""

    def test_concurrent_semantic_evaluations(self):
        """验证语义评估器的并发安全"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.85"
        evaluator = SemanticEvaluator(client=mock_client)

        results = []
        lock = threading.Lock()

        def worker(idx):
            request = EvaluationSchema(
                id=f"concurrent_sem_{idx:03d}",
                type="semantic",
                payload={
                    "user_input": f"问题 {idx}",
                    "actual_output": f"回答 {idx}",
                    "expected_output": f"预期 {idx}",
                },
            )
            result = evaluator.evaluate(request)
            with lock:
                results.append(result)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 50
        for result in results:
            assert result.is_valid is True
            assert result.score == pytest.approx(0.85, abs=0.01)

    def test_concurrent_code_evaluations(self):
        """验证代码评估器的并发安全"""
        evaluator = CodeEvaluator(client=None)

        results = []
        lock = threading.Lock()

        def worker(idx):
            request = EvaluationSchema(
                id=f"concurrent_code_{idx:03d}",
                type="code",
                payload={
                    "code": f"def func_{idx}(x):\n    return x + {idx}",
                    "metadata": {"language": "python"},
                },
            )
            result = evaluator.evaluate(request)
            with lock:
                results.append(result)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 50
        for result in results:
            assert result.is_valid is True
            assert result.data["syntax_valid"] is True

    def test_concurrent_risk_evaluations(self):
        """验证风险评估器的并发安全"""
        evaluator = RiskEvaluator()

        results = []
        lock = threading.Lock()

        def worker(idx):
            request = EvaluationSchema(
                id=f"concurrent_risk_{idx:03d}",
                type="risk",
                payload={
                    "action": "detect_all",
                    "feature_complexity": idx / 100,
                    "core_alignment": 1.0 - idx / 100,
                },
            )
            result = evaluator.evaluate(request)
            with lock:
                results.append(result)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 50
        for result in results:
            assert result.is_valid is True

    def test_repeated_requests_same_id(self):
        """验证重复请求相同 ID 的处理（幂等性）"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.9"
        mock_client.config = MagicMock()
        mock_client.config.model_name = "test-model"
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="repeated_request_001",
            type="semantic",
            payload={
                "user_input": "重复请求测试",
                "actual_output": "实际回答",
                "expected_output": "预期回答",
            },
        )

        results = []
        for _ in range(10):
            result = engine.run(request)
            results.append(result)

        assert len(results) == 10
        for result in results:
            assert result.response is not None
            assert result.response.is_valid is True
            assert result.case_id == "repeated_request_001"


class TestRealUserScenarios:
    """真实用户场景测试"""

    def test_qa_scenario_correct_answer(self):
        """QA场景：正确答案"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "1.0"
        evaluator = SemanticEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="real_user_qa_001",
            type="semantic",
            payload={
                "user_input": "中国的首都是哪里？",
                "actual_output": "北京",
                "expected_output": "北京",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_qa_scenario_wrong_answer(self):
        """QA场景：错误答案"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.1"
        evaluator = SemanticEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="real_user_qa_002",
            type="semantic",
            payload={
                "user_input": "中国的首都是哪里？",
                "actual_output": "上海",
                "expected_output": "北京",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.1

    def test_code_review_scenario(self):
        """代码审查场景：真实代码质量问题"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "代码存在安全风险：使用了eval函数"
        evaluator = CodeEvaluator(client=mock_client)

        risky_code = """
def execute_command(cmd):
    return eval(cmd)
"""
        request = EvaluationSchema(
            id="real_user_code_001",
            type="code",
            payload={
                "code": risky_code,
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["syntax_valid"] is True
        mock_client.chat.assert_called_once()

    def test_risk_assessment_scenario(self):
        """风险评估场景：真实项目风险"""
        evaluator = RiskEvaluator()

        request = EvaluationSchema(
            id="real_user_risk_001",
            type="risk",
            payload={
                "action": "detect_all",
                "feature_complexity": 0.7,
                "core_alignment": 0.6,
                "responsibility_blur": 0.5,
                "unresolved_warnings": 45,
                "duplicate_code_ratio": 0.3,
                "pending_refactoring": 8,
                "overall_coverage": 0.65,
                "new_code_coverage": 0.55,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["overall_risk_level"] in ["low", "medium", "high"]
        assert len(result.data["high_risks"]) > 0 or len(result.data["medium_risks"]) > 0

    def test_semantic_matching_scenario(self):
        """语义匹配场景：近义词识别"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.85"
        evaluator = SemanticEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="real_user_semantic_001",
            type="semantic",
            payload={
                "user_input": "如何提高工作效率？",
                "actual_output": "通过合理规划时间、减少干扰来提升工作效率",
                "expected_output": "提高工作效率的方法包括时间管理和减少干扰",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == pytest.approx(0.85, abs=0.01)

    def test_code_execution_with_test_cases(self):
        """代码执行场景：带测试用例"""
        evaluator = CodeEvaluator(client=None)

        request = EvaluationSchema(
            id="real_user_exec_001",
            type="code",
            payload={
                "code": """
def add(a, b):
    return a + b
""",
                "test_cases": [
                    {"input": [1, 2], "expected": 3},
                    {"input": [5, 5], "expected": 10},
                    {"input": [-1, 1], "expected": 0},
                ],
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["syntax_valid"] is True


class TestInvalidInputCombinations:
    """异常输入组合测试"""

    def test_missing_required_fields(self):
        """验证缺少必需字段的处理"""
        evaluator = SemanticEvaluator(client=MagicMock())

        request = EvaluationSchema(
            id="missing_fields_001",
            type="semantic",
            payload={},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False

    def test_wrong_field_types(self):
        """验证字段类型错误的处理"""
        evaluator = RiskEvaluator()

        request = EvaluationSchema(
            id="wrong_types_001",
            type="risk",
            payload={
                "action": "feature_creep",
                "feature_complexity": "not_a_number",
                "core_alignment": ["list", "instead", "of", "float"],
                "responsibility_blur": {"dict": "instead", "of": "float"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None

    def test_malformed_json_payload(self):
        """验证格式错误JSON的处理"""
        evaluator = RiskEvaluator()

        request = EvaluationSchema(
            id="malformed_json_001",
            type="risk",
            payload={
                "action": "detect_all",
                "data": "{invalid json",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_nested_structure_too_deep(self):
        """验证过深嵌套结构的处理"""
        deep_nested = {"level": 1}
        current = deep_nested
        for i in range(2, 100):
            current["nested"] = {"level": i}
            current = current["nested"]

        evaluator = RiskEvaluator()

        request = EvaluationSchema(
            id="deep_nested_001",
            type="risk",
            payload={
                "action": "detect_all",
                "deep_data": deep_nested,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_empty_string_values(self):
        """验证空字符串值的处理"""
        evaluator = SemanticEvaluator(client=MagicMock())

        request = EvaluationSchema(
            id="empty_strings_001",
            type="semantic",
            payload={
                "user_input": "",
                "actual_output": "",
                "expected_output": "",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False


class TestPerformanceStress:
    """性能压力测试"""

    def test_high_frequency_requests(self):
        """验证高频请求下的系统稳定性"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"
        mock_client.config = MagicMock()
        mock_client.config.model_name = "perf-test-model"
        engine = EvaluationEngine(client=mock_client)

        start = time.perf_counter()
        for i in range(50):
            request = EvaluationSchema(
                id=f"perf_{i:03d}",
                type="semantic",
                payload={
                    "user_input": f"问题 {i}",
                    "actual_output": f"回答 {i}",
                    "expected_output": f"预期 {i}",
                },
            )
            engine.run(request)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 50) * 1000
        assert avg_ms < 200, f"性能不达标: {avg_ms}ms/次"

    def test_large_payload_processing(self):
        """验证大 payload 的处理"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"
        evaluator = SemanticEvaluator(client=mock_client)

        large_text = "测试文本" * 5000
        request = EvaluationSchema(
            id="large_payload_001",
            type="semantic",
            payload={
                "user_input": large_text,
                "actual_output": large_text,
                "expected_output": large_text,
            },
        )

        start = time.perf_counter()
        result = evaluator.evaluate(request)
        elapsed = time.perf_counter() - start

        assert result.is_valid is True
        assert elapsed < 5.0, f"处理时间过长: {elapsed}s"

    def test_mixed_evaluator_types_performance(self):
        """验证混合评估器类型的性能"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"

        evaluators = [
            SemanticEvaluator(client=mock_client),
            CodeEvaluator(client=mock_client),
            RiskEvaluator(),
        ]

        start = time.perf_counter()
        for i in range(30):
            evaluator = evaluators[i % 3]
            if isinstance(evaluator, SemanticEvaluator):
                request = EvaluationSchema(
                    id=f"mixed_{i:03d}",
                    type="semantic",
                    payload={
                        "user_input": f"语义问题 {i}",
                        "actual_output": f"语义回答 {i}",
                        "expected_output": f"语义预期 {i}",
                    },
                )
            elif isinstance(evaluator, CodeEvaluator):
                request = EvaluationSchema(
                    id=f"mixed_{i:03d}",
                    type="code",
                    payload={
                        "code": f"def func_{i}(x):\n    return x * {i}",
                        "metadata": {"language": "python"},
                    },
                )
            else:
                request = EvaluationSchema(
                    id=f"mixed_{i:03d}",
                    type="risk",
                    payload={"action": "detect_all"},
                )
            evaluator.evaluate(request)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 30) * 1000
        assert avg_ms < 200, f"性能不达标: {avg_ms}ms/次"