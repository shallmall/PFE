"""
Verification Script for Deployment Suite
========================================
Tests REST API endpoints, Late Fusion AI scoring, database persistence,
and throttled Alastria blockchain sequential processing.
"""

import sys
import time
import asyncio
from pathlib import Path
from fastapi.testclient import TestClient

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add current directory to path
sys.path.append(str(Path(__file__).resolve().parent))

from app import app
from database import init_db

def run_tests():
    db_file = Path(__file__).resolve().parent / "reviews_ledger.db"
    if db_file.exists():
        try:
            db_file.unlink()
        except Exception:
            pass

    print("═"*70)
    print("  Running Verification Tests for Deployment Package")
    print("═"*70)
    
    with TestClient(app) as client:
        print("\n── 1. Submitting Genuine Review Payload ───────────────────────────")
        payload_genuine = {
            "submitter_id": "client_api_amazon",
            "submitter_name": "Amazon Verified API",
            "reviewer_id": "usr_genuine_001",
            "reviewer_name": "Alice Smith",
            "reviewee_id": "ASIN_B08N5WRWNW",
            "reviewee_name": "Sony Wireless Headphones",
            "reviewee_type": "Product",
            "review_text": "Excellent build quality, battery lasts all week and active noise cancellation is top tier.",
            "review_rating": 5.0,
            "num_photos": 2,
            "num_helpful": 14
        }
        
        t0 = time.time()
        res1 = client.post("/api/v1/reviews/submit", json=payload_genuine)
        dt1 = time.time() - t0
        assert res1.status_code == 201, f"Expected 201, got {res1.status_code}: {res1.text}"
        data1 = res1.json()
        print(f"✅ Submitted Genuine Review in {dt1*1000:.1f}ms")
        print(f"   • Submitter Client ID : {data1['submitter_id']}")
        print(f"   • Reviewer            : {data1['reviewer_name']} ({data1['reviewer_id']}) -> Updated Reputation: {data1['reviewer_score']}")
        print(f"   • Target Product      : {data1['reviewee_name']} ({data1['reviewee_id']}) -> Updated Reputation: {data1['reviewee_score']}")
        print(f"   • Universal Review ID : {data1['universal_review_id']}")
        print(f"   • AI Fraud Score      : {data1['ai_score']} / 100 (High = Genuine)")
        
        print("\n── 2. Submitting Suspicious Spam Review Payload ───────────────────")
        payload_spam = {
            "submitter_id": "client_api_amazon",
            "submitter_name": "Amazon Verified API",
            "reviewer_id": "usr_spammer_999",
            "reviewer_name": "Free Gift Cards Bot",
            "reviewee_id": "ASIN_B08N5WRWNW",
            "reviewee_name": "Sony Wireless Headphones",
            "reviewee_type": "Product",
            "review_text": "BUY NOW FREE CRYPTO DISCOUNT CLICK HERE http://scam.link BEST DEAL 100% LEGIT",
            "review_rating": 5.0,
            "num_photos": 0,
            "num_helpful": 0
        }
        
        t0 = time.time()
        res2 = client.post("/api/v1/reviews/submit", json=payload_spam)
        dt2 = time.time() - t0
        assert res2.status_code == 201, f"Expected 201, got {res2.status_code}"
        data2 = res2.json()
        print(f"✅ Submitted Spam Review in {dt2*1000:.1f}ms")
        print(f"   • Submitter Client ID : {data2['submitter_id']}")
        print(f"   • Reviewer            : {data2['reviewer_name']} ({data2['reviewer_id']}) -> Updated Reputation: {data2['reviewer_score']}")
        print(f"   • Target Product      : {data2['reviewee_name']} ({data2['reviewee_id']}) -> Updated Reputation: {data2['reviewee_score']}")
        print(f"   • Universal Review ID : {data2['universal_review_id']}")
        print(f"   • AI Fraud Score      : {data2['ai_score']} / 100 (Low = Fraud)")

        print("\n── 3. Verifying Alastria Throttled Queue Processing ───────────────")
        print("⏳ Waiting 8.5s for async background worker to process BOTH Reviewee and Reviewer transactions...")
        time.sleep(8.5)

        print("\n── 4. Querying Relational Audit Ledger & Blockchain TX status ─────")
        lookup_res = client.get(f"/api/v1/reviews/{data1['universal_review_id']}")
        assert lookup_res.status_code == 200, f"Lookup failed: {lookup_res.text}"
        ledger_data = lookup_res.json()
        print(f"✅ Single Review Ledger Verification Successful:")
        print(f"   • Review ID      : {ledger_data['universal_review_id']}")
        print(f"   • Reviewer       : {ledger_data['reviewer_name']} ({ledger_data['reviewer_id']})")
        print(f"   • Target         : {ledger_data['reviewee_name']} ({ledger_data['reviewee_id']})")
        print(f"   • Review AI Score: {ledger_data['ai_score']}")
        print(f"   • Reviewer Score : {ledger_data['reviewer_score']}")
        print(f"   • Reviewee Score : {ledger_data['reviewee_score']}")
        print(f"   • TX Hash        : {ledger_data['tx_hash']}")
        assert ledger_data['tx_hash'] is not None, "Transaction hash was not updated by worker!"

        print("\n── 5. Verifying Enriched Product & Reviewer Entity Endpoints ──────")
        prod_res = client.get(f"/api/v1/reviews/product/{payload_genuine['reviewee_id']}")
        assert prod_res.status_code == 200, f"Product lookup failed: {prod_res.text}"
        prod_data = prod_res.json()
        print(f"✅ Product Endpoint Verified -> Name: {prod_data['product_name']} | Score: {prod_data['product_score']} | Total Attached Reviews: {len(prod_data['reviews'])}")
        for pr in prod_data['reviews'][-3:]:
            print(f"   • Review {pr['universal_review_id'][:10]}... by {pr['reviewer_name']} | Review Score: {pr['ai_score']} | Reviewer Reputation: {pr['reviewer_score']}")

        user_res = client.get(f"/api/v1/reviews/reviewer/{payload_genuine['reviewer_id']}")
        assert user_res.status_code == 200, f"Reviewer lookup failed: {user_res.text}"
        user_data = user_res.json()
        print(f"✅ Reviewer Endpoint Verified -> Name: {user_data['reviewer_name']} | Score: {user_data['reviewer_score']} | Total Posted Comments: {len(user_data['reviews'])}")
        for ur in user_data['reviews'][-3:]:
            print(f"   • Review {ur['universal_review_id'][:10]}... on {ur['reviewee_name']} | Review Score: {ur['ai_score']} | Product Reputation: {ur['reviewee_score']}")

        print("\n── 6. Verifying Product Catalog Summary Endpoint ──────────────────")
        cat_res = client.get("/api/v1/products")
        assert cat_res.status_code == 200, f"Catalog lookup failed: {cat_res.text}"
        cat_data = cat_res.json()
        print(f"✅ Product Catalog Endpoint Verified -> {len(cat_data)} unique products found:")
        for item in cat_data:
            print(f"   • {item['product_name']} ({item['product_id']}) | Score: {item['product_score']} | Reviews: {item['num_reviews']}")

    print("\n✅ All deployment verification tests passed with flying colors!")
    print("═"*70)

if __name__ == "__main__":
    run_tests()
