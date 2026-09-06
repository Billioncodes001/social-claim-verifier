param([switch]$DownloadModel)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath 'verifier/static/dist/index.html')) {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Node.js 22.12+ and npm are required to build the web app.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Web app build failed.' }
}
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or newer is required.' }
    & $pythonPath -m pip install -e '.[test]'
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
if ($DownloadModel) {
    & $pythonPath scripts/setup_local_model.py
    if ($LASTEXITCODE -ne 0) { throw 'Model setup failed.' }
}
$binaryPath = Join-Path $projectRoot '.runtime/local-model/server/llama-server.exe'
if (Test-Path -LiteralPath $binaryPath) {
    & $pythonPath scripts/configure_local.py
    $modelPort = Get-NetTCPConnection -LocalPort 8087 -State Listen -ErrorAction SilentlyContinue
    if ($modelPort) {
        $existingModel = Get-Process -Id ($modelPort | Select-Object -First 1).OwningProcess
        if ($existingModel.Path -ne $binaryPath) { throw 'Port 8087 is used by another application. Configure a different local endpoint before starting.' }
    }
    if (-not $modelPort) {
        $arguments = @('--model', "`"$projectRoot/.runtime/local-model/Qwen3-4B-Q4_K_M.gguf`"", '--host', '127.0.0.1', '--port', '8087', '--alias', 'qwen3-4b-local', '--ctx-size', '32768', '--parallel', '2', '-ngl', '99', '--jinja', '--api-key-file', "`"$projectRoot/.runtime/local-model/api.key`"", '--cors-origins', 'http://127.0.0.1:8791')
        $modelProcess = Start-Process -FilePath $binaryPath -ArgumentList $arguments -WindowStyle Hidden -RedirectStandardOutput "$projectRoot/.runtime/model-out.log" -RedirectStandardError "$projectRoot/.runtime/model-error.log" -PassThru
        $modelProcess.Id | Set-Content .runtime/model.pid
    }
}
$appPort = Get-NetTCPConnection -LocalPort 8791 -State Listen -ErrorAction SilentlyContinue
if ($appPort) {
    $existingApp = Get-Process -Id ($appPort | Select-Object -First 1).OwningProcess
    if ($existingApp.Path -ne $pythonPath) { throw 'Port 8791 is used by another application. Start claim-verifier serve with an available --port.' }
}
if (-not $appPort) {
    New-Item -ItemType Directory -Force .runtime | Out-Null
    $appProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m','verifier.cli','serve') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput "$projectRoot/.runtime/app-out.log" -RedirectStandardError "$projectRoot/.runtime/app-error.log" -PassThru
    $appProcess.Id | Set-Content .runtime/app.pid
}
Write-Output 'Claim Verifier is starting at http://127.0.0.1:8791. Open it to create your administrator account.'
