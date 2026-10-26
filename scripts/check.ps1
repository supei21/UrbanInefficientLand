$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$environmentName = "TIANSHU"

Push-Location $projectRoot
try {
    conda run --name $environmentName ruff format --check backend tianshu_core report scripts tests
    if ($LASTEXITCODE -ne 0) { throw "Python 格式检查失败" }
    conda run --name $environmentName ruff check backend tianshu_core report scripts tests
    if ($LASTEXITCODE -ne 0) { throw "Python 静态检查失败" }
    conda run --name $environmentName python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "Python 测试失败" }
    conda run --name $environmentName npm --prefix frontend run typecheck
    if ($LASTEXITCODE -ne 0) { throw "Vue 类型检查失败" }
    conda run --name $environmentName npm --prefix frontend run lint
    if ($LASTEXITCODE -ne 0) { throw "前端 ESLint 检查失败" }
    conda run --name $environmentName npm --prefix frontend run format:check
    if ($LASTEXITCODE -ne 0) { throw "前端格式检查失败" }
    conda run --name $environmentName npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw "前端生产构建失败" }
} finally {
    Pop-Location
}

Write-Host "全部质量检查通过。"
