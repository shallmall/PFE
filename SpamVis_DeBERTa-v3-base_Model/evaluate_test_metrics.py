"""
Evaluate DeBERTa Model on Filtered Test Dataset
============================================
1. Loads data/public_reviews_dataset_cleaned.csv
2. Filters rows based on specific conditions:
   - Condition Fake (0): fake_review_product == True & reviewer_classified_fake == True & review_rating in [1, 5]
   - Condition Real (1): reviewer_classified_fake == False & fake_review_product == False
   - Rows not matching either condition are discarded.
3. Splits data into 80% Train, 10% Validation, 10% Test (seed=42).
4. Runs DeBERTa cleaning and tokenization (limit 128) on the Test split.
5. Runs inference using the SpamVis DeBERTa model and outputs comprehensive classification metrics.
"""

import os
import re
import sys
import time
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import unicodedata

import torch
from torch.utils.data import DataLoader, Dataset
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, classification_report, confusion_matrix
)

# Configure stdout for UTF-8 encoding on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Fix compatibility between PyTorch and recent Transformers versions regarding FP8 types
if not hasattr(torch, 'float8_e8m0fnu'):
    torch.float8_e8m0fnu = None

from transformers import AutoTokenizer, AutoModelForSequenceClassification

# Disable online checks to load local weights fast
os.environ["HF_HUB_OFFLINE"] = "1"


def clean_deberta_text(text) -> str:
    """Robust text cleaning for RoBERTa and DeBERTa (URL/Email Masking, whitespace fix, control chars)."""
    if pd.isna(text) or text is None:
        return ""
    text = str(text)
    
    # 1. URL & Email Masking
    text = re.sub(r'\S*@\S*\.com|\S*@\S*\.net|\S*@\S*\.org|\S*@\S*\.edu|\S*@\S*\.gov', '<EMAIL>', text)
    text = re.sub(r'https?:\/\/\S+|www\.\S+', '<URL>', text)
    text = re.sub(r'\b[a-zA-Z0-9.-]+\.(?:com|org|net|edu|gov|io|co|us|uk|ca|au|de|jp|fr|cn|in|ru)\b(?:\/\S*)?', '<URL>', text)

    # 2. Whitespace Normalization (MUST DO FIRST so \n and \t turn into spaces)
    text = re.sub(r'\s+', ' ', text)

    # 3. Control Character Removal
    text = ''.join(ch for ch in text if unicodedata.category(ch)[0] != 'C')
    
    return text.strip()


class ReviewDataset(Dataset):
    def __init__(self, texts):
        self.texts = texts

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        return self.texts[idx]


