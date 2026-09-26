"""Word Clock plugin for FiestaBoard.

Renders the current time the way a QLOCKTWO-style word clock does — as a
spelled-out phrase in five-minute steps ("ES IST VIERTEL NACH ZEHN",
"IT IS QUARTER PAST TEN") — and lays it out for the board it is rendering
on: a Flagship (22x6), a Note (15x3), or a note array of any size up to
120x24 (a FiestaPanel is a note array sized to a TV). Every dimension is
read from ``self.board``; nothing on the layout path is hardcoded to a
particular device.

A real word clock lights letters inside a fixed matrix. A split-flap has no
"dim" state, so this plugin renders only the words that would be lit, which
is what the matrix visually reduces to anyway -- that reasoning holds at any
board size, so this still does not carry a fixed letter grid. What DOES
change with the board is density: a phrase sized for a Flagship's 132 tiles
would occupy under 1% of a 120x24 array, so on anything wider than a
Flagship the phrase is letterspaced to fill the row (see `_letterspace`)
rather than left as a small island of text in a mostly blank board.
"""

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.plugins.base import PluginBase, PluginResult

logger = logging.getLogger(__name__)

# Last resort only. An unset timezone inherits the FiestaBoard-wide setting;
# this applies when that is unset too, so it has to be somewhere neutral
# rather than wherever the plugin happened to be written.
DEFAULT_TIMEZONE = "UTC"

# Board geometry assumed when the plugin runs outside a board-scoped render
# (unit tests, the /plugins/{id}/data endpoint). Flagship is the wider of the
# two shapes, so a phrase laid out for it never silently loses words.
FALLBACK_WIDTH = 22
FALLBACK_HEIGHT = 6

# Platform maximum for the line1..lineN template variables: an 8-tall note
# array is the tallest board FiestaBoard supports (8 notes * 3 rows). This is
# a variable-count bound, unrelated to FALLBACK_HEIGHT above (which is what
# self.board defaults to when no board is bound at all) -- do not conflate
# the two. Rows past the current board's height are simply emitted blank.
MAX_LINE_VARIABLES = 24

# A board wider than a Flagship has enough spare tiles that a single
# word-clock line reads as a stray scrap of text near the middle of a mostly
# blank row (a 120-wide note array puts a 22-character phrase in 0.8% of the
# board). Above this width, lines are letterspaced to fill the row -- see
# `_letterspace`. At or below it (Flagship and Note, and every array no wider
# than a Flagship), spacing is left untouched so existing layouts don't shift.
LETTERSPACE_ABOVE_WIDTH = FALLBACK_WIDTH

# Characters the board can actually flap. Anything outside this set is dropped
# rather than sent as a wrong tile. Reference: src/board_chars.py in FiestaBoard.
BOARD_CHARSET = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !@#$()-+&=;:'\"%,./?°")

# Umlauts have no board tile. "expand" is the correct German transliteration
# (FÜNF -> FUENF); "strip" is the shorter, more telegraphic form (FUNF).
UMLAUT_EXPAND = {"Ä": "AE", "Ö": "OE", "Ü": "UE", "ß": "SS"}
UMLAUT_STRIP = {"Ä": "A", "Ö": "O", "Ü": "U", "ß": "SS"}

DOT_COLORS = {
    "red": "{63}",
    "orange": "{64}",
    "yellow": "{65}",
    "green": "{66}",
    "blue": "{67}",
    "violet": "{68}",
    "white": "{69}",
}

LANGUAGES = ("de", "en", "es", "fr")
# Must match the manifest's language default; a test pins the two together.
DEFAULT_LANGUAGE = "en"

DE_PREFIX = "ES IST"
EN_PREFIX = "IT IS"
FR_PREFIX = "IL EST"
# Spanish agrees the copula with the hour: "ES LA UNA", "SON LAS DOS".
ES_PREFIX_SINGULAR = "ES LA"
ES_PREFIX_PLURAL = "SON LAS"

# Hour 1 is "EIN" only when it is immediately followed by UHR ("ES IST EIN UHR"),
# and "EINS" everywhere else ("ES IST FÜNF NACH EINS").
DE_HOURS = {
    1: "EINS",
    2: "ZWEI",
    3: "DREI",
    4: "VIER",
    5: "FÜNF",
    6: "SECHS",
    7: "SIEBEN",
    8: "ACHT",
    9: "NEUN",
    10: "ZEHN",
    11: "ELF",
    12: "ZWÖLF",
}

