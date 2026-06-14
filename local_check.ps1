# =====================================================================
# 本地代码质量检查脚本 (PowerShell)
# 使用方法: .\local_check.ps1 [选项]
# 
# 选项:
#   -Format     自动修复格式问题
#   -Full       运行完整测试（包括集成测试）
#   -Help       显示帮助
# =====================================================================

param(
    [switch]$Format,
    [switch]$Full,
    [switch]$Help
)

# 颜色输出
function Write-Success($msg) { Write-Host "✅ $msg" -ForegroundColor Green }
function Write-Error($msg) { Write-Host "❌ $msg" -ForegroundColor Red }
function Write-Warning($msg) { Write-Host "⚠️  $msg" -ForegroundColor Yellow }
function Write-Header($msg) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host "  $msg" -ForegroundColor Blue
    Write-Host "========================================" -ForegroundColor Blue
}

# 帮助信息
if ($Help) {
    Write-Host "使用方法: .\local_check.ps1 [选项]"
    Write-Host ""
    Write-Host "选项:"
    Write-Host "  -Format    自动修复格式问题（Black + isort）"
    Write-Host "  -Full      运行完整测试（包括集成测试）"
    Write-Host "  -Help      显示帮助"
    exit 0
}

Write-Header "本地代码质量检查"

# 1. 代码格式
Write-Header "1. 代码格式检查"

if ($Format) {
    Write-Host "正在自动修复格式..." -ForegroundColor Gray
    black src/ tests/
    isort src/ tests/
    Write-Success "格式修复完成"
} else {
    Write-Host "检查代码格式 (Black)..." -ForegroundColor Gray
    $blackResult = black --check src/ tests/ 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Black 检查通过"
    } else {
        Write-Error "Black 检查失败，请运行: black src/ tests/"
        exit 1
    }
    
    Write-Host "检查导入顺序 (isort)..." -ForegroundColor Gray
    $isortResult = isort --check-only src/ tests/ 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "isort 检查通过"
    } else {
        Write-Error "isort 检查失败，请运行: isort src/ tests/"
        exit 1
    }
}

# 2. 静态分析
Write-Header "2. 静态分析"

Write-Host "快速检查 (Ruff)..." -ForegroundColor Gray
$ruffResult = ruff check src/ tests/ 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Success "Ruff 检查通过"
} else {
    Write-Error "Ruff 检查失败"
    exit 1
}

Write-Host "代码规范检查 (Flake8)..." -ForegroundColor Gray
$flake8Result = flake8 src/ tests/ --max-line-length=100 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Success "Flake8 检查通过"
} else {
    Write-Error "Flake8 检查失败"
    exit 1
}

# 3. 单元测试
Write-Header "3. 单元测试"

Write-Host "运行单元测试..." -ForegroundColor Gray
$testResult = pytest tests/unit/ -v --tb=short 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Success "单元测试通过"
} else {
    Write-Error "单元测试失败"
    exit 1
}

# 4. 完整测试（可选）
if ($Full) {
    Write-Header "4. 完整测试（集成测试）"
    Write-Warning "此步骤需要 Redis 和 PostgreSQL 服务运行"
    Write-Host "运行完整测试..." -ForegroundColor Gray
    $fullResult = pytest tests/ -v --tb=short 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "完整测试通过"
    } else {
        Write-Error "完整测试失败"
        exit 1
    }
}

Write-Header "检查完成"
Write-Host ""
Write-Success "所有检查通过，可以提交代码！"
Write-Host ""
Write-Host "提交建议:"
Write-Host "  git add ."
Write-Host "  git commit -m \"你的提交信息\""
Write-Host "  git push origin main"