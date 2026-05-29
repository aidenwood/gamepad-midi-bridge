"""Tests for mapping slug validator."""

import pytest
from gamepad_midi_bridge.mapping_slug_validator import (
    normalize,
    validate,
    is_valid,
    suggest_alternatives,
    slug_from_name,
    SlugValidation,
    RESERVED_SLUGS,
    MAX_SLUG_LENGTH,
    MIN_SLUG_LENGTH,
)


class TestNormalize:
    """Tests for the normalize() function."""

    def test_normalize_simple_lowercase(self):
        """Simple text is lowercased."""
        assert normalize("Hello") == "hello"

    def test_normalize_with_spaces(self):
        """Spaces are converted to hyphens."""
        assert normalize("My Lead 2") == "my-lead-2"

    def test_normalize_with_punctuation(self):
        """Punctuation is stripped."""
        assert normalize("My Lead 2!") == "my-lead-2"

    def test_normalize_with_underscores(self):
        """Underscores are converted to hyphens."""
        assert normalize("my_cool_preset") == "my-cool-preset"

    def test_normalize_multiple_underscores(self):
        """Multiple underscores collapse to single hyphen."""
        assert normalize("__weird__name__") == "weird-name"

    def test_normalize_multiple_spaces(self):
        """Multiple spaces collapse to single hyphen."""
        assert normalize("My   Lead") == "my-lead"

    def test_normalize_mixed_whitespace_and_underscores(self):
        """Mixed whitespace and underscores collapse to hyphens."""
        assert normalize("my  _  weird  _  name") == "my-weird-name"

    def test_normalize_leading_trailing_hyphens_stripped(self):
        """Leading and trailing hyphens are stripped."""
        assert normalize("-hello-world-") == "hello-world"
        assert normalize("___hello___") == "hello"

    def test_normalize_unicode_accent_removal(self):
        """Accented characters are normalised (Café -> cafe)."""
        assert normalize("Café") == "cafe"
        assert normalize("Résumé") == "resume"
        assert normalize("naïve") == "naive"

    def test_normalize_empty_string(self):
        """Empty string returns empty string."""
        assert normalize("") == ""

    def test_normalize_whitespace_only(self):
        """Whitespace-only string returns empty."""
        assert normalize("   ") == ""
        assert normalize("\t\n") == ""

    def test_normalize_special_chars_stripped(self):
        """Special characters are stripped (removed, not hyphenated)."""
        assert normalize("hello@world#test$name") == "helloworldtestname"

    def test_normalize_special_chars_between_words_with_spaces(self):
        """Special characters between words with spaces become hyphens."""
        assert normalize("hello @ world") == "hello-world"

    def test_normalize_with_numbers(self):
        """Numbers are preserved."""
        assert normalize("Preset 123") == "preset-123"

    def test_normalize_collapse_hyphens(self):
        """Multiple hyphens collapse to single."""
        assert normalize("hello---world") == "hello-world"

    def test_normalize_truncate_long_slug(self):
        """Slug longer than MAX_SLUG_LENGTH is truncated."""
        long_slug = "a" * (MAX_SLUG_LENGTH + 10)
        result = normalize(long_slug)
        assert len(result) == MAX_SLUG_LENGTH

    def test_normalize_preserves_short_valid_slug(self):
        """Valid short slug is unchanged (after normalisation)."""
        assert normalize("my-cool-preset") == "my-cool-preset"

    def test_normalize_only_punctuation(self):
        """String with only punctuation returns empty."""
        assert normalize("!!!???") == ""

    def test_normalize_unicode_emoji_stripped(self):
        """Emoji and unicode symbols are stripped."""
        assert normalize("My Preset 🎵") == "my-preset"

    def test_normalize_mixed_complex(self):
        """Complex mix of all rules applied correctly."""
        assert normalize("__My  COOL  Preset-2023!__") == "my-cool-preset-2023"


