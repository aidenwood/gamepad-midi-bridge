"""Issuer-side helpers — keep the private key OFF the user's machine.

Workflow:
    python scripts/generate_license.py keygen
        -> writes private_key.pem (keep secret) and public_key.pem
        -> paste public_key.pem contents into src/gamepad_midi_bridge/license.py
           as PUBLIC_KEY_PEM
        -> paste private_key.pem into Netlify env as LICENSE_PRIVATE_KEY_PEM
           (mark as a secret — sensitive variable)

    python scripts/generate_license.py keygen --test
        -> writes private_key.test.pem + public_key.test.pem
        -> SEPARATE keypair from the production one. Used to test the Stripe
           webhook flow locally without ever putting the prod private key
           on your laptop. The test public key goes into license.py temporarily
           when you're testing, OR into a debug build.

    python scripts/generate_license.py sign --email buyer@example.com
        -> prints the license blob to deliver to the buyer

    python scripts/generate_license.py sign --email buyer@example.com --test
        -> signs with the TEST private key (matching --test keygen above)

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


SCRIPTS_DIR = Path(__file__).parent


def _paths(test: bool) -> tuple[Path, Path]:
    """Return (private, public) PEM paths, picking the test or prod set."""
    if test:
        return (
            SCRIPTS_DIR / "private_key.test.pem",
            SCRIPTS_DIR / "public_key.test.pem",
        )
    return (
        SCRIPTS_DIR / "private_key.pem",
        SCRIPTS_DIR / "public_key.pem",
    )


def keygen(test: bool = False) -> None:
    priv_path, pub_path = _paths(test)
    if priv_path.exists():
        print(f"Refusing to overwrite {priv_path}. Move it aside first.")
        sys.exit(1)

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()

    priv_path.write_bytes(priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    pub_path.write_bytes(pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ))

    if test:
        print(f"Wrote {priv_path} (TEST private key — local dev only, not for production)")
        print(f"Wrote {pub_path}  (TEST public key — use in dev builds or local Netlify)")
        print()
        print("To wire this up for local Stripe testing:")
        print(f"  1. Copy {priv_path} contents into PS5-MIDI-Bridge-Store/.env as LICENSE_PRIVATE_KEY_PEM")
        print(f"  2. Copy {pub_path} contents into license.py PUBLIC_KEY_PEM ONLY while you're testing.")
        print(f"     Don't commit this swap — revert before deploying.")
    else:
        print(f"Wrote {priv_path} (SECRET — store offline, paste into Netlify as LICENSE_PRIVATE_KEY_PEM)")
        print(f"Wrote {pub_path}  (embed in license.py PUBLIC_KEY_PEM)")


def sign(email: str, tier: str = "pro", test: bool = False) -> None:
    priv_path, _ = _paths(test)
    if not priv_path.exists():
        flag = " --test" if test else ""
        print(f"No private key at {priv_path}. Run 'keygen{flag}' first.")
        sys.exit(1)

    priv = serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
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

    keygen_p = sub.add_parser("keygen", help="Generate a fresh Ed25519 keypair.")
    keygen_p.add_argument(
        "--test",
        action="store_true",
        help="Write to private_key.test.pem + public_key.test.pem (local dev only). "
             "Use this for testing the Stripe webhook locally without exposing the production private key.",
    )

    sign_p = sub.add_parser("sign", help="Sign a license blob for one email.")
    sign_p.add_argument("--email", required=True)
    sign_p.add_argument("--tier", default="pro")
    sign_p.add_argument(
        "--test",
        action="store_true",
        help="Sign with the test private key (private_key.test.pem).",
    )

    args = parser.parse_args()
    if args.cmd == "keygen":
        keygen(test=args.test)
    elif args.cmd == "sign":
        sign(args.email, args.tier, test=args.test)


if __name__ == "__main__":
    main()
