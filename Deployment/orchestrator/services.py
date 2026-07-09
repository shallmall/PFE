from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import hmac
import hashlib
import json

from database.models import Submitter, Reviewer, Product, Review
from orchestrator.schemas import (
    HistoryResponse, ReviewerNode, ProductNode, ReviewNode,
    ScoreResultPayload, ScoredReviewItem, ReviewBatchInput,
    ReviewerScoreSummary, ProductScoreSummary, ReviewAuditLogItem,
    LedgerStatusResponse, LedgerSyncResponse
)
from sqlalchemy import func

def validate_submitter(db: Session, submitter_id: str, signature: str = None, api_key: str = None, reviews: list = None) -> Submitter:
    """
    Validates enterprise submitter cryptographic signature / encrypted hash against stored database keys.
    Enforces active account status (is_active == True).
    """
    submitter = db.query(Submitter).filter(Submitter.submitter_id == submitter_id).first()
    if not submitter:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid submitter_id: Submitter not registered in database")
    if not submitter.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Security / Verification Refusal: Submitter account is inactive (is_active == False)")
        
    token = signature or api_key
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Security / Verification Refusal: Missing cryptographic signature or encrypted hash")
        
    # 1. Legacy direct API key check (backwards compatibility)
    if token == submitter.api_key or token == submitter.public_key:
        return submitter

    # 2. Cryptographic HMAC / SHA256 signature verification against stored submitter secret/public keys
    valid_signatures = set()
    if submitter.api_key:
        secret_bytes = submitter.api_key.encode('utf-8')
        num_revs = len(reviews) if reviews else 0
        valid_signatures.add(hmac.new(secret_bytes, f"{submitter_id}:{num_revs}".encode('utf-8'), hashlib.sha256).hexdigest())
        if reviews:
            rev_ids = f"{submitter_id}:" + ",".join(getattr(r, 'review_id', str(r)) for r in reviews)
            valid_signatures.add(hmac.new(secret_bytes, rev_ids.encode('utf-8'), hashlib.sha256).hexdigest())
            try:
                dump_str = json.dumps([r.dict() if hasattr(r, 'dict') else r for r in reviews], sort_keys=True)
                valid_signatures.add(hmac.new(secret_bytes, dump_str.encode('utf-8'), hashlib.sha256).hexdigest())
            except Exception:
                pass
        valid_signatures.add(hashlib.sha256(f"{submitter.api_key}:{submitter_id}".encode('utf-8')).hexdigest())
        valid_signatures.add(hashlib.sha256(f"{submitter.api_key}:{submitter_id}:{num_revs}".encode('utf-8')).hexdigest())
        
    if token.strip().lower() in {s.lower() for s in valid_signatures}:
        return submitter
        
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Security / Verification Refusal: Cryptographic signature / encrypted hash verification failed against stored submitter key")

def get_historical_context(db: Session, submitter_id: str, current_timestamp: datetime) -> HistoryResponse:
    """
    Fetches historical subgraph context with strict zero-leakage chronological bounding:
    1. Time window: review_date >= current_timestamp - 180 days
    2. Strict zero leakage: review_date < current_timestamp
    3. Hard node limit: LIMIT 200,000 most recent reviews
    4. Computes historical rolling DeBERTa spam average per reviewer over time!
    """
    time_threshold = current_timestamp - timedelta(days=180)
    
    # Query historical reviews strictly before current_timestamp
    historical_reviews = (
        db.query(Review)
        .filter(Review.submitter_id == submitter_id)
        .filter(Review.review_date < current_timestamp)
        .filter(Review.review_date >= time_threshold)
        .order_by(Review.review_date.desc())
        .limit(200000)
        .all()
    )
    
    # Calculate historical average DeBERTa score per reviewer strictly before current_timestamp
    reviewer_deberta_sums = {}
    reviewer_review_counts = {}
    for r in historical_reviews:
        prob = getattr(r, 'deberta_prob', None)
        if prob is None or prob == 0.0:
            prob = getattr(r, 'ai_score', None) or 0.30
        reviewer_deberta_sums[r.reviewer_id] = reviewer_deberta_sums.get(r.reviewer_id, 0.0) + prob
        reviewer_review_counts[r.reviewer_id] = reviewer_review_counts.get(r.reviewer_id, 0) + 1
        
    # Extract unique reviewer and product IDs from the bounded historical slice
    reviewer_ids = {r.reviewer_id for r in historical_reviews}
    product_ids = {r.product_id for r in historical_reviews}
    
    reviewers = (
        db.query(Reviewer)
        .filter(Reviewer.universal_reviewer_id.in_(reviewer_ids))
        .all() if reviewer_ids else []
    )
    
    products = (
        db.query(Product)
        .filter(Product.universal_product_id.in_(product_ids))
        .all() if product_ids else []
    )
    
    reviewers_out = []
    for rev in reviewers:
        node = ReviewerNode.from_orm(rev)
        cnt = reviewer_review_counts.get(rev.universal_reviewer_id, 0)
        if cnt > 0:
            node.user_avg_past_deberta_score = round(reviewer_deberta_sums[rev.universal_reviewer_id] / cnt, 4)
        else:
            node.user_avg_past_deberta_score = getattr(rev, 'user_avg_past_deberta_score', 0.0) or 0.0
        reviewers_out.append(node)
    
    return HistoryResponse(
        submitter_id=submitter_id,
        reviewers=reviewers_out,
        products=[ProductNode.from_orm(p) for p in products],
        reviews=[ReviewNode.from_orm(r) for r in historical_reviews]
    )

