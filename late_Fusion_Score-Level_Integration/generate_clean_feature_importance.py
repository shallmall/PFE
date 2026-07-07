import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import xgboost as xgb
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

# Configure stdout encoding for Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def main():
    print("═" * 75)
    print("  Generating Clean Feature Importance Plots (Reviewer vs Review Heads)")
    print("═" * 75)

    script_dir = Path(__file__).resolve().parent
    data_path = script_dir / "late_fusion_features.csv"

    df = pd.read_csv(data_path)
    
    # Define exact feature subsets per task
    features_r = ['gnn_reviewer_score', 'deberta_spam_prob', 'user_avg_past_deberta_score']
    features_rev = ['deberta_spam_prob', 'gnn_review_score']
    
    X_r = df[features_r].values
    X_rev = df[features_rev].values
    
    # Define targets Y using exact hierarchical tagging logic
    honest_cols = ['reviewer_labeled_honest', 'reviewer_classified_honest']
    fake_cols = ['reviewer_labeled_fake', 'reviewer_classified_fake']

    df['tag'] = np.nan
    cond_tag_1 = (df[honest_cols[0]] == 1) | (df[honest_cols[0]] == True) | (df[honest_cols[1]] == 1) | (df[honest_cols[1]] == True)
    df.loc[cond_tag_1, 'tag'] = 0

    cond_tag_0 = ((df[fake_cols[0]] == 1) | (df[fake_cols[0]] == True) | (df[fake_cols[1]] == 1) | (df[fake_cols[1]] == True)) & df['tag'].isna()
    df.loc[cond_tag_0, 'tag'] = 1

    mask = df['tag'].notna().values
    y_target = np.zeros(len(df), dtype=int)
    y_target[mask] = df.loc[mask, 'tag'].astype(int).values
    
    # Stratified 80/10/10 split with seed=42 on labeled indices
    labeled_indices = np.where(mask)[0]
    train_val_idx, test_idx = train_test_split(labeled_indices, test_size=0.10, random_state=42, stratify=y_target[labeled_indices])
    train_idx, val_idx = train_test_split(train_val_idx, test_size=1/9, random_state=42, stratify=y_target[train_val_idx])

    X_r_train, y_train = X_r[train_idx], y_target[train_idx]
    X_r_val, y_val     = X_r[val_idx], y_target[val_idx]
    
    X_rev_train = X_rev[train_idx]
    X_rev_val   = X_rev[val_idx]

    # ── 1. Best Reviewer Model: LightGBM Classifier ───────────────
    print("Fitting Best Reviewer Classifier (LightGBM)...")
    lgb_r = lgb.LGBMClassifier(n_estimators=300, max_depth=5, learning_rate=0.05, random_state=42, verbose=-1)
    lgb_r.fit(X_r_train, y_train, eval_set=[(X_r_val, y_val)], callbacks=[lgb.early_stopping(20, verbose=False)])
    r_imp = lgb_r.feature_importances_
    r_imp_pct = (r_imp / r_imp.sum()) * 100

    # ── 2. Best Review Model: Logistic Regression (ElasticNet) ──────────────
    print("Fitting Best Review Classifier (ElasticNet)...")
    scaler_rev = StandardScaler()
    X_rev_train_s = scaler_rev.fit_transform(X_rev_train)
    lr_rev = LogisticRegression(solver='saga', l1_ratio=0.5, C=1.0, max_iter=500, random_state=42)
    lr_rev.fit(X_rev_train_s, y_train)
    rev_imp = np.abs(lr_rev.coef_[0])
    rev_imp_pct = (rev_imp / rev_imp.sum()) * 100

    # Plot Settings
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5))

    # Panel A: Reviewer Classifier Feature Importance (3 Features over Time)
    labels_r = ['HGT Reviewer Score', 'DeBERTa Spam Prob', 'User Avg Past DeBERTa']
    ax1.barh(np.arange(len(labels_r)), r_imp_pct, color='#2b5c8f', height=0.5, edgecolor='black', alpha=0.9)
    ax1.set_yticks(np.arange(len(labels_r)))
    ax1.set_yticklabels(labels_r, fontsize=11.5, fontweight='medium')
    ax1.set_xlabel('Relative Contribution (%)', fontsize=12, fontweight='bold')
    ax1.set_title('Reviewer Fraud Classifier (LightGBM)', fontsize=13, fontweight='bold', pad=12)
    ax1.grid(axis='x', linestyle='--', alpha=0.7)
    for i, v in enumerate(r_imp_pct):
        ax1.text(v + 1.0, i, f"{v:.1f}%", va='center', fontsize=10.5, fontweight='bold', color='#1a3a5c')
    ax1.set_xlim(0, 100)

    # Panel B: Review Classifier Feature Importance (2 Features)
    labels_rev = ['DeBERTa Spam Prob', 'HGT Review Score']
    ax2.barh(np.arange(len(labels_rev)), rev_imp_pct, color='#d95f02', height=0.5, edgecolor='black', alpha=0.9)
    ax2.set_yticks(np.arange(len(labels_rev)))
    ax2.set_yticklabels(labels_rev, fontsize=11.5, fontweight='medium')
    ax2.set_xlabel('Relative Contribution (%)', fontsize=12, fontweight='bold')
    ax2.set_title('Review Fraud Classifier (ElasticNet)', fontsize=13, fontweight='bold', pad=12)
    ax2.grid(axis='x', linestyle='--', alpha=0.7)
    for i, v in enumerate(rev_imp_pct):
        ax2.text(v + 1.0, i, f"{v:.1f}%", va='center', fontsize=10.5, fontweight='bold', color='#8c3d01')
    ax2.set_xlim(0, 100)

    plt.tight_layout()
    fig_path = script_dir / "clean_feature_importance_best_models.png"
    plt.savefig(fig_path, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"\nSaved dedicated feature importance plot to: {fig_path}")
    print("═" * 75)

if __name__ == "__main__":
    main()
