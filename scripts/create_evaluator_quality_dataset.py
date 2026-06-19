"""
评估器代码质量黄金数据集
用于校准 LLMAJudgeEvaluator 对代码质量的评估标准
"""

from src.domain.golden_dataset import golden_dataset_manager
from src.schemas.evaluation import EvaluationSchema


def create_evaluator_quality_golden_dataset():
    """创建评估器质量黄金数据集"""

    # 定义黄金标准样本
    golden_samples = [
        {
            "id": "good_code_001",
            "user_input": """审查以下Python代码的质量（满分100分）：
```python
class UserService:
    def __init__(self, repository):
        self.repository = repository

    def get_user(self, user_id: int) -> Optional[User]:
        try:
            return self.repository.find_by_id(user_id)
        except DatabaseError as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return None
```""",
            "expected_output": "85分 - 代码结构清晰，有错误处理，但缺少类型注解和文档注释",
            "scores": {
                "correctness": 90,
                "relevance": 85,
                "completeness": 80
            },
            "dimensions": ["correctness", "relevance", "completeness"]
        },
        {
            "id": "bad_code_001",
            "user_input": """审查以下Python代码的质量（满分100分）：
```python
def get(x):
    return db.query(x)
```""",
            "expected_output": "30分 - 变量命名不规范，无类型提示，无错误处理，无文档",
            "scores": {
                "correctness": 30,
                "relevance": 35,
                "completeness": 25
            },
            "dimensions": ["correctness", "relevance", "completeness"]
        },
        {
            "id": "security_issue_001",
            "user_input": """审查以下Python代码的安全性（满分100分）：
```python
def query(sql):
    return db.execute(sql)
```""",
            "expected_output": "20分 - 存在SQL注入风险，应使用参数化查询",
            "scores": {
                "security": 20,
                "correctness": 30,
                "completeness": 25
            },
            "dimensions": ["security", "correctness", "completeness"]
        }
    ]

    # 创建数据集
    dataset = golden_dataset_manager.create_dataset(
        name="evaluator_quality_standard",
        description="评估器代码质量评审标准",
        category="code_quality"
    )

    # 添加样本
    for sample in golden_samples:
        golden_dataset_manager.add_sample(
            dataset_id=dataset.id,
            sample_data={
                "id": sample["id"],
                "user_input": sample["user_input"],
                "actual_output": sample["expected_output"],
                "expected_output": sample["expected_output"],
                "dimensions": sample["dimensions"],
                "scores": sample["scores"]
            }
        )

    print(f"创建评估器质量黄金数据集: {dataset.id}")
    print(f"包含 {len(golden_samples)} 个标准样本")

    return dataset


if __name__ == "__main__":
    create_evaluator_quality_golden_dataset()