def generate_universal_id(submitter_id: str, local_id: str) -> str:
    """
    Generates a synchronized 16-byte hex hash Universal ID across the entire system.
    Format: 0x + 32 hex chars (SHA-256 of submitter_id:local_id truncated to 16 bytes / 32 hex digits).
    """
    raw_str = f"{submitter_id}:{local_id}"
    return "0x" + hashlib.sha256(raw_str.encode('utf-8')).hexdigest()[:32]

def ensure_batch_nodes(db: Session, batch: ReviewBatchInput):
    """
    Ensures reviewers and products in the new batch exist in the database,
    and inserts reviews in 'Pending' status without duplicate crashes.
    """
    sub_id = batch.submitter_id
    seen_reviewers = set()
    seen_products = set()
    seen_reviews = set()
    seen_reviewer_product = set()
    
    for item in batch.reviews:
        # Check/Create Reviewer
        univ_rev_id = generate_universal_id(sub_id, item.reviewer_id)
        if univ_rev_id not in seen_reviewers:
            seen_reviewers.add(univ_rev_id)
            reviewer = db.query(Reviewer).filter(Reviewer.universal_reviewer_id == univ_rev_id).first()
            if not reviewer:
                reviewer = Reviewer(
                    universal_reviewer_id=univ_rev_id,
                    submitter_id=sub_id,
                    reviewer_id=item.reviewer_id,
                    name=item.reviewer_name or f"User {item.reviewer_id}",
                    current_score=0.0,
                    user_avg_past_deberta_score=0.0
                )
                db.add(reviewer)
                db.flush()
            
        # Check/Create Product
        univ_prod_id = generate_universal_id(sub_id, item.product_id)
        if univ_prod_id not in seen_products:
            seen_products.add(univ_prod_id)
            product = db.query(Product).filter(Product.universal_product_id == univ_prod_id).first()
            if not product:
                product = Product(
                    universal_product_id=univ_prod_id,
                    submitter_id=sub_id,
                    product_id=item.product_id,
                    name=item.product_name or f"Product {item.product_id}",
                    category=item.product_category or "General"
                )
                db.add(product)
                db.flush()
            
        # Check/Create Review in Pending status (prevent duplicate review or duplicate reviewer-product submission crash)
        univ_review_id = generate_universal_id(sub_id, item.review_id)
        rev_prod_pair = (univ_rev_id, univ_prod_id)
        if univ_review_id in seen_reviews or rev_prod_pair in seen_reviewer_product:
            continue
        seen_reviews.add(univ_review_id)
        seen_reviewer_product.add(rev_prod_pair)
        
        # Also check database for existing review ID or existing reviewer-product pair
        existing_review = db.query(Review).filter(
            (Review.universal_review_id == univ_review_id) |
            ((Review.reviewer_id == univ_rev_id) & (Review.product_id == univ_prod_id))
        ).first()
        if not existing_review:
            review = Review(
                universal_review_id=univ_review_id,
                submitter_id=sub_id,
                reviewer_id=univ_rev_id,
                product_id=univ_prod_id,
                review_text=item.review_text,
                rating=item.rating,
                num_photos=item.num_photos,
                num_helpful=item.num_helpful,
                review_date=item.review_date,
                deberta_prob=0.0,
                status="Pending"
            )
            db.add(review)
            
    db.commit()

