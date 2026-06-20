"""
统计分析路由模块
包含A/B测试、置信区间、模型比较、功效分析等端点
"""

import logging

from fastapi import APIRouter

from src.api.common import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/statistics", tags=["统计分析"])


@router.post("/ab-test")
async def run_ab_test(data: dict):
    """运行 A/B 测试"""
    try:
        from src.domain.statistical_analysis import statistical_analyzer

        scores_a = data.get("scores_a", [])
        scores_b = data.get("scores_b", [])
        model_a_name = data.get("model_a_name", "Model A")
        model_b_name = data.get("model_b_name", "Model B")
        significance_level = data.get("significance_level", 0.05)
        test_type = data.get("test_type", "auto")

        if len(scores_a) < 3 or len(scores_b) < 3:
            return error_response(400, "每组至少需要3个样本")

        result = statistical_analyzer.run_ab_test(
            scores_a=scores_a,
            scores_b=scores_b,
            model_a_name=model_a_name,
            model_b_name=model_b_name,
            significance_level=significance_level,
            test_type=test_type,
        )

        return success_response(result.to_dict())
    except ValueError as e:
        return error_response(400, str(e))
    except Exception as e:
        logger.error(f"Failed to run AB test: {e}")
        return error_response(500, "A/B测试失败")


@router.post("/confidence-interval")
async def calculate_confidence_interval(data: dict):
    """计算置信区间"""
    try:
        from src.domain.statistical_analysis import statistical_analyzer

        scores = data.get("scores", [])
        confidence = data.get("confidence", 0.95)
        method = data.get("method", "t-distribution")

        if len(scores) < 2:
            return error_response(400, "至少需要2个样本")

        ci = statistical_analyzer.calculate_confidence_interval(
            scores=scores, confidence=confidence, method=method
        )

        return success_response(ci.to_dict())
    except ValueError as e:
        return error_response(400, str(e))
    except Exception as e:
        logger.error(f"Failed to calculate CI: {e}")
        return error_response(500, "置信区间计算失败")


@router.post("/compare-models")
async def compare_models(data: dict):
    """多模型比较"""
    try:
        from src.domain.statistical_analysis import statistical_analyzer

        model_scores = data.get("model_scores", {})
        baseline_model = data.get("baseline_model")
        significance_level = data.get("significance_level", 0.05)

        if not model_scores:
            return error_response(400, "model_scores 不能为空")

        result = statistical_analyzer.compare_multiple_models(
            model_scores=model_scores,
            baseline_model=baseline_model,
            significance_level=significance_level,
        )

        return success_response(result)
    except Exception as e:
        logger.error(f"Failed to compare models: {e}")
        return error_response(500, "模型比较失败")


@router.get("/power-analysis")
async def get_power_analysis(
    effect_size: float = 0.5, significance_level: float = 0.05, power: float = 0.8
):
    """统计功效分析 - 计算所需样本量"""
    try:
        from src.domain.statistical_analysis import statistical_analyzer

        result = statistical_analyzer.power_analysis(
            effect_size=effect_size, significance_level=significance_level, power=power
        )

        return success_response(result)
    except Exception as e:
        logger.error(f"Failed to calculate power: {e}")
        return error_response(500, "功效分析失败")
