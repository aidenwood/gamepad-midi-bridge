"""Tests for stick zone mapping."""

import math
import pytest

from gamepad_midi_bridge.stick_zones import (
    ZONE_4,
    ZONE_8,
    ZONE_9,
    StickZoneConfig,
    StickZoneMapper,
    pick_zone_4,
    pick_zone_8,
    pick_zone_9,
    zone_for,
)


class TestZone4:
    """Tests for 4-zone picker."""

    def test_pick_zone_4_north(self) -> None:
        """Y-axis dominant, positive y -> N."""
        assert pick_zone_4(0, 1) == "N"

    def test_pick_zone_4_east(self) -> None:
        """X-axis dominant, positive x -> E."""
        assert pick_zone_4(1, 0) == "E"

    def test_pick_zone_4_south(self) -> None:
        """Y-axis dominant, negative y -> S."""
        assert pick_zone_4(0, -1) == "S"

    def test_pick_zone_4_west(self) -> None:
        """X-axis dominant, negative x -> W."""
        assert pick_zone_4(-1, 0) == "W"

    def test_pick_zone_4_diagonal_northeast(self) -> None:
        """Diagonal: x dominates slightly -> E."""
        assert pick_zone_4(0.6, 0.5) == "E"

    def test_pick_zone_4_diagonal_northwest(self) -> None:
        """Diagonal: y dominates -> N."""
        assert pick_zone_4(-0.5, 0.6) == "N"


class TestZone8:
    """Tests for 8-zone picker."""

    def test_pick_zone_8_cardinal_north(self) -> None:
        """Straight up -> N."""
        assert pick_zone_8(0, 1) == "N"

    def test_pick_zone_8_cardinal_east(self) -> None:
        """Straight right -> E."""
        assert pick_zone_8(1, 0) == "E"

    def test_pick_zone_8_cardinal_south(self) -> None:
        """Straight down -> S."""
        assert pick_zone_8(0, -1) == "S"

    def test_pick_zone_8_cardinal_west(self) -> None:
        """Straight left -> W."""
        assert pick_zone_8(-1, 0) == "W"

    def test_pick_zone_8_diagonal_northeast(self) -> None:
        """45 degrees NE -> NE."""
        assert pick_zone_8(1, 1) == "NE"

    def test_pick_zone_8_diagonal_southeast(self) -> None:
        """45 degrees SE -> SE."""
        assert pick_zone_8(1, -1) == "SE"

    def test_pick_zone_8_diagonal_southwest(self) -> None:
        """45 degrees SW -> SW."""
        assert pick_zone_8(-1, -1) == "SW"

    def test_pick_zone_8_diagonal_northwest(self) -> None:
        """45 degrees NW -> NW."""
        assert pick_zone_8(-1, 1) == "NW"

    def test_pick_zone_8_all_zones_distinct(self) -> None:
        """All 8 zones are reachable and distinct."""
        angles = [i * (2 * math.pi / 8) for i in range(8)]
        zones = set()
        for angle in angles:
            x = math.cos(angle)
            y = math.sin(angle)
            zones.add(pick_zone_8(x, y))
        assert len(zones) == 8


