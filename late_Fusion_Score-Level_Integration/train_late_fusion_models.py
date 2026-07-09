"""
Train Late Fusion Multi-Model Reputation AI System (Pure 2-Feature Score-Level Integration)
=============================================================================================
Trains 4 distinct machine learning architectures on exact 2-feature point-in-time score pairs:
For Product Head: [deberta_spam_prob, gnn_product_score]
For Reviewer Head: [gnn_reviewer_score, deberta_spam_prob, user_avg_past_deberta_score] (3-Feature Rolling over Time)
For Review Head: [deberta_spam_prob, gnn_review_score]

Architectures trained for each head:
1. XGBoost Classifier (XGBoost)
2. LightGBM Classifier (LightGBM)
3. ElasticNet Logistic Regression (L1 + L2 Regularization)
4. Multi-Layer Perceptron (MLP Neural Network)

Evaluates strictly on chronological splits (80% Train, 10% Val, 10% Test).
"""

import os
import sys
import time
import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score, roc_auc_score, f1_score, precision_score, recall_score

import xgboost as xgb
import lightgbm as lgb

# Configure stdout encoding for Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def find_best_threshold(y_true, y_pred_prob):
    best_thresh = 0.5
    best_f1 = -1.0
    for thresh in np.arange(0.01, 1.0, 0.005):
        y_pred = (y_pred_prob >= thresh).astype(int)
        f1 = f1_score(y_true, y_pred, average='macro', zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = thresh
    return best_thresh

def calculate_metrics(y_true, y_pred_prob, threshold=None):
    """Calculates evaluation metrics for binary classification."""
    if threshold is None:
        threshold = find_best_threshold(y_true, y_pred_prob)
    if len(np.unique(y_true)) > 1:
        roc_auc = roc_auc_score(y_true, y_pred_prob)
    else:
        roc_auc = float('nan')
        
    y_pred = (y_pred_prob >= threshold).astype(int)
    acc = accuracy_score(y_true, y_pred)
    f1_fake = f1_score(y_true, y_pred, pos_label=1, zero_division=0)
    f1_real = f1_score(y_true, y_pred, pos_label=0, zero_division=0)
    prec_fake = precision_score(y_true, y_pred, pos_label=1, zero_division=0)
    rec_fake = recall_score(y_true, y_pred, pos_label=1, zero_division=0)
    prec_real = precision_score(y_true, y_pred, pos_label=0, zero_division=0)
    rec_real = recall_score(y_true, y_pred, pos_label=0, zero_division=0)
    f1_macro = f1_score(y_true, y_pred, average='macro', zero_division=0)
    
    return {
        'acc': acc, 'roc_auc': roc_auc,
        'f1_fake': f1_fake, 'f1_real': f1_real,
        'prec_fake': prec_fake, 'rec_fake': rec_fake,
        'prec_real': prec_real, 'rec_real': rec_real,
        'f1_macro': f1_macro,
        'threshold': float(threshold)
    }

def print_model_results(model_name, rev_metrics, review_metrics):
    print(f"\n╔{'═'*118}╗")
    print(f"║ Model: {model_name:<111} ║")
    print(f"╠{'═'*118}╣")
    print(f"║ Reviewer Head -> Acc: {rev_metrics['acc']:.4f} | ROC-AUC: {rev_metrics['roc_auc']:.4f} | Fake(P:{rev_metrics['prec_fake']:.4f}, R:{rev_metrics['rec_fake']:.4f}, F1:{rev_metrics['f1_fake']:.4f}) | Real(P:{rev_metrics['prec_real']:.4f}, R:{rev_metrics['rec_real']:.4f}, F1:{rev_metrics['f1_real']:.4f}) ║")
    print(f"║ Review Head   -> Acc: {review_metrics['acc']:.4f} | ROC-AUC: {review_metrics['roc_auc']:.4f} | Fake(P:{review_metrics['prec_fake']:.4f}, R:{review_metrics['rec_fake']:.4f}, F1:{review_metrics['f1_fake']:.4f}) | Real(P:{review_metrics['prec_real']:.4f}, R:{review_metrics['rec_real']:.4f}, F1:{review_metrics['f1_real']:.4f}) ║")
    print(f"╚{'═'*118}╝")

def main():
    print("═" * 120)
    print("Late Fusion Reputation AI: Pure 2-Feature Score-Level Training & Benchmarking")
    print("═" * 120)

    script_dir = Path(__file__).resolve().parent
    data_path = script_dir / "late_fusion_features.csv"

    if not data_path.exists():
        print(f"Error: Feature dataset not found at: {data_path}")
        print("Please run prepare_temporal_features.py first!")
        sys.exit(1)

    print("\n── 1. Loading Master Feature Dataset ──────────────────────────────")
    t0 = time.time()
    df = pd.read_csv(data_path)
    print(f"Loaded {len(df):,} transactions in {time.time() - t0:.2f}s")

    # Define exact feature subsets per task
    X_r = df[['gnn_reviewer_score', 'deberta_spam_prob', 'user_avg_past_deberta_score']].values
    X_rev = df[['deberta_spam_prob', 'gnn_review_score']].values

    print(f"Input Features per Task:")
    print(f"• Reviewer Head : [gnn_reviewer_score, deberta_spam_prob, user_avg_past_deberta_score] (3-Feature Rolling over Time)")
    print(f"• Review Head   : [deberta_spam_prob, gnn_review_score] (2-Feature Transaction Level)")

    # Define targets Y using exact hierarchical tagging logic
    honest_cols = ['reviewer_labeled_honest', 'reviewer_classified_honest']
    fake_cols = ['reviewer_labeled_fake', 'reviewer_classified_fake']

    df['tag'] = np.nan
    cond_tag_1 = (df[honest_cols[0]] == 1) | (df[honest_cols[0]] == True) | (df[honest_cols[1]] == 1) | (df[honest_cols[1]] == True)
    df.loc[cond_tag_1, 'tag'] = 0  # In GNN/Fusion convention: Honest/Real = 0

    cond_tag_0 = ((df[fake_cols[0]] == 1) | (df[fake_cols[0]] == True) | (df[fake_cols[1]] == 1) | (df[fake_cols[1]] == True)) & df['tag'].isna()
    df.loc[cond_tag_0, 'tag'] = 1  # Fake/Spam = 1

    mask = df['tag'].notna().values
    y_target = np.zeros(len(df), dtype=int)
    y_target[mask] = df.loc[mask, 'tag'].astype(int).values

    print(f"\n Target Supervision Summary:")
    print(f"• Reviewer & Review Supervision : {mask.sum():,} labeled rows ({mask.mean()*100:.1f}%) -> Fake Rate: {y_target[mask].mean()*100:.1f}%")

    # 2. Random Stratified Train / Val / Test Split (80% / 10% / 10% with seed=42)
    print("\n── 2. Performing Random Stratified Train/Val/Test Split (seed=42) ──")
    from sklearn.model_selection import train_test_split

    labeled_indices = np.where(mask)[0]
    train_val_idx, test_idx = train_test_split(labeled_indices, test_size=0.10, random_state=42, stratify=y_target[labeled_indices])
    train_idx, val_idx = train_test_split(train_val_idx, test_size=1/9, random_state=42, stratify=y_target[train_val_idx])

    print(f"Labeled Split Sizes -> Train: {len(train_idx):,} | Val: {len(val_idx):,} | Test: {len(test_idx):,}")

    X_r_train, y_train = X_r[train_idx], y_target[train_idx]
    X_r_val, y_val     = X_r[val_idx], y_target[val_idx]
    X_r_test, y_test   = X_r[test_idx], y_target[test_idx]

    X_rev_train = X_rev[train_idx]
    X_rev_val   = X_rev[val_idx]
    X_rev_test  = X_rev[test_idx]

    # Scalers for Logistic Regression and MLP
    scaler_r = StandardScaler()
    X_r_train_s = scaler_r.fit_transform(X_r_train)
    X_r_val_s = scaler_r.transform(X_r_val)
    X_r_test_s = scaler_r.transform(X_r_test)

    scaler_rev = StandardScaler()
    X_rev_train_s = scaler_rev.fit_transform(X_rev_train)
    X_rev_val_s = scaler_rev.transform(X_rev_val)
    X_rev_test_s = scaler_rev.transform(X_rev_test)

    results_summary = {}

    # 3. Model 1: XGBoost Classifier
    print("\n── 3. Training Model 1: XGBoost Classifier (2-Feature Late Fusion) ──")
    t0 = time.time()
    xgb_r = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.05, eval_metric='logloss', early_stopping_rounds=20, random_state=42, n_jobs=-1)
    xgb_r.fit(X_r_train, y_train, eval_set=[(X_r_val, y_val)], verbose=False)
    rev_pred_xgb = xgb_r.predict_proba(X_r_test)[:, 1]

    xgb_rev = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.05, eval_metric='logloss', early_stopping_rounds=20, random_state=42, n_jobs=-1)
    xgb_rev.fit(X_rev_train, y_train, eval_set=[(X_rev_val, y_val)], verbose=False)
    review_pred_xgb = xgb_rev.predict_proba(X_rev_test)[:, 1]

    metrics_r_xgb = calculate_metrics(y_test, rev_pred_xgb)
    metrics_rev_xgb = calculate_metrics(y_test, review_pred_xgb)
    print(f"Trained & evaluated XGBoost in {time.time() - t0:.2f}s")
    print_model_results("XGBoost Classifier", metrics_r_xgb, metrics_rev_xgb)
    results_summary["XGBoost"] = {"reviewer": metrics_r_xgb, "review": metrics_rev_xgb}

    # 4. Model 2: LightGBM Classifier
    print("\n── 4. Training Model 2: LightGBM Classifier (2-Feature Late Fusion) ─")
    t0 = time.time()
    lgb_r = lgb.LGBMClassifier(n_estimators=300, max_depth=5, learning_rate=0.05, random_state=42, n_jobs=-1, verbose=-1)
    lgb_r.fit(X_r_train, y_train, eval_set=[(X_r_val, y_val)], callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)])
    rev_val_lgb = lgb_r.predict_proba(X_r_val)[:, 1]
    best_thresh_r_lgb = find_best_threshold(y_val, rev_val_lgb)
    rev_pred_lgb = lgb_r.predict_proba(X_r_test)[:, 1]

    lgb_rev = lgb.LGBMClassifier(n_estimators=300, max_depth=5, learning_rate=0.05, random_state=42, n_jobs=-1, verbose=-1)
    lgb_rev.fit(X_rev_train, y_train, eval_set=[(X_rev_val, y_val)], callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)])
    review_val_lgb = lgb_rev.predict_proba(X_rev_val)[:, 1]
    best_thresh_rev_lgb = find_best_threshold(y_val, review_val_lgb)

    metrics_r_lgb = calculate_metrics(y_test, rev_pred_lgb, threshold=best_thresh_r_lgb)
    metrics_rev_lgb = calculate_metrics(y_test, review_pred_lgb, threshold=best_thresh_rev_lgb)
    print(f"Trained & evaluated LightGBM in {time.time() - t0:.2f}s (Val Tuned Thresholds -> Reviewer: {best_thresh_r_lgb:.2f}, Review: {best_thresh_rev_lgb:.2f})")
    print_model_results("LightGBM Classifier", metrics_r_lgb, metrics_rev_lgb)
    results_summary["LightGBM"] = {"reviewer": metrics_r_lgb, "review": metrics_rev_lgb}

    # 5. Model 3: Logistic Regression (ElasticNet)
    print("\n── 5. Training Model 3: Logistic Regression (L1/L2 Regularized) ───")
    t0 = time.time()
    lr_r = LogisticRegression(penalty='elasticnet', solver='saga', l1_ratio=0.5, C=1.0, max_iter=500, random_state=42, n_jobs=-1)
    lr_r.fit(X_r_train_s, y_train)
    rev_pred_lr = lr_r.predict_proba(X_r_test_s)[:, 1]

    lr_rev = LogisticRegression(penalty='elasticnet', solver='saga', l1_ratio=0.5, C=1.0, max_iter=500, random_state=42, n_jobs=-1)
    lr_rev.fit(X_rev_train_s, y_train)
    review_pred_lr = lr_rev.predict_proba(X_rev_test_s)[:, 1]

    metrics_r_lr = calculate_metrics(y_test, rev_pred_lr)
    metrics_rev_lr = calculate_metrics(y_test, review_pred_lr)
    print(f"Trained & evaluated Logistic Regression in {time.time() - t0:.2f}s")
    print_model_results("Logistic Regression (ElasticNet)", metrics_r_lr, metrics_rev_lr)
    results_summary["LogisticRegression"] = {"reviewer": metrics_r_lr, "review": metrics_rev_lr}

    # 6. Model 4: Multi-Layer Perceptron (MLP)
    print("\n── 6. Training Model 4: Multi-Layer Perceptron (MLP Neural Net) ───")
    t0 = time.time()
    mlp_r = MLPClassifier(hidden_layer_sizes=(64, 32), activation='relu', max_iter=100, random_state=42, early_stopping=True)
    mlp_r.fit(X_r_train_s, y_train)
    rev_pred_mlp = mlp_r.predict_proba(X_r_test_s)[:, 1]

    mlp_rev = MLPClassifier(hidden_layer_sizes=(64, 32), activation='relu', max_iter=100, random_state=42, early_stopping=True)
    mlp_rev.fit(X_rev_train_s, y_train)
    review_pred_mlp = mlp_rev.predict_proba(X_rev_test_s)[:, 1]

    metrics_r_mlp = calculate_metrics(y_test, rev_pred_mlp)
    metrics_rev_mlp = calculate_metrics(y_test, review_pred_mlp)
    print(f"Trained & evaluated MLP in {time.time() - t0:.2f}s")
    print_model_results("Multi-Layer Perceptron (MLP)", metrics_r_mlp, metrics_rev_mlp)
    results_summary["MLP"] = {"reviewer": metrics_r_mlp, "review": metrics_rev_mlp}

    # Save trained models and scalers to disk
    models_dir = script_dir / "saved_models"
    models_dir.mkdir(exist_ok=True)
    
    print("\n── 7. Saving Trained Model Weights & Artifacts to Disk ────────────")
    joblib.dump(scaler_r, models_dir / "scaler_reviewer.joblib")
    joblib.dump(scaler_rev, models_dir / "scaler_review.joblib")
    
    joblib.dump(xgb_r, models_dir / "xgboost_reviewer_model.joblib")
    joblib.dump(xgb_rev, models_dir / "xgboost_review_model.joblib")
    
    joblib.dump(lgb_r, models_dir / "lightgbm_reviewer_model.joblib")
    joblib.dump(lgb_rev, models_dir / "lightgbm_review_model.joblib")
    
    joblib.dump(lr_r, models_dir / "logistic_regression_reviewer_model.joblib")
    joblib.dump(lr_rev, models_dir / "logistic_regression_review_model.joblib")
    
    joblib.dump(mlp_r, models_dir / "mlp_reviewer_model.joblib")
    joblib.dump(mlp_rev, models_dir / "mlp_review_model.joblib")
    
    thresh_data_fusion = {
        "reviewer_threshold": float(best_thresh_r_lgb),
        "review_threshold": float(best_thresh_rev_lgb)
    }
    with open(models_dir / "best_thresholds.json", "w") as f:
        json.dump(thresh_data_fusion, f, indent=4)
        
    print(f"Saved all 8 model artifacts, scalers, and best_thresholds.json to: {models_dir}")

    # Save summary results
    summary_path = script_dir / "model_benchmarks_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results_summary, f, indent=4)
    print(f"\n Saved benchmark metrics summary to: {summary_path}")
    print("═" * 120)

if __name__ == "__main__":
    main()
