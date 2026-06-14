import redis

r = redis.Redis(host="localhost", port=6379, db=0)


def check_backlog():
    # 获取队列长度
    queue_len = r.llen("celery")
    if queue_len > 1000:
        print(f"警告：任务积压严重，当前队列长度: {queue_len}！建议增加 Worker 数量。")
    else:
        print(f"当前队列负载正常，任务数: {queue_len}")


check_backlog()
