import os
import sys
import time
import math
import numpy as np
import pandas as pd
import warnings
from datetime import timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import Counter
import json

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, f1_score, accuracy_score, precision_score, recall_score
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.linear_model import LogisticRegression
import xgboost as xgb
import lightgbm as lgb

warnings.filterwarnings('ignore')

def compute_entropy(labels):
    counts = Counter(labels)
    total = len(labels)
    ent = 0.0
    for count in counts.values():
        p = count / total
        ent -= p * math.log2(p)
    return ent

def extract_rolling_reviewer_features(df):
    print("Converting timestamps and computing rolling product averages (Zero Leakage)...")
    df['timestamp'] = pd.to_datetime(df['review_date'])
    df = df.sort_values(by='timestamp')
    
    # 1. Zero-Leakage Rolling Product Rating Average
    df['shifted_rating'] = df.groupby('asin')['review_rating'].shift(1)
    df['rolling_prod_avg'] = df.groupby('asin')['shifted_rating'].transform(lambda x: x.expanding().mean())
    df['rolling_prod_avg'].fillna(3.0, inplace=True)
    df['rating_dev'] = abs(df['review_rating'] - df['rolling_prod_avg'])
    
    print("Grouping by reviewer to calculate point-in-time rolling metrics for EVERY review...")
    
    grouped = df.groupby('reviewer_id')
    features = []
    
    total_reviewers = len(grouped)
    count = 0
    
    for reviewer_id, group in grouped:
        count += 1
        if count % 1000 == 0:
            print(f"  Processed {count} / {total_reviewers} reviewers...")
            
        group = group.sort_values(by='timestamp')
        
        timestamps = group['timestamp'].tolist()
        ratings = group['review_rating'].tolist()
        texts = group['review_text'].fillna("").astype(str).tolist()
        rating_devs = group['rating_dev'].tolist()
        products = group['asin'].tolist()
        review_ids = group['review_id'].tolist()
        
        # Get labels
        cls_f = group['reviewer_classified_fake'].tolist()
        lab_f = group['reviewer_labeled_fake'].tolist()
        cls_h = group['reviewer_classified_honest'].tolist()
        lab_h = group['reviewer_labeled_honest'].tolist()
        
        for i in range(len(timestamps)):
            f_c = cls_f[i]
            f_l = lab_f[i]
            h_c = cls_h[i]
            h_l = lab_h[i]
            
            # Safely check for True, handling NaNs
            fake_flag = (pd.notna(f_c) and f_c == True) or (pd.notna(f_l) and f_l == True)
            honest_flag = (pd.notna(h_c) and h_c == True) or (pd.notna(h_l) and h_l == True)
            
            if fake_flag:
                tag = 1.0
            elif honest_flag:
                tag = 0.0
            else:
                continue # Safely yeet the unsupervised data
                
            # Current rolling window (all reviews by this user up to timestamp i)
            current_time = timestamps[i]
            window_times = timestamps[:i+1]
            window_ratings = ratings[:i+1]
            window_texts = texts[:i+1]
            window_devs = rating_devs[:i+1]
            window_prods = products[:i+1]
            
            num_reviews = len(window_times)
            
            # Temporal Features
            if num_reviews > 1:
                time_diffs = [(window_times[j] - window_times[j-1]).total_seconds() / 3600.0 for j in range(1, num_reviews)]
                inter_review_time_mean = np.mean(time_diffs)
                inter_review_time_std = np.std(time_diffs)
            else:
                inter_review_time_mean = 0.0
                inter_review_time_std = 0.0
                
            burst_threshold = current_time - timedelta(hours=24)
            burst_count = sum(1 for t in window_times if t >= burst_threshold)
            burst_ratio = burst_count / num_reviews
            
            last_7d_threshold = current_time - timedelta(days=7)
            reviews_last_7d = sum(1 for t in window_times if t >= last_7d_threshold)
            
            lifespan_days = (current_time - window_times[0]).total_seconds() / (3600 * 24.0)
            lifespan_safe = max(1.0, lifespan_days)
            reviews_per_day = num_reviews / lifespan_safe
            reviewer_age_days = lifespan_days
            
            # Behavioral Features
            extremity_count = sum(1 for r in window_ratings if r == 1.0 or r == 5.0)
            rating_extremity = extremity_count / num_reviews
            
            rating_entropy = compute_entropy(window_ratings)
            rating_deviation_avg = np.mean(window_devs)
            
            word_counts = [len(t.split()) for t in window_texts]
            user_length_var = np.var(word_counts) if num_reviews > 1 else 0.0
            
            unique_products = len(set(window_prods))
            reviews_per_product = num_reviews / max(1, unique_products)
            
            # Intra-Account Text Similarity
            if num_reviews > 1:
                try:
                    vectorizer = TfidfVectorizer(max_features=100)
                    tfidf_matrix = vectorizer.fit_transform(window_texts)
                    sim_matrix = cosine_similarity(tfidf_matrix)
                    mask = np.triu(np.ones(sim_matrix.shape, dtype=bool), k=1)
                    sims = sim_matrix[mask]
                    intra_text_sim = np.mean(sims) if len(sims) > 0 else 0.0
                except:
                    intra_text_sim = 0.0
            else:
                intra_text_sim = 0.0
                
            features.append({
                'review_id': review_ids[i],
                'reviewer_id': reviewer_id,
                'inter_review_time_mean': inter_review_time_mean,
                'inter_review_time_std': inter_review_time_std,
                'burst_ratio': burst_ratio,
                'reviews_last_7d': reviews_last_7d,
                'reviews_per_day': reviews_per_day,
                'reviewer_age_days': reviewer_age_days,
                'rating_extremity': rating_extremity,
                'rating_entropy': rating_entropy,
                'rating_deviation_avg': rating_deviation_avg,
                'user_length_var': user_length_var,
                'reviews_per_product': reviews_per_product,
                'intra_text_sim': intra_text_sim,
                'tag': tag
            })
            
    return pd.DataFrame(features)

