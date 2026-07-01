#!/usr/bin/env python3
"""
评估器模板生成器 - 2026 工业级标准
自动生成符合项目架构规范的评估器代码模板

使用方式：
    1. 交互式模式: python scripts/generate_evaluator.py
    2. 命令行模式: python scripts/generate_evaluator.py --name MyEvaluator --type my_eval --description "我的评估器"

生成的模板包含：
    - 标准文档注释
    - EvaluatorFactory 注册装饰器
    - 双轨制评估入口（同步/异步）
    - 严格的输入验证
    - 完整的类型注解
    - LLM-as-a-Judge 模式支持
    - 降级策略集成
    - 自检清单
"""

import argparse
import os
import re
from typing import Optional, List


class EvaluatorTemplateGenerator:
    """评估器模板生成器"""

    BASE_TEMPLATE = """\"\"\"
{description}

{features}
\"\"\"

import logging
from typing import Any

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.fallback_policy import StrictSemanticPolicy
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)


@EvaluatorFactory.register("{evaluator_type}")
class {class_name}(BaseEvaluator):
    \"\"\"{class_description}\"\"\"

    def __init__(self, client: Any | None = None) -> None:
        \"\"\"初始化{class_name}

        Args:
            client: LLM 客户端实例（可选）
        \"\"\"
        super().__init__(
            client,
            fallback_policy=StrictSemanticPolicy(),
            require_input={require_input},
            require_expected={require_expected},
        )

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        \"\"\"执行评估逻辑

        Args:
            request: 评估请求

        Returns:
            DomainResponse: 评估结果
        \"\"\"
        {validation_block}

        {extraction_block}

        prompt = self._build_prompt({prompt_args})

        try:
            llm_output = self.client.chat(prompt)
            score = self.safe_parse_score(llm_output)

            if score is None:
                logger.error(f"{class_name} 响应数字提取失败: '{{llm_output}}'")
                return self.create_error_response(
                    error_message=f"无法解析评分: {{llm_output[:100]}}",
                    error_code="SCORE_PARSE_ERROR",
                )

            return self.create_success_response(
                text=actual_output,
                score=score,
                data={{
                    {data_fields}
                }},
                metadata={{"mode": "llm_as_judge"}},
            )

        except Exception as e:
            logger.exception(f"{class_name} LLM 调用失败: {{e}}")
            return self.create_error_response(
                error_message=f"LLM 调用异常: {{str(e)}}", error_code="LLM_CALL_ERROR"
            )

{prompt_method}
"""

    PROMPT_METHOD_TEMPLATE = """    def _build_prompt({args}) -> str:
        \"\"\"构建评估 Prompt

        Args:{arg_docs}

        Returns:
            str: 构建的 Prompt
        \"\"\"
        return (
            "你是一个资深的{evaluator_name}质量评测专家。请评估以下输出的质量。\\n"
            "评估标准：\\n"
            "- 完全符合预期：1.0分\\n"
            "- 基本符合预期：0.7-0.9分\\n"
            "- 部分符合预期：0.3-0.6分\\n"
            "- 完全不符合：0.0分\\n"
            "输出一个 0.0 到 1.0 的分数。\\n\\n"
            {prompt_variables}
            "最终评分（仅输出数字）："
        )
"""

    VALIDATION_BLOCK_REQUIRE_ALL = """        if error := self.validate_input(request):
            return error
        if error := self.validate_expected(request):
            return error
        if error := self.require_client_with_error():
            return error"""

    VALIDATION_BLOCK_REQUIRE_INPUT_ONLY = """        if error := self.validate_input(request):
            return error
        if error := self.require_client_with_error():
            return error"""

    VALIDATION_BLOCK_REQUIRE_CLIENT_ONLY = """        if error := self.require_client_with_error():
            return error"""

    def __init__(self):
        self.output_dir = os.path.join(os.path.dirname(__file__), "..", "src", "domain", "evaluators")

    def generate(self, **kwargs) -> str:
        """生成评估器代码"""
        class_name = kwargs.get("class_name", "MyEvaluator")
        evaluator_type = kwargs.get("evaluator_type", class_name.lower())
        description = kwargs.get("description", f"{class_name} - 2026 工业级标准评估器")
        class_description = kwargs.get("class_description", f"{class_name}（严格语义策略）")
        require_input = kwargs.get("require_input", True)
        require_expected = kwargs.get("require_expected", True)
        features = kwargs.get("features", self._default_features())

        validation_block = self._build_validation_block(require_input, require_expected)
        extraction_block = self._build_extraction_block(require_input, require_expected)
        prompt_args, data_fields, prompt_method = self._build_prompt_components(
            require_input, require_expected
        )

        return self.BASE_TEMPLATE.format(
            description=description,
            features=features,
            class_name=class_name,
            class_description=class_description,
            evaluator_type=evaluator_type,
            require_input=str(require_input).lower(),
            require_expected=str(require_expected).lower(),
            validation_block=validation_block,
            extraction_block=extraction_block,
            prompt_args=prompt_args,
            data_fields=data_fields,
            prompt_method=prompt_method,
        )

    def _default_features(self) -> str:
        return """工业级特性：
- LLM-as-a-Judge 置信度评分
- 严格语义策略（禁止静默降级）
- 完整类型注解
- 结构化异常处理
- 方法拆分（≤50行）"""

    def _build_validation_block(self, require_input: bool, require_expected: bool) -> str:
        if require_input and require_expected:
            return self.VALIDATION_BLOCK_REQUIRE_ALL
        elif require_input:
            return self.VALIDATION_BLOCK_REQUIRE_INPUT_ONLY
        else:
            return self.VALIDATION_BLOCK_REQUIRE_CLIENT_ONLY

    def _build_extraction_block(self, require_input: bool, require_expected: bool) -> str:
        lines = []
        if require_input:
            lines.append("        user_input = self.get_input_text(request)")
        lines.append("        actual_output = self.get_payload_data(request, \"actual_output\", \"\")")
        if require_expected:
            lines.append("        expected_output = self.get_payload_data(request, \"expected_output\", \"\")")
        return "\n".join(lines)

    def _build_prompt_components(self, require_input: bool, require_expected: bool) -> tuple:
        args_parts = ["self"]
        arg_docs = []
        prompt_vars = []
        data_fields = []

        if require_input:
            args_parts.append("user_input: str")
            arg_docs.append("            user_input: 用户输入文本")
            prompt_vars.append("        f\"【输入文本】：{{user_input}}\\n\"")

        args_parts.append("actual_output: str")
        arg_docs.append("            actual_output: 实际输出")
        prompt_vars.append("        f\"【实际输出】：{{actual_output}}\\n\"")

        if require_expected:
            args_parts.append("expected_output: str")
            arg_docs.append("            expected_output: 期望输出")
            prompt_vars.append("        f\"【期望输出】：{{expected_output}}\\n\"")

        data_fields.append("\"actual_output\": actual_output,")
        data_fields.append("\"raw_output\": llm_output,")
        data_fields.append(f"\"evaluator\": \"{self._get_evaluator_name()}\",")

        if require_input:
            data_fields.append("\"user_input\": user_input,")
        if require_expected:
            data_fields.append("\"expected_output\": expected_output,")

        prompt_args = ", ".join(
            [("user_input," if require_input else "") + " actual_output," + (" expected_output" if require_expected else "")]
        ).strip(", ")

        evaluator_name = self._get_evaluator_name()
        prompt_method = self.PROMPT_METHOD_TEMPLATE.format(
            args=", ".join(args_parts),
            arg_docs="\n".join(arg_docs),
            evaluator_name=evaluator_name,
            prompt_variables="".join(prompt_vars),
        )

        return prompt_args, "\n                ".join(data_fields), prompt_method

    def _get_evaluator_name(self) -> str:
        """获取评估器中文名称"""
        return "评估"

    def save(self, content: str, class_name: str) -> str:
        """保存生成的评估器文件"""
        filename = f"{class_name.lower()}.py"
        filepath = os.path.join(self.output_dir, filename)

        if os.path.exists(filepath):
            raise FileExistsError(f"文件已存在: {filepath}")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath


