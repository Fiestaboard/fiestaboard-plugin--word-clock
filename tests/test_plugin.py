"""Tests for the Word Clock plugin."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from plugins.word_clock import (
    DEFAULT_LANGUAGE,
    DE_PREFIX,
    LANGUAGES,
    build_phrase,
    hour_phrase,
    layout,
    prefix_for,
    round_to_step,
    spoken_hour,
    to_board_text,
    wrap_words,
)
from plugins.word_clock import _letterspace
from src.devices import BoardContext

FLAGSHIP = BoardContext.from_device_type("flagship")
NOTE = BoardContext.from_device_type("note")

ALL_STEPS = list(range(0, 60, 5))


def phrase_de(hour, step, style="standard", umlauts="expand"):
    return to_board_text(build_phrase(hour, step, "de", style), umlauts)


def phrase_en(hour, step):
    return to_board_text(build_phrase(hour, step, "en", "standard"), "expand")


def spoken(hour, step, language, style="standard"):
    """The full board sentence: prefix plus phrase, as fetch_data assembles it."""
    phrase = to_board_text(build_phrase(hour, step, language, style), "expand")
    prefix = to_board_text(prefix_for(language, spoken_hour(hour, step, language, style)), "expand")
    return f"{prefix} {phrase}"


class TestGermanPhrases:
    """The German half hour is the part that is easy to get wrong."""

    @pytest.mark.parametrize(
        ("step", "expected"),
        [
            (0, "ZEHN UHR"),
            (5, "FUENF NACH ZEHN"),
            (10, "ZEHN NACH ZEHN"),
            (15, "VIERTEL NACH ZEHN"),
            (20, "ZWANZIG NACH ZEHN"),
            (25, "FUENF VOR HALB ELF"),
            (30, "HALB ELF"),
            (35, "FUENF NACH HALB ELF"),
            (40, "ZWANZIG VOR ELF"),
            (45, "VIERTEL VOR ELF"),
            (50, "ZEHN VOR ELF"),
            (55, "FUENF VOR ELF"),
        ],
    )
    def test_standard_hour_ten(self, step, expected):
        assert phrase_de(10, step) == expected

    @pytest.mark.parametrize(
        ("step", "expected"),
        [
            (15, "VIERTEL ELF"),
            (20, "ZEHN VOR HALB ELF"),
            (40, "ZEHN NACH HALB ELF"),
            (45, "DREIVIERTEL ELF"),
        ],
    )
    def test_regional_counts_into_the_coming_hour(self, step, expected):
        assert phrase_de(10, step, style="regional") == expected

    def test_regional_leaves_untouched_steps_alone(self):
        assert phrase_de(10, 30, style="regional") == phrase_de(10, 30)

    def test_one_oclock_is_ein_not_eins(self):
        assert phrase_de(13, 0) == "EIN UHR"

    def test_one_keeps_its_s_when_not_followed_by_uhr(self):
        assert phrase_de(13, 5) == "FUENF NACH EINS"

    def test_hour_wraps_from_twelve_to_one(self):
        assert phrase_de(12, 30) == "HALB EINS"

    def test_midnight_is_twelve(self):
        assert phrase_de(0, 0) == "ZWOELF UHR"


class TestEnglishPhrases:
    @pytest.mark.parametrize(
        ("step", "expected"),
        [
            (0, "TEN O'CLOCK"),
            (5, "FIVE PAST TEN"),
            (15, "QUARTER PAST TEN"),
            (25, "TWENTY FIVE PAST TEN"),
            (30, "HALF PAST TEN"),
            (35, "TWENTY FIVE TO ELEVEN"),
            (45, "QUARTER TO ELEVEN"),
            (55, "FIVE TO ELEVEN"),
        ],
    )
    def test_standard_hour_ten(self, step, expected):
        assert phrase_en(10, step) == expected

    def test_apostrophe_survives_the_charset_filter(self):
        assert "'" in phrase_en(10, 0)


class TestSpanishPhrases:
    """Spanish agrees the copula with the hour and pivots to MENOS after the half."""

    @pytest.mark.parametrize(
        ("step", "expected"),
        [
            (0, "SON LAS DIEZ EN PUNTO"),
            (5, "SON LAS DIEZ Y CINCO"),
            (15, "SON LAS DIEZ Y CUARTO"),
            (25, "SON LAS DIEZ Y VEINTICINCO"),
            (30, "SON LAS DIEZ Y MEDIA"),
            (35, "SON LAS ONCE MENOS VEINTICINCO"),
            (45, "SON LAS ONCE MENOS CUARTO"),
            (55, "SON LAS ONCE MENOS CINCO"),
        ],
    )
    def test_hour_ten(self, step, expected):
        assert spoken(10, step, "es") == expected

    def test_one_oclock_takes_the_singular_copula(self):
        assert spoken(13, 0, "es") == "ES LA UNA EN PUNTO"

    def test_the_copula_follows_the_named_hour_not_the_clock(self):
        """12:40 names one o'clock, so it is singular even though the hour is twelve."""
        assert spoken(12, 40, "es") == "ES LA UNA MENOS VEINTE"

    def test_half_past_twelve_stays_plural(self):
        assert spoken(12, 30, "es") == "SON LAS DOCE Y MEDIA"


