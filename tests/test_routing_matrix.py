"""16x16 channel routing matrix tests."""
from __future__ import annotations

import pytest

from gamepad_midi_bridge.routing_matrix import RoutingMatrix, RoutingMatrixConfig


class TestRoutingMatrixConfigDefaults:
    """Test RoutingMatrixConfig default initialization."""

    def test_default_disabled(self):
        """Default config: routing disabled."""
        cfg = RoutingMatrixConfig()
        assert cfg.enabled is False

    def test_default_pass_through_false(self):
        """Default config: pass_through_unrouted is False."""
        cfg = RoutingMatrixConfig()
        assert cfg.pass_through_unrouted is False

    def test_default_matrix_is_identity(self):
        """Default config: matrix is 16x16 identity."""
        cfg = RoutingMatrixConfig()
        assert len(cfg.matrix) == 16
        for i in range(16):
            assert len(cfg.matrix[i]) == 16
            for j in range(16):
                expected = i == j
                assert cfg.matrix[i][j] is expected

    def test_matrix_padded_on_init(self):
        """Short matrix is padded to 16x16 on __post_init__."""
        cfg = RoutingMatrixConfig(matrix=[[True, False], [False, True]])
        assert len(cfg.matrix) == 16
        assert all(len(row) == 16 for row in cfg.matrix)

    def test_matrix_trimmed_on_init(self):
        """Long matrix is trimmed to 16x16 on __post_init__."""
        long_matrix = [[True] * 20 for _ in range(20)]
        cfg = RoutingMatrixConfig(matrix=long_matrix)
        assert len(cfg.matrix) == 16
        assert all(len(row) == 16 for row in cfg.matrix)


class TestRoutingMatrixConfigSerialization:
    """Test RoutingMatrixConfig to_dict/from_dict."""

    def test_to_dict_default(self):
        """to_dict of default config returns correct keys."""
        cfg = RoutingMatrixConfig()
        d = cfg.to_dict()
        assert "enabled" in d
        assert "matrix" in d
        assert "pass_through_unrouted" in d
        assert d["enabled"] is False
        assert d["pass_through_unrouted"] is False
        assert len(d["matrix"]) == 16

    def test_to_dict_custom_values(self):
        """to_dict preserves custom values."""
        cfg = RoutingMatrixConfig(enabled=True, pass_through_unrouted=True)
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["pass_through_unrouted"] is True

    def test_from_dict_default(self):
        """from_dict with empty dict uses defaults."""
        cfg = RoutingMatrixConfig.from_dict({})
        assert cfg.enabled is False
        assert cfg.pass_through_unrouted is False
        assert len(cfg.matrix) == 16

    def test_from_dict_custom_values(self):
        """from_dict preserves custom values."""
        cfg = RoutingMatrixConfig.from_dict({
            "enabled": True,
            "pass_through_unrouted": True,
        })
        assert cfg.enabled is True
        assert cfg.pass_through_unrouted is True

    def test_from_dict_pads_short_matrix(self):
        """from_dict pads short matrix to 16x16."""
        short = [[True, False], [False, True]]
        cfg = RoutingMatrixConfig.from_dict({"matrix": short})
        assert len(cfg.matrix) == 16
        assert all(len(row) == 16 for row in cfg.matrix)

    def test_from_dict_trims_long_matrix(self):
        """from_dict trims long matrix to 16x16."""
        long = [[True] * 20 for _ in range(20)]
        cfg = RoutingMatrixConfig.from_dict({"matrix": long})
        assert len(cfg.matrix) == 16
        assert all(len(row) == 16 for row in cfg.matrix)

    def test_round_trip_serialization(self):
        """Serialize and deserialize preserves all values."""
        cfg1 = RoutingMatrixConfig(enabled=True, pass_through_unrouted=True)
        d = cfg1.to_dict()
        cfg2 = RoutingMatrixConfig.from_dict(d)
        assert cfg2.enabled == cfg1.enabled
        assert cfg2.pass_through_unrouted == cfg1.pass_through_unrouted
        assert cfg2.matrix == cfg1.matrix


