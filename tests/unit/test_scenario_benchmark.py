import pytest

from src.domain.benchmarks.scenario import (
    CodeDevelopmentBenchmark,
    CustomerServiceBenchmark,
    EducationBenchmark,
    FinanceBenchmark,
    HealthcareBenchmark,
    ScenarioBenchmark,
)


class TestScenarioBenchmark:
    def test_load_customer_service_samples(self):
        benchmark = CustomerServiceBenchmark()
        samples = benchmark.load_dataset()
        assert len(samples) == 5
        assert samples[0]["scenario"] == "customer_service"

    def test_load_finance_samples(self):
        benchmark = FinanceBenchmark()
        samples = benchmark.load_dataset()
        assert len(samples) == 5
        assert samples[0]["scenario"] == "finance"

    def test_load_code_samples(self):
        benchmark = CodeDevelopmentBenchmark()
        samples = benchmark.load_dataset()
        assert len(samples) == 5
        assert samples[0]["scenario"] == "code_development"

    def test_load_healthcare_samples(self):
        benchmark = HealthcareBenchmark()
        samples = benchmark.load_dataset()
        assert len(samples) == 3
        assert samples[0]["scenario"] == "healthcare"

    def test_load_education_samples(self):
        benchmark = EducationBenchmark()
        samples = benchmark.load_dataset()
        assert len(samples) == 3
        assert samples[0]["scenario"] == "education"

    def test_build_prompt(self):
        benchmark = CustomerServiceBenchmark()
        sample = benchmark.samples[0]
        prompt = benchmark.build_prompt(sample)
        assert "客服" in prompt
        assert sample["task"] in prompt
        assert sample["input"] in prompt
        assert "步骤" in prompt

    def test_evaluate_with_samples(self):
        benchmark = CustomerServiceBenchmark()
        sample = benchmark.samples[0].copy()
        sample["actual_output"] = "非常抱歉给您带来不便！我理解您的心情，我们可以为您提供加急维修服务，预计3天内完成。请问这样可以吗？"

        result = benchmark.evaluate(samples=[sample])
        assert result.total_samples == 1
        assert result.accuracy >= 0

    def test_evaluate_sample_with_correct_output(self):
        benchmark = CustomerServiceBenchmark()
        sample = benchmark.samples[0].copy()
        sample["actual_output"] = "非常抱歉！我理解您的心情。我们可以提供加急维修服务。请问您满意这个解决方案吗？"

        result = benchmark._evaluate_sample(sample)
        assert result["sample_id"] == "cs_001"
        assert result["step_match_rate"] >= 0.5
        assert result["criteria_match_rate"] >= 0.5

    def test_evaluate_sample_with_incorrect_output(self):
        benchmark = CustomerServiceBenchmark()
        sample = benchmark.samples[0].copy()
        sample["actual_output"] = "不知道"

        result = benchmark._evaluate_sample(sample)
        assert result["step_match_rate"] == 0
        assert result["criteria_match_rate"] == 0
        assert result["is_correct"] is False

    def test_calculate_score(self):
        benchmark = CustomerServiceBenchmark()
        results = [
            {"step_match_rate": 0.8, "criteria_match_rate": 0.8},
            {"step_match_rate": 0.6, "criteria_match_rate": 0.6},
            {"step_match_rate": 0.4, "criteria_match_rate": 0.4},
        ]
        score = benchmark.calculate_score(results)
        assert score == pytest.approx(0.6, abs=0.01)

    def test_num_samples(self):
        cs_benchmark = CustomerServiceBenchmark()
        fin_benchmark = FinanceBenchmark()
        code_benchmark = CodeDevelopmentBenchmark()

        assert cs_benchmark.num_samples == 5
        assert fin_benchmark.num_samples == 5
        assert code_benchmark.num_samples == 5

    def test_scenario_types(self):
        scenarios = [
            ("customer_service", CustomerServiceBenchmark),
            ("finance", FinanceBenchmark),
            ("code_development", CodeDevelopmentBenchmark),
            ("healthcare", HealthcareBenchmark),
            ("education", EducationBenchmark),
        ]

        for scenario_type, benchmark_class in scenarios:
            benchmark = benchmark_class()
            assert benchmark.scenario_type == scenario_type
            assert len(benchmark.samples) > 0

    def test_sample_structure(self):
        benchmark = CustomerServiceBenchmark()
        sample = benchmark.samples[0]

        assert "id" in sample
        assert "scenario" in sample
        assert "task" in sample
        assert "input" in sample
        assert "expected_output" in sample
        assert "expected_steps" in sample
        assert "success_criteria" in sample
        assert "difficulty" in sample

    def test_evaluate_empty_samples(self):
        benchmark = CustomerServiceBenchmark()
        result = benchmark.evaluate(samples=[])
        assert result.total_samples == 0
        assert result.accuracy == 0
        assert result.correct_samples == 0

    def test_build_prompt_contains_all_steps(self):
        benchmark = FinanceBenchmark()
        sample = benchmark.samples[0]
        prompt = benchmark.build_prompt(sample)

        for step in sample["expected_steps"]:
            assert step in prompt

    def test_evaluate_with_matched_steps(self):
        benchmark = CodeDevelopmentBenchmark()
        sample = benchmark.samples[0].copy()
        sample["actual_output"] = "分析错误：这是一个IndexError，因为列表只有3个元素，但循环了4次。问题在于range(4)应该改为range(3)。修复方案：将range(4)改为range(len(numbers))。验证方案：运行修改后的代码应该正确输出1、2、3。"

        result = benchmark._evaluate_sample(sample)
        assert result["step_match_rate"] > 0.5
        assert result["is_correct"] is True