import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import xgboost as xgb
import lightgbm as lgb
from sklearn.model_selection import train_test_split

# Configure stdout encoding for Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def main():
    print("═" * 75)
    print("  Late Fusion Meta-Classifiers: Feature Importance Analysis (Universal Split)")
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

    # ── 1. Train XGBoost ─────────────────────────────────────────────────
    print("\nTraining XGBoost models to extract Feature Importance...")
    xgb_r = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.05, eval_metric='logloss', early_stopping_rounds=20, random_state=42)
    xgb_r.fit(X_r_train, y_train, eval_set=[(X_r_val, y_val)], verbose=False)
    xgb_r_imp = xgb_r.feature_importances_
    xgb_r_imp_pct = (xgb_r_imp / xgb_r_imp.sum()) * 100

    xgb_rev = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.05, eval_metric='logloss', early_stopping_rounds=20, random_state=42)
    xgb_rev.fit(X_rev_train, y_train, eval_set=[(X_rev_val, y_val)], verbose=False)
    xgb_rev_imp = xgb_rev.feature_importances_
    xgb_rev_imp_pct = (xgb_rev_imp / xgb_rev_imp.sum()) * 100

    # ── 2. Train LightGBM ────────────────────────────────────────────────
    print("Training LightGBM models to extract Feature Importance...")
    lgb_r = lgb.LGBMClassifier(n_estimators=300, max_depth=5, learning_rate=0.05, random_state=42, verbose=-1, importance_type='gain')
    lgb_r.fit(X_r_train, y_train, eval_set=[(X_r_val, y_val)], callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)])
    lgb_r_imp = lgb_r.feature_importances_
    lgb_r_imp_pct = (lgb_r_imp / lgb_r_imp.sum()) * 100

    lgb_rev = lgb.LGBMClassifier(n_estimators=300, max_depth=5, learning_rate=0.05, random_state=42, verbose=-1, importance_type='gain')
    lgb_rev.fit(X_rev_train, y_train, eval_set=[(X_rev_val, y_val)], callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)])
    lgb_rev_imp = lgb_rev.feature_importances_
    lgb_rev_imp_pct = (lgb_rev_imp / lgb_rev_imp.sum()) * 100

    # Print Tables
    print("\n── REVIEWER HEAD FEATURE IMPORTANCE (%) ─────────────────────────────")
    df_rev_head = pd.DataFrame({
        'Feature': ['GNN Reviewer Score', 'DeBERTa Spam Prob', 'User Avg Past DeBERTa'],
        'XGBoost (%)': xgb_r_imp_pct,
        'LightGBM (%)': lgb_r_imp_pct
    })
    print(df_rev_head.to_string(index=False))

    print("\n── REVIEW HEAD FEATURE IMPORTANCE (%) ───────────────────────────────")
    df_review_head = pd.DataFrame({
        'Feature': ['DeBERTa Spam Prob', 'GNN Review Score'],
        'XGBoost (%)': xgb_rev_imp_pct,
        'LightGBM (%)': lgb_rev_imp_pct
    })
    print(df_review_head.to_string(index=False))

    # ── 3. Generate Publication Figure ───────────────────────────────────
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5))

    # Left Plot: Reviewer Head (3 Features over Time)
    y_pos_r = np.arange(3)
    height = 0.35
    labels_r = ['GNN Reviewer Score', 'DeBERTa Spam Prob', 'User Avg Past DeBERTa']
    ax1.barh(y_pos_r - height/2, xgb_r_imp_pct, height, label='XGBoost', color='#2b5c8f', alpha=0.9)
    ax1.barh(y_pos_r + height/2, lgb_r_imp_pct, height, label='LightGBM (Gain)', color='#41b6c4', alpha=0.9)
    ax1.set_yticks(y_pos_r)
    ax1.set_yticklabels(labels_r, fontsize=11)
    ax1.set_xlabel('Relative Importance (%)', fontsize=12, fontweight='bold')
    ax1.set_title('Reviewer Head Feature Importance (3-Var over Time)', fontsize=13, fontweight='bold')
    ax1.legend(loc='lower right', fontsize=11)
    ax1.grid(axis='x', linestyle='--', alpha=0.7)
    ax1.set_xlim(0, 100)

    # Right Plot: Review Head (2 Features)
    y_pos_rev = np.arange(2)
    labels_rev = ['DeBERTa Spam Prob', 'GNN Review Score']
    ax2.barh(y_pos_rev - height/2, xgb_rev_imp_pct, height, label='XGBoost', color='#d95f02', alpha=0.9)
    ax2.barh(y_pos_rev + height/2, lgb_rev_imp_pct, height, label='LightGBM (Gain)', color='#fdae61', alpha=0.9)
    ax2.set_yticks(y_pos_rev)
    ax2.set_yticklabels(labels_rev, fontsize=11)
    ax2.set_xlabel('Relative Importance (%)', fontsize=12, fontweight='bold')
    ax2.set_title('Review Head Feature Importance (2-Var Transaction Level)', fontsize=13, fontweight='bold')
    ax2.legend(loc='lower right', fontsize=11)
    ax2.grid(axis='x', linestyle='--', alpha=0.7)
    ax2.set_xlim(0, 100)

    plt.tight_layout()
    fig_path = script_dir / "feature_importance_best_models.png"
    plt.savefig(fig_path, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"\nPublication-ready figure saved successfully to: {fig_path}")
    print("═" * 75)

if __name__ == "__main__":
    main()
