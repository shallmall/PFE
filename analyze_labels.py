import pandas as pd

def analyze_distributions(csv_path="data/public_reviews_dataset_cleaned.csv"):
    print(f"Loading dataset: {csv_path}...\n")
    df = pd.read_csv(csv_path, low_memory=False)
    
    columns_to_analyze = [
        'fake_review_product',
        'reviewer_classified_fake',
        'reviewer_classified_honest',
        'reviewer_labeled_fake',
        'reviewer_labeled_honest',
        'review_is_removed_by_amazon'
    ]
    
    for col in columns_to_analyze:
        if col in df.columns:
            print(f"--- Distribution for: {col} ---")
            counts = df[col].value_counts(dropna=False)
            percentages = df[col].value_counts(normalize=True, dropna=False) * 100
            
            # Combine counts and percentages
            dist_df = pd.DataFrame({'Count': counts, 'Percentage (%)': percentages})
            print(dist_df.to_string())
            print("\n")
        else:
            print(f"Column '{col}' not found in the dataset.\n")
            
    print("--- Intersection Analysis ---")
    total_reviews = len(df)
    
    # Intersection 1: Removed by Amazon = 1.0 AND reviewer_classified_honest = 1
    if 'review_is_removed_by_amazon' in df.columns and 'reviewer_classified_honest' in df.columns:
        intersect_1 = len(df[(df['review_is_removed_by_amazon'] == 1.0) & (df['reviewer_classified_honest'] == 1)])
        pct_1 = (intersect_1 / total_reviews) * 100
        print(f"Removed by Amazon (1.0) AND Honest Reviewer (1): {intersect_1} ({pct_1:.4f}%)")
        
    # Intersection 2: Removed by Amazon = 0.0 AND reviewer_classified_fake = True
    if 'review_is_removed_by_amazon' in df.columns and 'reviewer_classified_fake' in df.columns:
        intersect_2 = len(df[(df['review_is_removed_by_amazon'] == 0.0) & (df['reviewer_classified_fake'] == True)])
        pct_2 = (intersect_2 / total_reviews) * 100
        print(f"Active on Amazon (0.0) AND Fake Reviewer (True): {intersect_2} ({pct_2:.4f}%)")
        
    # Intersection 3: Labeled Honest AND Classified Honest
    if 'reviewer_labeled_honest' in df.columns and 'reviewer_classified_honest' in df.columns:
        intersect_3 = len(df[(df['reviewer_labeled_honest'] == 1.0) & (df['reviewer_classified_honest'] == 1)])
        labeled_honest_count = len(df[df['reviewer_labeled_honest'] == 1.0])
        pct_3_dataset = (intersect_3 / total_reviews) * 100
        pct_3_subset = (intersect_3 / labeled_honest_count) * 100 if labeled_honest_count > 0 else 0
        print(f"Labeled Honest (1.0) AND Classified Honest (True): {intersect_3} ({pct_3_dataset:.4f}% of total dataset, {pct_3_subset:.2f}% of all Labeled Honest)")
        
    # Intersection 4: Labeled Fake AND Classified Fake
    if 'reviewer_labeled_fake' in df.columns and 'reviewer_classified_fake' in df.columns:
        intersect_4 = len(df[(df['reviewer_labeled_fake'] == 1.0) & (df['reviewer_classified_fake'] == 1)])
        labeled_fake_count = len(df[df['reviewer_labeled_fake'] == 1.0])
        pct_4_dataset = (intersect_4 / total_reviews) * 100
        pct_4_subset = (intersect_4 / labeled_fake_count) * 100 if labeled_fake_count > 0 else 0
        print(f"Labeled Fake (1.0) AND Classified Fake (True): {intersect_4} ({pct_4_dataset:.4f}% of total dataset, {pct_4_subset:.2f}% of all Labeled Fake)")

    print("\n--- Labeled Features Ratio Analysis ---")
    if 'reviewer_labeled_fake' in df.columns and 'reviewer_labeled_honest' in df.columns:
        labeled_fake_count = len(df[df['reviewer_labeled_fake'] == 1.0])
        labeled_honest_count = len(df[df['reviewer_labeled_honest'] == 1.0])
        
        if labeled_honest_count > 0:
            ratio = labeled_fake_count / labeled_honest_count
            print(f"Ratio of reviewer_labeled_fake (1.0) to reviewer_labeled_honest (1.0): {ratio:.4f} to 1")
            print(f"  Fake Count (1.0): {labeled_fake_count}")
            print(f"  Honest Count (1.0): {labeled_honest_count}")
            
            total_labeled = labeled_fake_count + labeled_honest_count
            print(f"  Percentage Breakdown within labeled subset -> Fake: {(labeled_fake_count/total_labeled)*100:.2f}%, Honest: {(labeled_honest_count/total_labeled)*100:.2f}%")
        else:
            print("Cannot calculate ratio, labeled honest count is 0.")
        print("\n")

if __name__ == "__main__":
    analyze_distributions()
