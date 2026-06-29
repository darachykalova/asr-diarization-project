import argparse
import hashlib
import os
import secrets
import sys


sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from database.models import ApiKey
from database.session import SessionLocal


def create_key(
    scopes: str = "read,write",
    rate_limit: int = 100
) -> str:
    raw_key = secrets.token_urlsafe(32)

    key_hash = hashlib.sha256(
        raw_key.encode("utf-8")
    ).hexdigest()

    db = SessionLocal()

    try:
        api_key = ApiKey(
            key_hash=key_hash,
            scopes=scopes,
            rate_limit=rate_limit
        )

        db.add(api_key)
        db.commit()
        db.refresh(api_key)

        print()
        print("API key created")
        print(f"ID: {api_key.id}")
        print(f"Scopes: {api_key.scopes}")
        print(f"Rate limit: {api_key.rate_limit}")
        print()
        print("Save this key now. It will not be shown again:")
        print()
        print(raw_key)
        print()
        print("Use it like this:")
        print(f"Authorization: Bearer {raw_key}")
        print()

        return raw_key

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create API key"
    )

    parser.add_argument(
        "--scopes",
        default="read,write",
        help="Comma-separated scopes: read, write, admin"
    )

    parser.add_argument(
        "--rate-limit",
        type=int,
        default=100,
        help="Requests per minute"
    )

    args = parser.parse_args()

    create_key(
        scopes=args.scopes,
        rate_limit=args.rate_limit
    )
