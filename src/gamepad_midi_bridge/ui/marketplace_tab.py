"""Marketplace tab — browse + install community presets from midi.aidxn.com.

Free-tier visible. Browsing and downloading are public; only publishing will
require Pro (not implemented here).

Network: QNetworkAccessManager, no extra deps.
Cache: 5-minute in-memory cache so the tab works offline-ish after a fetch.
"""
from __future__ import annotations

import json
import time
import webbrowser
from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import QByteArray, Qt, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from .primitives import UIButton, UILabel, UIInput

from ..mapping import Mapping


STORE_BASE = "https://midi.aidxn.com"
LIST_URL = f"{STORE_BASE}/api/presets"
BROWSE_URL = f"{STORE_BASE}/marketplace"
CACHE_TTL_SECONDS = 5 * 60

ACCENT = "#2dd4bf"
MUTED = "#8a9099"
CARD_BG = "#16181d"
CARD_BORDER = "#24262d"
SUBTLE_TEXT = "#5a606b"


class MarketplaceTab(QWidget):
    """Community preset browser. Emits `preset_chosen(Mapping)` on install."""

    preset_chosen = Signal(Mapping)
    status_message = Signal(str)
    selection_changed = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._net = QNetworkAccessManager(self)
        self._presets: List[Dict[str, Any]] = []
        self._visible_presets: List[Dict[str, Any]] = []
        self._cache_fetched_at: float = 0.0
        self._cache_key: str = ""
        self._inflight_list: Optional[QNetworkReply] = None
        self._inflight_get: Optional[QNetworkReply] = None
        self._loading: bool = False
        self._selected_tags: Set[str] = set()
        self._sort_by: str = "newest"  # newest, downloads, rating, name

        self._build_ui()
        # Kick off first load without forcing — uses cache if a previous tab
        # instance populated it during the same session.
        self.refresh(force=False)

    # ---------------------------------------------------------------- ui builders

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        header = UILabel("Community presets — built by other players, ready to map.", variant="subheading")
        outer.addWidget(header)

        sub = UILabel(
            "Download a preset and it loads straight into your active mapping. "
            "Browse the full library on the web for screenshots and reviews.",
            variant="body",
        )
        outer.addWidget(sub)

        # Search box and sort
        outer.addLayout(self._build_search_sort_row())

        # Host / device filters
        outer.addLayout(self._build_filter_row())

        # Tag chips
        self._tag_chips_container = QWidget()
        self._tag_chips_layout = QHBoxLayout(self._tag_chips_container)
        self._tag_chips_layout.setContentsMargins(0, 0, 0, 0)
        self._tag_chips_layout.setSpacing(6)
        self._tag_chips_layout.addStretch(1)
        self._tag_chips_container.setVisible(False)
        outer.addWidget(self._tag_chips_container)

        self._status_label = UILabel("", variant="caption")
        outer.addWidget(self._status_label)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(self._scroll, 1)

        action_row = QHBoxLayout()
        browse = UIButton("Browse online", variant="ghost")
        browse.clicked.connect(lambda: webbrowser.open(BROWSE_URL))
        action_row.addWidget(browse)
        action_row.addStretch(1)
        outer.addLayout(action_row)

    def _build_search_sort_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self._search = UIInput("Search title / description / author / tags…")
        self._search.textChanged.connect(self._refresh_visible)
        row.addWidget(self._search, 1)

        row.addWidget(UILabel("Sort:", variant="caption"))
        self._sort_combo = QComboBox()
        self._sort_combo.addItem("Newest", userData="newest")
        self._sort_combo.addItem("Most downloaded", userData="downloads")
        self._sort_combo.addItem("Highest rated", userData="rating")
        self._sort_combo.addItem("Name A-Z", userData="name")
        self._sort_combo.currentIndexChanged.connect(
            lambda: self._set_sort(self._sort_combo.currentData())
        )
        row.addWidget(self._sort_combo)

        refresh_btn = UIButton("Refresh", variant="secondary")
        refresh_btn.clicked.connect(lambda: self.refresh(force=True))
        row.addWidget(refresh_btn)

        return row

    def _build_filter_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self._host_combo = QComboBox()
        self._host_combo.addItem("All hosts", userData="")
        for label, value in (
            ("Resolume", "resolume"),
            ("Ableton", "ableton"),
            ("TouchDesigner", "touchdesigner"),
            ("Generic", "generic"),
        ):
            self._host_combo.addItem(label, userData=value)
        self._host_combo.currentIndexChanged.connect(self._refresh_visible)
        row.addWidget(UILabel("Host:", variant="caption"))
        row.addWidget(self._host_combo)

        self._device_combo = QComboBox()
        self._device_combo.addItem("All devices", userData="")
        for label, value in (
            ("DualSense", "dualsense"),
            ("Xbox", "xbox"),
            ("Generic", "generic"),
        ):
            self._device_combo.addItem(label, userData=value)
        self._device_combo.currentIndexChanged.connect(self._refresh_visible)
        row.addWidget(UILabel("Device:", variant="caption"))
        row.addWidget(self._device_combo)

        return row

    # ---------------------------------------------------------------- public

    def refresh(self, force: bool = True) -> None:
        host = self._host_combo.currentData() or ""
        device = self._device_combo.currentData() or ""
        # Cache key doesn't include search — we filter locally
        cache_key = f"{host}|{device}"

        if (
            not force
            and self._presets
            and cache_key == self._cache_key
            and (time.time() - self._cache_fetched_at) < CACHE_TTL_SECONDS
        ):
            self._refresh_visible()
            return

        params: List[str] = []
        if host:
            params.append(f"host={host}")
        if device:
            params.append(f"device={device}")
        url = LIST_URL + ("?" + "&".join(params) if params else "")

        self._cancel_inflight_list()
        self._set_loading("Loading presets…")
        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"Accept", b"application/json")
        reply = self._net.get(req)
        self._inflight_list = reply
        reply.finished.connect(lambda: self._on_list_reply(reply, cache_key))

    # ---------------------------------------------------------------- network

    def _on_list_reply(self, reply: QNetworkReply, cache_key: str) -> None:
        if reply is not self._inflight_list:
            reply.deleteLater()
            return
        self._inflight_list = None
        try:
            err = reply.error()
            if err != QNetworkReply.NoError:
                self._set_error(f"Couldn't reach the marketplace: {reply.errorString()}")
                return
            raw = bytes(reply.readAll()).decode("utf-8", errors="replace")
            data = json.loads(raw)
            presets = data.get("presets") if isinstance(data, dict) else None
            if not isinstance(presets, list):
                self._set_error("Marketplace returned an unexpected response.")
                return
            self._presets = presets
            self._cache_key = cache_key
            self._cache_fetched_at = time.time()
            self._loading = False
            self._refresh_visible()
        except Exception as e:  # pragma: no cover
            self._set_error(f"Couldn't parse marketplace response: {e}")
        finally:
            reply.deleteLater()

    def _on_get_reply(self, reply: QNetworkReply, preset_meta: Dict[str, Any]) -> None:
        if reply is not self._inflight_get:
            reply.deleteLater()
            return
        self._inflight_get = None
        try:
            err = reply.error()
            if err != QNetworkReply.NoError:
                QMessageBox.warning(
                    self, "Install failed",
                    f"Couldn't download '{preset_meta.get('title', 'preset')}': "
                    f"{reply.errorString()}",
                )
                return
            raw = bytes(reply.readAll()).decode("utf-8", errors="replace")
            data = json.loads(raw)
            blob = data.get("json_blob") if isinstance(data, dict) else None
            if not isinstance(blob, dict):
                QMessageBox.warning(
                    self, "Install failed",
                    "Marketplace returned a preset without a valid mapping payload.",
                )
                return
            try:
                mapping = Mapping.from_dict(blob)
            except Exception as e:
                QMessageBox.warning(
                    self, "Install failed",
                    f"Preset couldn't be parsed into a mapping: {e}",
                )
                return
            mapping.name = preset_meta.get("title") or mapping.name
            self.preset_chosen.emit(mapping)
            self.status_message.emit(f"Installed '{mapping.name}' from the marketplace.")
        except Exception as e:  # pragma: no cover
            QMessageBox.warning(self, "Install failed", str(e))
        finally:
            reply.deleteLater()

    def _cancel_inflight_list(self) -> None:
        if self._inflight_list is not None:
            try:
                self._inflight_list.abort()
            except Exception:
                pass
            self._inflight_list = None

    # ---------------------------------------------------------------- filtering

    def _set_sort(self, sort_by: str) -> None:
        self._sort_by = sort_by
        self._refresh_visible()

    def _toggle_tag_filter(self, tag: str) -> None:
        if tag in self._selected_tags:
            self._selected_tags.remove(tag)
        else:
            self._selected_tags.add(tag)
        self._refresh_visible()

    def _refresh_visible(self) -> None:
        """Rebuild visible presets from _presets based on filters."""
        if not self._presets:
            self._visible_presets = []
            self._render_list()
            return

        search_q = self._search.text().strip().lower()
        host_filter = self._host_combo.currentData() or ""
        device_filter = self._device_combo.currentData() or ""

        visible = []
        for preset in self._presets:
            # Host filter
            if host_filter and preset.get("host_target") != host_filter:
                continue
            # Device filter
            if device_filter and preset.get("device_target") != device_filter:
                continue
            # Search across title, description, author, tags
            if search_q:
                title = (preset.get("title") or "").lower()
                description = (preset.get("description") or "").lower()
                author_obj = preset.get("author") or {}
                author_name = (
                    (author_obj.get("display_name") or "").lower() +
                    (author_obj.get("github_handle") or "").lower()
                )
                tags = preset.get("tags") or []
                tags_str = " ".join(str(t).lower() for t in tags)
                haystack = f"{title} {description} {author_name} {tags_str}"
                if search_q not in haystack:
                    continue
            # Tag filter — if any tags selected, preset must have at least one
            if self._selected_tags:
                preset_tags = set(str(t).lower() for t in (preset.get("tags") or []))
                selected_tags_lower = set(t.lower() for t in self._selected_tags)
                if not preset_tags & selected_tags_lower:
                    continue
            visible.append(preset)

        # Sort
        if self._sort_by == "newest":
            # Assume later presets are newer; reverse if needed
            visible.sort(key=lambda p: p.get("id", ""), reverse=True)
        elif self._sort_by == "downloads":
            visible.sort(key=lambda p: p.get("downloads", 0), reverse=True)
        elif self._sort_by == "rating":
            visible.sort(key=lambda p: p.get("rating", 0), reverse=True)
        elif self._sort_by == "name":
            visible.sort(key=lambda p: (p.get("title") or "Untitled").lower())

        self._visible_presets = visible
        self._build_tag_chips()
        self._render_list()

    def _build_tag_chips(self) -> None:
        """Extract unique tags from visible presets and render filter chips."""
        # Clear old chips
        while self._tag_chips_layout.count() > 1:
            item = self._tag_chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Collect unique tags from all presets (not just visible)
        all_tags: Set[str] = set()
        for preset in self._presets:
            tags = preset.get("tags") or []
            for tag in tags:
                all_tags.add(str(tag))

        if not all_tags:
            self._tag_chips_container.setVisible(False)
            return

        self._tag_chips_container.setVisible(True)
        sorted_tags = sorted(all_tags)
        for tag in sorted_tags:
            is_selected = tag in self._selected_tags
            chip = QPushButton(tag)
            chip.setMaximumWidth(120)
            chip.setCursor(Qt.PointingHandCursor)
            if is_selected:
                chip.setStyleSheet(
                    f"QPushButton {{ "
                    f"background-color: {ACCENT}; color: #0f1419; "
                    f"border: none; border-radius: 12px; padding: 4px 10px; "
                    f"font-size: 12px; font-weight: 500; }}"
                )
            else:
                chip.setStyleSheet(
                    f"QPushButton {{ "
                    f"background-color: #1f2229; color: {ACCENT}; "
                    f"border: 1px solid {CARD_BORDER}; border-radius: 12px; "
                    f"padding: 4px 10px; font-size: 12px; }} "
                    f"QPushButton:hover {{ background-color: #24262d; }}"
                )
            chip.clicked.connect(lambda _=False, t=tag: self._toggle_tag_filter(t))
            self._tag_chips_layout.insertWidget(self._tag_chips_layout.count() - 1, chip)

    # ---------------------------------------------------------------- rendering

    def _set_loading(self, message: str) -> None:
        self._loading = True
        self._status_label.setText(message)
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        spinner = UILabel("Loading…", variant="body")
        spinner.setAlignment(Qt.AlignCenter)
        v.addWidget(spinner)
        v.addStretch(1)
        self._scroll.setWidget(container)

    def _set_error(self, message: str) -> None:
        self._loading = False
        self._status_label.setText("")
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        lbl = UILabel(message, variant="body")
        lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(lbl)
        v.addStretch(1)
        self._scroll.setWidget(container)

    def _render_list(self) -> None:
        self._loading = False
        if self._cache_fetched_at:
            age = int(time.time() - self._cache_fetched_at)
            total = len(self._presets)
            visible = len(self._visible_presets)
            if visible == total:
                self._status_label.setText(f"Showing {visible} of {total} presets · cached {age}s ago")
            else:
                self._status_label.setText(f"Showing {visible} of {total} presets · cached {age}s ago")
        else:
            self._status_label.setText("")

        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        if not self._visible_presets:
            if self._presets:
                empty = UILabel(
                    "No presets match your filters.\n\n"
                    "Try adjusting your search or selecting different tags.",
                    variant="body",
                )
            else:
                empty = UILabel(
                    "No presets available yet.\n\n"
                    "Want to be first? Build a mapping, then publish it from the "
                    "marketplace site — your name goes on it forever.",
                    variant="body",
                )
            empty.setAlignment(Qt.AlignCenter)
            v.addWidget(empty)
        else:
            for preset in self._visible_presets:
                v.addWidget(self._preset_card(preset))

        v.addStretch(1)
        self._scroll.setWidget(container)

    def _preset_card(self, preset: Dict[str, Any]) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {CARD_BG}; "
            f"border: 1px solid {CARD_BORDER}; border-radius: 8px; padding: 14px; }}"
        )
        # Emit selection when card is clicked
        card.mousePressEvent = lambda ev, p=preset: self._emit_preset_selection(p)
        h = QHBoxLayout(card)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(14)

        # Left column — title + author + tags
        left = QVBoxLayout()
        left.setSpacing(4)

        title = UILabel(preset.get("title") or "Untitled preset", variant="subheading")
        left.addWidget(title)

        author = preset.get("author") or {}
        author_name = (
            author.get("display_name")
            or author.get("github_handle")
            or "Anonymous"
        )
        host = preset.get("host_target") or "generic"
        device = preset.get("device_target") or "generic"
        meta = UILabel(f"by {author_name}  ·  {host} · {device}", variant="caption")
        left.addWidget(meta)

        description = preset.get("description")
        if description:
            desc = UILabel(str(description), variant="body")
            left.addWidget(desc)

        tags = preset.get("tags") or []
        if isinstance(tags, list) and tags:
            chips_row = QHBoxLayout()
            chips_row.setSpacing(4)
            for tag in tags[:6]:
                chip = QLabel(str(tag))
                chip.setStyleSheet(
                    f"background-color: #1f2229; color: {ACCENT}; "
                    f"border-radius: 10px; padding: 2px 8px; font-size: 11px;"
                )
                chips_row.addWidget(chip)
            chips_row.addStretch(1)
            tag_holder = QWidget()
            tag_holder.setLayout(chips_row)
            left.addWidget(tag_holder)

        h.addLayout(left, 1)

        # Right column — downloads + install
        right = QVBoxLayout()
        right.setSpacing(6)
        downloads = preset.get("downloads") or 0
        dl_label = UILabel(f"{downloads} downloads", variant="caption")
        dl_label.setAlignment(Qt.AlignRight)
        right.addWidget(dl_label)

        install_btn = UIButton("Install preset", variant="primary")
        install_btn.setObjectName("PrimaryButton")
        install_btn.clicked.connect(lambda _=False, p=preset: self._on_install(p))
        right.addWidget(install_btn)
        right.addStretch(1)
        h.addLayout(right)

        return card

    # ---------------------------------------------------------------- actions

    def _emit_preset_selection(self, preset: Dict[str, Any]) -> None:
        """Emit preset metadata to the inspector panel."""
        payload = {
            "kind": "preset",
            "slug": preset.get("id", ""),
            "title": preset.get("title", "Untitled"),
            "downloads": preset.get("downloads", 0),
            "rating": preset.get("rating", 0),
            "author": (preset.get("author") or {}).get("display_name") or (preset.get("author") or {}).get("github_handle") or "Anonymous",
            "description": preset.get("description", ""),
            "label": preset.get("title", "Untitled preset"),
            "json_blob": preset.get("json_blob") or {},
        }
        self.selection_changed.emit(payload)

    def _on_install(self, preset: Dict[str, Any]) -> None:
        preset_id = preset.get("id")
        if not preset_id:
            QMessageBox.warning(self, "Install failed", "Preset is missing an id.")
            return

        if self._inflight_get is not None:
            try:
                self._inflight_get.abort()
            except Exception:
                pass
            self._inflight_get = None

        url = f"{LIST_URL}/{preset_id}"
        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"Accept", b"application/json")
        reply = self._net.get(req)
        self._inflight_get = reply
        self.status_message.emit(f"Downloading '{preset.get('title', 'preset')}'…")
        reply.finished.connect(lambda: self._on_get_reply(reply, preset))