class TestValidate:
    """Tests for the validate() function."""

    def test_validate_empty_string_error(self):
        """Empty string produces error."""
        result = validate("")
        assert result.valid is False
        assert len(result.errors) > 0
        assert "empty" in result.errors[0].lower()

    def test_validate_whitespace_only_error(self):
        """Whitespace-only string produces error."""
        result = validate("   ")
        assert result.valid is False

    def test_validate_too_short_error(self):
        """Slug shorter than MIN_SLUG_LENGTH produces error."""
        result = validate("a")
        assert result.valid is False
        assert any("short" in e.lower() for e in result.errors)

    def test_validate_min_length_valid(self):
        """Slug with exactly MIN_SLUG_LENGTH characters is valid."""
        result = validate("ab")
        assert result.valid is True
        assert result.normalized == "ab"
        assert len(result.errors) == 0

    def test_validate_long_slug_truncated_in_normalize(self):
        """Slug longer than MAX_SLUG_LENGTH is truncated by normalize."""
        long_slug = "a" * (MAX_SLUG_LENGTH + 1)
        result = validate(long_slug)
        # It gets truncated in normalize, so it's technically valid after normalisation
        assert len(result.normalized) == MAX_SLUG_LENGTH
        # But we get a normalisation warning
        assert any("normalised" in w.lower() for w in result.warnings)

    def test_validate_reserved_slug_error(self):
        """Reserved slug names produce error."""
        for reserved in RESERVED_SLUGS:
            result = validate(reserved)
            assert result.valid is False
            assert any("reserved" in e.lower() for e in result.errors)

    def test_validate_reserved_slug_case_insensitive(self):
        """Reserved check is case-insensitive (normalised)."""
        result = validate("DEFAULT")
        assert result.valid is False
        assert any("reserved" in e.lower() for e in result.errors)

    def test_validate_normalisation_warning(self):
        """Slug changed by normalisation produces warning."""
        result = validate("My Lead!")
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "normalised" in result.warnings[0].lower()
        assert result.normalized == "my-lead"

    def test_validate_special_chars_stripped(self):
        """Slug with special characters that are stripped normalises correctly."""
        result = validate("hello@world")
        assert result.valid is True  # It normalises successfully
        assert result.normalized == "helloworld"

    def test_validate_near_max_length_warning(self):
        """Slug near max length produces warning."""
        near_max = "a" * int(MAX_SLUG_LENGTH * 0.9)
        result = validate(near_max)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert "close to maximum" in result.warnings[0].lower()

    def test_validate_valid_slug(self):
        """Valid slug produces no errors or warnings."""
        result = validate("my-cool-preset")
        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert result.normalized == "my-cool-preset"

    def test_validate_valid_with_numbers(self):
        """Valid slug with numbers produces no errors."""
        result = validate("preset-2024")
        assert result.valid is True
        assert result.normalized == "preset-2024"

    def test_validate_result_to_dict(self):
        """SlugValidation.to_dict() serializes correctly."""
        result = validate("test-slug")
        d = result.to_dict()
        assert d["valid"] is True
        assert d["normalized"] == "test-slug"
        assert isinstance(d["errors"], list)
        assert isinstance(d["warnings"], list)

    def test_validate_result_from_dict(self):
        """SlugValidation.from_dict() deserializes correctly."""
        original = validate("test-slug")
        d = original.to_dict()
        restored = SlugValidation.from_dict(d)
        assert restored.valid == original.valid
        assert restored.normalized == original.normalized
        assert restored.errors == original.errors
        assert restored.warnings == original.warnings

    def test_validate_normalises_to_empty_error(self):
        """Slug that normalises to empty produces error."""
        result = validate("!!!???@@@")
        assert result.valid is False
        assert any("normalises to empty" in e.lower() for e in result.errors)


class TestIsValid:
    """Tests for the is_valid() function (boolean shortcut)."""

    def test_is_valid_true_for_clean_slug(self):
        """Valid slug returns True."""
        assert is_valid("my-cool-preset") is True

    def test_is_valid_false_for_empty(self):
        """Empty slug returns False."""
        assert is_valid("") is False

    def test_is_valid_false_for_too_short(self):
        """Too-short slug returns False."""
        assert is_valid("a") is False

    def test_is_valid_false_for_reserved(self):
        """Reserved slug returns False."""
        assert is_valid("default") is False

    def test_is_valid_true_with_normalisation(self):
        """Slug valid after normalisation returns True."""
        assert is_valid("My Lead!") is True


