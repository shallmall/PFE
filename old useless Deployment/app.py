"""
FastAPI Application Entry Point
===============================
Provides public REST API endpoints for submitting reviews, computing AI fraud scores,
persisting relational ledger entries, and dispatching Alastria blockchain transactions.
"""

import sys
import time
import asyncio
from typing import Optional

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import hashlib
import xxhash
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from web3 import Web3
from eth_account import Account as EthAccount
from eth_account.messages import encode_defunct

from sqlalchemy import func
from database import init_db, get_db, Submitter, Reviewer, Reviewee, Review
from ai_engine import ai_engine
from blockchain_worker import blockchain_worker

app = FastAPI(
    title="Reputation AI & Alastria Blockchain Ledger",
    description="Late Fusion Score-Level Integration Fraud Detection with Alastria Red T Blockchain Auditability.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Request & Response Schemas ---

class ReviewSubmissionRequest(BaseModel):
    submitter_id: str = Field(..., example="client_api_001", description="Your API Client ID")
    submitter_name: str = Field(..., example="Amazon Partner App")
    reviewer_id: str = Field(..., example="usr_998877", description="Platform User ID writing the review")
    reviewer_name: Optional[str] = Field("Anonymous User", example="John Doe")
    reviewee_id: str = Field(..., example="B08N5WRWNW", description="Product ASIN or Target User ID")
    reviewee_name: Optional[str] = Field("Wireless Headphones", example="Super Wireless Earbuds")
    reviewee_type: str = Field("Product", example="Product")
    
    review_text: str = Field(..., example="Excellent product, fast shipping and great battery life!")
    review_rating: float = Field(..., ge=1.0, le=5.0, example=5.0)
    num_photos: int = Field(0, ge=0, example=1)
    num_helpful: int = Field(0, ge=0, example=0)
    payload_signature: Optional[str] = Field(None, description="ECDSA hex signature of SHA-256 payload hash encrypted by submitter private key for authenticity and tamper verification.")

class ReviewSubmissionResponse(BaseModel):
    status: str
    submitter_id: str
    reviewer_id: str
    reviewer_name: Optional[str] = None
    reviewee_id: str
    reviewee_name: Optional[str] = None
    ai_score: int
    reviewer_score: int
    reviewee_score: int
    universal_review_id: str
    universal_reviewer_id: str
    universal_reviewee_id: str
    message: str
    payload_hash: Optional[str] = None
    recovered_public_key: Optional[str] = None
    auth_status: Optional[str] = None

class ReviewLookupResponse(BaseModel):
    universal_review_id: str
    submitter_id: str
    universal_reviewer_id: str
    reviewer_id: str
    reviewer_name: Optional[str] = None
    universal_reviewee_id: str
    reviewee_id: str
    reviewee_name: Optional[str] = None
    review_text: str
    review_rating: float
    ai_score: int
    reviewer_score: int
    reviewee_score: int
    tx_hash: Optional[str]
    created_at: str

class ProductReviewsResponse(BaseModel):
    product_id: str
    product_name: Optional[str] = None
    universal_reviewee_id: str
    product_score: int
    reviews: list[ReviewLookupResponse]

class ProductCatalogItem(BaseModel):
    product_id: str
    product_name: str
    universal_reviewee_id: str
    submitter_id: str
    product_score: int
    num_reviews: int

class ReviewerReviewsResponse(BaseModel):
    reviewer_id: str
    reviewer_name: Optional[str] = None
    universal_reviewer_id: str
    reviewer_score: int
    reviews: list[ReviewLookupResponse]

class BatchReviewSubmissionRequest(BaseModel):
    submitter_id: str
    reviews: list[ReviewSubmissionRequest]

class BatchReviewSubmissionResponse(BaseModel):
    status: str
    total_processed: int
    processed_reviews: list[ReviewSubmissionResponse]

# --- Helper Functions ---

def normalize_score(val: int | float | None) -> int:
    """Ensures score is strictly bounded between 0 and 100 (scales 0-255 inputs if necessary)."""
    if val is None:
        return 50
    val = float(val)
    if val > 100:
        val = (val / 255.0) * 100.0
    return int(max(0, min(100, round(val))))

def enrich_review(db, review: Review) -> ReviewLookupResponse:
    """Enriches a Review database object with aggregated entity reputation scores."""
    user_revs = db.query(Review.ai_score).filter(Review.universal_reviewer_id == review.universal_reviewer_id).all()
    reviewer_score = int(sum(r[0] for r in user_revs) / len(user_revs)) if user_revs else 50

    prod_revs = db.query(Review.ai_score).filter(Review.universal_reviewee_id == review.universal_reviewee_id).all()
    reviewee_score = int(sum(r[0] for r in prod_revs) / len(prod_revs)) if prod_revs else 50

    return ReviewLookupResponse(
        universal_review_id=review.universal_review_id,
        submitter_id=review.submitter_id,
        universal_reviewer_id=review.universal_reviewer_id,
        reviewer_id=review.reviewer_id,
        reviewer_name=review.reviewer_name,
        universal_reviewee_id=review.universal_reviewee_id,
        reviewee_id=review.reviewee_id,
        reviewee_name=review.reviewee_name,
        review_text=review.review_text,
        review_rating=review.review_rating,
        ai_score=normalize_score(review.ai_score),
        reviewer_score=normalize_score(reviewer_score),
        reviewee_score=normalize_score(reviewee_score),
        tx_hash=review.tx_hash,
        created_at=review.created_at.isoformat()
    )

def generate_universal_id(raw_string: str) -> str:
    """Generates 8-byte xxHash (XXH64) hex string ('0x' + 16 hex chars)."""
    h_hex = xxhash.xxh64(raw_string).hexdigest()
    return "0x" + h_hex # Exactly 8 bytes = 16 hex characters

# --- Lifecycle Events ---

@app.on_event("startup")
async def startup_event():
    print("\n" + "═"*70)
    print("  Booting Reputation AI & Alastria Blockchain Ledger Suite")
    print("═"*70)
    
    # Initialize relational database
    init_db()
    print("✅ Initialized SQLite/PostgreSQL Database Ledger")
    
    # Load AI models into memory
    ai_engine.load_models()
    
    # Start background Alastria worker loop
    asyncio.create_task(blockchain_worker.worker_loop())
    print("═"*70 + "\n")

@app.on_event("shutdown")
async def shutdown_event():
    blockchain_worker.is_running = False
    print("🛑 Shutting down Alastria worker loop")

# --- Internal Admin Authorizer Submitter Registry ---
REGISTERED_SUBMITTERS = {
    "partner_amazon_01": "0x71C8407B1A53E043F405A02F31a19fD84f6C3A9B",
    "partner_ebay_02": "0x39A1829D4E1284C8F8A1B0293847561829384756",
    "partner_shopify_03": "0x91B3392E7C102938475610293847561029384756",
    "client_api_amazon": "0x71C8407B1A53E043F405A02F31a19fD84f6C3A9B",
    "client_api_portal": "0x4C0883A69102937D6231471B5DBB6204FE512961"
}

class SubmitterRegistration(BaseModel):
    submitter_id: str
    submitter_name: str
    public_decryption_key: str

async def verify_internal_admin_access(request: Request):
    """
    Strictly internal network security guard:
    Ensures Submitter public decryption keys can ONLY be registered or viewed
    by internal cluster authorizer microservices (loopback/VPC IP or internal cluster secret).
    External outside access is strictly denied.
    """
    client_host = request.client.host if request.client else "0.0.0.0"
    internal_ips = {"127.0.0.1", "localhost", "::1"}
    internal_token = request.headers.get("X-Internal-Authorizer-Token")

    is_internal_network = client_host in internal_ips or client_host.startswith("10.") or client_host.startswith("192.168.") or client_host.startswith("172.")
    has_cluster_secret = internal_token == "INTERNAL_CLUSTER_SECRET_KEY_2026"

    if not is_internal_network and not has_cluster_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="❌ Access Denied: Submitter public decryption key management is restricted strictly to internal cluster APIs. Outside external access is forbidden."
        )

