import torch
from torch_geometric.data import HeteroData
import numpy as np

def temporal_split(data: HeteroData, df, reviewer_mapping, product_mapping, train_ratio=0.7, val_ratio=0.1) -> HeteroData:
    """
    Implements Strategy A: Temporal Split.
    Sorts the data by timestamp. Assigns nodes to train/val/test based on the
    timestamp of their most recent review.
    """
    print("Performing Temporal Split...")
    
    # We already have standardized timestamps in df, but let's use the original review_date for splitting
    # to be safe, or just sort df.
    df = df.sort_values('review_date')
    
    # Calculate cutoff times
    n = len(df)
    train_cutoff_idx = int(n * train_ratio)
    val_cutoff_idx = int(n * (train_ratio + val_ratio))
    
    train_cutoff_time = df.iloc[train_cutoff_idx]['review_date']
    val_cutoff_time = df.iloc[val_cutoff_idx]['review_date']
    
    print(f"Train cutoff: {train_cutoff_time}")
    print(f"Val cutoff: {val_cutoff_time}")
    
    # For each node type, find its max review_date
    reviewer_max_time = df.groupby('reviewer_id')['review_date'].max()
    product_max_time = df.groupby('asin')['review_date'].max()
    
    # Create masks
    num_reviewers = data['reviewer'].num_nodes
    reviewer_train_mask = torch.zeros(num_reviewers, dtype=torch.bool)
    reviewer_val_mask = torch.zeros(num_reviewers, dtype=torch.bool)
    reviewer_test_mask = torch.zeros(num_reviewers, dtype=torch.bool)
    
    for rev_id, max_t in reviewer_max_time.items():
        idx = reviewer_mapping[rev_id]
        if max_t <= train_cutoff_time:
            reviewer_train_mask[idx] = True
        elif max_t <= val_cutoff_time:
            reviewer_val_mask[idx] = True
        else:
            reviewer_test_mask[idx] = True
            
    num_products = data['product'].num_nodes
    product_train_mask = torch.zeros(num_products, dtype=torch.bool)
    product_val_mask = torch.zeros(num_products, dtype=torch.bool)
    product_test_mask = torch.zeros(num_products, dtype=torch.bool)
    
    for prod_id, max_t in product_max_time.items():
        idx = product_mapping[prod_id]
        if max_t <= train_cutoff_time:
            product_train_mask[idx] = True
        elif max_t <= val_cutoff_time:
            product_val_mask[idx] = True
        else:
            product_test_mask[idx] = True
            
    data['reviewer'].train_mask = reviewer_train_mask
    data['reviewer'].val_mask = reviewer_val_mask
    data['reviewer'].test_mask = reviewer_test_mask
    
    data['product'].train_mask = product_train_mask
    data['product'].val_mask = product_val_mask
    data['product'].test_mask = product_test_mask
    
    print(f"Reviewer Train: {reviewer_train_mask.sum()}, Val: {reviewer_val_mask.sum()}, Test: {reviewer_test_mask.sum()}")
    print(f"Product Train: {product_train_mask.sum()}, Val: {product_val_mask.sum()}, Test: {product_test_mask.sum()}")
    
    return data
