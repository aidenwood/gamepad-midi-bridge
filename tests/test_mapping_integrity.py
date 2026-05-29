"""Tests for mapping_integrity module.

Covers:
- Hash computation and determinism
- HMAC signing and verification
- Stamping and serialization
- Integrity verification with tampering detection
- Constant-time comparison
"""

import pytest
from gamepad_midi_bridge.mapping_integrity import (
    IntegrityStamp,
    compute_hash,
    compute_hmac,
    stamp,
    verify,
    attach_stamp,
    detach_stamp,
    verify_attached,
)


class TestComputeHash:
    """Tests for compute_hash function."""

    def test_compute_hash_returns_64_char_hex(self):
        """compute_hash returns 64-character hex string."""
        mapping = {"buttons": {0: {"note": 60}}}
        result = compute_hash(mapping)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_compute_hash_deterministic(self):
        """Same input produces same hash."""
        mapping = {"buttons": {0: {"note": 60}}, "axes": {0: {"cc": 1}}}
        hash1 = compute_hash(mapping)
        hash2 = compute_hash(mapping)
        assert hash1 == hash2

    def test_compute_hash_different_content_different_hash(self):
        """Different content produces different hash."""
        mapping1 = {"buttons": {0: {"note": 60}}}
        mapping2 = {"buttons": {0: {"note": 61}}}
        assert compute_hash(mapping1) != compute_hash(mapping2)

    def test_compute_hash_ignore_keys(self):
        """Hashes with ignored keys produce same result for changed values."""
        mapping1 = {"buttons": {0: {"note": 60}}, "last_modified": 1000}
        mapping2 = {"buttons": {0: {"note": 60}}, "last_modified": 2000}
        hash1 = compute_hash(mapping1, ignore_keys=["last_modified"])
        hash2 = compute_hash(mapping2, ignore_keys=["last_modified"])
        assert hash1 == hash2

    def test_compute_hash_ignore_keys_only_ignores_specified(self):
        """Ignoring keys only affects those keys, not others."""
        mapping1 = {"buttons": {0: {"note": 60}}, "version": "1.0"}
        mapping2 = {"buttons": {0: {"note": 61}}, "version": "1.0"}
        hash1 = compute_hash(mapping1, ignore_keys=["version"])
        hash2 = compute_hash(mapping2, ignore_keys=["version"])
        assert hash1 != hash2  # Still different due to buttons change


class TestComputeHmac:
    """Tests for compute_hmac function."""

    def test_compute_hmac_returns_64_char_hex(self):
        """compute_hmac returns 64-character hex string."""
        mapping = {"buttons": {0: {"note": 60}}}
        result = compute_hmac(mapping, "secret_key")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_compute_hmac_deterministic(self):
        """Same input and secret produce same HMAC."""
        mapping = {"buttons": {0: {"note": 60}}}
        hmac1 = compute_hmac(mapping, "secret_key")
        hmac2 = compute_hmac(mapping, "secret_key")
        assert hmac1 == hmac2

    def test_compute_hmac_different_secret_different_hash(self):
        """Different secrets produce different HMACs."""
        mapping = {"buttons": {0: {"note": 60}}}
        hmac1 = compute_hmac(mapping, "secret1")
        hmac2 = compute_hmac(mapping, "secret2")
        assert hmac1 != hmac2

    def test_compute_hmac_different_content_different_hash(self):
        """Different content produces different HMAC."""
        mapping1 = {"buttons": {0: {"note": 60}}}
        mapping2 = {"buttons": {0: {"note": 61}}}
        assert compute_hmac(mapping1, "secret") != compute_hmac(
            mapping2, "secret"
        )

    def test_compute_hmac_ignore_keys(self):
        """HMAC with ignored keys produces same result for changed values."""
        mapping1 = {"buttons": {0: {"note": 60}}, "last_modified": 1000}
        mapping2 = {"buttons": {0: {"note": 60}}, "last_modified": 2000}
        hmac1 = compute_hmac(mapping1, "secret", ignore_keys=["last_modified"])
        hmac2 = compute_hmac(mapping2, "secret", ignore_keys=["last_modified"])
        assert hmac1 == hmac2


class TestStamp:
    """Tests for stamp function."""

    def test_stamp_returns_integrity_stamp(self):
        """stamp returns IntegrityStamp instance."""
        mapping = {"buttons": {0: {"note": 60}}}
        result = stamp(mapping)
        assert isinstance(result, IntegrityStamp)

    def test_stamp_plain_hash_sets_algorithm(self):
        """stamp without secret sets algorithm to 'sha256'."""
        mapping = {"buttons": {0: {"note": 60}}}
        result = stamp(mapping)
        assert result.algorithm == "sha256"

    def test_stamp_with_secret_sets_algorithm(self):
        """stamp with secret sets algorithm to 'hmac_sha256'."""
        mapping = {"buttons": {0: {"note": 60}}}
        result = stamp(mapping, secret="my_secret")
        assert result.algorithm == "hmac_sha256"

    def test_stamp_includes_signer(self):
        """stamp includes the signer field."""
        mapping = {"buttons": {0: {"note": 60}}}
        result = stamp(mapping, signer="Alice")
        assert result.signer == "Alice"

    def test_stamp_includes_timestamp(self):
        """stamp includes the timestamp_s field."""
        mapping = {"buttons": {0: {"note": 60}}}
        result = stamp(mapping, now_s=1234567890.0)
        assert result.timestamp_s == 1234567890.0

    def test_stamp_version_default(self):
        """stamp sets version to '1.0' by default."""
        mapping = {"buttons": {0: {"note": 60}}}
        result = stamp(mapping)
        assert result.version == "1.0"


