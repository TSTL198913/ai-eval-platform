import redis


def check_backlog(host: str = "localhost", port: int = 6379, db: int = 0):
    """检查队列积压情况"""
    r = redis.Redis(host=host, port=port, db=db)
    queue_len = r.llen("celery")
    if queue_len > 1000:
        print(f"警告：任务积压严重，当前队列长度: {queue_len}！建议增加 Worker 数量。")
    else:
        print(f"当前队列负载正常，任务数: {queue_len}")


if __name__ == "__main__":
    check_backlog()
