// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title Alastria Reputation Ledger
 * @notice Immutable, access-controlled blockchain ledger for Reputation AI evaluations.
 * Compatible with Alastria Red T consortium nodes (EVM pre-PUSH0 / Paris target).
 * Hyper-optimized struct packed into 1 single EVM storage slot (6 bytes total in storage).
 * Indexed directly by Keccak ID of the entity (Product or Reviewer) and Entity Bit (0 or 1).
 * Supports both fast final reputation reads and querying the entire historical score evolution.
 */
contract ReputationLedger {
    address public owner;
    address public pendingOwner;

    // Custom errors compile down to 4-byte selectors, saving massive gas over string reverts
    error Unauthorized();
    error ZeroAddress();
    error InvalidEntityBit();

    struct AuditRecord {
        uint32 timestamp;       // 4-byte Unix timestamp valid until year 2106 (Slot 0: 4 bytes)
        uint8 entity_bit;       // 1-byte flag: 0 = Reviewee/Product, 1 = Reviewer/User (Slot 0: 1 byte)
        uint8 ai_score;         // 1-byte AI Fraud Score (0-100) (Slot 0: 1 byte -> Total: 6/32 bytes!)
    }

    struct AuditRecordView {
        bytes16 entity_id;
        uint32 timestamp;
        uint8 entity_bit;
        uint8 ai_score;
    }

    struct EntityKey {
        bytes16 entity_id;
        uint8 entity_bit;
    }

    // Mapping from Keccak entity_id => entity_bit (0 or 1) => latest 1-slot packed audit record
    mapping(bytes16 => mapping(uint8 => AuditRecord)) public entityRecords;

    // Mapping from Keccak entity_id => entity_bit (0 or 1) => entire history of historical audit records
    mapping(bytes16 => mapping(uint8 => AuditRecord[])) private entityHistory;

    // Sequential array of all unique entity keys to allow fetching latest records history
    EntityKey[] public allEntityKeys;

    event RecordSubmitted(
        bytes16 indexed entity_id,
        uint8 indexed entity_bit,
        uint8 ai_score,
        uint32 timestamp
    );

    event OwnershipTransferStarted(address indexed previousOwner, address indexed newOwner);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    /**
     * @notice Starts the 2-step ownership transfer by nominating a pending owner.
     */
    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        pendingOwner = newOwner;
        emit OwnershipTransferStarted(owner, newOwner);
    }

    /**
     * @notice Finalizes ownership transfer when called by the pending owner.
     */
    function acceptOwnership() external {
        if (msg.sender != pendingOwner) revert Unauthorized();
        emit OwnershipTransferred(owner, pendingOwner);
        owner = pendingOwner;
        pendingOwner = address(0);
    }

    /**
     * @notice Submits an AI reputation score for a specific Reviewee (Product) or Reviewer (User).
     * @param _entity_id Universal Keccak ID of the product or reviewer
     * @param _entity_bit 0 if entity is Reviewee (Product), 1 if entity is Reviewer (Author)
     * @param _ai_score AI model evaluation score (0-100)
     */
    function addRecord(
        bytes16 _entity_id,
        uint8 _entity_bit,
        uint8 _ai_score
    ) external onlyOwner {
        if (_entity_bit != 0 && _entity_bit != 1) revert InvalidEntityBit();

        AuditRecord memory newRecord = AuditRecord({
            timestamp: uint32(block.timestamp),
            entity_bit: _entity_bit,
            ai_score: _ai_score
        });

        // If this entity key has never been recorded before, track in history array
        if (entityRecords[_entity_id][_entity_bit].timestamp == 0) {
            allEntityKeys.push(EntityKey(_entity_id, _entity_bit));
        }

        entityRecords[_entity_id][_entity_bit] = newRecord;
        entityHistory[_entity_id][_entity_bit].push(newRecord);

        emit RecordSubmitted(_entity_id, _entity_bit, _ai_score, uint32(block.timestamp));
    }

    /**
     * @notice Retrieves the latest/final reputation score recorded for an entity.
     * @param _entity_id Universal Keccak ID of the product or reviewer
     * @param _entity_bit Define type: 0 for Product (Reviewee), 1 for Reviewer
     */
    function getEntityScore(bytes16 _entity_id, uint8 _entity_bit) external view returns (AuditRecordView memory) {
        if (_entity_bit != 0 && _entity_bit != 1) revert InvalidEntityBit();
        AuditRecord memory rec = entityRecords[_entity_id][_entity_bit];
        return AuditRecordView({
            entity_id: _entity_id,
            timestamp: rec.timestamp,
            entity_bit: _entity_bit,
            ai_score: rec.ai_score
        });
    }

    /**
     * @notice Retrieves the ENTIRE history of reputation scores recorded for a specific entity over time.
     * @param _entity_id Universal Keccak ID of the product or reviewer
     * @param _entity_bit Define type: 0 for Product (Reviewee), 1 for Reviewer
     */
    function getEntityHistory(bytes16 _entity_id, uint8 _entity_bit) external view returns (AuditRecordView[] memory) {
        if (_entity_bit != 0 && _entity_bit != 1) revert InvalidEntityBit();
        AuditRecord[] memory history = entityHistory[_entity_id][_entity_bit];
        uint256 count = history.length;
        AuditRecordView[] memory views = new AuditRecordView[](count);
        for (uint256 i = 0; i < count; i++) {
            views[i] = AuditRecordView({
                entity_id: _entity_id,
                timestamp: history[i].timestamp,
                entity_bit: _entity_bit,
                ai_score: history[i].ai_score
            });
        }
        return views;
    }

    /**
     * @notice Returns total number of unique entity records on chain.
     */
    function getTotalRecordsCount() external view returns (uint256) {
        return allEntityKeys.length;
    }

    /**
     * @notice Automatically reads the N latest entity reputation records sealed on the blockchain.
     * @param _limit Number of recent records to retrieve (capped at 500 for RPC DoS protection)
     */
    function getLatestRecords(uint256 _limit) external view returns (AuditRecordView[] memory) {
        if (_limit > 500) {
            _limit = 500;
        }
        uint256 total = allEntityKeys.length;
        if (_limit > total) {
            _limit = total;
        }

        AuditRecordView[] memory latest = new AuditRecordView[](_limit);
        for (uint256 i = 0; i < _limit; i++) {
            EntityKey memory key = allEntityKeys[total - 1 - i];
            AuditRecord memory rec = entityRecords[key.entity_id][key.entity_bit];

            latest[i] = AuditRecordView({
                entity_id: key.entity_id,
                timestamp: rec.timestamp,
                entity_bit: rec.entity_bit,
                ai_score: rec.ai_score
            });
        }
        return latest;
    }
}
