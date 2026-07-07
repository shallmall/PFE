import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3

# Load environment variables
load_dotenv()

ALASTRIA_RPC_URL = os.getenv("ALASTRIA_RPC_URL", "http://serezade.ujaen.es:8030/art/alastria")
ALASTRIA_PRIVATE_KEY = os.getenv("ALASTRIA_PRIVATE_KEY", "")

def deploy():
    print("══════════════════════════════════════════════════════════════════════")
    print("  Alastria Red T Smart Contract Deployment Utility")
    print("══════════════════════════════════════════════════════════════════════")

    if not ALASTRIA_PRIVATE_KEY:
        print("❌ Error: ALASTRIA_PRIVATE_KEY is missing in .env file.")
        print("Please paste your Alastria wallet private key into Deployment/.env and re-run.")
        sys.exit(1)

    # Try installing/importing solcx for compilation
    try:
        import solcx
        print("📦 Verifying Solidity compiler (v0.8.19 - Pre-PUSH0 Alastria target)...")
        try:
            solcx.install_solc("0.8.19")
        except Exception:
            pass
        solcx.set_solc_version("0.8.19")
        
        contract_path = Path(__file__).parent / "ReputationLedger.sol"
        print(f"🔨 Compiling {contract_path.name}...")
        compiled_sol = solcx.compile_files(
            [str(contract_path)],
            output_values=["abi", "bin"]
        )
        contract_key = next(k for k in compiled_sol.keys() if "ReputationLedger" in k)
        contract_interface = compiled_sol[contract_key]
        abi = contract_interface["abi"]
        bytecode = contract_interface["bin"]
        
        # Save compiled ABI to disk for reference
        abi_path = Path(__file__).parent / "ReputationLedger.json"
        with open(abi_path, "w") as f:
            json.dump(abi, f, indent=4)
        print(f"✅ Compiled ABI saved to {abi_path.name}")

    except ImportError:
        print("⚠️ 'py-solc-x' is not installed. To compile Solidity automatically, run:")
        print("    pip install py-solc-x")
        sys.exit(1)

    # Connect to Web3
    w3 = Web3(Web3.HTTPProvider(ALASTRIA_RPC_URL))
    if not w3.is_connected():
        print(f"❌ Could not connect to Alastria RPC at {ALASTRIA_RPC_URL}")
        sys.exit(1)

    account = w3.eth.account.from_key(ALASTRIA_PRIVATE_KEY)
    print(f"🔗 Connected to Alastria Red T. Deployer wallet: {account.address}")

    # Build deployment tx
    ReputationLedger = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.get_transaction_count(account.address)
    
    print("🚀 Constructing deployment transaction...")
    tx = ReputationLedger.constructor().build_transaction({
        'chainId': 2020, # Alastria Red T
        'gas': 1500000,
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
    })

    # Sign and send
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=ALASTRIA_PRIVATE_KEY)
    tx_hash_bytes = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    tx_hex = w3.to_hex(tx_hash_bytes)
    
    print(f"⏳ Deployment transaction broadcasted! TX Hash: {tx_hex}")
    print("⏳ Waiting for Alastria validators to confirm block receipt...")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=60)
    contract_address = receipt.contractAddress
    
    print("\n🎉 SUCCESS! ReputationLedger deployed to Alastria Red T!")
    print("══════════════════════════════════════════════════════════════════════")
    print(f"📍 Contract Address: {contract_address}")
    print("══════════════════════════════════════════════════════════════════════")
    print("\n👉 NEXT STEP: Copy the address above and paste it into your Deployment/.env file:")
    print(f"ALASTRIA_CONTRACT_ADDRESS={contract_address}\n")

if __name__ == "__main__":
    deploy()
