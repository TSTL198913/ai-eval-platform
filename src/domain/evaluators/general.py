from src.domain.evaluators.base import BaseEvaluator, EvaluatorFactory
from src.schemas.evaluation import DomainResponse


@EvaluatorFactory.register("general")
def create_general_evaluator(client=None):
    return GeneralEvaluator(client=client)


class GeneralEvaluator(BaseEvaluator):
    def evaluate(self, request):
        user_input = self.get_input_text(request)
        return DomainResponse(is_valid=True, data=f"通用评估: {user_input}")
