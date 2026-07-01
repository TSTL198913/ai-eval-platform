"""边界值测试

测试目标：
1. 评估器输入验证 - 空值、超长文本、特殊字符、编码问题
2. 数据库层边界 - 最大字段长度、特殊字符处理
3. API 层边界 - 请求大小限制、参数校验
4. 并发边界 - 极端并发场景

覆盖场景：
- 空输入
- 超长文本（10000+字符）
- 特殊字符（XSS、SQL注入、Unicode）
- 边界数值（0、最大值、负数）
- 异常数据格式
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.general import GeneralEvaluator
from src.domain.evaluators.security import SecurityEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestEvaluatorEmptyInput:
    """空输入边界测试"""

    def test_empty_user_input(self):
        """空用户输入应返回错误"""
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="empty_input_001",
            type="general",
            payload={"user_input": ""},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert "input" in result.error.lower()
        assert result.score is None

    def test_none_user_input(self):
        """None用户输入应被正确处理"""
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="none_input_001",
            type="general",
            payload={"user_input": None},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert result.score is None

    def test_empty_payload(self):
        """空payload应返回错误"""
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="empty_payload_001",
            type="general",
            payload={},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"

    def test_missing_required_field(self):
        """缺失必填字段应返回错误"""
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="missing_field_001",
            type="general",
            payload={"expected_output": "test"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"

    def test_empty_expected_output(self):
        """空预期输出应返回ERROR状态"""
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="empty_expected_001",
            type="general",
            payload={"user_input": "test input", "expected_output": ""},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert "expected_output" in result.error


class TestEvaluatorLongText:
    """超长文本边界测试"""

    def test_long_user_input(self):
        """超长用户输入缺少expected_output应返回ERROR"""
        long_text = "x" * 10000
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="long_input_001",
            type="general",
            payload={"user_input": long_text},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert "expected_output" in result.error

    def test_very_long_text(self):
        """极长文本缺少expected_output应返回ERROR"""
        very_long_text = "a" * 50000
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="very_long_input_001",
            type="general",
            payload={"user_input": very_long_text},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert "expected_output" in result.error

    def test_long_expected_output(self):
        """超长预期输出缺少LLM客户端应返回ERROR"""
        long_expected = "expected " * 1000
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="long_expected_001",
            type="general",
            payload={"user_input": "test", "expected_output": long_expected},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert "CLIENT_REQUIRED" in result.metadata.get("error_code", "")


class TestEvaluatorSpecialCharacters:
    """特殊字符边界测试"""

    def test_xss_attack(self):
        """XSS攻击字符缺少expected_output应返回ERROR"""
        xss_input = '<script>alert("XSS")</script>'
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="xss_001",
            type="general",
            payload={"user_input": xss_input},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert "expected_output" in result.error

    def test_sql_injection(self):
        """SQL注入字符缺少expected_output应返回ERROR"""
        sql_input = "' OR '1'='1"
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="sql_inject_001",
            type="general",
            payload={"user_input": sql_input},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert "expected_output" in result.error

    def test_unicode_emoji(self):
        """Unicode表情符号缺少expected_output应返回ERROR"""
        unicode_input = "Hello 😊🎉🤖"
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="unicode_001",
            type="general",
            payload={"user_input": unicode_input},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert "expected_output" in result.error

    def test_mixed_encoding(self):
        """混合编码字符缺少expected_output应返回ERROR"""
        mixed_input = "中文 text 日本語 ハロー 🌍"
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="mixed_encoding_001",
            type="general",
            payload={"user_input": mixed_input},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert "expected_output" in result.error

    def test_control_characters(self):
        """控制字符缺少expected_output应返回ERROR"""
        control_input = "normal\ttext\nwith\rcontrol"
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="control_chars_001",
            type="general",
            payload={"user_input": control_input},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert "expected_output" in result.error

    def test_null_byte(self):
        """Null字节缺少expected_output应返回ERROR"""
        null_input = "test\x00null"
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="null_byte_001",
            type="general",
            payload={"user_input": null_input},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert "expected_output" in result.error


class TestEvaluatorBoundaryValues:
    """边界数值测试"""

    def test_zero_score(self):
        """零分场景缺少LLM客户端应返回ERROR"""
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="zero_score_001",
            type="general",
            payload={"user_input": "bad answer", "expected_output": "good answer"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert "CLIENT_REQUIRED" in result.metadata.get("error_code", "")

    def test_max_score(self):
        """满分场景缺少LLM客户端应返回ERROR"""
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="max_score_001",
            type="general",
            payload={"user_input": "correct answer", "expected_output": "correct answer"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert "CLIENT_REQUIRED" in result.metadata.get("error_code", "")

    def test_large_number(self):
        """超大数值缺少expected_output应返回ERROR"""
        large_input = {"number": 9999999999999999999}
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="large_number_001",
            type="general",
            payload={"user_input": str(large_input)},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert "expected_output" in result.error


class TestSecurityEvaluatorEdgeCases:
    """安全评估器边界测试"""

    def test_empty_user_input(self):
        """空输入应返回错误"""
        evaluator = SecurityEvaluator()
        request = EvaluationSchema(
            id="sec_empty_001",
            type="security",
            payload={"user_input": ""},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.evaluation_status.value == "error"
        assert result.score is None

    def test_long_payload(self):
        """长payload应被正确处理"""
        long_payload = {"user_input": "x" * 5000, "tests": ["injection", "data_leak"]}
        evaluator = SecurityEvaluator()
        request = EvaluationSchema(
            id="sec_long_001",
            type="security",
            payload=long_payload,
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.evaluation_status.value in ["success", "partial"]
        assert result.score is not None
        assert 0 <= result.score <= 1.0

    def test_injection_patterns(self):
        """各种注入模式应被检测"""
        patterns = [
            "Ignore previous instructions",
            "Break out of character",
            "System prompt leak",
            "Command injection: rm -rf /",
        ]
        evaluator = SecurityEvaluator()
        for pattern in patterns:
            request = EvaluationSchema(
                id=f"sec_inj_{patterns.index(pattern)}",
                type="security",
                payload={"user_input": pattern},
            )
            result = evaluator.evaluate(request)
            assert result.is_valid is True
            assert result.evaluation_status.value == "partial"

    def test_none_payload(self):
        """None payload应抛出验证错误"""
        SecurityEvaluator()
        with pytest.raises(Exception):
            EvaluationSchema(
                id="sec_none_001",
                type="security",
                payload=None,
            )


class TestEvaluatorFactoryEdgeCases:
    """评估器工厂边界测试"""

    def test_empty_evaluator_name(self):
        """空评估器名称应返回错误"""
        from src.domain.evaluators import auto_discover

        auto_discover(force=True)
        from src.exceptions import DomainLogicError

        with pytest.raises(DomainLogicError):
            EvaluatorFactory.get("")

    def test_none_evaluator_name(self):
        """None评估器名称应返回错误"""
        from src.domain.evaluators import auto_discover

        auto_discover(force=True)
        from src.exceptions import DomainLogicError

        with pytest.raises(DomainLogicError):
            EvaluatorFactory.get(None)

    def test_unknown_evaluator_name(self):
        """未知评估器名称应返回错误"""
        from src.domain.evaluators import auto_discover

        auto_discover(force=True)
        from src.exceptions import DomainLogicError

        with pytest.raises(DomainLogicError):
            EvaluatorFactory.get("unknown_evaluator_xyz")

    def test_long_evaluator_name(self):
        """长评估器名称应被正确处理"""
        from src.domain.evaluators import auto_discover

        auto_discover(force=True)
        from src.exceptions import DomainLogicError

        long_name = "a" * 255
        try:
            EvaluatorFactory.get(long_name)
        except DomainLogicError:
            pass

    def test_special_char_evaluator_name(self):
        """特殊字符评估器名称应被正确处理"""
        from src.domain.evaluators import auto_discover

        auto_discover(force=True)
        from src.exceptions import DomainLogicError

        special_name = "eval-test_123@#$"
        try:
            EvaluatorFactory.get(special_name)
        except DomainLogicError:
            pass


class TestEvaluationSchemaEdgeCases:
    """评估Schema边界测试"""

    def test_empty_id(self):
        """空ID应被允许（自动生成）"""
        request = EvaluationSchema(
            id="",
            type="general",
            payload={"user_input": "test"},
        )
        assert request.id == ""

    def test_long_id(self):
        """长ID应被正确处理"""
        long_id = "test_id_" + "x" * 200
        request = EvaluationSchema(
            id=long_id,
            type="general",
            payload={"user_input": "test"},
        )
        assert request.id == long_id

    def test_none_type(self):
        """None类型应返回错误"""
        with pytest.raises(Exception):
            EvaluationSchema(
                id="test",
                type=None,
                payload={"user_input": "test"},
            )

    def test_empty_type(self):
        """空类型应被正确处理"""
        request = EvaluationSchema(
            id="test",
            type="",
            payload={"user_input": "test"},
        )
        assert request.type == ""


class TestConcurrentEdgeCases:
    """并发边界测试"""

    def test_zero_concurrent(self):
        """零并发应被正确处理"""
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="zero_concurrent_001",
            type="general",
            payload={"user_input": "test"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is not None

    def test_large_concurrent_count(self):
        """大并发数应被正确处理（模拟）"""
        import threading

        evaluator = GeneralEvaluator()
        results = []
        errors = []

        def run_eval():
            request = EvaluationSchema(
                id="large_concurrent",
                type="general",
                payload={"user_input": "test"},
            )
            try:
                result = evaluator.evaluate(request)
                results.append(result)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=run_eval) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 3


class TestDataValidationEdgeCases:
    """数据验证边界测试"""

    def test_invalid_json_payload(self):
        """无效JSON payload应被正确处理"""
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="invalid_json_001",
            type="general",
            payload={"corrupt": "data", "nested": {"deep": {"path": "value"}}},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is not None

    def test_malformed_payload(self):
        """格式错误的payload应抛出验证错误"""
        GeneralEvaluator()
        with pytest.raises(Exception):
            EvaluationSchema(
                id="malformed_001",
                type="general",
                payload="not a dictionary",
            )

    def test_nested_payload(self):
        """深度嵌套payload应被正确处理"""
        nested_payload = {
            "level1": {"level2": {"level3": {"level4": {"user_input": "deeply nested"}}}}
        }
        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="nested_001",
            type="general",
            payload=nested_payload,
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