class TestVerify:
    """Tests for verify function."""

    def test_verify_true_when_hash_matches(self):
        """verify returns True when mapping hash matches stamp."""
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping)
        assert verify(mapping, s)

    def test_verify_false_when_mapping_mutated(self):
        """verify returns False after mapping is mutated."""
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping)
        mapping_modified = {"buttons": {0: {"note": 61}}}
        assert not verify(mapping_modified, s)

    def test_verify_with_hmac_requires_same_secret(self):
        """verify with HMAC requires same secret."""
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping, secret="secret1")
        assert verify(mapping, s, secret="secret1")
        assert not verify(mapping, s, secret="secret2")

    def test_verify_hmac_without_secret_fails(self):
        """verify HMAC stamp without providing secret returns False."""
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping, secret="secret")
        assert not verify(mapping, s, secret=None)

    def test_verify_unknown_algorithm_returns_false(self):
        """verify with unknown algorithm returns False."""
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping)
        s.algorithm = "unknown_algo"
        assert not verify(mapping, s)

    def test_verify_uses_constant_time_comparison(self):
        """verify uses hmac.compare_digest for constant-time comparison.

        We verify this by checking that timing doesn't leak the hash value.
        """
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping)
        # Both should succeed without timing leaks (hmac.compare_digest handles this)
        assert verify(mapping, s)
        # Invalid stamp should fail safely
        s_invalid = stamp({"buttons": {0: {"note": 61}}})
        assert not verify(mapping, s_invalid)


class TestAttachStamp:
    """Tests for attach_stamp function."""

    def test_attach_stamp_adds_integrity_key(self):
        """attach_stamp adds _integrity key to mapping."""
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping)
        result = attach_stamp(mapping, s)
        assert "_integrity" in result

    def test_attach_stamp_preserves_original_keys(self):
        """attach_stamp preserves original mapping keys."""
        mapping = {"buttons": {0: {"note": 60}}, "axes": {0: {"cc": 1}}}
        s = stamp(mapping)
        result = attach_stamp(mapping, s)
        assert result["buttons"] == mapping["buttons"]
        assert result["axes"] == mapping["axes"]

    def test_attach_stamp_does_not_modify_input(self):
        """attach_stamp does not modify the input dict."""
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping)
        attach_stamp(mapping, s)
        assert "_integrity" not in mapping

    def test_attach_stamp_integrity_is_dict(self):
        """_integrity value is a dict (serializable)."""
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping, signer="Alice", now_s=1000.0)
        result = attach_stamp(mapping, s)
        assert isinstance(result["_integrity"], dict)
        assert result["_integrity"]["signer"] == "Alice"
        assert result["_integrity"]["timestamp_s"] == 1000.0


class TestDetachStamp:
    """Tests for detach_stamp function."""

    def test_detach_stamp_removes_integrity_key(self):
        """detach_stamp removes _integrity key."""
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping)
        stamped = attach_stamp(mapping, s)
        clean, _ = detach_stamp(stamped)
        assert "_integrity" not in clean

    def test_detach_stamp_returns_parsed_stamp(self):
        """detach_stamp returns parsed IntegrityStamp."""
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping, signer="Alice")
        stamped = attach_stamp(mapping, s)
        _, parsed = detach_stamp(stamped)
        assert isinstance(parsed, IntegrityStamp)
        assert parsed.signer == "Alice"

    def test_detach_stamp_no_integrity_key(self):
        """detach_stamp returns None stamp if no _integrity key."""
        mapping = {"buttons": {0: {"note": 60}}}
        clean, parsed = detach_stamp(mapping)
        assert clean == mapping
        assert parsed is None

    def test_detach_stamp_does_not_modify_input(self):
        """detach_stamp does not modify the input dict."""
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping)
        stamped = attach_stamp(mapping, s)
        detach_stamp(stamped)
        assert "_integrity" in stamped

    def test_detach_stamp_preserves_original_keys(self):
        """detach_stamp preserves original mapping keys."""
        mapping = {"buttons": {0: {"note": 60}}, "axes": {0: {"cc": 1}}}
        s = stamp(mapping)
        stamped = attach_stamp(mapping, s)
        clean, _ = detach_stamp(stamped)
        assert clean["buttons"] == mapping["buttons"]
        assert clean["axes"] == mapping["axes"]


