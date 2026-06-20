"""
Fine-tune 数据导出模块
从黄金数据集导出训练数据，支持多种格式
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ExportFormat(Enum):
    OPENAI = "openai"  # OpenAI Fine-tune 格式
    LLAMA_FACTORY = "llama"  # LLaMA-Factory 格式
    HUGGING_FACE = "hf"  # HuggingFace Dataset 格式
    RAW_JSONL = "jsonl"  # 原始 JSONL 格式


@dataclass
class TrainingSample:
    id: str
    prompt: str
    completion: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_openai_format(self) -> dict[str, str]:
        return {"prompt": self.prompt, "completion": self.completion}

    def to_llama_format(self) -> str:
        return f"USER: {self.prompt}\nASSISTANT: {self.completion}"

    def to_json(self) -> str:
        return json.dumps(
            {
                "id": self.id,
                "prompt": self.prompt,
                "completion": self.completion,
                "metadata": self.metadata,
            },
            ensure_ascii=False,
        )


@dataclass
class ExportStats:
    total_samples: int = 0
    by_dimension: dict[str, int] = field(default_factory=dict)
    avg_score: float = 0.0
    high_quality_samples: int = 0  # score >= 80
    low_quality_samples: int = 0  # score < 50
    export_time: str = ""


class FineTuneExporter:
    def __init__(self):
        self._stats = ExportStats()

    def export_from_golden_dataset(
        self,
        dataset_id: str,
        output_dir: str = "data/fine_tune",
        format: ExportFormat = ExportFormat.OPENAI,
        min_score: float = 0.0,
        include_metadata: bool = True,
    ) -> str:
        """从黄金数据集导出训练数据"""
        from src.domain.golden_dataset import golden_dataset_manager

        dataset = golden_dataset_manager.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset '{dataset_id}' not found")

        samples = [s for s in dataset.samples if s.scores]
        filtered = [s for s in samples if self._get_avg_score(s.scores) >= min_score]

        training_samples = self._convert_to_training_samples(
            filtered, dataset.name, include_metadata
        )

        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{dataset_id}_{timestamp}.{format.value}"
        filepath = os.path.join(output_dir, filename)

        self._write_file(filepath, training_samples, format)
        self._generate_stats(training_samples, filtered)

        # 生成元数据文件
        self._export_metadata(output_dir, dataset_id, filename)

        return filepath

    def export_from_db(
        self,
        output_dir: str = "data/fine_tune",
        format: ExportFormat = ExportFormat.OPENAI,
        limit: int = 1000,
        min_score: float = 50.0,
    ) -> str:
        """从数据库导出评估结果作为训练数据"""
        from src.infra.db.repository import EvaluationRepository

        repo = EvaluationRepository()
        records = repo.search(limit=limit)

        training_samples = []
        for record in records:
            response_data = record.get("response_data", {})
            total_score = response_data.get("total_score", 0)

            if total_score < min_score:
                continue

            user_input = record.get("case_id", "")
            actual_output = str(response_data.get("llm_judge_scores", ""))

            if not user_input or not actual_output:
                continue

            sample = TrainingSample(
                id=f"db_{record.get('id')}",
                prompt=self._build_prompt(user_input, actual_output),
                completion=self._build_completion(response_data),
                metadata={
                    "model_name": record.get("model_name"),
                    "adapter_name": record.get("adapter_name"),
                    "latency_ms": record.get("latency_ms"),
                    "source": "database",
                },
            )
            training_samples.append(sample)

        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"db_export_{timestamp}.{format.value}"
        filepath = os.path.join(output_dir, filename)

        self._write_file(filepath, training_samples, format)
        self._generate_stats(training_samples, training_samples)

        return filepath

    def _convert_to_training_samples(
        self, samples: list[Any], dataset_name: str, include_metadata: bool
    ) -> list[TrainingSample]:
        """将黄金样本转换为训练样本"""
        training_samples = []

        for sample in samples:
            avg_score = self._get_avg_score(sample.scores)
            dimensions_str = ", ".join(sample.dimensions)

            prompt = self._build_evaluation_prompt(
                user_input=sample.user_input,
                actual_output=sample.actual_output,
                expected_output=sample.expected_output or "",
                dimensions=dimensions_str,
                dataset_name=dataset_name,
            )

            completion = self._build_evaluation_completion(
                scores=sample.scores, total_score=avg_score, dimensions=sample.dimensions
            )

            metadata = (
                {
                    "dataset": dataset_name,
                    "sample_id": sample.id,
                    "avg_score": avg_score,
                    "is_corrected": sample.human_corrected,
                }
                if include_metadata
                else {}
            )

            training_samples.append(
                TrainingSample(
                    id=sample.id, prompt=prompt, completion=completion, metadata=metadata
                )
            )

        return training_samples

    def _build_evaluation_prompt(
        self,
        user_input: str,
        actual_output: str,
        expected_output: str,
        dimensions: str,
        dataset_name: str,
    ) -> str:
        """构建评估提示词"""
        expected_section = f"\n期望回答应包含: {expected_output}" if expected_output else ""
        return f"""你是一个专业的 AI 评测专家。请评估以下回答在 [{dimensions}] 维度的表现。

用户问题: {user_input}
AI回答: {actual_output}{expected_section}

