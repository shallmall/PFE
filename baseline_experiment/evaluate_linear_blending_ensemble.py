import os
import sys
import time
import json
import numpy as np
import pandas as pd
import warnings
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, precision_recall_curve, auc
import lightgbm as lgb

# Import feature extraction functions from sibling baseline scripts
from train_text_centric_model import extract_linguistic_features, get_fasttext_embeddings
from train_behavior_centric_model import extract_rolling_reviewer_features

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

warnings.filterwarnings('ignore')

def calculate_metrics(y_true, y_pred_prob, threshold=0.5, pos_label_fake=1):
    if len(np.unique(y_true)) > 1:
        roc_auc = roc_auc_score(y_true, y_pred_prob)
        precision_curve, recall_curve, _ = precision_recall_curve(y_true, y_pred_prob)
        pr_auc = auc(recall_curve, precision_curve)
    else:
        roc_auc = 0.0
        pr_auc = 0.0
        
    y_pred = (y_pred_prob >= threshold).astype(int)
    acc = accuracy_score(y_true, y_pred)
    f1_mac = f1_score(y_true, y_pred, average='macro', zero_division=0)
    
    # Assume pos_label_fake is the label for Fake (1), and 1 - pos_label_fake is Honest (0)
    real_label = 1 - pos_label_fake
    
    p_fake = precision_score(y_true, y_pred, pos_label=pos_label_fake, zero_division=0)
    r_fake = recall_score(y_true, y_pred, pos_label=pos_label_fake, zero_division=0)
    f_fake = f1_score(y_true, y_pred, pos_label=pos_label_fake, zero_division=0)
    
    p_real = precision_score(y_true, y_pred, pos_label=real_label, zero_division=0)
    r_real = recall_score(y_true, y_pred, pos_label=real_label, zero_division=0)
    f_real = f1_score(y_true, y_pred, pos_label=real_label, zero_division=0)
    
    return {
        'acc': acc, 'roc_auc': roc_auc, 'pr_auc': pr_auc, 'f1_macro': f1_mac,
        'prec_fake': p_fake, 'rec_fake': r_fake, 'f1_fake': f_fake,
        'prec_real': p_real, 'rec_real': r_real, 'f1_real': f_real
    }

def print_metrics_box(metrics, title, x_val, y_val):
    print("\n" + "╔" + "═" * 78 + "╗")
    print(f"║ {title:<76} ║")
    print(f"║ Optimal Blending Weights -> x (Text-Centric): {x_val:.2f} | y (Behavior-Centric): {y_val:.2f} ║")
    print("╠" + "═" * 78 + "╣")
    print(f"║ Accuracy: {metrics['acc']:.4f} | ROC-AUC: {metrics['roc_auc']:.4f} | PR-AUC: {metrics['pr_auc']:.4f} | F1-Macro: {metrics['f1_macro']:.4f} ║")
    print(f"║   [Real/0] Precision: {metrics['prec_real']:.4f} | Recall: {metrics['rec_real']:.4f} | F1: {metrics['f1_real']:.4f}         ║")
    print(f"║   [Fake/1] Precision: {metrics['prec_fake']:.4f} | Recall: {metrics['rec_fake']:.4f} | F1: {metrics['f1_fake']:.4f}         ║")
    print("╚" + "═" * 78 + "╝")

def find_best_linear_weights(y_train, prob_rev_train, prob_reviewer_train):
    best_x = 0.5
    best_f1 = 0.0
    best_thresh = 0.5
    
    # Grid search x in [0.00, 1.00] with step 0.01 (y = 1 - x)
    for x in np.arange(0.0, 1.01, 0.01):
        y = 1.0 - x
        blend_prob = x * prob_rev_train + y * prob_reviewer_train
        
        # Find best threshold for this blend
        for thresh in np.arange(0.1, 0.9, 0.05):
            pred = (blend_prob >= thresh).astype(int)
            macro_f1 = f1_score(y_train, pred, average='macro', zero_division=0)
            if macro_f1 > best_f1:
                best_f1 = macro_f1
                best_x = x
                best_thresh = thresh
                
    return best_x, 1.0 - best_x, best_thresh

