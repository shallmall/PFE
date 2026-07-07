import sys
import time
from web3 import Web3
from eth_account import Account
import solcx

# Ensure compiler is available
try:
    solcx.install_solc("0.8.19")
except Exception:
    pass

def run_live_alastria_transactions():
    print("═" * 70)
    print("  Executing Live Real-World Transactions on Alastria-B Blockchain")
    print("═" * 70)

    # 1. Connect to live Alastria node
    rpc_url = "http://sinbad2.ujaen.es:8012"
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 10}))
    
    if not w3.is_connected():
        print(f"❌ Failed to connect to {rpc_url}")
        return

    print(f"\n✅ Connected to Alastria Node ({rpc_url}) | Chain ID: {w3.eth.chain_id} | Block: {w3.eth.block_number:,}")

    # 2. Generate local deployer wallet
    account = Account.create()
    print(f"\n🔑 Autonomous Deployer Account Created:")
    print(f"   • Address : {account.address}")

    # 3. Compile Contract
    print("\n🛠️ Compiling ReputationLedger.sol...")
    with open("Deployment/ReputationLedger.sol", "r", encoding="utf-8") as f:
        source = f.read()

    compiled = solcx.compile_source(source, output_values=["abi", "bin"], solc_version="0.8.19")
    _, contract_interface = compiled.popitem()
    abi = contract_interface["abi"]
    bytecode = contract_interface["bin"]

    # 4. Deploy Live Contract with 0 Gas Price
    print("\n🚀 Deploying ReputationLedger to Live Alastria Network...")
    contract_cls = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.get_transaction_count(account.address)
    
    deploy_tx = contract_cls.constructor().build_transaction({
        'from': account.address,
        'nonce': nonce,
        'gas': 3000000,
        'gasPrice': 0,
        'chainId': w3.eth.chain_id
    })

    signed_deploy = w3.eth.account.sign_transaction(deploy_tx, private_key=account.key)
    deploy_hash = w3.eth.send_raw_transaction(signed_deploy.raw_transaction)
    print(f"   ⏳ Broadcasted deploy TX: {deploy_hash.hex()}. Waiting for block confirmation...")
    
    deploy_receipt = w3.eth.wait_for_transaction_receipt(deploy_hash)
    contract_address = deploy_receipt['contractAddress']
    print(f"   🎉 CONTRACT MINED ON ALASTRIA! Address: {contract_address}")
    print(f"   • Block Number : {deploy_receipt['blockNumber']:,}")
    print(f"   • Gas Used     : {deploy_receipt['gasUsed']:,} (Cost: 0 Wei)")

    # 5. Send Real Live Reputation Score Transactions
    contract = w3.eth.contract(address=contract_address, abi=abi)

    # Let's define some real entities
    # Entity A: Product ASIN_B08N5WRWNW (Keccak ID)
    prod_id_hex = "0x11112222333344445555666677778888"
    prod_bytes16 = bytes.fromhex(prod_id_hex[2:])

    # Entity B: Reviewer User usr_genuine_001 (Keccak ID)
    rev_id_hex = "0x99998888777766665555444433332222"
    rev_bytes16 = bytes.fromhex(rev_id_hex[2:])

    transactions_to_send = [
        {"desc": "Initial Product Score Evaluation", "entity": prod_bytes16, "hex": prod_id_hex, "bit": 0, "score": 92},
        {"desc": "Initial Reviewer Reputation", "entity": rev_bytes16, "hex": rev_id_hex, "bit": 1, "score": 85},
        {"desc": "Updated Product Score (After 2nd review)", "entity": prod_bytes16, "hex": prod_id_hex, "bit": 0, "score": 95},
    ]

    print("\n── Broadcasting Live Score Updates to Alastria Blockchain ────────")
    nonce = w3.eth.get_transaction_count(account.address)

    for idx, item in enumerate(transactions_to_send, 1):
        tx = contract.functions.addRecord(item["entity"], item["bit"], item["score"]).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': 500000,
            'gasPrice': 0,
            'chainId': w3.eth.chain_id
        })
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=account.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        nonce += 1 # Increment nonce for sequential mining
        
        print(f"   [{idx}/3] {item['desc']}")
        print(f"         • Target Entity : {item['hex']} (Bit: {item['bit']}) | Score: {item['score']}")
        print(f"         • TX Hash       : {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"         ✅ Confirmed in Block #{receipt['blockNumber']:,} (Gas Used: {receipt['gasUsed']:,})\n")
        time.sleep(1.0) # Small pause between mining confirmations

    # 6. Verify Live On-Chain State by Querying Contract
    print("── Reading Live On-Chain Data Back From Alastria Blockchain ──────")
    total_records = contract.functions.getTotalRecordsCount().call({'from': account.address})
    latest_prod_score = contract.functions.getEntityScore(prod_bytes16, 0).call({'from': account.address})
    latest_rev_score = contract.functions.getEntityScore(rev_bytes16, 1).call({'from': account.address})
    prod_history = contract.functions.getEntityHistory(prod_bytes16, 0).call({'from': account.address})

    import datetime
    print(f"   • Total Tracked Entities on Contract : {total_records}")
    print(f"   • Live Product Latest Score On-Chain : {latest_prod_score[3]} / 100 (Recorded at {datetime.datetime.fromtimestamp(latest_prod_score[1], datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')})")
    print(f"   • Live Reviewer Latest Score On-Chain: {latest_rev_score[3]} / 100 (Recorded at {datetime.datetime.fromtimestamp(latest_rev_score[1], datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')})")
    print(f"   • Live Product Historical Evaluation Trail ({len(prod_history)} points mined on-chain):")
    for h in prod_history:
        readable = datetime.datetime.fromtimestamp(h[1], datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
        print(f"     -> [Entity: 0x{h[0].hex()}] Timestamp: {readable} | Mined AI Score: {h[3]}")

    print("\n══════════════════════════════════════════════════════════════════════")
    print(f"🎉 SUCCESS! All scores permanently sealed on Alastria contract: {contract_address}")
    print("══════════════════════════════════════════════════════════════════════")

if __name__ == "__main__":
    run_live_alastria_transactions()
