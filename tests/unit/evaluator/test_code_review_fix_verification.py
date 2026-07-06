"""CodeReviewEvaluator 评分算法回归测试

覆盖三个修复点：
1. high 漏洞纳入权重调整（has_critical_or_high）
2. 重复触发线性惩罚封顶3倍（替代 math.log 无上限）
3. critical/high 存在时安全权重提升至 0.7/0.3
"""
import math

from src.domain.evaluators.security_rules import detect_security_vulnerabilities


def test_single_high_trigger_penalty_equals_base():
    """边界：单次 high 触发 -> penalty=base，与旧 log 公式一致"""
    # el.innerHTML = request.x 仅匹配 1 个 xss 模式
    code = "el.innerHTML = request.x"
    result = detect_security_vulnerabilities(code)
    # base=0.20, count=1 -> penalty=min(0.20*1, 0.20*3)=0.20 -> score=0.80
    assert result["score"] == 0.80, f"单次触发应为0.80，实际{result['score']}"
    assert result["summary"]["high"] >= 1


def test_repeated_high_trigger_capped_at_3x():
    """边界：同一 high 规则重复触发 10 次 -> 封顶3倍，避免 log 过度惩罚"""
    code = "\n".join([f"el.innerHTML = request.x{i}" for i in range(10)])
    result = detect_security_vulnerabilities(code)
    # 新公式: penalty=min(0.20*10, 0.20*3)=0.60 -> score=0.40
    # 旧 log 公式: penalty=0.20*(1+ln10)=0.66 -> score=0.34 (过度惩罚)
    assert result["score"] == 0.40, f"封顶3倍应为0.40，实际{result['score']}"
    old_score = round(max(0.0, 1.0 - 0.20 * (1 + math.log(10))), 4)
    assert result["score"] > old_score, f"新公式应比旧log更宽松: 新{result['score']} 旧{old_score}"


def test_single_critical_trigger():
    """正向：单次 critical 触发 -> penalty=base=0.35 -> score=0.65"""
    code = "os.system(request.x)"
    result = detect_security_vulnerabilities(code)
    assert result["score"] == 0.65, f"单次critical应为0.65，实际{result['score']}"
    assert result["summary"]["critical"] >= 1


def test_code_review_weights_high_vulnerability():
    """正向：纯 high 漏洞代码 -> 安全权重应提升"""
    from unittest.mock import MagicMock
    from src.domain.evaluators.code_review import CodeReviewEvaluator
    from src.schemas.evaluation import DomainResponse, EvaluationSchema

    mock_client = MagicMock()
    mock_client.config = MagicMock()
    mock_client.config.model_name = "gpt-4"

    target = CodeReviewEvaluator(client=mock_client)
    mock_delegate = MagicMock()
    # 质量分给高分 0.9，验证安全权重提升后不被稀释
    mock_delegate._do_evaluate.return_value = DomainResponse(text="ok", score=0.9, data={})
    target._delegate = mock_delegate

    # 纯 high 漏洞代码（XSS，仅匹配1个模式）
    request = EvaluationSchema(
        id="verify_high_001",
        type="code_review",
        payload={"code": "el.innerHTML = request.x", "expected_output": "x"},
    )
    result = target.evaluate(request)
    weights = result.data["weights_applied"]
    assert weights["security"] >= 0.5, f"high漏洞安全权重应>=0.5，实际{weights['security']}"
    assert weights["quality"] <= 0.5, f"high漏洞质量权重应<=0.5，实际{weights['quality']}"


def test_code_review_weights_medium_only_not_adjusted():
    """负向：仅 medium 漏洞 -> 使用默认权重"""
    from unittest.mock import MagicMock
    from src.domain.evaluators.code_review import CodeReviewEvaluator
    from src.schemas.evaluation import DomainResponse, EvaluationSchema

    mock_client = MagicMock()
    mock_client.config = MagicMock()
    mock_client.config.model_name = "gpt-4"

    target = CodeReviewEvaluator(client=mock_client)
    mock_delegate = MagicMock()
    mock_delegate._do_evaluate.return_value = DomainResponse(text="ok", score=0.9, data={})
    target._delegate = mock_delegate

    # 仅 medium 漏洞：硬编码密钥（medium 严重度）
    request = EvaluationSchema(
        id="verify_medium_001",
        type="code_review",
        payload={"code": 'password = "hardcoded_secret_value"', "expected_output": "x"},
    )
    result = target.evaluate(request)
    weights = result.data["weights_applied"]
    # 默认权重范围在0.4-0.6之间
    assert 0.4 <= weights["security"] <= 0.6, f"仅medium安全权重应在0.4-0.6之间，实际{weights['security']}"
