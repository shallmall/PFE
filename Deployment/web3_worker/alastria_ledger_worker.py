import os
import sys
import time
import hashlib
import argparse
from datetime import datetime, timezone
from typing import List, Tuple

# Ensure stdout encoding on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add parent directory to path to import database modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import solcx
    from web3 import Web3
    from web3.exceptions import Web3Exception
    from eth_account import Account
    from sqlalchemy.orm import Session
    from database.db import SessionLocal, engine, Base
    from database.models import Review, Reviewer, Product, Submitter
except ImportError as e:
    print(f"❌ Missing import: {e}")
    print("Please run: uv pip install py-solc-x web3 eth-account sqlalchemy")
    sys.exit(1)

# Ensure database tables exist
Base.metadata.create_all(bind=engine)

ALASTRIA_ENDPOINTS = [
    "http://sinbad2.ujaen.es:8012",
    "http://serezade.ujaen.es:8030/art/alastria"
]

def get_keccak_bytes16(universal_id: str) -> bytes:
    """Converts a Universal ID (16-byte hex hash or string format) into exact bytes16 for EVM."""
    if universal_id.startswith("0x") and len(universal_id) == 34:
        try:
            return bytes.fromhex(universal_id[2:])
        except ValueError:
            pass
    if len(universal_id) == 32 and not ":" in universal_id:
        try:
            return bytes.fromhex(universal_id)
        except ValueError:
            pass
    return hashlib.sha256(universal_id.encode('utf-8')).digest()[:16]

def scale_score_uint8(score: float) -> int:
    """Scales float score (0.00-1.00 or 0-100) to integer 0-100."""
    if score is None:
        return 0
    if score <= 1.0:
        val = int(round(score * 100))
    else:
        val = int(round(score))
    return max(0, min(val, 100))

def connect_web3(simulated: bool = False) -> Tuple[Web3, str]:
    """Connects to Alastria live nodes or simulated local provider."""
    if simulated:
        print("⚡ Connecting to Simulated Web3 EthereumTesterProvider...")
        try:
            from web3.providers.eth_tester import EthereumTesterProvider
            w3 = Web3(EthereumTesterProvider())
            return w3, "Simulated-EthTester"
        except Exception as e:
            print(f"⚠️ Could not start EthereumTesterProvider: {e}")
            print("Falling back to local HTTP provider http://127.0.0.1:8545...")
            w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
            return w3, "Local-8545"

    for rpc_url in ALASTRIA_ENDPOINTS:
        print(f"🌐 Attempting connection to Alastria Red T node: {rpc_url}...")
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 8}))
            if w3.is_connected():
                chain_id = w3.eth.chain_id
                block_num = w3.eth.block_number
                print(f"✅ Connected to {rpc_url}! | Chain ID: {chain_id} | Live Block: {block_num:,}")
                return w3, rpc_url
        except Exception as e:
            print(f"⚠️ Could not connect to {rpc_url}: {e}")
    
    print("\n❌ All Alastria live nodes unreachable! Falling back to simulated EthereumTesterProvider...")
    from web3.providers.eth_tester import EthereumTesterProvider
    w3 = Web3(EthereumTesterProvider())
    return w3, "Simulated-EthTester-Fallback"

