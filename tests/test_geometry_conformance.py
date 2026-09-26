"""Board-geometry conformance for the Word Clock plugin.

Runs the shared FiestaBoard conformance suite (``src/plugins/
geometry_conformance.py`` in core -- importable here because core is on
``PYTHONPATH`` in plugin CI) across every board shape the platform supports,
including note arrays up to 120x24. It renders the plugin many times and
never touches the network; the clock is frozen via ``_now`` since this
plugin has no other I/O to stub.

``strict_growth`` is intentionally omitted: a word clock has one fixed-size
phrase to show, not a list or a feed, so a taller board is not expected to
produce more content the way it would for a plugin that renders repeated
items. Growth here is genuinely meaningless.
"""

import json
import pathlib
from datetime import datetime
from zoneinfo import ZoneInfo

from plugins.word_clock import WordClockPlugin
from src.plugins.geometry_conformance import assert_board_conformance

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((ROOT / "manifest.json").read_text())


def make_plugin() -> WordClockPlugin:
    """Fresh, ready-to-render plugin. No network to stub -- only the clock."""
    plugin = WordClockPlugin(MANIFEST)
    plugin.config = {"timezone": "Europe/Berlin"}
    plugin._now = lambda: datetime(2026, 8, 12, 10, 17, tzinfo=ZoneInfo("Europe/Berlin"))
    return plugin


def test_renders_on_every_board_shape():
    assert_board_conformance(
        make_plugin,
        manifest=MANIFEST,
        require_note_array_preview=True,
    )