class InteractiveGenerator(EvaluatorTemplateGenerator):
    """交互式评估器生成器"""

    def run(self):
        """运行交互式生成流程"""
        print("=" * 60)
        print("评估器模板生成器 - 2026 工业级标准")
        print("=" * 60)
        print()

        class_name = self._prompt("评估器类名（如：MyEvaluator）", required=True)
        evaluator_type = self._prompt(
            f"评估器类型标识（默认: {class_name.lower()}）",
            default=class_name.lower()
        )
        description = self._prompt("评估器描述", default=f"{class_name} - 2026 工业级标准评估器")

        require_input = self._prompt_boolean("是否需要 user_input/text 字段?", default=True)
        require_expected = self._prompt_boolean("是否需要 expected_output 字段?", default=True)

        features = self._prompt_features()

        content = self.generate(
            class_name=class_name,
            evaluator_type=evaluator_type,
            description=description,
            require_input=require_input,
            require_expected=require_expected,
            features=features,
        )

        print()
        print("=" * 60)
        print("生成的代码预览：")
        print("=" * 60)
        print(content[:1000] + ("..." if len(content) > 1000 else ""))
        print()

        save = self._prompt_boolean("是否保存到文件?", default=True)
        if save:
            try:
                filepath = self.save(content, class_name)
                print(f"✓ 文件已保存: {filepath}")
                print(f"✓ 请在 src/domain/evaluators/__init__.py 中注册新评估器")
                print(f"✓ 请创建对应的测试文件: tests/unit/evaluator/test_{class_name.lower()}.py")
            except FileExistsError as e:
                print(f"✗ 错误: {e}")
                overwrite = self._prompt_boolean("是否覆盖?", default=False)
                if overwrite:
                    filepath = os.path.join(self.output_dir, f"{class_name.lower()}.py")
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"✓ 文件已覆盖: {filepath}")

    def _prompt(self, message: str, required: bool = False, default: Optional[str] = None) -> str:
        """提示用户输入"""
        prompt = f"{message}"
        if default is not None:
            prompt += f" [{default}]"
        prompt += ": "

        while True:
            try:
                value = input(prompt).strip()
            except EOFError:
                return default or ""

            if value:
                return value
            if default is not None:
                return default
            if not required:
                return ""

    def _prompt_boolean(self, message: str, default: bool = True) -> bool:
        """提示用户输入布尔值"""
        prompt = f"{message} [{'Y/n' if default else 'y/N'}]: "
        while True:
            try:
                value = input(prompt).strip().lower()
            except EOFError:
                return default

            if value in ("y", "yes", ""):
                return True
            if value in ("n", "no"):
                return False

    def _prompt_features(self) -> str:
        """提示用户选择特性"""
        print()
        print("请选择评估器特性（用空格分隔，输入编号）:")
        features = [
            ("1", "LLM-as-a-Judge 置信度评分"),
            ("2", "严格语义策略（禁止静默降级）"),
            ("3", "完整类型注解"),
            ("4", "结构化异常处理"),
            ("5", "方法拆分（≤50行）"),
        ]

        for num, desc in features:
            print(f"  [{num}] {desc}")

        selected = self._prompt("选择特性（默认全选）", default="12345")
        if not selected:
            return self._default_features()

        selected_features = []
        for num in selected:
            for n, desc in features:
                if n == num:
                    selected_features.append(desc)
                    break

        return "工业级特性：\n" + "\n".join(f"- {f}" for f in selected_features)