def load_or_compile_contract(w3: Web3, deployer_account, contract_address: str = None):
    """Compiles ReputationLedger.sol and deploys if address is not provided."""
    try:
        solcx.install_solc("0.8.19")
    except Exception:
        pass

    contract_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ReputationLedger.sol")
    if not os.path.exists(contract_path):
        raise FileNotFoundError(f"Contract file not found at {contract_path}")

    with open(contract_path, "r", encoding="utf-8") as f:
        source = f.read()

    compiled = solcx.compile_source(source, output_values=["abi", "bin"], solc_version="0.8.19")
    _, contract_interface = compiled.popitem()
    abi = contract_interface["abi"]
    bytecode = contract_interface["bin"]

    if contract_address and w3.is_address(contract_address):
        print(f"📄 Using existing contract at address: {contract_address}")
        return w3.eth.contract(address=contract_address, abi=abi)

    print("🚀 Deploying ReputationLedger contract with gasPrice = 0...")
    contract_cls = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    # Handle simulated vs live deploy
    if hasattr(w3.provider, 'ethereum_tester') or (w3.eth.accounts and deployer_account.address in w3.eth.accounts):
        tx_hash = contract_cls.constructor().transact({'from': deployer_account.address})
    else:
        nonce = w3.eth.get_transaction_count(deployer_account.address)
        deploy_tx = contract_cls.constructor().build_transaction({
            'from': deployer_account.address,
            'nonce': nonce,
            'gas': 3000000,
            'gasPrice': 0,
            'chainId': w3.eth.chain_id
        })
        signed_deploy = w3.eth.account.sign_transaction(deploy_tx, private_key=deployer_account.key)
        tx_hash = w3.eth.send_raw_transaction(signed_deploy.raw_transaction)

    print(f"   ⏳ Broadcasted deploy TX: {tx_hash.hex()}. Waiting for mining confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    address = receipt.contractAddress
    print(f"   🎉 CONTRACT MINED! Address: {address} | Gas Used: {receipt.gasUsed:,}")
    return w3.eth.contract(address=address, abi=abi)

def sync_pending_reviews(db: Session, w3: Web3, contract, account, batch_limit: int = 100) -> int:
    """
    Sweeps un-anchored reviews from SQL database and anchors them on-chain using saveReviewBatch.
    Only completes the off-chain database write to 'Confirmed_OnChain' AFTER receiving blockchain receipt!
    """
    pending = (
        db.query(Review)
        .filter(Review.status.in_(["Confirmed_OffChain", "Confirmed", "Pending_Ledger"]))
        .limit(batch_limit)
        .all()
    )

    if not pending:
        return 0

    print(f"\n📦 Found {len(pending)} un-anchored reviews in database! Preparing Web3 batch transaction...")

    review_ids_16 = []
    reviewer_ids_16 = []
    review_scores_8 = []
    reviewer_scores_8 = []

    for r in pending:
        review_ids_16.append(get_keccak_bytes16(r.universal_review_id))
        reviewer_ids_16.append(get_keccak_bytes16(r.reviewer_id))
        
        r_score = scale_score_uint8(getattr(r, 'ai_score', 0.0))
        
        # Get reviewer current score or fallback
        rev_score = 0
        if r.reviewer and getattr(r.reviewer, 'current_score', None) is not None:
            rev_score = scale_score_uint8(r.reviewer.current_score)
        else:
            rev_score = r_score
            
        review_scores_8.append(r_score)
        reviewer_scores_8.append(rev_score)

    try:
        if hasattr(w3.provider, 'ethereum_tester') or (w3.eth.accounts and account.address in w3.eth.accounts):
            tx_hash = contract.functions.saveReviewBatch(
                review_ids_16, reviewer_ids_16, review_scores_8, reviewer_scores_8
            ).transact({'from': account.address})
        else:
            nonce = w3.eth.get_transaction_count(account.address)
            tx = contract.functions.saveReviewBatch(
                review_ids_16, reviewer_ids_16, review_scores_8, reviewer_scores_8
            ).build_transaction({
                'from': account.address,
                'nonce': nonce,
                'gas': min(500000 + (len(pending) * 80000), 5000000),
                'gasPrice': 0,
                'chainId': w3.eth.chain_id
            })
            signed_tx = w3.eth.account.sign_transaction(tx, private_key=account.key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        hex_hash = tx_hash.hex()
        if not hex_hash.startswith("0x"):
            hex_hash = "0x" + hex_hash

        print(f"   ⏳ Broadcasted saveReviewBatch ({len(pending)} items) -> Hash: {hex_hash}")
        print("   ⏳ Waiting for block mining receipt...")
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        gas_used = receipt.get('gasUsed', 0)
        block_num = receipt.get('blockNumber', 0)
        print(f"   ✅ TRANSACTION MINED IN BLOCK #{block_num:,}! Gas used: {gas_used:,}")

        # CRITICAL USER REQUIREMENT: Complete the write on local DB ONLY AFTER receipt is received!
        print("   💾 Updating SQL database records to 'Confirmed_OnChain' with immutable receipt hash...")
        for r in pending:
            r.status = "Confirmed_OnChain"
            r.tx_hash = hex_hash
        db.commit()
        print(f"   🎉 Successfully synced {len(pending)} records to blockchain and local DB!")
        return len(pending)

    except Exception as e:
        db.rollback()
        print(f"❌ Error during Web3 transaction broadcast/receipt: {e}")
        return 0

def run_worker_loop(simulated: bool = False, once: bool = False, batch_threshold: int = 50, timer_seconds: int = 600):
    """
    Executes the Alastria Ledger Worker with the Dual Trigger Strategy:
    Triggers whenever EITHER 50 reviews accumulate OR 10 minutes (600s) elapse with >= 1 review waiting.
    """
    print("═" * 70)
    print("  LAYER 4: ALASTRIA ZERO-GAS EVM BLOCKCHAIN SYNC WORKER")
    print("═" * 70)

    w3, endpoint_name = connect_web3(simulated=simulated)

    # Setup deployer account
    if hasattr(w3.provider, 'ethereum_tester'):
        class SimulatedAccount:
            def __init__(self, address):
                self.address = address
                self.key = None
        account = SimulatedAccount(w3.eth.accounts[0])
        w3.eth.default_account = w3.eth.accounts[0]
    else:
        # Create or load autonomous account
        private_key_env = os.getenv("DEPLOYER_PRIVATE_KEY")
        if private_key_env:
            account = Account.from_key(private_key_env)
        else:
            account = Account.create()
            print(f"🔑 Created new Autonomous Deployer Account: {account.address}")

    contract_addr = os.getenv("CONTRACT_ADDRESS")
    contract = load_or_compile_contract(w3, account, contract_address=contract_addr)

    db = SessionLocal()
    last_timer_sync = time.time()

    if once:
        print("\n▶️ Running single immediate sync sweep (--once mode)...")
        synced = sync_pending_reviews(db, w3, contract, account, batch_limit=batch_threshold)
        print(f"🏁 Single sweep complete. Synced: {synced} records.")
        db.close()
        return

    print(f"\n⚙️ Worker Daemon started! Monitoring database via Dual Trigger Strategy:")
    print(f"   • Volume Trigger : {batch_threshold} reviews")
    print(f"   • Timer Trigger  : {timer_seconds // 60} minutes ({timer_seconds}s)")
    print("   Press Ctrl+C to stop.")

    try:
        while True:
            try:
                # Check un-anchored count
                pending_count = (
                    db.query(Review)
                    .filter(Review.status.in_(["Confirmed_OffChain", "Confirmed", "Pending_Ledger"]))
                    .filter((Review.tx_hash == None) | (Review.tx_hash == "") | (~Review.tx_hash.startswith("0x")))
                    .count()
                )

                elapsed = time.time() - last_timer_sync

                # Check Condition 1: Volume Trigger
                if pending_count >= batch_threshold:
                    print(f"\n🔔 [VOLUME TRIGGER] Reached threshold ({pending_count} >= {batch_threshold})!")
                    sync_pending_reviews(db, w3, contract, account, batch_limit=batch_threshold)
                    last_timer_sync = time.time()

                # Check Condition 2: Timer Trigger
                elif elapsed >= timer_seconds:
                    if pending_count > 0:
                        print(f"\n⏰ [TIMER TRIGGER] {int(elapsed)}s elapsed with {pending_count} reviews waiting!")
                        sync_pending_reviews(db, w3, contract, account, batch_limit=batch_threshold)
                    else:
                        # Queue is empty, skip silently!
                        pass
                    last_timer_sync = time.time()

            except Exception as e:
                print(f"⚠️ Worker loop error: {e}")
                db.rollback()

            time.sleep(5.0) # Check database queue every 5 seconds
    except KeyboardInterrupt:
        print("\n🛑 Worker daemon stopped by user.")
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Alastria Zero-Gas Blockchain Ledger Sync Worker")
    parser.add_argument("--simulated", action="store_true", help="Run against simulated EthereumTesterProvider")
    parser.add_argument("--once", action="store_true", help="Run a single immediate sync sweep and exit")
    parser.add_argument("--batch-threshold", type=int, default=50, help="Volume trigger threshold (default: 50)")
    parser.add_argument("--timer-seconds", type=int, default=600, help="Timer trigger threshold in seconds (default: 600s / 10m)")
    args = parser.parse_args()

    run_worker_loop(
        simulated=args.simulated,
        once=args.once,
        batch_threshold=args.batch_threshold,
        timer_seconds=args.timer_seconds
    )
