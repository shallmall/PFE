import os
import sys
import time
from datetime import datetime, timezone

# Ensure stdout encoding
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.db import Base
from database.models import Submitter, Reviewer, Product, Review
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider
from eth_account import Account

from web3_worker.alastria_ledger_worker import (
    load_or_compile_contract,
    sync_pending_reviews,
    get_keccak_bytes16
)

def main():
    print("═" * 70)
    print("E2E Test: Alastria Blockchain Worker & Off-Chain/On-Chain DB Sync")
    print("═" * 70)

    # 1. Setup in-memory SQLite database for testing
    print("\n Setting up test database & inserting 50 un-anchored reviews...")
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionTest = sessionmaker(bind=engine)
    db = SessionTest()

    sub = Submitter(submitter_id="test_sub", name="Test Enterprise", api_key="secret123", is_active=True)
    db.add(sub)
    db.flush()

    for i in range(5):
        rev = Reviewer(
            universal_reviewer_id=f"test_sub:user_{i}",
            submitter_id="test_sub",
            reviewer_id=f"user_{i}",
            name=f"User {i}",
            current_score=0.85
        )
        prod = Product(
            universal_product_id=f"test_sub:prod_{i}",
            submitter_id="test_sub",
            product_id=f"prod_{i}",
            name=f"Product {i}"
        )
        db.add(rev)
        db.add(prod)
    db.flush()

    # Add 50 reviews with status = 'Confirmed_OffChain' and tx_hash = None
    for i in range(50):
        review = Review(
            universal_review_id=f"test_sub:rev_{i:03d}",
            submitter_id="test_sub",
            reviewer_id=f"test_sub:user_{i % 5}",
            product_id=f"test_sub:prod_{i % 5}",
            review_text=f"This is review {i}",
            rating=5.0,
            review_date=datetime.now(timezone.utc),
            ai_score=0.92 - (i * 0.005),
            is_fraud=1 if i % 2 == 0 else 0,
            status="Confirmed_OffChain",
            tx_hash=None
        )
        db.add(review)
    db.commit()

    pending_before = db.query(Review).filter(Review.status == "Confirmed_OffChain").count()
    print(f"Inserted 50 reviews. Count of 'Confirmed_OffChain' in DB before sync: {pending_before}")
    assert pending_before == 50, "Failed to insert 50 reviews into DB!"

    # 2. Setup Simulated Web3 & Contract
    print("\n Initializing Simulated Web3 Node & Deploying Contract...")
    w3 = Web3(EthereumTesterProvider())
    
    class SimulatedAccount:
        def __init__(self, address):
            self.address = address
            self.key = None
            
    account = SimulatedAccount(w3.eth.accounts[0])
    w3.eth.default_account = w3.eth.accounts[0]

    contract = load_or_compile_contract(w3, account)
    print(f"Contract deployed at: {contract.address}")

    # 3. Execute Worker Sync
    print("\n Executing sync_pending_reviews (Sweeping DB & broadcasting Web3 batch)...")
    synced_count = sync_pending_reviews(db, w3, contract, account, batch_limit=100)
    print(f"Synced {synced_count} records!")
    assert synced_count == 50, f"Expected 50 synced records, got {synced_count}"

    # 4. Verify SQL DB State Transition
    print("\n Verifying SQL Database State after receipt confirmation...")
    pending_after = db.query(Review).filter(Review.status == "Confirmed_OffChain").count()
    confirmed_onchain = db.query(Review).filter(Review.status == "Confirmed_OnChain").count()
    print(f"• Remaining 'Confirmed_OffChain' in DB : {pending_after}")
    print(f"• Updated 'Confirmed_OnChain' in DB    : {confirmed_onchain}")
    assert pending_after == 0, "There should be 0 Confirmed_OffChain remaining!"
    assert confirmed_onchain == 50, "All 50 reviews should now be Confirmed_OnChain!"

    sample_review = db.query(Review).filter(Review.universal_review_id == "test_sub:rev_000").first()
    print(f"• Sample DB Record (rev_000) TX Hash   : {sample_review.tx_hash}")
    assert sample_review.tx_hash and sample_review.tx_hash.startswith("0x"), "TX hash not properly saved in DB!"

    # 5. Verify Smart Contract On-Chain Storage
    print("\n Querying Alastria Smart Contract On-Chain State...")
    rev_000_bytes16 = get_keccak_bytes16("test_sub:rev_000")
    details = contract.functions.getReviewDetails(rev_000_bytes16).call()
    print(f"• On-Chain Heavy Table (rev_000) -> Review Score: {details[2]} / 100 | Reviewer Score: {details[3]} / 100")
    assert details[2] > 0, "Review score was not saved on-chain!"

    user_0_bytes16 = get_keccak_bytes16("test_sub:user_0")
    history = contract.functions.getReviewerHistory(user_0_bytes16).call()
    print(f"• On-Chain Light Table (user_0)  -> Total Mined Historical Points: {len(history)}")
    assert len(history) == 10, f"Expected 10 historical records for user_0 (50 reviews / 5 users), got {len(history)}"

    print("\n══════════════════════════════════════════════════════════════════════")
    print("ALL E2E BLOCKCHAIN & DATABASE SYNC TESTS PASSED PERFECTLY!")
    print("══════════════════════════════════════════════════════════════════════")

if __name__ == "__main__":
    main()
