"""Phosphor icon loading, recoloured at runtime.

The SVGs ship with a hardcoded `fill="#000000"`, which is invisible on a
dark shell — so the fill is swapped for the requested colour before the SVG
is rasterised. Rendering through QSvgRenderer rather than QIcon(path) also
means the icon is sharp at any device pixel ratio instead of being scaled
from one bitmap.

Icons live in `resources/icons/` and are bundled by build.py's
`--add-data` of the whole resources tree, so no spec change is needed when
a new one is added.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap

_ICON_DIR = Path(__file__).resolve().parent.parent / "resources" / "icons"


def icon_path(name: str) -> Optional[Path]:
    p = _ICON_DIR / f"{name}.svg"
    return p if p.exists() else None


@lru_cache(maxsize=256)
def _pixmap(name: str, colour: str, size: int) -> QPixmap:
    """Rasterise one icon at one colour and size. Cached — these are built
    during paint/layout and the set is small and fixed."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    path = icon_path(name)
    if path is None:
        return pm
    try:
        from PySide6.QtSvg import QSvgRenderer
        svg = path.read_text(encoding="utf-8")
        # Phosphor ships a literal black fill; swap it for the brand colour.
        svg = svg.replace('fill="#000000"', f'fill="{colour}"')
        svg = svg.replace('fill="#000"', f'fill="{colour}"')
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
    except Exception:
        # A missing icon must never take the window down — the label and
        # tooltip still identify the control.
        return pm
    return pm


def load_icon(name: str, colour: str = "#2DD4BF", size: int = 18) -> QIcon:
    """A QIcon of `name`, tinted `colour`. Empty icon if the file is absent."""
    return QIcon(_pixmap(name, colour, size))


def available() -> list:
    """Every icon name shipped, for diagnostics and tests."""
    if not _ICON_DIR.exists():
        return []
    return sorted(p.stem for p in _ICON_DIR.glob("*.svg"))


@lru_cache(maxsize=32)
def _dot(colour: str, size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    from PySide6.QtGui import QBrush, QColor
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(QColor(colour)))
    inset = size * 0.18
    painter.drawEllipse(QRectF(inset, inset, size - inset * 2, size - inset * 2))
    painter.end()
    return pm


def dot_icon(colour: str = "#2DD4BF", size: int = 14) -> QIcon:
    """A filled dot. STATUS carries one in the wireframe rather than a
    glyph — its meaning comes from the colour, which comes from real
    state, never from the artwork."""
    return QIcon(_dot(colour, size))
