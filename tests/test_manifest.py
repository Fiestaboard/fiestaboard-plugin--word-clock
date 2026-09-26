"""Guards that keep manifest, code, docs and changelog from drifting apart.

The manifest is not just metadata — FiestaBoard renders the plugin directory
from it and the template editor offers whatever variables it declares. A field
that no longer matches the code is a broken listing, not a cosmetic slip.
"""

import json
import pathlib
import re

import pytest

from plugins.word_clock import DEFAULT_LANGUAGE, DOT_COLORS, LANGUAGES, WordClockPlugin
from src.devices import BoardContext

ROOT = pathlib.Path(__file__).resolve().parent.parent
BOARD_SHAPES = {"flagship": (6, 22), "note": (3, 15)}
NOTE_ROWS, NOTE_COLS = 3, 15
COLOR_MARKER = re.compile(r"\{(?:6[3-9]|7[01])\}")

# The language and times the committed previews were rendered from. Changing a
# preview means changing these too — that is the point.
PREVIEW_LANGUAGE = "en"
PREVIEW_TIMES = {"flagship": (10, 15), "note": (9, 30)}
# The note_array preview isn't in PREVIEW_TIMES/BOARD_SHAPES above because its
# board shape isn't fixed -- it comes from the preview's own notes_wide /
# notes_tall, the way a real note array's shape comes from the board owner's
# hardware rather than the device type.
NOTE_ARRAY_PREVIEW_TIME = (11, 0)


@pytest.fixture(scope="module")
def manifest():
    return json.loads((ROOT / "manifest.json").read_text())


def count_tiles(row: str) -> int:
    """Flaps used by a row. A color marker like ``{66}`` is one tile, not four."""
    return len(COLOR_MARKER.sub("X", row))


class TestIdentity:
    def test_id_matches_the_plugin_class(self, manifest):
        assert manifest["id"] == WordClockPlugin(manifest).plugin_id

    def test_version_is_semver(self, manifest):
        assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"])

    def test_version_matches_the_changelog(self, manifest):
        """The changelog is the source of truth; a release without an entry is a lie."""
        changelog = (ROOT / "CHANGELOG.md").read_text()
        released = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
        assert released, "CHANGELOG.md has no released versions"
        assert manifest["version"] == released[0], (
            f"manifest says {manifest['version']}, newest changelog entry is {released[0]}"
        )

    def test_changelog_versions_descend(self):
        changelog = (ROOT / "CHANGELOG.md").read_text()
        released = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
        keyed = [tuple(int(part) for part in v.split(".")) for v in released]
        assert keyed == sorted(keyed, reverse=True)


class TestSettingsSchema:
    def test_language_options_match_the_code(self, manifest):
        language = manifest["settings_schema"]["properties"]["language"]
        assert tuple(language["enum"]) == LANGUAGES

    def test_language_default_matches_the_code_fallback(self, manifest):
        """The schema default and the fetch_data fallback must be the same language.

        They are set in different files; if they drift, a board configured
        purely from defaults renders in a language the settings form does not
        show as selected.
        """
        assert manifest["settings_schema"]["properties"]["language"]["default"] == DEFAULT_LANGUAGE

    def test_preview_language_is_the_default_language(self, manifest):
        """The plugin card should show what a fresh install actually produces."""
        assert PREVIEW_LANGUAGE == DEFAULT_LANGUAGE

    def test_every_enum_has_a_label(self, manifest):
        for name, prop in manifest["settings_schema"]["properties"].items():
            if "enum" in prop:
                assert len(prop.get("enumNames", [])) == len(prop["enum"]), f"{name} labels do not line up"

    def test_every_enum_default_is_one_of_its_options(self, manifest):
        for name, prop in manifest["settings_schema"]["properties"].items():
            if "enum" in prop and "default" in prop:
                assert prop["default"] in prop["enum"], f"{name} default is not an option"

    def test_dot_colors_match_the_code(self, manifest):
        colors = manifest["settings_schema"]["properties"]["dot_color"]["enum"]
        assert set(colors) == set(DOT_COLORS)


class TestVariables:
    def test_declared_variables_are_the_ones_the_plugin_produces(self, manifest):
        """A declared variable that never materialises renders as blank on the board."""
        plugin = WordClockPlugin(manifest)
        plugin.config = {"timezone": "Europe/Berlin"}
        produced = set(plugin.get_data(BoardContext.from_device_type("flagship")).data)
        declared = set(manifest["variables"]["simple"])
        # "formatted" is the DisplayService fallback, not a template variable.
        assert produced - {"formatted"} == declared

    def test_every_variable_names_a_group_that_exists(self, manifest):
        groups = set(manifest["variables"]["groups"])
        for name, spec in manifest["variables"]["simple"].items():
            assert spec["group"] in groups, f"{name} points at an unknown group"

    def test_max_lengths_agree_with_the_variable_declarations(self, manifest):
        for name, declared in manifest["max_lengths"].items():
            if name in manifest["variables"]["simple"]:
                assert manifest["variables"]["simple"][name]["max_length"] == declared


