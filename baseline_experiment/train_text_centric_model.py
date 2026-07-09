import os
import sys
import pandas as pd
import numpy as np
import time
import string
import warnings

# Suppress warnings
warnings.filterwarnings('ignore')

# NLP Libraries
import nltk
from nltk.tokenize import word_tokenize
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import textstat
import gensim.downloader as api

# ML Libraries
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, roc_auc_score, f1_score, accuracy_score, precision_score, recall_score
from sklearn.neural_network import MLPClassifier
import json
from sklearn.ensemble import RandomForestClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.linear_model import LogisticRegression
import xgboost as xgb
import lightgbm as lgb

# Download required NLTK data (quietly)
nltk.download('punkt', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)

def extract_linguistic_features(df):
    print("Extracting linguistic features (this may take a few minutes)...")
    analyzer = SentimentIntensityAnalyzer()
    
    features = []
    texts_for_ft = []
    
    for i, row in df.iterrows():
        text = str(row['review_text'])
        if text.strip() == "" or text.lower() == "nan":
            text = "empty review"
            
        # 1. Text Length
        text_len = len(text)
        
        # 2. Capitalization Ratio
        cap_count = sum(1 for c in text if c.isupper())
        cap_ratio = cap_count / max(1, text_len)
        
        # 3. Readability Score
        try:
            readability = textstat.flesch_kincaid_grade(text)
        except:
            readability = 0.0
            
        # 4. VADER Sentiment
        vs = analyzer.polarity_scores(text)
        
        # 6. Adjective Ratio
        tokens = word_tokenize(text)
        texts_for_ft.append([t.lower() for t in tokens])
        
        pos_tags = nltk.pos_tag(tokens)
        adj_count = sum(1 for word, pos in pos_tags if pos.startswith('JJ'))
        adj_ratio = adj_count / max(1, len(tokens))
        
        features.append({
            'text_len': text_len,
            'cap_ratio': cap_ratio,
            'readability': readability,
            'vader_pos': vs['pos'],
            'vader_neg': vs['neg'],
            'vader_neu': vs['neu'],
            'vader_comp': vs['compound'],
            'adj_ratio': adj_ratio
        })
        
        if (i+1) % 10000 == 0:
            print(f"  Processed {i+1} / {len(df)} reviews...")
            
    return pd.DataFrame(features), texts_for_ft

def get_fasttext_embeddings(texts):
    print("Downloading/Loading pre-trained FastText model (~950MB, cached locally)...")
    ft_model = api.load('fasttext-wiki-news-subwords-300')
    vector_size = 300
    
    print("Extracting document vectors...")
    doc_vectors = []
    for text in texts:
        if len(text) == 0:
            doc_vectors.append(np.zeros(vector_size))
            continue
        
        vecs = [ft_model[word] for word in text if word in ft_model]
        if len(vecs) > 0:
            doc_vectors.append(np.mean(vecs, axis=0))
        else:
            doc_vectors.append(np.zeros(vector_size))
            
    # Create DataFrame with named columns
    col_names = [f"ft_dim_{i}" for i in range(vector_size)]
    return pd.DataFrame(doc_vectors, columns=col_names)

def main():
    print("=" * 60)
    print("Text-Centric Model (Linguistic + FastText)")
    print("=" * 60)
    
    data_path = os.path.join("..", "data", "final_enriched_reviews_dataset.csv")
    if not os.path.exists(data_path):
        # Try finding it in root
        data_path = os.path.join("data", "final_enriched_reviews_dataset.csv")
        
    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path, low_memory=False)
    
    # Label creation logic
    df['tag'] = np.nan
    fake_condition = (df['reviewer_classified_fake'] == True) | (df['reviewer_labeled_fake'] == True)
    df.loc[fake_condition, 'tag'] = 0.0
    honest_condition = (df['reviewer_classified_honest'] == True) | (df['reviewer_labeled_honest'] == True)
    df.loc[honest_condition, 'tag'] = 1.0
    
    df_filtered = df.dropna(subset=['tag']).copy()
    df_filtered['tag'] = df_filtered['tag'].astype(int)
    
    print("\nClass Distribution:")
    print(df_filtered['tag'].value_counts())
    
    # Feature Extraction
    ling_df, texts_for_ft = extract_linguistic_features(df_filtered)
    ft_df = get_fasttext_embeddings(texts_for_ft)
    
    # Combine features
    X = pd.concat([ling_df.reset_index(drop=True), ft_df.reset_index(drop=True)], axis=1)
    y = df_filtered['tag'].values
    
    print(f"\nFinal Feature Matrix Shape: {X.shape}")
    
    # Train Test Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Scaling
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Class weights
    # Note: 0 is Fake (majority in this subset: 57k), 1 is Honest (minority: 22k)
    scale_pos_weight_val = len(y[y==0]) / len(y[y==1])  # Weight for class 1
    
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
        
        # Fake is 0, Honest is 1
        p_fake = precision_score(y_test, y_pred, pos_label=0)
        r_fake = recall_score(y_test, y_pred, pos_label=0)
        f_fake = f1_score(y_test, y_pred, pos_label=0)
        
        p_real = precision_score(y_test, y_pred, pos_label=1)
        r_real = recall_score(y_test, y_pred, pos_label=1)
        f_real = f1_score(y_test, y_pred, pos_label=1)
        
        time_taken = time.time() - t0
        print(f"     [Done in {time_taken:.1f}s] AUC: {auc_val:.4f} | Acc: {acc:.4f} | F1-Macro: {f1_mac:.4f}")
        
        results.append({
            'Model': name,
            'Accuracy': acc,
            'ROC-AUC': auc_val,
            'Precision-Macro': prec_mac,
            'Recall-Macro': rec_mac,
            'F1-Macro': f1_mac,
            'Fake_0': {'Precision': p_fake, 'Recall': r_fake, 'F1': f_fake},
            'Honest_1': {'Precision': p_real, 'Recall': r_real, 'F1': f_real}
        })
        
    print("\n" + "=" * 60)
    print("FINAL BENCHMARK RESULTS")
    print("=" * 60)
    
    # Save to JSON right inside the script's directory (`baseline_experiment/`)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_json = os.path.join(script_dir, "text_centric_classification_metrics.json")
    with open(out_json, "w") as f:
        json.dump(results, f, indent=4)
    print(f"Full metrics strictly saved to {out_json}")

if __name__ == "__main__":
    main()