class TestSuggestAlternatives:
    """Tests for the suggest_alternatives() function."""

    def test_suggest_alternatives_basic(self):
        """Basic suggestion generates numbered variants."""
        suggestions = suggest_alternatives("lead", [])
        assert len(suggestions) == 5
        assert suggestions == ["lead-2", "lead-3", "lead-4", "lead-5", "lead-6"]

    def test_suggest_alternatives_skips_existing(self):
        """Already-used suggestions are skipped."""
        existing = ["lead", "lead-2"]
        suggestions = suggest_alternatives("lead", existing)
        assert "lead-2" not in suggestions
        assert suggestions == ["lead-3", "lead-4", "lead-5", "lead-6", "lead-7"]

    def test_suggest_alternatives_all_exist(self):
        """If all suggestions exist, return what's available (up to 5)."""
        existing = ["lead", "lead-2", "lead-3", "lead-4", "lead-5", "lead-6", "lead-7"]
        suggestions = suggest_alternatives("lead", existing)
        # All range 2-7 are taken, so empty
        assert suggestions == []

    def test_suggest_alternatives_partial_exist(self):
        """Mix of existing and new suggestions."""
        existing = ["lead", "lead-2", "lead-4"]
        suggestions = suggest_alternatives("lead", existing)
        assert "lead-2" not in suggestions
        assert "lead-4" not in suggestions
        assert "lead-3" in suggestions

    def test_suggest_alternatives_empty_input(self):
        """Empty input returns empty list."""
        assert suggest_alternatives("", []) == []
        assert suggest_alternatives("   ", []) == []

    def test_suggest_alternatives_too_short(self):
        """Too-short slug returns empty list."""
        assert suggest_alternatives("a", []) == []

    def test_suggest_alternatives_normalised(self):
        """Base slug is normalised before generating suggestions."""
        suggestions = suggest_alternatives("My Lead!", [])
        assert suggestions[0] == "my-lead-2"

    def test_suggest_alternatives_max_5_results(self):
        """Never returns more than 5 suggestions."""
        suggestions = suggest_alternatives("base", [])
        assert len(suggestions) <= 5

    def test_suggest_alternatives_only_valid_candidates(self):
        """All suggestions are valid slugs."""
        suggestions = suggest_alternatives("test", [])
        for slug in suggestions:
            assert is_valid(slug) is True


class TestSlugFromName:
    """Tests for the slug_from_name() function."""

    def test_slug_from_name_basic(self):
        """Basic name conversion."""
        assert slug_from_name("My Cool Preset") == "my-cool-preset"

    def test_slug_from_name_with_punctuation(self):
        """Name with punctuation is cleaned."""
        assert slug_from_name("My Cool Preset!") == "my-cool-preset"

    def test_slug_from_name_with_unicode(self):
        """Name with unicode accents is normalised."""
        assert slug_from_name("Café Résumé") == "cafe-resume"

    def test_slug_from_name_empty(self):
        """Empty name returns empty slug."""
        assert slug_from_name("") == ""

    def test_slug_from_name_is_normalize_alias(self):
        """slug_from_name is equivalent to normalize."""
        test_names = [
            "My Preset",
            "UPPERCASE",
            "with-hyphens",
            "with_underscores",
            "MixedCase",
        ]
        for name in test_names:
            assert slug_from_name(name) == normalize(name)


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_workflow_normalize_then_validate(self):
        """Typical workflow: normalise user input, then validate."""
        user_input = "My Cool Preset!"
        normalized = normalize(user_input)
        assert normalized == "my-cool-preset"
        validation = validate(normalized)
        assert validation.valid is True

    def test_workflow_validate_returns_normalized(self):
        """Validate returns the normalised slug even if user input is messy."""
        result = validate("My Cool Preset!")
        assert result.valid is True
        assert result.normalized == "my-cool-preset"

    def test_workflow_suggest_alternatives_for_collision(self):
        """User creates "my-preset", collision detected, suggest alternatives."""
        existing_presets = ["my-preset", "my-preset-2"]
        suggestions = suggest_alternatives("my-preset", existing_presets)
        assert "my-preset-3" in suggestions
        assert len(suggestions) > 0

    def test_workflow_build_preset_list(self):
        """Simulate building a list of valid presets from user names."""
        user_names = ["My Lead", "Cool Drums!", "bass", "Café Vibes"]
        slugs = [slug_from_name(name) for name in user_names]
        validations = [validate(slug) for slug in slugs]
        # All should be valid except "bass" is too short (only 4 chars, but MIN=2, so valid)
        assert all(v.valid for v in validations)
        assert slugs == ["my-lead", "cool-drums", "bass", "cafe-vibes"]

    def test_constants_exported(self):
        """Test that constants are accessible for external use."""
        assert isinstance(RESERVED_SLUGS, set)
        assert "default" in RESERVED_SLUGS
        assert isinstance(MAX_SLUG_LENGTH, int)
        assert isinstance(MIN_SLUG_LENGTH, int)
        assert MAX_SLUG_LENGTH > MIN_SLUG_LENGTH