class TestFrenchPhrases:
    """French carries the unit with the hour and replaces the twelves outright."""

    @pytest.mark.parametrize(
        ("step", "expected"),
        [
            (0, "IL EST DIX HEURES"),
            (5, "IL EST DIX HEURES CINQ"),
            (15, "IL EST DIX HEURES ET QUART"),
            (30, "IL EST DIX HEURES ET DEMIE"),
            (35, "IL EST ONZE HEURES MOINS VINGT-CINQ"),
            (45, "IL EST ONZE HEURES MOINS LE QUART"),
            (55, "IL EST ONZE HEURES MOINS CINQ"),
        ],
    )
    def test_hour_ten(self, step, expected):
        assert spoken(10, step, "fr") == expected

    def test_one_oclock_uses_the_singular_unit(self):
        assert spoken(13, 0, "fr") == "IL EST UNE HEURE"

    def test_noon_is_midi(self):
        assert spoken(12, 0, "fr") == "IL EST MIDI"

    def test_midnight_is_minuit(self):
        assert spoken(0, 0, "fr") == "IL EST MINUIT"

    def test_midi_carries_its_minutes(self):
        assert spoken(12, 15, "fr") == "IL EST MIDI ET QUART"

    def test_counting_down_into_noon_says_midi(self):
        assert spoken(11, 45, "fr") == "IL EST MIDI MOINS LE QUART"

    def test_counting_down_into_midnight_says_minuit(self):
        assert spoken(23, 45, "fr") == "IL EST MINUIT MOINS LE QUART"

    def test_the_hyphen_survives_the_charset_filter(self):
        assert "VINGT-CINQ" in spoken(10, 25, "fr")


class TestHourPhrase:
    @pytest.mark.parametrize(
        ("language", "hour", "expected"),
        [
            ("de", 13, "EINS"),
            ("en", 13, "ONE"),
            ("es", 13, "UNA"),
            ("fr", 13, "UNE HEURE"),
            ("fr", 14, "DEUX HEURES"),
            ("fr", 12, "MIDI"),
            ("fr", 0, "MINUIT"),
            ("de", 0, "ZWÖLF"),
            ("es", 0, "DOCE"),
        ],
    )
    def test_hour_is_named_the_way_the_language_does(self, language, hour, expected):
        assert hour_phrase(hour, language) == expected


class TestPrefix:
    @pytest.mark.parametrize(
        ("language", "named_hour", "expected"),
        [
            ("de", 5, "ES IST"),
            ("en", 5, "IT IS"),
            ("fr", 5, "IL EST"),
            ("fr", 1, "IL EST"),
            ("es", 5, "SON LAS"),
            ("es", 1, "ES LA"),
        ],
    )
    def test_only_spanish_varies_with_the_hour(self, language, named_hour, expected):
        assert prefix_for(language, named_hour) == expected


