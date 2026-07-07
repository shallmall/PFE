import sys
from web3 import Web3
from eth_account import Account
import solcx

# Ensure compiler is available
try:
    solcx.install_solc("0.8.19")
except Exception:
    pass

def test_alastria_live():
    print("═" * 70)
    print("  Testing Live Alastria Network Connection & Zero-Gas Deployment")
    print("═" * 70)

    # 1. Generate local keypair
    account = Account.create()
    print(f"\n🔑 1. Generated Autonomous Local Keypair:")
    print(f"   • Public Address : {account.address}")
    print(f"   • Private Key    : {account.key.hex()[:10]}... (kept local)")

    # 2. Test RPC Endpoints
    rpc_urls = [
        "http://serezade.ujaen.es:8030/art/alastria",
        "http://sinbad2.ujaen.es:8012"
    ]

    active_w3 = None
    active_url = None

    print("\n🌐 2. Probing Alastria University RPC Endpoints:")
    for url in rpc_urls:
        w3 = Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 5}))
        try:
            if w3.is_connected():
                chain_id = w3.eth.chain_id
                block_num = w3.eth.block_number
                print(f"   ✅ CONNECTED to {url} | Chain ID: {chain_id} | Latest Block: {block_num:,}")
                active_w3 = w3
                active_url = url
                break
            else:
                print(f"   ❌ Failed connection to {url}")
        except Exception as e:
            print(f"   ❌ Error connecting to {url}: {e}")

    if not active_w3:
        print("\n⚠️ Neither Alastria UJA RPC node is currently reachable from this machine (may require UJA VPN or specific firewall access).")
        return

    # 3. Compile ReputationLedger.sol
    print("\n🛠️ 3. Compiling ReputationLedger.sol...")
    with open("Deployment/ReputationLedger.sol", "r", encoding="utf-8") as f:
        source = f.read()

    compiled = solcx.compile_source(
        source,
        output_values=["abi", "bin"],
        solc_version="0.8.19"
    )
    contract_id, contract_interface = compiled.popitem()
    abi = contract_interface["abi"]
    bytecode = contract_interface["bin"]

    # 4. Attempt Zero-Gas Deployment
    print(f"\n🚀 4. Attempting Zero-Gas Deployment on {active_url}...")
    contract = active_w3.eth.contract(abi=abi, bytecode=bytecode)
    
    try:
        nonce = active_w3.eth.get_transaction_count(account.address)
        tx = contract.constructor().build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': 3000000,
            'gasPrice': 0, # Explicitly zero gas for Alastria consortium
            'chainId': active_w3.eth.chain_id
        })

        signed_tx = active_w3.eth.account.sign_transaction(tx, private_key=account.key)
        tx_hash = active_w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"   🎉 SUCCESS! Broadcasted deployment transaction! Hash: {tx_hash.hex()}")
    except Exception as e:
        err_msg = str(e)
        print(f"   🛑 Deployment Rejected by Node: {err_msg}")
        if "unauthorized" in err_msg.lower() or "permission" in err_msg.lower() or "whitelist" in err_msg.lower() or "insufficient funds" in err_msg.lower() or "gas" in err_msg.lower():
            print("\n" + "═"*70)
            print("🔍 DIAGNOSIS: Node-Level Account Whitelisting Required")
            print("   As the other AI explained, despite gasPrice = 0, this Alastria permissioned")
            print("   node enforces an account-level whitelist for broadcasting transactions.")
            print("   -> Action needed: Send the generated Public Address to your UJA node administrator")
            print(f"      to be whitelisted: {account.address}")
            print("═"*70)

if __name__ == "__main__":
    test_alastria_live()
