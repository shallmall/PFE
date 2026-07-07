@echo off
echo ========================================================
echo   Starting AI Fraud Detection System (Backend + Frontend)
echo ========================================================

echo [*] Launching Layer 1: AI Classification Engine (Port 8002)...
start "AI Engine (Port 8002)" cmd /k "uv run uvicorn ai_engine.app:app --host 0.0.0.0 --port 8002 --reload"

echo [*] Launching Layer 2: Orchestrator Gateway (Port 8000)...
start "Orchestrator (Port 8000)" cmd /k "uv run uvicorn orchestrator.app:app --host 0.0.0.0 --port 8000 --reload"

echo [*] Launching Layer 4: Alastria Web3 Blockchain Worker...
start "Alastria Web3 Worker" cmd /k "uv run python -m web3_worker.alastria_ledger_worker"

echo [*] Launching Vite React Frontend (Port 5173)...
cd frontend && start "Vite Frontend (Port 5173)" cmd /k "npm run dev"

echo.
echo [+] All services launched in separate terminal windows!
echo [+] Access the application at: http://localhost:5173
echo ========================================================