def print_metrics_box_3var(metrics, title, w1, w2, w3):
    print("\n" + "╔" + "═" * 78 + "╗")
    print(f"║ {title:<76} ║")
    print(f"║ Optimal Weights -> w1(Behavior): {w1:.2f} | w2(Curr Text): {w2:.2f} | w3(Hist Text): {w3:.2f} ║")
    print("╠" + "═" * 78 + "╣")
    print(f"║ Accuracy: {metrics['acc']:.4f} | ROC-AUC: {metrics['roc_auc']:.4f} | PR-AUC: {metrics['pr_auc']:.4f} | F1-Macro: {metrics['f1_macro']:.4f} ║")
    print(f"║   [Real/0] Precision: {metrics['prec_real']:.4f} | Recall: {metrics['rec_real']:.4f} | F1: {metrics['f1_real']:.4f}         ║")
    print(f"║   [Fake/1] Precision: {metrics['prec_fake']:.4f} | Recall: {metrics['rec_fake']:.4f} | F1: {metrics['f1_fake']:.4f}         ║")
    print("╚" + "═" * 78 + "╝")

def find_best_linear_weights_3var(y_train, v1_train, v2_train, v3_train):
    best_w1, best_w2, best_w3 = 0.33, 0.33, 0.34
    best_f1 = 0.0
    best_thresh = 0.5
    
    # Grid search w1, w2 in [0.00, 1.00] with step 0.02 (w3 = 1 - w1 - w2)
    for w1 in np.arange(0.0, 1.01, 0.02):
        for w2 in np.arange(0.0, 1.01 - w1, 0.02):
            w3 = round(1.0 - w1 - w2, 4)
            if w3 < -1e-5 or w3 > 1.0 + 1e-5:
                continue
            w3 = max(0.0, min(1.0, w3))
            
            blend_prob = w1 * v1_train + w2 * v2_train + w3 * v3_train
            
            # Find best threshold for this blend
            for thresh in np.arange(0.1, 0.9, 0.05):
                pred = (blend_prob >= thresh).astype(int)
                macro_f1 = f1_score(y_train, pred, average='macro', zero_division=0)
                if macro_f1 > best_f1:
                    best_f1 = macro_f1
                    best_w1, best_w2, best_w3 = w1, w2, w3
                    best_thresh = thresh
                    
    return best_w1, best_w2, best_w3, best_thresh

