"""Free/Pro feature gating via offline Ed25519-signed licences.

Pro panels render an upgrade overlay until `is_pro()` returns True. Activation
happens when the user pastes a licence blob into the settings panel — that
blob is the JSON payload `{"email": ..., "tier": "pro", "issued_at": ...}`
followed by an Ed25519 signature over the payload bytes, base64-url joined
with a `.`. Verification reads `PUBLIC_KEY_PEM` (embedded below); the matching
private key lives in the storefront's Netlify env and never touches this
codebase.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set

from .paths import license_path

# Production Ed25519 public key — matches scripts/public_key.pem. The
# matching private key lives in the storefront's Netlify env (LICENSE_PRIV_KEY_V1)
# and never enters this codebase.
PUBLIC_KEY_PEM: bytes = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEACfeGGd2FvDL7zy5uY87eB9EfAbgzdDC84+p1snjJz8I=
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
    return state().is_pro


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


def _b64url_decode(s: str) -> bytes:
    """urlsafe-base64 decode tolerant of stripped `=` padding.

    The storefront issuer (`src/lib/license.ts`) strips trailing `=` per the
    URL-safe convention in RFC 4648 §5. Python's `urlsafe_b64decode` requires
    the padding, so we re-add it before decoding. Without this, every real
    licence ever issued raises `binascii.Error: Incorrect padding`.
    """
    s = s.strip()
    pad = (-len(s)) % 4
    return base64.urlsafe_b64decode(s + ("=" * pad))


def _load_and_verify() -> LicenseState:
    path = license_path()
    if not path.exists():
        return LicenseState(is_pro=False, reason="No license installed")
    try:
        blob = path.read_text(encoding="utf-8").strip()
        payload_b64, sig_b64 = blob.split(".")
        payload_bytes = _b64url_decode(payload_b64)
        sig_bytes = _b64url_decode(sig_b64)
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
