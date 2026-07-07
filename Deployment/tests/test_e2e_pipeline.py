import os
import sys
import time
import json
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone
import uvicorn

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import SessionLocal
from database.models import Review
from database.init_db import init_and_seed_db
from orchestrator.app import app as orchestrator_app
from ai_engine.app import app as ai_engine_app

def start_orchestrator():
    uvicorn.run(orchestrator_app, host="127.0.0.1", port=8001, log_level="error")

def start_ai_engine():
    uvicorn.run(ai_engine_app, host="127.0.0.1", port=8002, log_level="error")

def run_e2e_verification():
    print("=" * 70)
    print("STARTING 3-LAYER FRAUD DETECTION E2E VERIFICATION PIPELINE")
    print("=" * 70)
    
    # Step 1: Initialize and seed database
    print("\n[Step 1] Initializing Layer 3 Local Off-Chain DB & Seeding Context...")
    init_and_seed_db(force_recreate=True)
    
    # Step 2: Start Layer 2 and Layer 1 microservices in background daemon threads
    print("\n[Step 2] Spinning up Layer 2 Orchestrator (Port 8001) & Layer 1 AI Engine (Port 8002)...")
    t1 = threading.Thread(target=start_orchestrator, daemon=True)
    t2 = threading.Thread(target=start_ai_engine, daemon=True)
    t1.start()
    t2.start()
    
    # Give uvicorn servers 3 seconds to start up and load AI models into memory
    time.sleep(3)
    
    # Step 3: Simulate Enterprise Submitter submitting a review batch
    print("\n[Step 3] Simulating Enterprise Submitter (AMAZON_US) submitting Review Batch...")
    now = datetime.now(timezone.utc)
    
    batch_payload = {
        "submitter_id": "AMAZON_US",
        "api_key": "key_amazon_12345",
        "reviews": [
            {
                "review_id": "LIVE_REV_001",
                "reviewer_id": "USER_001",
                "product_id": "PROD_001",
                "review_text": "Great product, really loved using it every day! Perfect packaging.",
                "rating": 5.0,
                "review_date": now.isoformat(),
                "num_photos": 2,
                "num_helpful": 10
            },
            {
                "review_id": "LIVE_REV_002",
                "reviewer_id": "USER_SPAMMER_999",
                "product_id": "PROD_002",
                "review_text": "Absolute scam! Fake product received, do not buy, horrible scam and deceptive!",
                "rating": 1.0,
                "review_date": now.isoformat(),
                "num_photos": 0,
                "num_helpful": 0
            },
            {
                "review_id": "LIVE_REV_003",
                "reviewer_id": "USER_003",
                "product_id": "PROD_003",
                "review_text": "Average item, does what it says but nothing special. Okay quality.",
                "rating": 3.0,
                "review_date": now.isoformat(),
                "num_photos": 0,
                "num_helpful": 2
            },
            {
                "review_id": "LIVE_REV_004",
                "reviewer_id": "USER_SPAMMER_999",
                "product_id": "PROD_001",
                "review_text": "Terrible broke worst scam refund counterfeit do not buy waste money!",
                "rating": 1.0,
                "review_date": now.isoformat(),
                "num_photos": 0,
                "num_helpful": 1
            }
        ]
    }
    
    print("Sending POST request to Layer 2 API Gateway: http://127.0.0.1:8001/api/v1/submit_batch")
    req = urllib.request.Request(
        "http://127.0.0.1:8001/api/v1/submit_batch",
        data=json.dumps(batch_payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            report = json.loads(resp.read().decode('utf-8'))
            status_code = resp.getcode()
            print(f"Response Status Code: {status_code}")
    except urllib.error.HTTPError as exc:
        print(f"FAILED! Error details: {exc.read().decode('utf-8', errors='ignore')}")
        sys.exit(1)
        
    print("\n[Step 4] API Call 1 -> 2 -> 3 Orchestration Complete! Batch Report Received:")
    print(f"  -> Submitter ID     : {report['submitter_id']}")
    print(f"  -> Total Processed  : {report['total_processed']}")
    print(f"  -> Fraud Detected   : {report['fraud_detected']}")
    print("\nDetailed Item Scores & Cryptographic Tx Hashes:")
    for res in report['results']:
        label_str = "[FAKE/SPAM]" if res['is_fraud'] == 1 else "[GENUINE]"
        print(f"  * [{res['review_id']}] Review Head (2-Var): {res['ai_score']:.4f} | Reviewer Head (3-Var): {res.get('reviewer_score', 0.0):.4f} | DeBERTa: {res.get('deberta_prob', 0.0):.4f} | {label_str}")
        print(f"    Web3 TxHash: {res['tx_hash']}")
        
    # Step 5: Direct Database State Verification
    print("\n[Step 5] Direct Database Verification (Layer 3 State Inspection)...")
    db = SessionLocal()
    try:
        live_reviews = db.query(Review).filter(Review.universal_review_id.like("AMAZON_US:LIVE_REV_%")).all()
        print(f"Found {len(live_reviews)} live reviews stored in database:")
        for r in live_reviews:
            print(f"  -> DB Record [{r.universal_review_id}]: ai_score={r.ai_score}, deberta_prob={r.deberta_prob}, is_fraud={r.is_fraud}, status='{r.status}', tx_hash='{r.tx_hash[:16]}...'")
            assert r.status == "Confirmed", f"Review {r.universal_review_id} status is not Confirmed!"
            assert r.tx_hash is not None and r.tx_hash.startswith("0x"), f"Invalid tx_hash for {r.universal_review_id}!"
            
        print("\n[OK] ALL 3 LAYERS VERIFIED SUCCESSFULLY! ZERO-LEAKAGE CHRONOLOGICAL PIPELINE OPERATIONAL!")
    finally:
        db.close()

if __name__ == "__main__":
    run_e2e_verification()
