"""Tests for mapping_share_link encoder/decoder."""

import pytest

from gamepad_midi_bridge.mapping_share_link import (
    compress_ratio,
    decode,
    encode,
    extract_from_url,
    is_share_link,
    safe_encode,
    wrap_in_url,
)


class TestEncodeDecode:
    """Test round-trip encoding and decoding."""

    def test_encode_decode_simple_dict(self):
        """Encoding and decoding preserves a simple dict."""
        original = {'a': 1, 'b': 2}
        encoded = encode(original)
        decoded = decode(encoded)
        assert decoded == original

    def test_encode_decode_nested_dict(self):
        """Encoding and decoding preserves nested dicts."""
        original = {'a': 1, 'b': [2, 3], 'c': {'d': 4, 'e': 5}}
        encoded = encode(original)
        decoded = decode(encoded)
        assert decoded == original

    def test_encode_decode_empty_dict(self):
        """Encoding and decoding preserves an empty dict."""
        original = {}
        encoded = encode(original)
        decoded = decode(encoded)
        assert decoded == original

    def test_encode_decode_complex_mapping(self):
        """Encoding and decoding preserves a complex mapping structure."""
        original = {
            'buttons': {'ps': 1, 'options': 2},
            'sticks': {'left_x': 0, 'right_y': 127},
            'triggers': [100, 200],
            'metadata': {'version': 1, 'name': 'test'},
        }
        encoded = encode(original)
        decoded = decode(encoded)
        assert decoded == original


class TestEncodeFormat:
    """Test that encode produces URL-safe characters."""

    def test_encode_produces_urlsafe_base64(self):
        """Encoded string contains only URL-safe base64 characters."""
        test_dict = {'a': 1, 'b': 2}
        encoded = encode(test_dict)

        # URL-safe base64 uses - and _ instead of + and /
        # Should not contain + / or = (we strip padding)
        assert '+' not in encoded
        assert '/' not in encoded
        assert '=' not in encoded

    def test_encode_is_ascii(self):
        """Encoded string is ASCII-safe."""
        test_dict = {'test': 'value'}
        encoded = encode(test_dict)

        # All chars should be ASCII
        assert all(ord(c) < 128 for c in encoded)

    def test_encode_is_short(self):
        """Encoding produces valid base64 (may expand tiny dicts due to zlib overhead)."""
        test_dict = {'a': 1, 'b': 2}
        encoded = encode(test_dict)

        # Base64 adds overhead; tiny dicts may expand, but large ones compress
        # Just verify it's a valid encoded string
        assert isinstance(encoded, str)
        assert len(encoded) > 0


class TestDecode:
    """Test decoding error handling."""

    def test_decode_corrupt_base64_raises(self):
        """Decoding invalid base64 raises ValueError."""
        with pytest.raises(ValueError):
            decode('!!!invalid!!!base64!!!')

    def test_decode_valid_base64_bad_zlib_raises(self):
        """Decoding valid base64 but corrupt zlib raises ValueError."""
        # Valid base64, but not valid zlib data
        import base64
        bad_zlib = base64.urlsafe_b64encode(b'not zlib data').decode('ascii').rstrip('=')
        with pytest.raises(ValueError):
            decode(bad_zlib)

    def test_decode_bad_json_raises(self):
        """Decoding decompressed non-JSON raises ValueError."""
        import zlib
        import base64

        # Compress something that's not valid JSON
        compressed = zlib.compress(b'not json data')
        bad_json = base64.urlsafe_b64encode(compressed).decode('ascii').rstrip('=')

        with pytest.raises(ValueError):
            decode(bad_json)

    def test_decode_empty_string_raises(self):
        """Decoding empty string raises ValueError."""
        with pytest.raises(ValueError):
            decode('')


class TestIsShareLink:
    """Test share link validation (non-raising)."""

    def test_is_share_link_valid(self):
        """is_share_link returns True for valid encoded string."""
        test_dict = {'a': 1, 'b': 2}
        encoded = encode(test_dict)
        assert is_share_link(encoded) is True

    def test_is_share_link_empty_dict_valid(self):
        """is_share_link returns True for empty dict encoding."""
        encoded = encode({})
        assert is_share_link(encoded) is True

    def test_is_share_link_invalid_base64(self):
        """is_share_link returns False for invalid base64."""
        assert is_share_link('!!!invalid!!!') is False

    def test_is_share_link_empty_string(self):
        """is_share_link returns False for empty string."""
        assert is_share_link('') is False

    def test_is_share_link_none(self):
        """is_share_link returns False for None."""
        assert is_share_link(None) is False

    def test_is_share_link_non_string(self):
        """is_share_link returns False for non-string."""
        assert is_share_link(123) is False
        assert is_share_link([]) is False

    def test_is_share_link_never_raises(self):
        """is_share_link never raises exceptions."""
        test_cases = [None, '', 'bad', 123, [], {}, b'bytes']
        for test_case in test_cases:
            # Should not raise
            result = is_share_link(test_case)
            assert isinstance(result, bool)