def main():
    print("=" * 60)
    print("Behavior-Centric Model (Rolling State Evaluation)")
    print("=" * 60)
    
    data_path = os.path.join("..", "data", "final_enriched_reviews_dataset.csv")
    if not os.path.exists(data_path):
        data_path = os.path.join("data", "final_enriched_reviews_dataset.csv")
        
    print(f"Loading raw data from {data_path}...")
    df_raw = pd.read_csv(data_path, low_memory=False)
    
    df = extract_rolling_reviewer_features(df_raw)
    
    print("\nExtracted Rolling Feature Matrix Shape:", df.shape)
    print("\nClass Distribution (1 = Fake, 0 = Honest):")
    print(df['tag'].value_counts())
    
    # Fill any potential NaNs (e.g. from missing ratings or empty variance)
    df.fillna(0.0, inplace=True)
    
    X = df.drop(columns=['review_id', 'reviewer_id', 'tag'])
    y = df['tag'].values.astype(int)
    
    # Train Test Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    scale_pos_weight_val = len(y[y==0]) / max(1, len(y[y==1]))
    
    print("\nTraining Models...")
    models = {
        "Logistic Regression": LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42),
        "Naive Bayes": GaussianNB(),
        "Random Forest": RandomForestClassifier(n_estimators=100, max_depth=10, class_weight='balanced', random_state=42, n_jobs=-1),
        "MLP Neural Net": MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=300, random_state=42),
        "XGBoost": xgb.XGBClassifier(scale_pos_weight=scale_pos_weight_val, eval_metric='logloss', random_state=42, n_jobs=-1),
        "LightGBM": lgb.LGBMClassifier(scale_pos_weight=scale_pos_weight_val, random_state=42, n_jobs=-1)
    }
    
    results = []
    for name, model in models.items():
        print(f"  -> Training {name}...")
        t0 = time.time()
        model.fit(X_train_scaled, y_train)
        
        y_pred = model.predict(X_test_scaled)
        if hasattr(model, "predict_proba"):
            y_prob = model.predict_proba(X_test_scaled)[:, 1]
            auc_val = roc_auc_score(y_test, y_prob)
        else:
            auc_val = 0.0
            
        acc = accuracy_score(y_test, y_pred)
        f1_mac = f1_score(y_test, y_pred, average='macro')
        prec_mac = precision_score(y_test, y_pred, average='macro')
        rec_mac = recall_score(y_test, y_pred, average='macro')
        
        # 1 = Fake, 0 = Honest
        p_fake = precision_score(y_test, y_pred, pos_label=1)
        r_fake = recall_score(y_test, y_pred, pos_label=1)
        f_fake = f1_score(y_test, y_pred, pos_label=1)
        
        p_real = precision_score(y_test, y_pred, pos_label=0)
        r_real = recall_score(y_test, y_pred, pos_label=0)
        f_real = f1_score(y_test, y_pred, pos_label=0)
        
        time_taken = time.time() - t0
        print(f"     [Done in {time_taken:.1f}s] AUC: {auc_val:.4f} | Acc: {acc:.4f} | F1-Macro: {f1_mac:.4f}")
        
        results.append({
            'Model': name,
            'Accuracy': acc,
            'ROC-AUC': auc_val,
            'Precision-Macro': prec_mac,
            'Recall-Macro': rec_mac,
            'F1-Macro': f1_mac,
            'Fake_1': {'Precision': p_fake, 'Recall': r_fake, 'F1': f_fake},
            'Honest_0': {'Precision': p_real, 'Recall': r_real, 'F1': f_real}
        })
        
    print("\n" + "=" * 60)
    print("FINAL BENCHMARK RESULTS")
    print("=" * 60)
    
    out_json = os.path.join(os.path.dirname(__file__), "behavior_centric_classification_metrics.json")
    with open(out_json, "w") as f:
        json.dump(results, f, indent=4)
    print(f"Full metrics strictly saved to {out_json}")

if __name__ == "__main__":
    main()
