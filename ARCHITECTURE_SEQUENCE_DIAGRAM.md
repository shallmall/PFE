# 4-Layer Entity Reputation Engine & Alastria Ledger Sequence Diagram

This document illustrates the end-to-end sequence flow of our **4-Layer Production Deployment Architecture**, detailing cryptographic batch ingestion, zero-leakage Graph Neural Network (GNN) + DeBERTa Late Fusion evaluation, entity reputation score aggregation, asynchronous Alastria Red T EVM zero-gas blockchain anchoring, and frontend dashboard explorer visualization.

```mermaid
sequenceDiagram
    autonumber
    actor User as Enterprise Submitter / API Client
    participant API as Layer 2: API Gateway (/api/v1/reviews/batch_submit)
    participant AI as Layer 1: AI Classification Engine (Port 8002)
    participant DB as Layer 3: Relational Database (SQLAlchemy ORM)
    participant Worker as Layer 4: Alastria Web3 Sync Daemon
    participant Chain as Alastria Red T EVM (ReputationLedger.sol)
    
    Note over User, DB: Phase 1: Cryptographic Batch Upload & Credential Validation
    User->>API: POST /api/v1/reviews/batch_submit (ReviewBatchInput JSON payload)
    API->>DB: Validate Submitter ID & API Key / ECDSA Credentials
    DB-->>API: Submitter Verified ✅
    API->>DB: ensure_batch_nodes(): Insert Reviewers, Products & Reviews as "Pending"
    DB-->>API: Nodes & Pending Reviews Committed
    
    Note over API, AI: Phase 2: Zero-Leakage AI Evaluation & Late Fusion
    API->>AI: POST http://localhost:8002/v1/score_batch (ReviewBatchInput)
    AI->>API: POST /api/v1/history (Request bounded subgraph strictly prior to batch timestamp)
    API->>DB: Query historical reviews (Max 200,000 nodes, 180 days, time < batch_time)
    DB-->>API: Return bounded historical graph & DeBERTa rolling averages
    API-->>AI: Return HistoryResponse
    Note over AI: 1. Build RAM/VRAM Localized Subgraph<br/>2. Compute HGT GNN Structural Risk Score<br/>3. Evaluate DeBERTa + GNN Late Fusion Scorer<br/>4. Flush Ephemeral Graph Memory (del history; gc.collect())
    AI->>API: POST /api/v1/results (Submit ai_score, deberta_prob, is_fraud)
    API->>DB: save_ai_results(): Update status to "Confirmed_OffChain" & update Reviewer scores
    DB-->>API: Off-Chain Results Committed
    
    Note over API, User: Phase 3: Score Aggregation & API Response
    API->>DB: get_aggregated_reviewer_scores(): Calculate Reviewer reputations & fraud counts
    API->>DB: get_aggregated_product_scores(): Calculate Product star ratings & AI risk averages
    DB-->>API: Return Aggregated Entity Summaries
    API-->>User: Return BatchReviewSubmissionResponse JSON (Reviewers, Products & Scored Results)
    
    Note over Worker, Chain: Phase 4: Asynchronous Zero-Gas Blockchain Anchoring (Layer 4)
    Note over Worker: Triggered by Volume (≥50 items), Timer (10 min), or Manual API (POST /api/v1/ledger/sync)
    Worker->>DB: Query un-anchored reviews (status in ['Confirmed_OffChain', 'Confirmed', 'Pending_Ledger'])
    DB-->>Worker: Return pending batch (e.g., 50 records)
    Worker->>Chain: Broadcast Zero-Gas Batch TX: saveReviewBatch(review_ids_16, reviewer_ids_16, scores_8, rev_scores_8) with gasPrice = 0
    Chain-->>Chain: Mine Block & Pack Storage Slots (ReviewRecord: 24B/slot, ReviewerHistoryRecord: 5B/slot)
    Chain-->>Worker: Return Immutable Mining Receipt & Web3 TxHash (0x19387c2f...)
    Worker->>DB: Update records to "Confirmed_OnChain" & save immutable blockchain tx_hash
    DB-->>Worker: Blockchain State Sync Completed ✅
    
    Note over User, API: Phase 5: REST API Queries (Explorer & Ledger Status Endpoints)
    User->>API: GET /api/v1/products & GET /api/v1/reviewers & GET /api/v1/reviews
    User->>API: GET /api/v1/reviews/product/{product_id} & GET /api/v1/reviews/reviewer/{reviewer_id}
    User->>API: GET /api/v1/ledger/status (Check DB queue vs On-Chain counts)
    API-->>User: Return JSON payloads (Entity scores, review audit logs with Web3 tx_hash, ledger status)
```

---

### Architectural Highlights of the Sequence Flow:
1. **Decoupled IO / Compute:** Layer 2 (`API Gateway`) handles all database orchestration and client interaction, while Layer 1 (`AI Engine`) strictly processes GPU/CPU graph inference and flushes ephemeral memory immediately after scoring.
2. **Strict Zero-Leakage Guarantee:** When Layer 1 requests historical context in Step 8, Layer 2 queries the database with `review_date < batch_time` and `LIMIT 200000`, preventing future target leakage and avoiding explosive $O(N^2)$ global attention scaling.
3. **Off-Chain to On-Chain State Machine:** In Step 13, scored reviews are initially marked as `Confirmed_OffChain`. The off-chain database write is only considered finalized as `Confirmed_OnChain` in Step 22 after receiving the cryptographic mining receipt from the Alastria Red T network.
4. **On-Demand Blockchain Sync:** In addition to background volume and timer triggers, clients can manually trigger Step 17 via `POST /api/v1/ledger/sync`.
