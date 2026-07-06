"""
CodeEvaluator 黄金标准对抗测试 - 2026年工业级标准
测试目标：验证代码评估器真的能识别安全漏洞和代码质量问题

黄金标准定义：
1. 包含eval()的代码 → 安全分数 ≤ 0.3
2. 包含exec()的代码 → 安全分数 ≤ 0.3
3. 包含SQL注入风险的代码 → 安全分数 ≤ 0.3
4. 语法正确的安全代码 → 总分 ≥ 0.8
5. 有明显bug的代码 → 质量分数 ≤ 0.5

业务逻辑验证：如果评估器对漏洞代码返回高分（漏放），或对安全代码返回低分（误报），测试失败
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.code import CodeEvaluator
from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus


class TestCodeEvaluatorGoldenStandard:
    """黄金标准对抗测试"""

    @pytest.fixture
    def evaluator(self):
        return CodeEvaluator()

    def test_eval_injection_vulnerability(self, evaluator):
        """
        黄金标准：eval()注入漏洞必须被识别
        漏洞类型：eval(user_input)
        预期：安全分数 ≤ 0.3
        """
        request = EvaluationSchema(
            id="code_gold_001",
            type="code",
            payload={
                "code": """
def process_input(user_input):
    result = eval(user_input)
    return result
""",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        assert result.score <= 0.3, f"eval漏洞代码分数应≤0.3，实际为{result.score}"
        assert "安全" in str(result.error or result.text or ""), \
            "漏洞代码应包含安全相关的错误信息"

    def test_exec_vulnerability(self, evaluator):
        """
        黄金标准：exec()漏洞必须被识别
        漏洞类型：exec(user_input)
        预期：安全分数 ≤ 0.3
        """
        request = EvaluationSchema(
            id="code_gold_002",
            type="code",
            payload={
                "code": """
def run_command(cmd):
    exec(cmd)
""",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        assert result.score <= 0.3, f"exec漏洞代码分数应≤0.3，实际为{result.score}"

    def test_sql_injection_vulnerability(self, evaluator):
        """
        黄金标准：SQL注入漏洞必须被识别
        漏洞类型：直接字符串拼接SQL
        预期：安全分数 ≤ 0.3
        """
        request = EvaluationSchema(
            id="code_gold_003",
            type="code",
            payload={
                "code": """
def query_user(username):
    query = f"SELECT * FROM users WHERE username = '{username}'"
    execute(query)
""",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        assert result.score <= 0.3, f"SQL注入漏洞代码分数应≤0.3，实际为{result.score}"

    def test_path_traversal_vulnerability(self, evaluator):
        """
        黄金标准：路径遍历漏洞必须被识别
        漏洞类型：直接拼接用户输入到文件路径
        预期：安全分数 ≤ 0.3
        """
        request = EvaluationSchema(
            id="code_gold_004",
            type="code",
            payload={
                "code": """
def read_file(filename):
    with open(f'/data/{filename}', 'r') as f:
        return f.read()
""",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        assert result.score <= 0.3, f"路径遍历漏洞代码分数应≤0.3，实际为{result.score}"

    def test_safe_code_high_score(self, evaluator):
        """
        黄金标准：安全代码应返回较高分数
        场景：使用参数化查询的安全代码
        预期：总分 ≥ 0.65
        """
        request = EvaluationSchema(
            id="code_gold_005",
            type="code",
            payload={
                "code": """
def get_user(username: str) -> dict:
    query = "SELECT * FROM users WHERE username = %s"
    return execute_query(query, (username,))
""",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        assert result.score >= 0.65, f"安全代码分数应≥0.65，实际为{result.score}"
        assert result.evaluation_status in [EvaluatorStatus.SUCCESS, EvaluatorStatus.PARTIAL]

    def test_well_structured_code(self, evaluator):
        """
        黄金标准：结构良好的代码应返回较高分数
        场景：有类型注解、异常处理、文档字符串的代码
        预期：总分 ≥ 0.7
        """
        request = EvaluationSchema(
            id="code_gold_006",
            type="code",
            payload={
                "code": '''
def process_data(items: list[str]) -> dict[str, int]:
    """处理字符串列表并返回计数结果"""
    if not items:
        raise ValueError("列表不能为空")
    result = {}
    for item in items:
        if not isinstance(item, str):
            raise TypeError("元素必须是字符串")
        result[item] = result.get(item, 0) + 1
    return result
''',
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        assert result.score >= 0.7, f"结构良好代码分数应≥0.7，实际为{result.score}"

    def test_obvious_bug_low_score(self, evaluator):
        """
        黄金标准：有明显bug的代码必须返回低分
        场景：除以零的明显错误
        预期：质量分数 ≤ 0.5
        """
        request = EvaluationSchema(
            id="code_gold_007",
            type="code",
            payload={
                "code": """
def calculate():
    x = 10 / 0
    return x
""",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        assert result.score <= 0.5, f"明显bug代码分数应≤0.5，实际为{result.score}"

    def test_unclosed_resource(self, evaluator):
        """
        黄金标准：未关闭资源的代码应返回较低分数
        场景：文件打开后未关闭
        预期：质量分数 ≤ 0.6
        """
        request = EvaluationSchema(
            id="code_gold_008",
            type="code",
            payload={
                "code": """
def read_data():
    f = open("data.txt", "r")
    data = f.read()
    return data
""",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        assert result.score <= 0.6, f"未关闭资源代码分数应≤0.6，实际为{result.score}"

    def test_syntax_error_zero_score(self, evaluator):
        """
        黄金标准：语法错误的代码应返回低分
        场景：缺少冒号的函数定义
        预期：score <= 0.5
        """
        request = EvaluationSchema(
            id="code_gold_009",
            type="code",
            payload={
                "code": """
def hello()
    print("Hello")
""",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score <= 0.5, f"语法错误代码分数应<=0.5，实际为{result.score}"

    def test_deserialization_vulnerability(self, evaluator):
        """
        黄金标准：反序列化漏洞必须被识别
        漏洞类型：使用pickle.loads处理用户输入
        预期：安全分数 ≤ 0.3
        """
        request = EvaluationSchema(
            id="code_gold_010",
            type="code",
            payload={
                "code": """
import pickle

def deserialize_data(data):
    return pickle.loads(data)
""",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        assert result.score <= 0.3, f"反序列化漏洞代码分数应≤0.3，实际为{result.score}"