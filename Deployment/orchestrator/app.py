import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Request, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_db, engine, Base
from database.models import Submitter
from orchestrator.schemas import (
    ReviewBatchInput, HistoryRequest, HistoryResponse,
    ScoreResultPayload, BatchReportResponse,
    BatchReviewSubmissionResponse, ReviewerScoreSummary, ProductScoreSummary,
    ReviewAuditLogItem, LedgerStatusResponse, LedgerSyncResponse,
    SubmitterCreateRequest, SubmitterUpdateRequest, SubmitterResponse
)
from orchestrator.services import (
    validate_submitter, get_historical_context,
    ensure_batch_nodes, save_ai_results,
    get_aggregated_reviewer_scores, get_aggregated_product_scores,
    get_review_audit_log, get_ledger_status_service, execute_manual_ledger_sync_service
)

app = FastAPI(
    title="Layer 2: Data Orchestration Controller & API Gateway",
    description="Decoupled IO-bound API Gateway, Entity Reputation Dashboard, and Alastria Web3 Orchestrator",
    version="2.0.0"
)

AI_ENGINE_URL = os.getenv("AI_ENGINE_URL", "http://localhost:8002/v1/score_batch")

def post_json(url: str, payload: dict, timeout: float = 120.0) -> dict:
    data = json.dumps(payload, default=str).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        err_text = exc.read().decode('utf-8', errors='ignore')
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI Engine inference failed: {err_text}")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Could not connect to AI Engine at {url}: {str(exc)}")

@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE submitters ADD COLUMN created_at TIMESTAMP"))
            conn.commit()
    except Exception:
        pass

@app.post("/api/v1/history", response_model=HistoryResponse, tags=["Internal AI Engine"])
def fetch_history(req: HistoryRequest, db: Session = Depends(get_db)):
    """
    API Call 2 Handler: Called by AI Classification Engine to fetch zero-leakage
    chronologically bounded historical subgraph nodes for a specific submitter.
    """
    return get_historical_context(db, req.submitter_id, req.current_timestamp)

@app.post("/api/v1/results", tags=["Internal AI Engine"])
def receive_results(payload: ScoreResultPayload, db: Session = Depends(get_db)):
    """
    API Call 3 Handler: Called by AI Classification Engine to persist final
    fraud probabilities, classification labels, and smart contract tx hashes.
    """
    updated_count = save_ai_results(db, payload.submitter_id, payload)
    return {"status": "success", "updated_records": updated_count}

@app.post("/api/v1/submit_batch", response_model=BatchReviewSubmissionResponse, tags=["Batch Ingestion"])
@app.post("/api/v1/reviews/batch_submit", response_model=BatchReviewSubmissionResponse, tags=["Batch Ingestion"])
def submit_review_batch(batch: ReviewBatchInput, db: Session = Depends(get_db)):
    """
    Phase 1, 4 & 6 Handler: Main entry point for Enterprise Submitters / CLI / Portal.
    1. Validates API Key & Credentials
    2. Ensures nodes exist & saves reviews as 'Pending'
    3. Forwards batch to Layer 1 AI Classification Engine
    4. Persists confirmed scores & updates entity reputations
    5. Computes & returns aggregated Reviewer and Reviewee/Product scores!
    """
    # 1. Validate credentials & cryptographic signature
    validate_submitter(db, batch.submitter_id, signature=batch.signature, api_key=batch.api_key, reviews=batch.reviews)
    
    # 2. Insert pending nodes into DB
    ensure_batch_nodes(db, batch)
    
    # 3. Forward to Layer 1 AI Classification Engine
    score_data = post_json(AI_ENGINE_URL, batch.dict())
    score_payload = ScoreResultPayload(**score_data)
            
    # 4. Save results to DB
    save_ai_results(db, batch.submitter_id, score_payload)
    
    fraud_count = sum(1 for item in score_payload.results if item.is_fraud == 1)
    
    # 5. Compute aggregated entity reputation scores (Phase 4)
    rev_scores = get_aggregated_reviewer_scores(db, batch.submitter_id)
    prod_scores = get_aggregated_product_scores(db, batch.submitter_id)
    
    return BatchReviewSubmissionResponse(
        submitter_id=batch.submitter_id,
        total_processed=len(score_payload.results),
        fraud_detected=fraud_count,
        reviewers_scores=rev_scores,
        products_scores=prod_scores,
        results=score_payload.results
    )

# ==========================================
#     PHASE 7: DASHBOARD & EXPLORER APIS
# ==========================================

@app.get("/api/v1/reviewers", response_model=list[ReviewerScoreSummary], tags=["Dashboard Tab 1: Reviewers"])
def list_reviewers(submitter_id: str = None, db: Session = Depends(get_db)):
    """Returns aggregated reputation scores and fraud counts for all Reviewers."""
    return get_aggregated_reviewer_scores(db, submitter_id)

@app.get("/api/v1/products", response_model=list[ProductScoreSummary], tags=["Dashboard Tab 2: Reviewees/Products"])
def list_products(submitter_id: str = None, db: Session = Depends(get_db)):
    """Returns aggregated star ratings and AI fraud risk scores for all Products."""
    return get_aggregated_product_scores(db, submitter_id)

@app.get("/api/v1/reviews", response_model=list[ReviewAuditLogItem], tags=["Dashboard Tab 3: Audit Log"])
def list_reviews(submitter_id: str = None, limit: int = 500, db: Session = Depends(get_db)):
    """Returns full chronological review audit log with Web3 transaction hashes."""
    return get_review_audit_log(db, submitter_id=submitter_id, limit=limit)

