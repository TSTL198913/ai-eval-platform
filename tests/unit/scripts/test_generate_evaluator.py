"""
评估器模板生成器单元测试
"""

import os
import pytest
from scripts.generate_evaluator import EvaluatorTemplateGenerator, InteractiveGenerator


class TestEvaluatorTemplateGenerator:
    """测试评估器模板生成器"""

    def test_generate_basic_evaluator(self):
        """测试生成基本评估器模板"""
        generator = EvaluatorTemplateGenerator()
        content = generator.generate(
            class_name="TestEvaluator",
            evaluator_type="test_eval",
            description="测试评估器",
        )

        assert "class TestEvaluator(BaseEvaluator):" in content
        assert '@EvaluatorFactory.register("test_eval")' in content
        assert "def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:" in content
        assert "self.create_success_response(" in content
        assert "self.create_error_response(" in content

    def test_generate_without_expected(self):
        """测试生成不需要 expected_output 的评估器"""
        generator = EvaluatorTemplateGenerator()
        content = generator.generate(
            class_name="NoExpectedEvaluator",
            evaluator_type="no_expected",
            require_expected=False,
        )

        assert "require_expected=false" in content
        assert "expected_output" not in content
        assert "validate_expected" not in content

    def test_generate_without_input(self):
        """测试生成不需要 user_input 的评估器"""
        generator = EvaluatorTemplateGenerator()
        content = generator.generate(
            class_name="NoInputEvaluator",
            evaluator_type="no_input",
            require_input=False,
        )

        assert "require_input=false" in content
        assert "validate_input" not in content
        assert "user_input" not in content

    def test_generate_minimal_evaluator(self):
        """测试生成最小化评估器"""
        generator = EvaluatorTemplateGenerator()
        content = generator.generate(
            class_name="MinimalEvaluator",
            evaluator_type="minimal",
            require_input=False,
            require_expected=False,
        )

        assert "require_input=false" in content
        assert "require_expected=false" in content
        assert "validate_input" not in content
        assert "validate_expected" not in content

    def test_generate_contains_fallback_policy(self):
        """测试生成的模板包含降级策略"""
        generator = EvaluatorTemplateGenerator()
        content = generator.generate(class_name="FallbackEvaluator")

        assert "StrictSemanticPolicy()" in content
        assert "fallback_policy=" in content

    def test_generate_contains_llm_as_judge(self):
        """测试生成的模板包含 LLM-as-a-Judge 模式"""
        generator = EvaluatorTemplateGenerator()
        content = generator.generate(class_name="LLMJudgeEvaluator")

        assert "llm_as_judge" in content
        assert "self.client.chat(prompt)" in content
        assert "self.safe_parse_score(llm_output)" in content

    def test_save_creates_file(self, tmp_path):
        """测试保存生成的文件"""
        generator = EvaluatorTemplateGenerator()
        generator.output_dir = str(tmp_path)

        content = generator.generate(class_name="SaveTestEvaluator")
        filepath = generator.save(content, "SaveTestEvaluator")

        assert os.path.exists(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            saved_content = f.read()
            assert content == saved_content

    def test_save_raises_error_if_exists(self, tmp_path):
        """测试保存已存在文件时抛出异常"""
        generator = EvaluatorTemplateGenerator()
        generator.output_dir = str(tmp_path)

        filepath = os.path.join(str(tmp_path), "existing.py")
        with open(filepath, "w") as f:
            f.write("existing content")

        content = generator.generate(class_name="Existing")
        with pytest.raises(FileExistsError):
            generator.save(content, "Existing")

    def test_build_validation_block_all_required(self):
        """测试构建完整验证块"""
        generator = EvaluatorTemplateGenerator()
        block = generator._build_validation_block(True, True)

        assert "validate_input" in block
        assert "validate_expected" in block
        assert "require_client_with_error" in block

    def test_build_validation_block_input_only(self):
        """测试构建仅输入验证块"""
        generator = EvaluatorTemplateGenerator()
        block = generator._build_validation_block(True, False)

        assert "validate_input" in block
        assert "validate_expected" not in block
        assert "require_client_with_error" in block

    def test_build_validation_block_client_only(self):
        """测试构建仅客户端验证块"""
        generator = EvaluatorTemplateGenerator()
        block = generator._build_validation_block(False, False)

        assert "validate_input" not in block
        assert "validate_expected" not in block
        assert "require_client_with_error" in block

    def test_build_extraction_block_all_required(self):
        """测试构建完整提取块"""
        generator = EvaluatorTemplateGenerator()
        block = generator._build_extraction_block(True, True)

        assert "user_input" in block
        assert "actual_output" in block
        assert "expected_output" in block

    def test_build_extraction_block_no_expected(self):
        """测试构建无期望输出提取块"""
        generator = EvaluatorTemplateGenerator()
        block = generator._build_extraction_block(True, False)

        assert "user_input" in block
        assert "actual_output" in block
        assert "expected_output" not in block

    def test_build_prompt_components_all_required(self):
        """测试构建完整的 Prompt 组件"""
        generator = EvaluatorTemplateGenerator()
        prompt_args, data_fields, prompt_method = generator._build_prompt_components(True, True)

        assert "user_input" in prompt_args
        assert "actual_output" in prompt_args
        assert "expected_output" in prompt_args
        assert "user_input" in data_fields
        assert "expected_output" in data_fields
        assert "用户输入文本" in prompt_method
        assert "期望输出" in prompt_method

    def test_default_features(self):
        """测试默认特性描述"""
        generator = EvaluatorTemplateGenerator()
        features = generator._default_features()

        assert "LLM-as-a-Judge" in features
        assert "严格语义策略" in features
        assert "类型注解" in features
        assert "异常处理" in features

    def test_get_evaluator_name(self):
        """测试获取评估器名称"""
        generator = EvaluatorTemplateGenerator()
        name = generator._get_evaluator_name()

        assert name == "评估"


class TestInteractiveGenerator:
    """测试交互式生成器"""

    def test_interactive_generator_inherits_from_base(self):
        """测试交互式生成器继承自基类"""
        generator = InteractiveGenerator()
        assert isinstance(generator, EvaluatorTemplateGenerator)

    def test_interactive_generator_has_run_method(self):
        """测试交互式生成器有 run 方法"""
        generator = InteractiveGenerator()
        assert hasattr(generator, "run")
        assert callable(generator.run)