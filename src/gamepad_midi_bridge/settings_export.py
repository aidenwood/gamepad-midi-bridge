"""App settings export/import: flat key/value store with typed accessors and namespace support.

Pure stdlib (json only), no Qt. Used for UI preferences, last-port-name, theme, etc.

Example:
    settings = SettingsManager()
    settings.set('volume', 64)
    settings.set('theme', 'dark')
    settings.set('ui.window_width', 800)

    # Typed getters with defaults
    vol = settings.get_int('volume', default=50)  # 64
    theme = settings.get_str('theme', default='light')  # 'dark'
    width = settings.get_int('ui.window_width', default=1024)  # 800

    # Namespace operations
    ui_prefs = settings.namespace('ui')  # {'window_width': 800, ...}
    settings.apply_namespace('audio', {'sample_rate': 44100, 'channels': 2})

    # JSON round-trip
    json_str = settings.to_json(indent=2)
    settings.from_json(json_str)

    # Legacy migration
    old_settings = {'volume': '64', 'theme': 'dark'}
    type_map = {'volume': 'int', 'theme': 'str'}
    typed = migrate_legacy_settings(old_settings, type_map)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SettingsStore:
    """Flat key/value store with JSON serialization."""
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a copy of the internal data dict."""
        return dict(self.data)

    def from_dict(self, data: Dict[str, Any]) -> None:
        """Replace internal data with a new dict."""
        self.data = dict(data)


class SettingsManager:
    """Typed settings manager with namespace support.

    Stores key/value pairs and provides typed accessors (int, float, bool, str, list).
    Supports namespace prefixing for logical grouping (e.g. 'ui.theme', 'audio.sample_rate').
    """

    def __init__(self, initial: Optional[Dict[str, Any]] = None) -> None:
        """Initialize with optional initial data."""
        self.data: Dict[str, Any] = dict(initial) if initial else {}

    def set(self, key: str, value: Any) -> None:
        """Set a key to a value."""
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a key, returning default if missing."""
        return self.data.get(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        """Get a key as int, returning default if missing or wrong type."""
        val = self.data.get(key)
        if val is None:
            return default
        if isinstance(val, int) and not isinstance(val, bool):
            return val
        if isinstance(val, (float, str)):
            try:
                return int(val)
            except (ValueError, TypeError):
                return default
        return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get a key as float, returning default if missing or wrong type."""
        val = self.data.get(key)
        if val is None:
            return default
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val)
            except (ValueError, TypeError):
                return default
        return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a key as bool, returning default if missing or wrong type.

        Recognizes: True, False, 1, 0, "true", "false", "1", "0" (case-insensitive).
        """
        val = self.data.get(key)
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        if isinstance(val, int):
            return val != 0
        if isinstance(val, str):
            lower = val.lower().strip()
            if lower in ("true", "1"):
                return True
            if lower in ("false", "0"):
                return False
            return default
        return default

    def get_str(self, key: str, default: str = "") -> str:
        """Get a key as str, returning default if missing."""
        val = self.data.get(key)
        if val is None:
            return default
        return str(val)

    def get_list(self, key: str, default: Optional[List] = None) -> List:
        """Get a key as list, returning default if missing or wrong type."""
        if default is None:
            default = []
        val = self.data.get(key)
        if val is None:
            return default
        if isinstance(val, list):
            return val
        return default

    def has(self, key: str) -> bool:
        """Check if a key exists."""
        return key in self.data

    def remove(self, key: str) -> bool:
        """Remove a key. Return True if it was removed, False if it didn't exist."""
        if key in self.data:
            del self.data[key]
            return True
        return False

    def keys(self, prefix: str = "") -> List[str]:
        """Return all keys, optionally filtered by prefix.

        If prefix is given, only keys starting with prefix are returned.
        """
        if not prefix:
            return list(self.data.keys())
        return [k for k in self.data.keys() if k.startswith(prefix)]

    def namespace(self, prefix: str) -> Dict[str, Any]:
        """Return a dict of keys starting with prefix, with prefix stripped.

        Example: if data is {'ui.theme': 'dark', 'ui.width': 800},
        namespace('ui.') returns {'theme': 'dark', 'width': 800}.
        """
        if not prefix:
            return {}
        sep = "" if prefix.endswith(".") else "."
        full_prefix = prefix + sep if not prefix.endswith(".") else prefix
        result = {}
        for k, v in self.data.items():
            if k.startswith(full_prefix):
                stripped = k[len(full_prefix) :]
                result[stripped] = v
        return result

    def apply_namespace(self, prefix: str, values: Dict[str, Any]) -> None:
        """Set keys with a namespace prefix.

        Example: apply_namespace('ui', {'theme': 'dark'}) sets 'ui.theme' to 'dark'.
        """
        sep = "" if prefix.endswith(".") else "."
        full_prefix = prefix + sep if not prefix.endswith(".") else prefix
        for k, v in values.items():
            self.data[full_prefix + k] = v

    def clear(self) -> None:
        """Remove all keys."""
        self.data.clear()

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.data, indent=indent)

    def from_json(self, json_str: str) -> None:
        """Replace data by parsing JSON string."""
        self.data = json.loads(json_str)

    def merge(self, other: Dict[str, Any]) -> None:
        """Overlay new keys onto existing data."""
        self.data.update(other)


def migrate_legacy_settings(
    old: Dict[str, str], type_map: Dict[str, str]
) -> Dict[str, Any]:
    """Migrate legacy string-keyed-string settings to typed dict.

    Args:
        old: Old settings dict with string values.
        type_map: Mapping of key name to type string ('int', 'float', 'bool', 'json').
                  Keys not in type_map are skipped.

    Returns:
        Typed dict suitable for SettingsManager initialization.

    Example:
        old = {'volume': '64', 'theme': 'dark', 'enabled': 'true'}
        type_map = {'volume': 'int', 'theme': 'str', 'enabled': 'bool'}
        typed = migrate_legacy_settings(old, type_map)
        # Returns {'volume': 64, 'theme': 'dark', 'enabled': True}
    """
    result: Dict[str, Any] = {}

    for key, type_str in type_map.items():
        if key not in old:
            continue

        val_str = old[key]

        if type_str == "int":
            try:
                result[key] = int(val_str)
            except (ValueError, TypeError):
                pass
        elif type_str == "float":
            try:
                result[key] = float(val_str)
            except (ValueError, TypeError):
                pass
        elif type_str == "bool":
            lower = val_str.lower().strip() if isinstance(val_str, str) else ""
            result[key] = lower in ("true", "1", "yes")
        elif type_str == "json":
            try:
                result[key] = json.loads(val_str)
            except (ValueError, TypeError, json.JSONDecodeError):
                pass
        elif type_str == "str":
            result[key] = str(val_str)

    return result
