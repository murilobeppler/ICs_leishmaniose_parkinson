# Inicia Módulo A (peptide-docking): FastAPI (:8001) + Next.js (:3001)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "[Módulo A] Garantindo dados sintéticos..." -ForegroundColor Cyan
uv run --directory modules/peptide-docking/backend python scripts/make_synthetic_library.py

$pnpmCmd = if (Get-Command pnpm.cmd -ErrorAction SilentlyContinue) { "pnpm.cmd" } else { "pnpm" }

Write-Host "[Módulo A] Iniciando FastAPI na porta 8001..." -ForegroundColor Green
$apiProcess = Start-Process -FilePath "uv" -ArgumentList @("run", "--directory", "modules/peptide-docking/backend", "uvicorn", "peptide_docking.api:app", "--reload", "--port", "8001") -PassThru

Write-Host "[Módulo A] Iniciando Next.js na porta 3001..." -ForegroundColor Green
$frontProcess = Start-Process -FilePath $pnpmCmd -ArgumentList @("--filter", "@ic-research-lab/peptide-docking-frontend", "dev") -PassThru

Write-Host "`nAmbiente Módulo A ativo:" -ForegroundColor Yellow
Write-Host "  - API Docs:  http://127.0.0.1:8001/docs"
Write-Host "  - Frontend:  http://localhost:3001"
Write-Host "`nPressione Enter para encerrar ambos os processos..." -ForegroundColor Gray
Read-Host

Stop-Process -Id $apiProcess.Id -ErrorAction SilentlyContinue
Stop-Process -Id $frontProcess.Id -ErrorAction SilentlyContinue
Write-Host "[Módulo A] Encerrado." -ForegroundColor Red

