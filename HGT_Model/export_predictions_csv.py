import pandas as pd
import numpy as np
import torch
import json
import os
from model import HGTModel
from torch_geometric.loader import NeighborLoader

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Exporting CSV Predictions using device: {device}")
    
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/public_reviews_dataset_cleaned.csv")
    print(f"Loading raw dataset from {csv_path}...")
    df = pd.read_csv(csv_path, low_memory=False)
    
    # Clean rows exactly as build_graph.py did to maintain consistent mapping
    df = df.dropna(subset=['review_date', 'reviewer_id', 'asin', 'review_id'])
    df['review_date'] = pd.to_datetime(df['review_date'], errors='coerce')
    df = df.dropna(subset=['review_date'])
    df = df.sort_values('review_date').reset_index(drop=True)
    
    asin_ids = df['asin'].unique()
    reviewer_ids = df['reviewer_id'].unique()
    review_ids = df['review_id'].unique()
    
    # Load Pre-built Graph & Trained Model
    data = torch.load(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/hetero_graph.pt"))
    model = HGTModel(
        hidden_channels=64,
        out_channels=1,
        num_layers=2,
        num_heads=4,
        dropout=0.3,
        metadata=data.metadata()
    ).to(device)
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model/best_model.pth")
    if not os.path.exists(model_path):
        model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/best_model.pth")
    model.load_state_dict(torch.load(model_path))
    model.eval()
    
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/best_thresholds.json"), 'r') as f:
        thresh = json.load(f)
    thresh_r = thresh['reviewer_threshold']
    thresh_rev = thresh.get('review_threshold', 0.5)
    
    print("Computing GNN inference across all graph nodes using strict time-aware sampling...")
    loader_r = NeighborLoader(data, num_neighbors=[10, 10], input_nodes='reviewer', time_attr='max_time', batch_size=2048, shuffle=False, num_workers=2)
    loader_rev = NeighborLoader(data, num_neighbors=[10, 10], input_nodes='review', time_attr='time', batch_size=2048, shuffle=False, num_workers=2)

    prob_reviewer, y_reviewer = [], []
    with torch.no_grad():
        for batch in loader_r:
            batch = batch.to(device)
            out_dict = model(batch.x_dict, batch.edge_index_dict)
            out_r = out_dict['reviewer'][:batch['reviewer'].batch_size].squeeze(-1)
            prob_reviewer.extend(torch.sigmoid(out_r).cpu().numpy())
            y_reviewer.extend(batch['reviewer'].y[:batch['reviewer'].batch_size].cpu().numpy())
            
    prob_review, y_review = [], []
    with torch.no_grad():
        for batch in loader_rev:
            batch = batch.to(device)
            out_dict = model(batch.x_dict, batch.edge_index_dict)
            out_rev = out_dict['review'][:batch['review'].batch_size].squeeze(-1)
            prob_review.extend(torch.sigmoid(out_rev).cpu().numpy())
            y_review.extend(batch['review'].y[:batch['review'].batch_size].cpu().numpy())
            
    prob_reviewer = np.array(prob_reviewer)
    prob_review = np.array(prob_review)
    y_reviewer = np.array(y_reviewer)
    y_review = np.array(y_review)
        
    pred_reviewer = (prob_reviewer >= thresh_r).astype(int)
    pred_review = (prob_review >= thresh_rev).astype(int)
    
    # 1. Reviewer Node-Level CSV
    print("Generating Reviewer Predictions CSV...")
    rev_df = pd.DataFrame({
        'reviewer_id': reviewer_ids[:len(prob_reviewer)],
        'ground_truth_label': y_reviewer,
        'predicted_fraud_probability': np.round(prob_reviewer, 6),
        'predicted_fraud_label': pred_reviewer
    })
    rev_csv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/final_reviewer_fraud_predictions.csv")
    rev_df.to_csv(rev_csv, index=False)
    print(f"Saved {len(rev_df)} reviewer predictions to {rev_csv}")
    
    # 3. Review Node-Level CSV
    print("Generating Review Predictions CSV...")
    review_df = pd.DataFrame({
        'review_id': review_ids[:len(prob_review)],
        'ground_truth_label': y_review,
        'predicted_fraud_probability': np.round(prob_review, 6),
        'predicted_fraud_label': pred_review
    })
    review_csv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/final_review_fraud_predictions.csv")
    review_df.to_csv(review_csv, index=False)
    print(f"Saved {len(review_df)} review predictions to {review_csv}")
    
    # 4. Master Enriched Transactions CSV
    print("Enriching Master Reviews Dataset...")
    rev_prob_map = dict(zip(rev_df['reviewer_id'], rev_df['predicted_fraud_probability']))
    rev_label_map = dict(zip(rev_df['reviewer_id'], rev_df['predicted_fraud_label']))
    
    review_prob_map = dict(zip(review_df['review_id'], review_df['predicted_fraud_probability']))
    review_label_map = dict(zip(review_df['review_id'], review_df['predicted_fraud_label']))
    
    df['gnn_reviewer_fraud_probability'] = df['reviewer_id'].map(rev_prob_map)
    df['gnn_reviewer_fraud_label'] = df['reviewer_id'].map(rev_label_map)
    
    df['gnn_review_fraud_probability'] = df['review_id'].map(review_prob_map)
    df['gnn_review_fraud_label'] = df['review_id'].map(review_label_map)
    
    master_csv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/final_enriched_reviews_dataset.csv")
    df.to_csv(master_csv, index=False)
    print(f"Saved {len(df)} enriched review transactions to {master_csv}")
    print("\nAll export deliverables successfully generated.")

if __name__ == "__main__":
    main()
