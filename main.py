from domain.models.base import ModelConfig
from infra.db.repository import PostgresRepository
from infra.db import SessionLocal
from src.engine import EvaluationEngine
from src.domain.models.deepseek import DeepSeekClient  # 假设你的模型实现类在这里
from src.schemas.schemas import EvaluationSchema

request = EvaluationSchema(
    case_id="001",
    user_input="请计算 1000 元人民币的贷款利息，年化利率 3%，期限 1 年。",
    domain="finance",  # 这里会触发 finance 领域的适配器
    system_prompt="你是一个专业的金融分析师，请按要求输出格式：金额: xxx, 币种: xxx",
)

# 配置客户端
config = ModelConfig(
    api_key="sk-5e5d625e3c7845959f8cc17c872a7169", model_name="deepseek-chat"
)
my_client = DeepSeekClient(config=config)


def main():
    # 使用上下文管理器确保 Session 在操作完成后自动关闭
    with SessionLocal() as db:
        repo = PostgresRepository(db)
        engine = EvaluationEngine(my_client)

        try:
            # 1. 执行评测
            result = engine.run(request)

            # 2. 持久化数据 (带错误捕获)
            repo.save(result)
            print(f"评测结果 {result.case_id} 已成功落库。")

        except Exception as e:
            # 在这里，即便评测成功了，如果写库失败，我们也能记录关键错误
            print(f"致命错误：评测完成但写入数据库失败: {str(e)}")
            # 建议：在此处加入日志记录或发送报警


if __name__ == "__main__":
    main()
