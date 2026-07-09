# Complete PC Migration & Full Stack Setup Guide (`gnn_fraud_detection`)

This document is your **complete end-to-end instruction manual** when transferring the `gnn_fraud_detection` platform to a new Windows PC. It covers installing all required toolchains (`uv` for Python, `Node.js` & `npm` for Frontend/PM2), rebuilding virtual environments, initializing the database, and launching the services.

---

## Important: Before Transferring / Copying the Folder
When copying the project folder (`gnn_fraud_detection`) to a USB drive or transferring it over network/cloud to the new PC:
* **DO NOT copy the `.venv` folder**: Virtual environments contain hardcoded absolute paths specifically tied to your old PC's username (`laake`). Copying `.venv` will break Python execution on the new computer.
* **DO NOT copy `node_modules` folders**: Like `.venv`, `node_modules` can contain OS-specific binaries.
* **DO copy all `.toml`, `.json`, `.lock`, and source code files!**

---

## Part 1: Install Required Prerequisites on the New PC

Before running any code on the new Windows PC, install these two core package managers:

### 1. Install `uv` (Fast Python Package & Environment Manager)
Open PowerShell on the new PC and run the official standalone installer:
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
*After running, **close and reopen your terminal window** so `uv` is available in your `PATH`.* Verify by running `uv --version`.

### 2. Install `Node.js` & `npm` (For React Frontend & PM2 Process Manager)
Download and run the **Node.js LTS (Long Term Support)** Windows installer from the official website:
**[Download Node.js LTS (v20.x or v22.x)](https://nodejs.org/en/download/)**

After installing, verify in PowerShell:
```powershell
node -v
npm -v
```

### 3. Install `PM2` Globally (Process Manager)
Run this command in PowerShell to install PM2 so you can manage background workers:
```powershell
npm install -g pm2
```

---

## Part 2: Setup Python AI Backend Engine (`uv`)

Once you place the `gnn_fraud_detection` directory on your new PC (for example, inside `C:\Projects\gnn_fraud_detection` or `Downloads`), set up all Python dependencies:

```powershell
# 1. Open terminal inside the project root directory
cd path\to\gnn_fraud_detection

# 2. Tell uv to sync dependencies and build a fresh 100% clean .venv for the new PC
uv sync
```
> [!NOTE]
> `uv sync` reads `pyproject.toml` and `uv.lock`, automatically downloads the correct Python version (if not already installed), and builds the `.venv` in seconds.

### Verify Python Backend & AI Model Loader
Test that the exact threshold JSON files (`0.47` & `0.70`), DeBERTa, and LightGBM models load properly:
```powershell
# Verify syntax across core backend engines
uv run python -m py_compile HGT_Heterogeneous_Graph_Model/train.py Deployment/ai_engine/model_loader.py Deployment/ai_engine/feature_engine.py

# Initialize database schema and pre-seed initial review records
uv run python Deployment/database/init_db.py
```

---

## Part 3: Setup React Frontend & UI (`npm`)

Now initialize the modern React + Vite + Tailwind CSS frontend interface located inside `Deployment/frontend`:

```powershell
# 1. Navigate into the frontend folder
cd Deployment/frontend

# 2. Install all frontend dependencies (React, Tailwind, Vite, Lucide Icons)
npm install
```

---

## Part 4: Running the Full Stack on the New PC

When you are ready to run the complete system locally, open **two separate terminal windows**:

### Terminal 1: Start React Frontend UI
```powershell
cd path\to\gnn_fraud_detection\Deployment\frontend
npm run dev
```
*The frontend interface will launch and be accessible at `http://localhost:5173`.*

### Terminal 2: Run Backend / Alastria Ledger Workers (or use PM2)
To run backend verification workers directly:
```powershell
cd path\to\gnn_fraud_detection
uv run python Deployment/web3_worker/alastria_ledger_worker.py
```

Or to run them continuously in the background using **PM2**:
```powershell
cd path\to\gnn_fraud_detection

# Start worker using PM2 and your uv virtual environment python
pm2 start ".venv\Scripts\python.exe" --name "alastria-worker" -- Deployment/web3_worker/alastria_ledger_worker.py

# Check status of all PM2 background processes
pm2 status

# View real-time output logs
pm2 logs alastria-worker
```

---

## Troubleshooting Checklist on New PC
* **If `uv` command is not found:** Manually add `$HOME\.local\bin` or `$HOME\.cargo\bin` to Windows Environment Variables (`PATH`) and restart terminal.
* **If `npm` command is not found:** Ensure Node.js was checked to "Add to PATH" during installation.
* **If AI models fail to load:** Ensure all model weights (`.pth` / `.joblib` / `deberta_predictions_output.csv`) were fully transferred and not skipped during file copy!
