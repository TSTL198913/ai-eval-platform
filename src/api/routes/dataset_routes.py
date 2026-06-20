"""
数据集路由模块
包含数据集列表查询、数据集详情等端点
"""

import logging

from fastapi import APIRouter, Response, status

from src.api.common import error_response, success_response, validate_dataset_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/datasets", tags=["数据集"])


@router.get("")
async def get_datasets():
    """获取可用的评测数据集"""
    try:
        from src.domain.benchmarks.standard_datasets import DatasetManager

        datasets = DatasetManager.list_datasets()
        stats = DatasetManager.get_all_stats()
        return success_response(
            {
                "datasets": datasets,
                "stats": stats,
            }
        )
    except Exception as e:
        logger.error(f"Failed to get datasets: {e}")
        return error_response(500, "获取数据集列表失败")


@router.get("/{dataset_name}")
async def get_dataset_details(dataset_name: str, response: Response):
    """获取数据集详情"""
    # 输入验证：防止特殊字符攻击
    if not validate_dataset_name(dataset_name):
        response.status_code = status.HTTP_404_NOT_FOUND
        return error_response(404, "Invalid dataset name format")

    try:
        from src.domain.benchmarks.standard_datasets import BenchmarkDataset, DatasetManager

        ds_type = BenchmarkDataset(dataset_name)
        ds = DatasetManager.get_dataset(ds_type)
        data = ds.load()
        stats = ds.get_stats()

        return success_response(
            {
                "name": dataset_name,
                "stats": stats,
                "sample_count": len(data),
                "sample": data[0] if data else None,
            }
        )
    except ValueError:
        response.status_code = status.HTTP_404_NOT_FOUND
        return error_response(404, f"Dataset '{dataset_name}' not found")
    except Exception as e:
        logger.error(f"Failed to get dataset: {e}")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return error_response(500, "获取数据集失败")
