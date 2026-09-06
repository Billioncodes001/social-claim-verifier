$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
foreach ($service in @('app','model')) {
    $pidFile = Join-Path $projectRoot ".runtime/$service.pid"
    if (Test-Path -LiteralPath $pidFile) {
        $serviceId = [int](Get-Content -LiteralPath $pidFile)
        $serviceProcess = Get-Process -Id $serviceId -ErrorAction SilentlyContinue
        if ($serviceProcess) {
            $expectedPath = if ($service -eq 'model') { Join-Path $projectRoot '.runtime/local-model/server/llama-server.exe' } else { Join-Path $projectRoot '.venv/Scripts/python.exe' }
            # PID reuse must never stop a different program.
            if ($serviceProcess.Path -and $serviceProcess.Path -eq $expectedPath) {
                Stop-Process -Id $serviceId
                Write-Output "$service stopped."
            } else { Write-Output "$service PID no longer identifies the expected executable; left running." }
        }
    }
}