class TestRoutingMatrixDefaults:
    """Test RoutingMatrix default initialization."""

    def test_default_identity_matrix(self):
        """Default matrix: each channel routes only to itself."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        for ch in range(1, 17):
            assert m.route(ch) == [ch]

    def test_default_total_routes_is_16(self):
        """Default identity has 16 routes (one per channel)."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        assert m.total_routes() == 16

    def test_matrix_copied_from_config(self):
        """RoutingMatrix copies config matrix; changes to config don't affect instance."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        cfg.matrix[0][1] = True  # Modify config
        # m should be unchanged
        assert not m.matrix[0][1]


class TestRoutingMatrixRoute:
    """Test route() method."""

    def test_route_single_input_default(self):
        """route(1) on default matrix returns [1]."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        assert m.route(1) == [1]

    def test_route_all_channels_default(self):
        """route(ch) == [ch] for all channels on default matrix."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        for ch in range(1, 17):
            assert m.route(ch) == [ch]

    def test_route_clamps_low(self):
        """route(0) is clamped to channel 1."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        assert m.route(0) == [1]

    def test_route_clamps_high(self):
        """route(17) is clamped to channel 16."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        assert m.route(17) == [16]

    def test_route_returns_list(self):
        """route() always returns a list."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        result = m.route(1)
        assert isinstance(result, list)

    def test_route_empty_without_pass_through(self):
        """route() returns empty list for unrouted channel if pass_through_unrouted=False."""
        cfg = RoutingMatrixConfig(pass_through_unrouted=False)
        m = RoutingMatrix(cfg)
        m.clear_row(1)
        assert m.route(1) == []

    def test_route_pass_through(self):
        """route() returns [channel] for unrouted if pass_through_unrouted=True."""
        cfg = RoutingMatrixConfig(pass_through_unrouted=True)
        m = RoutingMatrix(cfg)
        m.clear_row(5)
        assert m.route(5) == [5]

    def test_route_multiple_outputs(self):
        """route() returns all True entries in row."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_row(1)
        m.set_route(1, 1, True)
        m.set_route(1, 5, True)
        m.set_route(1, 16, True)
        assert sorted(m.route(1)) == [1, 5, 16]


class TestRoutingMatrixSetRoute:
    """Test set_route() method."""

    def test_set_route_adds_route(self):
        """set_route(1, 2, True) adds route from 1 to 2."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_row(1)
        m.set_route(1, 2, True)
        assert m.is_routed(1, 2) is True

    def test_set_route_both_present_when_enabled(self):
        """After set_route(1, 2), both 1 and 2 in route(1) if identity preserved."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.set_route(1, 2, True)
        assert 1 in m.route(1)
        assert 2 in m.route(1)

    def test_set_route_removes_when_disabled(self):
        """set_route(1, 2, False) removes route."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.set_route(1, 2, False)
        assert m.is_routed(1, 2) is False

    def test_set_route_clamps_in_channel(self):
        """set_route clamps input channel to 1..16."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.set_route(0, 5, True)
        # Should have clamped 0 → 1, so matrix[0][4] should be True
        assert m.matrix[0][4] is True

    def test_set_route_clamps_out_channel(self):
        """set_route clamps output channel to 1..16."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.set_route(5, 20, True)
        # Should have clamped 20 → 16, so matrix[4][15] should be True
        assert m.matrix[4][15] is True


class TestRoutingMatrixToggleRoute:
    """Test toggle_route() method."""

    def test_toggle_route_enables_disabled(self):
        """toggle_route on disabled route returns True (enables)."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_row(1)
        result = m.toggle_route(1, 2)
        assert result is True
        assert m.is_routed(1, 2) is True

    def test_toggle_route_disables_enabled(self):
        """toggle_route on enabled route returns False (disables)."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        result = m.toggle_route(1, 1)  # Identity has 1→1 enabled
        assert result is False
        assert m.is_routed(1, 1) is False

    def test_toggle_route_twice_restores(self):
        """toggle_route twice returns to original state."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        original = m.is_routed(1, 2)
        m.toggle_route(1, 2)
        m.toggle_route(1, 2)
        assert m.is_routed(1, 2) == original


class TestRoutingMatrixIsRouted:
    """Test is_routed() method."""

    def test_is_routed_default_identity(self):
        """is_routed(ch, ch) is True for identity on default matrix."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        for ch in range(1, 17):
            assert m.is_routed(ch, ch) is True

    def test_is_routed_default_non_identity(self):
        """is_routed(1, 2) is False on default identity matrix."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        assert m.is_routed(1, 2) is False

    def test_is_routed_clamps_channels(self):
        """is_routed clamps channels to 1..16."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        # is_routed(0, 0) should clamp to is_routed(1, 1)
        assert m.is_routed(0, 0) == m.is_routed(1, 1)


