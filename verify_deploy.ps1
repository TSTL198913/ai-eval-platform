# =====================================================================
# AI Evaluation Platform - 部署验证脚本 (Windows PowerShell)
# =====================================================================
#
# 功能�?# 1. 检查服务状�?# 2. 功能测试（API、任务队列）
# 3. 查看日志
# 4. 健康检�?#
# 使用方法�?#   .\verify_deploy.ps1 [命令]
#
# 命令�?#   status    - 查看服务状�?#   api       - 测试 API 接口
#   task      - 测试任务队列
#   health    - 健康检�?#   logs      - 查看日志（最�?100 行）
#   logs-all  - 查看完整日志
#   test      - 完整功能测试
#   help      - 显示帮助
#
# =====================================================================

param(
    [string]$Command = "help"
)

# 配置
$API_URL = if ($env:API_URL) { $env:API_URL } else { "http://localhost:8000" }
$REDIS_URL = if ($env:REDIS_URL) { $env:REDIS_URL } else { "redis://localhost:6379" }
$LOG_DIR = if ($env:LOG_DIR) { $env:LOG_DIR } else { ".\logs" }
$PROJECT_DIR = if ($env:PROJECT_DIR) { $env:PROJECT_DIR } else { "C:\ai-eval-platform" }

# 颜色输出
function Write-Success($msg) { Write-Host "�?$msg" -ForegroundColor Green }
function Write-Error($msg) { Write-Host "�?$msg" -ForegroundColor Red }
function Write-Warning($msg) { Write-Host "⚠️  $msg" -ForegroundColor Yellow }
function Write-Info($msg) { Write-Host "ℹ️  $msg" -ForegroundColor Cyan }
function Write-Header($msg) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host "  $msg" -ForegroundColor Blue
    Write-Host "========================================" -ForegroundColor Blue
}

# 检�?Docker 服务状�?function Get-DockerStatus {
    Write-Header "Docker 服务状�?
    docker compose ps
}

# 检�?API 健康状�?function Test-ApiHealth {
    Write-Header "API 健康检�?

    Write-Host "测试: GET /health" -ForegroundColor Gray

    try {
        $response = Invoke-WebRequest -Uri "$API_URL/health" -UseBasicParsing -TimeoutSec 10
        if ($response.StatusCode -eq 200) {
            Write-Success "API 服务正常"
            $response.Content | ConvertFrom-Json | Format-List
        } else {
            Write-Error "API 服务返回状态码: $($response.StatusCode)"
        }
    } catch {
        Write-Error "无法连接�?API: $_"
    }
}

