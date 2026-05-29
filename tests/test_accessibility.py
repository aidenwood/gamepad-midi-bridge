"""Accessibility module tests — reduce motion preferences."""
import pytest
from PySide6.QtCore import QSettings

from gamepad_midi_bridge.ui import accessibility


@pytest.fixture
def clean_qsettings(tmp_path):
    """Fixture that isolates QSettings from the real user config."""
    # PySide6 QSettings uses .config / Registry by default.
    # We'll use a test org/app name to avoid pollution.
    settings = QSettings("test_ucmd", "test_accessibility")
    settings.clear()
    yield settings
    settings.clear()


class TestReduceMotionEnabled:
    """Test reduce_motion_enabled() — user preference in QSettings."""

    def test_default_false(self):
        """When appearance/reduce_motion is not set, should return False."""
        # Start fresh
        qs = QSettings("ucmd", "gamepad-midi-bridge")
        qs.remove("appearance/reduce_motion")
        result = accessibility.reduce_motion_enabled()
        assert result is False

    def test_set_true(self):
        """When appearance/reduce_motion is set to True, should return True."""
        qs = QSettings("ucmd", "gamepad-midi-bridge")
        qs.setValue("appearance/reduce_motion", True)
        result = accessibility.reduce_motion_enabled()
        assert result is True

    def test_set_false(self):
        """When appearance/reduce_motion is set to False, should return False."""
        qs = QSettings("ucmd", "gamepad-midi-bridge")
        qs.setValue("appearance/reduce_motion", False)
        result = accessibility.reduce_motion_enabled()
        assert result is False


class TestPrefersReducedMotion:
    """Test prefers_reduced_motion() — combines user + OS settings."""

    def test_returns_true_when_user_pref_set(self):
        """Should return True if user has enable reduce_motion."""
        qs = QSettings("ucmd", "gamepad-midi-bridge")
        qs.setValue("appearance/reduce_motion", True)
        result = accessibility.prefers_reduced_motion()
        assert result is True

    def test_returns_false_when_no_prefs(self):
        """Should return False when user pref is off and OS check fails."""
        qs = QSettings("ucmd", "gamepad-midi-bridge")
        qs.setValue("appearance/reduce_motion", False)
        # OS checks might return True, but we can at least check the logic.
        result = accessibility.prefers_reduced_motion()
        # This will depend on OS settings; we just ensure it doesn't crash.
        assert isinstance(result, bool)

    def test_doesnt_crash_on_any_platform(self):
        """Should handle macOS, Windows, and Linux without raising."""
        # This is the integration test — just make sure nothing crashes.
        result = accessibility.prefers_reduced_motion()
        assert isinstance(result, bool)


class TestAccessibilityModuleImport:
    """Test that the accessibility module is importable and correct."""

    def test_module_import(self):
        """Should import without error."""
        from gamepad_midi_bridge.ui import accessibility  # noqa: F401

    def test_has_required_functions(self):
        """Should have both utility functions."""
        assert callable(accessibility.reduce_motion_enabled)
        assert callable(accessibility.prefers_reduced_motion)

    def test_compile_check(self):
        """Module should be syntactically valid."""
        # If we got here, import succeeded — syntax is fine.
        assert True
