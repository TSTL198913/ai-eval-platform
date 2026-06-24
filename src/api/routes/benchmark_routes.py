"""
Benchmark 基准测试 API

提供标准数据集评测、排行榜、结果查询接口。
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.dependencies import (
    PermissionDependency,
)
from src.infra.benchmark.benchmark_manager import BenchmarkManager, BenchmarkResult
from src.infra.security import Permission

router = APIRouter(prefix="/api/v1/benchmarks", tags=["Benchmark"])

# 全局 BenchmarkManager 实例
_benchmark_manager = BenchmarkManager()


# Pydantic 模型
class BenchmarkRunRequest(BaseModel):
    dataset_id: str = Field(..., description="数据集ID")
    model_name: str = Field(..., description="模型名称")
    model_provider: str | None = Field(None, description="模型提供商")
    sample_count: int | None = Field(None, description="采样数量（可选）")


class BenchmarkResultResponse(BaseModel):
    benchmark_id: str
    dataset_id: str
    model_name: str
    total_questions: int
    correct_count: int
    accuracy: float
    avg_latency_ms: float
    total_tokens: int
    cost_usd: float
    timestamp: str


class DatasetResponse(BaseModel):
    dataset_id: str
    name: str
    category: str
    questions_count: int
    version: str
    description: str | None = None


class LeaderboardEntry(BaseModel):
    model_name: str
    dataset_id: str
    accuracy: float
    avg_latency_ms: float
    total_tokens: int
    cost_usd: float
    benchmark_id: str
    timestamp: str


class LeaderboardResponse(BaseModel):
    dataset_id: str
    entries: list[LeaderboardEntry]
    total: int


@router.get("/datasets", response_model=list[DatasetResponse])
async def list_datasets(
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_BENCHMARK)),
) -> list[DatasetResponse]:
    """
    列出标准数据集

    需要 VIEW_BENCHMARK 权限。

    返回可用的基准测试数据集列表，包括：
    - GSM8K（数学推理）
    - MMLU（多领域知识）
    - HumanEval（代码生成）
    """
    datasets = _benchmark_manager.list_datasets()

    return [
        DatasetResponse(
            dataset_id=ds["dataset_id"],
            name=ds["name"],
            category=ds["category"],
            questions_count=ds["questions_count"],
            version=ds["version"],
        )
        for ds in datasets
    ]


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: str,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_BENCHMARK)),
) -> DatasetResponse:
    """
    获取数据集详情

    需要 VIEW_BENCHMARK 权限。
    """
    dataset = _benchmark_manager.get_dataset(dataset_id)

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"数据集 '{dataset_id}' 不存在",
        )

    return DatasetResponse(
        dataset_id=dataset.dataset_id,
        name=dataset.name,
        category=dataset.category,
        questions_count=len(dataset.questions),
        version=dataset.version,
        description=dataset.description,
    )


@router.post("/run", response_model=BenchmarkResultResponse, status_code=status.HTTP_201_CREATED)
async def run_benchmark(
    request: BenchmarkRunRequest,
    current_user: dict = Depends(PermissionDependency(Permission.RUN_BENCHMARK)),
) -> BenchmarkResultResponse:
    """
    运行基准测试

    需要 RUN_BENCHMARK 权限。

    使用指定模型对数据集进行评测。
    """
    # 检查数据集是否存在
    dataset = _benchmark_manager.get_dataset(request.dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"数据集 '{request.dataset_id}' 不存在",
        )

    # 生成 benchmark_id
    benchmark_id = f"bench_{uuid.uuid4().hex[:8]}"

    # 执行基准测试（简化版本，实际应调用评估引擎）
    # 这里返回模拟结果，实际实现需要调用 domain/evaluators
    result = BenchmarkResult(
        benchmark_id=benchmark_id,
        dataset_id=request.dataset_id,
        model_name=request.model_name,
        total_questions=len(dataset.questions),
        correct_count=0,  # 实际应计算
        accuracy=0.0,  # 实际应计算
        avg_latency_ms=0.0,
        total_tokens=0,
        cost_usd=0.0,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # 存储结果
    _benchmark_manager.results[benchmark_id] = result

    return BenchmarkResultResponse(
        benchmark_id=result.benchmark_id,
        dataset_id=result.dataset_id,
        model_name=result.model_name,
        total_questions=result.total_questions,
        correct_count=result.correct_count,
        accuracy=result.accuracy,
        avg_latency_ms=result.avg_latency_ms,
        total_tokens=result.total_tokens,
        cost_usd=result.cost_usd,
        timestamp=result.timestamp,
    )


@router.get("/results/{benchmark_id}", response_model=BenchmarkResultResponse)
async def get_result(
    benchmark_id: str,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_BENCHMARK)),
) -> BenchmarkResultResponse:
    """
    获取评测结果

    需要 VIEW_BENCHMARK 权限。
    """
    result = _benchmark_manager.results.get(benchmark_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"评测结果 '{benchmark_id}' 不存在",
        )

    return BenchmarkResultResponse(
        benchmark_id=result.benchmark_id,
        dataset_id=result.dataset_id,
        model_name=result.model_name,
        total_questions=result.total_questions,
        correct_count=result.correct_count,
        accuracy=result.accuracy,
        avg_latency_ms=result.avg_latency_ms,
        total_tokens=result.total_tokens,
        cost_usd=result.cost_usd,
        timestamp=result.timestamp,
    )


@router.get("/leaderboard", response_model=list[LeaderboardResponse])
async def get_leaderboard(
    dataset_id: str | None = None,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_BENCHMARK)),
) -> list[LeaderboardResponse]:
    """
    获取排行榜

    需要 VIEW_BENCHMARK 权限。

    按准确率排序，展示各模型在不同数据集上的表现。
    """
    # 按数据集分组
    results_by_dataset: dict[str, list[BenchmarkResult]] = {}

    for result in _benchmark_manager.results.values():
        if dataset_id and result.dataset_id != dataset_id:
            continue

        if result.dataset_id not in results_by_dataset:
            results_by_dataset[result.dataset_id] = []
        results_by_dataset[result.dataset_id].append(result)

    # 构建排行榜
    leaderboards = []

    for ds_id, results in results_by_dataset.items():
        # 按准确率排序
        sorted_results = sorted(results, key=lambda r: r.accuracy, reverse=True)

        entries = [
            LeaderboardEntry(
                model_name=r.model_name,
                dataset_id=r.dataset_id,
                accuracy=r.accuracy,
                avg_latency_ms=r.avg_latency_ms,
                total_tokens=r.total_tokens,
                cost_usd=r.cost_usd,
                benchmark_id=r.benchmark_id,
                timestamp=r.timestamp,
            )
            for r in sorted_results
        ]

        leaderboards.append(
            LeaderboardResponse(
                dataset_id=ds_id,
                entries=entries,
                total=len(entries),
            )
        )

    return leaderboards


@router.get("/leaderboard/{dataset_id}", response_model=LeaderboardResponse)
async def get_dataset_leaderboard(
    dataset_id: str,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_BENCHMARK)),
) -> LeaderboardResponse:
    """
    获取指定数据集的排行榜

    需要 VIEW_BENCHMARK 权限。
    """
    results = [r for r in _benchmark_manager.results.values() if r.dataset_id == dataset_id]

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"数据集 '{dataset_id}' 暂无评测结果",
        )

    # 按准确率排序
    sorted_results = sorted(results, key=lambda r: r.accuracy, reverse=True)

    entries = [
        LeaderboardEntry(
            model_name=r.model_name,
            dataset_id=r.dataset_id,
            accuracy=r.accuracy,
            avg_latency_ms=r.avg_latency_ms,
            total_tokens=r.total_tokens,
            cost_usd=r.cost_usd,
            benchmark_id=r.benchmark_id,
            timestamp=r.timestamp,
        )
        for r in sorted_results
    ]

    return LeaderboardResponse(
        dataset_id=dataset_id,
        entries=entries,
        total=len(entries),
    )


@router.get("/history/{model_name}", response_model=list[BenchmarkResultResponse])
async def get_model_history(
    model_name: str,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_BENCHMARK)),
) -> list[BenchmarkResultResponse]:
    """
    获取模型的评测历史

    需要 VIEW_BENCHMARK 权限。
    """
    results = [r for r in _benchmark_manager.results.values() if r.model_name == model_name]

    return [
        BenchmarkResultResponse(
            benchmark_id=r.benchmark_id,
            dataset_id=r.dataset_id,
            model_name=r.model_name,
            total_questions=r.total_questions,
            correct_count=r.correct_count,
            accuracy=r.accuracy,
            avg_latency_ms=r.avg_latency_ms,
            total_tokens=r.total_tokens,
            cost_usd=r.cost_usd,
            timestamp=r.timestamp,
        )
        for r in results
    ]


@router.get("/compare")
async def compare_models(
    model_a: str,
    model_b: str,
    dataset_id: str,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_BENCHMARK)),
) -> dict[str, Any]:
    """
    对比两个模型在同一数据集上的表现

    需要 VIEW_BENCHMARK 权限。
    """
    result_a = None
    result_b = None

    for r in _benchmark_manager.results.values():
        if r.dataset_id == dataset_id:
            if r.model_name == model_a:
                result_a = r
            if r.model_name == model_b:
                result_b = r

    if not result_a:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模型 '{model_a}' 在数据集 '{dataset_id}' 上暂无评测结果",
        )

    if not result_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模型 '{model_b}' 在数据集 '{dataset_id}' 上暂无评测结果",
        )

    return {
        "dataset_id": dataset_id,
        "model_a": {
            "name": result_a.model_name,
            "accuracy": result_a.accuracy,
            "avg_latency_ms": result_a.avg_latency_ms,
            "total_tokens": result_a.total_tokens,
            "cost_usd": result_a.cost_usd,
        },
        "model_b": {
            "name": result_b.model_name,
            "accuracy": result_b.accuracy,
            "avg_latency_ms": result_b.avg_latency_ms,
            "total_tokens": result_b.total_tokens,
            "cost_usd": result_b.cost_usd,
        },
        "comparison": {
            "accuracy_diff": result_a.accuracy - result_b.accuracy,
            "latency_diff": result_a.avg_latency_ms - result_b.avg_latency_ms,
            "cost_diff": result_a.cost_usd - result_b.cost_usd,
            "winner": model_a if result_a.accuracy > result_b.accuracy else model_b,
        },
    }