class TestSpokenHour:
    def test_before_half_past_names_the_current_hour(self):
        assert spoken_hour(10, 15, "de", "standard") == 10

    def test_from_twenty_five_past_names_the_coming_hour(self):
        assert spoken_hour(10, 25, "de", "standard") == 11

    def test_regional_quarter_names_the_coming_hour(self):
        assert spoken_hour(10, 15, "de", "regional") == 11

    def test_english_to_names_the_coming_hour(self):
        assert spoken_hour(23, 45, "en", "standard") == 12


class TestBoardText:
    def test_expand_writes_two_letter_umlauts(self):
        assert to_board_text("FÜNF ZWÖLF", "expand") == "FUENF ZWOELF"

    def test_strip_writes_the_bare_vowel(self):
        assert to_board_text("FÜNF ZWÖLF", "strip") == "FUNF ZWOLF"

    def test_lowercase_is_raised_to_board_case(self):
        assert to_board_text("halb zehn", "expand") == "HALB ZEHN"

    def test_characters_without_a_tile_are_dropped(self):
        assert to_board_text("A~B|C", "expand") == "ABC"


class TestRounding:
    def test_down_floors_to_the_five_minute_step(self):
        assert round_to_step(10, 17, "down") == (10, 15, 2)

    def test_nearest_rounds_up_and_reports_no_leftover(self):
        assert round_to_step(10, 18, "nearest") == (10, 20, 0)

    def test_nearest_carries_into_the_next_hour(self):
        assert round_to_step(10, 58, "nearest") == (11, 0, 0)

    def test_nearest_carry_wraps_at_midnight(self):
        assert round_to_step(23, 59, "nearest") == (0, 0, 0)

    def test_down_never_carries(self):
        assert round_to_step(10, 59, "down") == (10, 55, 4)


class TestWrapping:
    def test_words_are_packed_greedily(self):
        assert wrap_words("ES IST HALB ZEHN", 12) == ["ES IST HALB", "ZEHN"]

    def test_an_exact_fit_stays_on_one_line(self):
        assert wrap_words("ES IST HALB", 11) == ["ES IST HALB"]

    def test_a_word_wider_than_the_board_gets_its_own_line(self):
        assert wrap_words("DREIVIERTEL ELF", 8) == ["DREIVIERTEL", "ELF"]

    def test_empty_text_produces_no_lines(self):
        assert wrap_words("   ", 15) == []


class TestLayout:
    def test_every_row_is_exactly_board_width(self):
        rows = layout("VIERTEL NACH ZEHN", DE_PREFIX, 15, 3, "center")
        assert [len(row) for row in rows] == [15, 15, 15]

    def test_row_count_matches_board_height(self):
        assert len(layout("HALB ELF", DE_PREFIX, 22, 6, "center")) == 6

    def test_content_is_vertically_centered(self):
        rows = layout("HALB ELF", DE_PREFIX, 22, 6, "center")
        assert rows[0].strip() == ""
        assert rows[2].strip() == "ES IST HALB ELF"
        assert rows[5].strip() == ""

    def test_left_alignment_starts_at_the_first_tile(self):
        rows = layout("HALB ELF", DE_PREFIX, 15, 3, "left")
        assert rows[1] == "ES IST HALB ELF"

    def test_prefix_is_dropped_so_the_phrase_survives_whole(self):
        """With the prefix this needs three rows; without it, the phrase fits two."""
        rows = layout("FUENF NACH HALB ZWOELF", "ES IST", 12, 2, "left")
        assert [row.strip() for row in rows] == ["FUENF NACH", "HALB ZWOELF"]

    def test_leading_rows_are_dropped_before_the_hour_is_lost(self):
        rows = layout("FUENF NACH HALB ZWOELF", "", 6, 2, "left")
        assert len(rows) == 2
        assert rows[-1].strip() == "ZWOELF"

    @pytest.mark.parametrize("language", LANGUAGES)
    @pytest.mark.parametrize("style", ["standard", "regional"])
    @pytest.mark.parametrize("umlauts", ["expand", "strip"])
    @pytest.mark.parametrize("board", [FLAGSHIP, NOTE], ids=["flagship", "note"])
    def test_no_time_ever_loses_a_word(self, language, style, umlauts, board):
        """Every phrase must survive layout on both board shapes, prefix included.

        This is the test that decides whether a language is shippable: French
        runs to 37 characters ("IL EST QUATRE HEURES MOINS VINGT-CINQ") and
        still has to fit a Note's 15x3.
        """
        for hour in range(24):
            for step in ALL_STEPS:
                phrase = to_board_text(build_phrase(hour, step, language, style), umlauts)
                prefix = to_board_text(
                    prefix_for(language, spoken_hour(hour, step, language, style)), umlauts
                )
                rows = layout(phrase, prefix, board.width, board.height, "center")
                rendered = " ".join(" ".join(row.split()) for row in rows).split()
                assert rendered == f"{prefix} {phrase}".split(), (
                    f"{hour:02d}:{step:02d} {language}/{style}/{umlauts} lost words on {board.device_type}"
                )


