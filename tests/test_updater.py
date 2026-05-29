"""Tests for update channel filtering."""
import pytest

from gamepad_midi_bridge.updater import _is_version_allowed


class TestVersionAllowed:
    """Test release channel filtering logic."""

    def test_stable_rejects_beta(self):
        """Stable channel rejects beta versions."""
        assert not _is_version_allowed("v1.2.0-beta.1", "stable")
        assert not _is_version_allowed("1.2.0-beta.1", "stable")

    def test_stable_rejects_rc(self):
        """Stable channel rejects release candidate versions."""
        assert not _is_version_allowed("v1.2.0-rc.1", "stable")
        assert not _is_version_allowed("1.2.0-rc.2", "stable")

    def test_stable_rejects_dev(self):
        """Stable channel rejects dev versions."""
        assert not _is_version_allowed("v1.2.0-dev.1", "stable")
        assert not _is_version_allowed("1.2.0-dev.99", "stable")

    def test_stable_accepts_release(self):
        """Stable channel accepts release versions."""
        assert _is_version_allowed("v1.2.0", "stable")
        assert _is_version_allowed("1.2.0", "stable")
        assert _is_version_allowed("v0.1.0", "stable")
        assert _is_version_allowed("v10.20.30", "stable")

    def test_beta_accepts_beta(self):
        """Beta channel accepts beta versions."""
        assert _is_version_allowed("v1.2.0-beta.1", "beta")
        assert _is_version_allowed("1.2.0-beta.5", "beta")

    def test_beta_accepts_rc(self):
        """Beta channel accepts RC versions."""
        assert _is_version_allowed("v1.2.0-rc.1", "beta")
        assert _is_version_allowed("1.2.0-rc.2", "beta")

    def test_beta_accepts_stable(self):
        """Beta channel accepts stable versions."""
        assert _is_version_allowed("v1.2.0", "beta")
        assert _is_version_allowed("1.2.0", "beta")

    def test_beta_rejects_dev(self):
        """Beta channel rejects dev versions."""
        assert not _is_version_allowed("v1.2.0-dev.1", "beta")
        assert not _is_version_allowed("1.2.0-dev.99", "beta")

    def test_dev_accepts_all(self):
        """Dev channel accepts all version types."""
        assert _is_version_allowed("v1.2.0", "dev")
        assert _is_version_allowed("v1.2.0-beta.1", "dev")
        assert _is_version_allowed("v1.2.0-rc.1", "dev")
        assert _is_version_allowed("v1.2.0-dev.1", "dev")
        assert _is_version_allowed("1.2.0", "dev")
        assert _is_version_allowed("1.2.0-beta.99", "dev")

    def test_invalid_version_format(self):
        """Invalid version formats are rejected."""
        assert not _is_version_allowed("not-a-version", "stable")
        assert not _is_version_allowed("v1.2", "stable")
        assert not _is_version_allowed("", "stable")
        assert not _is_version_allowed("1.2.0.0", "stable")

    def test_invalid_channel(self):
        """Invalid channel returns False."""
        assert not _is_version_allowed("v1.2.0", "invalid")
        assert not _is_version_allowed("v1.2.0", "")
        assert not _is_version_allowed("v1.2.0", "nightly")

    def test_beta_rc_variants(self):
        """Test various RC and beta suffix formats."""
        assert _is_version_allowed("v1.2.0-rc.10", "beta")
        assert _is_version_allowed("v1.2.0-beta.a", "beta")
        assert not _is_version_allowed("v1.2.0-rc.1", "stable")
        assert not _is_version_allowed("v1.2.0-beta.1", "stable")
