"""
Generate Premium Evaluation Plots for 2-Feature Late Fusion Models
==================================================================
Generates high-resolution Confusion Matrices and Overlapping Probability Histograms
for the best performing models on the universal Test Set across Reviewer & Review heads:
1. Reviewer Head: XGBoost / LightGBM
2. Review Head: XGBoost / LightGBM / MLP
"""

import os
import sys
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split

# Configure stdout encoding for Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def setup_plot_style():
    """Applies modern sleek styling for visualizations."""
    plt.style.use('dark_background')
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.size': 12,
        'axes.labelsize': 14,
        'axes.titlesize': 16,
        'xtick.labelsize': 11,
        'ytick.labelsize': 11,
        'figure.titlesize': 18,
        'grid.color': '#2A2A2A',
        'grid.linestyle': '--',
        'grid.linewidth': 0.7
    })

def plot_confusion_matrix(y_true, y_pred, labels, title, save_path):
    cm = confusion_matrix(y_true, y_pred)
    cm_norm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
    
    fig, ax = plt.subplots(figsize=(7, 6))
    cax = ax.matshow(cm_norm, cmap=plt.cm.Blues, alpha=0.85)
    
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            val_str = f"{cm[i, j]:,}\n({cm_norm[i, j]*100:.1f}%)"
            color = "white" if cm_norm[i, j] > 0.5 else "black"
            ax.text(j, i, val_str, va='center', ha='center', color=color, fontsize=13, fontweight='bold')
            
    fig.colorbar(cax, fraction=0.046, pad=0.04)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_yticklabels(labels)
    ax.xaxis.set_ticks_position('bottom')
    
    plt.title(title, pad=20, fontweight='bold', color='#00D2FF')
    plt.ylabel('Ground Truth Label', fontweight='bold', labelpad=10)
    plt.xlabel('Predicted Label', fontweight='bold', labelpad=10)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, facecolor='#121212', edgecolor='none')
    plt.close()
    print(f"✅ Saved Confusion Matrix to: {save_path.name}")

def plot_overlapping_histogram(y_true, y_probs, title, save_path):
    fig, ax = plt.subplots(figsize=(9, 6))
    
    probs_genuine = y_probs[y_true == 0]
    probs_fraud = y_probs[y_true == 1]
    
    bins = np.linspace(0, 1, 50)
    
    ax.hist(probs_genuine, bins=bins, alpha=0.65, color='#00FFAA', label=f'Genuine (n={len(probs_genuine):,})', density=True, edgecolor='black', linewidth=0.5)
    ax.hist(probs_fraud, bins=bins, alpha=0.65, color='#FF3366', label=f'Fraud (n={len(probs_fraud):,})', density=True, edgecolor='black', linewidth=0.5)
    
    ax.set_title(title, pad=15, fontweight='bold', color='#00D2FF')
    ax.set_xlabel('Predicted Fraud Probability Score', fontweight='bold', labelpad=10)
    ax.set_ylabel('Normalized Density', fontweight='bold', labelpad=10)
    ax.grid(True)
    ax.legend(frameon=True, facecolor='#1E1E1E', edgecolor='#444444', fontsize=12)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, facecolor='#121212', edgecolor='none')
    plt.close()
    print(f"✅ Saved Overlapping Histogram to: {save_path.name}")