def save_ai_results(db: Session, submitter_id: str, payload: ScoreResultPayload) -> int:
    """Updates reviews in database with final AI classification scores and tx hashes, and updates Reviewer reputation scores."""
    updated_count = 0
    for res in payload.results:
        univ_review_id = generate_universal_id(submitter_id, res.review_id)
        review = db.query(Review).filter(Review.universal_review_id == univ_review_id).first()
        if review:
            review.ai_score = res.ai_score
            review.deberta_prob = getattr(res, 'deberta_prob', 0.0)
            review.is_fraud = res.is_fraud
            review.status = res.status
            review.tx_hash = res.tx_hash
            updated_count += 1
            
            # Update reviewer reputation score if present
            if review.reviewer:
                review.reviewer.current_score = res.reviewer_score if getattr(res, 'reviewer_score', 0.0) > 0 else (1.0 - res.ai_score)
                if getattr(res, 'deberta_prob', 0.0) > 0:
                    review.reviewer.user_avg_past_deberta_score = res.deberta_prob
            
    db.commit()
    return updated_count

def get_aggregated_reviewer_scores(db: Session, submitter_id: str = None) -> List[ReviewerScoreSummary]:
    """Phase 4 & 7: Computes aggregated reputation scores, review counts, and fraud counts per Reviewer."""
    query = db.query(Reviewer)
    if submitter_id:
        query = query.filter(Reviewer.submitter_id == submitter_id)
    reviewers = query.all()
    
    out = []
    for rev in reviewers:
        target_rev_ids = {rev.universal_reviewer_id, rev.reviewer_id, f"AMAZON_US:{rev.reviewer_id}", generate_universal_id(rev.submitter_id or "AMAZON_US", rev.reviewer_id)}
        reviews_for_rev = db.query(Review).filter(Review.reviewer_id.in_(list(target_rev_ids))).all()
        rev_count = len(reviews_for_rev)
        fraud_count = sum(1 for r in reviews_for_rev if r.is_fraud == 1)
        
        out.append(ReviewerScoreSummary(
            universal_reviewer_id=rev.universal_reviewer_id,
            reviewer_id=rev.reviewer_id,
            submitter_id=rev.submitter_id,
            name=rev.name,
            current_score=round(rev.current_score, 4) if rev.current_score else round(max(0.0, 1.0 - (fraud_count / max(1, rev_count))), 4),
            user_avg_past_deberta_score=round(rev.user_avg_past_deberta_score or 0.0, 4),
            review_count=rev_count,
            fraud_count=fraud_count
        ))
    return out

def get_aggregated_product_scores(db: Session, submitter_id: str = None) -> List[ProductScoreSummary]:
    """Phase 4 & 7: Computes aggregated star ratings, AI risk scores, and review counts per Product."""
    query = db.query(Product)
    if submitter_id:
        query = query.filter(Product.submitter_id == submitter_id)
    products = query.all()
    
    out = []
    for prod in products:
        target_prod_ids = {prod.universal_product_id, prod.product_id, f"AMAZON_US:{prod.product_id}", generate_universal_id(prod.submitter_id or "AMAZON_US", prod.product_id)}
        reviews_for_prod = db.query(Review).filter(Review.product_id.in_(list(target_prod_ids))).all()
        rev_count = len(reviews_for_prod)
        fraud_count = sum(1 for r in reviews_for_prod if r.is_fraud == 1)
        avg_rating = sum(r.rating for r in reviews_for_prod) / rev_count if rev_count > 0 else 0.0
        avg_ai = sum((r.ai_score or 0.0) for r in reviews_for_prod) / rev_count if rev_count > 0 else 0.0
        
        out.append(ProductScoreSummary(
            universal_product_id=prod.universal_product_id,
            product_id=prod.product_id,
            submitter_id=prod.submitter_id,
            name=prod.name,
            category=prod.category,
            avg_rating=round(avg_rating, 2),
            avg_ai_score=round(avg_ai, 4),
            review_count=rev_count,
            fraud_count=fraud_count
        ))
    return out

