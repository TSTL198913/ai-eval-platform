"""
行业标准评测数据集集成

支持:
- MT-Bench: 多轮对话评测基准
- GAIA: AI基础能力评测基准
- MMLU: 大规模多任务语言理解
- HumanEval: 代码生成评测
"""

import json
import os
from abc import ABC, abstractmethod
from enum import Enum


class BenchmarkDataset(Enum):
    MT_BENCH = "mt_bench"
    GAIA = "gaia"
    MMLU = "mmlu"
    HUMANEVAL = "humaneval"


class BaseDataset(ABC):
    """数据集基类"""

    @abstractmethod
    def load(self) -> list[dict]:
        pass

    @abstractmethod
    def get_sample(self, index: int) -> dict:
        pass

    @abstractmethod
    def get_stats(self) -> dict:
        pass


class MTBenchDataset(BaseDataset):
    """MT-Bench多轮对话评测数据集"""

    def __init__(self, data_dir: str = "data/datasets"):
        self.data_dir = data_dir
        self.data: list[dict] = []

    def load(self) -> list[dict]:
        file_path = os.path.join(self.data_dir, "mt_bench.json")
        if os.path.exists(file_path):
            with open(file_path, encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = self._generate_sample_data()
        return self.data

    def _generate_sample_data(self) -> list[dict]:
        return [
            {
                "id": "mt_bench_001",
                "category": "knowledge",
                "turns": [
                    {"role": "user", "content": "什么是人工智能？"},
                    {"role": "assistant", "content": "人工智能是模拟人类智能的计算机系统。"},
                    {"role": "user", "content": "它有哪些应用领域？"},
                    {"role": "assistant", "content": "包括医疗、金融、教育、自动驾驶等领域。"},
                ],
                "reference_answer": "人工智能在医疗领域可用于疾病诊断，金融领域可用于风险评估，教育领域可用于个性化学习，自动驾驶领域可用于车辆控制。",
            },
            {
                "id": "mt_bench_002",
                "category": "reasoning",
                "turns": [
                    {"role": "user", "content": "一个房间里有3个人，每个人都有2只手，一共有多少只手？"},
                    {"role": "assistant", "content": "3个人 × 2只手 = 6只手。"},
                    {"role": "user", "content": "如果每个人又多了1只手，一共有多少只手？"},
                    {"role": "assistant", "content": "3个人 × 3只手 = 9只手。"},
                ],
                "reference_answer": "9只手",
            },
            {
                "id": "mt_bench_003",
                "category": "coding",
                "turns": [
                    {"role": "user", "content": "写一个Python函数计算斐波那契数列。"},
                    {"role": "assistant", "content": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)"},
                    {"role": "user", "content": "优化这个函数使其支持大数值计算。"},
                    {"role": "assistant", "content": "使用动态规划或矩阵快速幂优化。"},
                ],
                "reference_answer": "使用动态规划或矩阵快速幂可以优化斐波那契数列计算。",
            },
        ]

    def get_sample(self, index: int) -> dict:
        return self.data[index]

    def get_stats(self) -> dict:
        categories = {}
        for item in self.data:
            cat = item.get("category", "other")
            categories[cat] = categories.get(cat, 0) + 1
        return {
            "total_samples": len(self.data),
            "categories": categories,
            "avg_turns": sum(len(item.get("turns", [])) for item in self.data) / max(len(self.data), 1),
        }


class GAIADataset(BaseDataset):
    """GAIA基础能力评测数据集"""

    def __init__(self, data_dir: str = "data/datasets"):
        self.data_dir = data_dir
        self.data: list[dict] = []

    def load(self) -> list[dict]:
        file_path = os.path.join(self.data_dir, "gaia.json")
        if os.path.exists(file_path):
            with open(file_path, encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = self._generate_sample_data()
        return self.data

    def _generate_sample_data(self) -> list[dict]:
        return [
            {
                "id": "gaia_001",
                "level": "easy",
                "question": "地球是圆的还是平的？",
                "reference_answer": "地球是圆的",
                "knowledge_domain": "geography",
            },
            {
                "id": "gaia_002",
                "level": "medium",
                "question": "如果今天是星期一，3天后是星期几？",
                "reference_answer": "星期四",
                "knowledge_domain": "logic",
            },
            {
                "id": "gaia_003",
                "level": "hard",
                "question": "小明有5个苹果，吃掉2个，又买了3个，最后送给小红1个，小明现在有几个苹果？",
                "reference_answer": "5个",
                "knowledge_domain": "math",
            },
        ]

    def get_sample(self, index: int) -> dict:
        return self.data[index]

    def get_stats(self) -> dict:
        levels = {}
        for item in self.data:
            level = item.get("level", "unknown")
            levels[level] = levels.get(level, 0) + 1
        return {
            "total_samples": len(self.data),
            "levels": levels,
        }


class MMLUDataset(BaseDataset):
    """MMLU大规模多任务语言理解数据集"""

    def __init__(self, data_dir: str = "data/datasets"):
        self.data_dir = data_dir
        self.data: list[dict] = []

    def load(self) -> list[dict]:
        file_path = os.path.join(self.data_dir, "mmlu.json")
        if os.path.exists(file_path):
            with open(file_path, encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = self._generate_sample_data()
        return self.data

    def _generate_sample_data(self) -> list[dict]:
        return [
            {
                "id": "mmlu_001",
                "subject": "computer_science",
                "question": "Python中，以下哪个是不可变类型？",
                "options": ["list", "dict", "tuple", "set"],
                "answer": "tuple",
                "difficulty": "easy",
            },
            {
                "id": "mmlu_002",
                "subject": "biology",
                "question": "DNA的全称是什么？",
                "options": ["Deoxyribonucleic Acid", "Ribonucleic Acid", "Amino Acid", "Fatty Acid"],
                "answer": "Deoxyribonucleic Acid",
                "difficulty": "medium",
            },
            {
                "id": "mmlu_003",
                "subject": "physics",
                "question": "光速约为多少？",
                "options": ["300000 km/s", "30000 km/s", "3000 km/s", "300 km/s"],
                "answer": "300000 km/s",
                "difficulty": "easy",
            },
        ]

    def get_sample(self, index: int) -> dict:
        return self.data[index]

    def get_stats(self) -> dict:
        subjects = {}
        for item in self.data:
            subject = item.get("subject", "other")
            subjects[subject] = subjects.get(subject, 0) + 1
        return {
            "total_samples": len(self.data),
            "subjects": subjects,
        }


class HumanEvalDataset(BaseDataset):
    """HumanEval代码生成评测数据集"""

    def __init__(self, data_dir: str = "data/datasets"):
        self.data_dir = data_dir
        self.data: list[dict] = []

    def load(self) -> list[dict]:
        # 优先尝试从真实数据集加载
        try:
            from src.domain.benchmarks.dataset_loader import DatasetLoader
            real_samples = DatasetLoader.load_humaneval()
            if real_samples:
                # 转换为标准格式
                self.data = []
                for s in real_samples:
                    self.data.append({
                        "id": s.get("task_id", f"humaneval_{len(self.data)}"),
                        "task_id": s.get("task_id"),
                        "prompt": s.get("prompt", ""),
                        "canonical_solution": s.get("canonical_solution", ""),
                        "test": s.get("test", ""),
                        "entry_point": s.get("entry_point", ""),
                        "reference": s.get("reference", ""),
                    })
                return self.data
        except Exception:
            pass

        file_path = os.path.join(self.data_dir, "humaneval.json")
        if os.path.exists(file_path):
            with open(file_path, encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = self._generate_sample_data()
        return self.data

    def _generate_sample_data(self) -> list[dict]:
        return [
            {
                "id": "humaneval_001",
                "task_id": "HumanEval/0",
                "prompt": "def factorial(n):\n    \"\"\"计算n的阶乘\"\"\"",
                "canonical_solution": "def factorial(n):\n    if n == 0:\n        return 1\n    return n * factorial(n-1)",
                "test": "def test_factorial():\n    assert factorial(0) == 1\n    assert factorial(5) == 120\n    assert factorial(10) == 3628800",
            },
            {
                "id": "humaneval_002",
                "task_id": "HumanEval/1",
                "prompt": "def reverse_string(s):\n    \"\"\"反转字符串\"\"\"",
                "canonical_solution": "def reverse_string(s):\n    return s[::-1]",
                "test": "def test_reverse_string():\n    assert reverse_string('hello') == 'olleh'\n    assert reverse_string('world') == 'dlrow'",
            },
        ]

    def get_sample(self, index: int) -> dict:
        return self.data[index]

    def get_stats(self) -> dict:
        return {
            "total_samples": len(self.data),
        }


class DatasetManager:
    """数据集管理器"""

    _datasets: dict[BenchmarkDataset, BaseDataset] = {}

    @classmethod
    def register(cls, dataset_type: BenchmarkDataset, dataset: BaseDataset):
        cls._datasets[dataset_type] = dataset

    @classmethod
    def get_dataset(cls, dataset_type: BenchmarkDataset) -> BaseDataset:
        if dataset_type not in cls._datasets:
            cls._init_default(dataset_type)
        return cls._datasets[dataset_type]

    @classmethod
    def _init_default(cls, dataset_type: BenchmarkDataset):
        if dataset_type == BenchmarkDataset.MT_BENCH:
            cls._datasets[dataset_type] = MTBenchDataset()
        elif dataset_type == BenchmarkDataset.GAIA:
            cls._datasets[dataset_type] = GAIADataset()
        elif dataset_type == BenchmarkDataset.MMLU:
            cls._datasets[dataset_type] = MMLUDataset()
        elif dataset_type == BenchmarkDataset.HUMANEVAL:
            cls._datasets[dataset_type] = HumanEvalDataset()

    @classmethod
    def list_datasets(cls) -> list[str]:
        return [ds.value for ds in BenchmarkDataset]

    @classmethod
    def get_all_stats(cls) -> dict[str, dict]:
        stats = {}
        for ds_type in BenchmarkDataset:
            ds = cls.get_dataset(ds_type)
            ds.load()
            stats[ds_type.value] = ds.get_stats()
        return stats


def load_all_datasets() -> dict[str, list[dict]]:
    """加载所有数据集"""
    results = {}
    for ds_type in BenchmarkDataset:
        ds = DatasetManager.get_dataset(ds_type)
        results[ds_type.value] = ds.load()
    return results


def generate_dataset_report() -> str:
    """生成数据集报告"""
    stats = DatasetManager.get_all_stats()
    report = "=== 评测数据集报告 ===\n\n"
    for name, data in stats.items():
        report += f"【{name}】\n"
        for key, value in data.items():
            if isinstance(value, dict):
                report += f"  {key}:\n"
                for k, v in value.items():
                    report += f"    - {k}: {v}\n"
            else:
                report += f"  {key}: {value}\n"
        report += "\n"
    return report