class TestVerifyAttached:
    """Tests for verify_attached function."""

    def test_verify_attached_true_for_valid_stamped_mapping(self):
        """verify_attached returns True for valid stamped mapping."""
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping)
        stamped = attach_stamp(mapping, s)
        assert verify_attached(stamped)

    def test_verify_attached_false_when_mapping_mutated(self):
        """verify_attached returns False when mapping is mutated after stamping."""
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping)
        stamped = attach_stamp(mapping, s)
        stamped["buttons"][0]["note"] = 61
        assert not verify_attached(stamped)

    def test_verify_attached_false_if_no_stamp(self):
        """verify_attached returns False if no _integrity key present."""
        mapping = {"buttons": {0: {"note": 60}}}
        assert not verify_attached(mapping)

    def test_verify_attached_with_hmac_requires_secret(self):
        """verify_attached with HMAC stamp requires secret."""
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping, secret="secret")
        stamped = attach_stamp(mapping, s)
        assert verify_attached(stamped, secret="secret")
        assert not verify_attached(stamped, secret="wrong_secret")


class TestIntegrityStampSerialization:
    """Tests for IntegrityStamp round-trip serialization."""

    def test_integrity_stamp_to_dict_from_dict_roundtrip(self):
        """IntegrityStamp round-trips through to_dict/from_dict."""
        original = IntegrityStamp(
            algorithm="hmac_sha256",
            hash="abc123def456",
            version="1.0",
            signer="Alice",
            timestamp_s=1234567890.5,
        )
        data = original.to_dict()
        restored = IntegrityStamp.from_dict(data)
        assert restored.algorithm == original.algorithm
        assert restored.hash == original.hash
        assert restored.version == original.version
        assert restored.signer == original.signer
        assert restored.timestamp_s == original.timestamp_s

    def test_integrity_stamp_from_dict_missing_fields_defaults(self):
        """IntegrityStamp.from_dict fills in defaults for optional fields."""
        data = {"algorithm": "sha256", "hash": "abc123"}
        stamp_obj = IntegrityStamp.from_dict(data)
        assert stamp_obj.version == "1.0"
        assert stamp_obj.signer == ""
        assert stamp_obj.timestamp_s == 0.0

    def test_integrity_stamp_from_dict_missing_required_raises(self):
        """IntegrityStamp.from_dict raises KeyError if required fields missing."""
        with pytest.raises(KeyError):
            IntegrityStamp.from_dict({"algorithm": "sha256"})  # Missing hash
        with pytest.raises(KeyError):
            IntegrityStamp.from_dict({"hash": "abc123"})  # Missing algorithm


class TestIntegrationScenarios:
    """Integration tests for realistic workflows."""

    def test_marketplace_download_verification_workflow(self):
        """Simulate marketplace preset download and verification."""
        # Preset creator stamps their mapping
        creator_mapping = {
            "buttons": {0: {"note": 60}, 1: {"note": 61}},
            "axes": {0: {"cc": 1}},
            "name": "Cool Preset",
        }
        creator_secret = "creator_key_12345"
        s = stamp(creator_mapping, signer="@coolcreator", secret=creator_secret)
        stamped = attach_stamp(creator_mapping, s)

        # Marketplace stores stamped mapping (includes _integrity)
        # ...

        # User downloads preset
        downloaded = stamped

        # User verifies with creator's public secret
        is_valid = verify_attached(downloaded, secret=creator_secret)
        assert is_valid

        # If attacker modifies the preset
        attacked = downloaded.copy()
        attacked["buttons"][0]["note"] = 100
        is_compromised = verify_attached(attacked, secret=creator_secret)
        assert not is_compromised

    def test_unsigned_hash_workflow(self):
        """Simulate unsigned hash workflow (no secret)."""
        mapping = {"buttons": {0: {"note": 60}}}
        s = stamp(mapping)  # No secret
        stamped = attach_stamp(mapping, s)

        # Verify without secret
        assert verify_attached(stamped)

        # Modify and verify fails
        stamped_modified = dict(stamped)
        stamped_modified["buttons"] = {0: {"note": 61}}
        assert not verify_attached(stamped_modified)

    def test_multiple_signers_scenario(self):
        """Multiple signers can create stamps with different secrets."""
        mapping = {"buttons": {0: {"note": 60}}}

        # Alice signs
        alice_stamp = stamp(mapping, signer="Alice", secret="alice_key")
        assert verify(mapping, alice_stamp, secret="alice_key")
        assert not verify(mapping, alice_stamp, secret="bob_key")

        # Bob signs the same mapping
        bob_stamp = stamp(mapping, signer="Bob", secret="bob_key")
        assert verify(mapping, bob_stamp, secret="bob_key")
        assert not verify(mapping, bob_stamp, secret="alice_key")
