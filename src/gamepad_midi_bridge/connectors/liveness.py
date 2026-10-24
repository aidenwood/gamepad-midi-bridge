"""Is the host app actually running right now?

The connector layer already answers "is the integration installed" —
``Connector.verify()`` stats the Remote Script / XML / .toe and reports
verified, outdated or missing. That is install state, not connection state.
A user whose Ableton is closed, or who installed the script six months ago
and has not opened Live since, sees exactly the same green tick as someone
mid-set.

This module adds the missing signal: whether the host process exists on this
machine at this moment. Combined with the install check it produces a status
that distinguishes the three states a user actually cares about —

    not installed  → nothing will work; run the installer
    installed      → will work once you open the app
    running        → the app is open and the integration is in place

Deliberately does NOT claim "connected". Knowing that a host has opened our
virtual MIDI port needs either a handshake the integration does not yet send,
or client enumeration that python-rtmidi does not expose. Reporting "running"
and meaning it is more useful than reporting "connected" and guessing — the
whole point of a status light is that it can be trusted.

Pure stdlib, no Qt. The process list is injectable so the logic is testable
without spawning anything.
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from enum import Enum


class HostState(str, Enum):
    """What we can honestly say about a host integration."""

    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"      # present, host not running
    RUNNING = "running"          # host process is up and integration present
    STALE = "stale"              # installed but the file is older than expected
    UNKNOWN = "unknown"          # probe failed; never pretend


# Process-name fragments per connector slug, matched case-insensitively
# against the running process list. Kept here rather than forked from
# daw_detector's app table because that table describes *bundles on disk*
# ("Ableton Live*.app") and these are *process names*, which differ —
# TouchDesigner's binary is "TouchDesigner" but Resolume's is "Arena".
_PROCESS_FRAGMENTS: dict[str, tuple[str, ...]] = {
    "ableton": ("ableton live", "live.exe"),
    "resolume": ("resolume", "arena", "avenue"),
    "touchdesigner": ("touchdesigner",),
    "madmapper": ("madmapper",),
    "vdmx": ("vdmx",),
    "obs": ("obs",),
    "reaper": ("reaper",),
}


@dataclass(frozen=True)
class HostStatus:
    """A status a UI can render without further interpretation."""

    slug: str
    state: HostState
    detail: str

    @property
    def is_live(self) -> bool:
        """True only when the host is open AND the integration is in place."""
        return self.state is HostState.RUNNING


def _list_processes() -> list[str]:
    """Running process names, lowercased. Empty list if the probe fails.

    Never raises: a status light that crashes the app is worse than one that
    says "unknown".
    """
    try:
        if sys.platform == "win32":
            out = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True, text=True, timeout=4, check=False,
            ).stdout
        else:
            out = subprocess.run(
                ["ps", "-axco", "command"],
                capture_output=True, text=True, timeout=4, check=False,
            ).stdout
        return [line.strip().lower() for line in out.splitlines() if line.strip()]
    except Exception:
        return []


def _name_matches(name: str, fragment: str) -> bool:
    """Word-boundary match, not a substring one.

    A plain `fragment in name` test looked fine until it was run against a
    real process list: "obs" matched Obsidian, jobs and observer, and "arena"
    matched arenanet. A status light that goes green because someone has a
    note-taking app open is worse than no status light.

    So: the name must equal the fragment, or begin with it followed by a
    non-alphanumeric character — which keeps "ableton live 12" matching
    "ableton live" while rejecting "obsidian".
    """
    if name == fragment:
        return True
    if not name.startswith(fragment):
        return False
    nxt = name[len(fragment):len(fragment) + 1]
    return not nxt.isalnum()


def is_host_running(slug: str, processes: list[str] | None = None) -> bool:
    """True when a process matching `slug` is running.

    `processes` is injectable for tests — pass a list of lowercased names.
    An unknown slug is False rather than an error; a new connector that
    forgets to register fragments degrades to "installed", never to a
    false green light.
    """
    fragments = _PROCESS_FRAGMENTS.get(slug)
    if not fragments:
        return False
    names = _list_processes() if processes is None else [p.lower() for p in processes]
    return any(_name_matches(name, frag) for frag in fragments for name in names)


def status_for(
    slug: str,
    verify_result: tuple[str, str] | None,
    processes: list[str] | None = None,
) -> HostStatus:
    """Compose install state and process state into one status.

    `verify_result` is whatever ``Connector.verify()`` returned — a
    (status, details) pair of 'verified' | 'outdated' | 'missing', or None
    when the probe could not run at all.
    """
    if verify_result is None:
        return HostStatus(slug, HostState.UNKNOWN, "Could not check the integration")

    install_state, detail = verify_result

    if install_state == "missing":
        return HostStatus(slug, HostState.NOT_INSTALLED, detail)

    running = is_host_running(slug, processes)

    if install_state == "outdated":
        suffix = " — the app is open" if running else ""
        return HostStatus(slug, HostState.STALE, f"{detail}{suffix}")

    if install_state == "verified":
        if running:
            return HostStatus(slug, HostState.RUNNING, "Integration installed, app is open")
        return HostStatus(slug, HostState.INSTALLED, "Installed — open the app to use it")

    # An install_state we do not recognise. Say so rather than guess.
    return HostStatus(slug, HostState.UNKNOWN, f"Unrecognised verify result: {install_state!r}")


def registered_slugs() -> tuple[str, ...]:
    """Connector slugs this module can detect a process for."""
    return tuple(sorted(_PROCESS_FRAGMENTS))
