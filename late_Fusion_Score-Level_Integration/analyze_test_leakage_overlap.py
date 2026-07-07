import os
import sys
import pandas as pd
from pathlib import Path

# Configure stdout encoding for Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def main():
    print("═" * 70)
    print("  Chronological Test Set Entity Overlap Analysis")
    print("═" * 70)

    script_dir = Path(__file__).resolve().parent
    data_path = script_dir / "late_fusion_features.csv"

    df = pd.read_csv(data_path, usecols=['review_id', 'reviewer_id', 'product_id', 'review_date'])
    
    n = len(df)
    idx_train = int(n * 0.8)
    idx_val = int(n * 0.9)

    df_train = df.iloc[:idx_train]
    df_val = df.iloc[idx_train:idx_val]
    df_test = df.iloc[idx_val:]

    print(f"Total rows: {n:,}")
    print(f"Train rows (0-80%): {len(df_train):,} ({df_train['review_date'].min()} to {df_train['review_date'].max()})")
    print(f"Test rows (90-100%): {len(df_test):,} ({df_test['review_date'].min()} to {df_test['review_date'].max()})")

    train_products = set(df_train['product_id'].unique())
    train_reviewers = set(df_train['reviewer_id'].unique())

    test_products = set(df_test['product_id'].unique())
    test_reviewers = set(df_test['reviewer_id'].unique())

    print("\n── 1. Unique Entity Overlap (Unique IDs in Test vs Train) ──────────")
    seen_products = test_products.intersection(train_products)
    unseen_products = test_products.difference(train_products)
    print(f"Total Unique Products in Test Set : {len(test_products):,}")
    print(f"  • Already Seen in Train (0-80%) : {len(seen_products):,} ({len(seen_products)/len(test_products)*100:.2f}%)")
    print(f"  • Brand New / Unseen in Train   : {len(unseen_products):,} ({len(unseen_products)/len(test_products)*100:.2f}%)")

    seen_reviewers = test_reviewers.intersection(train_reviewers)
    unseen_reviewers = test_reviewers.difference(train_reviewers)
    print(f"\nTotal Unique Reviewers in Test Set: {len(test_reviewers):,}")
    print(f"  • Already Seen in Train (0-80%) : {len(seen_reviewers):,} ({len(seen_reviewers)/len(test_reviewers)*100:.2f}%)")
    print(f"  • Brand New / Unseen in Train   : {len(unseen_reviewers):,} ({len(unseen_reviewers)/len(test_reviewers)*100:.2f}%)")

    print("\n── 2. Transaction Level Overlap (Test Rows with Seen Entities) ────")
    test_rows_seen_prod = df_test['product_id'].isin(train_products).sum()
    test_rows_seen_rev = df_test['reviewer_id'].isin(train_reviewers).sum()
    test_rows_seen_both = (df_test['product_id'].isin(train_products) & df_test['reviewer_id'].isin(train_reviewers)).sum()

    print(f"Total Test Transactions           : {len(df_test):,}")
    print(f"  • Rows targeting seen product   : {test_rows_seen_prod:,} ({test_rows_seen_prod/len(df_test)*100:.2f}%)")
    print(f"  • Rows authored by seen reviewer: {test_rows_seen_rev:,} ({test_rows_seen_rev/len(df_test)*100:.2f}%)")
    print(f"  • Rows with BOTH seen           : {test_rows_seen_both:,} ({test_rows_seen_both/len(df_test)*100:.2f}%)")
    print("═" * 70)

if __name__ == "__main__":
    main()
