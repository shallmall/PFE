import json
import sys
from pathlib import Path

# Insert Deployment path
deployment_dir = Path(__file__).resolve().parent / "Deployment"
sys.path.insert(0, str(deployment_dir))

from ai_engine import ai_engine

class MockSession:
    def query(self, *args, **kwargs):
        return self
    def filter(self, *args, **kwargs):
        return self
    def all(self):
        return []

def main():
    json_path = Path("amazon_50_products_all_reviews.json")
    if not json_path.exists():
        print("❌ File amazon_50_products_all_reviews.json not found.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    reviews = data.get("reviews", [])
    print(f"⏳ Evaluating {len(reviews):,} reviews with real Late Fusion AI Engine (LightGBM + BERT + GNN)...")

    ai_engine.load_models()
    mock_db = MockSession()

    scores = []
    flagged = 0
    genuine = 0

    # Sample first 2000 reviews for speed check
    sample_size = min(len(reviews), 2000)
    for idx, r in enumerate(reviews[:sample_size]):
        score = ai_engine.compute_ai_score(
            reviewer_id=r.get("reviewer_id", ""),
            product_id=r.get("reviewee_id", ""),
            review_text=r.get("review_text", ""),
            db_session=mock_db
        )
        scores.append(score)
        if score < 50:
            flagged += 1
        else:
            genuine += 1

    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    print(f"\n🎯 Real Late Fusion AI Engine Sample Results ({sample_size:,} reviews evaluated):")
    print(f"   • Verified High Trust (Score >= 50): {genuine:,} ({genuine/sample_size*100:.1f}%)")
    print(f"   • Flagged / Spam Risk (Score < 50):  {flagged:,} ({flagged/sample_size*100:.1f}%)")
    print(f"   • Average AI Trust Score:            {avg_score} / 100")

if __name__ == "__main__":
    main()
