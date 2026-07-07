"""
Manual SQL Submitter Registration Utility
Allows administrators to manually register or update enterprise submitters with secret API keys and public keys in the local database.
"""
import sys
import os
import argparse
from sqlalchemy.orm import Session

# Add Deployment directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import SessionLocal, engine, Base
from database.models import Submitter

def register_submitter(submitter_id: str, name: str, secret_key: str, public_key: str = None, is_active: bool = True):
    db: Session = SessionLocal()
    try:
        sub = db.query(Submitter).filter(Submitter.submitter_id == submitter_id).first()
        if sub:
            print(f"[*] Updating existing submitter: {submitter_id}")
            sub.name = name
            sub.api_key = secret_key
            if public_key:
                sub.public_key = public_key
            sub.is_active = is_active
        else:
            print(f"[*] Registering new submitter: {submitter_id}")
            sub = Submitter(
                submitter_id=submitter_id,
                name=name,
                api_key=secret_key,
                public_key=public_key or f"0x{submitter_id}PublicKey00001",
                is_active=is_active
            )
            db.add(sub)
        db.commit()
        print(f"[+] Successfully saved submitter '{submitter_id}' (is_active={sub.is_active}) to SQL database!")
    except Exception as e:
        db.rollback()
        print(f"[-] Error saving submitter: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manually register an enterprise submitter in SQL database")
    parser.add_argument("--id", default="AMAZON_US", help="Submitter ID (e.g. AMAZON_US)")
    parser.add_argument("--name", default="Amazon US Platform", help="Submitter Name")
    parser.add_argument("--key", default="key_amazon_12345", help="Secret API Key / HMAC Key")
    parser.add_argument("--pubkey", default="0xAmazonPublicKey00000000000000000000001", help="Public Key / Ethereum Address")
    parser.add_argument("--inactive", action="store_true", help="Set account as inactive")
    
    args = parser.parse_args()
    register_submitter(args.id, args.name, args.key, args.pubkey, not args.inactive)
