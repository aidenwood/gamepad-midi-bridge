"""3D logo widget — QWebEngineView wrapper that renders the GLB logo
inside a tiny Three.js scene.

Why a QWebEngineView instead of native Qt3D: the GLB ships with PBR
materials + a Draco-compressed mesh; QtWebEngine + Three.js handles both
natively, while a Qt3D port would mean re-authoring lighting/materials
in C++ bindings. The widget is opt-in (callers explicitly add it where
it makes sense) so the Chromium process only spawns when a screen
actually shows the logo.

Public API:
    Logo3DView()        — QWidget you can add to any layout.
    Logo3DView.shutdown() — call before app exit to clean up the engine.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QUrl
from PySide6.QtWebEngineCore import (
    QWebEngineUrlScheme,
    QWebEngineUrlSchemeHandler,
    QWebEngineUrlRequestJob,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QWidget


_RESOURCES = Path(__file__).resolve().parent.parent / "resources" / "3d"

# Custom URL scheme registered ONCE on first widget construction. We use
# it to serve the bundled GLB to Three.js without needing a real HTTP
# server. QWebEngine restricts what a `file://` page can fetch from disk
# (CORS-style sandboxing) so a custom scheme is the cleanest workaround.
_SCHEME_NAME = b"gmb"
_scheme_registered = False


def _register_scheme() -> None:
    """Register the `gmb://` URL scheme. Idempotent — calling twice is a no-op."""
    global _scheme_registered
    if _scheme_registered:
        return
    scheme = QWebEngineUrlScheme(_SCHEME_NAME)
    scheme.setFlags(
        QWebEngineUrlScheme.SecureScheme
        | QWebEngineUrlScheme.LocalScheme
        | QWebEngineUrlScheme.LocalAccessAllowed
        | QWebEngineUrlScheme.CorsEnabled,
    )
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Path)
    QWebEngineUrlScheme.registerScheme(scheme)
    _scheme_registered = True


class _GmbHandler(QWebEngineUrlSchemeHandler):
    """Resolves `gmb://<filename>` requests to bytes from `resources/3d/`."""

    def requestStarted(self, job: QWebEngineUrlRequestJob) -> None:
        url = job.requestUrl()
        # url.host() picks up the part right after the `gmb://`. So
        # gmb://logo.glb → host="logo.glb", path="".
        name = url.host() or url.path().lstrip("/")
        if not name:
            job.fail(QWebEngineUrlRequestJob.UrlNotFound)
            return
        target = (_RESOURCES / name).resolve()
        # Prevent path-escape — only serve files inside the resources dir.
        try:
            target.relative_to(_RESOURCES)
        except ValueError:
            job.fail(QWebEngineUrlRequestJob.UrlInvalid)
            return
        if not target.exists() or not target.is_file():
            job.fail(QWebEngineUrlRequestJob.UrlNotFound)
            return

        data = target.read_bytes()
        buf = QBuffer(parent=job)
        buf.setData(QByteArray(data))
        buf.open(QIODevice.ReadOnly)
        mime = b"model/gltf-binary" if target.suffix.lower() == ".glb" else b"application/octet-stream"
        job.reply(mime, buf)


class Logo3DView(QWebEngineView):
    """A small QWidget showing the rotating 3D logo.

    Usage:
        view = Logo3DView()
        view.setFixedSize(220, 220)
        layout.addWidget(view)
    """

    _handler: Optional[_GmbHandler] = None

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        _register_scheme()

        # Install one shared handler per profile so concurrent Logo3DViews
        # share a single Chromium content backend.
        profile = self.page().profile()
        if Logo3DView._handler is None:
            Logo3DView._handler = _GmbHandler()
            profile.installUrlSchemeHandler(_SCHEME_NAME, Logo3DView._handler)

        # Transparent background so the widget blends with the dark Qt theme.
        self.page().setBackgroundColor(0)  # Qt.transparent
        index = _RESOURCES / "index.html"
        if index.exists():
            self.load(QUrl.fromLocalFile(str(index)))

    def shutdown(self) -> None:
        """Stop loading + drop the page so Chromium can release the process."""
        self.stop()
        self.setHtml("")