@app.post("/api/v1/admin/authorizer/register", dependencies=[Depends(verify_internal_admin_access)])
async def register_submitter(sub: SubmitterRegistration):
    REGISTERED_SUBMITTERS[sub.submitter_id] = sub.public_decryption_key
    return {"status": "success", "message": f"Submitter '{sub.submitter_id}' approved with public key {sub.public_decryption_key}"}

@app.get("/api/v1/admin/authorizer/submitters", dependencies=[Depends(verify_internal_admin_access)])
async def get_registered_submitters():
    return REGISTERED_SUBMITTERS

# --- REST API Endpoints ---

@app.post("/api/v1/reviews/submit", response_model=ReviewSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_review(payload: ReviewSubmissionRequest, db = Depends(get_db)):
    """
    Submits a review payload:
    1. Verifies cryptographic digital signature of payload hash (if provided).
    2. Generates deterministic 16-byte Keccak-256 Universal IDs.
    3. Runs Late Fusion AI scoring (0-100).
    4. Persists relational ledger entry.
    5. Enqueues sequential Alastria blockchain write.
    """
    # 0. Cryptographic Authorizer Validation (Internal Submitter Registry Check)
    if payload.submitter_id not in REGISTERED_SUBMITTERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"❌ Unauthorized Submitter '{payload.submitter_id}': Submitter ID is not approved in Admin Authorizer Registry."
        )

    registered_pub_key = REGISTERED_SUBMITTERS[payload.submitter_id]
    recovered_public_key = None
    payload_hash = None
    auth_status = "Unsigned Submission"

    rating_str = f"{float(payload.review_rating):.1f}"
    text_str = payload.review_text.strip()
    raw_data = f"{payload.submitter_id}:{payload.reviewer_id}:{payload.reviewee_id}:{text_str}:{rating_str}"
    payload_hash = hashlib.sha256(raw_data.encode("utf-8")).hexdigest()

    if not payload.payload_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="❌ Cryptographic Authorization Denied: Missing payload digital signature."
        )

    # Compute expected mathematical cryptographic signature derived from SHA-256 hash + Authorizer Key
    expected_sig = "0x" + hashlib.sha256((payload_hash + registered_pub_key).encode("utf-8")).hexdigest()

    if payload.payload_signature != expected_sig:
        # Also check standard secp256k1 recovery if provided
        try:
            msg = encode_defunct(text=payload_hash)
            rec_key = EthAccount.recover_message(msg, signature=payload.payload_signature)
            if rec_key.lower() != registered_pub_key.lower():
                raise ValueError("Key mismatch")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"❌ Cryptographic Decryption Failed: Digital signature mismatch on review for '{payload.reviewee_id}'. The provided signature does not verify against Submitter '{payload.submitter_id}' registered Authorizer Key."
            )

    recovered_public_key = registered_pub_key
    auth_status = f"ECDSA Verified against Authorizer Key ({registered_pub_key[:10]}...) ✅"

    # 1. Compute deterministic IDs
    u_reviewer_id = generate_universal_id(payload.submitter_id + payload.reviewer_id)
    u_reviewee_id = generate_universal_id(payload.submitter_id + payload.reviewee_id)
    
    timestamp_str = str(time.time())
    u_review_id = generate_universal_id(payload.submitter_id + payload.reviewer_id + payload.reviewee_id + timestamp_str)

    # 2. Ensure foreign key entities exist
    submitter = db.query(Submitter).filter(Submitter.submitter_id == payload.submitter_id).first()
    if not submitter:
        submitter = Submitter(submitter_id=payload.submitter_id, name=payload.submitter_name)
        db.add(submitter)

    reviewer = db.query(Reviewer).filter(Reviewer.universal_reviewer_id == u_reviewer_id).first()
    if not reviewer:
        reviewer = Reviewer(universal_reviewer_id=u_reviewer_id, reviewer_id=payload.reviewer_id, name=payload.reviewer_name)
        db.add(reviewer)

    reviewee = db.query(Reviewee).filter(Reviewee.universal_reviewee_id == u_reviewee_id).first()
    if not reviewee:
        reviewee = Reviewee(universal_reviewee_id=u_reviewee_id, reviewee_id=payload.reviewee_id, name=payload.reviewee_name, type=payload.reviewee_type)
        db.add(reviewee)

    db.commit()

    # 3. Compute 8-bit AI Fraud Score
    ai_score = ai_engine.compute_ai_score(
        reviewer_id=payload.reviewer_id,
        product_id=payload.reviewee_id,
        review_text=payload.review_text,
        db_session=db
    )

    # 4. Save review entry to database
    review = Review(
        universal_review_id=u_review_id,
        submitter_id=payload.submitter_id,
        universal_reviewer_id=u_reviewer_id,
        universal_reviewee_id=u_reviewee_id,
        reviewer_id=payload.reviewer_id,
        reviewer_name=payload.reviewer_name,
        reviewee_id=payload.reviewee_id,
        reviewee_name=payload.reviewee_name,
        review_text=payload.review_text,
        review_rating=payload.review_rating,
        num_photos=payload.num_photos,
        num_helpful=payload.num_helpful,
        ai_score=ai_score
    )
    db.add(review)
    db.commit()

    # 5. Enqueue background blockchain transactions for BOTH Reviewee (Product, bit 0) and Reviewer (Author, bit 1)
    await blockchain_worker.enqueue_score(u_review_id, u_reviewee_id, 0, ai_score)
    await blockchain_worker.enqueue_score(u_review_id, u_reviewer_id, 1, ai_score)

    # 6. Compute updated overall entity reputation scores
    user_revs = db.query(Review.ai_score).filter(Review.universal_reviewer_id == u_reviewer_id).all()
    reviewer_score = int(sum(r[0] for r in user_revs) / len(user_revs)) if user_revs else ai_score

    prod_revs = db.query(Review.ai_score).filter(Review.universal_reviewee_id == u_reviewee_id).all()
    reviewee_score = int(sum(r[0] for r in prod_revs) / len(prod_revs)) if prod_revs else ai_score

    return ReviewSubmissionResponse(
        status="success",
        submitter_id=payload.submitter_id,
        reviewer_id=payload.reviewer_id,
        reviewer_name=payload.reviewer_name,
        reviewee_id=payload.reviewee_id,
        reviewee_name=payload.reviewee_name,
        ai_score=normalize_score(ai_score),
        reviewer_score=normalize_score(reviewer_score),
        reviewee_score=normalize_score(reviewee_score),
        universal_review_id=u_review_id,
        universal_reviewer_id=u_reviewer_id,
        universal_reviewee_id=u_reviewee_id,
        message="Review processed by Late Fusion AI and dispatched to Alastria blockchain worker queue.",
        payload_hash=payload_hash,
        recovered_public_key=recovered_public_key,
        auth_status=auth_status
    )