class TestLetterspacing:
    """`_letterspace` is what fills a wide note array instead of leaving a
    short phrase as a small island of text in an otherwise blank board.
    """

    def test_stretches_a_line_to_exactly_the_target_width(self):
        stretched = _letterspace("HALB ELF", 20)
        assert len(stretched) == 20
        assert stretched.startswith("H")
        assert stretched.endswith("F")

    def test_preserves_character_order(self):
        stretched = _letterspace("HALB ELF", 30)
        assert [c for c in stretched if c != " "] == list("HALBELF")

    def test_a_single_character_is_returned_unchanged(self):
        assert _letterspace("H", 20) == "H"

    def test_a_line_already_at_the_target_width_is_unchanged(self):
        assert _letterspace("HALB ELF", 8) == "HALB ELF"

    def test_a_line_longer_than_the_target_width_is_unchanged(self):
        """`_align` truncates; `_letterspace` only ever stretches."""
        assert _letterspace("HALB ELF", 5) == "HALB ELF"

    def test_layout_does_not_letterspace_a_flagship_width_board(self):
        """Below `LETTERSPACE_ABOVE_WIDTH`, spacing is untouched -- this is
        the boundary that keeps the Flagship/Note layouts unchanged.
        """
        rows = layout("HALB ELF", DE_PREFIX, 22, 1, "left")
        assert rows[0].strip() == "ES IST HALB ELF"
        assert "  " not in rows[0].strip()

    def test_layout_letterspaces_a_board_wider_than_a_flagship(self):
        rows = layout("HALB ELF", DE_PREFIX, 60, 1, "center")
        assert "".join(rows[0].split()) == "ESISTHALBELF"
        # Filled well beyond the ~25% a Flagship-style layout would leave.
        assert len(rows[0].strip()) > 45


class TestMinuteDots:
    def test_dots_sit_right_after_the_phrase(self):
        """Dots are anchored to the row holding the phrase, not the board's
        literal last row -- on a Flagship the phrase is vertically centered
        onto row 2 of 6, and that is where the dots belong.
        """
        rows = layout("HALB ELF", DE_PREFIX, 22, 6, "center", dots=3, dot_marker="{69}")
        text_row = next(i for i, row in enumerate(rows) if row.strip())
        assert rows[text_row].endswith("{69}{69}{69}")
        # The bug this fixes: dots used to land in the board's literal last
        # row even when that row held no text at all.
        assert rows[-1].strip() == ""

    def test_dots_stay_close_to_the_phrase_on_a_wide_board(self):
        """The bug this guards against: on a 120-wide board the old
        bottom-right-corner placement put the dots ~100 tiles from a
        centered phrase, reading as a stray, unrelated tile.
        """
        rows = layout("HALB ELF", DE_PREFIX, 120, 3, "center", dots=3, dot_marker="{69}")
        text_row = next(i for i, row in enumerate(rows) if row.strip())
        line = rows[text_row]
        dot_index = line.index("{69}")
        text_end = len(line[:dot_index].rstrip())
        assert dot_index - text_end <= 5

    def test_no_dots_are_drawn_at_the_five_minute_mark(self):
        rows = layout("HALB ELF", DE_PREFIX, 22, 6, "center", dots=0, dot_marker="{69}")
        assert "{69}" not in "".join(rows)

    def test_dots_are_skipped_when_the_bottom_row_is_full(self):
        rows = layout("FUENF NACH HALB ZWOELF", "", 11, 2, "left", dots=4, dot_marker="{69}")
        assert rows[-1].strip() == "HALB ZWOELF"
        assert "{69}" not in "".join(rows)


