from src.infra.analytics.analytics import QueryService
from src.infra.db.session import SessionLocal


def main():
    with SessionLocal() as db:
        service = QueryService(db)
        report = service.get_performance_report()

        print("-" * 30)
        print("评测分析概览")
        print(f"总计评测次数: {report['total_evals']}")
        print(f"当前成功率:   {report['success_rate']:.2%}")
        print(f"平均延迟:     {report['avg_latency_ms']:.2f} ms")
        print("-" * 30)


if __name__ == "__main__":
    main()
