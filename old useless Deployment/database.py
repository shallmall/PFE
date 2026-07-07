"""
Relational Database Schema & Ledger Models
==========================================
Encapsulates SQLite/PostgreSQL relational persistence inside the API application layer.
Defines Submitters, Reviewers, Reviewees, and the Core Reviews Ledger.
"""

import os
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

default_db_path = Path(__file__).resolve().parent / "reviews_ledger.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{default_db_path.as_posix()}")

# For SQLite, enable check_same_thread=False for FastAPI concurrency
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Submitter(Base):
    """API Client submitting review payloads."""
    __tablename__ = "submitters"

    submitter_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    public_key = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    reviews = relationship("Review", back_populates="submitter")

class Reviewer(Base):
    """Review author entity indexed by 16-byte Keccak-256 hex string."""
    __tablename__ = "reviewers"

    universal_reviewer_id = Column(String(34), primary_key=True, index=True) # '0x' + 32 hex chars
    reviewer_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=True)

    reviews = relationship("Review", back_populates="reviewer")

class Reviewee(Base):
    """Target entity (Product or User) indexed by 16-byte Keccak-256 hex string."""
    __tablename__ = "reviewees"

    universal_reviewee_id = Column(String(34), primary_key=True, index=True) # '0x' + 32 hex chars
    reviewee_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=True)
    type = Column(String, default="Product") # 'Product' or 'User'

    reviews = relationship("Review", back_populates="reviewee")

class Review(Base):
    """Core audit ledger linking universal IDs, AI scores, and blockchain transaction hashes."""
    __tablename__ = "reviews"

    universal_review_id = Column(String(34), primary_key=True, index=True) # '0x' + 32 hex chars
    submitter_id = Column(String, ForeignKey("submitters.submitter_id"), nullable=False)
    universal_reviewer_id = Column(String(34), ForeignKey("reviewers.universal_reviewer_id"), nullable=False)
    universal_reviewee_id = Column(String(34), ForeignKey("reviewees.universal_reviewee_id"), nullable=False)
    reviewer_id = Column(String, index=True, nullable=False)
    reviewer_name = Column(String, nullable=True)
    reviewee_id = Column(String, index=True, nullable=False)
    reviewee_name = Column(String, nullable=True)

    review_text = Column(Text, nullable=False)
    review_rating = Column(Float, nullable=False)
    num_photos = Column(Integer, default=0)
    num_helpful = Column(Integer, default=0)

    ai_score = Column(Integer, nullable=False) # 0 to 100 (0 = Pure Fraud, 100 = Pure Genuine)
    tx_hash = Column(String, nullable=True)    # Alastria blockchain transaction reference
    created_at = Column(DateTime, default=datetime.utcnow)

    submitter = relationship("Submitter", back_populates="reviews")
    reviewer = relationship("Reviewer", back_populates="reviews")
    reviewee = relationship("Reviewee", back_populates="reviews")

def init_db():
    """Create database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """FastAPI dependency generator for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
