"""Tests for host liveness — is the app actually open?

The existing Connector.verify() answers "is the integration installed", which
is not what a status light should say. Someone whose Ableton is closed sees
the same green tick as someone mid-set. These cover the composition of the
two signals, and the cases where we must refuse to guess.
"""

import pytest

from gamepad_midi_bridge.connectors import liveness as L
from gamepad_midi_bridge.connectors.liveness import HostState


class TestProcessMatching:
    def test_matches_a_running_host(self):
        assert L.is_host_running("ableton", ["ableton live 12", "finder"]) is True

    def test_is_case_insensitive(self):
        assert L.is_host_running("touchdesigner", ["TouchDesigner"]) is True

    def test_resolume_matches_either_edition(self):
        """The binary is Arena or Avenue, not 'Resolume'."""
        assert L.is_host_running("resolume", ["arena"]) is True
        assert L.is_host_running("resolume", ["avenue"]) is True

    def test_no_match_when_host_is_closed(self):
        assert L.is_host_running("ableton", ["finder", "safari"]) is False

    def test_unknown_slug_is_false_not_an_error(self):
        """A connector that forgets to register must degrade to 'installed',
        never to a false green light."""
        assert L.is_host_running("not_a_connector", ["anything"]) is False

    def test_empty_process_list(self):
        assert L.is_host_running("ableton", []) is False

    def test_every_registered_slug_has_fragments(self):
        for slug in L.registered_slugs():
            assert L._PROCESS_FRAGMENTS[slug], f"{slug} has no process fragments"

    def test_the_three_hosts_we_care_about_are_registered(self):
        for slug in ("ableton", "resolume", "touchdesigner"):
            assert slug in L.registered_slugs()


class TestStatusComposition:
    def test_missing_integration_is_not_installed(self):
        s = L.status_for("ableton", ("missing", "No Remote Script found"), [])
        assert s.state is HostState.NOT_INSTALLED
        assert s.is_live is False

    def test_installed_but_app_closed(self):
        s = L.status_for("ableton", ("verified", "ok"), ["finder"])
        assert s.state is HostState.INSTALLED
        assert s.is_live is False
        assert "open the app" in s.detail.lower()

    def test_installed_and_app_open_is_the_only_live_state(self):
        s = L.status_for("ableton", ("verified", "ok"), ["ableton live 12"])
        assert s.state is HostState.RUNNING
        assert s.is_live is True

    def test_outdated_is_reported_as_stale_not_live(self):
        s = L.status_for("resolume", ("outdated", "file is 200 days old"), ["arena"])
        assert s.state is HostState.STALE
        assert s.is_live is False

    def test_stale_still_mentions_the_app_being_open(self):
        s = L.status_for("resolume", ("outdated", "old"), ["arena"])
        assert "app is open" in s.detail

    def test_failed_probe_is_unknown_never_a_guess(self):
        s = L.status_for("ableton", None, [])
        assert s.state is HostState.UNKNOWN
        assert s.is_live is False

    def test_unrecognised_verify_result_is_unknown(self):
        """A new verify() status must not fall through to a green light."""
        s = L.status_for("ableton", ("something_new", "?"), ["ableton live"])
        assert s.state is HostState.UNKNOWN
        assert s.is_live is False

    @pytest.mark.parametrize("slug", ["ableton", "resolume", "touchdesigner"])
    def test_is_live_requires_both_signals(self, slug):
        """Neither signal alone may produce a live status."""
        installed_only = L.status_for(slug, ("verified", "ok"), [])
        running_only = L.status_for(slug, ("missing", "no"), [slug])
        assert installed_only.is_live is False
        assert running_only.is_live is False


class TestProbeIsSafe:
    def test_process_probe_never_raises(self):
        """Runs the real probe. A status light must not crash the app."""
        result = L._list_processes()
        assert isinstance(result, list)

    def test_process_probe_returns_lowercase(self):
        for name in L._list_processes():
            assert name == name.lower()

    def test_status_for_with_real_probe_does_not_raise(self):
        s = L.status_for("ableton", ("verified", "ok"))
        assert s.state in {HostState.RUNNING, HostState.INSTALLED}


class TestNoFalsePositives:
    """Substring matching shipped a status light that went green for the
    wrong app. Found by running the matcher against this machine's real
    738-process list: "obs" matched Obsidian, jobs and observer; "arena"
    matched arenanet. A green light nobody can trust is worse than none.
    """

    @pytest.mark.parametrize(
        "process,slug",
        [
            ("obsidian", "obs"),        # the one that would actually bite
            ("jobs", "obs"),
            ("observer", "obs"),
            ("arenanet", "resolume"),
            ("liveupdate", "ableton"),
            ("reapermanager", "reaper"),
            ("vdmxtra", "vdmx"),
        ],
    )
    def test_similar_names_do_not_match(self, process, slug):
        assert L.is_host_running(slug, [process]) is False, (
            f"{process!r} must not look like {slug}"
        )

    @pytest.mark.parametrize(
        "process,slug",
        [
            ("ableton live 12", "ableton"),
            ("ableton live 11 suite", "ableton"),
            ("live.exe", "ableton"),
            ("arena", "resolume"),
            ("avenue", "resolume"),
            ("resolume arena", "resolume"),
            ("touchdesigner", "touchdesigner"),
            ("obs", "obs"),
            ("reaper", "reaper"),
        ],
    )
    def test_real_host_names_still_match(self, process, slug):
        assert L.is_host_running(slug, [process]) is True

    def test_helper_processes_count_as_the_host(self):
        """A Resolume helper being up does mean Resolume is up — this is a
        true positive, not a miss in the boundary rule."""
        assert L.is_host_running("resolume", ["resolume-helper"]) is True

    def test_matcher_is_clean_against_this_machine(self):
        """Regression guard against the real process list, whatever it holds.

        Any match here is either a genuinely running host or a false positive;
        this asserts we do not match something obviously unrelated.
        """
        procs = L._list_processes()
        for slug in L.registered_slugs():
            for name in procs:
                if L.is_host_running(slug, [name]):
                    frags = L._PROCESS_FRAGMENTS[slug]
                    assert any(name.startswith(f) for f in frags), (
                        f"{slug} matched {name!r} without a prefix match"
                    )
