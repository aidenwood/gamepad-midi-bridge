"""Free/Pro feature gating with offline-activation hooks.

V1 ships with `is_pro()` always returning False — Pro panels are visible but
locked behind an upgrade dialog. The Ed25519 verification path is wired up so
a purchase flow can drop in later without touching the UI layer.

Issuing keys (issuer-side, kept off the user's machine):
    1. Generate one keypair with scripts/generate_license.py — embed the
       PUBLIC key as PUBLIC_KEY_PEM below. NEVER ship the private key.
    2. For each sale, sign the buyer's email with the private key. Distribute
       the signed payload as the license.

The signed payload is JSON: {"email": "...", "tier": "pro", "issued_at": "..."}
followed by an Ed25519 signature.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set

from .paths import license_path

# TEST public key (matches scripts/public_key.test.pem + private_key.test.pem).
# Used for dev / local testing of the license-activate flow. Swap for the
# production public key before tagging v2.0.0 — paste contents of
# scripts/public_key.pem here.
PUBLIC_KEY_PEM: bytes = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEANE5ihyMUoHerpfxmquOtXLwjrj5d/9V+7dzny4O5krY=
-----END PUBLIC KEY-----
"""


PRO_FEATURES: Set[str] = {
    "mapping_editor",
    "presets",
    "multi_controller",  # reserved for v1.1
    "osc_output",        # reserved for v1.1
}


@dataclass
class LicenseState:
    is_pro: bool
    email: Optional[str] = None
    reason: Optional[str] = None   # populated when verification fails


_cached_state: Optional[LicenseState] = None


def state() -> LicenseState:
    global _cached_state
    if _cached_state is not None:
        return _cached_state
    _cached_state = _load_and_verify()
    return _cached_state


def is_pro() -> bool:
    # TESTING UNLOCK — all Pro features open during the PS5 controller
    # bring-up. Revert this line to `return state().is_pro` before any
    # release build goes out, otherwise the signed-license gate is bypassed.
    return True


def feature_enabled(feature: str) -> bool:
    if feature not in PRO_FEATURES:
        return True
    return is_pro()


def activate_from_string(blob: str) -> LicenseState:
    """Write a license string to disk and re-verify. Returns the new state."""
    global _cached_state
    license_path().write_text(blob.strip(), encoding="utf-8")
    _cached_state = _load_and_verify()
    return _cached_state


def deactivate() -> None:
    global _cached_state
    p = license_path()
    if p.exists():
        p.unlink()
    _cached_state = LicenseState(is_pro=False)


# --------------------------------------------------------------------- internals


def _load_and_verify() -> LicenseState:
    path = license_path()
    if not path.exists():
        return LicenseState(is_pro=False, reason="No license installed")
    try:
        blob = path.read_text(encoding="utf-8").strip()
        payload_b64, sig_b64 = blob.split(".")
        payload_bytes = base64.urlsafe_b64decode(payload_b64.encode("ascii"))
        sig_bytes = base64.urlsafe_b64decode(sig_b64.encode("ascii"))
        payload = json.loads(payload_bytes.decode("utf-8"))
        if not _verify_signature(payload_bytes, sig_bytes):
            return LicenseState(is_pro=False, reason="Signature invalid")
        if payload.get("tier") != "pro":
            return LicenseState(is_pro=False, reason="Wrong tier")
        return LicenseState(is_pro=True, email=payload.get("email"))
    except Exception as e:
        return LicenseState(is_pro=False, reason=f"License unreadable: {e}")


def _verify_signature(payload_bytes: bytes, sig_bytes: bytes) -> bool:
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.exceptions import InvalidSignature

        pub = load_pem_public_key(PUBLIC_KEY_PEM)
        try:
            pub.verify(sig_bytes, payload_bytes)
            return True
        except InvalidSignature:
            return False
    except Exception:
        # Placeholder public key / cryptography missing — fail closed.
        return False