class TestRoutingMatrixClearRow:
    """Test clear_row() method."""

    def test_clear_row_zeros_all_routes(self):
        """clear_row(1) sets all routes in row 1 to False."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_row(1)
        for out_ch in range(1, 17):
            assert m.is_routed(1, out_ch) is False

    def test_clear_row_other_rows_unchanged(self):
        """clear_row(1) doesn't affect other rows."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_row(1)
        for ch in range(2, 17):
            assert m.is_routed(ch, ch) is True

    def test_clear_row_route_returns_empty(self):
        """After clear_row(1) with pass_through=False, route(1) returns []."""
        cfg = RoutingMatrixConfig(pass_through_unrouted=False)
        m = RoutingMatrix(cfg)
        m.clear_row(1)
        assert m.route(1) == []

    def test_clear_row_clamps_channel(self):
        """clear_row clamps channel to 1..16."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_row(20)
        # Should have clamped to 16, so matrix[15] should be all False
        assert all(not x for x in m.matrix[15])


class TestRoutingMatrixClearAll:
    """Test clear_all() method."""

    def test_clear_all_zeros_entire_matrix(self):
        """clear_all() zeros entire matrix."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_all()
        for i in range(16):
            for j in range(16):
                assert m.matrix[i][j] is False

    def test_clear_all_total_routes_zero(self):
        """After clear_all(), total_routes() returns 0."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_all()
        assert m.total_routes() == 0

    def test_clear_all_route_returns_empty(self):
        """After clear_all() with pass_through=False, route(ch) returns []."""
        cfg = RoutingMatrixConfig(pass_through_unrouted=False)
        m = RoutingMatrix(cfg)
        m.clear_all()
        for ch in range(1, 17):
            assert m.route(ch) == []


class TestRoutingMatrixSetIdentity:
    """Test set_identity() method."""

    def test_set_identity_restores_diagonal(self):
        """set_identity() restores 1→1, 2→2, ..., 16→16."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_all()
        m.set_identity()
        for ch in range(1, 17):
            assert m.route(ch) == [ch]

    def test_set_identity_total_routes_16(self):
        """After set_identity(), total_routes() is 16."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_all()
        m.set_identity()
        assert m.total_routes() == 16

    def test_set_identity_clears_extra_routes(self):
        """set_identity() removes non-identity routes."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.set_broadcast(1)  # 1 → all 16 channels
        m.set_identity()
        assert m.route(1) == [1]


class TestRoutingMatrixSetBroadcast:
    """Test set_broadcast() method."""

    def test_set_broadcast_routes_to_all_16(self):
        """set_broadcast(1) makes route(1) == [1..16]."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_row(1)
        m.set_broadcast(1)
        assert sorted(m.route(1)) == list(range(1, 17))

    def test_set_broadcast_single_channel(self):
        """set_broadcast(5) only affects channel 5."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_all()
        m.set_broadcast(5)
        assert sorted(m.route(5)) == list(range(1, 17))
        assert m.route(4) == []
        assert m.route(6) == []

    def test_set_broadcast_total_routes(self):
        """set_broadcast(1) on clear_all adds 16 routes."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_all()
        m.set_broadcast(1)
        assert m.total_routes() == 16

    def test_set_broadcast_clamps_channel(self):
        """set_broadcast clamps channel to 1..16."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_all()
        m.set_broadcast(20)
        # Should have clamped to 16
        assert sorted(m.route(16)) == list(range(1, 17))


