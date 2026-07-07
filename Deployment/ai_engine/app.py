import os
import sys
import gc
import json
import urllib.request
import urllib.error
from fastapi import FastAPI, HTTPException, status

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_engine.schemas import ReviewBatchInput, HistoryRequest, HistoryResponse, ScoreResultPayload
from ai_engine.model_loader import model_loader
from ai_engine.graph_builder import build_localized_subgraph
from ai_engine.feature_engine import compute_late_fusion_scores

app = FastAPI(
    title="Layer 1: AI Classification Engine",
    description="Compute-bound Inference & Localized Subgraph Attention Microservice",
    version="1.0.0"
)

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000/api/v1/history")

def post_json(url: str, payload: dict, timeout: float = 120.0) -> dict:
    data = json.dumps(payload, default=str).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        err_text = exc.read().decode('utf-8', errors='ignore')
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to fetch historical context from Orchestrator: {err_text}")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Could not connect to Orchestrator at {url}: {str(exc)}")

@app.on_event("startup")
def startup_event():
    model_loader.initialize()

@app.post("/v1/score_batch", response_model=ScoreResultPayload)
def score_review_batch(batch: ReviewBatchInput):
    """
    Main Compute Handler for Layer 1:
    1. Determines zero-leakage chronological boundary
    2. API Call 2: Requests historical subgraph context from Layer 2 Data Orchestration Controller
    3. Builds localized in-memory subgraph and computes HGT GNN anomaly scores
    4. Executes 2-Feature Late Fusion (DeBERTa + HGT) scoring
    5. Flushes localized subgraph from RAM/VRAM immediately
    6. Returns scored payload
    """
    if not batch.reviews:
        return ScoreResultPayload(submitter_id=batch.submitter_id, results=[])
        
    # 1. Zero-leakage chronological boundary: earliest review timestamp in the incoming batch
    earliest_date = min(r.review_date for r in batch.reviews)
    
    # 2. API Call 2: Request historical context from Layer 2
    hist_req = {"submitter_id": batch.submitter_id, "current_timestamp": earliest_date.isoformat()}
    hist_data = post_json(ORCHESTRATOR_URL, hist_req)
    history = HistoryResponse(**hist_data)
            
    # 3. Build localized subgraph in RAM/VRAM & compute HGT structural scores
    try:
        hgt_scores = build_localized_subgraph(history, batch)
        
        # 4. Execute Late Fusion classification with historical context
        score_payload = compute_late_fusion_scores(batch, hgt_scores, history)
    finally:
        # 5. Ephemeral Teardown: Flush localized graph from memory immediately!
        del history
        if 'hgt_scores' in locals():
            del hgt_scores
        gc.collect()
        
    return score_payload

