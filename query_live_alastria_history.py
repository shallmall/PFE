import datetime
from web3 import Web3

# ─────────────────────────────────────────────────────────────────────────────
# 1. LIVE ALASTRIA CONNECTION & CONTRACT CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
RPC_URL = "http://sinbad2.ujaen.es:8012"
CONTRACT_ADDRESS = "0x729F000825fBaC462ad694700E51D5C719459bEE"

# Minimal ABI containing only the read view functions needed
MINIMAL_ABI = [
    {
        "inputs": [
            {"internalType": "bytes16", "name": "_entity_id", "type": "bytes16"},
            {"internalType": "uint8", "name": "_entity_bit", "type": "uint8"}
        ],
        "name": "getEntityScore",
        "outputs": [
            {
                "components": [
                    {"internalType": "bytes16", "name": "entityId", "type": "bytes16"},
                    {"internalType": "uint64", "name": "timestamp", "type": "uint64"},
                    {"internalType": "uint8", "name": "entityBit", "type": "uint8"},
                    {"internalType": "uint8", "name": "aiScore", "type": "uint8"}
                ],
                "internalType": "struct ReputationLedger.AuditRecordView",
                "name": "",
                "type": "tuple"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "bytes16", "name": "_entity_id", "type": "bytes16"},
            {"internalType": "uint8", "name": "_entity_bit", "type": "uint8"}
        ],
        "name": "getEntityHistory",
        "outputs": [
            {
                "components": [
                    {"internalType": "bytes16", "name": "entityId", "type": "bytes16"},
                    {"internalType": "uint64", "name": "timestamp", "type": "uint64"},
                    {"internalType": "uint8", "name": "entityBit", "type": "uint8"},
                    {"internalType": "uint8", "name": "aiScore", "type": "uint8"}
                ],
                "internalType": "struct ReputationLedger.AuditRecordView[]",
                "name": "",
                "type": "tuple[]"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

def main():
    print("═" * 70)
    print("  QUERYING LIVE ALASTRIA BLOCKCHAIN FOR ENTITY REPUTATION")
    print(f"  Node URL : {RPC_URL}")
    print(f"  Contract : {CONTRACT_ADDRESS}")
    print("═" * 70)

    # Connect to Alastria Node
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("❌ Could not connect to Alastria node.")
        return

    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=MINIMAL_ABI)

    # Choose the Entity with 2 live scores mined on-chain (Product ID: 0x1111...)
    target_entity_hex = "11112222333344445555666677778888"
    target_entity_bytes = bytes.fromhex(target_entity_hex)
    entity_bit = 0 # 0 = Product / Reviewee Target

    print(f"\nTarget Entity Keccak ID : 0x{target_entity_hex}")
    print(f"Target Entity Type      : Product (Bit {entity_bit})")

    # ─────────────────────────────────────────────────────────────────────────
    # REQUEST 1: READ LATEST REPUTATION SCORE SNAPSHOT
    # ─────────────────────────────────────────────────────────────────────────
    print("\n── REQUEST 1: Querying Latest Score Snapshot (getEntityScore) ─────")
    latest_record = contract.functions.getEntityScore(target_entity_bytes, entity_bit).call()
    
    # Unpack tuple: (entityId, timestamp, entityBit, aiScore)
    _, timestamp_latest, _, score_latest = latest_record
    readable_time_latest = datetime.datetime.fromtimestamp(timestamp_latest, datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')

    print(f"✅ Latest Sealed AI Score : {score_latest} / 100")
    print(f"✅ Last Updated On-Chain  : {readable_time_latest}")

    # ─────────────────────────────────────────────────────────────────────────
    # REQUEST 2: READ ENTIRE CHRONOLOGICAL EVOLUTION TRAIL
    # ─────────────────────────────────────────────────────────────────────────
    print("\n── REQUEST 2: Querying Entire Chronological History (getEntityHistory) ──")
    history_records = contract.functions.getEntityHistory(target_entity_bytes, entity_bit).call()

    print(f"✅ Found {len(history_records)} historical evaluations permanently recorded on Alastria:\n")
    
    for idx, rec in enumerate(history_records, 1):
        _, timestamp_hist, _, score_hist = rec
        readable_time_hist = datetime.datetime.fromtimestamp(timestamp_hist, datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
        
        # Explain progression
        status = "Initial Evaluation" if idx == 1 else "Reputation Adjustment"
        print(f"   [{idx}] {status:<22} -> Score: {score_hist:<3} / 100 | Timestamp: {readable_time_hist}")

    print("\n" + "═" * 70)

if __name__ == "__main__":
    main()
