content = '''"\"\"\"MemoryEvaluator 单元测试\"\"\"

from src.domain.evaluators.memory import MemoryEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestMemoryEvaluator:
    \"\"\"MemoryEvaluator 测试类\"\"\"

    def setup_method(self):
        \"\"\"设置测试环境\"\"\"
        self.evaluator = MemoryEvaluator()

    def _create_request(self, **kwargs):
        \"\"\"创建测试请求\"\"\"
        return EvaluationSchema(
            id=\"test_case_001\",
            type=\"memory\",
            input_text=kwargs.get(\"input_text\", \"\"),
            payload=kwargs.get(\"payload\", {}),
        )

    def test_evaluate_retrieval_high_relevance(self):
        \"\"\"测试检索评估 - 高相关性\"\"\"
        request = self._create_request(
            input_text=\"Python代码优化技巧\",
            payload={
                \"retrieved_context\": \"Python代码优化技巧包括使用列表推导式、避免循环中的函数调用、使用内置函数等\",
                \"expected_context\": \"Python代码优化技巧\",
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid
        assert result.score >= 0.7
        assert result.data[\"retrieval_acceptable\"] is True

    def test_evaluate_retrieval_low_relevance(self):
        \"\"\"测试检索评估 - 低相关性\"\"\"
        request = self._create_request(
            input_text=\"Python代码优化技巧\",
            payload={
                \"retrieved_context\": \"天气很好，今天阳光明媚\",
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid
        assert result.score < 0.7
        assert result.data[\"retrieval_acceptable\"] is False

    def test_evaluate_retrieval_missing_query(self):
        \"\"\"测试检索评估 - 缺少查询\"\"\"
        request = self._create_request(
            payload={
                \"retrieved_context\": \"some context\",
            },
        )
        result = self.evaluator.evaluate(request)
        assert not result.is_valid
        assert \"不能为空\" in result.error

    def test_evaluate_retrieval_missing_context(self):
        \"\"\"测试检索评估 - 缺少检索上下文\"\"\"
        request = self._create_request(
            input_text=\"test query\",
            payload={},
        )
        result = self.evaluator.evaluate(request)
        assert not result.is_valid
        assert \"retrieved_context\" in result.error

    def test_evaluate_consistency_high(self):
        \"\"\"测试一致性评估 - 高一致性\"\"\"
        request = self._create_request(
            payload={
                \"old_memory\": \"用户张三，年龄30岁，程序员\",
                \"new_memory\": \"用户张三，年龄30岁，高级程序员\",
                \"update_intent\": \"升级职位\",
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid
        assert result.score >= 0.7
        assert result.data[\"consistency_acceptable\"] is True

    def test_evaluate_consistency_with_contradiction(self):
        \"\"\"测试一致性评估 - 包含矛盾\"\"\"
        request = self._create_request(
            payload={
                \"old_memory\": \"用户张三，年龄30岁，程序员\",
                \"new_memory\": \"用户张三，年龄30岁，不是程序员\",
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid
        assert result.data[\"contradiction_detected\"] is True

    def test_evaluate_consistency_with_info_loss(self):
        \"\"\"测试一致性评估 - 信息丢失\"\"\"
        request = self._create_request(
            payload={
                \"old_memory\": \"用户张三，年龄30岁，程序员，北京人，本科毕业\",
                \"new_memory\": \"用户张三，年龄30岁\",
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid
        assert result.data[\"info_loss_detected\"] is True

    def test_evaluate_consistency_missing_memory(self):
        \"\"\"测试一致性评估 - 缺少记忆数据\"\"\"
        request = self._create_request(
            payload={
                \"old_memory\": \"some memory\",
            },
        )
        result = self.evaluator.evaluate(request)
        assert not result.is_valid
        assert \"new_memory\" in result.error

    def test_evaluate_forgetting_none(self):
        \"\"\"测试遗忘率评估 - 无遗忘\"\"\"
        request = self._create_request(
            payload={
                \"original_memory\": \"用户张三，年龄30岁，程序员\",
                \"current_memory\": \"用户张三，年龄30岁，程序员\",
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid
        assert result.data[\"forgetting_rate\"] <= 0.1

    def test_evaluate_forgetting_high(self):
        \"\"\"测试遗忘率评估 - 高遗忘\"\"\"
        request = self._create_request(
            payload={
                \"original_memory\": \"用户张三，年龄30岁，程序员，北京人，本科毕业\",
                \"current_memory\": \"用户张三\",
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid
        assert result.data[\"forgetting_rate\"] > 0.4

    def test_evaluate_forgetting_missing_memory(self):
        \"\"\"测试遗忘率评估 - 缺少记忆数据\"\"\"
        request = self._create_request(
            payload={
                \"original_memory\": \"some memory\",
            },
        )
        result = self.evaluator.evaluate(request)
        assert not result.is_valid
        assert \"current_memory\" in result.error

    def test_evaluate_unknown_action(self):
        \"\"\"测试未知 action\"\"\"
        request = self._create_request(
            payload={
                \"action\": \"unknown_action\",
            },
        )
        result = self.evaluator.evaluate(request)
        assert not result.is_valid
        assert \"未知的 action\" in result.error
'''\"'''.replace('\\\\\"\"\"', '\"\"\"').replace('\"\\\"\"\"', '\"\"\"')

with open(r\"d:\\workspace\\ai-eval-platform-refactor\\tests\\unit\\test_memory_evaluator.py\", \"w\", encoding=\"utf-8\") as f:
    f.write(content)
print(\"Test file created\")
