from typing import Any

from src.domain.benchmarks.base import BaseBenchmark, BenchmarkResult
from src.domain.benchmarks.registry import BenchmarkRegistry


class ScenarioBenchmark(BaseBenchmark):
    name: str = "scenario"
    description: str = "业务场景端到端评估基准"
    category: str = "scenario"
    num_samples: int = 0

    def __init__(self, scenario_type: str = "customer_service"):
        self.scenario_type = scenario_type
        self.samples = self._load_scenario_samples()
        self.num_samples = len(self.samples)

    def _load_scenario_samples(self) -> list[dict[str, Any]]:
        if self.scenario_type == "customer_service":
            return self._load_customer_service_samples()
        elif self.scenario_type == "finance":
            return self._load_finance_samples()
        elif self.scenario_type == "code_development":
            return self._load_code_samples()
        elif self.scenario_type == "healthcare":
            return self._load_healthcare_samples()
        elif self.scenario_type == "education":
            return self._load_education_samples()
        else:
            return []

    def _load_customer_service_samples(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "cs_001",
                "scenario": "customer_service",
                "task": "处理客户投诉",
                "input": "我对你们的产品非常不满意！上周买的手机刚用两天就死机了，客服说要等一周才能修。这太不合理了！",
                "expected_output": "真诚道歉并提供解决方案",
                "expected_steps": ["道歉", "表达理解", "提供解决方案", "确认满意度"],
                "context": {"product": "手机", "issue": "死机", "purchase_date": "上周"},
                "difficulty": "medium",
                "success_criteria": ["道歉真诚", "解决方案合理", "表达理解"],
            },
            {
                "id": "cs_002",
                "scenario": "customer_service",
                "task": "产品咨询",
                "input": "你好，我想问一下这款笔记本电脑的续航时间是多久？支持快充吗？",
                "expected_output": "清晰回答问题并提供产品优势",
                "expected_steps": ["问候", "回答续航时间", "回答快充问题", "询问是否需要更多信息"],
                "context": {"product": "笔记本电脑", "questions": ["续航时间", "快充"]},
                "difficulty": "easy",
                "success_criteria": ["信息准确", "回答全面", "表达清晰"],
            },
            {
                "id": "cs_003",
                "scenario": "customer_service",
                "task": "退换货申请",
                "input": "我想退货，买的衣服尺码不合适，吊牌还在，是昨天刚收到的。",
                "expected_output": "确认退货条件并引导操作",
                "expected_steps": ["确认退货条件", "告知退货流程", "确认收货信息", "预估退款时间"],
                "context": {
                    "product": "衣服",
                    "issue": "尺码不合适",
                    "purchase_date": "昨天",
                    "tags_intact": True,
                },
                "difficulty": "easy",
                "success_criteria": ["条件确认", "流程清晰", "时间明确"],
            },
            {
                "id": "cs_004",
                "scenario": "customer_service",
                "task": "处理愤怒客户",
                "input": "你们怎么搞的！快递三天了还没到，电话也打不通，我急用啊！",
                "expected_output": "安抚情绪并解决问题",
                "expected_steps": ["安抚情绪", "查询物流", "提供解决方案", "表达歉意"],
                "context": {"issue": "快递延误", "urgency": "高"},
                "difficulty": "hard",
                "success_criteria": ["情绪安抚有效", "问题解决", "表达真诚"],
            },
            {
                "id": "cs_005",
                "scenario": "customer_service",
                "task": "售后服务",
                "input": "我的家电保修期到了，现在出了点问题，请问还能修吗？怎么收费？",
                "expected_output": "说明保修政策并提供维修方案",
                "expected_steps": ["理解问题", "说明保修政策", "提供维修方案", "告知收费标准"],
                "context": {"product": "家电", "status": "过保"},
                "difficulty": "medium",
                "success_criteria": ["政策清晰", "方案可行", "费用透明"],
            },
        ]

    def _load_finance_samples(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "fin_001",
                "scenario": "finance",
                "task": "理财咨询",
                "input": "我有5万元闲钱，想做投资，风险承受能力中等，有什么推荐吗？",
                "expected_output": "推荐适合的理财产品并说明风险收益",
                "expected_steps": ["了解需求", "评估风险", "推荐产品", "说明风险收益"],
                "context": {"amount": "5万元", "risk_tolerance": "中等"},
                "difficulty": "medium",
                "success_criteria": ["推荐合适", "风险说明", "收益预期"],
            },
            {
                "id": "fin_002",
                "scenario": "finance",
                "task": "账户问题",
                "input": "我的银行卡今天突然不能用了，显示余额不足，但我明明刚存了钱。",
                "expected_output": "排查问题并提供解决方案",
                "expected_steps": ["了解情况", "排查原因", "提供解决方案", "确认结果"],
                "context": {"issue": "账户异常", "recent_action": "存款"},
                "difficulty": "medium",
                "success_criteria": ["问题定位", "解决方案", "确认解决"],
            },
            {
                "id": "fin_003",
                "scenario": "finance",
                "task": "贷款申请",
                "input": "我想申请房贷，首付30%，贷款200万，20年还清，利率多少？每月还多少？",
                "expected_output": "计算贷款方案并说明条件",
                "expected_steps": ["确认需求", "计算利率", "计算月供", "说明条件"],
                "context": {"loan_amount": "200万", "down_payment": "30%", "term": "20年"},
                "difficulty": "easy",
                "success_criteria": ["计算准确", "利率说明", "条件清晰"],
            },
            {
                "id": "fin_004",
                "scenario": "finance",
                "task": "信用卡账单",
                "input": "这个月的信用卡账单好像有问题，我没记得花这么多钱，能帮我查一下吗？",
                "expected_output": "协助核对账单并解释疑问",
                "expected_steps": ["理解疑问", "协助核对", "解释费用", "确认无误"],
                "context": {"issue": "账单疑问"},
                "difficulty": "easy",
                "success_criteria": ["耐心协助", "解释清楚", "确认无误"],
            },
            {
                "id": "fin_005",
                "scenario": "finance",
                "task": "保险咨询",
                "input": "我想买一份重疾险，今年35岁，预算每年1万元左右，有什么推荐吗？",
                "expected_output": "推荐合适的保险产品并说明保障范围",
                "expected_steps": ["了解需求", "评估情况", "推荐产品", "说明保障"],
                "context": {"age": "35岁", "budget": "1万元/年", "type": "重疾险"},
                "difficulty": "medium",
                "success_criteria": ["推荐合适", "保障清晰", "费用透明"],
            },
        ]

    def _load_code_samples(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "code_001",
                "scenario": "code_development",
                "task": "代码调试",
                "input": "我这段Python代码运行时出现IndexError，帮我看看哪里错了：\nnumbers = [1, 2, 3]\nfor i in range(4):\n    print(numbers[i])",
                "expected_output": "指出错误并提供修复方案",
                "expected_steps": ["分析错误", "指出问题", "提供修复", "验证方案"],
                "context": {"language": "Python", "error": "IndexError", "code": "列表越界"},
                "difficulty": "easy",
                "success_criteria": ["错误定位准确", "修复方案正确", "解释清晰"],
            },
            {
                "id": "code_002",
                "scenario": "code_development",
                "task": "功能开发",
                "input": "帮我写一个Python函数，计算两个日期之间的天数差。",
                "expected_output": "提供完整的函数实现",
                "expected_steps": ["理解需求", "设计方案", "编写代码", "提供示例"],
                "context": {"language": "Python", "function": "日期计算"},
                "difficulty": "easy",
                "success_criteria": ["功能正确", "代码规范", "示例完整"],
            },
            {
                "id": "code_003",
                "scenario": "code_development",
                "task": "代码优化",
                "input": "这段代码性能不太好，帮我优化一下：\nresult = []\nfor i in range(1000000):\n    if i % 2 == 0:\n        result.append(i)",
                "expected_output": "分析性能问题并提供优化方案",
                "expected_steps": ["分析性能", "指出瓶颈", "提供优化", "对比效果"],
                "context": {"language": "Python", "issue": "性能优化"},
                "difficulty": "medium",
                "success_criteria": ["分析准确", "优化有效", "解释清楚"],
            },
            {
                "id": "code_004",
                "scenario": "code_development",
                "task": "API设计",
                "input": "帮我设计一个RESTful API，用于管理用户信息，包括CRUD操作。",
                "expected_output": "提供API设计方案",
                "expected_steps": ["理解需求", "设计端点", "定义数据模型", "提供示例"],
                "context": {"type": "RESTful API", "resource": "用户"},
                "difficulty": "medium",
                "success_criteria": ["设计合理", "端点完整", "示例清晰"],
            },
            {
                "id": "code_005",
                "scenario": "code_development",
                "task": "数据库设计",
                "input": "帮我设计一个电商系统的数据库表结构，包含用户、商品、订单等。",
                "expected_output": "提供数据库设计方案",
                "expected_steps": ["理解需求", "设计表结构", "定义关系", "提供SQL"],
                "context": {"system": "电商", "tables": ["用户", "商品", "订单"]},
                "difficulty": "hard",
                "success_criteria": ["设计合理", "关系清晰", "SQL完整"],
            },
        ]

    def _load_healthcare_samples(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "hc_001",
                "scenario": "healthcare",
                "task": "症状咨询",
                "input": "我最近总是头疼，特别是下午，还伴有恶心，这是什么原因？",
                "expected_output": "询问症状细节并给出健康建议",
                "expected_steps": ["询问细节", "分析可能原因", "给出建议", "提醒就医"],
                "context": {"symptom": "头疼", "time": "下午", "伴随": "恶心"},
                "difficulty": "medium",
                "success_criteria": ["询问全面", "建议合理", "提醒就医"],
            },
            {
                "id": "hc_002",
                "scenario": "healthcare",
                "task": "用药指导",
                "input": "医生给我开了阿莫西林，请问应该怎么吃？有什么注意事项？",
                "expected_output": "提供用药指导和注意事项",
                "expected_steps": ["确认药物", "说明用法", "说明注意事项", "提醒遵医嘱"],
                "context": {"drug": "阿莫西林"},
                "difficulty": "easy",
                "success_criteria": ["用法准确", "注意事项全面", "提醒遵医嘱"],
            },
            {
                "id": "hc_003",
                "scenario": "healthcare",
                "task": "健康建议",
                "input": "我今年40岁，想开始健身，有什么适合我的运动推荐吗？",
                "expected_output": "提供个性化的健身建议",
                "expected_steps": ["了解情况", "评估身体状况", "推荐运动", "提醒注意事项"],
                "context": {"age": "40岁", "goal": "健身"},
                "difficulty": "easy",
                "success_criteria": ["推荐合适", "考虑年龄", "提醒注意事项"],
            },
        ]

    def _load_education_samples(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "edu_001",
                "scenario": "education",
                "task": "学习规划",
                "input": "我想学习Python编程，零基础，有什么好的学习路径吗？",
                "expected_output": "提供学习规划和资源推荐",
                "expected_steps": ["了解基础", "推荐学习路径", "推荐资源", "建议练习"],
                "context": {"goal": "学习Python", "level": "零基础"},
                "difficulty": "easy",
                "success_criteria": ["路径清晰", "资源推荐", "建议实用"],
            },
            {
                "id": "edu_002",
                "scenario": "education",
                "task": "概念解释",
                "input": "什么是机器学习？和深度学习有什么区别？",
                "expected_output": "用通俗易懂的语言解释概念",
                "expected_steps": ["定义机器学习", "定义深度学习", "说明区别", "举例说明"],
                "context": {"topic": "机器学习", "comparison": "深度学习"},
                "difficulty": "medium",
                "success_criteria": ["解释清晰", "区别明确", "例子易懂"],
            },
            {
                "id": "edu_003",
                "scenario": "education",
                "task": "论文辅导",
                "input": "我要写一篇关于AI的论文，不知道怎么选题，能给我一些建议吗？",
                "expected_output": "提供论文选题建议和写作指导",
                "expected_steps": ["了解兴趣", "推荐选题", "建议方向", "指导写作"],
                "context": {"topic": "AI", "purpose": "论文"},
                "difficulty": "hard",
                "success_criteria": ["选题合适", "方向明确", "指导实用"],
            },
        ]

    def load_dataset(self) -> list[dict[str, Any]]:
        return self.samples

    def evaluate(
        self, llm_client=None, samples: list[dict[str, Any]] | None = None
    ) -> BenchmarkResult:
        if samples is None:
            samples = self.samples

        results = []
        correct_count = 0

        for sample in samples:
            result = self._evaluate_sample(sample)
            results.append(result)
            if result.get("is_correct", False):
                correct_count += 1

        accuracy = correct_count / len(samples) if samples else 0

        return BenchmarkResult(
            benchmark_name=f"{self.scenario_type}_scenario",
            total_samples=len(samples),
            correct_samples=correct_count,
            accuracy=accuracy,
            scores=results,
            metadata={"scenario_type": self.scenario_type},
        )

    def _evaluate_sample(self, sample: dict[str, Any]) -> dict[str, Any]:
        actual_output = sample.get("actual_output", "")
        sample.get("expected_output", "")
        expected_steps = sample.get("expected_steps", [])
        success_criteria = sample.get("success_criteria", [])

        step_matches = []
        for step in expected_steps:
            if self._check_step_match(step, actual_output):
                step_matches.append({"step": step, "matched": True})
            else:
                step_matches.append({"step": step, "matched": False})

        criteria_matches = []
        for criterion in success_criteria:
            if self._check_criterion_match(criterion, actual_output):
                criteria_matches.append({"criterion": criterion, "matched": True})
            else:
                criteria_matches.append({"criterion": criterion, "matched": False})

        step_match_rate = (
            sum(1 for m in step_matches if m["matched"]) / len(step_matches) if step_matches else 0
        )
        criteria_match_rate = (
            sum(1 for m in criteria_matches if m["matched"]) / len(criteria_matches)
            if criteria_matches
            else 0
        )

        is_correct = step_match_rate >= 0.6 and criteria_match_rate >= 0.6

        return {
            "sample_id": sample["id"],
            "task": sample["task"],
            "step_matches": step_matches,
            "criteria_matches": criteria_matches,
            "step_match_rate": step_match_rate,
            "criteria_match_rate": criteria_match_rate,
            "is_correct": is_correct,
        }

    def _check_step_match(self, step: str, actual_output: str) -> bool:
        if not actual_output:
            return False

        step_lower = step.lower()
        output_lower = actual_output.lower()

        if step_lower in output_lower:
            return True

        for i in range(len(step_lower) - 1):
            substring = step_lower[i : i + 2]
            if substring in output_lower:
                return True

        return False

    def _check_criterion_match(self, criterion: str, actual_output: str) -> bool:
        if not actual_output:
            return False

        criterion_lower = criterion.lower()
        output_lower = actual_output.lower()

        if criterion_lower in output_lower:
            return True

        for i in range(len(criterion_lower) - 1):
            substring = criterion_lower[i : i + 2]
            if substring in output_lower:
                return True

        return False

    def calculate_score(self, results: list[dict[str, Any]]) -> float:
        if not results:
            return 0.0

        total_score = 0.0
        for result in results:
            step_rate = result.get("step_match_rate", 0)
            criteria_rate = result.get("criteria_match_rate", 0)
            total_score += step_rate * 0.5 + criteria_rate * 0.5

        return total_score / len(results)

    def build_prompt(self, sample: dict[str, Any]) -> str:
        prompt = f"""你是一个专业的{self._get_scenario_name()}助手。

任务：{sample["task"]}

用户输入：{sample["input"]}

请按照以下步骤完成任务：
"""
        for i, step in enumerate(sample.get("expected_steps", []), 1):
            prompt += f"{i}. {step}\n"

        prompt += "\n请给出详细的回答："
        return prompt

    def _get_scenario_name(self) -> str:
        scenario_names = {
            "customer_service": "客服",
            "finance": "金融",
            "code_development": "代码开发",
            "healthcare": "医疗健康",
            "education": "教育",
        }
        return scenario_names.get(self.scenario_type, "业务")


