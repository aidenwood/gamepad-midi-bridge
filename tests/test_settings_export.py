"""Tests for SettingsManager: typed accessors, namespace, JSON round-trip, migration."""
from __future__ import annotations

import json

import pytest


class TestSettingsManagerBasic:
    """set() + get() round-trip."""

    def test_set_get_string(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('theme', 'dark')
        assert mgr.get('theme') == 'dark'

    def test_set_get_int(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('volume', 64)
        assert mgr.get('volume') == 64

    def test_get_returns_default_when_missing(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        assert mgr.get('nonexistent') is None
        assert mgr.get('nonexistent', 'default') == 'default'

    def test_set_overwrites(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('key', 'value1')
        mgr.set('key', 'value2')
        assert mgr.get('key') == 'value2'


class TestSettingsManagerTypedGetters:
    """get_int, get_float, get_bool, get_str, get_list."""

    def test_get_int_from_int(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('port', 5000)
        assert mgr.get_int('port') == 5000

    def test_get_int_from_string(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('port', '5000')
        assert mgr.get_int('port') == 5000

    def test_get_int_from_float(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('samples', 100.7)
        assert mgr.get_int('samples') == 100

    def test_get_int_bad_value_returns_default(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('bad', 'not_a_number')
        assert mgr.get_int('bad') == 0
        assert mgr.get_int('bad', default=42) == 42

    def test_get_int_missing_returns_default(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        assert mgr.get_int('missing') == 0
        assert mgr.get_int('missing', default=99) == 99

    def test_get_float_from_float(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('gain', 1.5)
        assert mgr.get_float('gain') == 1.5

    def test_get_float_from_int(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('gain', 2)
        assert mgr.get_float('gain') == 2.0

    def test_get_float_from_string(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('gain', '3.14')
        assert mgr.get_float('gain') == 3.14

    def test_get_float_bad_value_returns_default(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('bad', 'not_a_float')
        assert mgr.get_float('bad') == 0.0
        assert mgr.get_float('bad', default=2.5) == 2.5

    def test_get_bool_from_bool(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('enabled', True)
        assert mgr.get_bool('enabled') is True
        mgr.set('enabled', False)
        assert mgr.get_bool('enabled') is False

    def test_get_bool_from_string(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('a', 'true')
        mgr.set('b', 'false')
        mgr.set('c', 'TRUE')
        mgr.set('d', '1')
        mgr.set('e', '0')
        assert mgr.get_bool('a') is True
        assert mgr.get_bool('b') is False
        assert mgr.get_bool('c') is True
        assert mgr.get_bool('d') is True
        assert mgr.get_bool('e') is False

    def test_get_bool_from_int(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('a', 1)
        mgr.set('b', 0)
        mgr.set('c', 5)
        assert mgr.get_bool('a') is True
        assert mgr.get_bool('b') is False
        assert mgr.get_bool('c') is True

    def test_get_bool_bad_value_returns_default(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('bad', 'maybe')
        assert mgr.get_bool('bad') is False
        assert mgr.get_bool('bad', default=True) is True

    def test_get_str_from_any(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('a', 'hello')
        mgr.set('b', 42)
        mgr.set('c', 3.14)
        assert mgr.get_str('a') == 'hello'
        assert mgr.get_str('b') == '42'
        assert mgr.get_str('c') == '3.14'

    def test_get_str_missing_returns_default(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        assert mgr.get_str('missing') == ''
        assert mgr.get_str('missing', default='fallback') == 'fallback'

    def test_get_list_from_list(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('ports', [1, 2, 3])
        assert mgr.get_list('ports') == [1, 2, 3]

    def test_get_list_wrong_type_returns_default(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('not_list', 'string')
        assert mgr.get_list('not_list') == []
        assert mgr.get_list('not_list', default=['a']) == ['a']

    def test_get_list_missing_returns_default(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        assert mgr.get_list('missing') == []
        assert mgr.get_list('missing', default=['x', 'y']) == ['x', 'y']


class TestSettingsManagerHasRemove:
    """has() and remove()."""

    def test_has_true_when_key_exists(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('key', 'value')
        assert mgr.has('key') is True

    def test_has_false_when_missing(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        assert mgr.has('missing') is False

    def test_remove_deletes_and_returns_true(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('key', 'value')
        assert mgr.remove('key') is True
        assert mgr.has('key') is False

    def test_remove_missing_returns_false(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        assert mgr.remove('missing') is False


class TestSettingsManagerKeys:
    """keys() with optional prefix filter."""

    def test_keys_returns_all(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('a', 1)
        mgr.set('b', 2)
        mgr.set('c', 3)
        keys = sorted(mgr.keys())
        assert keys == ['a', 'b', 'c']

    def test_keys_empty(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        assert mgr.keys() == []

    def test_keys_with_prefix_filter(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('ui.theme', 'dark')
        mgr.set('ui.width', 800)
        mgr.set('audio.volume', 64)
        keys = sorted(mgr.keys('ui'))
        assert keys == ['ui.theme', 'ui.width']

    def test_keys_prefix_no_match(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('a', 1)
        assert mgr.keys('nonexistent') == []


class TestSettingsManagerNamespace:
    """namespace() and apply_namespace()."""

    def test_namespace_returns_dict_with_prefix_stripped(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('ui.theme', 'dark')
        mgr.set('ui.width', 800)
        mgr.set('audio.volume', 64)
        ui = mgr.namespace('ui')
        assert ui == {'theme': 'dark', 'width': 800}

    def test_namespace_with_dot_suffix(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('ui.theme', 'dark')
        mgr.set('ui.width', 800)
        ui = mgr.namespace('ui.')
        assert ui == {'theme': 'dark', 'width': 800}

    def test_namespace_empty_prefix(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('a', 1)
        assert mgr.namespace('') == {}

    def test_namespace_no_match(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('a', 1)
        assert mgr.namespace('audio') == {}

    def test_apply_namespace_sets_prefixed_keys(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.apply_namespace('ui', {'theme': 'dark', 'width': 800})
        assert mgr.get('ui.theme') == 'dark'
        assert mgr.get('ui.width') == 800

    def test_apply_namespace_with_dot_suffix(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.apply_namespace('audio.', {'volume': 64, 'channels': 2})
        assert mgr.get('audio.volume') == 64
        assert mgr.get('audio.channels') == 2

    def test_apply_namespace_overlays(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('ui.theme', 'light')
        mgr.apply_namespace('ui', {'theme': 'dark'})
        assert mgr.get('ui.theme') == 'dark'


class TestSettingsManagerClear:
    """clear() empties all keys."""

    def test_clear_removes_all(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('a', 1)
        mgr.set('b', 2)
        mgr.clear()
        assert mgr.keys() == []
        assert mgr.has('a') is False
        assert mgr.has('b') is False

    def test_clear_empty(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.clear()  # should not raise
        assert mgr.keys() == []


class TestSettingsManagerJSON:
    """to_json() and from_json() round-trip."""

    def test_to_json_empty(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        json_str = mgr.to_json(indent=0)
        assert json.loads(json_str) == {}

    def test_to_json_preserves_types(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('int_val', 42)
        mgr.set('float_val', 3.14)
        mgr.set('bool_val', True)
        mgr.set('str_val', 'hello')
        mgr.set('list_val', [1, 2, 3])
        json_str = mgr.to_json(indent=0)
        data = json.loads(json_str)
        assert data['int_val'] == 42
        assert data['float_val'] == 3.14
        assert data['bool_val'] is True
        assert data['str_val'] == 'hello'
        assert data['list_val'] == [1, 2, 3]

    def test_from_json_replaces_data(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('old_key', 'old_value')
        json_str = '{"new_key": "new_value"}'
        mgr.from_json(json_str)
        assert mgr.has('old_key') is False
        assert mgr.get('new_key') == 'new_value'

    def test_json_round_trip(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr1 = SettingsManager()
        mgr1.set('theme', 'dark')
        mgr1.set('volume', 64)
        mgr1.set('ports', [1, 2, 3])
        json_str = mgr1.to_json()

        mgr2 = SettingsManager()
        mgr2.from_json(json_str)
        assert mgr2.get('theme') == 'dark'
        assert mgr2.get('volume') == 64
        assert mgr2.get('ports') == [1, 2, 3]


class TestSettingsManagerMerge:
    """merge() overlays new keys."""

    def test_merge_adds_new_keys(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('a', 1)
        mgr.merge({'b': 2, 'c': 3})
        assert mgr.get('a') == 1
        assert mgr.get('b') == 2
        assert mgr.get('c') == 3

    def test_merge_overwrites_existing(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('a', 1)
        mgr.merge({'a': 999})
        assert mgr.get('a') == 999

    def test_merge_empty(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        mgr.set('a', 1)
        mgr.merge({})
        assert mgr.get('a') == 1


class TestSettingsManagerInit:
    """__init__ with initial data."""

    def test_init_empty(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        mgr = SettingsManager()
        assert mgr.keys() == []

    def test_init_with_data(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        initial = {'a': 1, 'b': 2}
        mgr = SettingsManager(initial=initial)
        assert mgr.get('a') == 1
        assert mgr.get('b') == 2

    def test_init_data_is_copied(self):
        from gamepad_midi_bridge.settings_export import SettingsManager
        initial = {'a': 1}
        mgr = SettingsManager(initial=initial)
        initial['a'] = 999
        assert mgr.get('a') == 1


class TestMigrateSettings:
    """migrate_legacy_settings() type conversion."""

    def test_migrate_int(self):
        from gamepad_midi_bridge.settings_export import migrate_legacy_settings
        old = {'volume': '64'}
        type_map = {'volume': 'int'}
        result = migrate_legacy_settings(old, type_map)
        assert result['volume'] == 64
        assert isinstance(result['volume'], int)

    def test_migrate_float(self):
        from gamepad_midi_bridge.settings_export import migrate_legacy_settings
        old = {'gain': '1.5'}
        type_map = {'gain': 'float'}
        result = migrate_legacy_settings(old, type_map)
        assert result['gain'] == 1.5
        assert isinstance(result['gain'], float)

    def test_migrate_bool_from_string(self):
        from gamepad_midi_bridge.settings_export import migrate_legacy_settings
        old = {'enabled': 'true', 'disabled': 'false'}
        type_map = {'enabled': 'bool', 'disabled': 'bool'}
        result = migrate_legacy_settings(old, type_map)
        assert result['enabled'] is True
        assert result['disabled'] is False

    def test_migrate_str(self):
        from gamepad_midi_bridge.settings_export import migrate_legacy_settings
        old = {'theme': 'dark'}
        type_map = {'theme': 'str'}
        result = migrate_legacy_settings(old, type_map)
        assert result['theme'] == 'dark'

    def test_migrate_json(self):
        from gamepad_midi_bridge.settings_export import migrate_legacy_settings
        old = {'ports': '[1, 2, 3]'}
        type_map = {'ports': 'json'}
        result = migrate_legacy_settings(old, type_map)
        assert result['ports'] == [1, 2, 3]

    def test_migrate_bad_value_skips_key(self):
        from gamepad_midi_bridge.settings_export import migrate_legacy_settings
        old = {'volume': 'not_a_number'}
        type_map = {'volume': 'int'}
        result = migrate_legacy_settings(old, type_map)
        assert 'volume' not in result

    def test_migrate_missing_key_skips(self):
        from gamepad_midi_bridge.settings_export import migrate_legacy_settings
        old = {'a': '1'}
        type_map = {'b': 'int'}
        result = migrate_legacy_settings(old, type_map)
        assert result == {}

    def test_migrate_mixed_types(self):
        from gamepad_midi_bridge.settings_export import migrate_legacy_settings
        old = {'vol': '64', 'theme': 'dark', 'enabled': 'true', 'gain': '2.5'}
        type_map = {
            'vol': 'int',
            'theme': 'str',
            'enabled': 'bool',
            'gain': 'float',
        }
        result = migrate_legacy_settings(old, type_map)
        assert result == {
            'vol': 64,
            'theme': 'dark',
            'enabled': True,
            'gain': 2.5,
        }

    def test_migrate_ignores_unmapped_keys(self):
        from gamepad_midi_bridge.settings_export import migrate_legacy_settings
        old = {'a': '1', 'b': '2', 'c': '3'}
        type_map = {'a': 'int'}
        result = migrate_legacy_settings(old, type_map)
        assert result == {'a': 1}
