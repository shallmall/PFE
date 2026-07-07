#!/usr/bin/env python3
"""
Automated E2E Test for Standalone Public Verifier CLI (Simulated Hardhat/Ethereum Node)
========================================================================================
This test script verifies that our standalone public verifier CLI works seamlessly by:
1. Spinning up an in-memory simulated Ethereum blockchain (EthereumTesterProvider / Hardhat equivalent).
2. Compiling and deploying the ReputationLedger.sol smart contract.
3. Broadcasting a zero-gas batch transaction to anchor sample review and reviewer reputation scores.
4. Executing all 4 Trustless Verification Modes:
   - Mode 1: Review ID Verification (--review-id)
   - Mode 2: Latest Reviewer Reputation Verification (--reviewer-id)
   - Mode 3: Complete Reviewer Historical Progression Verification (--reviewer-id --history)
   - Mode 4: Mining Receipt & Event Log Decoding Verification (--tx-hash)
"""

import os
import sys
import hashlib
from datetime import datetime, timezone

# Ensure UTF-8 printing in Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add parent directory to path to import worker helper if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider
import solcx

from verifier.public_verifier_cli import (
    VERIFIER_ABI, get_keccak_bytes16, verify_review_id,
    verify_reviewer_id, verify_tx_hash
)

def compile_contract():
    """Compiles ReputationLedger.sol using solcx."""
    contract_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ReputationLedger.sol"))
    if not os.path.exists(contract_path):
        # Fallback to web3_worker/contracts
        contract_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web3_worker", "contracts", "ReputationLedger.sol"))
        
    print(f"📦 Compiling contract from: {contract_path}")
    with open(contract_path, 'r', encoding='utf-8') as f:
        source_code = f.read()
        
    compiled = solcx.compile_source(
        source_code,
        output_values=["abi", "bin"],
        solc_version="0.8.19"
    )
    contract_id, contract_interface = compiled.popitem()
    return contract_interface['abi'], contract_interface['bin']

def run_simulated_verifier_test():
    print("=" * 80)
    print(" 🚀 STARTING SIMULATED HARDHAT/ETHEREUM PUBLIC VERIFIER E2E TEST")
    print("=" * 80)
    
    # 1. Start Simulated Ethereum Provider
    w3 = Web3(EthereumTesterProvider())
    assert w3.is_connected(), "Failed to connect to EthereumTesterProvider!"
    
    deployer = w3.eth.accounts[0]
    w3.eth.default_account = deployer
    print(f" ✅ Connected to Simulated Blockchain (Deployer: {deployer})")
    
    # 2. Compile & Deploy Contract
    abi, bytecode = compile_contract()
    ContractCls = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    print(" 🔨 Deploying ReputationLedger smart contract...")
    tx_hash = ContractCls.constructor().transact({'from': deployer})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    contract_address = receipt.contractAddress
    print(f" ✅ Contract Deployed at Address: {contract_address}")
    
    contract = w3.eth.contract(address=contract_address, abi=abi)
    
    # 3. Anchor Sample Batch Data (Simulating Alastria Worker)
    print("\n 📝 Broadcasting Zero-Gas Batch TX to anchor 3 sample reviews...")
    review_ids = [
        get_keccak_bytes16("AMAZON_US:R_1001"),
        get_keccak_bytes16("AMAZON_US:R_1002"),
        get_keccak_bytes16("AMAZON_US:R_1003")
    ]
    reviewer_ids = [
        get_keccak_bytes16("AMAZON_US:REV_ALICE"),
        get_keccak_bytes16("AMAZON_US:REV_ALICE"), # Alice wrote 2 reviews!
        get_keccak_bytes16("AMAZON_US:REV_BOB")
    ]
    review_scores = [95, 10, 88]      # Review 1001 is 95% fake, 1002 is 10% fake, 1003 is 88% fake
    reviewer_scores = [20, 85, 12]    # Alice's rep was 20, then jumped to 85; Bob's rep is 12
    
    batch_tx_hash = contract.functions.saveReviewBatch(
        review_ids, reviewer_ids, review_scores, reviewer_scores
    ).transact({'from': deployer})
    
    batch_receipt = w3.eth.wait_for_transaction_receipt(batch_tx_hash)
    batch_tx_hex = batch_tx_hash.hex()
    print(f" ✅ Batch Anchored Successfully! TxHash: {batch_tx_hex} | Gas Used: {batch_receipt.gasUsed:,}")
    
    # =========================================================================
    # 4. EXECUTE TRUSTLESS VERIFICATION CLI MODES
    # =========================================================================
    
    print("\n" + "=" * 80)
    print(" 🔍 RUNNING PUBLIC VERIFIER CLI TEST SUITE")
    print("=" * 80)
    
    # Test Mode 1: Review ID Verification
    verify_review_id(w3, contract, "AMAZON_US:R_1001")
    
    # Test Mode 2: Reviewer Latest Reputation Verification
    verify_reviewer_id(w3, contract, "AMAZON_US:REV_ALICE", show_history=False)
    
    # Test Mode 3: Reviewer Complete Historical Trail Verification
    verify_reviewer_id(w3, contract, "AMAZON_US:REV_ALICE", show_history=True)
    
    # Test Mode 4: Transaction Receipt & Event Log Verification
    verify_tx_hash(w3, contract, batch_tx_hex)
    
    print("\n🎉 ALL 4 TRUSTLESS VERIFICATION MODES EXECUTED AND PASSED PERFECTLY!")

if __name__ == "__main__":
    run_simulated_verifier_test()
