"""
Layer 4: Standalone Public Verifier CLI (Trustless On-Chain Reader)
====================================================================
This standalone script implements Phase 2 of the Public Verifier Dashboard workflow:
"Trustless On-Chain Verification".

It connects DIRECTLY to the Alastria Red T consortium EVM network (or any Ethereum RPC node),
completely bypassing our backend API and database, to read immutable reputation scores and
verify transaction receipts.

Usage Examples:
---------------
1. Verify a specific Review ID (using true Universal ID or 16-byte Keccak hash):
   python public_verifier_cli.py --review-id "AMAZON_US:R1001"

2. Verify a Reviewer's current reputation score:
   python public_verifier_cli.py --reviewer-id "AMAZON_US:REV888"

3. Verify a Reviewer's complete historical score progression:
   python public_verifier_cli.py --reviewer-id "AMAZON_US:REV888" --history

4. Verify an immutable Mining Receipt Hash (decodes RecordSaved event logs):
   python public_verifier_cli.py --tx-hash 0xedc0c12aafba155af3130db74e1af3ce8a16ceb9d5563b3f82996bc2fee56263
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import List, Tuple, Any

# Ensure UTF-8 printing in Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

try:
    from web3 import Web3
    from web3.exceptions import Web3Exception
except ImportError:
    print("[ERROR] Missing web3 library. Please run: uv pip install web3")
    sys.exit(1)

# Default Alastria Red T RPC Endpoints
DEFAULT_RPC_URL = os.getenv("ALASTRIA_RPC_URL", "http://sinbad2.ujaen.es:8012")
DEFAULT_CONTRACT_ADDRESS = os.getenv("ALASTRIA_CONTRACT_ADDRESS", "0x51EA9c1D046BE57E3B461d9048176800cb3380f5")

# Minimal ABI required for trustless verification reading
VERIFIER_ABI = [
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
    },
    {
        "inputs": [{"internalType": "bytes16", "name": "_review_id", "type": "bytes16"}],
        "name": "getReviewDetails",
        "outputs": [
            {
                "components": [
                    {"internalType": "bytes16", "name": "reviewer_id", "type": "bytes16"},
                    {"internalType": "uint48", "name": "timestamp", "type": "uint48"},
                    {"internalType": "uint8", "name": "review_score", "type": "uint8"},
                    {"internalType": "uint8", "name": "reviewer_score", "type": "uint8"}
                ],
                "internalType": "struct ReputationLedger.ReviewRecord",
                "name": "",
                "type": "tuple"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "bytes16", "name": "_reviewer_id", "type": "bytes16"}],
        "name": "getCurrentReviewerScore",
        "outputs": [
            {
                "components": [
                    {"internalType": "uint32", "name": "timestamp", "type": "uint32"},
                    {"internalType": "uint8", "name": "reviewer_score", "type": "uint8"}
                ],
                "internalType": "struct ReputationLedger.ReviewerHistoryRecord",
                "name": "",
                "type": "tuple"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "bytes16", "name": "_reviewer_id", "type": "bytes16"}],
        "name": "getReviewerHistory",
        "outputs": [
            {
                "components": [
                    {"internalType": "uint32", "name": "timestamp", "type": "uint32"},
                    {"internalType": "uint8", "name": "reviewer_score", "type": "uint8"}
                ],
                "internalType": "struct ReputationLedger.ReviewerHistoryRecord[]",
                "name": "",
                "type": "tuple[]"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "bytes16", "name": "review_id", "type": "bytes16"},
            {"indexed": True, "internalType": "bytes16", "name": "reviewer_id", "type": "bytes16"},
            {"indexed": False, "internalType": "uint8", "name": "review_score", "type": "uint8"},
            {"indexed": False, "internalType": "uint8", "name": "reviewer_score", "type": "uint8"},
            {"indexed": False, "internalType": "uint32", "name": "timestamp", "type": "uint32"}
        ],
        "name": "RecordSaved",
        "type": "event"
    }
]

def get_keccak_bytes16(universal_id: str) -> bytes:
    """Converts a string ID or hex string into a deterministic 16-byte (bytes16) Keccak/SHA256 hash."""
    if universal_id.startswith("0x") and len(universal_id) == 34:
        try:
            return bytes.fromhex(universal_id[2:])
        except ValueError:
            pass
    return hashlib.sha256(universal_id.encode('utf-8')).digest()[:16]

def format_timestamp(ts: int) -> str:
    """Formats Unix timestamp into human-readable UTC string."""
    if ts == 0:
        return "N/A (Not Found)"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def verify_review_id(w3: Web3, contract: Any, review_id_str: str):
    """Queries smart contract for immutable review details."""
    print(f"\n[VERIFY] [Mode 1] Trustless Verification for Review ID: '{review_id_str}'")
    rev_bytes = get_keccak_bytes16(review_id_str)
    print(f"   └── Cryptographic bytes16 Key: 0x{rev_bytes.hex()}")
    
    try:
        try:
            record = contract.functions.getReviewDetails(rev_bytes).call()
            reviewer_id_hex, ts, r_score, rver_score = record
        except Exception:
            # Fallback for live Alastria Red T contract (AuditRecordView)
            record = contract.functions.getEntityScore(rev_bytes, 0).call()
            _, ts, _, r_score = record
            reviewer_id_hex = b'\x00' * 16
            rver_score = r_score
            
        if ts == 0:
            print(f"[NOT FOUND] Result: NOT FOUND on blockchain! This review has not been anchored yet.")
            return
            
        print(f"[FOUND] Result: FOUND ON-CHAIN (Immutable Storage Slot Verified)")
        print("-" * 60)
        if reviewer_id_hex != b'\x00' * 16:
            print(f"   • On-Chain Reviewer Hash : 0x{reviewer_id_hex.hex()}")
        print(f"   • Mined Timestamp        : {format_timestamp(ts)} ({ts})")
        print(f"   • Review AI Fraud Score  : {r_score} / 100")
        if reviewer_id_hex != b'\x00' * 16:
            print(f"   • Reviewer Reputation    : {rver_score} / 100")
        print("-" * 60)
    except Exception as e:
        print(f"[ERROR] RPC Query Failed: {e}")

def verify_reviewer_id(w3: Web3, contract: Any, reviewer_id_str: str, show_history: bool = False):
    """Queries smart contract for reviewer reputation score or full historical trail."""
    print(f"\n[VERIFY] [Mode 2] Trustless Verification for Reviewer ID: '{reviewer_id_str}'")
    rver_bytes = get_keccak_bytes16(reviewer_id_str)
    print(f"   └── Cryptographic bytes16 Key: 0x{rver_bytes.hex()}")
    
    try:
        if not show_history:
            try:
                record = contract.functions.getCurrentReviewerScore(rver_bytes).call()
                ts, score = record
            except Exception:
                # Fallback for live Alastria Red T contract (check bit 1, then bit 0)
                record = contract.functions.getEntityScore(rver_bytes, 1).call()
                _, ts, _, score = record
                if ts == 0 and score == 0:
                    record = contract.functions.getEntityScore(rver_bytes, 0).call()
                    _, ts, _, score = record
                
            if ts == 0 and score == 0:
                print(f"[NOT FOUND] Result: NOT FOUND on blockchain! This reviewer has no anchored history.")
                return
            print(f"[VERIFIED] Result: LATEST REPUTATION SCORE VERIFIED")
            print("-" * 60)
            print(f"   • Last Updated Timestamp : {format_timestamp(ts)} ({ts})")
            print(f"   • Current Reputation     : {score} / 100")
            print("-" * 60)
        else:
            try:
                history = contract.functions.getReviewerHistory(rver_bytes).call()
            except Exception:
                # Fallback for live Alastria Red T contract (check bit 1, then bit 0)
                raw_hist = contract.functions.getEntityHistory(rver_bytes, 1).call()
                if not raw_hist:
                    raw_hist = contract.functions.getEntityHistory(rver_bytes, 0).call()
                history = [(rec[1], rec[3]) for rec in raw_hist]
                
            if not history:
                print(f"[NOT FOUND] Result: NOT FOUND on blockchain! This reviewer has no anchored history.")
                return
            print(f"[VERIFIED] Result: COMPLETE HISTORICAL REPUTATION TRAIL VERIFIED ({len(history)} updates)")
            print("-" * 60)
            print(f"   {'Update #':<10} | {'Mined Timestamp (UTC)':<24} | {'Reputation Score':<18}")
            print("-" * 60)
            for idx, (ts, score) in enumerate(history, 1):
                print(f"   #{idx:<9} | {format_timestamp(ts):<24} | {score:>3} / 100")
            print("-" * 60)
    except Exception as e:
        print(f"[ERROR] RPC Query Failed: {e}")

def verify_tx_hash(w3: Web3, contract: Any, tx_hash: str):
    """Fetches mining receipt and decodes RecordSaved event logs directly from the blockchain block."""
    print(f"\n[VERIFY] [Mode 3] Trustless Verification for Transaction Receipt Hash:")
    print(f"   └── TxHash: {tx_hash}")
    
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
        print(f"[FOUND] Result: MINING RECEIPT FOUND (Block #{receipt.blockNumber:,})")
        print("-" * 60)
        print(f"   • Gas Used           : {receipt.gasUsed:,}")
        print(f"   • Status             : {'SUCCESS (1)' if receipt.status == 1 else 'REVERTED (0)'}")
        print(f"   • Contract Address   : {receipt.contractAddress or receipt.to}")
        
        # Decode RecordSaved events emitted in this transaction
        events = contract.events.RecordSaved().process_receipt(receipt)
        print(f"   • Anchored Records   : {len(events)} review(s) anchored in this block!")
        print("-" * 60)
        
        if events:
            print(f"   {'Review Hash (First 10c)':<18} | {'Reviewer Hash (First 10c)':<24} | {'Rev Score':<10} | {'Rver Score':<10} | {'Mined Time':<20}")
            print("-" * 90)
            for ev in events:
                args = ev['args']
                rev_h = f"0x{args['review_id'].hex()[:10]}..."
                rver_h = f"0x{args['reviewer_id'].hex()[:10]}..."
                r_sc = args['review_score']
                rver_sc = args['reviewer_score']
                ts_str = format_timestamp(args['timestamp'])
                print(f"   {rev_h:<18} | {rver_h:<24} | {r_sc:>4} / 100 | {rver_sc:>4} / 100 | {ts_str:<20}")
            print("-" * 90)
    except Exception as e:
        print(f"[ERROR] Receipt Verification Failed: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Public Verifier CLI: Trustless On-Chain Reader for Alastria Red T / EVM"
    )
    parser.add_argument("--rpc-url", default=DEFAULT_RPC_URL, help="Web3 RPC Endpoint URL")
    parser.add_argument("--contract", default=DEFAULT_CONTRACT_ADDRESS, help="Deployed ReputationLedger Contract Address")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--review-id", help="Verify a specific Review ID (true Universal ID or 0x... hex hash)")
    group.add_argument("--reviewer-id", help="Verify a Reviewer ID (true Universal ID or 0x... hex hash)")
    group.add_argument("--tx-hash", help="Verify a mining receipt hash and decode block logs (0x...)")
    
    parser.add_argument("--history", action="store_true", help="When used with --reviewer-id, displays full historical score progression")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print(" [ALASTRIA RED T / EVM PUBLIC VERIFIER] TRUSTLESS ON-CHAIN READER")
    print("=" * 70)
    print(f" • RPC Endpoint     : {args.rpc_url}")
    print(f" • Contract Address : {args.contract}")
    
    # Connect to Web3
    try:
        if args.rpc_url.lower() == "simulated":
            from web3.providers.eth_tester import EthereumTesterProvider
            w3 = Web3(EthereumTesterProvider())
            print(" • Provider Type    : Simulated (EthereumTesterProvider)")
        else:
            w3 = Web3(Web3.HTTPProvider(args.rpc_url))
            if not w3.is_connected():
                print(f"[WARN] Warning: Could not connect to live node at {args.rpc_url}. Is the node reachable?")
            else:
                print(f" • Provider Status  : Connected [OK] (Chain ID: {w3.eth.chain_id})")
    except Exception as e:
        print(f"[ERROR] Failed to initialize Web3 provider: {e}")
        sys.exit(1)
        
    contract = w3.eth.contract(address=w3.to_checksum_address(args.contract), abi=VERIFIER_ABI)
    
    if args.review_id:
        verify_review_id(w3, contract, args.review_id)
    elif args.reviewer_id:
        verify_reviewer_id(w3, contract, args.reviewer_id, show_history=args.history)
    elif args.tx_hash:
        verify_tx_hash(w3, contract, args.tx_hash)

if __name__ == "__main__":
    main()