EN_HOURS = {
    1: "ONE",
    2: "TWO",
    3: "THREE",
    4: "FOUR",
    5: "FIVE",
    6: "SIX",
    7: "SEVEN",
    8: "EIGHT",
    9: "NINE",
    10: "TEN",
    11: "ELEVEN",
    12: "TWELVE",
}

ES_HOURS = {
    1: "UNA",
    2: "DOS",
    3: "TRES",
    4: "CUATRO",
    5: "CINCO",
    6: "SEIS",
    7: "SIETE",
    8: "OCHO",
    9: "NUEVE",
    10: "DIEZ",
    11: "ONCE",
    12: "DOCE",
}

FR_HOURS = {
    1: "UNE",
    2: "DEUX",
    3: "TROIS",
    4: "QUATRE",
    5: "CINQ",
    6: "SIX",
    7: "SEPT",
    8: "HUIT",
    9: "NEUF",
    10: "DIX",
    11: "ONZE",
    12: "DOUZE",
}

HOURS = {"de": DE_HOURS, "en": EN_HOURS, "es": ES_HOURS, "fr": FR_HOURS}

# Phrase templates keyed by the five-minute step. "{h}" is the current hour,
# "{h1}" the next one — German counts toward the coming hour from :25 onward.
DE_STANDARD = {
    0: "{h} UHR",
    5: "FÜNF NACH {h}",
    10: "ZEHN NACH {h}",
    15: "VIERTEL NACH {h}",
    20: "ZWANZIG NACH {h}",
    25: "FÜNF VOR HALB {h1}",
    30: "HALB {h1}",
    35: "FÜNF NACH HALB {h1}",
    40: "ZWANZIG VOR {h1}",
    45: "VIERTEL VOR {h1}",
    50: "ZEHN VOR {h1}",
    55: "FÜNF VOR {h1}",
}

# Ostdeutsch/fränkisch/sächsisch: quarters are counted into the coming hour
# ("VIERTEL ZEHN" = 9:15), and :20/:40 hinge on HALB instead of the full hour.
DE_REGIONAL = {
    **DE_STANDARD,
    15: "VIERTEL {h1}",
    20: "ZEHN VOR HALB {h1}",
    40: "ZEHN NACH HALB {h1}",
    45: "DREIVIERTEL {h1}",
}

EN_STANDARD = {
    0: "{h} O'CLOCK",
    5: "FIVE PAST {h}",
    10: "TEN PAST {h}",
    15: "QUARTER PAST {h}",
    20: "TWENTY PAST {h}",
    25: "TWENTY FIVE PAST {h}",
    30: "HALF PAST {h}",
    35: "TWENTY FIVE TO {h1}",
    40: "TWENTY TO {h1}",
    45: "QUARTER TO {h1}",
    50: "TEN TO {h1}",
    55: "FIVE TO {h1}",
}

# Spanish and French name the hour first and hang the minutes off it, so the
# hour placeholder leads. Both switch to counting down from the coming hour
# after the half — Spanish at :35, French likewise.
ES_STANDARD = {
    0: "{h} EN PUNTO",
    5: "{h} Y CINCO",
    10: "{h} Y DIEZ",
    15: "{h} Y CUARTO",
    20: "{h} Y VEINTE",
    25: "{h} Y VEINTICINCO",
    30: "{h} Y MEDIA",
    35: "{h1} MENOS VEINTICINCO",
    40: "{h1} MENOS VEINTE",
    45: "{h1} MENOS CUARTO",
    50: "{h1} MENOS DIEZ",
    55: "{h1} MENOS CINCO",
}

FR_STANDARD = {
    0: "{h}",
    5: "{h} CINQ",
    10: "{h} DIX",
    15: "{h} ET QUART",
    20: "{h} VINGT",
    25: "{h} VINGT-CINQ",
    30: "{h} ET DEMIE",
    35: "{h1} MOINS VINGT-CINQ",
    40: "{h1} MOINS VINGT",
    45: "{h1} MOINS LE QUART",
    50: "{h1} MOINS DIX",
    55: "{h1} MOINS CINQ",
}


