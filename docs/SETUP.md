# Word Clock Setup Guide

Show the time spelled out in words on your Vestaboard, in German, English, Spanish or French.

## Overview

**What it does.** Instead of `10:17`, the board reads `IT IS QUARTER PAST TEN`. The phrase advances in five-minute steps, the way a QLOCKTWO word clock does. All four languages fit a Note (15×3) as well as a Flagship (22×6) — the plugin re-wraps the phrase for whichever board it is sent to.

**Prerequisites.** None. The plugin does not call any external service, so there is no API key to register and no account to create.

## Quick Setup

1. **Install** — Integrations → Install from repository:

   ```
   https://github.com/Fiestaboard/fiestaboard-plugin--word-clock
   ```

2. **Enable and configure** — open the Word Clock card on the Integrations page, switch **Enabled** on, and set **Language** and **Timezone**. Everything else has a sensible default; see the reference below.

3. **Add it to a page** — create a page of type *Plugin* and pick **Word Clock**. The plugin fills the board itself, so no template is needed.

4. **View** — the board updates on your page's normal schedule. A refresh every one to five minutes keeps it in step with the five-minute phrase.

## Template Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{{word_clock.phrase}}` | Full spelled-out time including the prefix | `IT IS QUARTER PAST TEN` |
| `{{word_clock.phrase_short}}` | Same, without the opener | `QUARTER PAST TEN` |
| `{{word_clock.prefix}}` | The opener, which Spanish agrees with the hour | `IT IS` |
| `{{word_clock.block}}` | The whole laid-out board, rows separated by newlines | see below |
| `{{word_clock.line1}}` … `{{word_clock.line24}}` | The same rows individually, padded to the board width. `line24` is the platform maximum (an 8-tall note array); rows past the board's actual height are empty. | `IT IS QUARTER PAST TEN` |
| `{{word_clock.hour_word}}` | The hour the phrase names | `TEN` |
| `{{word_clock.time}}` | Exact time behind the phrase | `10:17` |
| `{{word_clock.step}}` | Five-minute step (0–55) | `15` |
| `{{word_clock.minute_offset}}` | Minutes past that step (0–4) | `2` |
| `{{word_clock.minute_dots}}` | Color tiles for the offset | `{69}{69}` |
| `{{word_clock.language}}` | Active language code | `en` |

### Using them in a template page

If you want the clock inside a page of your own rather than as a single-plugin page, put `block` on the **first** template line and leave the rest empty:

```
{{word_clock.block}}
```

FiestaBoard splits a value containing newlines across the board rows, so this gives you the same centered layout as the single-plugin page.

**Do not use `{{word_clock.phrase}}` on a plain line.** It is a single string and gets cut off at the board edge — `IT IS TWENTY FIVE PAST TWELVE` loses `TWELVE`. Switch the line to **wrap** in the page editor if you want the raw phrase to flow across the lines below it; note that the block then starts at the top of the board instead of being centered.

## Configuration Reference

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | boolean | `false` | Enable the plugin |
| `language` | `de` \| `en` \| `es` \| `fr` | `en` | Language the time is spelled out in |
| `timezone` | string | *(empty)* | IANA timezone name. Empty follows the FiestaBoard-wide timezone |
| `show_prefix` | boolean | `true` | Show `ES IST` / `IT IS` / `SON LAS` / `IL EST` |
| `german_style` | `standard` \| `regional` | `standard` | See *German dialects* below. German only |
| `umlauts` | `expand` \| `strip` | `expand` | `FUENF`/`ZWOELF` vs. `FUNF`/`ZWOLF`. German only |
| `rounding` | `down` \| `nearest` | `down` | `down` matches a physical word clock |
| `alignment` | `center` \| `left` | `center` | Horizontal alignment of each row |
| `show_minute_dots` | boolean | `false` | Corner dots for the minutes the words cannot express |
| `dot_color` | `white`, `red`, `orange`, `yellow`, `green`, `blue`, `violet` | `white` | Tile color for the minute dots |

### German dialects

| Time | `standard` | `regional` |
|------|-----------|-----------|
| 10:15 | `VIERTEL NACH ZEHN` | `VIERTEL ELF` |
| 10:20 | `ZWANZIG NACH ZEHN` | `ZEHN VOR HALB ELF` |
| 10:40 | `ZWANZIG VOR ELF` | `ZEHN NACH HALB ELF` |
| 10:45 | `VIERTEL VOR ELF` | `DREIVIERTEL ELF` |

`regional` is the counting used in East Germany, Franconia and Saxony, where the quarters belong to the coming hour.

### Spanish and French

| Time | `es` | `fr` |
|------|------|------|
| 13:00 | `ES LA UNA EN PUNTO` | `IL EST UNE HEURE` |
| 10:30 | `SON LAS DIEZ Y MEDIA` | `IL EST DIX HEURES ET DEMIE` |
| 10:45 | `SON LAS ONCE MENOS CUARTO` | `IL EST ONZE HEURES MOINS LE QUART` |
| 12:00 | `SON LAS DOCE EN PUNTO` | `IL EST MIDI` |
| 00:00 | `SON LAS DOCE EN PUNTO` | `IL EST MINUIT` |

Spanish agrees the opener with the hour the phrase *names*: 12:40 reads `ES LA UNA MENOS VEINTE`, singular, because the named hour is one. French carries the unit with the hour and never says "douze heures" — noon is `MIDI`, midnight is `MINUIT`.

### Minute dots

A QLOCKTWO carries four corner dots for the minutes between two five-minute steps. With **Show minute dots** on, the plugin puts up to four colored tiles in the bottom right — one per minute past the step. At 10:33 with `down` rounding the board reads `IT IS HALF PAST TEN` plus three dots — 10:33 floors to the half-hour step, and the three minutes past it become the dots.

The dots are skipped when the bottom row has no free tiles; the time itself always wins.

## Environment Variables

None. The plugin reads nothing from the environment — no API key, no service URL.

## Troubleshooting

**The board shows a time a few minutes behind.** That is the point — with `down` rounding the phrase changes on the full five minutes, like a physical word clock. Switch **Rounding** to `Nearest` if you prefer it to round to the closest step.

**The time is wrong by whole hours.** Check **Timezone**. If it is empty the plugin uses the FiestaBoard-wide timezone (Settings → General), which may differ from where the board hangs.

**The opener (`IT IS`, `ES IST`, …) is missing.** On a narrow board it is dropped automatically when the phrase would otherwise not fit. This only happens on boards smaller than a Note; on a Note and Flagship every phrase fits with the prefix.

**Umlauts look wrong.** The Vestaboard character set has no `Ä`, `Ö` or `Ü`. **Expand** writes `FUENF` and `ZWOELF`, **Strip** writes `FUNF` and `ZWOLF`. Pick whichever you find less jarring.

**Minute dots do not appear.** They only show when the minute is not an exact multiple of five, and they are skipped when the bottom board row is already full of letters.

**The phrase is cut off at the board edge.** You are using `{{word_clock.phrase}}` on a plain line. Use `{{word_clock.block}}` on the first line instead — see *Using them in a template page* above.