class TestZone9:
    """Tests for 9-zone picker with center deadzone."""

    def test_pick_zone_9_center_in_deadzone(self) -> None:
        """Magnitude 0 within deadzone 0.15 -> C."""
        assert pick_zone_9(0, 0, center_deadzone=0.15) == "C"

    def test_pick_zone_9_center_low_x_in_deadzone(self) -> None:
        """Small x in deadzone -> C."""
        assert pick_zone_9(0.05, 0.05, center_deadzone=0.15) == "C"

    def test_pick_zone_9_north_above_deadzone(self) -> None:
        """Magnitude above deadzone, pointing north -> N."""
        assert pick_zone_9(0, 0.5, center_deadzone=0.15) == "N"

    def test_pick_zone_9_northeast_above_deadzone(self) -> None:
        """Magnitude above deadzone, pointing NE -> NE."""
        assert pick_zone_9(0.5, 0.5, center_deadzone=0.15) == "NE"

    def test_pick_zone_9_south_above_deadzone(self) -> None:
        """Magnitude above deadzone, pointing south -> S."""
        assert pick_zone_9(0, -0.5, center_deadzone=0.15) == "S"

    def test_pick_zone_9_strict_deadzone_boundary(self) -> None:
        """Exactly at deadzone boundary should still be C."""
        # Magnitude = 0.15, deadzone = 0.15, so should be C (not outside)
        x = 0.15 / math.sqrt(2)
        y = 0.15 / math.sqrt(2)
        assert pick_zone_9(x, y, center_deadzone=0.15) == "C"

    def test_pick_zone_9_just_outside_deadzone(self) -> None:
        """Just outside deadzone should be cardinal zone."""
        # Magnitude = 0.151, deadzone = 0.15
        magnitude = 0.151
        x = magnitude / math.sqrt(2)
        y = magnitude / math.sqrt(2)
        assert pick_zone_9(x, y, center_deadzone=0.15) == "NE"


class TestZoneFor:
    """Tests for zone_for dispatcher."""

    def test_zone_for_4zone_north(self) -> None:
        """4-zone mode -> N."""
        cfg = StickZoneConfig(zone_count=4, center_deadzone=0.15)
        assert zone_for(0, 1, cfg) == "N"

    def test_zone_for_4zone_deadzone(self) -> None:
        """4-zone mode below deadzone -> None."""
        cfg = StickZoneConfig(zone_count=4, center_deadzone=0.15)
        assert zone_for(0.05, 0.05, cfg) is None

    def test_zone_for_8zone_northeast(self) -> None:
        """8-zone mode -> NE."""
        cfg = StickZoneConfig(zone_count=8)
        assert zone_for(1, 1, cfg) == "NE"

    def test_zone_for_8zone_deadzone(self) -> None:
        """8-zone mode below deadzone -> None."""
        cfg = StickZoneConfig(zone_count=8, center_deadzone=0.15)
        assert zone_for(0.05, 0.05, cfg) is None

    def test_zone_for_9zone_center(self) -> None:
        """9-zone mode center -> C."""
        cfg = StickZoneConfig(zone_count=9, center_deadzone=0.15)
        assert zone_for(0, 0, cfg) == "C"

    def test_zone_for_9zone_north(self) -> None:
        """9-zone mode north -> N."""
        cfg = StickZoneConfig(zone_count=9, center_deadzone=0.15)
        assert zone_for(0, 0.5, cfg) == "N"

    def test_zone_for_clamped_zone_count_to_8(self) -> None:
        """16-zone maps to 8-zone logic for now."""
        cfg = StickZoneConfig(zone_count=16)
        assert zone_for(1, 1, cfg) == "NE"


