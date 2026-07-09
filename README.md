# AI-Based Decentralized Reputation & E-Commerce Fraud Detection Framework

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.4+-ee4c2c.svg)](https://pytorch.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg)](https://fastapi.tiangolo.com/)
[![Web3.py](https://img.shields.io/badge/Web3.py-Alastria%20Red%20T-f16822.svg)](https://web3py.readthedocs.io/)
[![React](https://img.shields.io/badge/React-18.x-61dafb.svg)](https://react.dev/)

An enterprise-grade hybrid AI & Blockchain architecture designed to detect deceptive e-commerce reviews, fake reviewer recruitment campaigns, and organized collusion rings. The system evaluates semantic text anomalies using **DeBERTa-v3**, models relational network structures using a **Heterogeneous Graph Transformer (HGT)**, and immutably anchors final reputation scores directly onto an Ethereum-compatible distributed ledger (**Alastria Red T**).

---

## 🏛️ System Architecture & Directory Structure

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

## 📦 Dataset Download & Setup Note

Because the raw reviews dataset (`public_reviews_dataset_cleaned.csv`) is **~267 MB**, it exceeds GitHub's standard 100 MB file limit. 
To run the full training pipelines or initial database seed:
1. Download the cleaned reviews dataset from the project's **GitHub Releases** or public repository link.
2. Place the file inside the `data/` directory so its path is exact:
   ```text
   gnn_fraud_detection/data/public_reviews_dataset_cleaned.csv
   ```

---

## 🚀 Installation & Setup Guide

When cloning this project from GitHub, you can set up the Python backend using either **Option A (Modern & Ultra-Fast via `uv`)** or **Option B (Standard Python via `pip`)**. Both methods fully support CUDA GPU acceleration on Windows and Linux.

### Prerequisites (For All Installation Methods)
* **Python**: Version `3.11` or `3.12` recommended.
* **Node.js & npm**: Version `20.x` or higher (required for the web frontend UI and PM2 worker management).

---

### Option A: Installation via `uv` (Recommended for Speed & Cleanliness)

[`uv`](https://github.com/astral-sh/uv) is an ultra-fast Rust-based Python environment manager that automatically resolves GPU wheel dependencies without conflicts.

1. **Install `uv` (if not already installed)**:
   ```powershell
   # On Windows PowerShell:
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   
   # On Linux/macOS:
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
2. **Clone the repository and sync the virtual environment**:
   ```powershell
   git clone https://github.com/yourusername/gnn_fraud_detection.git
   cd gnn_fraud_detection
   
   # Automatically create .venv and download exact PyTorch + CUDA dependencies
   uv sync
   ```

---

### Option B: Installation via Standard `pip`

If you prefer standard Python virtual environments, use `requirements.txt`:

1. **Clone the repository**:
   ```powershell
   git clone https://github.com/yourusername/gnn_fraud_detection.git
   cd gnn_fraud_detection
   ```
2. **Create and activate a virtual environment**:
   ```powershell
   # On Windows:
   python -m venv venv
   .\venv\Scripts\activate
   
   # On Linux/macOS:
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install exact dependencies**:
   ```powershell
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

### Frontend UI Setup (`Node.js` & `npm`)

To install the dependencies for the modern React web interface:

```powershell
cd Deployment/frontend
npm install
cd ../..
```

---

## ⚡ Running the Platform Locally

Once your Python and Node.js environments are initialized, run the following steps to start the complete system:

### 1. Initialize & Seed the Off-Chain SQLite Database
```powershell
# Using uv:
uv run python Deployment/database/init_db.py

# Using standard pip (inside activated venv):
python Deployment/database/init_db.py
```

### 2. Start the Backend API & AI Engine
Open **Terminal 1** and start the FastAPI orchestrator service:
```powershell
# Using uv:
uv run uvicorn Deployment.orchestrator.main:app --host 0.0.0.0 --port 8000 --reload

# Using standard pip:
uvicorn Deployment.orchestrator.main:app --host 0.0.0.0 --port 8000 --reload
```
*API Swagger Documentation will be available at: `http://localhost:8000/docs`*

### 3. Start the React Frontend Dashboard
Open **Terminal 2** and start the Vite development server:
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

## 🔍 Public Verification CLI (`public_verifier_cli.py`)

Independent auditors or consumers can verify any score on the blockchain without accessing the local database:

```powershell
# Verify an individual review directly from the smart contract by Review ID (0x...):
uv run python Deployment/verifier/public_verifier_cli.py --review-id 0x1234567890abcdef1234567890abcdef

# Verify a mining receipt transaction hash directly on-chain:
uv run python Deployment/verifier/public_verifier_cli.py --tx-hash 0xabcdef...
```

---

## 📄 License
This project is developed as part of an academic thesis on Decentralized E-Commerce Fraud Detection & Reputation Management.
