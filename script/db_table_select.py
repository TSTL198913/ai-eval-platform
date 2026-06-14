# 运行这段小脚本来查看到底存在哪些表
from sqlalchemy import inspect

from infra.db import engine

inspector = inspect(engine)
print(inspector.get_table_names())