class TestStickZoneConfig:
    """Tests for StickZoneConfig dataclass."""

    def test_config_defaults(self) -> None:
        """Default config is sensible."""
        cfg = StickZoneConfig()
        assert cfg.enabled is False
        assert cfg.zone_count == 9
        assert cfg.center_deadzone == 0.15
        assert cfg.outer_threshold == 0.95
        assert cfg.channel == 1
        assert cfg.velocity == 100
        assert cfg.zone_notes == {}

    def test_config_clamp_zone_count_low(self) -> None:
        """zone_count < 4 clamped to 4."""
        cfg = StickZoneConfig(zone_count=2)
        assert cfg.zone_count == 4

    def test_config_clamp_zone_count_high(self) -> None:
        """zone_count > 16 clamped to 16."""
        cfg = StickZoneConfig(zone_count=32)
        assert cfg.zone_count == 16

    def test_config_clamp_center_deadzone_low(self) -> None:
        """center_deadzone < 0 clamped to 0."""
        cfg = StickZoneConfig(center_deadzone=-0.1)
        assert cfg.center_deadzone == 0.0

    def test_config_clamp_center_deadzone_high(self) -> None:
        """center_deadzone > 0.5 clamped to 0.5."""
        cfg = StickZoneConfig(center_deadzone=0.7)
        assert cfg.center_deadzone == 0.5

    def test_config_clamp_outer_threshold_low(self) -> None:
        """outer_threshold < 0.1 clamped to 0.1."""
        cfg = StickZoneConfig(outer_threshold=0.05)
        assert cfg.outer_threshold == 0.1

    def test_config_clamp_outer_threshold_high(self) -> None:
        """outer_threshold > 1.0 clamped to 1.0."""
        cfg = StickZoneConfig(outer_threshold=1.5)
        assert cfg.outer_threshold == 1.0

    def test_config_clamp_channel(self) -> None:
        """channel clamped to 1..16."""
        cfg1 = StickZoneConfig(channel=0)
        assert cfg1.channel == 1
        cfg2 = StickZoneConfig(channel=20)
        assert cfg2.channel == 16

    def test_config_clamp_velocity(self) -> None:
        """velocity clamped to 1..127."""
        cfg1 = StickZoneConfig(velocity=0)
        assert cfg1.velocity == 1
        cfg2 = StickZoneConfig(velocity=150)
        assert cfg2.velocity == 127

    def test_config_to_dict(self) -> None:
        """Serialize to dict."""
        cfg = StickZoneConfig(
            enabled=True,
            zone_count=8,
            center_deadzone=0.2,
            zone_notes={"N": 60, "E": 62},
            channel=5,
            velocity=80,
        )
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["zone_count"] == 8
        assert d["center_deadzone"] == 0.2
        assert d["zone_notes"] == {"N": 60, "E": 62}
        assert d["channel"] == 5
        assert d["velocity"] == 80

    def test_config_from_dict(self) -> None:
        """Deserialize from dict."""
        d = {
            "enabled": True,
            "zone_count": 8,
            "center_deadzone": 0.2,
            "zone_notes": {"N": 60, "E": 62},
            "channel": 5,
            "velocity": 80,
        }
        cfg = StickZoneConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.zone_count == 8
        assert cfg.center_deadzone == 0.2
        assert cfg.zone_notes == {"N": 60, "E": 62}
        assert cfg.channel == 5
        assert cfg.velocity == 80

    def test_config_round_trip(self) -> None:
        """to_dict -> from_dict round-trip preserves state."""
        original = StickZoneConfig(
            enabled=True,
            zone_count=9,
            center_deadzone=0.25,
            outer_threshold=0.85,
            zone_notes={"N": 60, "S": 48},
            channel=10,
            velocity=100,
        )
        restored = StickZoneConfig.from_dict(original.to_dict())
        assert restored.enabled == original.enabled
        assert restored.zone_count == original.zone_count
        assert restored.center_deadzone == original.center_deadzone
        assert restored.outer_threshold == original.outer_threshold
        assert restored.zone_notes == original.zone_notes
        assert restored.channel == original.channel
        assert restored.velocity == original.velocity


