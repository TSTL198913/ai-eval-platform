"""
组合评估器 - Chain Multiple Evaluators
实现链式调用多个评估器，计算加权总分
"""

from dataclasses import dataclass

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.models.base import BaseLLMClient
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus


@dataclass
class EvaluatorChainConfig:
    """评估器链配置"""

    evaluator_type: str
    weight: float = 1.0
    enabled: bool = True
    custom_weights: dict[str, float] | None = None  # 自定义子维度权重


class CompositeEvaluator(BaseEvaluator):
    """组合评估器

    按顺序调用多个评估器，计算加权总分。
    支持：
    - 评估器链配置
    - 自定义权重
    - 并行/串行执行
    - 结果聚合与归因
    """

    def __init__(
        self,
        evaluators: list[EvaluatorChainConfig] | None = None,
        client: BaseLLMClient | None = None,
        execution_mode: str = "sequential",  # sequential, parallel
        aggregate_method: str = "weighted_sum",  # weighted_sum, max, min, average
    ):
        super().__init__(client=client)
        self.evaluators = evaluators or self._get_default_chain()
        self.execution_mode = execution_mode
        self.aggregate_method = aggregate_method

    def _get_default_chain(self) -> list[EvaluatorChainConfig]:
        """获取默认评估器链"""
        return [
            EvaluatorChainConfig("security", weight=0.3),
            EvaluatorChainConfig("llm_as_judge", weight=0.5),
            EvaluatorChainConfig("factuality", weight=0.2),
        ]

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        if error := self.validate_input(request):
            return error

        results = []
        total_weight = 0.0
        weighted_score_sum = 0.0
        all_data = {}
        # 🧠 2026 架构升级：收集子评估器状态，用于聚合最终状态
        all_statuses = []
        dimensions_evaluated = []
        dimensions_skipped = []
        skip_reasons = {}

        for config in self.evaluators:
            if not config.enabled:
                continue

            try:
                # 获取评估器实例
                evaluator = EvaluatorFactory.get(config.evaluator_type, client=self.client)

                # 执行评估
                result = evaluator.safe_evaluate(request)

                # 收集状态
                all_statuses.append(result.evaluation_status)

                # 收集结果
                results.append(
                    {
                        "evaluator": config.evaluator_type,
                        "weight": config.weight,
                        "score": result.score,
                        "is_valid": result.is_valid,
                        "error": result.error,
                        "evaluation_status": result.evaluation_status.value,
                    }
                )

                if result.is_valid and result.score is not None:
                    weighted_score_sum += result.score * config.weight
                    total_weight += config.weight

                    # 合并数据
                    if result.data:
                        all_data[config.evaluator_type] = result.data

                    # 合并维度信息
                    if hasattr(result, 'data') and result.data:
                        if "dimensions_evaluated" in result.data:
                            dims = result.data["dimensions_evaluated"]
                            if isinstance(dims, list):
                                dimensions_evaluated.extend([f"{config.evaluator_type}:{d}" for d in dims])
                        if "dimensions_skipped" in result.data:
                            dims = result.data["dimensions_skipped"]
                            if isinstance(dims, list):
                                dimensions_skipped.extend([f"{config.evaluator_type}:{d}" for d in dims])
                        if "skip_reasons" in result.data:
                            reasons = result.data["skip_reasons"]
                            if isinstance(reasons, dict):
                                for k, v in reasons.items():
                                    if v:
                                        skip_reasons[f"{config.evaluator_type}:{k}"] = v

            except Exception as e:
                all_statuses.append(EvaluatorStatus.ERROR)
                results.append(
                    {
                        "evaluator": config.evaluator_type,
                        "weight": config.weight,
                        "score": 0.0,
                        "is_valid": False,
                        "error": str(e),
                        "evaluation_status": "error",
                    }
                )

        # 计算聚合分数
        if total_weight > 0:
            final_score = weighted_score_sum / total_weight
        else:
            final_score = 0.0

        # 🧠 2026 架构升级：聚合子评估器状态
        # 状态聚合规则：
        # - 有 ERROR → ERROR
        # - 有 CANNOT_EVALUATE → CANNOT_EVALUATE
        # - 有 PARTIAL → PARTIAL
        # - 全部 SUCCESS → SUCCESS
        final_status = self._aggregate_statuses(all_statuses)

        # 收集改进建议
        improvement_suggestions = []
        for data in all_data.values():
            if isinstance(data, dict) and "improvement_suggestions" in data:
                improvement_suggestions.extend(data["improvement_suggestions"])

        # 检查是否有冲突
        conflict_detected = any(r.get("score", 0) < 0.3 for r in results if r["is_valid"])

        # 根据最终状态选择返回方法
        if final_status == EvaluatorStatus.SUCCESS:
            return self.create_success_response(
                text=f"组合评估完成，调用了 {len([r for r in results if r['is_valid']])} 个评估器",
                score=final_score,
                data={
                    "composite_score": final_score,
                    "evaluator_results": results,
                    "total_evaluators": len(self.evaluators),
                    "successful_evaluators": len([r for r in results if r["is_valid"]]),
                    "conflict_detected": conflict_detected,
                    "improvement_suggestions": list(set(improvement_suggestions)),
                    "execution_mode": self.execution_mode,
                    "aggregate_method": self.aggregate_method,
                    "detailed_scores": all_data,
                    "dimensions_evaluated": dimensions_evaluated,
                    "dimensions_skipped": dimensions_skipped,
                    "skip_reasons": skip_reasons,
                },
            )
        elif final_status == EvaluatorStatus.PARTIAL:
            return self.create_partial_response(
                text=f"组合评估完成（部分维度），调用了 {len([r for r in results if r['is_valid']])} 个评估器",
                score=final_score,
                dimensions_evaluated=dimensions_evaluated,
                dimensions_skipped=dimensions_skipped,
                skip_reasons=skip_reasons,
                data={
                    "composite_score": final_score,
                    "evaluator_results": results,
                    "total_evaluators": len(self.evaluators),
                    "successful_evaluators": len([r for r in results if r["is_valid"]]),
                    "conflict_detected": conflict_detected,
                    "improvement_suggestions": list(set(improvement_suggestions)),
                    "execution_mode": self.execution_mode,
                    "aggregate_method": self.aggregate_method,
                    "detailed_scores": all_data,
                },
            )
        elif final_status == EvaluatorStatus.CANNOT_EVALUATE:
            return self.create_cannot_evaluate_response(
                reason="组合评估无法完成：部分子评估器无法评估",
                dimensions_skipped=dimensions_skipped,
                metadata={
                    "evaluator_results": results,
                    "failed_evaluators": [r["evaluator"] for r in results if r["evaluation_status"] == "cannot_evaluate"],
                },
            )
        else:
            return self.create_error_response(
                error_message="组合评估失败：部分子评估器发生错误",
                error_code="COMPOSITE_ERROR",
                metadata={
                    "evaluator_results": results,
                    "error_evaluators": [r["evaluator"] for r in results if r["evaluation_status"] == "error"],
                },
            )

    def _aggregate_statuses(self, statuses: list[EvaluatorStatus]) -> EvaluatorStatus:
        """聚合子评估器状态

        状态聚合规则（优先级从高到低）：
        1. 有 ERROR → ERROR
        2. 有 CANNOT_EVALUATE → CANNOT_EVALUATE
        3. 有 PARTIAL → PARTIAL
        4. 全部 SUCCESS → SUCCESS
        """
        if not statuses:
            return EvaluatorStatus.SUCCESS

        if EvaluatorStatus.ERROR in statuses:
            return EvaluatorStatus.ERROR
        if EvaluatorStatus.CANNOT_EVALUATE in statuses:
            return EvaluatorStatus.CANNOT_EVALUATE
        if EvaluatorStatus.PARTIAL in statuses:
            return EvaluatorStatus.PARTIAL
        return EvaluatorStatus.SUCCESS

    def evaluate_with_radar(self, request: EvaluationSchema) -> DomainResponse:
        """评估并生成雷达图数据"""
        result = self.evaluate(request)

        # 生成雷达图数据结构
        radar_data = {
            "dimensions": [],
            "scores": [],
            "labels": [],
        }

        for _data_key, data_value in result.data.get("detailed_scores", {}).items():
            if isinstance(data_value, dict):
                # 尝试提取多维度分数
                if "llm_judge_scores" in data_value:
                    for dim, score_info in data_value["llm_judge_scores"].items():
                        if isinstance(score_info, dict):
                            radar_data["dimensions"].append(dim)
                            radar_data["scores"].append(score_info.get("score", 0) / 100.0)
                            radar_data["labels"].append(score_info.get("level", "unknown"))

        # 添加评估器级别的分数
        for eval_result in result.data.get("evaluator_results", []):
            if eval_result["is_valid"]:
                radar_data["dimensions"].append(f"evaluator:{eval_result['evaluator']}")
                radar_data["scores"].append(eval_result["score"])
                radar_data["labels"].append("good" if eval_result["score"] > 0.7 else "poor")

        result.data["radar_chart"] = radar_data
        return result


