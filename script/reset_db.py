from infra.db import Base, engine


def reset_database():
    print("正在清空数据库架构...")
    # 删除所有表
    Base.metadata.drop_all(engine)
    # 重新创建表 (基于新的 Schema)
    Base.metadata.create_all(engine)
    print("数据库已重置，架构更新完成。")

if __name__ == "__main__":
    reset_database()