@app.get("/api/v1/reviews/product/{product_id}", response_model=list[ReviewAuditLogItem], tags=["Explorer"])
def get_product_reviews(product_id: str, db: Session = Depends(get_db)):
    """Returns all reviews and AI scores for a specific product."""
    return get_review_audit_log(db, product_id=product_id)

@app.get("/api/v1/reviews/reviewer/{reviewer_id}", response_model=list[ReviewAuditLogItem], tags=["Explorer"])
def get_reviewer_reviews(reviewer_id: str, db: Session = Depends(get_db)):
    """Returns all reviews submitted by a specific reviewer."""
    return get_review_audit_log(db, reviewer_id=reviewer_id)

# ==========================================
#     PHASE 5: ALASTRIA BLOCKCHAIN LEDGER
# ==========================================

@app.get("/api/v1/ledger/status", response_model=LedgerStatusResponse, tags=["Alastria Blockchain"])
def get_ledger_status(db: Session = Depends(get_db)):
    """Returns real-time Alastria Red T blockchain synchronization status and pending queue counts."""
    return get_ledger_status_service(db)

@app.post("/api/v1/ledger/sync", response_model=LedgerSyncResponse, tags=["Alastria Blockchain"])
def trigger_manual_ledger_sync(db: Session = Depends(get_db)):
    """Triggers an immediate zero-gas Web3 sweep to anchor pending reviews on Alastria Red T."""
    return execute_manual_ledger_sync_service(db)

# ==========================================
#     INTERNAL SYS.ADMIN API (NO FRONTEND)
# ==========================================
ADMIN_SECRET_KEY = os.getenv("INTERNAL_ADMIN_SECRET", "sys_admin_secret_888")

def verify_internal_admin(request: Request, x_admin_secret: Optional[str] = Header(None)):
    """
    Security check for Internal Sys.Admin API:
    Ensures endpoint cannot be accessed by external public clients.
    Allows access if request originates from localhost/internal loopback IP OR if valid internal secret header is provided.
    """
    client_host = request.client.host if request.client else "127.0.0.1"
    is_localhost = client_host in ("127.0.0.1", "::1", "localhost", "0.0.0.0") or client_host.startswith("10.") or client_host.startswith("172.") or client_host.startswith("192.168.")
    if not is_localhost and x_admin_secret != ADMIN_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security Refusal: Access to Internal Sys.Admin API is restricted to internal network / authorized administrators only."
        )

@app.post("/api/v1/internal/admin/submitters", response_model=SubmitterResponse, tags=["Internal Sys.Admin API"], dependencies=[Depends(verify_internal_admin)])
def create_submitter(req: SubmitterCreateRequest, db: Session = Depends(get_db)):
    """
    Sys.Admin Internal API: Add a new enterprise submitter with ID, name, secret API key, public key, and active status.
    Cannot be accessed by external public clients.
    """
    existing = db.query(Submitter).filter(Submitter.submitter_id == req.submitter_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Submitter ID '{req.submitter_id}' already exists")
        
    new_sub = Submitter(
        submitter_id=req.submitter_id,
        name=req.name,
        api_key=req.api_key,
        public_key=req.public_key or f"0x{req.submitter_id}PublicKey001",
        is_active=req.is_active,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)
    return new_sub

@app.patch("/api/v1/internal/admin/submitters/{submitter_id}", response_model=SubmitterResponse, tags=["Internal Sys.Admin API"], dependencies=[Depends(verify_internal_admin)])
@app.put("/api/v1/internal/admin/submitters/{submitter_id}", response_model=SubmitterResponse, tags=["Internal Sys.Admin API"], dependencies=[Depends(verify_internal_admin)])
def update_submitter(submitter_id: str, req: SubmitterUpdateRequest, db: Session = Depends(get_db)):
    """
    Sys.Admin Internal API: Edit is_active status or credentials of an existing submitter in the database.
    """
    sub = db.query(Submitter).filter(Submitter.submitter_id == submitter_id).first()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Submitter ID '{submitter_id}' not found")
        
    if req.name is not None:
        sub.name = req.name
    if req.api_key is not None:
        sub.api_key = req.api_key
    if req.public_key is not None:
        sub.public_key = req.public_key
    if req.is_active is not None:
        sub.is_active = req.is_active
        
    db.commit()
    db.refresh(sub)
    return sub

@app.get("/api/v1/internal/admin/submitters", response_model=list[SubmitterResponse], tags=["Internal Sys.Admin API"], dependencies=[Depends(verify_internal_admin)])
def list_submitters(db: Session = Depends(get_db)):
    """
    Sys.Admin Internal API: Read list of all enterprise submitters and their info from the database.
    """
    return db.query(Submitter).all()

@app.get("/api/v1/internal/admin/submitters/{submitter_id}", response_model=SubmitterResponse, tags=["Internal Sys.Admin API"], dependencies=[Depends(verify_internal_admin)])
def get_submitter_info(submitter_id: str, db: Session = Depends(get_db)):
    """
    Sys.Admin Internal API: Read details for a specific enterprise submitter by ID.
    """
    sub = db.query(Submitter).filter(Submitter.submitter_id == submitter_id).first()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Submitter ID '{submitter_id}' not found")
    return sub

# ==========================================
#     FRONTEND REACT STATIC MOUNTING
# ==========================================
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    @app.get("/")
    @app.get("/{catchall:path}")
    def serve_frontend(catchall: str = None):
        if catchall and catchall.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        return FileResponse(os.path.join(frontend_dist, "index.html"))


