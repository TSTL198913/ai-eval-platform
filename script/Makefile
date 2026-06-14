# 设置变量
PYTHON := python3
SRC_DIR := src
TEST_DIR := tests
REPORT_DIR := reports

.PHONY: all check test lint clean help init

# 默认指令：执行全量检查
all: check

# 1. 环境初始化与自检
init:
	@echo "--- 正在检测运行环境 ---"
	@command -v $(PYTHON) >/dev/null 2>&1 || { echo >&2 "错误: 未找到 $(PYTHON)。请先安装 Python。"; exit 1; }
	pip install --upgrade pip
	pip install -r requirements.txt
	@echo "环境自检完成，依赖已安装。"

# 2. 静态分析：Linting
lint:
	@echo "--- 运行 Ruff 静态分析 ---"
	ruff check $(SRC_DIR) $(TEST_DIR) --fix

# 3. 单元测试与覆盖率门禁
test:
	@echo "--- 运行单元测试并计算覆盖率 ---"
	pytest --cov=$(SRC_DIR) --cov-report=term-missing --cov-fail-under=100 $(TEST_DIR)

# 4. 复合指令：综合质量门禁
check: lint test
	@echo "--- 所有质量检查通过！---"

# 5. 清理残留文件
clean:
	rm -rf .pytest_cache .coverage .ruff_cache $(REPORT_DIR)
	find . -type d -name "__pycache__" -exec rm -rf {} +

# 6. 帮助文档
help:
	@echo "可用指令:"
	@echo "  make init   : 初始化环境并检查依赖"
	@echo "  make lint   : 运行 Ruff 自动格式化"
	@echo "  make test   : 运行单元测试并强制 100% 覆盖率"
	@echo "  make check  : 执行 lint + test (CI 流水线调用)"
	@echo "  make clean  : 清理临时文件"