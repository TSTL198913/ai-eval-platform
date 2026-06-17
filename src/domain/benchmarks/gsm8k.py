import json
import logging
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BenchmarkResult
from .registry import BenchmarkRegistry

logger = logging.getLogger(__name__)


@BenchmarkRegistry.register("gsm8k")
class GSM8KBenchmark:
    name = "GSM8K"
    description = "Grade School Math 8K - Tests mathematical reasoning"
    category = "reasoning"
    num_samples = 50

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent / "data" / "gsm8k"
        self._dataset: Optional[List[Dict[str, Any]]] = None

    def load_dataset(self) -> List[Dict[str, Any]]:
        if self._dataset is not None:
            return self._dataset

        dataset = []
        if self.data_dir.exists() and self.data_dir.is_dir():
            for filename in self.data_dir.glob("*.jsonl"):
                with open(filename, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            item = json.loads(line.strip())
                            dataset.append({
                                "question": item.get("question", ""),
                                "answer": item.get("answer", ""),
                                "id": item.get("id", len(dataset)),
                            })
                        except json.JSONDecodeError:
                            continue

        if not dataset:
            dataset = self._generate_synthetic_data()

        random.seed(42)
        self._dataset = random.sample(dataset, min(self.num_samples, len(dataset)))
        return self._dataset

    def _generate_synthetic_data(self) -> List[Dict[str, Any]]:
        synthetic = [
            {
                "question": "John has 5 apples. He buys 3 more apples from the store. How many apples does John have now?",
                "answer": "8",
                "id": 0,
            },
            {
                "question": "A train travels at 60 miles per hour. How far will it travel in 3 hours?",
                "answer": "180",
                "id": 1,
            },
            {
                "question": "Sarah has 12 cookies. She shares them equally among 4 friends. How many cookies does each friend get?",
                "answer": "3",
                "id": 2,
            },
            {
                "question": "There are 25 students in a class. If 5 students are absent, how many students are present?",
                "answer": "20",
                "id": 3,
            },
            {
                "question": "A bookshelf has 5 shelves. Each shelf holds 10 books. How many books can the shelf hold in total?",
                "answer": "50",
                "id": 4,
            },
            {
                "question": "Tom saves $5 every week. How much will he save in 8 weeks?",
                "answer": "40",
                "id": 5,
            },
            {
                "question": "A pizza has 8 slices. If 3 people share it equally, how many slices does each person get?",
                "answer": "2",
                "id": 6,
            },
            {
                "question": "A garden has 15 flowers. 6 are roses and the rest are daisies. How many daisies are there?",
                "answer": "9",
                "id": 7,
            },
            {
                "question": "A car gets 25 miles per gallon. How many gallons are needed to travel 150 miles?",
                "answer": "6",
                "id": 8,
            },
            {
                "question": "There are 30 days in April. If today is the 15th, how many days are left in the month?",
                "answer": "15",
                "id": 9,
            },
        ]

        extended = []
        for i in range(50):
            base = synthetic[i % len(synthetic)]
            extended.append({
                "question": base["question"],
                "answer": base["answer"],
                "id": i,
            })

        return extended

    def evaluate(self, llm_client, samples: Optional[List[Dict[str, Any]]] = None) -> BenchmarkResult:
        if samples is None:
            samples = self.load_dataset()

        results = []
        correct = 0
        errors = []

        for sample in samples:
            try:
                prompt = self._build_prompt(sample)
                response = llm_client.chat_completion(prompt)
                predicted_answer = self._parse_answer(response)
                is_correct = self._compare_answers(predicted_answer, sample["answer"])

                if is_correct:
                    correct += 1

                results.append({
                    "id": sample["id"],
                    "question": sample["question"],
                    "correct_answer": sample["answer"],
                    "predicted_answer": predicted_answer,
                    "is_correct": is_correct,
                    "raw_response": response,
                })

            except Exception as e:
                errors.append(f"Sample {sample['id']}: {str(e)}")
                results.append({
                    "id": sample["id"],
                    "question": sample["question"],
                    "correct_answer": sample["answer"],
                    "predicted_answer": None,
                    "is_correct": False,
                    "error": str(e),
                })

        accuracy = correct / len(samples) if samples else 0.0

        return BenchmarkResult(
            benchmark_name=self.name,
            total_samples=len(samples),
            correct_samples=correct,
            accuracy=accuracy,
            scores=results,
            metadata={"category": self.category},
            error_count=len(errors),
            error_messages=errors,
        )

    def _build_prompt(self, sample: Dict[str, Any]) -> str:
        return f"""Solve the following math problem:

{sample['question']}

Please provide only the numerical answer."""

    def _parse_answer(self, response: str) -> str:
        numbers = re.findall(r"-?\d+\.?\d*", response)
        return numbers[-1] if numbers else ""

    def _compare_answers(self, predicted: str, expected: str) -> bool:
        try:
            pred_num = float(predicted) if predicted else 0
            exp_num = float(expected) if expected else 0
            return abs(pred_num - exp_num) < 0.01
        except ValueError:
            return predicted.strip() == expected.strip()

    def calculate_score(self, results: List[Dict[str, Any]]) -> float:
        if not results:
            return 0.0
        correct = sum(1 for r in results if r.get("is_correct", False))
        return correct / len(results)
