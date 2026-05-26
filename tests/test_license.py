"""Ed25519 license verification — round-trip with a freshly generated key."""
from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _sign_blob(priv: Ed25519PrivateKey, payload: dict) -> str:
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig_bytes = priv.sign(payload_bytes)
    return (
        base64.urlsafe_b64encode(payload_bytes).decode("ascii")
        + "."
        + base64.urlsafe_b64encode(sig_bytes).decode("ascii")
    )


@pytest.fixture
def fresh_keypair(monkeypatch):
    """Generate Ed25519 keys + patch the module-level public key in place."""
    from gamepad_midi_bridge import license as license_mod

    priv = Ed25519PrivateKey.generate()
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setattr(license_mod, "PUBLIC_KEY_PEM", pub_pem)
    return priv


def test_valid_pro_license_activates(tmp_user_data, fresh_keypair):
    from gamepad_midi_bridge import license as license_mod

    blob = _sign_blob(fresh_keypair, {
        "email": "test@example.com",
        "tier": "pro",
        "issued_at": "2026-05-26T00:00:00+00:00",
    })
    state = license_mod.activate_from_string(blob)
    assert state.is_pro is True
    assert state.email == "test@example.com"
    assert license_mod.is_pro() is True
    assert license_mod.state().email == "test@example.com"


def test_tampered_blob_fails(tmp_user_data, fresh_keypair):
    """Flipping a payload byte must break the signature."""
    from gamepad_midi_bridge import license as license_mod

    blob = _sign_blob(fresh_keypair, {
        "email": "test@example.com",
        "tier": "pro",
        "issued_at": "2026-05-26T00:00:00+00:00",
    })
    payload_b64, sig_b64 = blob.split(".")
    payload_bytes = base64.urlsafe_b64decode(payload_b64.encode("ascii"))
    # Swap the email to something else; signature was for the original.
    tampered = json.loads(payload_bytes.decode("utf-8"))
    tampered["email"] = "attacker@example.com"
    tampered_payload = json.dumps(tampered, separators=(",", ":")).encode("utf-8")
    tampered_blob = (
        base64.urlsafe_b64encode(tampered_payload).decode("ascii") + "." + sig_b64
    )
    state = license_mod.activate_from_string(tampered_blob)
    assert state.is_pro is False
    assert state.reason == "Signature invalid"


def test_wrong_tier_rejected(tmp_user_data, fresh_keypair):
    """A correctly-signed 'free' tier blob must not unlock Pro."""
    from gamepad_midi_bridge import license as license_mod

    blob = _sign_blob(fresh_keypair, {
        "email": "test@example.com",
        "tier": "free",
        "issued_at": "2026-05-26T00:00:00+00:00",
    })
    state = license_mod.activate_from_string(blob)
    assert state.is_pro is False
    assert state.reason == "Wrong tier"


def test_no_license_installed(tmp_user_data, fresh_keypair):
    from gamepad_midi_bridge import license as license_mod

    # Ensure no license file exists.
    p = license_mod.license_path()
    if p.exists():
        p.unlink()
    license_mod._cached_state = None
    state = license_mod.state()
    assert state.is_pro is False
    assert state.reason == "No license installed"


def test_deactivate_removes_license(tmp_user_data, fresh_keypair):
    from gamepad_midi_bridge import license as license_mod

    blob = _sign_blob(fresh_keypair, {
        "email": "test@example.com",
        "tier": "pro",
        "issued_at": "2026-05-26T00:00:00+00:00",
    })
    license_mod.activate_from_string(blob)
    assert license_mod.is_pro() is True
    license_mod.deactivate()
    assert license_mod.is_pro() is False
    assert not license_mod.license_path().exists()


def test_feature_gating(tmp_user_data, fresh_keypair):
    from gamepad_midi_bridge import license as license_mod

    # Free user — pro features locked, non-pro features open.
    license_mod._cached_state = None
    assert license_mod.feature_enabled("anything_unlisted") is True
    assert license_mod.feature_enabled("mapping_editor") is False

    blob = _sign_blob(fresh_keypair, {
        "email": "test@example.com",
        "tier": "pro",
        "issued_at": "2026-05-26T00:00:00+00:00",
    })
    license_mod.activate_from_string(blob)
    assert license_mod.feature_enabled("mapping_editor") is True
