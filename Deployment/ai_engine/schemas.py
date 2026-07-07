from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class ReviewItemInput(BaseModel):
    review_id: str
    reviewer_id: str
    product_id: str
    review_text: str = ""
    rating: float = 3.0
    review_date: datetime
    num_photos: int = 0
    num_helpful: int = 0
    reviewer_name: Optional[str] = None
    product_name: Optional[str] = None
    product_category: Optional[str] = None

class ReviewBatchInput(BaseModel):
    submitter_id: str
    api_key: Optional[str] = None
    signature: Optional[str] = Field(None, alias="encrypted_hash")
    reviews: List[ReviewItemInput]

    class Config:
        populate_by_name = True

class HistoryRequest(BaseModel):
    submitter_id: str
    current_timestamp: datetime

class ReviewerNode(BaseModel):
    universal_reviewer_id: str
    reviewer_id: str
    name: Optional[str] = None
    current_score: float = 0.0
    user_avg_past_deberta_score: float = 0.0

class ProductNode(BaseModel):
    universal_product_id: str
    product_id: str
    name: Optional[str] = None
    category: Optional[str] = None

class ReviewNode(BaseModel):
    universal_review_id: str
    reviewer_id: str
    product_id: str
    review_text: str
    rating: float
    review_date: datetime
    num_photos: int
    num_helpful: int
    deberta_prob: Optional[float] = 0.0

class HistoryResponse(BaseModel):
    submitter_id: str
    reviewers: List[ReviewerNode]
    products: List[ProductNode]
    reviews: List[ReviewNode]

class ScoredReviewItem(BaseModel):
    review_id: str
    ai_score: float
    deberta_prob: float = 0.0
    reviewer_score: float = 0.0
    review_score: float = 0.0
    is_fraud: int
    status: str = "Confirmed"
    tx_hash: Optional[str] = None

class ScoreResultPayload(BaseModel):
    submitter_id: str
    results: List[ScoredReviewItem]
