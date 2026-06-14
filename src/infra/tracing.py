import contextvars
import uuid

# 全局上下文变量，用于存储当前请求的 Trace ID
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="system")

def generate_trace_id() -> str:
    return str(uuid.uuid4())[:8]
