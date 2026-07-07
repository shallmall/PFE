import os
import sys
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.model_selection import train_test_split

def plot_confidence_distribution(y_true, y_prob, title, ax, color_honest="#1f77b4", color_fake="#d62728"):
    prob_honest = y_prob[y_true == 0]
    prob_fake = y_prob[y_true == 1]
    
    bins = np.linspace(0.0, 1.0, 45)
    
    # Plot Histograms
    ax.hist(prob_honest, bins=bins, density=True, color=color_honest, alpha=0.55, edgecolor='black', linewidth=0.8, label=f"True Honest (n={len(prob_honest):,})")
    ax.hist(prob_fake, bins=bins, density=True, color=color_fake, alpha=0.55, edgecolor='black', linewidth=0.8, label=f"True Fake (n={len(prob_fake):,})")
    
    ax.set_title(title, fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel(r"Predicted Fraud Confidence Score (Probability $\hat{y}$)", fontsize=12, fontweight='bold')
    ax.set_ylabel("Density / Normalized Frequency", fontsize=12, fontweight='bold')
    ax.set_xlim(-0.02, 1.02)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper center", fontsize=11, frameon=True, facecolor="white", edgecolor="black")

def main():
    print("Generating Confidence Probability Distribution Histograms on Universal Test Set...")
    script_dir = Path(__file__).resolve().parent
    data_path = script_dir / "late_fusion_features.csv"
    models_dir = script_dir / "saved_models"
    
    df = pd.read_csv(data_path)
    
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
    
    # Load Top Performing Models
    xgb_r = joblib.load(models_dir / "xgboost_reviewer_model.joblib")
    xgb_rev = joblib.load(models_dir / "xgboost_review_model.joblib")
    
    prob_r_test = xgb_r.predict_proba(X_test_r)[:, 1]
    prob_rev_test = xgb_rev.predict_proba(X_test_rev)[:, 1]
    
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    
    plot_confidence_distribution(y_test, prob_r_test, "Reviewer Head (XGBoost - Universal Test Set)", axes[0], color_honest="#1b9e77", color_fake="#d95f02")
    plot_confidence_distribution(y_test, prob_rev_test, "Review Head (XGBoost - Universal Test Set)", axes[1], color_honest="#2b5c8f", color_fake="#d95f02")
    
    plt.tight_layout()
    output_path = script_dir / "late_fusion_confidence_histograms.png"
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Saved High-Resolution Confidence Histograms to: {output_path}")

if __name__ == "__main__":
    main()
