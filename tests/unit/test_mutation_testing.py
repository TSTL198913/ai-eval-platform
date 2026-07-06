"""
变异测试 - 验证测试的可靠性

核心思想：故意破坏系统逻辑，验证现有测试能否捕获这些破坏
如果被破坏的系统仍然通过测试，说明测试无效

变异类型：
1. Always-Low 变异：风险评估器总是返回低风险
2. Skip-Security 变异：代码评估器跳过安全检查
3. Ignore-Fallback 变异：忽略降级机制
4. Zero-Score 变异：强制返回零分
5. Random-Status 变异：随机返回评估状态
"""

import random
from unittest.mock import MagicMock, patch

import pytest

from src.domain.evaluators.code import CodeEvaluator
from src.domain.evaluators.risk import RiskEvaluator
from src.domain.evaluators.semantic import SemanticEvaluator
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus


class TestMutationAlwaysLowRisk:
    """变异：风险评估器总是返回低风险"""

    @pytest.mark.xfail(reason="故意注入变异，验证测试能捕获风险评估器被篡改")
    def test_risk_evaluator_always_low_mutation(self):
        """验证测试能捕获风险评估器被篡改的情况"""
        original_get_risk_level = RiskEvaluator._get_risk_level

        def mutated_get_risk_level(self, risk_score, threshold):
            return "low"

        RiskEvaluator._get_risk_level = mutated_get_risk_level

        try:
            evaluator = RiskEvaluator()
            request = EvaluationSchema(
                id="mutation_test_001",
                type="risk",
                payload={
                    "action": "detect_all",
                    "feature_complexity": 0.9,
                    "core_alignment": 0.1,
                    "overall_coverage": 0.1,
                    "test_pass_rate": 0.1,
                },
            )

            result = evaluator.evaluate(request)

            assert result.data["overall_risk_level"] == "high", \
                f"变异测试失败：风险评估器被篡改后应返回 high，但返回了 {result.data['overall_risk_level']}"
        finally:
            RiskEvaluator._get_risk_level = original_get_risk_level


class TestMutationSkipSecurityCheck:
    """变异：代码评估器跳过安全检查"""

    def test_code_evaluator_skip_security_mutation(self):
        """验证测试能捕获代码评估器跳过安全检查的情况"""
        original_validate_code_safety = None

        import src.domain.evaluators.security_rules as security_rules
        original_validate_code_safety = security_rules.validate_code_safety

        def mutated_validate_code_safety(code):
            return True, ""

        security_rules.validate_code_safety = mutated_validate_code_safety

        try:
            evaluator = CodeEvaluator(client=None)
            risky_code = """
def execute_command(cmd):
    return eval(cmd)
"""
            request = EvaluationSchema(
                id="mutation_test_002",
                type="code",
                payload={
                    "code": risky_code,
                    "metadata": {"language": "python"},
                },
            )

            result = evaluator.evaluate(request)

            assert result.metadata.get("safety_valid") is False, \
                f"变异测试失败：使用 eval 的代码应被标记为不安全，但 safety_valid={result.metadata.get('safety_valid')}"
            assert result.score < 0.5, \
                f"变异测试失败：使用 eval 的代码分数应低于 0.5，但分数为 {result.score}"
        finally:
            if original_validate_code_safety is not None:
                security_rules.validate_code_safety = original_validate_code_safety


class TestMutationIgnoreFallback:
    """变异：语义评估器忽略降级机制"""

    def test_semantic_evaluator_ignore_fallback_mutation(self):
        """验证测试能捕获语义评估器忽略降级的情况"""
        original_evaluate = SemanticEvaluator._do_evaluate

        def mutated_do_evaluate(self, request):
            raise RuntimeError("LLM调用失败，未触发降级")

        SemanticEvaluator._do_evaluate = mutated_do_evaluate

        try:
            evaluator = SemanticEvaluator(client=MagicMock())
            request = EvaluationSchema(
                id="mutation_test_003",
                type="semantic",
                payload={
                    "user_input": "测试",
                    "actual_output": "测试",
                    "expected_output": "测试",
                },
            )

            result = evaluator.safe_evaluate(request)

            assert result.evaluation_status in [EvaluatorStatus.PARTIAL, EvaluatorStatus.ERROR], \
                f"变异测试失败：LLM调用失败应触发降级或错误，但返回了 {result.evaluation_status}"
        finally:
            SemanticEvaluator._do_evaluate = original_evaluate