def main():
    parser = argparse.ArgumentParser(description="Evaluate DeBERTa Model on Filtered Test Set.")
    
    script_dir = Path(__file__).resolve().parent
    default_model_dir = script_dir  # Model files are directly in the DeBERTa folder
    default_csv_path = script_dir.parent / "data" / "public_reviews_dataset_cleaned.csv"
    
    # Load best threshold from JSON if it exists
    best_threshold = 0.5
    threshold_file = script_dir / "best_threshold.json"
    if threshold_file.exists():
        import json
        with open(threshold_file, "r") as f:
            data = json.load(f)
            best_threshold = data.get("best_threshold", 0.5)

    parser.add_argument("--csv_path", type=str, default=str(default_csv_path),
                        help="Path to the input CSV file.")
    parser.add_argument("--model_dir", type=str, default=str(default_model_dir),
                        help="Path to the saved DeBERTa Model directory.")
    parser.add_argument("--batch_size", type=int, default=64,
                        help="Batch size for DeBERTa inference.")
    parser.add_argument("--max_length", type=int, default=128,
                        help="Max token length for DeBERTa tokenization (default: 128).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Optional limit on number of test rows to evaluate (for fast debugging).")
    parser.add_argument("--threshold", type=float, default=best_threshold,
                        help=f"Decision threshold for classifying review as Genuine vs Spam (default from JSON: {best_threshold:.4f}).")

    args = parser.parse_args()

    print("=" * 70)
    print("  SpamVis DeBERTa Evaluation: Filtered Test Set Metrics")
    print("=" * 70)

    # Setup device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using Device      : {device.type.upper()}" + (f" ({torch.cuda.get_device_name(0)})" if device.type == "cuda" else ""))
    print(f"Model Directory   : {args.model_dir}")
    print(f"Input CSV         : {args.csv_path}")

    # 1. Load CSV
    print("\n[Step 1] Loading dataset...")
    t0 = time.time()
    df = pd.read_csv(args.csv_path, low_memory=False)
    print(f"Loaded {len(df):,} total rows in {time.time() - t0:.2f}s")

    # 2. Define conditions and filter using requested hierarchical tagging approach
    print("\n[Step 2] Applying Fake and Real criteria...")
    honest_cols = ['reviewer_labeled_honest', 'reviewer_classified_honest']
    fake_cols = ['reviewer_labeled_fake', 'reviewer_classified_fake']

    df['tag'] = np.nan
    cond_tag_1 = (df[honest_cols[0]] == 1) | (df[honest_cols[0]] == True) | (df[honest_cols[1]] == 1) | (df[honest_cols[1]] == True)
    df.loc[cond_tag_1, 'tag'] = 1

    cond_tag_0 = ((df[fake_cols[0]] == 1) | (df[fake_cols[0]] == True) | (df[fake_cols[1]] == 1) | (df[fake_cols[1]] == True)) & df['tag'].isna()
    df.loc[cond_tag_0, 'tag'] = 0

    # Filter rows matching either category 1 or 0
    df_filtered = df[df['tag'].notna()].copy()
    df_filtered['target_label'] = df_filtered['tag'].astype(int)

    fake_count = (df_filtered['target_label'] == 0).sum()
    real_count = (df_filtered['target_label'] == 1).sum()
    discarded_count = len(df) - len(df_filtered)

    print(f"Kept Rows         : {len(df_filtered):,} ({len(df_filtered)/len(df)*100:.1f}%)")
    print(f"  -> Fake (Label 0): {fake_count:,} ({fake_count/len(df_filtered)*100:.1f}%)")
    print(f"  -> Real (Label 1): {real_count:,} ({real_count/len(df_filtered)*100:.1f}%)")
    print(f"Discarded Rows    : {discarded_count:,} ({discarded_count/len(df)*100:.1f}%)")

    # 3. Stratified Split (Matching Colab exactly: 90/10 then 1/9 of the 90%)
    print(f"\n[Step 3] Splitting data (Matching Colab: 80% Train, 10% Val, 10% Test | seed=42)...")
    train_val_df, test_df = train_test_split(
        df_filtered, test_size=0.10, random_state=42, stratify=df_filtered['target_label']
    )
    train_df, val_df = train_test_split(
        train_val_df, test_size=1/9, random_state=42, stratify=train_val_df['target_label']
    )

    print(f"Train Split (80%) : {len(train_df):,} rows")
    print(f"Val Split   (10%) : {len(val_df):,} rows")
    print(f"Test Split  (10%) : {len(test_df):,} rows")

    if args.limit:
        print(f"\n[Note] Limiting Test evaluation to first {args.limit:,} rows as requested.")
        test_df = test_df.iloc[:args.limit].copy()

    # 4. Extract and Clean Test Set Texts
    print("\n[Step 4] Extracting and cleaning test review texts...")
    text_col = "review_text" if "review_text" in test_df.columns else "text"
    
    cleaned_texts = [clean_deberta_text(t) for t in test_df[text_col]]
    true_labels = test_df['target_label'].values

    # 5. Load Model
    print("\n[Step 5] Loading DeBERTa Model & Tokenizer...")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(args.model_dir, local_files_only=True)
    model = model.to(device)
    model.eval()
    print(f"Loaded weights in {time.time() - t0:.2f}s")

    # 6. Run Inference
    print(f"\n[Step 6] Running Inference on {len(test_df):,} test reviews...")
    dataset = ReviewDataset(cleaned_texts)
    dataloader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False)

    all_spam_probs = []
    all_genuine_probs = []

    t0 = time.time()
    with torch.no_grad():
        for batch_idx, batch_texts in enumerate(dataloader):
            inputs = tokenizer(
                list(batch_texts),
                max_length=args.max_length,
                padding=True,
                truncation=True,
                return_tensors="pt"
            ).to(device)

            outputs = model(**inputs)
            probs = torch.softmax(outputs.logits, dim=1)

            all_spam_probs.extend(probs[:, 0].cpu().numpy())
            all_genuine_probs.extend(probs[:, 1].cpu().numpy())

            if (batch_idx + 1) % max(1, len(dataloader) // 10) == 0 or (batch_idx + 1) == len(dataloader):
                processed = min((batch_idx + 1) * args.batch_size, len(test_df))
                print(f"  Processed {processed:,} / {len(test_df):,} ({processed/len(test_df)*100:.1f}%)")

    elapsed = time.time() - t0
    print(f"Inference finished in {elapsed:.2f}s ({len(test_df)/elapsed:.1f} reviews/sec)")

    # 7. Compute Metrics
    print("\n" + "=" * 70)
    print(f"  FINAL TEST SET PERFORMANCE (Threshold = {args.threshold:.2f})")
    print("=" * 70)

    all_spam_probs = np.array(all_spam_probs)
    # Predict Spam (0) if P(Spam) >= (1 - threshold), else Genuine (1)
    pred_labels = np.where(all_spam_probs >= (1.0 - args.threshold), 0, 1)

    acc = accuracy_score(true_labels, pred_labels)
    try:
        auc = roc_auc_score(true_labels, 1.0 - all_spam_probs) # probability of class 1
    except Exception:
        auc = 0.0

    prec_spam = precision_score(true_labels, pred_labels, pos_label=0, zero_division=0)
    prec_real = precision_score(true_labels, pred_labels, pos_label=1, zero_division=0)
    rec_spam  = recall_score(true_labels, pred_labels, pos_label=0, zero_division=0)
    rec_real  = recall_score(true_labels, pred_labels, pos_label=1, zero_division=0)
    f1_spam   = f1_score(true_labels, pred_labels, pos_label=0, zero_division=0)
    f1_real   = f1_score(true_labels, pred_labels, pos_label=1, zero_division=0)

    f1_macro  = f1_score(true_labels, pred_labels, average='macro', zero_division=0)
    prec_macro = precision_score(true_labels, pred_labels, average='macro', zero_division=0)
    rec_macro  = recall_score(true_labels, pred_labels, average='macro', zero_division=0)

    print(f"  Accuracy   : {acc*100:.2f}%")
    print(f"  AUC-ROC    : {auc*100:.2f}%")
    print("-" * 70)
    print(f"  {'Metric':<15} | {'Spam/Fake (0)':<20} | {'Genuine/Real (1)':<20}")
    print("-" * 70)
    print(f"  {'Precision':<15} | {prec_spam*100:>10.2f}%          | {prec_real*100:>12.2f}%")
    print(f"  {'Recall':<15} | {rec_spam*100:>10.2f}%          | {rec_real*100:>12.2f}%")
    print(f"  {'F1 Score':<15} | {f1_spam*100:>10.2f}%          | {f1_real*100:>12.2f}%")
    print("-" * 70)
    print(f"  F1 Macro Avg   : {f1_macro*100:.2f}%")
    print(f"  Prec Macro Avg : {prec_macro*100:.2f}%")
    print(f"  Rec Macro Avg  : {rec_macro*100:.2f}%")
    print("=" * 70)

    print("\nConfusion Matrix:")
    cm = confusion_matrix(true_labels, pred_labels)
    print(f"                Pred Spam (0)   Pred Genuine (1)")
    print(f"Actual Spam (0)    {cm[0, 0]:<14,}  {cm[0, 1]:<14,}")
    print(f"Actual Real (1)    {cm[1, 0]:<14,}  {cm[1, 1]:<14,}")
    print("=" * 70)


if __name__ == "__main__":
    main()