def main():
    print("═" * 80)
    print("  Baseline Linear Weighted Blending Ensemble (Text & Behavior Centric)")
    print("═" * 80)
    
    data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "final_enriched_reviews_dataset.csv")
    print(f"Loading raw data from {data_path}...")
    df_raw = pd.read_csv(data_path, low_memory=False)
    
    # ---------------------------------------------------------
    # 1. Reviewer-Centric Feature Extraction & Dataset Setup
    # ---------------------------------------------------------
    print("\n── 1. Extracting Behavior-Centric Rolling Features ────────────────────")
    t0 = time.time()
    df_reviewer = extract_rolling_reviewer_features(df_raw.copy())
    df_reviewer.fillna(0.0, inplace=True)
    print(f"✅ Behavior-centric features extracted in {time.time() - t0:.2f}s | Shape: {df_reviewer.shape}")
    
    # Ensure consistent review_id ordering and filtering
    df_reviewer = df_reviewer.sort_values('review_id').reset_index(drop=True)
    
    # ---------------------------------------------------------
    # 2. Review-Centric Feature Extraction & Dataset Setup
    # ---------------------------------------------------------
    print("\n── 2. Extracting Text-Centric Linguistic & FastText Features ────────")
    t0 = time.time()
    # Filter raw df to match exactly the labeled review_ids present in df_reviewer
    valid_review_ids = set(df_reviewer['review_id'])
    df_rev_raw = df_raw[df_raw['review_id'].isin(valid_review_ids)].sort_values('review_id').reset_index(drop=True)
    
    # Note: In Text-Centric baseline script, tag was 0 for Fake and 1 for Honest. 
    # To keep our ensemble mathematical blending consistent, we standardize BOTH to: 1 = Fake, 0 = Honest!
    ling_df, texts_for_ft = extract_linguistic_features(df_rev_raw)
    ft_df = get_fasttext_embeddings(texts_for_ft)
    X_rev = pd.concat([ling_df.reset_index(drop=True), ft_df.reset_index(drop=True)], axis=1)
    print(f"✅ Text-centric features extracted in {time.time() - t0:.2f}s | Shape: {X_rev.shape}")
    
    # Align features exactly by row index
    X_reviewer = df_reviewer.drop(columns=['review_id', 'reviewer_id', 'tag'])
    y_target = df_reviewer['tag'].values.astype(int) # 1 = Fake, 0 = Honest
    review_ids_list = df_reviewer['review_id'].values
    reviewer_ids_list = df_reviewer['reviewer_id'].values
    
    # ---------------------------------------------------------
    # 3. Universal Stratified 80/20 Train/Test Split (seed=42)
    # ---------------------------------------------------------
    print("\n── 3. Applying 80% Train / 20% Test Stratified Split (seed=42) ────────")
    indices = np.arange(len(y_target))
    idx_train, idx_test, y_train, y_test = train_test_split(
        indices, y_target, test_size=0.2, random_state=42, stratify=y_target
    )
    print(f"✅ Split Sizes -> Train: {len(idx_train):,} reviews | Test: {len(idx_test):,} reviews")
    
    # Scale both feature sets independently
    scaler_rev = StandardScaler()
    X_rev_train = scaler_rev.fit_transform(X_rev.iloc[idx_train])
    X_rev_test = scaler_rev.transform(X_rev.iloc[idx_test])
    
    scaler_reviewer = StandardScaler()
    X_reviewer_train = scaler_reviewer.fit_transform(X_reviewer.iloc[idx_train])
    X_reviewer_test = scaler_reviewer.transform(X_reviewer.iloc[idx_test])
    
    # ---------------------------------------------------------
    # 4. Train Winning Baseline Models (LightGBM)
    # ---------------------------------------------------------
    print("\n── 4. Training Top-Performing Baseline Models (LightGBM) ──────────────")
    scale_pos_weight_val = len(y_train[y_train==0]) / max(1, len(y_train[y_train==1]))
    
    print("🔹 Training Text-Centric LightGBM...")
    model_rev = lgb.LGBMClassifier(scale_pos_weight=scale_pos_weight_val, random_state=42, n_jobs=-1)
    model_rev.fit(X_rev_train, y_train)
    prob_rev_train = model_rev.predict_proba(X_rev_train)[:, 1]
    prob_rev_test = model_rev.predict_proba(X_rev_test)[:, 1]
    
    print("🔹 Training Behavior-Centric LightGBM...")
    model_reviewer = lgb.LGBMClassifier(scale_pos_weight=scale_pos_weight_val, random_state=42, n_jobs=-1)
    model_reviewer.fit(X_reviewer_train, y_train)
    prob_reviewer_train = model_reviewer.predict_proba(X_reviewer_train)[:, 1]
    prob_reviewer_test = model_reviewer.predict_proba(X_reviewer_test)[:, 1]
    
    # ---------------------------------------------------------
    # 5. Review Head Optimization & Evaluation (Transaction Level)
    # ---------------------------------------------------------
    print("\n── 5. Optimizing Linear Blending Weights on Train Data (Review Head) ──")
    x1, y1, best_thresh_1 = find_best_linear_weights(y_train, prob_rev_train, prob_reviewer_train)
    print(f"✅ Optimal Review Head Weights -> x1 (Text-Centric): {x1:.2f} | y1 (Behavior-Centric): {y1:.2f} | Thresh: {best_thresh_1:.2f}")
    
    print("Evaluating Review Head on Unseen Test Data...")
    blend_prob_test_review = x1 * prob_rev_test + y1 * prob_reviewer_test
    metrics_review = calculate_metrics(y_test, blend_prob_test_review, threshold=best_thresh_1, pos_label_fake=1)
    print_metrics_box(metrics_review, "REVIEW HEAD (Transaction-Level Fraud Detection)", x1, y1)
    
    # ---------------------------------------------------------
    # 6. Reviewer Head Optimization & Evaluation (Account Level over Time)
    # ---------------------------------------------------------
    print("\n── 6. Optimizing 3-Variable Blending Weights on Train Data (Reviewer Head over Time) ")
    # Reconstruct full prediction arrays across all rows to calculate point-in-time expanding means
    all_prob_rev = np.zeros(len(y_target))
    all_prob_rev[idx_train] = prob_rev_train
    all_prob_rev[idx_test] = prob_rev_test
    
    all_prob_behavior = np.zeros(len(y_target))
    all_prob_behavior[idx_train] = prob_reviewer_train
    all_prob_behavior[idx_test] = prob_reviewer_test
    
    df_all_scores = pd.DataFrame({
        'reviewer_id': reviewer_ids_list,
        'prob_rev': all_prob_rev,
        'prob_behavior': all_prob_behavior
    })
    
    # Compute expanding rolling mean of text scores per reviewer over time (zero leakage!)
    df_all_scores['hist_mean_text'] = df_all_scores.groupby('reviewer_id')['prob_rev'].transform(lambda x: x.expanding().mean())
    
    v1_train = all_prob_behavior[idx_train]
    v2_train = all_prob_rev[idx_train]
    v3_train = df_all_scores['hist_mean_text'].values[idx_train]
    
    w1, w2, w3, best_thresh_2 = find_best_linear_weights_3var(y_train, v1_train, v2_train, v3_train)
    print(f"✅ Optimal Reviewer Head Weights -> w1 (Behavior): {w1:.2f} | w2 (Curr Text): {w2:.2f} | w3 (Hist Text): {w3:.2f} | Thresh: {best_thresh_2:.2f}")
    
    v1_test = all_prob_behavior[idx_test]
    v2_test = all_prob_rev[idx_test]
    v3_test = df_all_scores['hist_mean_text'].values[idx_test]
    
    blend_prob_test_reviewer = w1 * v1_test + w2 * v2_test + w3 * v3_test
    metrics_reviewer = calculate_metrics(y_test, blend_prob_test_reviewer, threshold=best_thresh_2, pos_label_fake=1)
    print_metrics_box_3var(metrics_reviewer, "REVIEWER HEAD (Account-Level Fraud Detection over Time)", w1, w2, w3)
    
    # ---------------------------------------------------------
    # 7. Save Benchmark Summary
    # ---------------------------------------------------------
    summary_out = {
        'review_head_weights': {'x1_text_centric': float(x1), 'y1_behavior_centric': float(y1), 'threshold': float(best_thresh_1)},
        'review_head_metrics': metrics_review,
        'reviewer_head_weights': {'w1_behavior_centric': float(w1), 'w2_current_text_centric': float(w2), 'w3_hist_mean_text_centric': float(w3), 'threshold': float(best_thresh_2)},
        'reviewer_head_metrics': metrics_reviewer
    }
    
    out_file = os.path.join(os.path.dirname(__file__), "linear_blending_ensemble_metrics.json")
    with open(out_file, "w") as f:
        json.dump(summary_out, f, indent=4)
    print(f"\n✅ All ensemble benchmark metrics saved to: {out_file}")
    print("═" * 80)

if __name__ == "__main__":
    main()
