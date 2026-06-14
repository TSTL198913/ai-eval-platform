import json
from src.schemas.evaluation import EvaluationSchema
from src.domain.evaluators import EvaluatorFactory


def run_live_demo(title: str, raw_json_data: dict):
    print(f"\n{'=' * 30} {title} {'=' * 30}")
    print(
        f"【1. 进来的原始数据】:\n{json.dumps(raw_json_data, indent=4, ensure_ascii=False)}"
    )

    try:
        # 1. 体验数据整形 (Contract Layer)
        request = EvaluationSchema(**raw_json_data)
        print(f"\n 精型成功！Pydantic 核心契约对象为:\n  {repr(request)}")

        # 2. 体验智能分流 (Domain Layer)
        evaluator = EvaluatorFactory.get(request.type)
        print(f" 路由成功！系统自动分流至评估器: {type(evaluator).__name__}")

        # 3. 体验业务执行
        result = evaluator.evaluate(request)
        print(f" 执行成功！最终标准业务返回 (DomainResponse):\n  {result}")

    except Exception as e:
        print(f"\n❌ 拦截成功！数据未能通过防腐层，系统安然无恙。错误原因:\n{e}")


# ==========================================
# 准备三个不同的真实场景进行轰炸
# ==========================================

# 场景 A：就是你觉得“挺规范”但其实带有一点小冗余的数据
normal_case = {
    "id": "case_001",
    "type": "finance",
    "payload": {
        "case_id": "c1",
        "user_input": "计算利息",
        "domain": "finance",
        "metadata": {"rate": 0.05},
    },
    "metadata": {},
}

# 场景 B：上游作死！缺了关键的核心字段，看系统会不会蓝屏
broken_case = {
    "id": "case_002",
    # 故意把 type 漏掉了，而且 payload 格式也是错的
    "metadata": {"attacker": "bad_json"},
}

# 场景 C：一秒接入新分流！试试分流到文本评估器
text_case = {
    "id": "case_003",
    "type": "text",  # 换成 text 领域
    "payload": {"user_input": "你好，帮我写一首关于重构通过的诗"},
}

# 开始真实体验
run_live_demo("场景 A：正常数据的整形与分流", normal_case)
run_live_demo("场景 B：恶意/残缺数据的清洗与拦截", broken_case)
run_live_demo("场景 C：动态改变领域的分流体验", text_case)