def main():
    parser = argparse.ArgumentParser(description="评估器模板生成器")
    parser.add_argument("--name", help="评估器类名（如：MyEvaluator）")
    parser.add_argument("--type", help="评估器类型标识")
    parser.add_argument("--description", help="评估器描述")
    parser.add_argument("--no-input", action="store_true", help="不需要 user_input 字段")
    parser.add_argument("--no-expected", action="store_true", help="不需要 expected_output 字段")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的文件")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不保存")

    args = parser.parse_args()

    if args.name:
        generator = EvaluatorTemplateGenerator()
        content = generator.generate(
            class_name=args.name,
            evaluator_type=args.type or args.name.lower(),
            description=args.description or f"{args.name} - 2026 工业级标准评估器",
            require_input=not args.no_input,
            require_expected=not args.no_expected,
        )

        print(content)

        if not args.dry_run:
            try:
                filepath = generator.save(content, args.name)
                print(f"\n✓ 文件已保存: {filepath}")
            except FileExistsError as e:
                if args.force:
                    filepath = os.path.join(generator.output_dir, f"{args.name.lower()}.py")
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"\n✓ 文件已覆盖: {filepath}")
                else:
                    print(f"\n✗ 错误: {e}（使用 --force 覆盖）")
    else:
        generator = InteractiveGenerator()
        generator.run()


if __name__ == "__main__":
    main()