import uuid
import contextvars
import logging

# 定义全局上下文变量
request_id_ctx = contextvars.ContextVar("request_id", default="N/A")

def get_trace_id():
    return request_id_ctx.get()

def set_trace_id():
    # 生成唯一标识，后续压测日志中只需检索这个 ID
    trace_id = str(uuid.uuid4())[:8]
    request_id_ctx.set(trace_id)
    return trace_id