@BenchmarkRegistry.register("scenario_customer_service")
class CustomerServiceBenchmark(ScenarioBenchmark):
    name = "scenario_customer_service"
    description = "客服场景端到端评估基准"
    category = "scenario"

    def __init__(self):
        super().__init__(scenario_type="customer_service")


@BenchmarkRegistry.register("scenario_finance")
class FinanceBenchmark(ScenarioBenchmark):
    name = "scenario_finance"
    description = "金融场景端到端评估基准"
    category = "scenario"

    def __init__(self):
        super().__init__(scenario_type="finance")


@BenchmarkRegistry.register("scenario_code")
class CodeDevelopmentBenchmark(ScenarioBenchmark):
    name = "scenario_code"
    description = "代码开发场景端到端评估基准"
    category = "scenario"

    def __init__(self):
        super().__init__(scenario_type="code_development")


@BenchmarkRegistry.register("scenario_healthcare")
class HealthcareBenchmark(ScenarioBenchmark):
    name = "scenario_healthcare"
    description = "医疗健康场景端到端评估基准"
    category = "scenario"

    def __init__(self):
        super().__init__(scenario_type="healthcare")


@BenchmarkRegistry.register("scenario_education")
class EducationBenchmark(ScenarioBenchmark):
    name = "scenario_education"
    description = "教育场景端到端评估基准"
    category = "scenario"

    def __init__(self):
        super().__init__(scenario_type="education")
