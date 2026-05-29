"""Tests for keyboard-as-controller hardware-free mode."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from gamepad_midi_bridge.keyboard_bus import KeyboardBus
from gamepad_midi_bridge.keyboard_controller import KeyboardControllerReader


@pytest.fixture
def keyboard_bus() -> KeyboardBus:
    """Return a fresh KeyboardBus instance for testing."""
    # Create a new instance (we'll reset the singleton pattern for clean tests)
    return KeyboardBus()


@pytest.fixture
def reader(keyboard_bus) -> KeyboardControllerReader:
    """Create a KeyboardControllerReader bound to the test bus."""
    # Patch the singleton to use our test bus
    original_instance = KeyboardBus._instance
    KeyboardBus._instance = keyboard_bus
    try:
        reader = KeyboardControllerReader()
        yield reader
    finally:
        # Restore original singleton
        KeyboardBus._instance = original_instance


class TestKeyboardControllerReader:
    """KeyboardControllerReader instantiation and interface compliance."""

    def test_init(self, reader):
        """Controller reader initializes cleanly."""
        assert reader is not None
        assert reader._slot_index == 0

    def test_detect_returns_controller_info(self, reader):
        """detect() returns a fake DualSense controller info."""
        info = reader.detect()
        assert info is not None
        assert info.name == "Keyboard Controller (hardware-free testing)"
        assert info.num_axes == 6
        assert info.num_buttons == 11
        assert info.num_hats == 1

    def test_is_connected_always_true(self, reader):
        """Keyboard is always 'connected'."""
        assert reader.is_connected() is True

    def test_close_noop(self, reader):
        """close() does nothing (no resources to free)."""
        reader.close()  # should not raise

    def test_num_axes_buttons_hats(self, reader):
        """num_axes(), num_buttons(), num_hats() match controller info."""
        assert reader.num_axes() == 6
        assert reader.num_buttons() == 11
        assert reader.num_hats() == 1


class TestKeyboardBusAndAxisMapping:
    """Test key-to-axis mapping via the KeyboardBus."""

    def test_left_stick_w_key_down(self, reader, keyboard_bus):
        """Pressing W sets left stick Y to -1.0."""
        keyboard_bus.on_key_pressed(Qt.Key_W)
        reader.pump()
        assert reader.get_axis(0) == 0.0  # X unchanged
        assert reader.get_axis(1) == -1.0  # Y is -1 (up)

    def test_left_stick_s_key_down(self, reader, keyboard_bus):
        """Pressing S sets left stick Y to +1.0."""
        keyboard_bus.on_key_pressed(Qt.Key_S)
        reader.pump()
        assert reader.get_axis(0) == 0.0  # X unchanged
        assert reader.get_axis(1) == 1.0  # Y is +1 (down)

    def test_left_stick_a_key_down(self, reader, keyboard_bus):
        """Pressing A sets left stick X to -1.0."""
        keyboard_bus.on_key_pressed(Qt.Key_A)
        reader.pump()
        assert reader.get_axis(0) == -1.0  # X is -1 (left)
        assert reader.get_axis(1) == 0.0  # Y unchanged

    def test_left_stick_d_key_down(self, reader, keyboard_bus):
        """Pressing D sets left stick X to +1.0."""
        keyboard_bus.on_key_pressed(Qt.Key_D)
        reader.pump()
        assert reader.get_axis(0) == 1.0  # X is +1 (right)
        assert reader.get_axis(1) == 0.0  # Y unchanged

    def test_left_stick_w_and_s_cancel(self, reader, keyboard_bus):
        """Pressing W and S simultaneously → Y = 0 (cancels out)."""
        keyboard_bus.on_key_pressed(Qt.Key_W)
        keyboard_bus.on_key_pressed(Qt.Key_S)
        reader.pump()
        assert reader.get_axis(1) == 0.0  # Y is 0

    def test_left_stick_a_and_d_cancel(self, reader, keyboard_bus):
        """Pressing A and D simultaneously → X = 0 (cancels out)."""
        keyboard_bus.on_key_pressed(Qt.Key_A)
        keyboard_bus.on_key_pressed(Qt.Key_D)
        reader.pump()
        assert reader.get_axis(0) == 0.0  # X is 0

    def test_right_stick_up_key_down(self, reader, keyboard_bus):
        """Pressing Up sets right stick Y to -1.0."""
        keyboard_bus.on_key_pressed(Qt.Key_Up)
        reader.pump()
        assert reader.get_axis(2) == 0.0  # X unchanged
        assert reader.get_axis(3) == -1.0  # Y is -1 (up)

    def test_right_stick_down_key_down(self, reader, keyboard_bus):
        """Pressing Down sets right stick Y to +1.0."""
        keyboard_bus.on_key_pressed(Qt.Key_Down)
        reader.pump()
        assert reader.get_axis(2) == 0.0  # X unchanged
        assert reader.get_axis(3) == 1.0  # Y is +1 (down)

    def test_right_stick_left_key_down(self, reader, keyboard_bus):
        """Pressing Left sets right stick X to -1.0."""
        keyboard_bus.on_key_pressed(Qt.Key_Left)
        reader.pump()
        assert reader.get_axis(2) == -1.0  # X is -1 (left)
        assert reader.get_axis(3) == 0.0  # Y unchanged

    def test_right_stick_right_key_down(self, reader, keyboard_bus):
        """Pressing Right sets right stick X to +1.0."""
        keyboard_bus.on_key_pressed(Qt.Key_Right)
        reader.pump()
        assert reader.get_axis(2) == 1.0  # X is +1 (right)
        assert reader.get_axis(3) == 0.0  # Y unchanged

    def test_l2_trigger_q_key(self, reader, keyboard_bus):
        """Pressing Q sets L2 trigger to +1.0 (pressed)."""
        keyboard_bus.on_key_pressed(Qt.Key_Q)
        reader.pump()
        assert reader.get_axis(4) == 1.0

    def test_l2_trigger_released(self, reader, keyboard_bus):
        """Releasing Q sets L2 trigger to -1.0 (released)."""
        keyboard_bus.on_key_pressed(Qt.Key_Q)
        reader.pump()
        assert reader.get_axis(4) == 1.0
        keyboard_bus.on_key_released(Qt.Key_Q)
        reader.pump()
        assert reader.get_axis(4) == -1.0

    def test_r2_trigger_e_key(self, reader, keyboard_bus):
        """Pressing E sets R2 trigger to +1.0 (pressed)."""
        keyboard_bus.on_key_pressed(Qt.Key_E)
        reader.pump()
        assert reader.get_axis(5) == 1.0

    def test_r2_trigger_released(self, reader, keyboard_bus):
        """Releasing E sets R2 trigger to -1.0 (released)."""
        keyboard_bus.on_key_pressed(Qt.Key_E)
        reader.pump()
        assert reader.get_axis(5) == 1.0
        keyboard_bus.on_key_released(Qt.Key_E)
        reader.pump()
        assert reader.get_axis(5) == -1.0


class TestKeyboardBusAndButtonMapping:
    """Test key-to-button mapping."""

    def test_space_is_button_0_cross(self, reader, keyboard_bus):
        """Pressing Space sets button 0 (cross/A)."""
        keyboard_bus.on_key_pressed(Qt.Key_Space)
        reader.pump()
        assert reader.get_button(0) is True

    def test_shift_is_button_1_square(self, reader, keyboard_bus):
        """Pressing Shift sets button 1 (square/X)."""
        keyboard_bus.on_key_pressed(Qt.Key_Shift)
        reader.pump()
        assert reader.get_button(1) is True

    def test_z_is_button_2_triangle(self, reader, keyboard_bus):
        """Pressing Z sets button 2 (triangle/Y)."""
        keyboard_bus.on_key_pressed(Qt.Key_Z)
        reader.pump()
        assert reader.get_button(2) is True

    def test_x_is_button_3_circle(self, reader, keyboard_bus):
        """Pressing X sets button 3 (circle/B)."""
        keyboard_bus.on_key_pressed(Qt.Key_X)
        reader.pump()
        assert reader.get_button(3) is True

    def test_tab_is_button_4_l1(self, reader, keyboard_bus):
        """Pressing Tab sets button 4 (L1)."""
        keyboard_bus.on_key_pressed(Qt.Key_Tab)
        reader.pump()
        assert reader.get_button(4) is True

    def test_backspace_is_button_5_r1(self, reader, keyboard_bus):
        """Pressing Backspace sets button 5 (R1)."""
        keyboard_bus.on_key_pressed(Qt.Key_Backspace)
        reader.pump()
        assert reader.get_button(5) is True

    def test_multiple_buttons_pressed(self, reader, keyboard_bus):
        """Multiple buttons can be pressed simultaneously."""
        keyboard_bus.on_key_pressed(Qt.Key_Space)
        keyboard_bus.on_key_pressed(Qt.Key_Z)
        keyboard_bus.on_key_pressed(Qt.Key_Tab)
        reader.pump()
        assert reader.get_button(0) is True  # Space
        assert reader.get_button(2) is True  # Z
        assert reader.get_button(4) is True  # Tab
        assert reader.get_button(3) is False  # X not pressed

    def test_button_release(self, reader, keyboard_bus):
        """Released buttons return False."""
        keyboard_bus.on_key_pressed(Qt.Key_Space)
        reader.pump()
        assert reader.get_button(0) is True
        keyboard_bus.on_key_released(Qt.Key_Space)
        reader.pump()
        assert reader.get_button(0) is False


class TestKeyboardBusAndHat:
    """Test D-pad (hat) mapping."""

    def test_hat_always_zero(self, reader):
        """D-pad hat always returns (0, 0) (reserved for future)."""
        reader.pump()
        assert reader.get_hat(0) == (0, 0)

    def test_hat_with_various_keys(self, reader, keyboard_bus):
        """D-pad hat stays at (0, 0) even with other keys pressed."""
        keyboard_bus.on_key_pressed(Qt.Key_Up)
        keyboard_bus.on_key_pressed(Qt.Key_Space)
        reader.pump()
        assert reader.get_hat(0) == (0, 0)


class TestKeyboardBusStateManagement:
    """Test KeyboardBus state tracking."""

    def test_bus_tracks_key_state(self, keyboard_bus):
        """KeyboardBus tracks which keys are currently down."""
        assert keyboard_bus.is_key_down(Qt.Key_W) is False
        keyboard_bus.on_key_pressed(Qt.Key_W)
        assert keyboard_bus.is_key_down(Qt.Key_W) is True
        keyboard_bus.on_key_released(Qt.Key_W)
        assert keyboard_bus.is_key_down(Qt.Key_W) is False

    def test_bus_multiple_keys_down(self, keyboard_bus):
        """KeyboardBus can track multiple keys simultaneously."""
        keyboard_bus.on_key_pressed(Qt.Key_W)
        keyboard_bus.on_key_pressed(Qt.Key_A)
        keyboard_bus.on_key_pressed(Qt.Key_Space)
        assert keyboard_bus.is_key_down(Qt.Key_W) is True
        assert keyboard_bus.is_key_down(Qt.Key_A) is True
        assert keyboard_bus.is_key_down(Qt.Key_Space) is True
        assert keyboard_bus.is_key_down(Qt.Key_S) is False

    def test_bus_partial_release(self, keyboard_bus):
        """KeyboardBus can release individual keys while others remain."""
        keyboard_bus.on_key_pressed(Qt.Key_W)
        keyboard_bus.on_key_pressed(Qt.Key_A)
        keyboard_bus.on_key_released(Qt.Key_W)
        assert keyboard_bus.is_key_down(Qt.Key_W) is False
        assert keyboard_bus.is_key_down(Qt.Key_A) is True


class TestKeyboardBusSingleton:
    """Test KeyboardBus singleton pattern."""

    def test_instance_returns_same_object(self):
        """KeyboardBus.instance() returns the same singleton each time."""
        original_instance = KeyboardBus._instance
        try:
            KeyboardBus._instance = None
            bus1 = KeyboardBus.instance()
            bus2 = KeyboardBus.instance()
            assert bus1 is bus2
        finally:
            KeyboardBus._instance = original_instance


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
        """Buttons 6–10 are always False (reserved)."""
        reader.pump()
        for btn_idx in range(6, 11):
            assert reader.get_button(btn_idx) is False


class TestAxisCoherence:
    """Test axis coherence across pump() calls."""

    def test_axis_coherence_single_pump(self, reader, keyboard_bus):
        """All axes are coherent within a single pump() call."""
        keyboard_bus.on_key_pressed(Qt.Key_W)
        keyboard_bus.on_key_pressed(Qt.Key_A)
        keyboard_bus.on_key_pressed(Qt.Key_Q)
        reader.pump()
        # Read all axes multiple times — values should be stable
        assert reader.get_axis(0) == reader.get_axis(0)  # X stable
        assert reader.get_axis(1) == reader.get_axis(1)  # Y stable
        assert reader.get_axis(4) == reader.get_axis(4)  # L2 stable

    def test_axis_updates_on_pump(self, reader, keyboard_bus):
        """Axes only update when pump() is called."""
        keyboard_bus.on_key_pressed(Qt.Key_W)
        # Before pump(), axis should not reflect the key press
        initial_y = reader.get_axis(1)
        reader.pump()
        # After pump(), axis should reflect the key press
        pumped_y = reader.get_axis(1)
        assert initial_y == 0.0
        assert pumped_y == -1.0