请给出评分和理由，格式如下:
总分: <分数>
各维度评分: <维度>: <分数> (<理由>)
"""

    def _build_evaluation_completion(
        self, scores: dict[str, float], total_score: float, dimensions: list[str]
    ) -> str:
        """构建评估回复"""
        dim_scores = []
        for dim in dimensions:
            score = scores.get(dim, 0)
            dim_scores.append(f"{dim}: {score}分")

        return f"""总分: {total_score:.0f}
各维度评分: {", ".join(dim_scores)}
"""

    def _build_prompt(self, user_input: str, actual_output: str) -> str:
        return f"评估以下回答:\n用户输入: {user_input}\n回答: {actual_output}"

    def _build_completion(self, response_data: dict[str, Any]) -> str:
        total = response_data.get("total_score", 0)
        scores = response_data.get("llm_judge_scores", {})
        parts = [f"总分: {total:.0f}"]
        for dim, data in scores.items():
            if isinstance(data, dict):
                parts.append(f"{dim}: {data.get('score', 0)}分")
        return "\n".join(parts)

    def _get_avg_score(self, scores: dict[str, float]) -> float:
        if not scores:
            return 0.0
        return sum(scores.values()) / len(scores)

    def _write_file(self, filepath: str, samples: list[TrainingSample], format: ExportFormat):
        """按指定格式写入文件"""
        with open(filepath, "w", encoding="utf-8") as f:
            for sample in samples:
                if format == ExportFormat.OPENAI:
                    f.write(json.dumps(sample.to_openai_format(), ensure_ascii=False) + "\n")
                elif format == ExportFormat.LLAMA_FACTORY:
                    f.write(sample.to_llama_format() + "\n")
                elif format == ExportFormat.RAW_JSONL:
                    f.write(sample.to_json() + "\n")

    def _generate_stats(self, training_samples: list[TrainingSample], original_samples: list):
        """生成导出统计"""
        self._stats = ExportStats()
        self._stats.total_samples = len(training_samples)
        self._stats.export_time = datetime.now().isoformat()

        scores = [
            s.metadata.get("avg_score", 0) for s in training_samples if s.metadata.get("avg_score")
        ]
        if scores:
            self._stats.avg_score = sum(scores) / len(scores)
            self._stats.high_quality_samples = len([s for s in scores if s >= 80])
            self._stats.low_quality_samples = len([s for s in scores if s < 50])

    def _export_metadata(self, output_dir: str, dataset_id: str, filename: str):
        """导出元数据文件"""
        metadata_file = os.path.join(output_dir, f"{dataset_id}_metadata.json")
        metadata = {
            "dataset_id": dataset_id,
            "export_file": filename,
            "export_time": self._stats.export_time,
            "total_samples": self._stats.total_samples,
            "stats": {
                "avg_score": self._stats.avg_score,
                "high_quality_samples": self._stats.high_quality_samples,
                "low_quality_samples": self._stats.low_quality_samples,
            },
        }
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_samples": self._stats.total_samples,
            "avg_score": round(self._stats.avg_score, 2),
            "high_quality_samples": self._stats.high_quality_samples,
            "low_quality_samples": self._stats.low_quality_samples,
            "export_time": self._stats.export_time,
        }

    def generate_quality_report(self, samples: list[TrainingSample]) -> dict[str, Any]:
        """生成训练数据质量报告"""
        if not samples:
            return {"error": "No samples to analyze"}

        scores = [s.metadata.get("avg_score", 0) for s in samples if s.metadata.get("avg_score")]

        score_distribution = {
            "excellent": len([s for s in scores if s >= 90]),  # 90-100
            "good": len([s for s in scores if 70 <= s < 90]),  # 70-89
            "fair": len([s for s in scores if 50 <= s < 70]),  # 50-69
            "poor": len([s for s in scores if s < 50]),  # <50
        }

        return {
            "total_samples": len(samples),
            "scored_samples": len(scores),
            "avg_score": round(sum(scores) / max(len(scores), 1), 2),
            "score_distribution": score_distribution,
            "quality_grade": self._calculate_quality_grade(score_distribution),
            "recommendations": self._generate_recommendations(score_distribution),
        }

    def _calculate_quality_grade(self, distribution: dict[str, int]) -> str:
        total = sum(distribution.values())
        if total == 0:
            return "N/A"

        excellent_ratio = distribution["excellent"] / total
        good_ratio = distribution["good"] / total
        poor_ratio = distribution["poor"] / total

        if excellent_ratio >= 0.3 and poor_ratio < 0.1:
            return "A (优秀)"
        elif good_ratio >= 0.5 and poor_ratio < 0.2:
            return "B (良好)"
        elif poor_ratio < 0.3:
            return "C (一般)"
        else:
            return "D (需改进)"

    def _generate_recommendations(self, distribution: dict[str, int]) -> list[str]:
        recommendations = []
        total = sum(distribution.values())

        if distribution["excellent"] < total * 0.2:
            recommendations.append("建议增加高质量样本(90+)到30%以上")

        if distribution["poor"] > total * 0.1:
            recommendations.append("建议过滤低质量样本(<50)，避免模型学习错误模式")

        if distribution["fair"] > total * 0.4:
            recommendations.append("建议人工审核中等质量样本，提升整体数据质量")

        if not recommendations:
            recommendations.append("数据质量良好，可用于Fine-tune训练")

        return recommendations


fine_tune_exporter = FineTuneExporter()
