# AI-Based Decentralized Reputation & E-Commerce Fraud Detection Framework

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.4+-ee4c2c.svg)](https://pytorch.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg)](https://fastapi.tiangolo.com/)
[![Web3.py](https://img.shields.io/badge/Web3.py-Alastria%20Red%20T-f16822.svg)](https://web3py.readthedocs.io/)
[![React](https://img.shields.io/badge/React-18.x-61dafb.svg)](https://react.dev/)

An enterprise-grade hybrid AI & Blockchain architecture designed to detect deceptive e-commerce reviews, fake reviewer recruitment campaigns, and organized collusion rings. The system evaluates semantic text anomalies using **DeBERTa-v3**, models relational network structures using a **Heterogeneous Graph Transformer (HGT)**, and immutably anchors final reputation scores directly onto an Ethereum-compatible distributed ledger (**Alastria Red T**).

---

## System Architecture & Directory Structure

```text
gnn_fraud_detection/
├── Deployment/                              # Production Stack (API, Web3 Worker, Database & Frontend)
│   ├── ai_engine/                           # Singleton AI Model Loader & Feature Engineering Engine
│   ├── database/                            # SQLite Off-Chain Metadata & Initial Setup (`init_db.py`)
│   ├── frontend/                            # Modern React + Vite + Tailwind CSS User Interface
│   ├── orchestrator/                        # FastAPI Asynchronous REST Service & Batch Handlers
│   ├── verifier/                            # Public Read-Only Blockchain Verification CLI Tools
│   ├── web3_worker/                         # Alastria Ledger Background Anchor & Smart Contract Workers
│   └── ReputationLedger.sol                 # Solidity Smart Contract for Immutable On-Chain Storage
├── HGT_Heterogeneous_Graph_Model/           # Relational Graph Neural Network (`PyTorch Geometric`)
├── SpamVis_DeBERTa-v3-base_Model/           # Semantic NLP Scorer (`Transformers` & `best_threshold.json`)
├── late_Fusion_Score-Level_Integration/     # LightGBM / XGBoost Ensemble Training & Threshold Tuning
├── data/                                    # Public Datasets (`public_reviews_dataset_cleaned.csv`)
├── requirements.txt                         # Categorized Python Package Dependencies (for `pip`)
└── pyproject.toml                           # Project Metadata & Configuration (for `uv`)
```

---

## Dataset Download & Setup Note

Because the cleaned e-commerce reviews dataset (`public_reviews_dataset_cleaned.csv`) is **~267 MB**, it exceeds GitHub's standard 100 MB file limit.
To prepare the dataset:
1. Go to the public benchmark dataset repository: [https://github.com/bretthollenbeck/fake-reviews-data](https://github.com/bretthollenbeck/fake-reviews-data) (or the project's Release assets) and download the CSV data.
2. Place the downloaded CSV file directly inside your `./data` directory so the path is:
   ```text
   ./data/public_reviews_dataset_cleaned.csv
   ```

---

## Installation & Setup Guide

### 1. Prerequisites Verification (`Node.js` & `uv`)
Before installing the backend dependencies, verify that you have `Node.js` and `npm` installed on your system:
```powershell
node -v
npm -v
```
*(Requires Node.js version `20.x` or higher to manage the React frontend and background process workers).*

Next, ensure you have **`uv`** installed. `uv` is an **ultra-fast Rust-based Python package and virtual environment manager** that resolves deep learning dependencies instantly:
```powershell
# On Windows PowerShell:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# On Linux/macOS:
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

### 2. AI System Setup (`uv sync`)

To initialize the entire AI system, you do not need manual `virtualenv` or `pip install -r requirements.txt` steps. **`uv sync` does everything automatically**: it reads `pyproject.toml`, creates a clean isolated `.venv` virtual environment inside `./`, and downloads exact PyTorch, PyG, Transformers, and Web3 libraries in seconds.

Run this command directly from the root folder (`./`):
```powershell
uv sync
```

> **WARNING: CUDA Architecture Compatibility**  
> By default, `pyproject.toml` and `requirements.txt` target **NVIDIA CUDA 12.1** (`+cu121`) acceleration (`https://download.pytorch.org/whl/cu121`). If you are running on a machine without an NVIDIA GPU (such as Apple Silicon Mac, AMD GPU, or pure CPU), adjust the PyTorch wheel index URL inside `pyproject.toml` to match your local hardware before running `uv sync`.

---

### 3. Frontend UI Setup
To install the package dependencies for the modern React web interface:
```powershell
cd ./Deployment/frontend
npm install
cd ../..
```

---

## Running the Platform Locally

Once your Python environment (`uv sync`), Node.js environment (`npm install`), and dataset (`./data/public_reviews_dataset_cleaned.csv`) are ready, initialize the database and start the entire platform:

### 1. Initialize & Seed the SQLite Database
Run the initialization script directly from your root directory (`./`):
```powershell
uv run python ./Deployment/database/init_db.py
```

### 2. Launch All Microservices with `server.py` (Master Orchestrator)
Instead of opening four separate terminal windows for the AI Engine, FastAPI Orchestrator, Alastria Web3 Worker, and React UI, run our unified master launcher:
```powershell
uv run python ./Deployment/server.py
```
`server.py` automatically boots all four microservice layers (`AI Engine`, `FastAPI Orchestrator on port 8000`, `Alastria Web3 Worker`, and `React UI on port 5173`) inside a single terminal with real-time color-coded logging and zero pop-up windows. Press `Ctrl+C` at any time to cleanly shut down the entire system at once.

---

### Alternative: Manual Multi-Terminal Launch (If running services individually)

#### A. Start the Backend API & AI Engine (Terminal 1)
```powershell
uv run uvicorn Deployment.orchestrator.main:app --host 0.0.0.0 --port 8000 --reload
```
*API Swagger Documentation will be available at: `http://localhost:8000/docs`*

#### B. Start the React Frontend Dashboard (Terminal 2)
```powershell
cd Deployment/frontend
npm run dev
```
*The web dashboard will open at: `http://localhost:5173`*

### 4. Run the Blockchain Ledger Worker (Optional / Background Daemon)
To process batches of `Confirmed_OffChain` reviews and anchor them immutably to the Alastria Red T smart contract (`ReputationLedger.sol`):
```powershell
# Directly via Python:
uv run python Deployment/web3_worker/alastria_ledger_worker.py

# Or continuously in the background using PM2:
npm install -g pm2
pm2 start ".venv/Scripts/python.exe" --name "alastria-worker" -- Deployment/web3_worker/alastria_ledger_worker.py
```

---

## Public Verification CLI (`public_verifier_cli.py`)

Independent auditors or consumers can verify any score on the blockchain without accessing the local database:

```powershell
# Verify an individual review directly from the smart contract by Review ID (0x...):
uv run python Deployment/verifier/public_verifier_cli.py --review-id 0x1234567890abcdef1234567890abcdef

# Verify a mining receipt transaction hash directly on-chain:
uv run python Deployment/verifier/public_verifier_cli.py --tx-hash 0xabcdef...
```

---

## License
This project is developed as part of an academic thesis on Decentralized E-Commerce Fraud Detection & Reputation Management.