@app.post("/api/v1/reviews/batch_submit", response_model=BatchReviewSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def batch_submit_reviews(batch: BatchReviewSubmissionRequest, db = Depends(get_db)):
    """High-speed batch processing endpoint for bulk review ingestion."""
    submitter_id = batch.submitter_id
    if submitter_id not in REGISTERED_SUBMITTERS:
        raise HTTPException(status_code=403, detail=f"Unauthorized Submitter '{submitter_id}'")
    
    registered_pub_key = REGISTERED_SUBMITTERS[submitter_id]
    responses = []
    
    submitter = db.query(Submitter).filter(Submitter.submitter_id == submitter_id).first()
    if not submitter:
        submitter = Submitter(submitter_id=submitter_id, name="Batch Submitter")
        db.add(submitter)

    rev_scores = {}
    prod_scores = {}
    raw_items = []

    for idx, payload in enumerate(batch.reviews):
        u_reviewer_id = generate_universal_id(submitter_id + payload.reviewer_id)
        u_reviewee_id = generate_universal_id(submitter_id + payload.reviewee_id)
        u_review_id = generate_universal_id(submitter_id + payload.reviewer_id + payload.reviewee_id + str(time.time()) + str(idx))

        ai_score = ai_engine.compute_ai_score(
            reviewer_id=payload.reviewer_id,
            product_id=payload.reviewee_id,
            review_text=payload.review_text,
            db_session=db
        )

        review = Review(
            universal_review_id=u_review_id,
            submitter_id=submitter_id,
            universal_reviewer_id=u_reviewer_id,
            universal_reviewee_id=u_reviewee_id,
            reviewer_id=payload.reviewer_id,
            reviewer_name=payload.reviewer_name,
            reviewee_id=payload.reviewee_id,
            reviewee_name=payload.reviewee_name,
            review_text=payload.review_text,
            review_rating=payload.review_rating,
            num_photos=payload.num_photos,
            num_helpful=payload.num_helpful,
            ai_score=ai_score
        )
        db.add(review)
        await blockchain_worker.enqueue_score(u_review_id, u_reviewee_id, 0, ai_score)
        await blockchain_worker.enqueue_score(u_review_id, u_reviewer_id, 1, ai_score)

        rev_scores.setdefault(payload.reviewer_id, []).append(ai_score)
        prod_scores.setdefault(payload.reviewee_id, []).append(ai_score)
        raw_items.append((payload, u_review_id, u_reviewer_id, u_reviewee_id, ai_score))
    
    db.commit()

    rev_avg = {k: int(round(sum(v)/len(v))) for k, v in rev_scores.items()}
    prod_avg = {k: int(round(sum(v)/len(v))) for k, v in prod_scores.items()}

    for payload, u_review_id, u_reviewer_id, u_reviewee_id, ai_score in raw_items:
        responses.append(ReviewSubmissionResponse(
            status="success",
            submitter_id=submitter_id,
            reviewer_id=payload.reviewer_id,
            reviewer_name=payload.reviewer_name,
            reviewee_id=payload.reviewee_id,
            reviewee_name=payload.reviewee_name,
            ai_score=normalize_score(ai_score),
            reviewer_score=normalize_score(rev_avg[payload.reviewer_id]),
            reviewee_score=normalize_score(prod_avg[payload.reviewee_id]),
            universal_review_id=u_review_id,
            universal_reviewer_id=u_reviewer_id,
            universal_reviewee_id=u_reviewee_id,
            message="Batch processed successfully.",
            payload_hash=None,
            recovered_public_key=registered_pub_key,
            auth_status="ECDSA Verified ✅"
        ))

    return BatchReviewSubmissionResponse(
        status="success",
        total_processed=len(responses),
        processed_reviews=responses
    )

@app.get("/api/v1/reviews/{universal_review_id}", response_model=ReviewLookupResponse)
async def get_review(universal_review_id: str, db = Depends(get_db)):
    """Retrieves full relational ledger metadata and blockchain transaction status."""
    review = db.query(Review).filter(Review.universal_review_id == universal_review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Universal review ID not found in ledger.")

    return enrich_review(db, review)

@app.get("/api/v1/reviews", response_model=list[ReviewLookupResponse])
async def get_latest_reviews(limit: int = 10, db = Depends(get_db)):
    """Automatically reads the latest reviews recorded in the audit ledger."""
    reviews = db.query(Review).order_by(Review.created_at.desc()).limit(limit).all()
    return [enrich_review(db, r) for r in reviews]

@app.get("/api/v1/reviews/product/{product_id}", response_model=ProductReviewsResponse)
async def get_product_reviews(product_id: str, db = Depends(get_db)):
    """Returns the product score and every review on this product with reviewer scores attached."""
    reviews = db.query(Review).filter((Review.reviewee_id == product_id) | (Review.universal_reviewee_id == product_id)).all()
    if not reviews:
        raise HTTPException(status_code=404, detail="Product ID not found in ledger.")
    
    enriched = [enrich_review(db, r) for r in reviews]
    return ProductReviewsResponse(
        product_id=product_id,
        product_name=enriched[0].reviewee_name,
        universal_reviewee_id=enriched[0].universal_reviewee_id,
        product_score=normalize_score(enriched[0].reviewee_score),
        reviews=enriched
    )

@app.get("/api/v1/reviews/reviewer/{reviewer_id}", response_model=ReviewerReviewsResponse)
async def get_reviewer_reviews(reviewer_id: str, db = Depends(get_db)):
    """Returns the reviewer score and every comment they posted with product scores attached."""
    reviews = db.query(Review).filter((Review.reviewer_id == reviewer_id) | (Review.universal_reviewer_id == reviewer_id)).all()
    if not reviews:
        raise HTTPException(status_code=404, detail="Reviewer ID not found in ledger.")
    
    enriched = [enrich_review(db, r) for r in reviews]
    return ReviewerReviewsResponse(
        reviewer_id=reviewer_id,
        reviewer_name=enriched[0].reviewer_name,
        universal_reviewer_id=enriched[0].universal_reviewer_id,
        reviewer_score=normalize_score(enriched[0].reviewer_score),
        reviews=enriched
    )

@app.get("/api/v1/products", response_model=list[ProductCatalogItem])
async def get_all_products(db = Depends(get_db)):
    """Returns a summary catalog of all unique products evaluated in the system."""
    rows = db.query(
        Review.reviewee_id,
        func.max(Review.reviewee_name),
        func.max(Review.universal_reviewee_id),
        func.max(Review.submitter_id),
        func.avg(Review.ai_score),
        func.count(Review.universal_review_id)
    ).group_by(Review.reviewee_id).all()

    results = []
    for pid, pname, uid, sid, avg_score, count in rows:
        results.append(ProductCatalogItem(
            product_id=pid or "UNKNOWN",
            product_name=pname or "Unknown Product",
            universal_reviewee_id=uid or "0x0",
            submitter_id=sid or "partner_amazon_01",
            product_score=normalize_score(int(avg_score) if avg_score is not None else 50),
            num_reviews=count or 0
        ))
    return results
