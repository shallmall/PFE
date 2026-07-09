from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .db import Base

class Submitter(Base):
    __tablename__ = "submitters"

    submitter_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    api_key = Column(String, unique=True, index=True, nullable=False)
    public_key = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=True)

    reviewers = relationship("Reviewer", back_populates="submitter", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="submitter", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="submitter", cascade="all, delete-orphan")


class Reviewer(Base):
    __tablename__ = "reviewers"

    universal_reviewer_id = Column(String, primary_key=True, index=True)  # Format: 16-byte hex hash (0x + 32 chars) of submitter_id:reviewer_id
    submitter_id = Column(String, ForeignKey("submitters.submitter_id"), index=True, nullable=False)
    reviewer_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=True)
    current_score = Column(Float, default=0.0)
    user_avg_past_deberta_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    submitter = relationship("Submitter", back_populates="reviewers")
    reviews = relationship("Review", back_populates="reviewer", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    universal_product_id = Column(String, primary_key=True, index=True)  # Format: 16-byte hex hash (0x + 32 chars) of submitter_id:product_id
    submitter_id = Column(String, ForeignKey("submitters.submitter_id"), index=True, nullable=False)
    product_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=True)
    category = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    submitter = relationship("Submitter", back_populates="products")
    reviews = relationship("Review", back_populates="product", cascade="all, delete-orphan")


class Review(Base):
    __tablename__ = "reviews"

    universal_review_id = Column(String, primary_key=True, index=True)  # Format: 16-byte hex hash (0x + 32 chars) of submitter_id:review_id
    submitter_id = Column(String, ForeignKey("submitters.submitter_id"), index=True, nullable=False)
    reviewer_id = Column(String, ForeignKey("reviewers.universal_reviewer_id"), index=True, nullable=False)
    product_id = Column(String, ForeignKey("products.universal_product_id"), index=True, nullable=False)
    
    review_text = Column(Text, nullable=True)
    rating = Column(Float, default=3.0)
    num_photos = Column(Integer, default=0)
    num_helpful = Column(Integer, default=0)
    
    # Indexed for strict zero-leakage chronological lookback queries!
    review_date = Column(DateTime, index=True, nullable=False)
    
    ai_score = Column(Float, nullable=True)  # Late fusion fraud probability (0.0 to 1.0)
    deberta_prob = Column(Float, nullable=True, default=0.0)  # DeBERTa NLP spam probability
    is_fraud = Column(Integer, nullable=True)  # 0 = Genuine, 1 = Fake/Anomaly
    status = Column(String, default="Pending", index=True)  # "Pending", "Confirmed", "Failed"
    tx_hash = Column(String, nullable=True)  # On-chain smart contract transaction hash
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    submitter = relationship("Submitter", back_populates="reviews")
    reviewer = relationship("Reviewer", back_populates="reviews")
    product = relationship("Product", back_populates="reviews")
