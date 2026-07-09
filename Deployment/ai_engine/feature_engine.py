import hashlib
from typing import Dict
from ai_engine.schemas import ReviewBatchInput, ScoreResultPayload, ScoredReviewItem
from ai_engine.model_loader import model_loader

def compute_late_fusion_scores(batch: ReviewBatchInput, hgt_scores: Dict[str, float], history=None) -> ScoreResultPayload:
    """
    Executes Late Fusion inference across Reviewer Head (3-Var) and Review Head (2-Var).
    Computes rolling historical average DeBERTa spam probability per reviewer over time.
    Generates immutable cryptographic tx hashes for Web3 on-chain verification.
    """
    sub_id = batch.submitter_id
    reviewer_deberta_sums = {}
    reviewer_review_counts = {}
    
    # 1. Initialize historical DeBERTa sums and counts per reviewer from DB context
    if history and getattr(history, 'reviews', None):
        for r in history.reviews:
            prob = getattr(r, 'deberta_prob', None)
            if prob is None or prob == 0.0:
                prob = 0.30
            reviewer_deberta_sums[r.reviewer_id] = reviewer_deberta_sums.get(r.reviewer_id, 0.0) + prob
            reviewer_review_counts[r.reviewer_id] = reviewer_review_counts.get(r.reviewer_id, 0) + 1
            
    if history and getattr(history, 'reviewers', None):
        for rev in history.reviewers:
            if rev.universal_reviewer_id not in reviewer_review_counts and getattr(rev, 'user_avg_past_deberta_score', 0.0) > 0:
                reviewer_deberta_sums[rev.universal_reviewer_id] = rev.user_avg_past_deberta_score
                reviewer_review_counts[rev.universal_reviewer_id] = 1

    scored_items = []
    
    for item in batch.reviews:
        univ_rev_id = f"{sub_id}:{item.reviewer_id}"
        
        # 1. NLP Text Spam Probability (DeBERTa-v3 / Vector Engine)
        deberta_prob = model_loader.predict_deberta_prob(item.review_text)
        
        # 2. Localized Subgraph Anomaly Score (HGT GNN)
        hgt_score = hgt_scores.get(item.review_id, 0.30)
        
        # 3. Reviewer Head 3rd Feature: Historical Average DeBERTa Score over Time
        cnt = reviewer_review_counts.get(univ_rev_id, 0)
        if cnt > 0:
            user_avg_past_deberta_score = reviewer_deberta_sums[univ_rev_id] / cnt
        else:
            user_avg_past_deberta_score = 0.0
            
        # 4. Predict Reviewer Head (3-Var) and Review Head (2-Var) using BEST Late Fusion Models (LightGBM!)
        reviewer_score = model_loader.predict_late_fusion_reviewer(hgt_score, deberta_prob, user_avg_past_deberta_score)
        review_score = model_loader.predict_late_fusion_review(deberta_prob, hgt_score)
        
        # Primary Transaction Score using exact JSON validation threshold
        ai_score = round(float(review_score), 4)
        is_fraud = 1 if ai_score >= getattr(model_loader, 'review_threshold', 0.47) else 0
        
        # Update rolling state for subsequent reviews by same author in this batch!
        reviewer_deberta_sums[univ_rev_id] = reviewer_deberta_sums.get(univ_rev_id, 0.0) + deberta_prob
        reviewer_review_counts[univ_rev_id] = cnt + 1
        
        # 5. Generate deterministic cryptographic Web3 Transaction Hash
        raw_string = f"{batch.submitter_id}:{item.review_id}:{ai_score}:{is_fraud}:{item.review_date}"
        tx_hash = "0x" + hashlib.sha256(raw_string.encode()).hexdigest()
        
        scored_items.append(
            ScoredReviewItem(
                review_id=item.review_id,
                ai_score=ai_score,
                deberta_prob=round(float(deberta_prob), 4),
                reviewer_score=round(float(reviewer_score), 4),
                review_score=round(float(review_score), 4),
                is_fraud=is_fraud,
                status="Confirmed",
                tx_hash=tx_hash
            )
        )
        
    return ScoreResultPayload(
        submitter_id=batch.submitter_id,
        results=scored_items
    )
