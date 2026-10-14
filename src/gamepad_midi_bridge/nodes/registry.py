"""Node registry — single source of truth for every NodeSpec the app knows about.

Loading priority (later overrides earlier with the same `kind`):
    1. First-party builtins shipped under nodes/builtins/*.py
    2. User-authored Python modules under <user_data_dir>/user_nodes/*.py

User nodes use the same NodeSpec contract as builtins — drop a .py file into
the user_nodes folder, define one or more NodeSpec instances, expose them via
a module-level ``NODES = [spec1, spec2, ...]`` list. The loader picks them up
on next launch.

This module deliberately stays UI-free. The Phase-2 canvas will read
`registry.all()` to populate the node-picker, but the registry doesn't import
Qt and doesn't care whether anything is shown to the user.
"""
from __future__ import annotations

import importlib
import importlib.util
import logging
import pkgutil
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .model import NodeSpec

log = logging.getLogger("gamepad_midi_bridge.nodes.registry")


# ---------------------------------------------------------------------------

class NodeRegistry:
    """Holds every NodeSpec the app knows about, keyed by ``kind``.

    Construct one at app startup, call ``load_builtins()``, optionally
    ``load_user_dir(path)``, then pass the populated registry to the bridge
    + UI. Re-loading is supported via ``reload()`` for hot-reload in dev.
    """

    def __init__(self) -> None:
        self._specs: Dict[str, NodeSpec] = {}
        self._user_dir: Optional[Path] = None

    # ------------------------------------------------------------------ public

    def register(self, spec: NodeSpec, *, source: str = "?") -> None:
        """Register one spec. Later registrations of the same `kind` override.

        ``source`` is for log readability — pass e.g. "builtin" or the
        absolute path of the user-authored module.
        """
        if not spec.kind or not isinstance(spec.kind, str):
            raise ValueError(f"NodeSpec.kind must be a non-empty string (got {spec.kind!r})")
        if spec.wire_eligible and (len(spec.inputs) != 1 or len(spec.outputs) != 1):
            raise ValueError(
                f"NodeSpec(kind={spec.kind!r}) declares wire_eligible=True but has "
                f"{len(spec.inputs)} inputs / {len(spec.outputs)} outputs. "
                f"Wire-eligible nodes must be 1-in / 1-out."
            )
        if spec.kind in self._specs:
            log.debug("overriding NodeSpec %r (from %s)", spec.kind, source)
        self._specs[spec.kind] = spec

    def get(self, kind: str) -> Optional[NodeSpec]:
        return self._specs.get(kind)

    def require(self, kind: str) -> NodeSpec:
        """Like ``get`` but raises if not found — for evaluator hot paths."""
        spec = self._specs.get(kind)
        if spec is None:
            raise KeyError(f"No NodeSpec registered for kind={kind!r}")
        return spec

    def all(self) -> List[NodeSpec]:
        """Every spec, sorted by category's `sort_priority` then label —
        matches the TouchDesigner-style node-picker layout where categories
        appear in a stable order (input → gate → shape → spatial → ...).
        Unknown categories fall to the end so user-authored nodes that
        invent new category names don't break the picker.
        """
        from .model import CATEGORIES
        priority = {c.kind: c.sort_priority for c in CATEGORIES}
        return sorted(
            self._specs.values(),
            key=lambda s: (priority.get(s.category, 999), s.label),
        )

    def wire_eligible(self) -> List[NodeSpec]:
        """Subset that may be used as inline transforms on a Connection."""
        return [s for s in self.all() if s.wire_eligible]

    def by_category(self) -> Dict[str, List[NodeSpec]]:
        """Group every spec by category kind, preserving the picker order.

        Phase 2's node picker iterates the returned dict to render category
        headers + the nodes underneath each. Categories with no registered
        nodes are simply absent from the dict (no empty sections).
        """
        from .model import CATEGORIES
        # Initialise in priority order so dict iteration yields the right
        # sequence on insertion-ordered dicts (Python 3.7+ guarantees).
        grouped: Dict[str, List[NodeSpec]] = {}
        for c in CATEGORIES:
            grouped[c.kind] = []
        for spec in self.all():
            grouped.setdefault(spec.category, []).append(spec)
        # Drop empties so the UI doesn't have to.
        return {k: v for k, v in grouped.items() if v}

    # ------------------------------------------------------------------ loading

    def load_builtins(self) -> None:
        """Import every module under gamepad_midi_bridge.nodes.builtins and
        register their ``NODES`` lists.

        New builtin? Just drop a .py file in nodes/builtins/ that exposes a
        module-level ``NODES = [...]`` — the loader picks it up here. No
        registration call needed.
        """
        from . import builtins as builtins_pkg

        for mod_info in pkgutil.iter_modules(builtins_pkg.__path__):
            full_name = f"{builtins_pkg.__name__}.{mod_info.name}"
            try:
                mod = importlib.import_module(full_name)
            except Exception:
                log.exception("failed to import builtin node module %s", full_name)
                continue
            self._register_module_nodes(mod, source=f"builtin:{mod_info.name}")

    def load_user_dir(self, path: Path) -> None:
        """Load every *.py in `path` as a user-authored node module.

        The directory is created if it does not exist; first launch will see
        no files and that's fine. Each module is imported in isolation under a
        synthetic ``gamepad_midi_bridge.user_nodes.<stem>`` package name so it
        doesn't collide with anything on sys.path.

        Failures in one user module never block the others — a bad node spec
        gets logged and we move on.
        """
        path = Path(path)
        self._user_dir = path
        path.mkdir(parents=True, exist_ok=True)
        for py in sorted(path.glob("*.py")):
            if py.name.startswith("_"):
                continue
            mod_name = f"gamepad_midi_bridge.user_nodes.{py.stem}"
            try:
                spec = importlib.util.spec_from_file_location(mod_name, py)
                if spec is None or spec.loader is None:
                    log.warning("could not build module spec for %s", py)
                    continue
                mod = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = mod
                spec.loader.exec_module(mod)
            except Exception:
                log.exception("failed to import user node module %s", py)
                continue
            self._register_module_nodes(mod, source=str(py))

    def reload(self) -> None:
        """Drop every registration and re-load builtins + the last user dir.

        Useful in dev — edit a node file, call reload(), the new spec
        replaces the old one. The graph evaluator picks up the change on the
        next tick because it look up specs by kind string each time.
        """
        self._specs.clear()
        self.load_builtins()
        if self._user_dir is not None:
            self.load_user_dir(self._user_dir)

    # ------------------------------------------------------------------ private

    def _register_module_nodes(self, mod, *, source: str) -> None:
        """Pull ``NODES`` from a loaded module and register each entry."""
        raw = getattr(mod, "NODES", None)
        if raw is None:
            log.debug("module %s has no NODES list; skipping", source)
            return
        if not isinstance(raw, Iterable):
            log.warning("module %s NODES is not iterable; skipping", source)
            return
        for entry in raw:
            if not isinstance(entry, NodeSpec):
                log.warning("module %s NODES contains a non-NodeSpec entry: %r", source, entry)
                continue
            try:
                self.register(entry, source=source)
            except ValueError:
                log.exception("rejected NodeSpec %r from %s", getattr(entry, "kind", "?"), source)


# ---------------------------------------------------------------------------
# Convenience: a process-wide default registry.
#
# The bridge constructs and populates this once at startup. Code paths that
# need the registry can `from .nodes.registry import default_registry` rather
# than threading the instance through five layers of constructors.
# ---------------------------------------------------------------------------

_default_registry: Optional[NodeRegistry] = None


def default_registry() -> NodeRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = NodeRegistry()
    return _default_registry


def reset_default_registry() -> None:
    """Test helper — drops the singleton so a fresh one is built next call."""
    global _default_registry
    _default_registry = None