class TestPlugin:
    def test_plugin_id_matches_the_manifest(self, make_plugin):
        assert make_plugin().plugin_id == "word_clock"

    def test_note_layout_is_three_rows_of_fifteen(self, make_plugin):
        result = make_plugin().get_data(NOTE)
        assert result.available
        assert [len(row) for row in result.formatted_lines] == [15, 15, 15]

    def test_flagship_layout_is_six_rows_of_twentytwo(self, make_plugin):
        result = make_plugin().get_data(FLAGSHIP)
        assert [len(row) for row in result.formatted_lines] == [22] * 6

    def test_phrase_matches_the_configured_clock(self, make_plugin, monkeypatch):
        plugin = make_plugin(language="de")
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, 10, 17, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        data = plugin.get_data(NOTE).data
        assert data["phrase"] == "ES IST VIERTEL NACH ZEHN"
        assert data["time"] == "10:17"
        assert data["step"] == "15"
        assert data["minute_offset"] == "2"

    @pytest.mark.parametrize(
        ("language", "expected"),
        [
            ("de", "ES IST VIERTEL VOR ELF"),
            ("en", "IT IS QUARTER TO ELEVEN"),
            ("es", "SON LAS ONCE MENOS CUARTO"),
            ("fr", "IL EST ONZE HEURES MOINS LE QUART"),
        ],
    )
    def test_language_switches_the_whole_phrase(self, make_plugin, monkeypatch, language, expected):
        plugin = make_plugin(language=language)
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, 10, 45, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        assert plugin.get_data(NOTE).data["phrase"] == expected
        assert plugin.get_data(NOTE).data["language"] == language

    def test_an_unknown_language_falls_back_to_the_default(self, make_plugin, monkeypatch):
        plugin = make_plugin(language="kl")
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, 10, 45, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        data = plugin.get_data(NOTE).data
        assert data["language"] == DEFAULT_LANGUAGE
        assert data["phrase"] == "IT IS QUARTER TO ELEVEN"

    def test_an_absent_language_uses_the_default(self, make_plugin, monkeypatch):
        plugin = make_plugin()
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, 10, 45, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        assert plugin.get_data(NOTE).data["language"] == DEFAULT_LANGUAGE

    def test_the_spanish_copula_reaches_the_board(self, make_plugin, monkeypatch):
        plugin = make_plugin(language="es")
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, 13, 0, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        data = plugin.get_data(NOTE).data
        assert data["prefix"] == "ES LA"
        assert data["phrase"] == "ES LA UNA EN PUNTO"

    def test_prefix_can_be_turned_off(self, make_plugin, monkeypatch):
        plugin = make_plugin(language="de", show_prefix=False)
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, 10, 30, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        data = plugin.get_data(NOTE).data
        assert data["prefix"] == ""
        assert data["phrase"] == "HALB ELF"

    def test_line_variables_mirror_the_board_rows(self, make_plugin, monkeypatch):
        plugin = make_plugin()
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, 10, 30, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        result = plugin.get_data(NOTE)
        assert result.data["line1"] == result.formatted_lines[0]
        assert result.data["line4"] == ""

    def test_line_variables_keep_the_full_board_width(self, make_plugin):
        """The engine pads *around* what it is given, so a short row indents twice."""
        data = make_plugin().get_data(NOTE).data
        assert [len(data[f"line{n}"]) for n in (1, 2, 3)] == [15, 15, 15]

    def test_line_variables_reach_every_row_on_a_tall_board(self, make_plugin, monkeypatch):
        """The bug this guards against: line1..line6 used to come from
        ``range(FALLBACK_HEIGHT)`` -- a hardcoded 6 -- regardless of the
        board's actual height. On a board taller than a Flagship the
        vertically-centered phrase lands well past row 6 (row 12 on a 120x24
        array), so every line variable came back blank and a page built from
        ``{{word_clock.lineN}}`` rendered an empty board even though
        ``formatted_lines`` (and so ``block``) was correct.
        """
        plugin = make_plugin()
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, 10, 30, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        board = BoardContext(device_type="note_array", rows=24, cols=120)
        result = plugin.get_data(board)
        assert len(result.formatted_lines) == 24
        for index, row in enumerate(result.formatted_lines, start=1):
            assert result.data[f"line{index}"] == row
        # The phrase is one line, vertically centered among 24 rows, so it
        # lands well past row 6 -- exactly what the hardcoded loop missed.
        content_rows = [n for n in range(1, 25) if result.data[f"line{n}"].strip()]
        assert content_rows and min(content_rows) > 6

    def test_block_joins_every_board_row(self, make_plugin):
        result = make_plugin().get_data(NOTE)
        assert result.data["block"] == "\n".join(result.formatted_lines)

    def test_minute_dots_reach_the_board_when_enabled(self, make_plugin, monkeypatch):
        plugin = make_plugin(show_minute_dots=True, dot_color="green")
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, 10, 33, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        result = plugin.get_data(NOTE)
        # Anchored right after the phrase itself (one blank spacer), not the
        # board's literal last row (which may just be blank vertical padding).
        text_row = next(row for row in reversed(result.formatted_lines) if row.strip())
        assert "{66}{66}{66}" in text_row
        dot_index = text_row.index("{66}")
        text_before_dots = text_row[:dot_index].rstrip()
        assert text_before_dots  # the dots have real phrase text before them
        assert text_row[len(text_before_dots) : dot_index] == " "
        assert result.data["minute_dots"] == "{66}{66}{66}"

    def test_minute_dots_stay_off_by_default(self, make_plugin, monkeypatch):
        plugin = make_plugin()
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, 10, 33, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        assert plugin.get_data(NOTE).data["minute_dots"] == ""

    def test_live_data_bypasses_the_cache(self, make_plugin, monkeypatch):
        """A clock that serves a cached phrase is wrong by definition."""
        plugin = make_plugin()
        times = iter(
            [
                datetime(2026, 8, 12, 10, 30, tzinfo=ZoneInfo("Europe/Berlin")),
                datetime(2026, 8, 12, 10, 35, tzinfo=ZoneInfo("Europe/Berlin")),
            ]
        )
        monkeypatch.setattr(plugin, "_now", lambda: next(times))
        first = plugin.get_data(NOTE).data["phrase"]
        second = plugin.get_data(NOTE).data["phrase"]
        assert first != second

    def test_missing_board_falls_back_to_flagship_geometry(self, make_plugin):
        result = make_plugin().fetch_data()
        assert [len(row) for row in result.formatted_lines] == [22] * 6

    def test_a_broken_clock_reports_an_error_instead_of_raising(self, make_plugin, monkeypatch):
        plugin = make_plugin()
        monkeypatch.setattr(plugin, "_now", _raise)
        result = plugin.fetch_data()
        assert result.available is False
        assert "no clock" in result.error

    def test_empty_timezone_falls_back_to_the_board_setting(self, make_plugin):
        plugin = make_plugin(timezone="")
        assert plugin.fetch_data().available is True


