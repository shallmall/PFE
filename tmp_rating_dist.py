import pandas as pd

def analyze_chunk():
    print("Loading dataset: data/public_reviews_dataset_cleaned.csv...")
    df = pd.read_csv("data/public_reviews_dataset_cleaned.csv", low_memory=False)
    
    # Filter for the specific chunk
    print("Filtering data for: reviewer_classified_fake == False AND fake_review_product == False...")
    chunk = df[(df['reviewer_classified_fake'] == False) & (df['fake_review_product'] == False)]
    
    print(f"\nTotal reviews in this specific chunk: {len(chunk):,}")
    
    if len(chunk) > 0 and 'review_rating' in chunk.columns:
        counts = chunk['review_rating'].value_counts().sort_index()
        percentages = chunk['review_rating'].value_counts(normalize=True).sort_index() * 100
        
        dist_df = pd.DataFrame({'Count': counts, 'Percentage (%)': percentages})
        print("\n--- Star Rating Distribution (1 to 5) ---")
        print(dist_df.to_string())
    else:
        print("No data found for this specific chunk or 'review_rating' column is missing.")

if __name__ == "__main__":
    analyze_chunk()
