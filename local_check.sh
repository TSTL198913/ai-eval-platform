#!/bin/bash
# =====================================================================
# 本地代码质量检查脚本
# 使用方法: ./local_check.sh [选项]
# 
# 选项:
#   --format    自动修复格式问题
#   --full      运行完整测试（包括集成测试）
#   --help      显示帮助
# =====================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# 参数处理
FORMAT_FIX=false
FULL_TEST=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --format) FORMAT_FIX=true ;;
        --full) FULL_TEST=true ;;
        --help)
            echo "使用方法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --format    自动修复格式问题（Black + isort）"
            echo "  --full      运行完整测试（包括集成测试）"
            echo "  --help      显示帮助"
            exit 0
            ;;
        *) echo "未知选项: $1"; exit 1 ;;
    esac
    shift
done

print_header "本地代码质量检查"

# 1. 代码格式
print_header "1. 代码格式检查"

if $FORMAT_FIX; then
    echo "正在自动修复格式..."
    black src/ tests/
    isort src/ tests/
    print_success "格式修复完成"
else
    echo "检查代码格式 (Black)..."
    if black --check src/ tests/; then
        print_success "Black 检查通过"
    else
        print_error "Black 检查失败，请运行: black src/ tests/"
        exit 1
    fi
    
    echo "检查导入顺序 (isort)..."
    if isort --check-only src/ tests/; then
        print_success "isort 检查通过"
    else
        print_error "isort 检查失败，请运行: isort src/ tests/"
        exit 1
    fi
fi

# 2. 静态分析
print_header "2. 静态分析"

echo "快速检查 (Ruff)..."
if ruff check src/ tests/; then
    print_success "Ruff 检查通过"
else
    print_error "Ruff 检查失败"
    exit 1
fi

echo "代码规范检查 (Flake8)..."
if flake8 src/ tests/ --max-line-length=100; then
    print_success "Flake8 检查通过"
else
    print_error "Flake8 检查失败"
    exit 1
fi

# 3. 单元测试
print_header "3. 单元测试"

echo "运行单元测试..."
if pytest tests/unit/ -v --tb=short; then
    print_success "单元测试通过"
else
    print_error "单元测试失败"
    exit 1
fi

# 4. 完整测试（可选）
if $FULL_TEST; then
    print_header "4. 完整测试（集成测试）"
    echo "⚠️  此步骤需要 Redis 和 PostgreSQL 服务运行"
    echo "运行完整测试..."
    if pytest tests/ -v --tb=short; then
        print_success "完整测试通过"
    else
        print_error "完整测试失败"
        exit 1
    fi
fi

print_header "检查完成"
echo ""
echo -e "${GREEN}✅ 所有检查通过，可以提交代码！${NC}"
echo ""
echo "提交建议:"
echo "  git add ."
echo "  git commit -m \"你的提交信息\""
echo "  git push origin main"