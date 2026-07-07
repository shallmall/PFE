"""
Real-Time AI Fraud Detection Engine
===================================
Encapsulates memory loading and real-time inference for:
1. Fine-tuned BERT Spam Text Classifier
2. PyG Temporal Heterogeneous Graph (HGAT)
3. Late Fusion Meta-Models (XGBoost Reviewer Head + MLP Product Head)
4. Blockchain 8-bit score mapping (0-255)
"""

import os
import sys
import torch
import joblib
import numpy as np
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import re
from transformers import AutoTokenizer, AutoModelForSequenceClassification

def clean_bert_text(text: str) -> str:
    """Standard BERT cleaning: strips HTML tags and normalizes whitespace while preserving contextual grammar."""
    if not text:
        return ""
    text = str(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

class AIEngine:
    def __init__(self, models_dir=None):
        if models_dir is None:
            self.models_dir = Path(__file__).resolve().parent / "models"
        else:
            self.models_dir = Path(models_dir)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        self.bert_tokenizer = None
        self.bert_model = None
        self.graph = None
        
        self.lgb_reviewer = None
        self.lgb_product = None
        self.scaler = None
        
        # In-memory score mappings from baseline graph inference
        self.reviewer_gnn_map = {}
        self.product_gnn_map = {}
        self.is_loaded = False

    def load_models(self):
        """Loads all AI artifacts into server RAM upon startup."""
        print(f"⏳ Loading AI models from {self.models_dir.resolve()} onto {self.device}...")
        
        # 1. Load BERT
        bert_path = self.models_dir / "SpamVis_BERT_Model"
        if bert_path.exists():
            self.bert_tokenizer = AutoTokenizer.from_pretrained(bert_path)
            self.bert_model = AutoModelForSequenceClassification.from_pretrained(bert_path).to(self.device)
            self.bert_model.eval()
            print("✅ Loaded BERT Spam Classifier")
        else:
            print(f"⚠️ Warning: BERT model path not found at {bert_path}")

        # 2. Load PyG HeteroGraph & Node Structural Anomaly Maps
        graph_path = self.models_dir / "hetero_graph" / "hetero_graph.pt"
        if graph_path.exists():
            self.graph = torch.load(graph_path, map_location=self.device)
            print(f"✅ Loaded HeteroGraph ({self.graph['review'].num_nodes:,} reviews)")
        else:
            print(f"⚠️ Warning: Graph path not found at {graph_path}")

        try:
            import pandas as pd
            rev_preds_path = Path("/app/data/final_reviewer_fraud_predictions.csv")
            if not rev_preds_path.exists():
                rev_preds_path = Path("../data/final_reviewer_fraud_predictions.csv")
            if rev_preds_path.exists():
                df_rev = pd.read_csv(rev_preds_path)
                self.reviewer_gnn_map = dict(zip(df_rev["reviewer_id"], df_rev["predicted_fraud_probability"]))
                print(f"✅ Loaded GNN Reviewer Structural Risk Map ({len(self.reviewer_gnn_map):,} nodes)")

            prod_preds_path = Path("/app/data/final_product_fraud_predictions.csv")
            if not prod_preds_path.exists():
                prod_preds_path = Path("../data/final_product_fraud_predictions.csv")
            if prod_preds_path.exists():
                df_prod = pd.read_csv(prod_preds_path)
                self.product_gnn_map = dict(zip(df_prod["asin"], df_prod["predicted_fraud_probability"]))
                print(f"✅ Loaded GNN Product Structural Risk Map ({len(self.product_gnn_map):,} nodes)")
        except Exception as e:
            print(f"⚠️ Note: Could not load GNN prediction maps: {e}")

        # 3. Load Late Fusion Models (LightGBM / XGBoost)
        fusion_dir = self.models_dir / "late_fusion"
        rev_path = fusion_dir / "lightgbm_reviewer_model.joblib"
        if not rev_path.exists():
            rev_path = fusion_dir / "xgboost_reviewer_model.joblib"

        prod_path = fusion_dir / "lightgbm_product_model.joblib"
        if not prod_path.exists():
            prod_path = fusion_dir / "xgboost_product_model.joblib"

        scaler_path = fusion_dir / "standard_scaler.joblib"
        
        if rev_path.exists() and prod_path.exists():
            try:
                self.lgb_reviewer = joblib.load(rev_path)
                self.lgb_product = joblib.load(prod_path)
                if scaler_path.exists():
                    self.scaler = joblib.load(scaler_path)
                print(f"✅ Loaded Late Fusion Meta-Models ({rev_path.name} + {prod_path.name})")
            except Exception as e:
                print(f"⚠️ Note: Could not unpickle joblib models ({e}). Operating with direct BERT + GNN Late Fusion engine.")
        else:
            print("⚠️ Warning: Meta-models missing in models/late_fusion/")
            
        self.is_loaded = True
        print("🚀 AI Engine fully initialized and ready for inference!")

    def predict_bert_spam_prob(self, text: str) -> float:
        """Runs fast NLP inference on review text after standard BERT cleaning and 128-token truncation."""
        if not self.bert_model or not self.bert_tokenizer:
            return 0.85 # Fallback genuine baseline
            
        cleaned_text = clean_bert_text(text)
        inputs = self.bert_tokenizer(cleaned_text, return_tensors="pt", truncation=True, max_length=128, padding=True).to(self.device)
        with torch.no_grad():
            outputs = self.bert_model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)
            # Index 1 is Spam/Fraud probability in our BERT model
            spam_prob = probs[0, 1].item()
        return spam_prob

    def get_gnn_scores(self, reviewer_id: str, product_id: str):
        """Retrieves or estimates GNN structural risk scores."""
        # In production, look up known node embeddings or return baseline dataset means
        rev_score = self.reviewer_gnn_map.get(reviewer_id, 0.28)
        prod_score = self.product_gnn_map.get(product_id, 0.32)
        return rev_score, prod_score

    def compute_ai_score(self, reviewer_id: str, product_id: str, review_text: str, db_session) -> int:
        """
        Computes AI Fraud Score (0-100) for Alastria smart contract.
        0 = Pure Fraud, 100 = Pure Genuine.
        """
        if not self.is_loaded:
            self.load_models()

        # 1. Get BERT probability
        bert_prob = self.predict_bert_spam_prob(review_text)

        # 2. Get GNN structural anomaly scores
        gnn_rev_score, gnn_prod_score = self.get_gnn_scores(reviewer_id, product_id)

        # 3. Query Point-in-Time historical stats from Database Ledger
        from database import Review
        past_user_reviews = db_session.query(Review).filter(Review.reviewer_id == reviewer_id).all()
        past_prod_reviews = db_session.query(Review).filter(Review.reviewee_id == product_id).all()

        if len(past_user_reviews) > 0:
            user_hist_fake_ratio = sum(1 for r in past_user_reviews if r.ai_score < 50) / len(past_user_reviews)
            user_avg_bert = sum((r.ai_score / 100.0) for r in past_user_reviews) / len(past_user_reviews)
        else:
            user_hist_fake_ratio = 0.0
            user_avg_bert = bert_prob

        if len(past_prod_reviews) > 0:
            prod_hist_fake_ratio = sum(1 for r in past_prod_reviews if r.ai_score < 50) / len(past_prod_reviews)
        else:
            prod_hist_fake_ratio = 0.0

        # 4. Assemble 6 features for Late Fusion models
        features = np.array([[
            bert_prob,
            gnn_rev_score,
            gnn_prod_score,
            user_hist_fake_ratio,
            user_avg_bert,
            prod_hist_fake_ratio
        ]])

        # 5. Run Late Fusion Meta-Models
        if self.lgb_reviewer and self.lgb_product:
            eval_features = self.scaler.transform(features) if self.scaler else features
            prob_rev_fake = float(self.lgb_reviewer.predict_proba(eval_features)[0, 1])
            prob_prod_fake = float(self.lgb_product.predict_proba(eval_features)[0, 1])
            
            # Combine risk: take highest detected risk across text spam, reviewer head, and product head
            overall_fraud_prob = max(prob_rev_fake, prob_prod_fake, bert_prob)
        else:
            # Direct Late Fusion heuristic combining BERT spam probability and GNN structural risk
            overall_fraud_prob = max(bert_prob, gnn_rev_score, gnn_prod_score)

        # 6. Map to integer (0 to 100)
        genuine_prob = 1.0 - overall_fraud_prob
        ai_score = int(np.clip(round(genuine_prob * 100), 0, 100))
        return ai_score

ai_engine = AIEngine()
