# Inicia Módulo B (fog-gnn): FastAPI (:8002) + Next.js (:3002)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "[Módulo B] Garantindo dados sintéticos IMU e experimento LOSO..." -ForegroundColor Cyan
uv run --directory modules/fog-gnn/backend python scripts/make_synthetic_imu.py

$pnpmCmd = if (Get-Command pnpm.cmd -ErrorAction SilentlyContinue) { "pnpm.cmd" } else { "pnpm" }

Write-Host "[Módulo B] Iniciando FastAPI na porta 8002..." -ForegroundColor Green
$apiProcess = Start-Process -FilePath "uv" -ArgumentList @("run", "--directory", "modules/fog-gnn/backend", "uvicorn", "fog_gnn.api:app", "--reload", "--port", "8002") -PassThru

Write-Host "[Módulo B] Iniciando Next.js na porta 3002..." -ForegroundColor Green
$frontProcess = Start-Process -FilePath $pnpmCmd -ArgumentList @("--filter", "@ic-research-lab/fog-gnn-frontend", "dev") -PassThru

Write-Host "`nAmbiente Módulo B ativo:" -ForegroundColor Yellow
Write-Host "  - API Docs:  http://127.0.0.1:8002/docs"
Write-Host "  - Frontend:  http://localhost:3002"
Write-Host "`nPressione Enter para encerrar ambos os processos..." -ForegroundColor Gray
Read-Host

Stop-Process -Id $apiProcess.Id -ErrorAction SilentlyContinue
Stop-Process -Id $frontProcess.Id -ErrorAction SilentlyContinue
Write-Host "[Módulo B] Encerrado." -ForegroundColor Red

