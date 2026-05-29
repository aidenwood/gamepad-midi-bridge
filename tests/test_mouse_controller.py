"""Tests for mouse-as-controller hardware-free mode."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint

from gamepad_midi_bridge.mouse_bus import MouseBus
from gamepad_midi_bridge.mouse_controller import MouseControllerReader


@pytest.fixture
def mouse_bus() -> MouseBus:
    """Return a fresh MouseBus instance for testing."""
    return MouseBus()


@pytest.fixture
def reader(mouse_bus) -> MouseControllerReader:
    """Create a MouseControllerReader bound to the test bus."""
    # Patch the singleton to use our test bus
    original_instance = MouseBus._instance
    MouseBus._instance = mouse_bus
    try:
        reader = MouseControllerReader()
        yield reader
    finally:
        # Restore original singleton
        MouseBus._instance = original_instance


class TestMouseControllerReader:
    """MouseControllerReader instantiation and interface compliance."""

    def test_init(self, reader):
        """Controller reader initializes cleanly."""
        assert reader is not None
        assert reader._slot_index == 0

    def test_detect_returns_controller_info(self, reader):
        """detect() returns a fake DualSense controller info."""
        info = reader.detect()
        assert info is not None
        assert info.name == "Mouse Controller (hardware-free demo)"
        assert info.num_axes == 6
        assert info.num_buttons == 11
        assert info.num_hats == 1

    def test_is_connected_always_true(self, reader):
        """Mouse is always 'connected'."""
        assert reader.is_connected() is True

    def test_close_noop(self, reader):
        """close() does nothing (no resources to free)."""
        reader.close()  # should not raise

    def test_num_axes_buttons_hats(self, reader):
        """num_axes(), num_buttons(), num_hats() match controller info."""
        assert reader.num_axes() == 6
        assert reader.num_buttons() == 11
        assert reader.num_hats() == 1


class TestMouseBusAndAxisMapping:
    """Test mouse position to axis mapping via the MouseBus."""

    def test_mouse_center_maps_to_zero(self, reader, mouse_bus):
        """Mouse at window center → left stick (0, 0)."""
        center = QPoint(400, 300)
        cursor = QPoint(400, 300)
        mouse_bus.on_mouse_move(center, cursor)
        reader.pump()
        assert reader.get_axis(0) == 0.0  # X
        assert reader.get_axis(1) == 0.0  # Y

    def test_mouse_right_maps_to_positive_x(self, reader, mouse_bus):
        """Mouse right of center → positive X."""
        center = QPoint(400, 300)
        cursor = QPoint(800, 300)
        mouse_bus.on_mouse_move(center, cursor)
        reader.pump()
        assert reader.get_axis(0) == 1.0  # X max
        assert reader.get_axis(1) == 0.0  # Y unchanged

    def test_mouse_left_maps_to_negative_x(self, reader, mouse_bus):
        """Mouse left of center → negative X."""
        center = QPoint(400, 300)
        cursor = QPoint(0, 300)
        mouse_bus.on_mouse_move(center, cursor)
        reader.pump()
        assert reader.get_axis(0) == -1.0  # X min
        assert reader.get_axis(1) == 0.0  # Y unchanged

    def test_mouse_down_maps_to_positive_y(self, reader, mouse_bus):
        """Mouse below center → positive Y."""
        center = QPoint(400, 300)
        cursor = QPoint(400, 700)
        mouse_bus.on_mouse_move(center, cursor)
        reader.pump()
        assert reader.get_axis(0) == 0.0  # X unchanged
        assert reader.get_axis(1) == 1.0  # Y max

    def test_mouse_up_maps_to_negative_y(self, reader, mouse_bus):
        """Mouse above center → negative Y."""
        center = QPoint(400, 300)
        cursor = QPoint(400, -100)
        mouse_bus.on_mouse_move(center, cursor)
        reader.pump()
        assert reader.get_axis(0) == 0.0  # X unchanged
        assert reader.get_axis(1) == -1.0  # Y min

    def test_mouse_diagonal_maps_both_axes(self, reader, mouse_bus):
        """Mouse diagonal from center → both axes set."""
        center = QPoint(400, 300)
        cursor = QPoint(800, 700)
        mouse_bus.on_mouse_move(center, cursor)
        reader.pump()
        assert reader.get_axis(0) == 1.0  # X max
        assert reader.get_axis(1) == 1.0  # Y max

    def test_mouse_clamping_beyond_range(self, reader, mouse_bus):
        """Mouse far beyond range clamps to [-1, +1]."""
        center = QPoint(400, 300)
        cursor = QPoint(2000, 2000)  # Very far right and down
        mouse_bus.on_mouse_move(center, cursor)
        reader.pump()
        assert reader.get_axis(0) == 1.0  # Clamped to max
        assert reader.get_axis(1) == 1.0  # Clamped to max


class TestMouseBusAndButtonMapping:
    """Test mouse button to gamepad button mapping."""

    def test_left_click_is_button_0(self, reader, mouse_bus):
        """Left click → button 0 (cross/A)."""
        mouse_bus.on_button_pressed(0)
        reader.pump()
        assert reader.get_button(0) is True

    def test_right_click_is_button_1(self, reader, mouse_bus):
        """Right click → button 1 (square/X)."""
        mouse_bus.on_button_pressed(1)
        reader.pump()
        assert reader.get_button(1) is True

    def test_middle_click_is_button_4(self, reader, mouse_bus):
        """Middle click → button 4 (L1)."""
        mouse_bus.on_button_pressed(4)
        reader.pump()
        assert reader.get_button(4) is True

    def test_multiple_buttons_pressed(self, reader, mouse_bus):
        """Multiple mouse buttons can be pressed simultaneously."""
        mouse_bus.on_button_pressed(0)  # Left
        mouse_bus.on_button_pressed(1)  # Right
        mouse_bus.on_button_pressed(4)  # Middle
        reader.pump()
        assert reader.get_button(0) is True  # Left
        assert reader.get_button(1) is True  # Right
        assert reader.get_button(4) is True  # Middle

    def test_button_release(self, reader, mouse_bus):
        """Released buttons return False."""
        mouse_bus.on_button_pressed(0)
        reader.pump()
        assert reader.get_button(0) is True
        mouse_bus.on_button_released(0)
        reader.pump()
        assert reader.get_button(0) is False


class TestMouseWheelMapping:
    """Test mouse wheel to L2 trigger mapping."""

    def test_wheel_scroll_up_is_l2_pressed(self, reader, mouse_bus):
        """Mouse wheel up → L2 trigger = +1.0."""
        mouse_bus.on_wheel_scroll(120)  # Positive delta = up
        reader.pump()
        assert reader.get_axis(4) == 1.0

    def test_wheel_scroll_down_is_l2_released(self, reader, mouse_bus):
        """Mouse wheel down → L2 trigger = -1.0."""
        mouse_bus.on_wheel_scroll(-120)  # Negative delta = down
        reader.pump()
        assert reader.get_axis(4) == -1.0

    def test_wheel_scroll_zero_is_l2_neutral(self, reader, mouse_bus):
        """Mouse wheel neutral → L2 trigger = 0.0."""
        mouse_bus.on_wheel_scroll(0)
        reader.pump()
        assert reader.get_axis(4) == 0.0

    def test_wheel_scroll_up_and_axis_movement(self, reader, mouse_bus):
        """Wheel and stick movement work independently."""
        center = QPoint(400, 300)
        cursor = QPoint(600, 300)
        mouse_bus.on_mouse_move(center, cursor)
        mouse_bus.on_wheel_scroll(120)
        reader.pump()
        assert reader.get_axis(0) == 0.5  # X from mouse
        assert reader.get_axis(4) == 1.0  # L2 from wheel


class TestMouseBusStateManagement:
    """Test MouseBus state tracking."""

    def test_bus_tracks_button_state(self, mouse_bus):
        """MouseBus tracks which buttons are currently down."""
        assert mouse_bus.is_button_down(0) is False
        mouse_bus.on_button_pressed(0)
        assert mouse_bus.is_button_down(0) is True
        mouse_bus.on_button_released(0)
        assert mouse_bus.is_button_down(0) is False

    def test_bus_tracks_position(self, mouse_bus):
        """MouseBus tracks normalized cursor position."""
        center = QPoint(400, 300)
        cursor = QPoint(800, 700)
        mouse_bus.on_mouse_move(center, cursor)
        x, y = mouse_bus.get_position()
        assert x == 1.0
        assert y == 1.0

    def test_bus_multiple_buttons_down(self, mouse_bus):
        """MouseBus can track multiple buttons simultaneously."""
        mouse_bus.on_button_pressed(0)
        mouse_bus.on_button_pressed(1)
        mouse_bus.on_button_pressed(4)
        assert mouse_bus.is_button_down(0) is True
        assert mouse_bus.is_button_down(1) is True
        assert mouse_bus.is_button_down(4) is True


class TestMouseBusSingleton:
    """Test MouseBus singleton pattern."""

    def test_instance_returns_same_object(self):
        """MouseBus.instance() returns the same singleton each time."""
        original_instance = MouseBus._instance
        try:
            MouseBus._instance = None
            bus1 = MouseBus.instance()
            bus2 = MouseBus.instance()
            assert bus1 is bus2
        finally:
            MouseBus._instance = original_instance


class TestOutOfBoundsAndEdgeCases:
    """Test edge cases and out-of-bounds access."""

    def test_get_axis_out_of_bounds(self, reader):
        """get_axis() with invalid index returns 0.0."""
        reader.pump()
        assert reader.get_axis(99) == 0.0
        assert reader.get_axis(-1) == 0.0

    def test_get_button_out_of_bounds(self, reader):
        """get_button() with invalid index returns False."""
        reader.pump()
        assert reader.get_button(99) is False
        assert reader.get_button(-1) is False

    def test_get_hat_with_various_indices(self, reader):
        """get_hat() returns (0, 0) regardless of index."""
        reader.pump()
        assert reader.get_hat(0) == (0, 0)
        assert reader.get_hat(1) == (0, 0)
        assert reader.get_hat(99) == (0, 0)

    def test_unused_buttons_always_false(self, reader):
        """Buttons 2–3 and 5–10 are always False (unmapped)."""
        reader.pump()
        unmapped = [2, 3, 5, 6, 7, 8, 9, 10]
        for btn_idx in unmapped:
            assert reader.get_button(btn_idx) is False


class TestAxisCoherence:
    """Test axis coherence across pump() calls."""

    def test_axis_coherence_single_pump(self, reader, mouse_bus):
        """All axes are coherent within a single pump() call."""
        center = QPoint(400, 300)
        cursor = QPoint(600, 450)
        mouse_bus.on_mouse_move(center, cursor)
        mouse_bus.on_wheel_scroll(120)
        reader.pump()
        # Read all axes multiple times — values should be stable
        assert reader.get_axis(0) == reader.get_axis(0)  # X stable
        assert reader.get_axis(1) == reader.get_axis(1)  # Y stable
        assert reader.get_axis(4) == reader.get_axis(4)  # L2 stable

    def test_axis_updates_on_pump(self, reader, mouse_bus):
        """Axes only update when pump() is called."""
        center = QPoint(400, 300)
        cursor = QPoint(800, 300)
        mouse_bus.on_mouse_move(center, cursor)
        # Before pump(), axis should not reflect the mouse move
        initial_x = reader.get_axis(0)
        reader.pump()
        # After pump(), axis should reflect the mouse move
        pumped_x = reader.get_axis(0)
        assert initial_x == 0.0
        assert pumped_x == 1.0
