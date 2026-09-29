# Windows launcher: .\rw.ps1 <command> [args]  (same as python rw.py)
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { Write-Error "python not found"; exit 1 }
& $py.Source (Join-Path $PSScriptRoot "rw.py") @args
exit $LASTEXITCODE
