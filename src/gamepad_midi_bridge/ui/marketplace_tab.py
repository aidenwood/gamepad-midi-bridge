"""Marketplace tab — browse + install community presets from store.aidxn.com.

Free-tier visible. Browsing and downloading are public; only publishing will
require Pro (not implemented here).

Network: QNetworkAccessManager, no extra deps.
Cache: 5-minute in-memory cache so the tab works offline-ish after a fetch.
"""
from __future__ import annotations

import json
import time
import webbrowser
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QByteArray, Qt, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ..mapping import Mapping


STORE_BASE = "https://store.aidxn.com"
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
        self._cache_fetched_at: float = 0.0
        self._cache_key: str = ""
        self._inflight_list: Optional[QNetworkReply] = None
        self._inflight_get: Optional[QNetworkReply] = None
        self._loading: bool = False

        self._build_ui()
        # Kick off first load without forcing — uses cache if a previous tab
        # instance populated it during the same session.
        self.refresh(force=False)

    # ---------------------------------------------------------------- ui builders

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        header = QLabel("Community presets — built by other players, ready to map.")
        header.setStyleSheet("font-size: 14px; font-weight: 600; color: #f5f7fa;")
        outer.addWidget(header)

        sub = QLabel(
            "Download a preset and it loads straight into your active mapping. "
            "Browse the full library on the web for screenshots and reviews."
        )
        sub.setStyleSheet(f"color: {MUTED};")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        outer.addLayout(self._build_filter_row())

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {MUTED}; padding: 2px 0;")
        outer.addWidget(self._status_label)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(self._scroll, 1)

        action_row = QHBoxLayout()
        browse = QPushButton("Browse online")
        browse.clicked.connect(lambda: webbrowser.open(BROWSE_URL))
        action_row.addWidget(browse)
        action_row.addStretch(1)
        outer.addLayout(action_row)

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
        row.addWidget(QLabel("Host:"))
        row.addWidget(self._host_combo)

        self._device_combo = QComboBox()
        self._device_combo.addItem("All devices", userData="")
        for label, value in (
            ("DualSense", "dualsense"),
            ("Xbox", "xbox"),
            ("Generic", "generic"),
        ):
            self._device_combo.addItem(label, userData=value)
        row.addWidget(QLabel("Device:"))
        row.addWidget(self._device_combo)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search title / description…")
        self._search.returnPressed.connect(lambda: self.refresh(force=True))
        row.addWidget(self._search, 1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(lambda: self.refresh(force=True))
        row.addWidget(refresh_btn)

        return row

    # ---------------------------------------------------------------- public

    def refresh(self, force: bool = True) -> None:
        host = self._host_combo.currentData() or ""
        device = self._device_combo.currentData() or ""
        q = self._search.text().strip()
        cache_key = f"{host}|{device}|{q}"

        if (
            not force
            and self._presets
            and cache_key == self._cache_key
            and (time.time() - self._cache_fetched_at) < CACHE_TTL_SECONDS
        ):
            self._render_list()
            return

        params: List[str] = []
        if host:
            params.append(f"host={host}")
        if device:
            params.append(f"device={device}")
        if q:
            from urllib.parse import quote
            params.append(f"q={quote(q)}")
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
            self._render_list()
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

    # ---------------------------------------------------------------- rendering

    def _set_loading(self, message: str) -> None:
        self._loading = True
        self._status_label.setText(message)
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        spinner = QLabel("Loading…")
        spinner.setAlignment(Qt.AlignCenter)
        spinner.setStyleSheet(f"color: {MUTED}; padding: 60px;")
        v.addWidget(spinner)
        v.addStretch(1)
        self._scroll.setWidget(container)

    def _set_error(self, message: str) -> None:
        self._loading = False
        self._status_label.setText("")
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(message)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {MUTED}; padding: 40px;")
        lbl.setWordWrap(True)
        v.addWidget(lbl)
        v.addStretch(1)
        self._scroll.setWidget(container)

    def _render_list(self) -> None:
        self._loading = False
        if self._cache_fetched_at:
            age = int(time.time() - self._cache_fetched_at)
            self._status_label.setText(f"{len(self._presets)} preset(s) · cached {age}s ago")
        else:
            self._status_label.setText("")

        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        if not self._presets:
            empty = QLabel(
                "No presets match those filters yet.\n\n"
                "Want to be first? Build a mapping, then publish it from the "
                "marketplace site — your name goes on it forever."
            )
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color: {MUTED}; padding: 40px;")
            v.addWidget(empty)
        else:
            for preset in self._presets:
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

        title = QLabel(preset.get("title") or "Untitled preset")
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #f5f7fa;")
        left.addWidget(title)

        author = preset.get("author") or {}
        author_name = (
            author.get("display_name")
            or author.get("github_handle")
            or "Anonymous"
        )
        host = preset.get("host_target") or "generic"
        device = preset.get("device_target") or "generic"
        meta = QLabel(f"by {author_name}  ·  {host} · {device}")
        meta.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        left.addWidget(meta)

        description = preset.get("description")
        if description:
            desc = QLabel(str(description))
            desc.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
            desc.setWordWrap(True)
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
        dl_label = QLabel(f"{downloads} downloads")
        dl_label.setAlignment(Qt.AlignRight)
        dl_label.setStyleSheet(f"color: {SUBTLE_TEXT}; font-size: 11px;")
        right.addWidget(dl_label)

        install_btn = QPushButton("Install")
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
