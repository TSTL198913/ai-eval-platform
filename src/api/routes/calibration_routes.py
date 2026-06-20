"""
校准路由模块
包含黄金标准数据集管理、样本标注、修正等端点
"""

import logging

from fastapi import APIRouter

from src.api.common import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/calibration", tags=["校准"])


@router.get("/datasets")
async def get_golden_datasets():
    """获取黄金标准数据集列表"""
    try:
        from src.domain.golden_dataset import golden_dataset_manager

        datasets = golden_dataset_manager.list_datasets()
        return success_response({"datasets": datasets})
    except Exception as e:
        logger.error(f"Failed to get golden datasets: {e}")
        return error_response(500, "获取黄金数据集失败")


@router.post("/datasets")
async def create_golden_dataset(data: dict):
    """创建黄金标准数据集"""
    try:
        from src.domain.golden_dataset import golden_dataset_manager

        dataset_id = data.get("dataset_id")
        description = data.get("description", "")
        dimensions = data.get("dimensions", ["correctness"])
        if not dataset_id:
            return error_response(400, "dataset_id 必填")
        golden_dataset_manager.create_dataset(dataset_id, description, dimensions)
        return success_response({"dataset_id": dataset_id, "message": "数据集创建成功"})
    except Exception as e:
        logger.error(f"Failed to create golden dataset: {e}")
        return error_response(500, "创建黄金数据集失败")


@router.post("/datasets/{dataset_id}/samples")
async def add_golden_sample(dataset_id: str, data: dict):
    """添加黄金标注样本"""
    try:
        from src.domain.golden_dataset import golden_dataset_manager

        sample = data.get("sample")
        if not sample:
            return error_response(400, "sample 必填")
        golden_dataset_manager.add_sample(dataset_id, sample)
        return success_response({"message": "样本添加成功"})
    except Exception as e:
        logger.error(f"Failed to add golden sample: {e}")
        return error_response(500, "添加样本失败")


@router.post("/datasets/{dataset_id}/samples/{sample_id}/correct")
async def correct_golden_sample(dataset_id: str, sample_id: str, data: dict):
    """修正评估结果"""
    try:
        from src.domain.golden_dataset import golden_dataset_manager

        corrected_scores = data.get("corrected_scores")
        corrected_reason = data.get("corrected_reason", "")
        golden_dataset_manager.correct_sample(
            dataset_id, sample_id, corrected_scores, corrected_reason
        )
        return success_response({"message": "修正成功"})
    except Exception as e:
        logger.error(f"Failed to correct golden sample: {e}")
        return error_response(500, "修正失败")


@router.get("/datasets/{dataset_id}/few-shot")
async def get_few_shot_examples(dataset_id: str, limit: int = 3, dimensions: str = None):
    """获取 Few-shot 示例"""
    try:
        from src.domain.golden_dataset import golden_dataset_manager

        dim_list = dimensions.split(",") if dimensions else None
        examples = golden_dataset_manager.get_few_shot_examples(
            dataset_id, limit=limit, dimensions=dim_list
        )
        return success_response({"examples": examples})
    except Exception as e:
        logger.error(f"Failed to get few-shot examples: {e}")
        return error_response(500, "获取 Few-shot 示例失败")
