import csv
import json
import hashlib
from pathlib import Path

def compute_signature(submitter_id, reviewer_id, reviewee_id, review_text, review_rating, pub_key):
    rating_str = f"{float(review_rating):.1f}"
    text_str = str(review_text).strip()
    raw_data = f"{submitter_id}:{reviewer_id}:{reviewee_id}:{text_str}:{rating_str}"
    payload_hash = hashlib.sha256(raw_data.encode("utf-8")).hexdigest()
    expected_sig = "0x" + hashlib.sha256((payload_hash + pub_key).encode("utf-8")).hexdigest()
    return expected_sig

def main():
    csv_path = Path("data/public_reviews_dataset_cleaned.csv")
    if not csv_path.exists():
        print(f"❌ Could not find {csv_path}")
        return

    print("⏳ Reading dataset and grouping reviews by product...")
    product_reviews = {}
    product_names = {}

    with open(csv_path, mode="r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            asin = row.get("asin", "").strip()
            if not asin:
                continue
            if asin not in product_reviews:
                product_reviews[asin] = []
                product_names[asin] = row.get("product_title", "").strip() or f"Product {asin}"
            
            product_reviews[asin].append(row)

    # Select 50 unique products (sort by review count so we pick products with good review history)
    sorted_products = sorted(product_reviews.keys(), key=lambda p: len(product_reviews[p]), reverse=True)[:50]

    submitter_id = "partner_amazon_01"
    submitter_name = "Amazon Marketplace API"
    pub_key = "0x71C8407B1A53E043F405A02F31a19fD84f6C3A9B"

    all_reviews_output = []
    total_reviews = 0

    for asin in sorted_products:
        pname = product_names[asin]
        reviews_list = product_reviews[asin]
        for r in reviews_list:
            rev_id = (r.get("reviewer_id") or "ANONYMOUS")[:20]
            rev_name = (r.get("review_title") or "Verified Purchaser").strip()[:40]
            text = (r.get("review_text") or "Good product.").strip()
            try:
                rating = float(r.get("review_rating") or 5.0)
            except ValueError:
                rating = 5.0
            try:
                photos = int(float(r.get("number_of_photos") or 0))
            except ValueError:
                photos = 0
            try:
                helpful = int(float(r.get("number_of_helpful") or 0))
            except ValueError:
                helpful = 0

            sig = compute_signature(submitter_id, rev_id, asin, text, rating, pub_key)

            all_reviews_output.append({
                "submitter_id": submitter_id,
                "reviewer_id": rev_id,
                "reviewer_name": rev_name,
                "reviewee_id": asin,
                "reviewee_name": pname,
                "review_rating": rating,
                "review_text": text,
                "num_photos": photos,
                "num_helpful": helpful,
                "payload_signature": sig
            })
            total_reviews += 1

    output_payload = {
        "submitter_id": submitter_id,
        "submitter_name": submitter_name,
        "reviews": all_reviews_output
    }

    out_file = Path("amazon_50_products_all_reviews.json")
    with open(out_file, mode="w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    print(f"✅ Created {out_file} containing exactly 50 unique products with ALL their reviews ({total_reviews:,} total reviews generated and signed!)")

if __name__ == "__main__":
    main()
