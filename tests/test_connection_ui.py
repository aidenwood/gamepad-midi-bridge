"""Native-window probes use the launcher's os._exit convention for Qt teardown."""

import os
import subprocess
import sys
import textwrap
from unittest.mock import Mock

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QDialog, QWidget

from gamepad_midi_bridge.multi import SlotConnection
from gamepad_midi_bridge.ui.calibration_dialog import CalibrationToast


def test_real_window_console_limits_and_controller_status(tmp_path):
    # MainWindow is deliberately checked in its own process: the production
    # launcher also avoids PySide's interpreter-finalization segfault path.
    script = textwrap.dedent("""
        import os
        import traceback
        from pathlib import Path
        from unittest.mock import Mock
        from PySide6.QtWidgets import QApplication
        from gamepad_midi_bridge import paths
        folder = Path(os.environ['GMB_TEST_USER_DATA'])
        folder.mkdir(parents=True, exist_ok=True)
        paths.user_data_dir = lambda: folder
        from gamepad_midi_bridge.ui import main_window
        from gamepad_midi_bridge.multi import SlotConnection
        main_window.UpdateChecker.check_async = lambda self: None
        main_window.MainWindow._show_onboarding = lambda self: None
        app = QApplication([])
        try:
            win = main_window.MainWindow()
            win.resize(1200, 900)
            win.show()
            app.processEvents()
            win._midi_log_panel.set_collapsed(True)
            win._log_console.set_collapsed(False)
            app.processEvents()
            win._body_splitter.moveSplitter(1, 1)
            app.processEvents()
            height = win._body_splitter.sizes()[1]
            assert win.height() // 2 - 12 <= height <= win.height() // 2, height
            assert win._bottom_dock.height() <= win.height() // 2
            assert win._midi_log_panel.is_collapsed()
            win._log_console.set_collapsed_silent(True)
            win._midi_log_panel.set_collapsed_silent(True)
            win._body_splitter.setSizes([450, 250])
            win._on_body_splitter_moved(450, 1)
            assert not win._log_console.is_collapsed()
            assert win._bottom_open_height > win._log_console.header_height()
            win._multi.connections = [
                SlotConnection(name='DualSense', phase='Bridging', port='MIDI 1', running=True, messages=12),
                SlotConnection(name='Xbox', phase='Error', channel=2, error='Output unavailable'),
            ]
            win._popup = Mock()
            win._open_status_dropdown()
            menu = win._popup.call_args.args[0]
            text = '\\n'.join(action.text() for action in menu.actions())
            for expected in ['DualSense', 'Xbox', 'MIDI 1', 'MIDI channel 2', '12', 'Output unavailable']:
                assert expected in text, expected
            win._multi.shutdown()
            print('Window geometry and per-controller status verified', flush=True)
        except BaseException:
            traceback.print_exc()
            os._exit(1)
        os._exit(0)
    """)
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "GMB_UI_SMOKE": "1",
        "GMB_TEST_USER_DATA": str(tmp_path),
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_calibration_is_non_modal_and_result_dismisses_automatically(qapp):
    parent = QWidget()
    parent.resize(800, 600)
    parent.show()
    toast = CalibrationToast(parent)
    assert not isinstance(toast, QDialog)
    toast.on_progress(0.2)
    assert toast.isVisible()
    assert "Keep your hands off" in toast._title.text()
    toast.on_done({0: 0.01}, [], [])
    assert toast._title.text() == "Sticks ready"
    assert toast._dismiss.isActive()
    parent.close()
    parent.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_reconnect_does_not_stop_the_other_controller(monkeypatch):
    from types import SimpleNamespace

    from gamepad_midi_bridge.ui import main_window

    first = SimpleNamespace(
        thread=SimpleNamespace(isRunning=lambda: False), worker=SimpleNamespace(), start=Mock()
    )
    second = SimpleNamespace(
        thread=SimpleNamespace(isRunning=lambda: True), worker=SimpleNamespace(), start=Mock()
    )
    states = [
        SlotConnection(name="DualSense", phase="Disconnected", instance_id=10),
        SlotConnection(name="Xbox", phase="Bridging", instance_id=22, running=True),
    ]
    fake = SimpleNamespace(
        _multi=SimpleNamespace(connections=states, bridges=[first, second]),
        _reconnect_retry_timer=Mock(),
    )
    monkeypatch.setattr(
        main_window,
        "available_devices",
        lambda: [
            SimpleNamespace(name="Xbox", instance_id=22),
            SimpleNamespace(name="DualSense", instance_id=33),
        ],
    )
    main_window.MainWindow._attempt_reconnect(fake)
    first.start.assert_called_once()
    second.start.assert_not_called()
    assert first.worker._controller_instance_id == 33
