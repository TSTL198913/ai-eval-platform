# src/domain/evaluators/__init__.py
import importlib
import pkgutil

from .base import EvaluatorFactory


# 1. 自动发现：扫描并导入所有子模块，触发 @EvaluatorFactory.register
def auto_discover():
    for _, name, _is_pkg in pkgutil.iter_modules(__path__):
        if name not in ["base", "metadata"]:
            importlib.import_module(f".{name}", package=__name__)


# 执行自动注册
auto_discover()

# 2. 兼容性导出：为了满足 evaluator_svc.py 中的导入需求
# 如果你之前是通过 EVALUATOR_REGISTRY 访问的，这里直接指向工厂的注册表
EVALUATOR_REGISTRY = EvaluatorFactory._registry
