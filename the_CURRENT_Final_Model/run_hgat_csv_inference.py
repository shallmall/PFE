"""
Run HGAT (Heterogeneous Graph Attention Network) Inference on CSV Reviews
========================================================================
Maps graph node predictions (Reviewer and Product heads) back to individual review transactions.
Generates a CSV containing: review_id, reviewer_id, product_id, reviewer_model_score, 
reviewer_prediction (0/1), reviewee_score, and reviewee_label (0/1).
"""

import os
import json
import time
import pandas as pd
import numpy as np
import torch
from pathlib import Path
import sys
import argparse

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add project root to sys.path
script_dir = Path(__file__).resolve().parent
sys.path.append(str(script_dir))
sys.path.append(str(script_dir.parent))

from model import HGTModel


def main():
    parser = argparse.ArgumentParser(description="Run HGAT Inference on Reviews CSV")
    parser.add_argument("--temporal_mode", type=str, default="monthly", choices=["full", "monthly", "weekly", "daily"],
                        help="Rolling temporal evaluation mode: full (batch), monthly (~37s), weekly (~2.5m), daily (~17m)")
    args = parser.parse_args()

    print("=" * 70)
    print("  HGAT Model Pipeline: Reviewer & Product (Reviewee) Inference")
    print(f"  Temporal Mode: {args.temporal_mode.upper()}")
    print("=" * 70)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[INFO] Using Device: {device}")

    # Paths
    model_dir = script_dir if (script_dir / "best_model.pth").exists() else (script_dir.parent / "the_CURRENT_Final_Model")
    if not (model_dir / "best_model.pth").exists():
        model_dir = script_dir.parent / "data"

    graph_path = model_dir / "hetero_graph.pt"
    weights_path = model_dir / "best_model.pth"
    thresh_path = model_dir / "best_thresholds.json"
    csv_path = script_dir.parent / "data" / "public_reviews_dataset_cleaned.csv"
    output_csv = model_dir / "hgat_predictions_output.csv"

    print(f"[INFO] Model Dir   : {model_dir}")
    print(f"[INFO] Input CSV   : {csv_path}")

    # 1. Load Raw CSV
    t0 = time.time()
    df = pd.read_csv(csv_path, low_memory=False)
    print(f"[OK] Loaded {len(df):,} raw reviews in {time.time() - t0:.2f}s")

    # Clean and sort chronologically exactly as build_graph.py did
    df = df.dropna(subset=['review_date', 'reviewer_id', 'asin', 'review_id'])
    df['review_date'] = pd.to_datetime(df['review_date'], errors='coerce')
    df = df.dropna(subset=['review_date'])
    df = df.sort_values('review_date').reset_index(drop=True)

    asin_ids = df['asin'].unique()
    reviewer_ids = df['reviewer_id'].unique()

    # 2. Load Graph & Model
    print("\n-- 1. Loading Graph & Trained HGAT Model ----------------------------------")
    t0 = time.time()
    data = torch.load(graph_path, map_location=device, weights_only=False)
    
    model = HGTModel(
        hidden_channels=64,
        out_channels=1,
        num_layers=2,
        num_heads=4,
        dropout=0.3,
        metadata=data.metadata()
    ).to(device)
    
    model.load_state_dict(torch.load(weights_path, map_location=device, weights_only=True))
    model.eval()
    print(f"[OK] Loaded graph & weights in {time.time() - t0:.2f}s")

    # Load thresholds
    with open(thresh_path, 'r') as f:
        thresh = json.load(f)
    thresh_p = thresh.get('product_threshold', 0.53)
    thresh_r = thresh.get('reviewer_threshold', 0.33)
    print(f"[INFO] Using Thresholds -> Product (Reviewee): {thresh_p:.2f} | Reviewer: {thresh_r:.2f}")

    # 3. Run GNN Inference
    product_id_col = "asin" if "asin" in df.columns else "product_id"

    if args.temporal_mode == 'full':
        print("\n-- 2. Computing Graph Node Probabilities (Full Batch Graph) ---------------")
        t0 = time.time()
        with torch.no_grad():
            out_dict = model(data.x_dict, data.edge_index_dict)
            prob_product = torch.sigmoid(out_dict['product'].squeeze(-1)).cpu().numpy()
            prob_reviewer = torch.sigmoid(out_dict['reviewer'].squeeze(-1)).cpu().numpy()
        print(f"[OK] Computed node probabilities in {time.time() - t0:.4f}s")

        prod_prob_map = dict(zip(asin_ids[:len(prob_product)], prob_product))
        rev_prob_map = dict(zip(reviewer_ids[:len(prob_reviewer)], prob_reviewer))

        rev_scores = np.round(df["reviewer_id"].map(rev_prob_map).fillna(0).values, 4)
        prod_scores = np.round(df[product_id_col].map(prod_prob_map).fillna(0).values, 4)
    else:
        print(f"\n-- 2. Computing Rolling Temporal Probabilities ({args.temporal_mode.upper()}) -----------")
        t0 = time.time()
        freq_map = {'daily': 'D', 'weekly': 'W', 'monthly': 'M'}
        df['period'] = df['review_date'].dt.to_period(freq_map[args.temporal_mode])
        periods = df['period'].unique()
        end_indices = df.groupby('period').indices

        rev_to_idx = {r_id: idx for idx, r_id in enumerate(reviewer_ids)}
        prod_to_idx = {p_id: idx for idx, p_id in enumerate(asin_ids)}
        mapped_rev = df['reviewer_id'].map(rev_to_idx).values
        mapped_prod = df[product_id_col].map(prod_to_idx).values

        rev_scores = np.zeros(len(df), dtype=np.float32)
        prod_scores = np.zeros(len(df), dtype=np.float32)

        latest_rev = np.zeros(len(reviewer_ids), dtype=np.float32)
        latest_prod = np.zeros(len(asin_ids), dtype=np.float32)

        print(f"[INFO] Stepping across {len(periods):,} rolling temporal windows...")
        with torch.no_grad():
            for idx_p, p in enumerate(periods):
                p_indices = end_indices[p]
                end_idx = p_indices[-1]
                sub_edges = {et: ei[:, :end_idx+1] for et, ei in data.edge_index_dict.items()}
                out_dict = model(data.x_dict, sub_edges)
                latest_prod = torch.sigmoid(out_dict['product'].squeeze(-1)).cpu().numpy()
                latest_rev = torch.sigmoid(out_dict['reviewer'].squeeze(-1)).cpu().numpy()

                rev_scores[p_indices] = latest_rev[mapped_rev[p_indices]]
                prod_scores[p_indices] = latest_prod[mapped_prod[p_indices]]

                if (idx_p + 1) % 50 == 0 or (idx_p + 1) == len(periods):
                    print(f"       Window {idx_p+1}/{len(periods)} completed ({time.time()-t0:.1f}s)")

        rev_scores = np.round(rev_scores, 4)
        prod_scores = np.round(prod_scores, 4)
        print(f"[OK] Completed rolling temporal evaluation in {time.time() - t0:.2f}s")

    # In HGAT anomaly detection: probability >= threshold indicates Anomaly/Fake (1), else Normal/Genuine (0)
    pred_product = (prod_scores >= thresh_p).astype(int)
    pred_reviewer = (rev_scores >= thresh_r).astype(int)

    # Map node predictions back to review IDs
    print("\n-- 3. Mapping Node Scores to Reviews & Saving -----------------------------")
    output_df = pd.DataFrame({
        "review_id": df["review_id"],
        "reviewer_id": df["reviewer_id"],
        "product_id": df[product_id_col],
        "reviewer_model_score": rev_scores,
        "reviewer_prediction": pred_reviewer,
        "reviewee_score": prod_scores,
        "reviewee_label": pred_product
    })

    output_df.to_csv(output_csv, index=False)
    print(f"[OK] Saved HGAT predictions ({len(output_df):,} rows) to: {output_csv}")

    # Summary
    rev_fake_cnt = (output_df["reviewer_prediction"] == 1).sum()
    prod_fake_cnt = (output_df["reviewee_label"] == 1).sum()
    print("\n-- HGAT Prediction Summary --")
    print(f"   Total Reviews Evaluated      : {len(output_df):,}")
    print(f"   Reviewers Classified Fake (1): {rev_fake_cnt:,} ({rev_fake_cnt/len(output_df)*100:.1f}%)")
    print(f"   Products Classified Fake (1) : {prod_fake_cnt:,} ({prod_fake_cnt/len(output_df)*100:.1f}%)")
    print("=" * 70)


if __name__ == "__main__":
    main()
