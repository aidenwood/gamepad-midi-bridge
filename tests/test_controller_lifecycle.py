"""Device discovery must not close a live controller or change its identity."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from gamepad_midi_bridge import controller


class Device:
    def __init__(self, instance):
        self.instance = instance
        self.initialized = True

    def init(self):
        self.initialized = True

    def quit(self):
        self.initialized = False

    def get_init(self):
        return self.initialized

    def get_instance_id(self):
        return self.instance

    def get_name(self):
        return f"Controller {self.instance}"

    def get_guid(self):
        return "030000004c050000e60c000000000000"

    def get_numaxes(self):
        if not self.initialized:
            raise RuntimeError("Joystick not initialized")
        return 6

    def get_numbuttons(self):
        return 17

    def get_numhats(self):
        return 0

    def get_axis(self, _index):
        return self.instance / 100


@pytest.fixture
def devices(monkeypatch):
    attached = [Device(11), Device(22)]
    joystick = SimpleNamespace(
        get_init=lambda: True,
        init=Mock(),
        quit=Mock(),
        get_count=lambda: len(attached),
        Joystick=lambda index: attached[index],
    )
    fake = SimpleNamespace(
        get_init=lambda: True,
        init=Mock(),
        joystick=joystick,
        event=SimpleNamespace(pump=Mock()),
        error=RuntimeError,
    )
    monkeypatch.setattr(controller, "pygame", fake)
    return attached, fake


def test_count_and_name_queries_preserve_both_live_handles(devices):
    attached, fake = devices
    first, second = controller.ControllerReader(0), controller.ControllerReader(1)
    first.detect()
    second.detect()
    for _ in range(3):
        assert controller.available_count() == 2
        assert len(controller.available_controllers()) == 2
    assert first.get_axis(0) == 0.11
    assert second.get_axis(0) == 0.22
    assert all(device.initialized for device in attached)
    fake.joystick.quit.assert_not_called()


def test_stopping_primary_does_not_close_secondary(devices):
    _, fake = devices
    first, second = controller.ControllerReader(0), controller.ControllerReader(1)
    first.detect()
    second.detect()
    first.close()
    assert second.num_axes() == 6
    assert second.get_axis(0) == 0.22
    fake.joystick.quit.assert_not_called()


def test_remaining_device_survives_index_shift(devices):
    attached, _ = devices
    first, second = controller.ControllerReader(0), controller.ControllerReader(1)
    first.detect()
    second.detect()
    attached.pop(0)
    assert not first.is_connected()
    assert second.is_connected()
    assert second.get_axis(0) == 0.22


def test_selected_instance_is_used_even_if_enumeration_order_changes(devices):
    attached, _ = devices
    reader = controller.ControllerReader(0, instance_id=22)
    attached.reverse()
    assert reader.detect().instance_id == 22
    assert reader.get_axis(0) == 0.22


def test_inventory_can_list_a_stopped_but_still_attached_device(devices):
    reader = controller.ControllerReader(0)
    reader.detect()
    reader.close()
    assert controller.available_count() == 2


def test_failed_start_releases_reader_and_emits_stopped(monkeypatch, qapp):
    from gamepad_midi_bridge import bridge

    reader = SimpleNamespace(detect=lambda: None, close=Mock())
    monkeypatch.setattr(bridge, "ControllerReader", lambda **kwargs: reader)
    worker = bridge.BridgeWorker()
    stopped, errors = [], []
    worker.stopped.connect(lambda: stopped.append(True))
    worker.error.connect(errors.append)
    worker.start()
    assert stopped == [True]
    assert errors and "No controller" in errors[0]
    assert worker._reader is None
    reader.close.assert_called_once()


def test_recalibration_is_requested_without_running_hardware_on_gui_thread(qapp):
    from gamepad_midi_bridge.bridge import BridgeWorker

    worker = BridgeWorker()
    worker._reader = SimpleNamespace()
    worker._running = True
    worker._run_calibration = Mock()
    worker.recalibrate()
    assert worker._recalibrate_requested.is_set()
    worker._run_calibration.assert_not_called()
    assert worker._running
