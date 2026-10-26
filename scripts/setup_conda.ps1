$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$environmentName = "TIANSHU"
$environmentFile = Join-Path $projectRoot "environment.yml"

conda env update --name $environmentName --file $environmentFile --prune
if ($LASTEXITCODE -ne 0) {
    throw "Conda 环境创建或更新失败，退出码：$LASTEXITCODE"
}

Push-Location (Join-Path $projectRoot "frontend")
try {
    conda run --name $environmentName npm install
} finally {
    Pop-Location
}
if ($LASTEXITCODE -ne 0) {
    throw "Vue 前端依赖安装失败，退出码：$LASTEXITCODE"
}

Write-Host "Conda 环境与 Vue 前端依赖准备完成：$environmentName"
Write-Host "运行命令：conda run --name $environmentName python scripts\run_demo.py"