# API 功能测试
function Test-ApiFunction {
    Write-Header "API 功能测试"

    # 测试 1: 契约拦截
    Write-Host ""
    Write-Host "测试 1: 契约拦截（无效输入应返回 CONTRACT_ERROR�? -ForegroundColor Yellow
    Write-Host "-------------------------------------------" -ForegroundColor DarkGray

    try {
        $body = '{"wrong": "data"}'
        $response = Invoke-WebRequest -Uri "$API_URL/api/v1/evaluate" `
            -Method POST `
            -ContentType "application/json" `
            -Body $body `
            -UseBasicParsing `
            -TimeoutSec 10

        $content = $response.Content | ConvertFrom-Json
        if ($content.error.code -eq "CONTRACT_ERROR") {
            Write-Success "契约拦截正常"
        }
        $content | Format-Json
    } catch {
        Write-Warning "契约拦截测试失败: $_"
    }

    # 测试 2: 业务路由
    Write-Host ""
    Write-Host "测试 2: 业务路由（finance 类型�? -ForegroundColor Yellow
    Write-Host "-------------------------------------------" -ForegroundColor DarkGray

    try {
        $body = @{
            id = "TEST_001"
            type = "finance"
            payload = @{
                case_id = "c1"
                user_input = "10000元存一年定期，利率3%，利息多少？"
                expected_output = "300�?
                metadata = @{ rate = 0.03 }
            }
        } | ConvertTo-Json -Depth 10

        $response = Invoke-WebRequest -Uri "$API_URL/api/v1/evaluate" `
            -Method POST `
            -ContentType "application/json" `
            -Body $body `
            -UseBasicParsing `
            -TimeoutSec 30

        $content = $response.Content | ConvertFrom-Json
        if ($content.evaluation_status) {
            Write-Success "业务路由正常"
        }
        $content | Format-Json
    } catch {
        Write-Warning "业务路由测试失败（可能需要配�?LLM�? $_"
    }

    # 测试 3: 异步任务提交
    Write-Host ""
    Write-Host "测试 3: 异步任务提交" -ForegroundColor Yellow
    Write-Host "-------------------------------------------" -ForegroundColor DarkGray

    try {
        $body = @{
            id = "ASYNC_001"
            type = "general"
            payload = @{
                case_id = "c2"
                user_input = "你好"
                expected_output = "你好"
            }
        } | ConvertTo-Json -Depth 10

        $response = Invoke-WebRequest -Uri "$API_URL/api/v1/evaluate/async" `
            -Method POST `
            -ContentType "application/json" `
            -Body $body `
            -UseBasicParsing `
            -TimeoutSec 10

        $content = $response.Content | ConvertFrom-Json
        if ($content.task_id) {
            Write-Success "异步任务提交正常"
        }
        $content | Format-Json
    } catch {
        Write-Warning "异步任务提交测试失败: $_"
    }
}

# 任务队列测试
function Test-TaskQueue {
    Write-Header "任务队列测试"

    # 检�?Redis
    Write-Host ""
    Write-Host "检�?Redis 连接..." -ForegroundColor Gray

    try {
        $redisResult = docker compose exec -T redis redis-cli ping 2>$null
        if ($redisResult -match "PONG") {
            Write-Success "Redis 连接正常"
            docker compose exec -T redis redis-cli info | Select-String -Pattern "redis_version", "connected_clients", "used_memory_human"
        }
    } catch {
        Write-Error "Redis 连接失败: $_"
    }

    # 检�?Celery Worker
    Write-Host ""
    Write-Host "检�?Celery Worker..." -ForegroundColor Gray

    try {
        $workerStats = docker compose exec -T worker celery -A src.workers.celery_app inspect stats 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Celery Worker 运行正常"
        }
    } catch {
        Write-Warning "Celery Worker 可能未运�? $_"
    }
}

# 查看日志
function Get-Logs {
    param([switch]$All)

    Write-Header "查看日志"

    if ($All) {
        docker compose logs
    } else {
        docker compose logs --tail=100
    }
}

# 完整测试
function Start-FullTest {
    Write-Header "完整功能测试"

    Write-Host "开始全面测�?.." -ForegroundColor Gray
    Write-Host ""

    Get-DockerStatus
    Test-ApiHealth
    Test-ApiFunction
    Test-TaskQueue

    Write-Host ""
    Write-Host "最近日�?" -ForegroundColor Yellow
    docker compose logs --tail=20 2>$null

    Write-Header "测试完成"
}

# 帮助信息
function Show-Help {
    Write-Host ""
    Write-Host "AI Evaluation Platform - 部署验证脚本" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "使用方法: .\verify_deploy.ps1 [命令]"
    Write-Host ""
    Write-Host "可用命令:"
    Write-Host "  status     查看 Docker 服务状�?
    Write-Host "  health     健康检查（容器 + API�?
    Write-Host "  api        API 功能测试"
    Write-Host "  task       任务队列测试"
    Write-Host "  logs       查看日志（最�?100 行）"
    Write-Host "  logs-all   查看完整日志"
    Write-Host "  test       完整功能测试"
    Write-Host "  help       显示帮助"
    Write-Host ""
    Write-Host "环境变量:"
    Write-Host "  `$env:API_URL         API 地址 (默认: http://localhost:8000)"
    Write-Host "  `$env:REDIS_URL       Redis 地址 (默认: redis://localhost:6379)"
    Write-Host "  `$env:LOG_DIR         日志目录 (默认: .\logs)"
    Write-Host "  `$env:PROJECT_DIR     项目目录 (默认: C:\ai-eval-platform)"
    Write-Host ""
    Write-Host "示例:"
    Write-Host "  `$env:API_URL='http://localhost:9000'; .\verify_deploy.ps1 api"
    Write-Host "  .\verify_deploy.ps1 test"
    Write-Host ""
}

# 主程�?switch ($Command.ToLower()) {
    "status" { Get-DockerStatus }
    "health" { Test-ApiHealth }
    "api" { Test-ApiHealth; Test-ApiFunction }
    "task" { Test-TaskQueue }
    "logs" { Get-Logs }
    "logs-all" { Get-Logs -All }
    "test" { Start-FullTest }
    { $_ -in "help", "--help", "-h" } { Show-Help }
    default {
        Write-Error "未知命令: $Command"
        Write-Host "运行 '.\verify_deploy.ps1 help' 查看帮助" -ForegroundColor Gray
        exit 1
    }
}
