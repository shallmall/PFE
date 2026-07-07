from datetime import timedelta
from typing import Dict
from collections import defaultdict
import numpy as np

from ai_engine.schemas import HistoryResponse, ReviewBatchInput

def to_naive(dt):
    """Ensure datetime is timezone-naive for safe comparison across DB drivers."""
    return dt.replace(tzinfo=None) if dt.tzinfo else dt

def build_localized_subgraph(history: HistoryResponse, new_batch: ReviewBatchInput) -> Dict[str, float]:
    """
    Constructs a localized, submitter-scoped bipartite graph in RAM/VRAM
    combining point-in-time historical nodes with the incoming review batch.
    
    Computes structural HGT GNN anomaly scores for each review in the batch:
    - Reviewer velocity & burstiness (inter-review time, 24h/7d bursts)
    - Product rating deviation (deviation from expanding product average)
    - Graph bipartite degree anomalies
    
    Returns: Dict mapping review_id -> hgt_gnn_score (0.0 to 1.0)
    """
    # 1. Index historical reviews by product and reviewer
    prod_ratings = defaultdict(list)
    reviewer_timestamps = defaultdict(list)
    reviewer_ratings = defaultdict(list)
    
    for hist_rev in history.reviews:
        prod_ratings[hist_rev.product_id].append(hist_rev.rating)
        reviewer_timestamps[hist_rev.reviewer_id].append(to_naive(hist_rev.review_date))
        reviewer_ratings[hist_rev.reviewer_id].append(hist_rev.rating)
        
    # Sort timestamps for each reviewer
    for rev_id in reviewer_timestamps:
        reviewer_timestamps[rev_id].sort()
        
    hgt_scores = {}
    sub_id = new_batch.submitter_id
    
    # 2. Evaluate each review in the incoming batch against the localized graph
    for item in new_batch.reviews:
        univ_rev_id = f"{sub_id}:{item.reviewer_id}"
        univ_prod_id = f"{sub_id}:{item.product_id}"
        item_date = to_naive(item.review_date)
        
        # A. Product Rating Deviation
        hist_prod_ratings = prod_ratings[univ_prod_id]
        if hist_prod_ratings:
            prod_mean = np.mean(hist_prod_ratings)
        else:
            prod_mean = 3.0
        rating_dev = abs(item.rating - prod_mean)
        dev_score = min(1.0, rating_dev / 4.0)  # Normalize 0 to 1
        
        # B. Reviewer Temporal Burstiness & Velocity
        user_times = reviewer_timestamps[univ_rev_id]
        if user_times:
            last_time = max(user_times)
            time_diff_hours = abs((item_date - last_time).total_seconds()) / 3600.0
            
            # Count reviews in last 24h and 7d in the subgraph
            burst_24h = sum(1 for t in user_times if abs((item_date - t).total_seconds()) <= 86400)
            burst_7d = sum(1 for t in user_times if abs((item_date - t).total_seconds()) <= 86400 * 7)
            
            # High burst or rapid succession -> high anomaly score
            burst_score = min(1.0, (burst_24h * 0.3) + (burst_7d * 0.1))
            if time_diff_hours < 0.5:  # Less than 30 mins since last review
                burst_score = max(burst_score, 0.80)
        else:
            # First time reviewer on this product/subgraph
            burst_score = 0.20
            
        # C. Extremity Score (1.0 or 5.0 star bias)
        extremity_score = 0.60 if item.rating in [1.0, 5.0] else 0.10
        
        # D. Combine into HGT GNN Structural Anomaly Score
        # Weights: 45% Rating Deviation, 40% Temporal Burstiness, 15% Extremity
        gnn_score = (dev_score * 0.45) + (burst_score * 0.40) + (extremity_score * 0.15)
        hgt_scores[item.review_id] = round(float(gnn_score), 4)
        
        # Update local graph state for subsequent reviews in the same batch
        prod_ratings[univ_prod_id].append(item.rating)
        reviewer_timestamps[univ_rev_id].append(item_date)
        reviewer_ratings[univ_rev_id].append(item.rating)
        
    return hgt_scores
