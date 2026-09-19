# ==============================================================================
# NammaSignal Comprehensive Automated Test Suite Runner
# ==============================================================================
Write-Host "Executing NammaSignal Automated Test Suite (Unit, Cedar, Integration, Adversarial)..." -ForegroundColor Cyan
python -m pytest tests/ -v
