$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$environmentName = "TIANSHU"

Push-Location $projectRoot
try {
    conda run --name $environmentName python "scripts\run_demo.py"
    if ($LASTEXITCODE -ne 0) { throw "天枢杯系统启动失败" }
} finally {
    Pop-Location
}
