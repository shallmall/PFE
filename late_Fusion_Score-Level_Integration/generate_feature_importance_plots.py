import os
import sys
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# Configure stdout encoding for Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def main():
    print("=" * 80)
    print("  Late Fusion Feature Importance Extraction & Plotting")
    print("=" * 80)

    script_dir = Path(__file__).resolve().parent
    models_dir = script_dir / "saved_models"

    xgb_r = joblib.load(models_dir / "xgboost_reviewer_model.joblib")
    xgb_rev = joblib.load(models_dir / "xgboost_review_model.joblib")

    # Features for Reviewer Head
    feats_r = ['GNN Reviewer Score', 'DeBERTa Spam Prob', 'User Avg Past DeBERTa']
    imp_r = xgb_r.feature_importances_
    imp_r_pct = (imp_r / imp_r.sum()) * 100

    # Features for Review Head
    feats_rev = ['DeBERTa Spam Prob', 'GNN Review Score']
    imp_rev = xgb_rev.feature_importances_
    imp_rev_pct = (imp_rev / imp_rev.sum()) * 100

    print("\n🔹 Reviewer Head Feature Importance (XGBoost):")
    for f, val in zip(feats_r, imp_r_pct):
        print(f"   • {f:<22} : {val:.2f}%")

    print("\n🔹 Review Head Feature Importance (XGBoost):")
    for f, val in zip(feats_rev, imp_rev_pct):
        print(f"   • {f:<22} : {val:.2f}%")

    # Also check LightGBM
    lgb_r = joblib.load(models_dir / "lightgbm_reviewer_model.joblib")
    lgb_rev = joblib.load(models_dir / "lightgbm_review_model.joblib")

    lgb_imp_r = lgb_r.booster_.feature_importance(importance_type='gain')
    lgb_imp_r_pct = (lgb_imp_r / lgb_imp_r.sum()) * 100

    lgb_imp_rev = lgb_rev.booster_.feature_importance(importance_type='gain')
    lgb_imp_rev_pct = (lgb_imp_rev / lgb_imp_rev.sum()) * 100

    print("\n🔹 Reviewer Head Feature Importance (LightGBM Gain):")
    for f, val in zip(feats_r, lgb_imp_r_pct):
        print(f"   • {f:<22} : {val:.2f}%")

    print("\n🔹 Review Head Feature Importance (LightGBM Gain):")
    for f, val in zip(feats_rev, lgb_imp_rev_pct):
        print(f"   • {f:<22} : {val:.2f}%")

    # Plotting side by side
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5))

    # Ax 1: Reviewer Head
    bars1 = ax1.bar(feats_r, imp_r_pct, color=['#2b5c8f', '#d95f02', '#41b6c4'], width=0.5, edgecolor='black')
    ax1.set_ylabel('Relative Importance (%)', fontsize=12, fontweight='bold')
    ax1.set_title('Reviewer Classification Head (XGBoost)', fontsize=13, fontweight='bold', pad=12)
    ax1.set_ylim(0, 100)
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 2, f'{yval:.1f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')

    # Ax 2: Review Head
    bars2 = ax2.bar(feats_rev, imp_rev_pct, color=['#2b5c8f', '#7570b3'], width=0.5, edgecolor='black')
    ax2.set_ylabel('Relative Importance (%)', fontsize=12, fontweight='bold')
    ax2.set_title('Review Classification Head (XGBoost)', fontsize=13, fontweight='bold', pad=12)
    ax2.set_ylim(0, 100)
    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2.0, yval + 2, f'{yval:.1f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')

    plt.tight_layout()
    plot_path = script_dir / "late_fusion_2feat_importance.png"
    plt.savefig(plot_path, dpi=300)
    print(f"\n✅ Saved feature importance comparison chart to: {plot_path}")
    print("=" * 80)

if __name__ == "__main__":
    main()
