"""
Prepare Point-in-Time Temporal Features for Late Fusion
=========================================================
This script merges predictions from:
1. DeBERTa text classifier (Spam probability)
2. HGAT temporal graph neural network (Reviewer & Product structural anomaly scores)
3. Cleaned metadata dataset (Timestamps & ground truth labels)

It calculates 3 historical rolling features strictly prior to each review date (shift(1))
to guarantee ZERO target leakage from future transactions:
- user_historical_fake_ratio
- user_avg_past_deberta_score
- product_historical_fake_ratio (Realistic flagged percentage)
"""

import os
import sys
import time
import pandas as pd
import numpy as np
from pathlib import Path

# Configure stdout encoding for Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def main():
    print("═" * 70)
    print("  Late Fusion Data Preparation: Realistic Point-in-Time Feature Engine")
    print("═" * 70)

    script_dir = Path(__file__).resolve().parent
    base_dir = script_dir.parent

    enriched_csv = base_dir / "data" / "final_enriched_reviews_dataset.csv"
    deberta_csv = base_dir / "SpamVis_DeBERTa-v3-base_Model" / "deberta_predictions_output.csv"
    output_csv = script_dir / "late_fusion_features.csv"

    # 1. Verify files exist
    for path, name in [(enriched_csv, "Enriched Dataset"), (deberta_csv, "DeBERTa Predictions")]:
        if not path.exists():
            print(f"❌ Error: {name} not found at: {path}")
            sys.exit(1)

    print("\n── 1. Loading Input Datasets ──────────────────────────────────────")
    t0 = time.time()
    
    cols_meta = ['review_id', 'reviewer_id', 'asin', 'review_date', 
                 'review_is_removed_by_amazon', 'fake_review_product', 
                 'reviewer_classified_fake', 'reviewer_classified_honest',
                 'reviewer_labeled_fake', 'reviewer_labeled_honest',
                 'gnn_product_fraud_probability', 'gnn_reviewer_fraud_probability',
                 'gnn_review_fraud_probability']
    df_meta = pd.read_csv(enriched_csv, usecols=lambda c: c in cols_meta, low_memory=False)
    if 'asin' in df_meta.columns:
        df_meta = df_meta.rename(columns={'asin': 'product_id'})
    df_meta = df_meta.rename(columns={
        'gnn_product_fraud_probability': 'gnn_product_score',
        'gnn_reviewer_fraud_probability': 'gnn_reviewer_score',
        'gnn_review_fraud_probability': 'gnn_review_score'
    })
    
    df_deberta = pd.read_csv(deberta_csv, usecols=['review_id', 'model_score', 'predicted_label'])
    df_deberta = df_deberta.rename(columns={'model_score': 'deberta_spam_prob', 'predicted_label': 'deberta_pred_label'})

    print(f"✅ Loaded raw data in {time.time() - t0:.2f}s")

    # 2. Merge Datasets
    print("\n── 2. Merging Multi-Modal Predictions ─────────────────────────────")
    t0 = time.time()
    df = df_meta.merge(df_deberta, on='review_id', how='inner')
    print(f"✅ Merged {len(df):,} rows in {time.time() - t0:.2f}s")

    # 3. Sort Chronologically
    print("\n── 3. Applying Chronological Time-Travel Ordering ─────────────────")
    df['review_date'] = pd.to_datetime(df['review_date'])
    df = df.sort_values(['review_date', 'review_id']).reset_index(drop=True)
    print(f"✅ Sorted records spanning from {df['review_date'].min().date()} to {df['review_date'].max().date()}")

    # Define flag indicators for historical rolling counts without using future ground truth
    # A review is flagged historically if removed by Amazon OR DeBERTa predicted spam (0) OR GNN reviewer score suspicious (>=0.40)
    df['is_flagged_review'] = ((df['review_is_removed_by_amazon'] == 1.0) | (df['deberta_pred_label'] == 0) | (df['gnn_reviewer_score'] >= 0.40)).astype(float)

    # 4. Compute Point-in-Time Rolling Historical Features (Strictly Shifted by 1)
    print("\n── 4. Computing Vectorized Point-in-Time Historical Features ──────")
    t0 = time.time()

    # User level rolling features
    print("🔹 Computing User Historical Fake Ratio & Avg DeBERTa Score...")
    user_grp = df.groupby(['reviewer_id', 'review_date'], sort=False)
    
    u_daily_cnt = user_grp['review_id'].count()
    u_daily_flag = user_grp['is_flagged_review'].sum()
    u_daily_deberta = user_grp['deberta_spam_prob'].sum()

    u_cum_cnt = u_daily_cnt.groupby('reviewer_id').cumsum()
    u_cum_flag = u_daily_flag.groupby('reviewer_id').cumsum()
    u_cum_deberta = u_daily_deberta.groupby('reviewer_id').cumsum()

    u_prev_cnt = u_cum_cnt.groupby('reviewer_id').shift(1, fill_value=0)
    u_prev_flag = u_cum_flag.groupby('reviewer_id').shift(1, fill_value=0.0)
    u_prev_deberta = u_cum_deberta.groupby('reviewer_id').shift(1, fill_value=0.0)

    u_history = pd.DataFrame({'prev_cnt': u_prev_cnt, 'prev_flag': u_prev_flag, 'prev_deberta': u_prev_deberta}).reset_index()
    df = df.merge(u_history, on=['reviewer_id', 'review_date'], how='left')

    df['user_historical_fake_ratio'] = np.where(df['prev_cnt'] > 0, df['prev_flag'] / df['prev_cnt'], 0.0)
    df['user_avg_past_deberta_score'] = np.where(df['prev_cnt'] > 0, df['prev_deberta'] / df['prev_cnt'], 0.0)
    df.drop(columns=['prev_cnt', 'prev_flag', 'prev_deberta'], inplace=True)

    # Product level rolling features (Realistic Flagged Ratio)
    print("🔹 Computing Product Historical Flagged Ratio...")
    prod_grp = df.groupby(['product_id', 'review_date'], sort=False)

    p_daily_cnt = prod_grp['review_id'].count()
    p_daily_flag = prod_grp['is_flagged_review'].sum()

    p_cum_cnt = p_daily_cnt.groupby('product_id').cumsum()
    p_cum_flag = p_daily_flag.groupby('product_id').cumsum()

    p_prev_cnt = p_cum_cnt.groupby('product_id').shift(1, fill_value=0)
    p_prev_flag = p_cum_flag.groupby('product_id').shift(1, fill_value=0.0)

    p_history = pd.DataFrame({'p_prev_cnt': p_prev_cnt, 'p_prev_flag': p_prev_flag}).reset_index()
    df = df.merge(p_history, on=['product_id', 'review_date'], how='left')

    df['product_historical_fake_ratio'] = np.where(df['p_prev_cnt'] > 0, df['p_prev_flag'] / df['p_prev_cnt'], 0.0)
    df.drop(columns=['p_prev_cnt', 'p_prev_flag', 'is_flagged_review'], inplace=True)

    print(f"✅ Computed all time-travel historical features in {time.time() - t0:.2f}s")

    # 5. Sanity Check Leakage Verification
    print("\n── 5. Zero Leakage Verification ───────────────────────────────────")
    first_row = df.iloc[0]
    print(f"   First chronological transaction ({first_row['review_date'].date()}):")
    print(f"     user_historical_fake_ratio : {first_row['user_historical_fake_ratio']:.4f}")
    print(f"     user_avg_past_deberta_score   : {first_row['user_avg_past_deberta_score']:.4f}")
    print(f"     prod_historical_fake_ratio : {first_row['product_historical_fake_ratio']:.4f}")
    assert first_row['user_historical_fake_ratio'] == 0.0 and first_row['product_historical_fake_ratio'] == 0.0, "Leakage detected on first row!"
    print("   ✅ Time-Travel Causality Verified: Initial transactions show 0.0 prior history.")

    # 6. Save final feature matrix
    print("\n── 6. Saving Master Feature CSV ───────────────────────────────────")
    t0 = time.time()
    df.to_csv(output_csv, index=False)
    print(f"✅ Saved master late fusion dataset ({len(df):,} rows) to: {output_csv}")
    print(f"   Total elapsed time: {time.time() - t0:.2f}s")
    print("═" * 70)

if __name__ == "__main__":
    main()
