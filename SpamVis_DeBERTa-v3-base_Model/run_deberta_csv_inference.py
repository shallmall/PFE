"""
Run DeBERTa Inference on CSV Reviews
=================================
This script takes a CSV file, extracts the review text, runs standard DeBERTa cleaning
(preserving grammar and punctuation natively via BPE), tokenizes the text to a max length
of 128 tokens, and passes it through the fine-tuned SpamVis DeBERTa model to generate fraud/spam predictions.
"""

import os
import re
import sys
import argparse
import time
from pathlib import Path
import pandas as pd
import numpy as np
import unicodedata

import torch
from torch.utils.data import DataLoader, Dataset

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
    parser = argparse.ArgumentParser(description="Run DeBERTa Spam Detection Inference on a CSV dataset.")
    
    # Determine default paths relative to this script's directory
    script_dir = Path(__file__).resolve().parent
    default_model_dir = script_dir  # DeBERTa model files are natively in this directory
    default_csv_path = script_dir.parent / "data" / "public_reviews_dataset_cleaned.csv"

    parser.add_argument("--csv_path", type=str, default=str(default_csv_path),
                        help="Path to the input CSV file.")
    parser.add_argument("--model_dir", type=str, default=str(default_model_dir),
                        help="Path to the saved DeBERTa Model directory.")
    parser.add_argument("--text_col", type=str, default=None,
                        help="Column name containing review text. Auto-detected if not specified.")
    parser.add_argument("--batch_size", type=int, default=256,
                        help="Batch size for DeBERTa inference.")
    parser.add_argument("--max_length", type=int, default=128,
                        help="Max token length for DeBERTa tokenization (default: 128).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit processing to the first N rows (useful for fast testing).")
    parser.add_argument("--output_csv", type=str, default=str(script_dir / "deberta_predictions_output.csv"),
                        help="Path to save the output CSV with predictions.")
    parser.add_argument("--threshold", type=float, default=0.23,
                        help="Decision threshold for classifying review as Genuine vs Spam (default: 0.23).")

    args = parser.parse_args()

    # Auto-load threshold from best_threshold.json if present
    thresh_file = script_dir / "best_threshold.json"
    if thresh_file.exists():
        import json
        with open(thresh_file, "r") as f:
            t_data = json.load(f)
        if "best_threshold" in t_data:
            args.threshold = float(t_data["best_threshold"])
            print(f"[OK] Loaded exact validation threshold from {thresh_file}: {args.threshold:.4f}")
        elif "threshold" in t_data:
            args.threshold = float(t_data["threshold"])
            print(f"[OK] Loaded exact validation threshold from {thresh_file}: {args.threshold:.4f}")
        else:
            raise RuntimeError(f"Error: valid threshold key ('best_threshold' or 'threshold') not found in {thresh_file}. Never use default threshold!")
    else:
        raise RuntimeError(f"Error: exact threshold JSON file not found at {thresh_file}. Never use default threshold!")

    print("═" * 70)
    print("SpamVis DeBERTa Pipeline: CSV Cleaning & Model Inference")
    print("═" * 70)

    # 1. Verify paths
    if not os.path.exists(args.csv_path):
        print(f"Error: Input CSV file not found at: {args.csv_path}")
        print("Please specify a valid path using --csv_path <path_to_csv>")
        sys.exit(1)

    if not os.path.exists(args.model_dir):
        print(f"Error: DeBERTa model directory not found at: {args.model_dir}")
        sys.exit(1)

    # Setup device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using Device      : {device.type.upper()}" + (f" ({torch.cuda.get_device_name(0)})" if device.type == "cuda" else ""))
    print(f"Model Directory   : {args.model_dir}")
    print(f"Input CSV         : {args.csv_path}")
    print(f"Max Token Length  : {args.max_length}")

    # 2. Load CSV Data
    print("\n── 1. Loading & Cleaning CSV Data ─────────────────────────────────")
    t0 = time.time()
    df = pd.read_csv(args.csv_path, nrows=args.limit, low_memory=False)
    print(f"Loaded {len(df):,} rows in {time.time() - t0:.2f}s")

    # Auto-detect text column
    text_col = args.text_col
    if not text_col:
        for col in ["review_text", "text", "body", "content", "review"]:
            if col in df.columns:
                text_col = col
                break
    
    if not text_col or text_col not in df.columns:
        print(f"Error: Could not find review text column in CSV. Available columns: {list(df.columns)}")
        print("Please specify the exact column name using --text_col <column_name>")
        sys.exit(1)

    print(f"Using text column : '{text_col}'")

    # Apply Advanced DeBERTa Text Cleaning
    print("Applying advanced DeBERTa cleaning (URL masking, control chars)...")
    cleaned_texts = [clean_deberta_text(t) for t in df[text_col]]
    
    # Show sample before and after
    sample_idx = 0
    while sample_idx < len(cleaned_texts) and len(cleaned_texts[sample_idx]) < 10:
        sample_idx += 1
    if sample_idx < len(cleaned_texts):
        print("\n   [Sample Text]")
        print(f"Original : {str(df[text_col].iloc[sample_idx])[:80]}...")
        print(f"Input    : {cleaned_texts[sample_idx][:80]}...")

    # 3. Load Model & Tokenizer
    print("\n── 2. Loading Fine-Tuned DeBERTa Model & Tokenizer ───────────────────")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(args.model_dir, local_files_only=True)
    model = model.to(device)
    model.eval()
    print(f"Loaded weights in {time.time() - t0:.2f}s")

    # 4. Run Inference
    print("\n── 3. Running DeBERTa Inference ──────────────────────────────────────")
    dataset = ReviewDataset(cleaned_texts)
    dataloader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False)

    all_spam_probs = []
    all_genuine_probs = []

    t0 = time.time()
    with torch.no_grad():
        for batch_idx, batch_texts in enumerate(dataloader):
            # Tokenize batch with max_length=128
            inputs = tokenizer(
                list(batch_texts),
                max_length=args.max_length,
                padding=True,
                truncation=True,
                return_tensors="pt"
            ).to(device)

            # Forward pass
            outputs = model(**inputs)
            probs = torch.softmax(outputs.logits, dim=1)

            # Extract probabilities: label 0 = Spam, label 1 = Genuine
            all_spam_probs.extend(probs[:, 0].cpu().numpy())
            all_genuine_probs.extend(probs[:, 1].cpu().numpy())

            if (batch_idx + 1) % max(1, len(dataloader) // 10) == 0 or (batch_idx + 1) == len(dataloader):
                processed = min((batch_idx + 1) * args.batch_size, len(df))
                print(f"Processed {processed:,} / {len(df):,} reviews ({processed/len(df)*100:.1f}%)")

    elapsed = time.time() - t0
    print(f"Inference completed in {elapsed:.2f}s ({len(df)/elapsed:.1f} reviews/sec)")

    # 5. Append predictions and save
    print("\n── 4. Saving Predictions ──────────────────────────────────────────")
    product_id_col = "asin" if "asin" in df.columns else ("product_id" if "product_id" in df.columns else df.columns[0])
    
    all_spam_probs = np.array(all_spam_probs)
    # Predict binary label 0 (Spam) if P(Spam) >= (1.0 - threshold), else 1 (Genuine)
    binary_labels = np.where(all_spam_probs >= (1.0 - args.threshold), 0, 1)

    output_df = pd.DataFrame({
        "review_id": df["review_id"] if "review_id" in df.columns else df.index,
        "reviewer_id": df["reviewer_id"] if "reviewer_id" in df.columns else df.index,
        "product_id": df[product_id_col],
        "model_score": np.round(all_spam_probs, 4),
        "predicted_label": binary_labels
    })

    output_df.to_csv(args.output_csv, index=False)
    print(f"Saved binary results (0/1) to: {args.output_csv}")

    # Summary Statistics
    spam_count = (binary_labels == 0).sum()
    genuine_count = len(df) - spam_count
    print("\n── Prediction Summary ──")
    print(f"Total Reviews Predicted   : {len(df):,}")
    print(f"Classified as Genuine (1) : {genuine_count:,} ({genuine_count/len(df)*100:.1f}%)")
    print(f"Classified as Spam (0)    : {spam_count:,} ({spam_count/len(df)*100:.1f}%)")
    print("═" * 70)


if __name__ == "__main__":
    main()