class TestRoutingMatrixSetMerge:
    """Test set_merge() method."""

    def test_set_merge_all_to_single(self):
        """set_merge(5) makes all input channels route to 5."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_all()
        m.set_merge(5)
        for in_ch in range(1, 17):
            assert m.is_routed(in_ch, 5) is True

    def test_set_merge_single_output(self):
        """set_merge(5) only adds 5 to routes (doesn't remove others)."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_all()
        m.set_merge(5)
        # All 16 channels should have 5 as a route
        for in_ch in range(1, 17):
            assert 5 in m.route(in_ch)

    def test_set_merge_total_routes(self):
        """set_merge(5) on clear_all adds 16 routes."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_all()
        m.set_merge(5)
        assert m.total_routes() == 16

    def test_set_merge_clamps_channel(self):
        """set_merge clamps output channel to 1..16."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_all()
        m.set_merge(20)
        # Should have clamped to 16
        for in_ch in range(1, 17):
            assert m.is_routed(in_ch, 16) is True


class TestRoutingMatrixTotalRoutes:
    """Test total_routes() method."""

    def test_total_routes_default_16(self):
        """Default identity matrix has 16 routes."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        assert m.total_routes() == 16

    def test_total_routes_zero_after_clear_all(self):
        """After clear_all(), total_routes() is 0."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_all()
        assert m.total_routes() == 0

    def test_total_routes_counts_all_true(self):
        """total_routes() counts every True entry."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_all()
        m.set_route(1, 1, True)
        m.set_route(1, 2, True)
        m.set_route(2, 5, True)
        assert m.total_routes() == 3


class TestRoutingMatrixSerialization:
    """Test RoutingMatrix to_dict/from_dict."""

    def test_to_dict_contains_expected_keys(self):
        """to_dict() returns dict with 'enabled', 'matrix', 'pass_through_unrouted'."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        d = m.to_dict()
        assert "enabled" in d
        assert "matrix" in d
        assert "pass_through_unrouted" in d

    def test_to_dict_preserves_values(self):
        """to_dict() preserves enabled, matrix, and pass_through_unrouted."""
        cfg = RoutingMatrixConfig(enabled=True, pass_through_unrouted=True)
        m = RoutingMatrix(cfg)
        d = m.to_dict()
        assert d["enabled"] is True
        assert d["pass_through_unrouted"] is True

    def test_from_dict_restores_instance(self):
        """from_dict() creates RoutingMatrix with same state as source."""
        cfg = RoutingMatrixConfig(enabled=True, pass_through_unrouted=True)
        m1 = RoutingMatrix(cfg)
        m1.set_route(1, 5, True)
        d = m1.to_dict()
        m2 = RoutingMatrix.from_dict(d)
        assert m2.enabled == m1.enabled
        assert m2.pass_through_unrouted == m1.pass_through_unrouted
        assert m2.is_routed(1, 5) == m1.is_routed(1, 5)

    def test_round_trip_serialization(self):
        """Serialize → deserialize preserves all state."""
        cfg = RoutingMatrixConfig(enabled=True)
        m1 = RoutingMatrix(cfg)
        m1.clear_all()
        m1.set_broadcast(3)
        m1.set_merge(7)
        d = m1.to_dict()
        m2 = RoutingMatrix.from_dict(d)
        assert m2.total_routes() == m1.total_routes()
        for ch in range(1, 17):
            assert m2.route(ch) == m1.route(ch)


class TestRoutingMatrixEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_large_negative_channel_clamped(self):
        """route(-100) clamps to 1."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        assert m.route(-100) == [1]

    def test_large_positive_channel_clamped(self):
        """route(1000) clamps to 16."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        assert m.route(1000) == [16]

    def test_multiple_set_route_calls_cumulative(self):
        """Multiple set_route calls add to routes."""
        cfg = RoutingMatrixConfig()
        m = RoutingMatrix(cfg)
        m.clear_row(1)
        m.set_route(1, 1, True)
        m.set_route(1, 8, True)
        m.set_route(1, 16, True)
        assert sorted(m.route(1)) == [1, 8, 16]

    def test_pass_through_unrouted_flag_respected(self):
        """pass_through_unrouted flag changes route() behavior."""
        cfg_no_pt = RoutingMatrixConfig(pass_through_unrouted=False)
        cfg_pt = RoutingMatrixConfig(pass_through_unrouted=True)
        m_no_pt = RoutingMatrix(cfg_no_pt)
        m_pt = RoutingMatrix(cfg_pt)
        m_no_pt.clear_row(1)
        m_pt.clear_row(1)
        assert m_no_pt.route(1) == []
        assert m_pt.route(1) == [1]

    def test_empty_row_behavior_consistent(self):
        """Clearing a row consistently returns [] or [ch] based on pass_through."""
        cfg = RoutingMatrixConfig(pass_through_unrouted=False)
        m = RoutingMatrix(cfg)
        m.clear_all()
        for ch in range(1, 17):
            assert m.route(ch) == []
