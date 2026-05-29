"""Tests for the global command palette (Cmd-K / Ctrl-K)."""
from __future__ import annotations

import pytest


def _qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _has_pyside6() -> bool:
    try:
        from PySide6.QtWidgets import QApplication
        return True
    except ImportError:
        return False


skip_no_qt = pytest.mark.skipif(not _has_pyside6(), reason="PySide6 not available")


# ---------------------------------------------------------------------------
# CommandPalette instantiation
# ---------------------------------------------------------------------------

@skip_no_qt
def test_command_palette_creates_without_crash():
    """CommandPalette(commands=[]) does not raise."""
    _qapp()
    from gamepad_midi_bridge.ui.command_palette import Command, CommandPalette

    palette = CommandPalette([], parent=None)
    assert palette is not None
    palette.close()


@skip_no_qt
def test_command_palette_with_commands():
    """CommandPalette populated with commands renders without crash."""
    _qapp()
    from gamepad_midi_bridge.ui.command_palette import Command, CommandPalette

    fired = []
    cmds = [
        Command("Start bridge", "Start MIDI bridging", lambda: fired.append("start")),
        Command("Stop bridge",  "Stop MIDI bridging",  lambda: fired.append("stop")),
    ]
    palette = CommandPalette(cmds, parent=None)
    assert palette._list.count() == 2
    palette.close()


# ---------------------------------------------------------------------------
# Search filtering
# ---------------------------------------------------------------------------

@skip_no_qt
def test_search_start_returns_start_command():
    """Typing 'start' shows commands with 'Start' in the title."""
    _qapp()
    from gamepad_midi_bridge.ui.command_palette import Command, CommandPalette

    cmds = [
        Command("Start bridge", "Start MIDI bridging", lambda: None),
        Command("Stop bridge",  "Stop MIDI bridging",  lambda: None),
        Command("Toggle Console", "Show/hide console",  lambda: None),
    ]
    palette = CommandPalette(cmds)
    palette._refresh_list("start")

    titles = [palette._list.item(i).text() for i in range(palette._list.count())]
    assert any("Start" in t for t in titles), f"Expected 'Start' in results, got {titles}"
    palette.close()


@skip_no_qt
def test_search_empty_returns_all_commands():
    """Empty query shows all commands."""
    _qapp()
    from gamepad_midi_bridge.ui.command_palette import Command, CommandPalette

    cmds = [Command(f"Command {i}", "", lambda: None) for i in range(5)]
    palette = CommandPalette(cmds)
    palette._refresh_list("")
    assert palette._list.count() == 5
    palette.close()


@skip_no_qt
def test_search_no_match_returns_empty():
    """Query with no match produces an empty list."""
    _qapp()
    from gamepad_midi_bridge.ui.command_palette import Command, CommandPalette

    cmds = [Command("Start bridge", "desc", lambda: None)]
    palette = CommandPalette(cmds)
    palette._refresh_list("zzznomatch")
    assert palette._list.count() == 0
    palette.close()


# ---------------------------------------------------------------------------
# Fuzzy match ordering
# ---------------------------------------------------------------------------

@skip_no_qt
def test_fuzzy_order_toggle_split_before_word_substring():
    """'tog' matches Toggle Split at a higher score than a substring-only match."""
    _qapp()
    from gamepad_midi_bridge.ui.command_palette import Command, CommandPalette, _score

    # "Toggle Split view" starts with "tog" so scores 3 (exact-prefix rule).
    assert _score("tog", "Toggle Split view") == 3
    # "Photography settings" contains "tog" as a substring (phot-og-raphy), scores 1.
    assert _score("tog", "Photography settings") == 1

    # Toggle Split (score 3) should sort before the substring match (score 1).
    cmds = [
        Command("Photography settings", "desc", lambda: None),
        Command("Toggle Split view",    "desc", lambda: None),
    ]
    palette = CommandPalette(cmds)
    palette._refresh_list("tog")

    assert palette._list.count() == 2
    first_title = palette._list.item(0).text()
    assert first_title == "Toggle Split view", (
        f"Expected 'Toggle Split view' first, got '{first_title}'"
    )
    palette.close()


# ---------------------------------------------------------------------------
# Scoring unit tests (no Qt needed)
# ---------------------------------------------------------------------------

def test_score_exact_prefix():
    from gamepad_midi_bridge.ui.command_palette import _score
    assert _score("start", "Start bridge") == 3


def test_score_word_prefix():
    from gamepad_midi_bridge.ui.command_palette import _score
    assert _score("bri", "Start bridge") == 2


def test_score_substring():
    from gamepad_midi_bridge.ui.command_palette import _score
    # "tog" appears inside "photography" (phot-og-raphy)
    assert _score("tog", "Photography settings") == 1


def test_score_no_match():
    from gamepad_midi_bridge.ui.command_palette import _score
    assert _score("xyz", "Start bridge") == 0


def test_score_empty_query_matches_all():
    from gamepad_midi_bridge.ui.command_palette import _score
    assert _score("", "Anything at all") > 0


# ---------------------------------------------------------------------------
# Callback execution
# ---------------------------------------------------------------------------

@skip_no_qt
def test_enter_triggers_callback():
    """Selecting a command and calling _execute_current fires its callback."""
    _qapp()
    from gamepad_midi_bridge.ui.command_palette import Command, CommandPalette

    fired = []
    cmds = [
        Command("Start bridge", "Start MIDI bridging", lambda: fired.append("start")),
    ]
    palette = CommandPalette(cmds)
    palette._refresh_list("")
    palette._list.setCurrentRow(0)

    # Override accept() so the dialog doesn't try to close in a test context.
    palette.accept = lambda: None  # type: ignore[method-assign]
    palette._execute_current()

    assert fired == ["start"]
    palette.close()