class TestTemplateEngineIntegration:
    """The variables have to survive FiestaBoard's own template renderer.

    `{{word_clock.phrase}}` on a plain line is truncated at the board edge —
    that is what these variables exist to avoid.
    """

    @staticmethod
    def _render_block(plugin, board, alignment="center"):
        from src.templates.engine import TemplateEngine

        template = ["{{word_clock.block}}"] + [""] * (board.height - 1)
        metadata = [{"alignment": alignment, "wrap": False} for _ in range(board.height)]
        rendered = TemplateEngine().render_lines(
            template,
            context={"word_clock": plugin.get_data(board).data},
            line_metadata=metadata,
            device_type=board.device_type,
        )
        return rendered.split("\n")

    def test_a_bare_phrase_is_what_gets_truncated(self, make_plugin, monkeypatch):
        """Establishes the bug the block variable fixes."""
        plugin = make_plugin(language="en")
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, 11, 35, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        from src.templates.engine import TemplateEngine

        rendered = TemplateEngine().render_lines(
            ["{{word_clock.phrase}}"] + [""] * 5,
            context={"word_clock": plugin.get_data(FLAGSHIP).data},
            line_metadata=[{"alignment": "center", "wrap": False} for _ in range(6)],
            device_type="flagship",
        )
        # "IT IS TWENTY FIVE TO TWELVE" is 27 tiles; the board is 22 wide.
        assert "TWENTY FIVE" in rendered
        assert "TWELVE" not in rendered

    @pytest.mark.parametrize("board", [FLAGSHIP, NOTE], ids=["flagship", "note"])
    def test_block_reproduces_the_plugin_layout_exactly(self, make_plugin, monkeypatch, board):
        plugin = make_plugin()
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, 11, 35, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        assert self._render_block(plugin, board) == plugin.get_data(board).formatted_lines

    @pytest.mark.parametrize("alignment", ["center", "left", "right"])
    def test_block_survives_any_page_alignment(self, make_plugin, monkeypatch, alignment):
        """Full-width rows pass through the engine's alignment untouched."""
        plugin = make_plugin()
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, 11, 35, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        assert self._render_block(plugin, FLAGSHIP, alignment) == plugin.get_data(FLAGSHIP).formatted_lines

    def test_line_variable_is_not_indented_twice(self, make_plugin, monkeypatch):
        plugin = make_plugin()
        monkeypatch.setattr(
            plugin, "_now", lambda: datetime(2026, 8, 12, 10, 30, tzinfo=ZoneInfo("Europe/Berlin"))
        )
        data = plugin.get_data(FLAGSHIP).data
        from src.templates.engine import TemplateEngine

        rendered = TemplateEngine().render_lines(
            ["{{word_clock.line3}}"] + [""] * 5,
            context={"word_clock": data},
            line_metadata=[{"alignment": "center", "wrap": False} for _ in range(6)],
            device_type="flagship",
        )
        assert rendered.split("\n")[0] == data["line3"]


