import pandas as pd
import numpy as np
import torch
from torch_geometric.data import HeteroData
import torch_geometric.transforms as T
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import os

def build_hetero_graph(csv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/public_reviews_dataset_cleaned.csv"), save_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/hetero_graph.pt")):
    print(f"Loading raw dataset from {csv_path}...")
    df = pd.read_csv(csv_path, low_memory=False)
    
    # Drop rows without dates or essential IDs to maintain chronological integrity
    df = df.dropna(subset=['review_date', 'reviewer_id', 'asin', 'review_id'])
    df['review_date'] = pd.to_datetime(df['review_date'], errors='coerce')
    df = df.dropna(subset=['review_date'])
    
    # 1. Sort Chronologically to prevent temporal leakage
    df = df.sort_values('review_date').reset_index(drop=True)
    
    print("Aggregating features...")
    # Fill NAs in numeric columns
    df['number_of_helpful'] = pd.to_numeric(df['number_of_helpful'], errors='coerce').fillna(0)
    df['number_of_photos'] = pd.to_numeric(df['number_of_photos'], errors='coerce').fillna(0)
    df['review_rating'] = pd.to_numeric(df['review_rating'], errors='coerce').fillna(3.0)
    
    # 2. Local Index Mapping
    # Since df is sorted, unique() grabs IDs in order of first chronological appearance
    reviewer_ids = df['reviewer_id'].unique()
    asin_ids = df['asin'].unique()
    review_ids = df['review_id'].unique()
    
    reviewer_map = {rid: i for i, rid in enumerate(reviewer_ids)}
    asin_map = {aid: i for i, aid in enumerate(asin_ids)}
    review_map = {rid: i for i, rid in enumerate(review_ids)}
    
    df['mapped_reviewer'] = df['reviewer_id'].map(reviewer_map)
    df['mapped_product'] = df['asin'].map(asin_map)
    df['mapped_review'] = df['review_id'].map(review_map)
    
    # 3. Feature Aggregation
    
    # Reviewer Features
    reviewer_group = df.groupby('mapped_reviewer')
    rev_feats = pd.DataFrame()
    rev_feats['review_volume'] = reviewer_group.size()
    rev_feats['mean_rating_given'] = reviewer_group['review_rating'].mean()
    rev_feats['rating_variance'] = reviewer_group['review_rating'].var().fillna(0)
    rev_feats['helpfulness_ratio'] = reviewer_group['number_of_helpful'].mean()
    rev_feats['media_propensity'] = reviewer_group['number_of_photos'].sum()
    
    # Max Daily Velocity (Reviewers) using optimized pandas
    daily_counts = df.groupby(['mapped_reviewer', df['review_date'].dt.date]).size().reset_index(name='daily_count')
    rev_feats['max_daily_velocity'] = daily_counts.groupby('mapped_reviewer')['daily_count'].max()
    
    # PU Labeling Logic (Hierarchical Tagging: Honest=0, Fake=1)
    is_labeled_honest = (reviewer_group['reviewer_labeled_honest'].first() == 1) | (reviewer_group['reviewer_labeled_honest'].first() == True)
    is_class_honest = (reviewer_group['reviewer_classified_honest'].first() == 1) | (reviewer_group['reviewer_classified_honest'].first() == True)
    is_honest = is_labeled_honest | is_class_honest
    
    is_labeled_fake = (reviewer_group['reviewer_labeled_fake'].first() == 1) | (reviewer_group['reviewer_labeled_fake'].first() == True)
    is_class_fake = (reviewer_group['reviewer_classified_fake'].first() == 1) | (reviewer_group['reviewer_classified_fake'].first() == True)
    is_fake = is_labeled_fake | is_class_fake
    
    reviewer_labels = pd.Series(-1, index=list(reviewer_group.indices.keys()))
    reviewer_labels[is_honest] = 0
    reviewer_labels[is_fake & ~is_honest] = 1
    
    # Product Features
    prod_group = df.groupby('mapped_product')
    prod_feats = pd.DataFrame()
    prod_feats['total_review_weight'] = prod_group.size()
    # Bimodal Distribution Index (Products)
    rating_counts = df.groupby('mapped_product')['review_rating'].value_counts().unstack(fill_value=0)
    for r in [1.0, 2.0, 3.0, 4.0, 5.0]:
        if r not in rating_counts.columns:
            rating_counts[r] = 0
    prod_feats['bimodal_index'] = (rating_counts[1.0] + rating_counts[5.0]) / (rating_counts[2.0] + rating_counts[3.0] + rating_counts[4.0] + 1)
    
    prod_lifespan = (prod_group['review_date'].max() - prod_group['review_date'].min()).dt.days
    prod_feats['arrival_velocity'] = prod_feats['total_review_weight'] / (prod_lifespan.replace(0, 1))
    
    product_labels = prod_group['fake_review_product'].first().fillna(0).astype(int)
    
    # 4-Hop Shortcut Feature for Reviewers
    # Map the calculated product bimodal_index back to each review in the main DataFrame
    df['target_bimodal_index'] = df['mapped_product'].map(prod_feats['bimodal_index'])
    # For each reviewer, calculate the mean of the bimodal indices of the products they reviewed
    avg_target_bimodal = df.groupby('mapped_reviewer')['target_bimodal_index'].mean()
    rev_feats['avg_target_product_bimodal_index'] = avg_target_bimodal
    
    # Review Features (Time-aware: expanding mean up to that review date to prevent future data leakage)
    df['prod_expanding_avg_rating'] = df.groupby('mapped_product')['review_rating'].expanding().mean().reset_index(level=0, drop=True)
    df['rating_dev_from_mean'] = df['review_rating'] - df['prod_expanding_avg_rating']
    
    # (5) 5th Feature: Days Since First Review (Zero-Leakage Lifecycle Context)
    df['prod_first_review_date'] = df.groupby('mapped_product')['review_date'].transform('min')
    df['days_since_first_review'] = (df['review_date'] - df['prod_first_review_date']).dt.days.fillna(0)
    
    # Keep reviews in order of mapped_review index
    review_df = df.sort_values('mapped_review').set_index('mapped_review')
    review_feats = review_df[['review_rating', 'rating_dev_from_mean', 'number_of_helpful', 'number_of_photos', 'days_since_first_review']]
    
    # PU Labeling Logic for Reviews (Hierarchical Tagging: Honest=0, Fake=1)
    rev_labeled_honest = (review_df['reviewer_labeled_honest'] == 1) | (review_df['reviewer_labeled_honest'] == True)
    rev_class_honest = (review_df['reviewer_classified_honest'] == 1) | (review_df['reviewer_classified_honest'] == True)
    is_honest_review = rev_labeled_honest | rev_class_honest
    
    rev_labeled_fake = (review_df['reviewer_labeled_fake'] == 1) | (review_df['reviewer_labeled_fake'] == True)
    rev_class_fake = (review_df['reviewer_classified_fake'] == 1) | (review_df['reviewer_classified_fake'] == True)
    is_fake_review = rev_labeled_fake | rev_class_fake
    
    review_labels = pd.Series(-1, index=review_df.index)
    review_labels[is_honest_review] = 0
    review_labels[is_fake_review & ~is_honest_review] = 1
    
    print("Scaling features...")
    # 4. Feature Scaling (Crucial PyTorch Step)
    scaler_rev = StandardScaler()
    scaler_prod = StandardScaler()
    scaler_review = StandardScaler()
    
    rev_x = scaler_rev.fit_transform(rev_feats.values)
    prod_x = scaler_prod.fit_transform(prod_feats.values)
    review_x = scaler_review.fit_transform(review_feats.values)
    
    print("Constructing PyG HeteroData...")
    # 5. Build HeteroData Object
    data = HeteroData()
    
    data['reviewer'].x = torch.tensor(rev_x, dtype=torch.float)
    data['reviewer'].y = torch.tensor(reviewer_labels.values, dtype=torch.long)
    
    data['product'].x = torch.tensor(prod_x, dtype=torch.float)
    data['product'].y = torch.tensor(product_labels.values, dtype=torch.long)
    
    data['review'].x = torch.tensor(review_x, dtype=torch.float)
    data['review'].y = torch.tensor(review_labels.values, dtype=torch.long)
    
    # Assign Monotonically Increasing Time Attributes (Causal Clocks)
    # 1. 'time' attribute: arrival/first review timestamp for entity nodes (used for Review seed sampling so edges are never dropped in Hop 1)
    data['review'].time = torch.tensor(df['mapped_review'].values, dtype=torch.long)
    min_rev_time = df.groupby('mapped_reviewer')['mapped_review'].min()
    data['reviewer'].time = torch.tensor(min_rev_time.values, dtype=torch.long)
    min_prod_time = df.groupby('mapped_product')['mapped_review'].min()
    data['product'].time = torch.tensor(min_prod_time.values, dtype=torch.long)
    
    # 2. 'max_time' attribute: latest review timestamp for entity nodes (used for Reviewer seed sampling so they see their entire history)
    data['review'].max_time = torch.tensor(df['mapped_review'].values, dtype=torch.long)
    max_rev_time = df.groupby('mapped_reviewer')['mapped_review'].max()
    data['reviewer'].max_time = torch.tensor(max_rev_time.values, dtype=torch.long)
    max_prod_time = df.groupby('mapped_product')['mapped_review'].max()
    data['product'].max_time = torch.tensor(max_prod_time.values, dtype=torch.long)
    
    # 6. Insert Edges using Local Index Maps
    reviewer_to_review = torch.tensor([
        df['mapped_reviewer'].values,
        df['mapped_review'].values
    ], dtype=torch.long)
    data['reviewer', 'authored', 'review'].edge_index = reviewer_to_review
    
    review_to_product = torch.tensor([
        df['mapped_review'].values,
        df['mapped_product'].values
    ], dtype=torch.long)
    data['review', 'targeted', 'product'].edge_index = review_to_product
    
    # 7. Universal Stratified Split (80/10/10 with seed 42 on supervised nodes matching DeBERTa)
    def create_stratified_split_mask(num_nodes, labels=None, seed=42):
        train_mask = torch.zeros(num_nodes, dtype=torch.bool)
        val_mask = torch.zeros(num_nodes, dtype=torch.bool)
        test_mask = torch.zeros(num_nodes, dtype=torch.bool)
        
        if labels is not None:
            valid_indices = np.where(labels.numpy() != -1)[0]
            valid_labels = labels.numpy()[valid_indices]
            
            # Match Colab/DeBERTa exactly: 10% test, then 1/9 of 90% (10%) val
            train_val_idx, test_idx = train_test_split(
                valid_indices, test_size=0.10, random_state=seed, stratify=valid_labels
            )
            train_val_labels = labels.numpy()[train_val_idx]
            train_idx, val_idx = train_test_split(
                train_val_idx, test_size=1/9, random_state=seed, stratify=train_val_labels
            )
            
            train_mask[train_idx] = True
            val_mask[val_idx] = True
            test_mask[test_idx] = True
        else:
            np.random.seed(seed)
            indices = np.random.permutation(num_nodes)
            train_end = int(num_nodes * 0.8)
            val_end = int(num_nodes * 0.9)
            train_mask[indices[:train_end]] = True
            val_mask[indices[train_end:val_end]] = True
            test_mask[indices[val_end:]] = True
            
        return train_mask, val_mask, test_mask
        
    tr, va, te = create_stratified_split_mask(data['reviewer'].num_nodes, labels=data['reviewer'].y, seed=42)
    data['reviewer'].train_mask = tr
    data['reviewer'].val_mask = va
    data['reviewer'].test_mask = te
    
    tr_p, va_p, te_p = create_stratified_split_mask(data['product'].num_nodes, seed=42)
    data['product'].train_mask = tr_p
    data['product'].val_mask = va_p
    data['product'].test_mask = te_p
    
    tr_r, va_r, te_r = create_stratified_split_mask(data['review'].num_nodes, labels=data['review'].y, seed=42)
    data['review'].train_mask = tr_r
    data['review'].val_mask = va_r
    data['review'].test_mask = te_r
        
    # Apply ToUndirected to add reverse edges for bidirectional message passing
    data = T.ToUndirected()(data)
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    torch.save(data, save_path)
    print(f"Data ingested and scaled successfully! Saved to {save_path}")
    print(data)

if __name__ == "__main__":
    build_hetero_graph()
