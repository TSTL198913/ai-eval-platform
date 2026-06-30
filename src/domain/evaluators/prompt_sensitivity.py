"""
Prompt敏感度评估器
测试Prompt变化对输出的影响，评估模型的稳定性
"""

import re
import statistics
from dataclasses import dataclass

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.models.base import BaseLLMClient
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@dataclass
class PromptVariant:
    """Prompt变体"""

    name: str
    template: str
    variables: dict
    description: str = ""


class PromptSensitivityEvaluator(BaseEvaluator):
    """Prompt敏感度评估器

    通过改变Prompt的细微设置，观察模型输出的方差。
    用于评估：
    - 模型对Prompt措辞的敏感程度
    - 输出的稳定性和一致性
    - Prompt工程的最佳实践
    """

    def __init__(self, client: BaseLLMClient | None = None):
        super().__init__(client=client, require_input=True)
        self.variance_threshold = 0.15  # 方差阈值
        self.stability_threshold = 0.8  # 稳定性阈值

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        if error := self.validate_input(request):
            return error

        # 获取参数
        base_prompt = self.get_payload_data(request, "base_prompt", "")
        user_input = self.get_input_text(request)
        variants = self.get_payload_data(request, "variants", None)
        evaluation_dimensions = self.get_payload_data(
            request, "evaluation_dimensions", ["semantic", "lexical", "stylistic"]
        )

        if not base_prompt:
            return DomainResponse(is_valid=False, error="base_prompt不能为空")

        # 生成Prompt变体
        if variants is None:
            variants = self._generate_default_variants(base_prompt, user_input)

        # 执行评估
        results = []
        for variant in variants:
            if not self.client:
                # Mock结果
                variant_result = self._mock_variant_result(variant)
            else:
                # 实际调用
                variant_result = self._execute_variant(variant, user_input)
            results.append(variant_result)

        # 分析结果
        analysis = self._analyze_results(results, evaluation_dimensions)

        return DomainResponse(
            is_valid=True,
            text=analysis["summary"],
            score=analysis["stability_score"],
            data=analysis,
        )

    def _generate_default_variants(self, base_prompt: str, user_input: str) -> list[PromptVariant]:
        """生成默认Prompt变体"""
        return [
            PromptVariant(
                name="original",
                template=base_prompt,
                variables={"input": user_input},
                description="原始Prompt",
            ),
            PromptVariant(
                name="concise",
                template=base_prompt.replace("请", "简要").replace("详细", "简明"),
                variables={"input": user_input},
                description="简洁版本",
            ),
            PromptVariant(
                name="formal",
                template=base_prompt + "\n请使用正式语言。",
                variables={"input": user_input},
                description="正式语气",
            ),
            PromptVariant(
                name="detailed",
                template=base_prompt + "\n请尽可能详细地回答。",
                variables={"input": user_input},
                description="详细要求",
            ),
            PromptVariant(
                name="step_by_step",
                template=base_prompt + "\n请分步骤解答。",
                variables={"input": user_input},
                description="分步骤要求",
            ),
        ]

    def _execute_variant(self, variant: PromptVariant, user_input: str) -> dict:
        """执行单个Prompt变体"""
        try:
            prompt = variant.template.format(**variant.variables, input=user_input)
            response = self.client.chat(prompt)

            return {
                "name": variant.name,
                "description": variant.description,
                "prompt": prompt,
                "response": response,
                "success": True,
                "error": None,
                "response_length": len(response),
            }
        except Exception as e:
            return {
                "name": variant.name,
                "description": variant.description,
                "prompt": "",
                "response": "",
                "success": False,
                "error": str(e),
                "response_length": 0,
            }

    def _mock_variant_result(self, variant: PromptVariant) -> dict:
        """生成Mock结果"""
        base_responses = {
            "original": "这是一个关于主题的详细回答，涵盖了多个方面。",
            "concise": "主题回答：要点1、要点2、要点3。",
            "formal": "尊敬的用户，关于您提出的主题，本回答将从专业角度进行阐述。",
            "detailed": "本回答将全面、深入地探讨该主题的各个层面：第一部分...第二部分...第三部分...",
            "step_by_step": "好的，让我分步骤为您解答：\n步骤1：首先... \n步骤2：然后... \n步骤3：最后...",
        }

        response = base_responses.get(variant.name, "这是测试回复内容。")

        return {
            "name": variant.name,
            "description": variant.description,
            "prompt": variant.template,
            "response": response,
            "success": True,
            "error": None,
            "response_length": len(response),
        }

    def _analyze_results(self, results: list[dict], dimensions: list[str]) -> dict:
        """分析Prompt变体结果"""
        # 过滤成功的响应
        successful_results = [r for r in results if r["success"]]
        failed_results = [r for r in results if not r["success"]]

        if not successful_results:
            return {
                "stability_score": 0.0,
                "variance": 1.0,
                "summary": "所有Prompt变体均失败",
                "is_stable": False,
            }

        # 计算各维度指标
        metrics = {}

        if "lexical" in dimensions:
            metrics["lexical"] = self._calculate_lexical_variance(successful_results)

        if "semantic" in dimensions:
            metrics["semantic"] = self._calculate_semantic_variance(successful_results)

        if "stylistic" in dimensions:
            metrics["stylistic"] = self._calculate_stylistic_variance(successful_results)

        if "length" in dimensions:
            metrics["length"] = self._calculate_length_variance(successful_results)

        # 计算综合稳定性分数
        stability_score = self._calculate_stability_score(metrics)

        # 生成详细分析
        analysis = {
            "variant_count": len(results),
            "successful_count": len(successful_results),
            "failed_count": len(failed_results),
            "metrics": metrics,
            "stability_score": stability_score,
            "variance": 1.0 - stability_score,
            "is_stable": stability_score >= self.stability_threshold,
            "sensitivity_level": self._get_sensitivity_level(stability_score),
            "variant_results": results,
            "failed_results": failed_results,
        }

        # 生成建议
        analysis["recommendations"] = self._generate_recommendations(analysis)

        # 生成总结
        analysis["summary"] = self._generate_summary(analysis)

        return analysis

    def _calculate_lexical_variance(self, results: list[dict]) -> dict:
        """计算词汇差异"""
        responses = [r["response"] for r in results]

        # 计算响应长度方差
        lengths = [len(r) for r in responses]
        length_variance = (
            statistics.variance(lengths) / (statistics.mean(lengths) + 1) if len(lengths) > 1 else 0
        )

        # 计算词汇多样性（唯一词比例）
        vocabularies = [set(r.split()) for r in responses]
        avg_vocab_ratio = statistics.mean(
            [len(v) / (len(r.split()) + 1) for v, r in zip(vocabularies, responses, strict=False)]
        )

        return {
            "length_variance": length_variance,
            "vocabulary_diversity": avg_vocab_ratio,
            "normalized_variance": min(length_variance, 1.0),
        }

    def _calculate_semantic_variance(self, results: list[dict]) -> dict:
        """计算语义差异（简化版）"""
        # 简化实现：基于关键词重叠度
        responses = [r["response"].lower() for r in results]

        keywords_sets = []
        for response in responses:
            # 提取关键词
            words = re.findall(r"\b\w{3,}\b", response)
            keywords_sets.append(set(words))

        if len(keywords_sets) < 2:
            return {"overlap_ratio": 1.0, "normalized_variance": 0.0}

        # 计算平均重叠度
        overlaps = []
        for i in range(len(keywords_sets)):
            for j in range(i + 1, len(keywords_sets)):
                intersection = len(keywords_sets[i] & keywords_sets[j])
                union = len(keywords_sets[i] | keywords_sets[j])
                if union > 0:
                    overlaps.append(intersection / union)

        avg_overlap = statistics.mean(overlaps) if overlaps else 1.0

        return {
            "keyword_overlap": avg_overlap,
            "normalized_variance": 1.0 - avg_overlap,
        }

    def _calculate_stylistic_variance(self, results: list[dict]) -> dict:
        """计算风格差异"""
        responses = [r["response"] for r in results]

        # 检查标点符号使用
        punct_counts = [r.count("。") + r.count("!") + r.count("?") for r in responses]
        avg_punct = statistics.mean(punct_counts) if punct_counts else 0

        # 检查句子平均长度
        sentence_lengths = []
        for r in responses:
            sentences = re.split(r"[。!?]", r)
            if sentences:
                sentence_lengths.append(statistics.mean([len(s) for s in sentences if s]))

        avg_sentence_length = statistics.mean(sentence_lengths) if sentence_lengths else 0

        return {
            "punctuation_usage": avg_punct,
            "avg_sentence_length": avg_sentence_length,
            "normalized_variance": 0.0,  # 需要更多数据才能计算
        }

    def _calculate_length_variance(self, results: list[dict]) -> dict:
        """计算长度差异"""
        lengths = [r["response_length"] for r in results]
        mean_length = statistics.mean(lengths) if lengths else 0
        std_length = statistics.stdev(lengths) if len(lengths) > 1 else 0
        cv = std_length / (mean_length + 1) if mean_length > 0 else 0

        return {
            "mean_length": mean_length,
            "std_length": std_length,
            "coefficient_of_variation": cv,
            "normalized_variance": min(cv, 1.0),
        }

    def _calculate_stability_score(self, metrics: dict) -> float:
        """计算综合稳定性分数"""
        variances = []
        weights = []

        dimension_weights = {
            "lexical": 0.3,
            "semantic": 0.4,
            "stylistic": 0.1,
            "length": 0.2,
        }

        for dim, weight in dimension_weights.items():
            if dim in metrics:
                normalized = metrics[dim].get("normalized_variance", 0)
                variances.append(normalized)
                weights.append(weight)

        if not variances:
            return 1.0

        # 加权平均，然后转换为稳定性分数
        weighted_variance = sum(v * w for v, w in zip(variances, weights, strict=False)) / sum(
            weights
        )
        stability_score = 1.0 - weighted_variance

        return max(0.0, min(1.0, stability_score))

    def _get_sensitivity_level(self, stability_score: float) -> str:
        """获取敏感度等级"""
        if stability_score >= 0.9:
            return "very_low"  # 非常稳定
        elif stability_score >= 0.75:
            return "low"  # 稳定
        elif stability_score >= 0.5:
            return "medium"  # 中等敏感
        elif stability_score >= 0.25:
            return "high"  # 高敏感
        else:
            return "very_high"  # 非常敏感

    def _generate_recommendations(self, analysis: dict) -> list[str]:
        """生成改进建议"""
        recommendations = []

        sensitivity = analysis.get("sensitivity_level", "medium")

        if sensitivity in ["high", "very_high"]:
            recommendations.append("模型对Prompt变化非常敏感，建议使用更明确的指令")
            recommendations.append("考虑使用Few-shot示例来稳定输出")

        if "lexical" in analysis.get("metrics", {}):
            lex_var = analysis["metrics"]["lexical"].get("normalized_variance", 0)
            if lex_var > 0.5:
                recommendations.append("输出长度差异较大，考虑在Prompt中指定输出长度要求")

        if "semantic" in analysis.get("metrics", {}):
            sem_overlap = analysis["metrics"]["semantic"].get("keyword_overlap", 0)
            if sem_overlap < 0.5:
                recommendations.append("不同Prompt变体产生差异较大的内容，需优化Prompt模板")

        if analysis.get("failed_count", 0) > 0:
            recommendations.append(
                f"有 {analysis['failed_count']} 个变体执行失败，请检查Prompt格式"
            )

        if not recommendations:
            recommendations.append("模型对Prompt变化反应良好，当前Prompt模板设计合理")

        return recommendations

    def _generate_summary(self, analysis: dict) -> str:
        """生成总结"""
        sensitivity = analysis.get("sensitivity_level", "medium")
        sensitivity_names = {
            "very_low": "非常稳定",
            "low": "稳定",
            "medium": "中等敏感",
            "high": "高敏感",
            "very_high": "非常敏感",
        }

        summary = f"Prompt敏感度{sensitivity_names.get(sensitivity, sensitivity)}，"
        summary += f"稳定性分数: {analysis['stability_score']:.2f}，"
        summary += f"共测试 {analysis['variant_count']} 个变体"

        return summary


@EvaluatorFactory.register("prompt_sensitivity")
class PromptSensitivityEvaluatorFactory(BaseEvaluator):
    """Prompt敏感度评估器工厂"""

    def __init__(self, client: BaseLLMClient | None = None):
        self.client = client

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        evaluator = PromptSensitivityEvaluator(client=self.client)
        return evaluator.evaluate(request)