def _preview_board(preview: dict) -> BoardContext:
    """The board a preview entry describes.

    ``flagship``/``note`` are fixed shapes; ``note_array`` has none of its
    own -- like the real hardware, its shape comes from ``notes_wide`` /
    ``notes_tall`` on the entry itself.
    """
    if preview["device_type"] == "note_array":
        return BoardContext(
            device_type="note_array",
            rows=preview["notes_tall"] * NOTE_ROWS,
            cols=preview["notes_wide"] * NOTE_COLS,
        )
    return BoardContext.from_device_type(preview["device_type"])


class TestBoardPreviews:
    def test_teaser_fits_the_narrowest_board(self, manifest):
        assert count_tiles(manifest["teaser"]) <= 15

    def test_preview_rows_fit_their_board(self, manifest):
        for preview in manifest["previews"]:
            board = _preview_board(preview)
            assert len(preview["rows"]) <= board.rows
            for row in preview["rows"]:
                assert count_tiles(row) <= board.cols, f"{preview['device_type']} row is too wide"

    def test_both_board_shapes_are_covered(self, manifest):
        """Every fixed shape (Flagship, Note) has a preview -- device types
        with no fixed shape (note_array) are checked separately below since
        "covered" doesn't mean the same thing for them.
        """
        shapes = {p["device_type"] for p in manifest["previews"]}
        assert set(BOARD_SHAPES) <= shapes

    def test_a_note_array_preview_exists(self, manifest):
        """A FiestaPanel is a note array -- without this preview the plugin
        directory shows nothing for how the plugin looks on one.
        """
        arrays = [p for p in manifest["previews"] if p["device_type"] == "note_array"]
        assert arrays, "no note_array preview in manifest.json previews"
        for preview in arrays:
            assert 1 <= preview["notes_wide"] <= 4
            assert 1 <= preview["notes_tall"] <= 4

    @pytest.mark.parametrize("device_type", sorted(BOARD_SHAPES))
    def test_previews_match_what_the_plugin_actually_renders(self, manifest, device_type, monkeypatch):
        """A hand-edited preview that no longer matches the code misleads the directory."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        hour, minute = PREVIEW_TIMES[device_type]
        plugin = WordClockPlugin(manifest)
        plugin.config = {"timezone": "Europe/Berlin", "language": PREVIEW_LANGUAGE}
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, hour, minute, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        rendered = plugin.get_data(BoardContext.from_device_type(device_type)).formatted_lines
        declared = next(p["rows"] for p in manifest["previews"] if p["device_type"] == device_type)
        assert declared == rendered

    def test_note_array_preview_matches_what_the_plugin_actually_renders(self, manifest, monkeypatch):
        """Same guard as above, for the note_array preview's own declared shape."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        hour, minute = NOTE_ARRAY_PREVIEW_TIME
        preview = next(p for p in manifest["previews"] if p["device_type"] == "note_array")
        plugin = WordClockPlugin(manifest)
        plugin.config = {"timezone": "Europe/Berlin", "language": PREVIEW_LANGUAGE}
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, hour, minute, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        rendered = plugin.get_data(_preview_board(preview)).formatted_lines
        assert preview["rows"] == rendered


class TestDocumentation:
    def test_every_screenshot_exists(self, manifest):
        for shot in manifest["screenshots"]:
            assert (ROOT / shot["src"]).is_file(), f"missing {shot['src']}"

    def test_exactly_one_screenshot_is_primary(self, manifest):
        assert sum(bool(s.get("primary")) for s in manifest["screenshots"]) == 1

    def test_every_screenshot_has_alt_text(self, manifest):
        for shot in manifest["screenshots"]:
            assert shot.get("alt", "").strip(), f"{shot['src']} has no alt text"

    @pytest.mark.parametrize("document", ["README.md", "docs/SETUP.md"])
    def test_docs_link_only_to_images_that_exist(self, document):
        text = (ROOT / document).read_text()
        for target in re.findall(r"!\[[^\]]*\]\(\./([^)]+)\)", text):
            source = ROOT / ("docs" if document.startswith("docs/") else "") / target
            resolved = source if source.is_file() else ROOT / target
            assert resolved.is_file(), f"{document} references missing image {target}"
