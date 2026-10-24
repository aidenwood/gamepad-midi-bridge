"""The Marketplace tag chips must not pin the window's width.

THE BUG: `_build_tag_chips` put one ~120px chip per unique tag into a single
`QHBoxLayout`. A QHBoxLayout's minimum width is the sum of its children, so
with the live marketplace's tag spread the Marketplace page reported a
**3556px** minimum against a 380px window floor. Nothing could shrink the page
under it, so on a laptop-width window the content ran off the right edge
instead of reflowing — preset descriptions cut mid-sentence, Inspector clipped.

`tests/test_narrow_page_floors.py` measures this across every tab and was
failing on `('Marketplace', 3556)`. This file pins the specific cause so a
future `QHBoxLayout` here fails with an obvious name rather than as one entry
in a generic sweep.

The fix is `FlowLayout` — the primitive written for exactly this, already used
by the Bluetooth tab's action row. Wrapping is the honest fix: the chips take
as many rows as they need and none are hidden.
"""

from __future__ import annotations

import pytest

WINDOW_FLOOR = 380


@pytest.fixture()
def tab(qapp):
    from gamepad_midi_bridge.ui.marketplace_tab import MarketplaceTab

    t = MarketplaceTab()
    # A realistic spread — the live library is ~23 presets with many tags.
    t._presets = [
        {"tags": [f"tag{i}", f"host{i % 5}", "dualsense", "vj"]} for i in range(23)
    ]
    t._build_tag_chips()
    return t


class TestTagChipsDoNotPinTheWindow:
    def test_page_fits_under_the_window_floor(self, tab):
        floor = tab.minimumSizeHint().width()
        assert floor <= WINDOW_FLOOR, (
            f"Marketplace demands {floor}px minimum width; the window floor is "
            f"{WINDOW_FLOOR}px, so the page can never reflow narrower"
        )

    def test_the_chip_row_itself_is_not_the_offender(self, tab):
        """The row is the thing that used to contribute 3556px."""
        assert tab._tag_chips_container.minimumSizeHint().width() <= WINDOW_FLOOR

    def test_chips_wrap_rather_than_disappear(self, tab):
        """Wrapping, not hiding — every tag stays reachable."""
        assert tab._tag_chips_layout.count() > 10
        tall = tab._tag_chips_layout.heightForWidth(880)
        assert tall > 0, "a wrapping row must report its height for a width"

    def test_narrower_width_needs_more_rows(self, tab):
        """Proves it actually reflows instead of overflowing silently."""
        wide = tab._tag_chips_layout.heightForWidth(1200)
        narrow = tab._tag_chips_layout.heightForWidth(420)
        assert narrow > wide

    def test_rebuild_does_not_accumulate_chips(self, tab):
        """The clear loop stops at 0 now there is no trailing stretch to keep."""
        first = tab._tag_chips_layout.count()
        tab._build_tag_chips()
        assert tab._tag_chips_layout.count() == first

    def test_no_tags_hides_the_row(self, tab):
        """Pre-existing behaviour — an empty row should not take space."""
        tab._presets = [{"tags": []}]
        tab._build_tag_chips()
        assert tab._tag_chips_container.isVisible() is False
