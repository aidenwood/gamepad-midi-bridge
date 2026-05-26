"""Issuer-side helpers — keep the private key OFF the user's machine.

Workflow:
    python scripts/generate_license.py keygen
        -> writes private_key.pem (keep secret) and public_key.pem
        -> paste public_key.pem contents into src/gamepad_midi_bridge/license.py
           as PUBLIC_KEY_PEM

    python scripts/generate_license.py sign --email buyer@example.com
        -> prints the license blob to deliver to the buyer

The buyer pastes the blob into the app's "Enter license key" dialog.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


PRIVATE_PATH = Path(__file__).parent / "private_key.pem"
PUBLIC_PATH = Path(__file__).parent / "public_key.pem"


def keygen() -> None:
    if PRIVATE_PATH.exists():
        print(f"Refusing to overwrite {PRIVATE_PATH}. Move it aside first.")
        sys.exit(1)
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()

    PRIVATE_PATH.write_bytes(priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    PUBLIC_PATH.write_bytes(pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    print(f"Wrote {PRIVATE_PATH} (SECRET — store offline)")
    print(f"Wrote {PUBLIC_PATH}  (embed in license.py)")


def sign(email: str, tier: str = "pro") -> None:
    if not PRIVATE_PATH.exists():
        print(f"No private key at {PRIVATE_PATH}. Run 'keygen' first.")
        sys.exit(1)
    priv = serialization.load_pem_private_key(
        PRIVATE_PATH.read_bytes(), password=None
    )
    payload = {
        "email": email,
        "tier": tier,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig_bytes = priv.sign(payload_bytes)
    blob = (
        base64.urlsafe_b64encode(payload_bytes).decode("ascii")
        + "."
        + base64.urlsafe_b64encode(sig_bytes).decode("ascii")
    )
    print(blob)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("keygen")

    sign_p = sub.add_parser("sign")
    sign_p.add_argument("--email", required=True)
    sign_p.add_argument("--tier", default="pro")

    args = parser.parse_args()
    if args.cmd == "keygen":
        keygen()
    elif args.cmd == "sign":
        sign(args.email, args.tier)


if __name__ == "__main__":
    main()
