from src.domain.evaluators.base import BaseEvaluator, EvaluatorFactory
from src.domain.evaluators.code import CodeEvaluator


@EvaluatorFactory.register("code_review")
def create_code_review_evaluator(client=None):
    return CodeReviewEvaluator(client=client)


class CodeReviewEvaluator(BaseEvaluator):
    """code_review 复用 CodeEvaluator 的审查逻辑。"""

    def __init__(self, client=None):
        super().__init__(client=client)
        self._delegate = CodeEvaluator(client=client)

    def evaluate(self, request):
        return self._delegate.evaluate(request)