def main():
    print("═" * 80)
    print("  Generating Evaluation Plots on Universal 80/10/10 Test Set (seed=42)")
    print("═" * 80)
    
    setup_plot_style()
    
    script_dir = Path(__file__).resolve().parent
    data_path = script_dir / "late_fusion_features.csv"
    models_dir = script_dir / "saved_models"
    plots_dir = script_dir / "evaluation_plots"
    plots_dir.mkdir(exist_ok=True)
    
    df = pd.read_csv(data_path)
    
    # Define exact feature subsets per task
    X_r = df[['gnn_reviewer_score', 'deberta_spam_prob', 'user_avg_past_deberta_score']].values
    X_rev = df[['deberta_spam_prob', 'gnn_review_score']].values
    
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
    
    X_test_r = X_r[test_idx]
    X_test_rev = X_rev[test_idx]
    y_test = y_target[test_idx]
    
    print(f"✅ Universal Labeled Test Set Size: {len(test_idx):,} rows")
    
    # 1. Reviewer Head: XGBoost
    print("\n── 1. Evaluating Reviewer Head: XGBoost Classifier ───────────────")
    xgb_r = joblib.load(models_dir / "xgboost_reviewer_model.joblib")
    probs_r_xgb = xgb_r.predict_proba(X_test_r)[:, 1]
    preds_r_xgb = (probs_r_xgb >= 0.50).astype(int)
    
    plot_confusion_matrix(
        y_test, preds_r_xgb, ['Honest Reviewer', 'Fake Reviewer'],
        'Reviewer Head Late Fusion (XGBoost) - Confusion Matrix',
        plots_dir / "reviewer_xgboost_confusion_matrix.png"
    )
    plot_overlapping_histogram(
        y_test, probs_r_xgb,
        'Reviewer Head Late Fusion (XGBoost) - Score Distribution',
        plots_dir / "reviewer_xgboost_overlapping_histogram.png"
    )

    # 2. Reviewer Head: LightGBM
    print("\n── 2. Evaluating Reviewer Head: LightGBM Classifier ───────────────")
    lgb_r = joblib.load(models_dir / "lightgbm_reviewer_model.joblib")
    probs_r_lgb = lgb_r.predict_proba(X_test_r)[:, 1]
    preds_r_lgb = (probs_r_lgb >= 0.50).astype(int)
    
    plot_confusion_matrix(
        y_test, preds_r_lgb, ['Honest Reviewer', 'Fake Reviewer'],
        'Reviewer Head Late Fusion (LightGBM) - Confusion Matrix',
        plots_dir / "reviewer_lightgbm_confusion_matrix.png"
    )
    plot_overlapping_histogram(
        y_test, probs_r_lgb,
        'Reviewer Head Late Fusion (LightGBM) - Score Distribution',
        plots_dir / "reviewer_lightgbm_overlapping_histogram.png"
    )

    # 3. Review Head: XGBoost
    print("\n── 3. Evaluating Review Head: XGBoost Classifier ──────────────────")
    xgb_rev = joblib.load(models_dir / "xgboost_review_model.joblib")
    probs_rev_xgb = xgb_rev.predict_proba(X_test_rev)[:, 1]
    preds_rev_xgb = (probs_rev_xgb >= 0.50).astype(int)
    
    plot_confusion_matrix(
        y_test, preds_rev_xgb, ['Honest Review', 'Fake Review'],
        'Review Head Late Fusion (XGBoost) - Confusion Matrix',
        plots_dir / "review_xgboost_confusion_matrix.png"
    )
    plot_overlapping_histogram(
        y_test, probs_rev_xgb,
        'Review Head Late Fusion (XGBoost) - Score Distribution',
        plots_dir / "review_xgboost_overlapping_histogram.png"
    )

    # 4. Review Head: MLP
    print("\n── 4. Evaluating Review Head: Multi-Layer Perceptron (MLP) ────────")
    mlp_rev = joblib.load(models_dir / "mlp_review_model.joblib")
    scaler_rev = joblib.load(models_dir / "scaler_review.joblib")
    X_test_rev_s = scaler_rev.transform(X_test_rev)
    probs_rev_mlp = mlp_rev.predict_proba(X_test_rev_s)[:, 1]
    preds_rev_mlp = (probs_rev_mlp >= 0.50).astype(int)
    
    plot_confusion_matrix(
        y_test, preds_rev_mlp, ['Honest Review', 'Fake Review'],
        'Review Head Late Fusion (MLP) - Confusion Matrix',
        plots_dir / "review_mlp_confusion_matrix.png"
    )
    plot_overlapping_histogram(
        y_test, probs_rev_mlp,
        'Review Head Late Fusion (MLP) - Score Distribution',
        plots_dir / "review_mlp_overlapping_histogram.png"
    )

    print("\n✅ All evaluation plots saved to:", plots_dir)
    print("═" * 80)

if __name__ == "__main__":
    main()
