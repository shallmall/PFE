// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract ReputationLedger {
    address public owner;
    address public pendingOwner;

    // ==========================================
    //            CUSTOM ERROR PROTECTIONS
    // ==========================================
    error Unauthorized();
    error ZeroAddress();
    error ReviewAlreadyExists(); 
    error InvalidScoreBounds();
    error HistoryTooLargeUsePagination();
    error InvalidPagination();

    // ==========================================
    //            NEW SPLIT ARCHITECTURE
    // ==========================================

    // TABLE 1: The "Heavy" Review Table (24 bytes total -> Fits 1 per 32-byte slot)
    struct ReviewRecord {
        bytes16 reviewer_id;    // 16 bytes
        uint48 timestamp;       // 6 bytes (Safe until year 8,921,056)
        uint8 review_score;     // 1 byte
        uint8 reviewer_score;   // 1 byte
    }

    // TABLE 2: The "Light" Reviewer Table (5 bytes total -> Packs 6 per 32-byte slot)
    struct ReviewerHistoryRecord {
        uint32 timestamp;       // 4 bytes (Will overflow in year 2106)
        uint8 reviewer_score;   // 1 byte
    }

    mapping(bytes16 => ReviewRecord) public reviewRecords;
    mapping(bytes16 => ReviewerHistoryRecord[]) private reviewerHistory;

    event RecordSaved(
        bytes16 indexed review_id,
        bytes16 indexed reviewer_id,
        uint8 review_score,
        uint8 reviewer_score,
        uint32 timestamp
    );

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    // ==========================================
    //                WRITE METHODS
    // ==========================================

    function saveReview(
        bytes16 _review_id,
        bytes16 _reviewer_id,
        uint8 _review_score,
        uint8 _reviewer_score
    ) external onlyOwner {
        
        // Prevent silent overwrites
        if (reviewRecords[_review_id].timestamp != 0) {
            revert ReviewAlreadyExists();
        }

        // Validate score boundaries
        if (_review_score > 100 || _reviewer_score > 100) {
            revert InvalidScoreBounds();
        }
        
        // 1. Save to the Heavy Table (Costs 1 slot)
        reviewRecords[_review_id] = ReviewRecord({
            reviewer_id: _reviewer_id,
            timestamp: uint48(block.timestamp),
            review_score: _review_score,
            reviewer_score: _reviewer_score
        });

        // 2. Save to the Light Table (Packed efficiently into shared slots)
        reviewerHistory[_reviewer_id].push(ReviewerHistoryRecord({
            timestamp: uint32(block.timestamp),
            reviewer_score: _reviewer_score
        }));

        emit RecordSaved(
            _review_id, _reviewer_id, 
            _review_score, _reviewer_score, 
            uint32(block.timestamp)
        );
    }

    function saveReviewBatch(
        bytes16[] calldata _review_ids,
        bytes16[] calldata _reviewer_ids,
        uint8[] calldata _review_scores,
        uint8[] calldata _reviewer_scores
    ) external onlyOwner {
        uint256 len = _review_ids.length;
        if (len != _reviewer_ids.length || len != _review_scores.length || len != _reviewer_scores.length) {
            revert InvalidPagination();
        }

        uint48 currTime48 = uint48(block.timestamp);
        uint32 currTime32 = uint32(block.timestamp);

        for (uint256 i = 0; i < len; i++) {
            bytes16 rev_id = _review_ids[i];
            bytes16 rver_id = _reviewer_ids[i];
            uint8 r_score = _review_scores[i];
            uint8 rver_score = _reviewer_scores[i];

            // Prevent silent overwrites
            if (reviewRecords[rev_id].timestamp != 0) {
                revert ReviewAlreadyExists();
            }

            // Validate score boundaries
            if (r_score > 100 || rver_score > 100) {
                revert InvalidScoreBounds();
            }

            // 1. Save to the Heavy Table (Costs 1 slot)
            reviewRecords[rev_id] = ReviewRecord({
                reviewer_id: rver_id,
                timestamp: currTime48,
                review_score: r_score,
                reviewer_score: rver_score
            });

            // 2. Save to the Light Table (Packed efficiently into shared slots)
            reviewerHistory[rver_id].push(ReviewerHistoryRecord({
                timestamp: currTime32,
                reviewer_score: rver_score
            }));

            emit RecordSaved(
                rev_id, rver_id, 
                r_score, rver_score, 
                currTime32
            );
        }
    }

    // ==========================================
    //                READ METHODS
    // ==========================================

    function getReviewDetails(bytes16 _review_id) external view returns (ReviewRecord memory) {
        return reviewRecords[_review_id];
    }

    function getCurrentReviewerScore(bytes16 _reviewer_id) external view returns (ReviewerHistoryRecord memory) {
        uint256 len = reviewerHistory[_reviewer_id].length;
        if (len == 0) return ReviewerHistoryRecord(0, 0); // Returns 0s if they don't exist
        return reviewerHistory[_reviewer_id][len - 1];
    }

    function getReviewerHistory(bytes16 _reviewer_id) external view returns (ReviewerHistoryRecord[] memory) {
        uint256 count = reviewerHistory[_reviewer_id].length;
        
        // BUG FIX 1: Safely handle non-existent reviewers
        if (count == 0) return new ReviewerHistoryRecord[](0);
        if (count > 1000) revert HistoryTooLargeUsePagination();
        
        // Because the struct matches perfectly, we can just return the array!
        return reviewerHistory[_reviewer_id];
    }

    function getReviewerHistoryPaginated(
        bytes16 _reviewer_id, 
        uint256 _offset, 
        uint256 _limit
    ) external view returns (ReviewerHistoryRecord[] memory) {
        uint256 totalCount = reviewerHistory[_reviewer_id].length;
        
        // BUG FIX 2: Prevent underflow crash if user has no history
        if (totalCount == 0) return new ReviewerHistoryRecord[](0);

        if (_offset >= totalCount) revert InvalidPagination();

        if (_offset + _limit > totalCount) {
            _limit = totalCount - _offset;
        }

        ReviewerHistoryRecord[] memory result = new ReviewerHistoryRecord[](_limit);
        for (uint256 i = 0; i < _limit; i++) {
            result[i] = reviewerHistory[_reviewer_id][_offset + i];
        }
        return result;
    }

    // ==========================================
    //            OWNERSHIP MANAGEMENT
    // ==========================================

    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        pendingOwner = newOwner;
    }

    function acceptOwnership() external {
        if (msg.sender != pendingOwner) revert Unauthorized();
        emit OwnershipTransferred(owner, pendingOwner);
        owner = pendingOwner;
        pendingOwner = address(0);
    }
}