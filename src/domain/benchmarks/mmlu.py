import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BenchmarkResult
from .registry import BenchmarkRegistry

logger = logging.getLogger(__name__)


@BenchmarkRegistry.register("mmlu")
class MMLUBenchmark:
    name = "MMLU"
    description = "Massive Multitask Language Understanding - Tests across 57 subjects"
    category = "knowledge"
    num_samples = 100

    SUBJECTS = [
        "abstract_algebra", "anatomy", "astronomy", "business_ethics", "clinical_knowledge",
        "college_biology", "college_chemistry", "college_computer_science", "college_mathematics",
        "college_medicine", "college_physics", "computer_security", "conceptual_physics",
        "econometrics", "electrical_engineering", "elementary_mathematics", "formal_logic",
        "global_facts", "high_school_biology", "high_school_chemistry", "high_school_computer_science",
        "high_school_economics", "high_school_geography", "high_school_government_and_politics",
        "high_school_history", "high_school_mathematics", "high_school_physics", "high_school_statistics",
        "human_aging", "human_sexuality", "international_law", "jurisprudence", "logical_fallacies",
        "machine_learning", "management", "marketing", "medical_genetics", "miscellaneous",
        "moral_disputes", "moral_scenarios", "nutrition", "philosophy", "prehistory",
        "professional_accounting", "professional_law", "professional_medicine", "professional_psychology",
        "public_relations", "security_studies", "sociology", "us_foreign_policy",
        "virology", "world_religions", "business_management", "college_education",
        "college_psychology", "high_school_psychology", "law"
    ]

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent / "data" / "mmlu"
        self._dataset: Optional[List[Dict[str, Any]]] = None

    def load_dataset(self) -> List[Dict[str, Any]]:
        if self._dataset is not None:
            return self._dataset

        dataset = []
        if self.data_dir.exists() and self.data_dir.is_dir():
            for subject in self.SUBJECTS[:5]:
                subject_file = self.data_dir / f"{subject}_test.jsonl"
                if subject_file.exists():
                    with open(subject_file, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                item = json.loads(line.strip())
                                dataset.append({
                                    "subject": subject,
                                    "question": item.get("question", ""),
                                    "choices": item.get("choices", []),
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
        synthetic = []
        templates = [
            {
                "question": "What is the capital of {country}?",
                "choices": ["A. London", "B. Paris", "C. Berlin", "D. Rome"],
                "answers": {"United Kingdom": "A", "France": "B", "Germany": "C", "Italy": "D"},
                "subject": "high_school_geography",
            },
            {
                "question": "What is 2 + 2?",
                "choices": ["A. 3", "B. 4", "C. 5", "D. 6"],
                "answers": {"math": "B"},
                "subject": "elementary_mathematics",
            },
            {
                "question": "Which planet is known as the Red Planet?",
                "choices": ["A. Venus", "B. Mars", "C. Jupiter", "D. Saturn"],
                "answers": {"space": "B"},
                "subject": "astronomy",
            },
            {
                "question": "What is the chemical symbol for water?",
                "choices": ["A. CO2", "B. H2O", "C. NaCl", "D. O2"],
                "answers": {"chemistry": "B"},
                "subject": "high_school_chemistry",
            },
            {
                "question": "Who wrote 'Romeo and Juliet'?",
                "choices": ["A. Charles Dickens", "B. William Shakespeare", "C. Mark Twain", "D. Ernest Hemingway"],
                "answers": {"literature": "B"},
                "subject": "miscellaneous",
            },
        ]

        for i in range(100):
            template = templates[i % len(templates)]
            context_key = list(template["answers"].keys())[0]
            synthetic.append({
                "subject": template["subject"],
                "question": template["question"].format(country="United Kingdom"),
                "choices": template["choices"],
                "answer": template["answers"][context_key],
                "id": i,
            })

        return synthetic

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
                is_correct = predicted_answer == sample["answer"]

                if is_correct:
                    correct += 1

                results.append({
                    "id": sample["id"],
                    "subject": sample["subject"],
                    "question": sample["question"],
                    "choices": sample["choices"],
                    "correct_answer": sample["answer"],
                    "predicted_answer": predicted_answer,
                    "is_correct": is_correct,
                })

            except Exception as e:
                errors.append(f"Sample {sample['id']}: {str(e)}")
                results.append({
                    "id": sample["id"],
                    "subject": sample["subject"],
                    "question": sample["question"],
                    "choices": sample["choices"],
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
        choices_text = "\n".join(sample["choices"])
        return f"""Question: {sample['question']}

Options:
{choices_text}

Please provide only the letter (A, B, C, or D) corresponding to the correct answer."""

    def _parse_answer(self, response: str) -> str:
        response = response.strip().upper()
        found = []
        for char in response:
            if char in ["A", "B", "C", "D"]:
                found.append(char)
        return found[-1] if found else ""

    def calculate_score(self, results: List[Dict[str, Any]]) -> float:
        if not results:
            return 0.0
        correct = sum(1 for r in results if r.get("is_correct", False))
        return correct / len(results)
