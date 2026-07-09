#!/usr/bin/env python3
"""
Deployment/server.py - Enterprise Unified Microservice Launcher (Pure Python Orchestrator)
==========================================================================================
Launches all 4 core layers of the AI Fraud Detection Stack within a single terminal window,
completely eliminating legacy `.bat` pop-ups, third-party PM2/Docker overhead, and duplicate 
dependency installations.

Usage:
------
    uv run python Deployment/server.py
        or (if inside Deployment/ directory):
    uv run python server.py

Features:
---------
• Zero Console Pop-ups: Uses `creationflags=CREATE_NO_WINDOW` (`0x08000000`) on Windows to ensure 
  child processes never open annoying separate DOS/command prompt windows.
• Unified Real-time Logging: Pipes STDOUT/STDERR from all 4 services and displays them with colored 
  service prefixes (`[AI Engine]`, `[Orchestrator]`, `[Web3 Worker]`, `[React UI]`) right here.
• Instant Graceful Shutdown: Intercepts `Ctrl+C` (`SIGINT`) and terminates the entire process tree cleanly.
"""

import os
import sys
import time
import signal
import subprocess
import threading
from pathlib import Path

# Windows process creation flag to suppress command prompt window popups
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Colors for terminal output
COLOR_AI = "\033[96m"      # Cyan
COLOR_ORCH = "\033[92m"    # Green
COLOR_WEB3 = "\033[95m"    # Magenta
COLOR_UI = "\033[93m"      # Yellow
COLOR_SYS = "\033[97m"     # White
COLOR_RESET = "\033[0m"

# Store active child process references
ACTIVE_PROCESSES = []
SHUTDOWN_EVENT = threading.Event()

def stream_logs(proc: subprocess.Popen, prefix: str, color: str):
    """Reads STDOUT from a child process line-by-line and prints with colored prefix."""
    try:
        for line in iter(proc.stdout.readline, b''):
            if SHUTDOWN_EVENT.is_set():
                break
            if not line:
                break
            text = line.decode('utf-8', errors='ignore').rstrip()
            if text:
                print(f"{color}{prefix:<16}{COLOR_RESET} | {text}", flush=True)
    except Exception:
        pass
    finally:
        if proc.stdout:
            proc.stdout.close()

def terminate_process_tree(proc: subprocess.Popen):
    """Terminates a process and its entire child process tree across OS platforms."""
    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            # On Windows, kill the entire process tree using taskkill /T /F
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW
            )
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
            proc.kill()
        except Exception:
            pass

def cleanup_all(*args):
    """Signal handler executed on Ctrl+C or script termination."""
    if SHUTDOWN_EVENT.is_set():
        return
    SHUTDOWN_EVENT.set()
    print(f"\n{COLOR_SYS}[SYSTEM] Intercepted shutdown signal. Gracefully stopping all services...{COLOR_RESET}", flush=True)
    
    for proc in reversed(ACTIVE_PROCESSES):
        terminate_process_tree(proc)
        
    print(f"{COLOR_SYS}[SYSTEM] All microservice ports freed and terminated cleanly.{COLOR_RESET}\n", flush=True)
    sys.exit(0)

def main():
    # Register Ctrl+C / SIGTERM signal handlers
    signal.signal(signal.SIGINT, cleanup_all)
    signal.signal(signal.SIGTERM, cleanup_all)

    # Resolve paths relative to this script folder (Deployment/)
    deployment_dir = Path(__file__).resolve().parent
    root_dir = deployment_dir.parent
    frontend_dir = deployment_dir / "frontend"
    db_dir = deployment_dir / "database"
    db_path = db_dir / "offchain_fraud_detection.db"

    # Set up shared environment variables
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONPATH"] = f"{root_dir};{deployment_dir}"
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["ORCHESTRATOR_URL"] = "http://localhost:8000/api/v1/history"
    env["VITE_PROXY_TARGET"] = "http://localhost:8000"

    print(f"{COLOR_SYS}{'='*64}")
    print(f"  Unified AI Fraud Detection Stack Launcher (Zero Pop-ups)")
    print(f"{'='*64}{COLOR_RESET}")
    print(f"{COLOR_SYS}[SYSTEM] Launching all 4 microservice layers in background processes...{COLOR_RESET}\n", flush=True)

    # Define the 4 services
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    services = [
        {
            "name": "[AI Engine]",
            "color": COLOR_AI,
            "cmd": ["uv", "run", "uvicorn", "ai_engine.app:app", "--host", "0.0.0.0", "--port", "8002", "--reload"],
            "cwd": str(deployment_dir)
        },
        {
            "name": "[Orchestrator]",
            "color": COLOR_ORCH,
            "cmd": ["uv", "run", "uvicorn", "orchestrator.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
            "cwd": str(deployment_dir)
        },
        {
            "name": "[Web3 Worker]",
            "color": COLOR_WEB3,
            "cmd": ["uv", "run", "python", "-m", "web3_worker.alastria_ledger_worker"],
            "cwd": str(deployment_dir)
        },
        {
            "name": "[React UI]",
            "color": COLOR_UI,
            "cmd": [npm_cmd, "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"],
            "cwd": str(frontend_dir)
        }
    ]

    # Launch each service
    for s in services:
        print(f"{s['color']} -> Starting {s['name']} inside {s['cwd']}...{COLOR_RESET}", flush=True)
        try:
            proc = subprocess.Popen(
                s["cmd"],
                cwd=s["cwd"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW
            )
            ACTIVE_PROCESSES.append(proc)
            
            # Start background thread to stream logs for this service
            t = threading.Thread(
                target=stream_logs,
                args=(proc, s["name"], s["color"]),
                daemon=True
            )
            t.start()
        except Exception as exc:
            print(f"{COLOR_SYS}[ERROR] Failed to start {s['name']}: {exc}{COLOR_RESET}", flush=True)
            cleanup_all()

    print(f"\n{COLOR_SYS}{'+'*64}")
    print(f" [+] All services running inside this single terminal!")
    print(f" [+] React UI Dashboard:       http://localhost:5173")
    print(f" [+] Orchestrator Swagger API: http://localhost:8000/docs")
    print(f" [+] AI Engine Swagger API:    http://localhost:8002/docs")
    print(f" [!] Press Ctrl+C anytime here to shut down all 4 services cleanly.")
    print(f"{'+'*64}{COLOR_RESET}\n", flush=True)

    # Keep main thread alive monitoring processes
    try:
        while not SHUTDOWN_EVENT.is_set():
            time.sleep(1)
            # Check if any critical process died unexpectedly
            all_dead = all(proc.poll() is not None for proc in ACTIVE_PROCESSES)
            if all_dead and ACTIVE_PROCESSES:
                print(f"\n{COLOR_SYS}[SYSTEM] All child processes exited.{COLOR_RESET}", flush=True)
                break
    except KeyboardInterrupt:
        cleanup_all()

if __name__ == "__main__":
    main()