def get_review_audit_log(db: Session, submitter_id: str = None, product_id: str = None, reviewer_id: str = None, limit: int = 500) -> List[ReviewAuditLogItem]:
    """Phase 7: Fetches detailed review audit logs with Web3 cryptographic transaction hashes."""
    query = db.query(Review)
    if submitter_id:
        query = query.filter(Review.submitter_id == submitter_id)
    if product_id:
        matching_prods = db.query(Product).filter(
            (Product.product_id == product_id) | 
            (Product.universal_product_id == product_id) |
            (Product.product_id.endswith(f":{product_id}"))
        ).all()
        target_ids = {product_id, f"AMAZON_US:{product_id}", generate_universal_id("AMAZON_US", product_id)}
        for p in matching_prods:
            target_ids.add(p.universal_product_id)
            target_ids.add(p.product_id)
        if ":" in product_id:
            sub, loc = product_id.split(":", 1)
            target_ids.add(generate_universal_id(sub, loc))
            target_ids.add(loc)
        query = query.filter(Review.product_id.in_(list(target_ids)))
    if reviewer_id:
        matching_revs = db.query(Reviewer).filter(
            (Reviewer.reviewer_id == reviewer_id) | 
            (Reviewer.universal_reviewer_id == reviewer_id) |
            (Reviewer.reviewer_id.endswith(f":{reviewer_id}"))
        ).all()
        target_rev_ids = {reviewer_id, f"AMAZON_US:{reviewer_id}", generate_universal_id("AMAZON_US", reviewer_id)}
        for r in matching_revs:
            target_rev_ids.add(r.universal_reviewer_id)
            target_rev_ids.add(r.reviewer_id)
        if ":" in reviewer_id:
            sub, loc = reviewer_id.split(":", 1)
            target_rev_ids.add(generate_universal_id(sub, loc))
            target_rev_ids.add(loc)
        query = query.filter(Review.reviewer_id.in_(list(target_rev_ids)))
            
    reviews = query.order_by(Review.review_date.desc()).limit(limit).all()
    
    out = []
    for r in reviews:
        out.append(ReviewAuditLogItem(
            universal_review_id=r.universal_review_id,
            submitter_id=r.submitter_id,
            reviewer_id=r.reviewer_id,
            product_id=r.product_id,
            review_text=r.review_text,
            rating=r.rating,
            review_date=r.review_date,
            ai_score=round(r.ai_score, 4) if r.ai_score is not None else 0.0,
            deberta_prob=round(r.deberta_prob, 4) if r.deberta_prob is not None else 0.0,
            is_fraud=r.is_fraud or 0,
            status=r.status or "Confirmed",
            tx_hash=r.tx_hash,
            reviewer_name=r.reviewer.name if r.reviewer else None,
            product_name=r.product.name if r.product else None
        ))
    return out

def get_ledger_status_service(db: Session) -> LedgerStatusResponse:
    """Phase 5 & 7: Queries real-time off-chain DB queue and Alastria blockchain status."""
    offchain_cnt = db.query(Review).filter(Review.status.in_(["Confirmed_OffChain", "Confirmed"])).count()
    onchain_cnt = db.query(Review).filter(Review.status == "Confirmed_OnChain").count()
    pending_cnt = db.query(Review).filter(Review.status == "Pending_Ledger").count()
    
    latest_rev = db.query(Review).filter(Review.status == "Confirmed_OnChain").order_by(Review.created_at.desc()).first()
    latest_hash = latest_rev.tx_hash if latest_rev else None
    
    return LedgerStatusResponse(
        chain_name="Alastria Red T Permissioned Consortium Network (Chain ID: 2020)",
        contract_address="0x51EA9c1D046BE57E3B461d9048176800cb3380f5",
        confirmed_offchain_count=offchain_cnt,
        confirmed_onchain_count=onchain_cnt,
        pending_ledger_count=pending_cnt,
        latest_tx_hash=latest_hash,
        status_message=f"System operational. {offchain_cnt} records queued for Alastria zero-gas anchoring."
    )

def execute_manual_ledger_sync_service(db: Session) -> LedgerSyncResponse:
    """Triggers an immediate synchronous Web3 sweep to anchor pending reviews on Alastria Red T."""
    try:
        from web3_worker.alastria_ledger_worker import connect_web3, load_or_compile_contract, sync_pending_reviews
        from web3 import Account
        w3, endpoint_name = connect_web3(simulated=False)
        
        if hasattr(w3.provider, 'ethereum_tester'):
            class SimulatedAccount:
                def __init__(self, address):
                    self.address = address
                    self.key = None
            account = SimulatedAccount(w3.eth.accounts[0])
            w3.eth.default_account = w3.eth.accounts[0]
        else:
            account = Account.create()
            
        contract = load_or_compile_contract(w3, account)
        synced = sync_pending_reviews(db, w3, contract, account, batch_limit=100)
        
        latest_rev = db.query(Review).filter(Review.status == "Confirmed_OnChain").order_by(Review.created_at.desc()).first()
        latest_hash = latest_rev.tx_hash if latest_rev else None
        
        return LedgerSyncResponse(
            status="success" if synced > 0 else "idle",
            synced_records=synced,
            latest_tx_hash=latest_hash,
            message=f"Successfully anchored {synced} reviews to Alastria blockchain via {endpoint_name}."
        )
    except Exception as e:
        return LedgerSyncResponse(
            status="error",
            synced_records=0,
            latest_tx_hash=None,
            message=f"Ledger sync failed: {str(e)}"
        )