class TestStickZoneMapper:
    """Tests for StickZoneMapper state machine."""

    def test_mapper_init(self) -> None:
        """Mapper initializes with config and no last_zone."""
        cfg = StickZoneConfig()
        mapper = StickZoneMapper(cfg)
        assert mapper.cfg is cfg
        assert mapper._last_zone is None
        assert mapper.current_zone() is None

    def test_mapper_feed_first_zone_mapped(self) -> None:
        """First feed returns (zone, note) if zone is mapped."""
        cfg = StickZoneConfig(zone_count=9, zone_notes={"N": 60})
        mapper = StickZoneMapper(cfg)
        result = mapper.feed(0, 1)
        assert result == ("N", 60)
        assert mapper.current_zone() == "N"

    def test_mapper_feed_first_zone_unmapped(self) -> None:
        """First feed returns None if zone not in zone_notes."""
        cfg = StickZoneConfig(zone_count=9, zone_notes={"S": 60})
        mapper = StickZoneMapper(cfg)
        result = mapper.feed(0, 1)  # N is not mapped
        assert result is None
        assert mapper.current_zone() == "N"

    def test_mapper_feed_same_zone_no_change(self) -> None:
        """Feeding same zone again returns None."""
        cfg = StickZoneConfig(zone_count=9, zone_notes={"N": 60})
        mapper = StickZoneMapper(cfg)
        result1 = mapper.feed(0, 0.8)
        assert result1 == ("N", 60)
        result2 = mapper.feed(0, 0.9)  # Still N
        assert result2 is None

    def test_mapper_feed_zone_change(self) -> None:
        """Zone change triggers return (zone, note)."""
        cfg = StickZoneConfig(
            zone_count=9, zone_notes={"N": 60, "E": 62, "S": 64}
        )
        mapper = StickZoneMapper(cfg)
        result1 = mapper.feed(0, 1)  # N
        assert result1 == ("N", 60)
        result2 = mapper.feed(1, 0)  # E
        assert result2 == ("E", 62)
        result3 = mapper.feed(0, -1)  # S
        assert result3 == ("S", 64)

    def test_mapper_feed_unmapped_zone_after_mapped(self) -> None:
        """Transition to unmapped zone returns None."""
        cfg = StickZoneConfig(zone_count=9, zone_notes={"N": 60})
        mapper = StickZoneMapper(cfg)
        result1 = mapper.feed(0, 1)  # N (mapped)
        assert result1 == ("N", 60)
        result2 = mapper.feed(1, 0)  # E (unmapped)
        assert result2 is None
        assert mapper.current_zone() == "E"

    def test_mapper_feed_mapped_zone_after_unmapped(self) -> None:
        """Transition from unmapped to mapped zone returns (zone, note)."""
        cfg = StickZoneConfig(zone_count=9, zone_notes={"E": 62})
        mapper = StickZoneMapper(cfg)
        result1 = mapper.feed(0, 1)  # N (unmapped)
        assert result1 is None
        result2 = mapper.feed(1, 0)  # E (mapped)
        assert result2 == ("E", 62)

    def test_mapper_feed_none_zone(self) -> None:
        """Below deadzone (4-zone mode) returns None."""
        cfg = StickZoneConfig(
            zone_count=4, center_deadzone=0.15, zone_notes={"N": 60}
        )
        mapper = StickZoneMapper(cfg)
        result = mapper.feed(0.05, 0.05)  # Below deadzone
        assert result is None
        assert mapper.current_zone() is None

    def test_mapper_reset_clears_last_zone(self) -> None:
        """Reset clears _last_zone so next feed triggers change."""
        cfg = StickZoneConfig(zone_count=9, zone_notes={"N": 60})
        mapper = StickZoneMapper(cfg)
        result1 = mapper.feed(0, 1)  # N
        assert result1 == ("N", 60)
        result2 = mapper.feed(0, 0.9)  # Still N
        assert result2 is None
        mapper.reset()
        result3 = mapper.feed(0, 0.9)  # Still N, but after reset -> triggers again
        assert result3 == ("N", 60)

    def test_mapper_4zone_with_deadzone(self) -> None:
        """4-zone with deadzone transitions correctly."""
        cfg = StickZoneConfig(
            zone_count=4,
            center_deadzone=0.2,
            zone_notes={"N": 60, "E": 62},
        )
        mapper = StickZoneMapper(cfg)
        result1 = mapper.feed(0.05, 0.05)  # Below deadzone
        assert result1 is None
        result2 = mapper.feed(0, 1)  # N (above deadzone, mapped)
        assert result2 == ("N", 60)
        result3 = mapper.feed(1, 0)  # E (above deadzone, mapped)
        assert result3 == ("E", 62)

    def test_mapper_config_change_after_creation(self) -> None:
        """Modifying config after mapper creation affects behavior."""
        cfg = StickZoneConfig(zone_count=9, zone_notes={})
        mapper = StickZoneMapper(cfg)
        result1 = mapper.feed(0, 1)  # N
        assert result1 is None
        cfg.zone_notes["N"] = 60
        result2 = mapper.feed(1, 0)  # E (zone change)
        # Change N to be mapped
        mapper.reset()
        result3 = mapper.feed(0, 1)  # Back to N, now mapped
        assert result3 == ("N", 60)
