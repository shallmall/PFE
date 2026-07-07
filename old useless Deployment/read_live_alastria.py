import datetime
from web3 import Web3
import solcx

w3 = Web3(Web3.HTTPProvider('http://sinbad2.ujaen.es:8012'))
with open('Deployment/ReputationLedger.sol', 'r', encoding='utf-8') as f:
    compiled = solcx.compile_source(f.read(), output_values=['abi'], solc_version='0.8.19')
abi = list(compiled.values())[0]['abi']

contract = w3.eth.contract('0x729F000825fBaC462ad694700E51D5C719459bEE', abi=abi)
prod_id = bytes.fromhex('11112222333344445555666677778888')
rev_id = bytes.fromhex('99998888777766665555444433332222')

ps = contract.functions.getEntityScore(prod_id, 0).call()
rs = contract.functions.getEntityScore(rev_id, 1).call()
ph = contract.functions.getEntityHistory(prod_id, 0).call()

print("═" * 70)
print("  LIVE ALASTRIA RED T / ALASTRIA-B ON-CHAIN VERIFICATION")
print("  Contract Address : 0x729F000825fBaC462ad694700E51D5C719459bEE")
print("═" * 70)
print(f"✅ Product Latest On-Chain Score : {ps[3]} / 100 (Recorded at {datetime.datetime.fromtimestamp(ps[1], datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')})")
print(f"✅ Reviewer Latest On-Chain Score: {rs[3]} / 100 (Recorded at {datetime.datetime.fromtimestamp(rs[1], datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')})")
print(f"✅ Product Mined Evolution Trail ({len(ph)} points permanently sealed on Alastria):")
for h in ph:
    t = datetime.datetime.fromtimestamp(h[1], datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"   -> [Entity: 0x{h[0].hex()}] | Timestamp: {t} | Sealed AI Score: {h[3]}")
print("═" * 70)