def round_to_step(hour: int, minute: int, rounding: str) -> tuple[int, int, int]:
    """Reduce a wall-clock time to a five-minute word-clock step.

    Returns ``(hour, step, leftover)`` where *step* is a multiple of 5 and
    *leftover* is the minutes the words cannot express, which the corner dots
    show. Rounding up past :57 carries into the next hour. Only floor rounding
    has a leftover — with "nearest" the phrase already absorbs the difference.
    """
    if rounding == "nearest":
        step, leftover = ((minute + 2) // 5) * 5, 0
    else:
        step, leftover = (minute // 5) * 5, minute % 5
    if step >= 60:
        step = 0
        hour = (hour + 1) % 24
    return hour, step, leftover


def _template_for(step: int, language: str, german_style: str) -> str:
    """Return the raw phrase template for a five-minute step."""
    if language == "en":
        return EN_STANDARD[step]
    if language == "es":
        return ES_STANDARD[step]
    if language == "fr":
        return FR_STANDARD[step]
    return (DE_REGIONAL if german_style == "regional" else DE_STANDARD)[step]


def hour_phrase(hour: int, language: str) -> str:
    """Spell out the hour as the language names it inside a phrase.

    German, English and Spanish name the bare numeral. French carries the unit
    with it — "DIX HEURES", "UNE HEURE" — and replaces the twelves outright:
    a French clock says MIDI and MINUIT, never "douze heures", which is why
    this takes the 24-hour value rather than a 1-12 one.
    """
    h12 = hour % 12 or 12
    if language != "fr":
        return HOURS[language][h12]
    if hour == 12:
        return "MIDI"
    if hour == 0:
        return "MINUIT"
    return f"{FR_HOURS[h12]} {'HEURE' if h12 == 1 else 'HEURES'}"


def prefix_for(language: str, spoken_hour_12: int) -> str:
    """Return the "it is" opener, which Spanish agrees with the hour.

    *spoken_hour_12* is the hour the phrase actually names — at 12:40 Spanish
    reads "ES LA UNA MENOS VEINTE", singular, because the named hour is one.
    """
    if language == "en":
        return EN_PREFIX
    if language == "fr":
        return FR_PREFIX
    if language == "es":
        return ES_PREFIX_SINGULAR if spoken_hour_12 == 1 else ES_PREFIX_PLURAL
    return DE_PREFIX


def spoken_hour(hour: int, step: int, language: str, german_style: str) -> int:
    """Return the 1-12 hour the phrase actually names.

    From :25 onward German counts toward the coming hour ("HALB ZEHN" is 9:30),
    and English switches to "TO" — in both cases the spoken hour is the next one.
    """
    h12 = hour % 12 or 12
    if "{h1}" in _template_for(step, language, german_style):
        return h12 % 12 + 1
    return h12


def build_phrase(hour: int, step: int, language: str, german_style: str) -> str:
    """Spell out ``hour``/``step`` as a word-clock phrase, without the prefix.

    The result still contains umlauts; :func:`to_board_text` converts them.
    """
    template = _template_for(step, language, german_style)
    this_hour = hour_phrase(hour, language)
    next_hour = hour_phrase((hour + 1) % 24, language)

    if language == "de" and hour % 12 == 1 and template.startswith("{h} UHR"):
        # "ES IST EIN UHR", but "ES IST FÜNF NACH EINS".
        this_hour = "EIN"

    return template.format(h=this_hour, h1=next_hour)


def to_board_text(text: str, umlauts: str) -> str:
    """Uppercase *text* and reduce it to characters the board can display."""
    table = UMLAUT_STRIP if umlauts == "strip" else UMLAUT_EXPAND
    text = text.upper()
    for source, replacement in table.items():
        text = text.replace(source, replacement)
    return "".join(char for char in text if char in BOARD_CHARSET)


def wrap_words(text: str, width: int) -> list[str]:
    """Greedily wrap *text* to *width*, never splitting a word.

    A word longer than the board is emitted on its own line rather than
    truncated — the caller decides what to do with an overlong layout.
    """
    lines: list[str] = []
    current = ""
    for word in text.split():
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _letterspace(line: str, width: int) -> str:
    """Stretch *line* to exactly *width* by widening the gaps between tiles.

    Only called for boards wider than a Flagship (see
    ``LETTERSPACE_ABOVE_WIDTH``). A word clock has, at most, a few dozen
    characters to show; centering that phrase in a 120-tile note array with
    plain edge padding leaves under 1% of the board lit. Distributing the
    slack between every character instead -- "H A L B   E L F" rather than
    "HALB ELF" -- turns the same words into a display that actually uses the
    row, the way large-format signage letterspaces short headlines.

    Distributes as evenly as possible across the internal gaps (never before
    the first or after the last character, so centering/left-alignment still
    controls the outer margin). A line with fewer than two characters, or
    already at *width*, is returned unchanged -- there is no gap to widen.
    """
    if len(line) < 2 or len(line) >= width:
        return line
    gaps = len(line) - 1
    extra = width - len(line)
    base, remainder = divmod(extra, gaps)
    out: list[str] = [line[0]]
    for index, char in enumerate(line[1:], start=1):
        out.append(" " * (base + (1 if index <= remainder else 0)))
        out.append(char)
    return "".join(out)


def _align(line: str, width: int, alignment: str, reserve: int = 0) -> list[str]:
    """Return *line* as a list of exactly *width* single-tile tokens.

    *reserve* holds back that many trailing tiles (left blank) for the
    minute dots on the row that will carry them -- letterspacing otherwise
    fills a wide row edge-to-edge with no gap left for them. Ignored (and
    left as ordinary padding) when it would truncate the line.
    """
    usable = width - reserve if reserve and reserve < width and len(line) <= width - reserve else width
    if usable > LETTERSPACE_ABOVE_WIDTH and len(line) < usable:
        line = _letterspace(line, usable)
    tiles = list(line[:usable])
    padding = usable - len(tiles)
    if alignment == "center":
        left = padding // 2
        result = [" "] * left + tiles + [" "] * (padding - left)
    else:
        result = tiles + [" "] * padding
    return result + [" "] * (width - usable)


def _place_dots(rows: list[list[str]], dots: int, marker: str, content_row: int | None) -> None:
    """Write *dots* markers right after the phrase, in place.

    Anchored to *content_row* -- the row holding the last line of the laid-out
    phrase -- rather than the physical bottom-right corner of the board. A
    QLOCKTWO's corner dots sit at a fixed matrix corner because the matrix
    itself is fixed; a split-flap board reflows to every board width, and on
    anything wider than a Flagship the literal corner can be dozens of tiles
    from a centered phrase, reading as a stray, unrelated tile rather than a
    minutes indicator. Skipped when there is no content row, or when the tiles
    right after the phrase (plus one blank spacer) don't have room -- the time
    itself always outranks the dots.
    """
    if dots <= 0 or not rows or content_row is None:
        return
    row = rows[content_row]
    width = len(row)
    last_used = next((i for i in range(width - 1, -1, -1) if row[i] != " "), -1)
    start = last_used + 2  # one blank tile of breathing room, then the dots
    if start + dots > width:
        return
    row[start : start + dots] = [marker] * dots


def layout(
    phrase: str,
    prefix: str,
    width: int,
    height: int,
    alignment: str,
    dots: int = 0,
    dot_marker: str = "",
) -> list[str]:
    """Lay the phrase out as *height* board rows of *width* tiles.

    The prefix ("ES IST"/"IT IS") is the first thing sacrificed when the phrase
    does not fit; if it still overflows, the leading rows are dropped so the
    hour survives.
    """
    text = f"{prefix} {phrase}".strip() if prefix else phrase
    lines = wrap_words(text, width)
    if len(lines) > height and prefix:
        lines = wrap_words(phrase, width)
    if len(lines) > height:
        lines = lines[-height:]

    top = (height - len(lines)) // 2
    content_row = top + len(lines) - 1 if lines else None
    # Letterspacing (see `_align`) fills a wide row edge-to-edge, leaving no
    # gap for the dots on the row that will carry them -- reserve one first.
    # Narrow boards never letterspace, so this never shrinks them; it is
    # itself skipped by `_align` if the line wouldn't fit in what's left.
    dot_reserve = dots + 1 if dot_marker and dots > 0 and width > LETTERSPACE_ABOVE_WIDTH else 0

    rows = [[" "] * width for _ in range(top)]
    for offset, line in enumerate(lines):
        row_index = top + offset
        reserve = dot_reserve if row_index == content_row else 0
        rows.append(_align(line, width, alignment, reserve=reserve))
    rows += [[" "] * width for _ in range(height - len(rows))]

    if dot_marker:
        _place_dots(rows, dots, dot_marker, content_row)
    return ["".join(row) for row in rows]


class WordClockPlugin(PluginBase):
    """Word clock in four languages, sized to the board it renders on."""

    @property
    def plugin_id(self) -> str:
        return "word_clock"

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """Reject a timezone the runtime cannot resolve; everything else is enum-bounded.

        An empty timezone is valid and means "use the FiestaBoard-wide setting"
        — it is the shipped default, so rejecting it would make a plugin that
        has never been touched fail its own validation.
        """
        errors: list[str] = []
        timezone = config.get("timezone", "")
        if timezone is None or (isinstance(timezone, str) and not timezone.strip()):
            return errors
        if not isinstance(timezone, str):
            errors.append(f"Invalid timezone: {timezone!r}")
            return errors
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError, AttributeError, KeyError):
            errors.append(f"Invalid timezone: {timezone}")
        return errors

    def _now(self) -> datetime:
        """Current time in the configured timezone, falling back to the board's."""
        timezone = self.config.get("timezone")
        if not timezone:
            from src.config import Config

            timezone = Config.GENERAL_TIMEZONE or DEFAULT_TIMEZONE
        return datetime.now(ZoneInfo(timezone))

    def fetch_data(self) -> PluginResult:
        """Build the phrase for the current time and lay it out for this board."""
        try:
            now = self._now()
            language = self.config.get("language", DEFAULT_LANGUAGE)
            if language not in LANGUAGES:
                language = DEFAULT_LANGUAGE
            umlauts = self.config.get("umlauts", "expand")
            german_style = self.config.get("german_style", "standard")
            alignment = self.config.get("alignment", "center")

            hour, step, leftover = round_to_step(now.hour, now.minute, self.config.get("rounding", "down"))
            named_hour = spoken_hour(hour, step, language, german_style)
            phrase = to_board_text(build_phrase(hour, step, language, german_style), umlauts)
            prefix = ""
            if self.config.get("show_prefix", True):
                prefix = to_board_text(prefix_for(language, named_hour), umlauts)

            board = self.board
            width = board.width if board else FALLBACK_WIDTH
            height = board.height if board else FALLBACK_HEIGHT

            dot_marker = ""
            if self.config.get("show_minute_dots", False):
                dot_marker = DOT_COLORS.get(self.config.get("dot_color", "white"), DOT_COLORS["white"])

            lines = layout(phrase, prefix, width, height, alignment, leftover, dot_marker)

            full = f"{prefix} {phrase}".strip()
            data: dict[str, Any] = {
                "phrase": full,
                "phrase_short": phrase,
                "prefix": prefix,
                "hour_word": to_board_text(HOURS[language][named_hour], umlauts),
                "time": now.strftime("%H:%M"),
                "step": str(step),
                "minute_offset": str(leftover),
                "minute_dots": dot_marker * leftover,
                "language": language,
                "formatted": full,
            }
            # One variable that fills the whole board: the laid-out rows joined
            # by newlines. FiestaBoard's template engine splits a value on "\n"
            # across board rows, so `{{word_clock.block}}` on the first template
            # line reproduces the centered layout without needing |wrap.
            data["block"] = "\n".join(lines)
            # line1..line24 mirror the board rows individually, up to the
            # platform's tallest board (an 8-tall note array). They keep their
            # full board width on purpose: the engine's alignment pads *around*
            # whatever it is given, so an rstripped row would be indented twice
            # on a centered line. A full-width row passes through untouched.
            # Rows past the current board's height are simply blank -- this
            # used to loop range(FALLBACK_HEIGHT) (always 6), so a 12- or
            # 24-row board left line7..line24 undeclared *and* left
            # line1..line6 blank whenever the phrase landed past row 6.
            for index in range(MAX_LINE_VARIABLES):
                data[f"line{index + 1}"] = lines[index] if index < len(lines) else ""

            return PluginResult(available=True, data=data, formatted_lines=lines)

        except Exception as error:  # noqa: BLE001 — a broken clock must not break the render loop
            logger.exception("Error building word clock")
            return PluginResult(available=False, error=str(error))


# Export the plugin class
Plugin = WordClockPlugin
