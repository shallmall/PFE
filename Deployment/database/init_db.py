import sys
import os
import json
from datetime import datetime, timedelta, timezone
import random

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import engine, SessionLocal, Base
from database.models import Submitter, Reviewer, Product, Review
from orchestrator.services import generate_universal_id

def init_and_seed_db(force_recreate=False):
    thresh_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../HGT_Heterogeneous_Graph_Model/model/best_thresholds.json"))
    if not os.path.exists(thresh_path):
        thresh_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/best_thresholds.json"))
    with open(thresh_path, 'r') as f:
        thresh_data = json.load(f)
    review_thresh = float(thresh_data['review_threshold'])

    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "offchain_fraud_detection.db")
    if force_recreate and os.path.exists(db_path):
        try:
            os.remove(db_path)
            print("Removed existing database file for fresh schema initialization.")
        except Exception as e:
            print(f"Could not remove database: {e}")

    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Check if submitters already exist
        existing = db.query(Submitter).first()
        if existing:
            print("Database already seeded! Skipping seeding step.")
            return

        print("Seeding Enterprise Submitters...")
        sub_amazon = Submitter(
            submitter_id="AMAZON_US",
            name="Amazon US Platform",
            api_key="key_amazon_12345",
            public_key="0xAmazonPublicKey00000000000000000000001",
            is_active=True
        )
        sub_shop = Submitter(
            submitter_id="SHOPPING_GLOBAL",
            name="Shopping Global App",
            api_key="key_shopping_67890",
            public_key="0xShoppingPublicKey000000000000000000002",
            is_active=True
        )
        db.add_all([sub_amazon, sub_shop])
        db.commit()

        print("Seeding sample historical context for AMAZON_US (for localized subgraph testing)...")
        now = datetime.now(timezone.utc)
        
        # Create 10 historical reviewers
        reviewers = []
        for i in range(1, 11):
            loc_id = f"USER_{i:03d}"
            rev = Reviewer(
                universal_reviewer_id=generate_universal_id("AMAZON_US", loc_id),
                submitter_id="AMAZON_US",
                reviewer_id=loc_id,
                name=f"Historical Reviewer {i}",
                current_score=random.uniform(0.1, 0.9),
                user_avg_past_deberta_score=round(random.uniform(0.1, 0.8), 4),
                created_at=now - timedelta(days=180)
            )
            reviewers.append(rev)
        db.add_all(reviewers)

        # Create 5 historical products
        products = []
        for i in range(1, 6):
            loc_id = f"PROD_{i:03d}"
            prod = Product(
                universal_product_id=generate_universal_id("AMAZON_US", loc_id),
                submitter_id="AMAZON_US",
                product_id=loc_id,
                name=f"Sample Product {i}",
                category="Electronics" if i % 2 == 0 else "Home & Kitchen",
                created_at=now - timedelta(days=180)
            )
            products.append(prod)
        db.add_all(products)
        db.commit()

        # Create 50 historical reviews spanning the last 150 days (all strictly in the past!)
        reviews = []
        sample_texts = [
            "Great product, really loved using it every day!",
            "Terrible quality, broke after two days of use. Do not buy.",
            "Average item, does what it says but nothing special.",
            "Best purchase ever! Highly recommended to everyone.",
            "Not worth the money at all. Customer service was unhelpful.",
            "Amazing! Five stars all the way. Perfect packaging.",
            "Decent quality for the price point. Would buy again on sale.",
            "Absolute scam! Fake product received, extremely disappointed."
        ]

        for i in range(1, 51):
            rev_date = now - timedelta(days=random.randint(10, 150), hours=random.randint(0, 23))
            reviewer = random.choice(reviewers)
            product = random.choice(products)
            rating = random.choice([1.0, 2.0, 3.0, 4.0, 5.0])
            ai_score = random.uniform(0.05, 0.95)
            deberta_prob = min(1.0, max(0.0, ai_score * random.uniform(0.8, 1.2)))
            is_fraud = 1 if ai_score >= review_thresh else 0
            loc_rev_id = f"HIST_REV_{i:03d}"

            review = Review(
                universal_review_id=generate_universal_id("AMAZON_US", loc_rev_id),
                submitter_id="AMAZON_US",
                reviewer_id=reviewer.universal_reviewer_id,
                product_id=product.universal_product_id,
                review_text=random.choice(sample_texts),
                rating=rating,
                num_photos=random.randint(0, 2),
                num_helpful=random.randint(0, 15),
                review_date=rev_date,
                ai_score=round(ai_score, 4),
                deberta_prob=round(deberta_prob, 4),
                is_fraud=is_fraud,
                status="Confirmed",
                tx_hash=f"0x{random.getrandbits(256):064x}"
            )
            reviews.append(review)

        db.add_all(reviews)
        db.commit()
        print(f"[OK] Successfully seeded database with {len(reviewers)} reviewers, {len(products)} products, and {len(reviews)} historical reviews!")

    finally:
        db.close()

if __name__ == "__main__":
    init_and_seed_db()