@EvaluatorFactory.register("composite")
class CompositeEvaluatorFactory(BaseEvaluator):
    """组合评估器工厂"""

    def __init__(self, client: BaseLLMClient | None = None):
        self.client = client

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        # 获取评估器链配置
        chain_configs = self.get_payload_data(request, "evaluator_chain", None)

        evaluators = None
        if chain_configs:
            evaluators = [
                EvaluatorChainConfig(
                    evaluator_type=c.get("type", c.get("evaluator_type", "")),
                    weight=c.get("weight", 1.0),
                    enabled=c.get("enabled", True),
                )
                for c in chain_configs
            ]

        composite = CompositeEvaluator(
            evaluators=evaluators,
            client=self.client,
            execution_mode=self.get_payload_data(request, "execution_mode", "sequential"),
        )

        return composite.evaluate(request)


# 预设的评估器组合
PRESET_CHAINS = {
    # 代码质量评估组合
    "code_quality": [
        EvaluatorChainConfig("code", weight=0.4),
        EvaluatorChainConfig("llm_as_judge", weight=0.3),
        EvaluatorChainConfig("security", weight=0.2),
        EvaluatorChainConfig("robustness", weight=0.1),
    ],
    # 对话质量评估组合
    "conversation_quality": [
        EvaluatorChainConfig("llm_as_judge", weight=0.5),
        EvaluatorChainConfig("safety", weight=0.25),
        EvaluatorChainConfig("factuality", weight=0.15),
        EvaluatorChainConfig("robustness", weight=0.1),
    ],
    # 安全评估组合
    "security_audit": [
        EvaluatorChainConfig("security", weight=0.5),
        EvaluatorChainConfig("llm_as_judge", weight=0.3),
        EvaluatorChainConfig("factuality", weight=0.2),
    ],
    # 快速评估组合
    "quick": [
        EvaluatorChainConfig("llm_as_judge", weight=0.6),
        EvaluatorChainConfig("safety", weight=0.4),
    ],
}


def get_preset_chain(preset_name: str) -> list[EvaluatorChainConfig]:
    """获取预设评估器链"""
    return PRESET_CHAINS.get(preset_name, PRESET_CHAINS["quick"])
