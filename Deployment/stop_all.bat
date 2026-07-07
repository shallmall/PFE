@echo off
echo [*] Stopping all running system services...
taskkill /F /FI "WINDOWTITLE eq AI Engine (Port 8002)*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Orchestrator (Port 8000)*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Alastria Web3 Worker*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Vite Frontend (Port 5173)*" /T >nul 2>&1
echo [+] All system services stopped cleanly!
