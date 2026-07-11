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
./
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
1. Go to the public benchmark dataset repository: [https://github.com/bretthollenbeck/fake-reviews-data](https://github.com/bretthollenbeck/fake-reviews-data).
2. Download the **CSV version of the dataset** (compressed archive/zip).
3. **Unzip/extract** the downloaded archive.
4. Place the unzipped CSV file (`public_reviews_dataset_cleaned.csv`) directly inside your **`./data`** directory so that the exact relative path is:
   ```text
   ./data/public_reviews_dataset_cleaned.csv
   ```

---

## Pre-Trained DeBERTa Model Setup

The core NLP classification engine relies on a heavily fine-tuned DeBERTa-v3 model. You have two options to prepare this model:

**Option 1: Download the Fine-Tuned Model (Recommended)**
1. Download the pre-trained model weights from Google Drive: [https://drive.google.com/file/d/12JV-zwgF8m4ZWuISgzGp5ZsrKqyd9w0c/view?usp=sharing](https://drive.google.com/file/d/12JV-zwgF8m4ZWuISgzGp5ZsrKqyd9w0c/view?usp=sharing)
2. Extract the downloaded `.zip` file.
3. Place all extracted contents directly into the following folder so the inference script can find them:
   ```text
   ./SpamVis_DeBERTa-v3-base_Model
   ```

**Option 2: Fine-Tune it Yourself**
If you prefer to train the semantic model from scratch on your own GPU, you can run the interactive training workflow using the provided Jupyter Notebook:
`./SpamVis_DeBERTa-v3-base_Model/DeBERTa V3 Training Notebook.ipynb`

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
uv add gensim textstat vaderSentiment nltk
```

**CRITICAL: Install PyTorch Geometric Hardware Extensions**
Because the Graph Neural Network (HGT) relies on C++ extensions that must precisely match your local hardware (Mac/Apple Silicon, Windows AMD, or NVIDIA CUDA), we have provided an automated script. 

**Order matters:** You must run this script *strictly after* `uv sync` finishes. The script uses the PyTorch library installed by `uv sync` to automatically detect your exact hardware architecture and fetch the matching C++ binaries without crashing.
```powershell
uv run python install_pyg.py
```

> **WARNING: Hardware-Dependent Libraries (CUDA Compatibility)**  
> Disclaimer: Deep learning libraries such as `torch`, `torchvision`, and the PyTorch Geometric C++ extensions (`pyg-lib`, `torch-scatter`, etc.) are heavily affected by your specific GPU architecture and CUDA version. By default, `pyproject.toml` and `requirements.txt` target **NVIDIA CUDA 12.1** (`+cu121`) acceleration (`https://download.pytorch.org/whl/cu121`). If you are running on a machine without an NVIDIA GPU (such as Apple Silicon Mac, AMD GPU, or pure CPU), you must adjust the PyTorch wheel index URL inside `pyproject.toml` to match your local hardware before running `uv sync` to prevent installation crashes (e.g. `WinError 127`).

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

## Experimental Benchmarks & Code Roadmap

This repository is structured around three core empirical experiments evaluated across the academic thesis, along with a live blockchain verification tool. Each experiment corresponds directly to a dedicated directory in the project root:

### 1. Experiment 1: Baseline Machine Learning Classifiers (`./baseline_experiment`)
Contains the complete code for evaluating standard ML baselines on both review-centric text metrics and reviewer-centric behavioral metrics:
* **Text-Centric Baseline Models**: Logistic Regression, Random Forest, XGBoost, and LightGBM (`train_text_centric_model.py`).
* **Behavioral-Centric Baseline Models**: Evaluates reviewer metadata anomalies and statistical patterns (`train_behavior_centric_model.py`).
* **Linear Blending Ensemble**: Evaluates optimal score-level blending of text and behavioral predictions (`evaluate_linear_blending_ensemble.py`).

### 2. Experiment 2: Semantic Transformer Fine-Tuning (`./SpamVis_DeBERTa-v3-base_Model`)
Contains the Jupyter notebooks and scripts used to fine-tune the **DeBERTa-v3-base** transformer model (`microsoft/deberta-v3-base`) for advanced semantic fraud detection and review text classification across the e-commerce dataset (`run_deberta_csv_inference.py`, `evaluate_deberta.py`, and interactive `.ipynb` training workflows).

### 3. Experiment 3: Heterogeneous Graph Transformer & Late Fusion (`./HGT_Heterogeneous_Graph_Model` & `./late_Fusion_Score-Level_Integration`)
The culmination of the thesis architecture, capturing complex structural network topologies and fusing them with semantic language representations:
* **`./HGT_Heterogeneous_Graph_Model`**: Contains the PyTorch Geometric training script (`train.py`) and model definitions (`models.py`, `dataset.py`) for the Heterogeneous Graph Transformer (HGT) across bipartite `Reviewer <-> Review` graphs.
* **`./late_Fusion_Score-Level_Integration`**: Contains the code for combining DeBERTa-v3 semantic scores with HGT graph embeddings via gradient boosting meta-classifiers (`train_late_fusion_models.py`), achieving optimal macro F1 and AUC performance across both reviewer recruitment rings and fake review text.

### 4. Cryptographic Blockchain Ledger Verification (`./Deployment/verifier/public_verifier_cli.py`)
Provides a command-line interface (`public_verifier_cli.py`) that interacts directly with the live **Alastria Red T** decentralized blockchain network (`ReputationLedger.sol`). Independent auditors can cryptographically verify any review reputation score, transaction hash (`0x...`), or mining block confirmation receipt directly on-chain without requiring access to our internal SQLite database.

---

## Public Verification CLI (`public_verifier_cli.py`)

Independent auditors or consumers can verify any score on the blockchain without accessing the local database:

```powershell
# Verify an individual review directly from the smart contract by Review ID (0x...):
uv run python ./Deployment/verifier/public_verifier_cli.py --review-id 0x1234567890abcdef1234567890abcdef

# Verify a mining receipt transaction hash directly on-chain:
uv run python ./Deployment/verifier/public_verifier_cli.py --tx-hash 0xabcdef...
```

---

## License
This project is developed as part of an academic thesis on Decentralized E-Commerce Fraud Detection & Reputation Management.
