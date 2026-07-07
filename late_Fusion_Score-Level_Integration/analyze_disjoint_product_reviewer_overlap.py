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
    print("═" * 75)
    print("  Disjoint Product Partition -> Reviewer Overlap Analysis")
    print("═" * 75)

    script_dir = Path(__file__).resolve().parent
    data_path = script_dir / "late_fusion_features.csv"

    df = pd.read_csv(data_path, usecols=['review_id', 'reviewer_id', 'product_id', 'review_date'])
    
    # Order unique products chronologically by their first review appearance date (exactly like build_graph.py)
    first_seen = df.groupby('product_id')['review_date'].min().reset_index()
    first_seen = first_seen.sort_values('review_date').reset_index(drop=True)

    unique_prods = first_seen['product_id'].values
    n_prods = len(unique_prods)

    idx_train = int(n_prods * 0.8)
    idx_val = int(n_prods * 0.9)

    train_prods = set(unique_prods[:idx_train])
    val_prods = set(unique_prods[idx_train:idx_val])
    test_prods = set(unique_prods[idx_val:])

    print(f"Total Unique Products: {n_prods:,}")
    print(f"  • Train Products (0-80%)  : {len(train_prods):,}")
    print(f"  • Val Products   (80-90%) : {len(val_prods):,}")
    print(f"  • Test Products  (90-100%): {len(test_prods):,}")

    df_train = df[df['product_id'].isin(train_prods)]
    df_val = df[df['product_id'].isin(val_prods)]
    df_test = df[df['product_id'].isin(test_prods)]

    print(f"\nTransaction Counts:")
    print(f"  • Train Transactions : {len(df_train):,} ({len(df_train)/len(df)*100:.1f}%)")
    print(f"  • Val Transactions   : {len(df_val):,} ({len(df_val)/len(df)*100:.1f}%)")
    print(f"  • Test Transactions  : {len(df_test):,} ({len(df_test)/len(df)*100:.1f}%)")

    train_reviewers = set(df_train['reviewer_id'].unique())
    test_reviewers = set(df_test['reviewer_id'].unique())

    print("\n── Reviewer Overlap (Test Product Group vs Train Product Group) ──")
    seen_reviewers = test_reviewers.intersection(train_reviewers)
    unseen_reviewers = test_reviewers.difference(train_reviewers)

    print(f"Total Unique Reviewers reviewing Test Products: {len(test_reviewers):,}")
    print(f"  • Already seen reviewing Train Products : {len(seen_reviewers):,} ({len(seen_reviewers)/len(test_reviewers)*100:.2f}%)")
    print(f"  • Brand New / Unseen Reviewers          : {len(unseen_reviewers):,} ({len(unseen_reviewers)/len(test_reviewers)*100:.2f}%)")

    print("\n── Transaction Level Reviewer Overlap in Test Group ──────────────")
    test_rows_seen_rev = df_test['reviewer_id'].isin(train_reviewers).sum()
    print(f"Total Test Transactions                   : {len(df_test):,}")
    print(f"  • Authored by Reviewer seen in Train    : {test_rows_seen_rev:,} ({test_rows_seen_rev/len(df_test)*100:.2f}%)")
    print(f"  • Authored by brand new Reviewer        : {len(df_test) - test_rows_seen_rev:,} ({(1 - test_rows_seen_rev/len(df_test))*100:.2f}%)")
    print("═" * 75)

if __name__ == "__main__":
    main()