class TestValidateConfig:
    def test_a_known_timezone_passes(self, make_plugin):
        assert make_plugin().validate_config({"timezone": "Europe/Berlin"}) == []

    def test_an_unknown_timezone_is_rejected(self, make_plugin):
        errors = make_plugin().validate_config({"timezone": "Mars/Olympus_Mons"})
        assert errors and "Invalid timezone" in errors[0]

    def test_a_non_string_timezone_is_rejected(self, make_plugin):
        assert make_plugin().validate_config({"timezone": 42}) != []

    def test_an_omitted_timezone_is_valid(self, make_plugin):
        assert make_plugin().validate_config({}) == []

    @pytest.mark.parametrize("blank", ["", "   ", None])
    def test_a_blank_timezone_is_valid(self, make_plugin, blank):
        """Empty means "follow the FiestaBoard timezone" — and it is the shipped default."""
        assert make_plugin().validate_config({"timezone": blank}) == []

    def test_the_shipped_default_passes_its_own_validation(self, make_plugin):
        import json
        import pathlib

        manifest = json.loads((pathlib.Path(__file__).resolve().parent.parent / "manifest.json").read_text())
        defaults = {
            name: spec["default"]
            for name, spec in manifest["settings_schema"]["properties"].items()
            if "default" in spec
        }
        assert make_plugin().validate_config(defaults) == []


def _raise():
    raise RuntimeError("no clock available")