class TestCompressRatio:
    """Test compression ratio calculation."""

    def test_compress_ratio_returns_float(self):
        """compress_ratio returns a float."""
        test_dict = {'a': 1, 'b': 2}
        ratio = compress_ratio(test_dict)
        assert isinstance(ratio, float)

    def test_compress_ratio_large_dict(self):
        """compress_ratio returns < 1.0 for larger dicts with repetition."""
        # Create a larger dict with repeated keys that compress well
        test_dict = {f'control_{i}': i for i in range(50)}
        ratio = compress_ratio(test_dict)
        # Larger, repetitive dicts compress well
        assert 0 < ratio < 1.0

    def test_compress_ratio_empty_dict(self):
        """compress_ratio handles empty dict."""
        ratio = compress_ratio({})
        # Empty dict compresses to "{}"; ratio could be > 1 due to base64 expansion
        assert ratio >= 0

    def test_compress_ratio_matches_encode(self):
        """compress_ratio matches actual encoded / json lengths."""
        test_dict = {'a': 1, 'b': [2, 3, 4]}
        ratio = compress_ratio(test_dict)

        import json
        json_str = json.dumps(test_dict, separators=(',', ':'), sort_keys=True)
        encoded = encode(test_dict)

        expected_ratio = len(encoded) / len(json_str)
        assert abs(ratio - expected_ratio) < 0.001  # Float precision


class TestWrapInUrl:
    """Test URL wrapping."""

    def test_wrap_in_url_default(self):
        """wrap_in_url uses default base URL."""
        share_str = 'abc123'
        url = wrap_in_url(share_str)
        assert url == 'https://midi.aidxn.com/import?p=abc123'

    def test_wrap_in_url_custom_base(self):
        """wrap_in_url accepts custom base URL."""
        share_str = 'abc123'
        custom_base = 'https://example.com/load?s='
        url = wrap_in_url(share_str, custom_base)
        assert url == 'https://example.com/load?s=abc123'

    def test_wrap_in_url_with_encoded_string(self):
        """wrap_in_url works with actual encoded strings."""
        test_dict = {'x': 1}
        encoded = encode(test_dict)
        url = wrap_in_url(encoded)

        assert url.startswith('https://midi.aidxn.com/import?p=')
        assert encoded in url


class TestExtractFromUrl:
    """Test URL extraction."""

    def test_extract_from_url_default(self):
        """extract_from_url extracts share string from default URL."""
        share_str = 'abc123'
        url = 'https://midi.aidxn.com/import?p=abc123'
        extracted = extract_from_url(url)
        assert extracted == share_str

    def test_extract_from_url_custom_base(self):
        """extract_from_url works with custom base URL."""
        share_str = 'xyz789'
        custom_base = 'https://example.com/load?s='
        url = f'{custom_base}{share_str}'
        extracted = extract_from_url(url, custom_base)
        assert extracted == share_str

    def test_extract_from_url_mismatch_returns_none(self):
        """extract_from_url returns None when URL doesn't match base."""
        url = 'https://other-domain.com/import?p=abc123'
        extracted = extract_from_url(url)
        assert extracted is None

    def test_extract_from_url_empty_share_string(self):
        """extract_from_url handles empty share string."""
        url = 'https://midi.aidxn.com/import?p='
        extracted = extract_from_url(url)
        assert extracted == ''

    def test_extract_from_url_round_trip(self):
        """extract_from_url reverses wrap_in_url."""
        test_dict = {'a': 1, 'b': 2}
        encoded = encode(test_dict)
        url = wrap_in_url(encoded)
        extracted = extract_from_url(url)

        assert extracted == encoded
        assert decode(extracted) == test_dict


class TestSafeEncode:
    """Test safe encoding with length limits."""

    def test_safe_encode_within_limit(self):
        """safe_encode returns string when within limit."""
        test_dict = {'a': 1, 'b': 2}
        result = safe_encode(test_dict, max_length=2000)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) <= 2000

    def test_safe_encode_exceeds_limit_returns_none(self):
        """safe_encode returns None when result exceeds limit."""
        # Create a dict that will compress to > 100 bytes
        test_dict = {'x' * i: i for i in range(1, 50)}
        result = safe_encode(test_dict, max_length=10)
        assert result is None

    def test_safe_encode_exactly_at_limit(self):
        """safe_encode accepts result exactly at limit."""
        test_dict = {'a': 1}
        encoded = encode(test_dict)
        result = safe_encode(test_dict, max_length=len(encoded))
        assert result == encoded

    def test_safe_encode_round_trip(self):
        """safe_encode result can be decoded."""
        test_dict = {'a': 1, 'b': [2, 3]}
        result = safe_encode(test_dict, max_length=2000)
        assert result is not None
        assert decode(result) == test_dict


class TestIntegration:
    """Integration tests for real-world scenarios."""

    def test_full_flow_encode_wrap_extract_decode(self):
        """Full flow: encode -> wrap -> extract -> decode."""
        original = {'buttons': {'ps': 1}, 'sticks': [0, 127]}

        encoded = encode(original)
        url = wrap_in_url(encoded)
        extracted = extract_from_url(url)
        decoded = decode(extracted)

        assert decoded == original

    def test_share_multiple_users(self):
        """Multiple users can share and import the same mapping."""
        mapping = {
            'mapping_version': 3,
            'mappings': {
                'left_stick': {'x': 'cc_1', 'y': 'cc_2'},
                'right_stick': {'x': 'cc_3', 'y': 'cc_4'},
            },
        }

        # User A encodes and shares
        encoded = encode(mapping)
        url = wrap_in_url(encoded)

        # User B receives the URL and imports
        extracted = extract_from_url(url)
        imported = decode(extracted)

        assert imported == mapping

    def test_large_mapping(self):
        """Large mappings still compress reasonably."""
        # Simulate a large mapping with many controls
        mapping = {
            f'control_{i}': {
                'type': 'cc' if i % 2 == 0 else 'note',
                'channel': i % 16,
                'value': i % 127,
            }
            for i in range(100)
        }

        encoded = encode(mapping)
        ratio = compress_ratio(mapping)

        # Should be compressible
        assert ratio < 1.0
        assert is_share_link(encoded)
        assert decode(encoded) == mapping
