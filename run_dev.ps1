# ==============================================================================
# NammaSignal One-Command Developer / Demo Launcher
# ==============================================================================
Write-Host "Starting NammaSignal Intelligence Engine..." -ForegroundColor Cyan
Write-Host "Opening web dashboard at: http://localhost:8000" -ForegroundColor Green

python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