class TestMutationZeroScore:
    """变异：强制返回零分"""

    def test_zero_score_mutation_detection(self):
        """验证测试能捕获被强制返回零分的情况"""
        original_create_success_response = None

        import src.domain.evaluators.base as base_module
        original_create_success_response = base_module.BaseEvaluator.create_success_response

        def mutated_create_success_response(self, **kwargs):
            kwargs["score"] = 0.0
            return original_create_success_response(self, **kwargs)

        base_module.BaseEvaluator.create_success_response = mutated_create_success_response

        try:
            evaluator = CodeEvaluator(client=None)
            good_code = """
def add(a, b):
    return a + b
"""
            request = EvaluationSchema(
                id="mutation_test_004",
                type="code",
                payload={
                    "code": good_code,
                    "metadata": {"language": "python"},
                },
            )

            result = evaluator.evaluate(request)

            assert result.score > 0.5, \
                f"变异测试失败：优质代码分数应高于 0.5，但分数为 {result.score}"
        finally:
            if original_create_success_response is not None:
                base_module.BaseEvaluator.create_success_response = original_create_success_response


class TestMutationRandomStatus:
    """变异：随机返回评估状态"""

    @pytest.mark.xfail(reason="故意注入变异，验证测试能捕获随机状态变异")
    def test_random_status_mutation_detection(self):
        """验证测试能捕获随机状态变异的情况"""
        original_evaluate = RiskEvaluator._do_evaluate

        def mutated_do_evaluate(self, request):
            result = original_evaluate(self, request)
            result = result.model_copy(update={
                "evaluation_status": random.choice([
                    EvaluatorStatus.SUCCESS,
                    EvaluatorStatus.PARTIAL,
                    EvaluatorStatus.CANNOT_EVALUATE,
                    EvaluatorStatus.ERROR,
                ])
            })
            return result

        RiskEvaluator._do_evaluate = mutated_do_evaluate

        try:
            evaluator = RiskEvaluator()
            request = EvaluationSchema(
                id="mutation_test_005",
                type="risk",
                payload={
                    "action": "detect_all",
                },
            )

            result = evaluator.evaluate(request)

            assert result.evaluation_status == EvaluatorStatus.SUCCESS, \
                f"变异测试失败：正常评估应返回 SUCCESS，但返回了 {result.evaluation_status}"
        finally:
            RiskEvaluator._do_evaluate = original_evaluate


class TestMutationDataCorruption:
    """变异：数据损坏"""

    def test_data_corruption_mutation_detection(self):
        """验证测试能捕获数据损坏变异的情况"""
        original_get_payload_data = None

        import src.domain.evaluators.base as base_module
        original_get_payload_data = base_module.BaseEvaluator.get_payload_data

        def mutated_get_payload_data(self, request, key, default=None):
            value = original_get_payload_data(self, request, key, default)
            if isinstance(value, float):
                return float("nan")
            return value

        base_module.BaseEvaluator.get_payload_data = mutated_get_payload_data

        try:
            evaluator = RiskEvaluator()
            request = EvaluationSchema(
                id="mutation_test_006",
                type="risk",
                payload={
                    "action": "detect_all",
                    "feature_complexity": 0.5,
                    "core_alignment": 0.5,
                },
            )

            result = evaluator.evaluate(request)

            assert result.is_valid is True, \
                f"变异测试失败：数据损坏后系统应保持有效，但 is_valid={result.is_valid}"
            assert result.score is not None and not (isinstance(result.score, float) and result.score != result.score), \
                f"变异测试失败：分数不应为 NaN，但分数为 {result.score}"
        finally:
            if original_get_payload_data is not None:
                base_module.BaseEvaluator.get_payload_data = original_get_payload_data


class TestMutationDenialOfService:
    """变异：拒绝服务攻击模拟"""

    def test_dos_mutation_detection(self):
        """验证测试能捕获拒绝服务变异的情况"""
        original_evaluate = RiskEvaluator._do_evaluate

        import time

        def mutated_do_evaluate(self, request):
            time.sleep(10)
            return original_evaluate(self, request)

        RiskEvaluator._do_evaluate = mutated_do_evaluate

        try:
            evaluator = RiskEvaluator()
            request = EvaluationSchema(
                id="mutation_test_007",
                type="risk",
                payload={
                    "action": "detect_all",
                },
            )

            import signal

            class TimeoutException(Exception):
                pass

            def timeout_handler(signum, frame):
                raise TimeoutException("评估超时")

            if hasattr(signal, 'SIGALRM'):
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(5)

                try:
                    result = evaluator.evaluate(request)
                    assert False, "变异测试失败：评估应在5秒内完成"
                except TimeoutException:
                    assert True, "变异测试成功：检测到评估超时"
                finally:
                    if hasattr(signal, 'SIGALRM'):
                        signal.alarm(0)
            else:
                pytest.skip("当前平台不支持 SIGALRM")
        finally:
            RiskEvaluator._do_evaluate = original_evaluate