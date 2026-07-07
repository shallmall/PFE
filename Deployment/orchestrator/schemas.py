from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class ReviewItemInput(BaseModel):
    review_id: str = Field(..., description="Local unique review ID on submitter platform")
    reviewer_id: str = Field(..., description="Local unique author/reviewer ID")
    product_id: str = Field(..., description="Local unique product ID (e.g., ASIN)")
    review_text: str = Field("", description="Text content of the review")
    rating: float = Field(3.0, description="Star rating from 1.0 to 5.0")
    review_date: datetime = Field(..., description="Timestamp of review creation")
    num_photos: int = Field(0, description="Number of photos attached")
    num_helpful: int = Field(0, description="Helpful votes count")
    reviewer_name: Optional[str] = None
    product_name: Optional[str] = None
    product_category: Optional[str] = None

class ReviewBatchInput(BaseModel):
    submitter_id: str = Field(..., description="Enterprise submitter ID (e.g., AMAZON_US)")
    api_key: Optional[str] = Field(None, description="Legacy secret API key (optional/deprecated in favor of signature)")
    signature: Optional[str] = Field(None, alias="encrypted_hash", description="Encrypted hash / cryptographic signature of the review batch")
    reviews: List[ReviewItemInput] = Field(..., description="Batch of reviews to process")

    class Config:
        populate_by_name = True

class HistoryRequest(BaseModel):
    submitter_id: str = Field(..., description="Enterprise submitter ID")
    current_timestamp: datetime = Field(..., description="Strict upper bound timestamp for zero-leakage query")

class ReviewerNode(BaseModel):
    universal_reviewer_id: str
    reviewer_id: str
    name: Optional[str] = None
    current_score: float = 0.0
    user_avg_past_deberta_score: float = 0.0

    class Config:
        from_attributes = True

class ProductNode(BaseModel):
    universal_product_id: str
    product_id: str
    name: Optional[str] = None
    category: Optional[str] = None

    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True

class HistoryResponse(BaseModel):
    submitter_id: str
    reviewers: List[ReviewerNode]
    products: List[ProductNode]
    reviews: List[ReviewNode]

class ScoredReviewItem(BaseModel):
    review_id: str = Field(..., description="Local review ID")
    ai_score: float = Field(..., description="Late fusion fraud probability (0.0 to 1.0)")
    deberta_prob: float = Field(0.0, description="DeBERTa NLP spam probability")
    reviewer_score: float = Field(0.0, description="3-Var Reviewer Head score over time")
    review_score: float = Field(0.0, description="2-Var Review Head score at tx level")
    is_fraud: int = Field(..., description="0 = Genuine, 1 = Fake/Anomaly")
    status: str = Field("Confirmed", description="Status of database persistence")
    tx_hash: Optional[str] = Field(None, description="Smart contract transaction hash")

class ScoreResultPayload(BaseModel):
    submitter_id: str
    results: List[ScoredReviewItem]

class BatchReportResponse(BaseModel):
    submitter_id: str
    total_processed: int
    fraud_detected: int
    results: List[ScoredReviewItem]

class ReviewerScoreSummary(BaseModel):
    universal_reviewer_id: str
    reviewer_id: str
    submitter_id: Optional[str] = None
    name: Optional[str] = None
    current_score: float = Field(0.0, description="Aggregated reputation score (0.0 to 1.0)")
    user_avg_past_deberta_score: float = Field(0.0, description="Historical NLP risk average")
    review_count: int = Field(0, description="Total reviews submitted by this reviewer")
    fraud_count: int = Field(0, description="Total fake reviews detected for this reviewer")

class ProductScoreSummary(BaseModel):
    universal_product_id: str
    product_id: str
    submitter_id: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    avg_rating: float = Field(0.0, description="Average star rating (1.0 to 5.0)")
    avg_ai_score: float = Field(0.0, description="Average AI fraud risk score")
    review_count: int = Field(0, description="Total reviews received for this product")
    fraud_count: int = Field(0, description="Total fake reviews detected for this product")

class ReviewAuditLogItem(BaseModel):
    universal_review_id: str
    submitter_id: str
    reviewer_id: str
    product_id: str
    review_text: str
    rating: float
    review_date: datetime
    ai_score: Optional[float] = 0.0
    deberta_prob: Optional[float] = 0.0
    is_fraud: Optional[int] = 0
    status: str
    tx_hash: Optional[str] = None
    reviewer_name: Optional[str] = None
    product_name: Optional[str] = None

class BatchReviewSubmissionResponse(BaseModel):
    submitter_id: str
    total_processed: int
    fraud_detected: int
    reviewers_scores: List[ReviewerScoreSummary]
    products_scores: List[ProductScoreSummary]
    results: List[ScoredReviewItem]

class LedgerStatusResponse(BaseModel):
    chain_name: str
    contract_address: Optional[str]
    confirmed_offchain_count: int
    confirmed_onchain_count: int
    pending_ledger_count: int
    latest_tx_hash: Optional[str]
    status_message: str

class LedgerSyncResponse(BaseModel):
    status: str
    synced_records: int
    latest_tx_hash: Optional[str]
    message: str

class SubmitterCreateRequest(BaseModel):
    submitter_id: str = Field(..., max_length=64, description="Unique Enterprise Submitter ID")
    name: str = Field(..., max_length=128, description="Name of the enterprise submitter")
    api_key: str = Field(..., description="Secret API Key / HMAC Secret for signature verification")
    public_key: Optional[str] = Field(None, max_length=128, description="Public Key / Web3 Address")
    is_active: bool = Field(True, description="Whether the submitter account is active")

class SubmitterUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=128, description="Updated name of the enterprise submitter")
    api_key: Optional[str] = Field(None, description="Updated Secret API Key / HMAC Secret")
    public_key: Optional[str] = Field(None, max_length=128, description="Updated Public Key / Web3 Address")
    is_active: Optional[bool] = Field(None, description="Updated active status (True/False)")

class SubmitterResponse(BaseModel):
    submitter_id: str
    name: str
    api_key: str
    public_key: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

