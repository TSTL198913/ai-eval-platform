"""评分计算工具类 - 统一评分计算逻辑"""


class ScoreCalculator:
    """统一的评分计算工具"""

    def __init__(self, initial_score: float = 1.0):
        self.score = initial_score

    def deduct(self, amount: float) -> None:
        """扣分"""
        self.score = max(0.0, self.score - amount)

    def add(self, amount: float) -> None:
        """加分"""
        self.score = min(1.0, self.score + amount)

    def get_score(self) -> float:
        """获取最终分数"""
        return max(0.0, min(1.0, self.score))

    def get_risk_level(self) -> str:
        """根据分数判断风险等级"""
        if self.score >= 0.8:
            return "low"
        elif self.score >= 0.5:
            return "medium"
        else:
            return "high"

    @staticmethod
    def calculate_weighted_average(
        scores: dict[str, float],
        weights: dict[str, float]
    ) -> float:
        """加权平均计算"""
        weighted_score = sum(
            scores[key] * weights.get(key, 1.0)
            for key in scores
        )
        total_weight = sum(weights.get(key, 1.0) for key in scores)
        return weighted_score / total_weight if total_weight > 0 else 1.0
