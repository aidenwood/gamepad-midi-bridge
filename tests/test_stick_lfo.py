"""Tests for StickLfoConfig dataclass and _stick_lfo_from_dict helper."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.mapping import (
    StickConfig,
    StickLfoConfig,
    _stick_from_dict,
    _stick_lfo_from_dict,
)


# ---------------------------------------------------------------------------
# StickLfoConfig defaults
# ---------------------------------------------------------------------------

class TestStickLfoConfigDefaults:
    def test_enabled_default_false(self):
        cfg = StickLfoConfig()
        assert cfg.enabled is False

    def test_waveform_default(self):
        assert StickLfoConfig().waveform == "sine"

    def test_rate_hz_default(self):
        assert StickLfoConfig().rate_hz == 0.5

    def test_depth_default(self):
        assert StickLfoConfig().depth == 0.5

    def test_phase_lock_default(self):
        assert StickLfoConfig().phase_lock_to_bpm is False

    def test_blend_mode_default(self):
        assert StickLfoConfig().blend_mode == "add"


# ---------------------------------------------------------------------------
# StickConfig gains lfo field
# ---------------------------------------------------------------------------

class TestStickConfigHasLfo:
    def test_lfo_field_exists(self):
        cfg = StickConfig()
        assert hasattr(cfg, "lfo")
        assert isinstance(cfg.lfo, StickLfoConfig)

    def test_lfo_disabled_by_default(self):
        assert StickConfig().lfo.enabled is False


# ---------------------------------------------------------------------------
# Round-trip serialisation via _stick_from_dict
# ---------------------------------------------------------------------------

class TestStickLfoRoundTrip:
    def _make_dict(self, **lfo_overrides):
        lfo = {"enabled": False, "waveform": "sine", "rate_hz": 0.5,
               "depth": 0.5, "phase_lock_to_bpm": False, "blend_mode": "add"}
        lfo.update(lfo_overrides)
        return {"lfo": lfo}

    def test_round_trip_defaults(self):
        cfg = _stick_from_dict(self._make_dict())
        assert cfg.lfo.enabled is False
        assert cfg.lfo.waveform == "sine"
        assert cfg.lfo.rate_hz == 0.5
        assert cfg.lfo.depth == 0.5
        assert cfg.lfo.blend_mode == "add"

    def test_round_trip_enabled(self):
        cfg = _stick_from_dict(self._make_dict(enabled=True, waveform="triangle",
                                               rate_hz=2.0, depth=0.8,
                                               blend_mode="replace"))
        assert cfg.lfo.enabled is True
        assert cfg.lfo.waveform == "triangle"
        assert cfg.lfo.rate_hz == 2.0
        assert cfg.lfo.depth == 0.8
        assert cfg.lfo.blend_mode == "replace"

    def test_missing_lfo_key_gives_defaults(self):
        cfg = _stick_from_dict({})
        assert isinstance(cfg.lfo, StickLfoConfig)
        assert cfg.lfo.enabled is False

    def test_none_dict_gives_defaults(self):
        cfg = _stick_from_dict(None)
        assert isinstance(cfg.lfo, StickLfoConfig)


# ---------------------------------------------------------------------------
# _stick_lfo_from_dict — waveform validation
# ---------------------------------------------------------------------------

class TestStickLfoWaveformValidation:
    @pytest.mark.parametrize("wf", ["sine", "triangle", "square", "saw", "random"])
    def test_valid_waveforms_accepted(self, wf):
        cfg = _stick_lfo_from_dict({"waveform": wf})
        assert cfg.waveform == wf

    def test_invalid_waveform_falls_back_to_sine(self):
        cfg = _stick_lfo_from_dict({"waveform": "unknown_wave"})
        assert cfg.waveform == "sine"

    def test_empty_waveform_falls_back_to_sine(self):
        cfg = _stick_lfo_from_dict({"waveform": ""})
        assert cfg.waveform == "sine"

    def test_none_dict_gives_sine(self):
        cfg = _stick_lfo_from_dict(None)
        assert cfg.waveform == "sine"


# ---------------------------------------------------------------------------
# _stick_lfo_from_dict — blend_mode validation
# ---------------------------------------------------------------------------

class TestStickLfoBlendModeValidation:
    @pytest.mark.parametrize("mode", ["add", "replace", "multiply"])
    def test_valid_modes_accepted(self, mode):
        cfg = _stick_lfo_from_dict({"blend_mode": mode})
        assert cfg.blend_mode == mode

    def test_invalid_blend_mode_falls_back_to_add(self):
        cfg = _stick_lfo_from_dict({"blend_mode": "nonsense"})
        assert cfg.blend_mode == "add"

    def test_empty_blend_mode_falls_back_to_add(self):
        cfg = _stick_lfo_from_dict({"blend_mode": ""})
        assert cfg.blend_mode == "add"


# ---------------------------------------------------------------------------
# _stick_lfo_from_dict — rate_hz clamping
# ---------------------------------------------------------------------------

class TestStickLfoRateClamp:
    def test_rate_below_min_clamped(self):
        cfg = _stick_lfo_from_dict({"rate_hz": 0.0})
        assert cfg.rate_hz == pytest.approx(0.01)

    def test_rate_above_max_clamped(self):
        cfg = _stick_lfo_from_dict({"rate_hz": 999.0})
        assert cfg.rate_hz == pytest.approx(20.0)

    def test_rate_within_range_accepted(self):
        cfg = _stick_lfo_from_dict({"rate_hz": 5.0})
        assert cfg.rate_hz == pytest.approx(5.0)

    def test_rate_at_min_boundary(self):
        cfg = _stick_lfo_from_dict({"rate_hz": 0.01})
        assert cfg.rate_hz == pytest.approx(0.01)

    def test_rate_at_max_boundary(self):
        cfg = _stick_lfo_from_dict({"rate_hz": 20.0})
        assert cfg.rate_hz == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# _stick_lfo_from_dict — depth clamping
# ---------------------------------------------------------------------------

class TestStickLfoDepthClamp:
    def test_depth_below_zero_clamped(self):
        cfg = _stick_lfo_from_dict({"depth": -0.5})
        assert cfg.depth == pytest.approx(0.0)

    def test_depth_above_one_clamped(self):
        cfg = _stick_lfo_from_dict({"depth": 5.0})
        assert cfg.depth == pytest.approx(1.0)

    def test_depth_within_range(self):
        cfg = _stick_lfo_from_dict({"depth": 0.75})
        assert cfg.depth == pytest.approx(0.75)

    def test_depth_at_zero(self):
        cfg = _stick_lfo_from_dict({"depth": 0.0})
        assert cfg.depth == pytest.approx(0.0)

    def test_depth_at_one(self):
        cfg = _stick_lfo_from_dict({"depth": 1.0})
        assert cfg.depth == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# _stick_lfo_from_dict — phase_lock_to_bpm
# ---------------------------------------------------------------------------

class TestStickLfoPhaseLock:
    def test_phase_lock_false_by_default(self):
        cfg = _stick_lfo_from_dict({})
        assert cfg.phase_lock_to_bpm is False

    def test_phase_lock_true_roundtrip(self):
        cfg = _stick_lfo_from_dict({"phase_lock_to_bpm": True})
        assert cfg.phase_lock_to_bpm is True
