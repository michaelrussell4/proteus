"""Proteus Scriptorium Programmatic Cover Art Engine (`covers.py`).

Generates high-resolution (1200×1920, 1:1.6 Kindle Paperwhite / KDP aspect ratio)
book covers with a standardized fine-press visual identity:
- Classical tracked typography (`Constantia` & `Palatino Linotype` with custom letter-spacing)
- Standardized Series Header Bands and Edition Pills (with Clean editions carrying zero title clutter)
- Large, intricate 2× supersampled centerpiece illustrations (`liahona`, `codex`, `tree`, `collation`, `seal`, `arch`, `rose`)
"""

from __future__ import annotations

import io
import itertools
import math
import re
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from proteus.core.models import Work


@dataclass
class CoverPalette:
    bg_top: tuple[int, int, int]
    bg_bottom: tuple[int, int, int]
    glow_color: tuple[int, int, int]
    card_bg: tuple[int, int, int] | None
    primary_accent: tuple[int, int, int]
    secondary_accent: tuple[int, int, int]
    title_color: tuple[int, int, int]
    subtitle_color: tuple[int, int, int]
    pill_bg: tuple[int, int, int]
    pill_text: tuple[int, int, int]
    emblem_style: str  # "liahona", "codex", "tree", "collation", "seal", "arch", "rose"
    series_banner: str


PALETTES: dict[str, CoverPalette] = {
    "clean": CoverPalette(
        bg_top=(246, 241, 230),
        bg_bottom=(234, 226, 209),
        glow_color=(253, 250, 244),
        card_bg=(250, 246, 238),
        primary_accent=(136, 38, 24),
        secondary_accent=(168, 134, 72),
        title_color=(26, 22, 18),
        subtitle_color=(82, 74, 64),
        pill_bg=(136, 38, 24),
        pill_text=(250, 246, 238),
        emblem_style="codex",
        series_banner="STANDARD WORKS • CLEAN EDITION",
    ),
    "canon": CoverPalette(
        bg_top=(15, 29, 48),
        bg_bottom=(8, 16, 28),
        glow_color=(28, 52, 84),
        card_bg=None,
        primary_accent=(218, 179, 84),
        secondary_accent=(148, 118, 54),
        title_color=(248, 244, 234),
        subtitle_color=(208, 198, 178),
        pill_bg=(28, 48, 76),
        pill_text=(232, 198, 108),
        emblem_style="liahona",
        series_banner="STANDARD WORKS • CANONICAL SERIES",
    ),
    "narrative": CoverPalette(
        bg_top=(18, 38, 46),
        bg_bottom=(10, 22, 28),
        glow_color=(32, 66, 78),
        card_bg=None,
        primary_accent=(222, 174, 96),
        secondary_accent=(142, 112, 66),
        title_color=(246, 242, 234),
        subtitle_color=(204, 198, 184),
        pill_bg=(28, 56, 68),
        pill_text=(236, 194, 120),
        emblem_style="tree",
        series_banner="READER’S SERIES • NARRATIVE & JOURNAL EDITIONS",
    ),
    "enriched": CoverPalette(
        bg_top=(30, 18, 44),
        bg_bottom=(16, 9, 25),
        glow_color=(56, 34, 80),
        card_bg=None,
        primary_accent=(228, 188, 86),
        secondary_accent=(164, 126, 58),
        title_color=(250, 246, 236),
        subtitle_color=(216, 206, 190),
        pill_bg=(52, 32, 74),
        pill_text=(240, 206, 112),
        emblem_style="liahona",
        series_banner="STUDY SERIES • RELATIONAL & LEXICAL EDITIONS",
    ),
    "variants": CoverPalette(
        bg_top=(42, 26, 18),
        bg_bottom=(22, 13, 9),
        glow_color=(74, 46, 32),
        card_bg=None,
        primary_accent=(224, 186, 104),
        secondary_accent=(158, 126, 68),
        title_color=(248, 243, 232),
        subtitle_color=(216, 202, 182),
        pill_bg=(68, 42, 28),
        pill_text=(238, 204, 128),
        emblem_style="collation",
        series_banner="STUDY SERIES • CRITICAL COLLATION & POETICS",
    ),
    "apocrypha": CoverPalette(
        bg_top=(54, 15, 24),
        bg_bottom=(28, 7, 12),
        glow_color=(88, 26, 40),
        card_bg=None,
        primary_accent=(224, 182, 96),
        secondary_accent=(158, 120, 58),
        title_color=(250, 244, 232),
        subtitle_color=(222, 204, 184),
        pill_bg=(82, 24, 36),
        pill_text=(240, 202, 120),
        emblem_style="seal",
        series_banner="ANCIENT TEXTS • APOCRYPHA & PSEUDEPIGRAPHA",
    ),
    "literature": CoverPalette(
        bg_top=(15, 42, 32),
        bg_bottom=(8, 22, 17),
        glow_color=(28, 72, 54),
        card_bg=None,
        primary_accent=(218, 182, 88),
        secondary_accent=(146, 118, 58),
        title_color=(247, 244, 235),
        subtitle_color=(206, 214, 198),
        pill_bg=(26, 64, 48),
        pill_text=(236, 202, 114),
        emblem_style="arch",
        series_banner="HISTORICAL LIBRARY • RESTORATION CLASSICS",
    ),
    "guides": CoverPalette(
        bg_top=(22, 34, 52),
        bg_bottom=(12, 19, 30),
        glow_color=(38, 58, 88),
        card_bg=None,
        primary_accent=(220, 184, 96),
        secondary_accent=(148, 122, 64),
        title_color=(248, 244, 236),
        subtitle_color=(208, 202, 188),
        pill_bg=(36, 54, 82),
        pill_text=(238, 204, 118),
        emblem_style="rose",
        series_banner="PHILOLOGY SERIES • SCRIPTURE READING GUIDES",
    ),
}


# Explicit, standardized cover specification for each edition ID:
# (palette_key, main_title, edition_pill, clean_subtitle, emblem_override)
COVER_SPECS: dict[str, tuple[str, str, str, str, str | None]] = {
    # Clean Series (no appendations on the main title!)
    "lds-standard-works-minimalist": (
        "clean",
        "The Standard Works",
        "",
        "Old Testament • New Testament • Book of Mormon • Doctrine and Covenants • Pearl of Great Price",
        "codex",
    ),
    "old-testament-minimalist": (
        "clean",
        "The Old Testament",
        "",
        "The King James Version",
        "codex",
    ),
    "new-testament-minimalist": (
        "clean",
        "The New Testament",
        "",
        "The King James Version",
        "codex",
    ),
    "book-of-mormon-minimalist": (
        "clean",
        "The Book of Mormon",
        "",
        "Another Testament of Jesus Christ",
        "codex",
    ),
    "doctrine-and-covenants-minimalist": (
        "clean",
        "The Doctrine and Covenants",
        "",
        "Of The Church of Jesus Christ of Latter-day Saints",
        "codex",
    ),
    "pearl-of-great-price-minimalist": (
        "clean",
        "The Pearl of Great Price",
        "",
        "A Selection from the Revelations, Translations, and Narrations of Joseph Smith",
        "codex",
    ),
    # Canonical Series
    "book-of-mormon": (
        "canon",
        "The Book of Mormon",
        "2013 STANDARD EDITION",
        "Another Testament of Jesus Christ",
        "liahona",
    ),
    "book-of-mormon-1830": (
        "canon",
        "The Book of Mormon",
        "1830 PALMYRA EDITION",
        "An Account Written by the Hand of Mormon upon Plates Taken from the Plates of Nephi",
        "liahona",
    ),
    "doctrine-and-covenants": (
        "canon",
        "The Doctrine and Covenants",
        "2013 STANDARD EDITION",
        "Containing Revelations Given to Joseph Smith, the Prophet",
        "liahona",
    ),
    "pearl-of-great-price": (
        "canon",
        "The Pearl of Great Price",
        "2013 STANDARD EDITION",
        "Revelations, Translations, and Narrations of Joseph Smith",
        "liahona",
    ),
    # Reader's & Narrative Series
    "book-of-mormon-narrative": (
        "narrative",
        "The Book of Mormon",
        "CONTINUOUS NARRATIVE EDITION",
        "Flowing Literary Paragraphs with Interactive Verse-Range Locators",
        "tree",
    ),
    "book-of-mormon-1830-narrative": (
        "narrative",
        "The Book of Mormon",
        "1830 NARRATIVE EDITION",
        "The Original Palmyra Text in Flowing Literary Paragraphs",
        "tree",
    ),
    "new-testament-narrative": (
        "narrative",
        "The New Testament",
        "CONTINUOUS NARRATIVE EDITION",
        "The King James Version in Flowing Literary Paragraphs",
        "tree",
    ),
    "book-of-mormon-study-notebook": (
        "narrative",
        "The Book of Mormon",
        "WIDE-MARGIN STUDY NOTEBOOK",
        "Spacious Annotation Layout with Chapter Reflection Grids",
        "codex",
    ),
    # Enriched & Study Series
    "book-of-mormon-master-study": (
        "enriched",
        "The Book of Mormon",
        "MASTER STUDY EDITION",
        "With BYU Onomasticon Etymologies & 19th-Century Discourse Citations",
        "liahona",
    ),
    "book-of-mormon-onomasticon": (
        "enriched",
        "The Book of Mormon",
        "ONOMASTICON STUDY EDITION",
        "With Interactive BYU Etymologies, Semitic Roots & IPA Pronunciations",
        "liahona",
    ),
    "top-1000-cited-verses": (
        "enriched",
        "Top 1,000 Cited Verses",
        "RESTORATION CITATION INDEX",
        "Ranked by 19th-Century Sermon Frequency with Public-Domain Excerpts",
        "arch",
    ),
    # Variants, Parallels & Poetics
    "book-of-mormon-historical-variants": (
        "variants",
        "The Book of Mormon",
        "HISTORICAL VARIANTS • 1830–2013",
        "Word-Level Collation Across Eight Landmark Print Editions",
        "collation",
    ),
    "bom-intertextual-parallels": (
        "variants",
        "Book of Mormon Parallels",
        "INTERTEXTUAL COLLATION EDITION",
        "Brass Plates Isaiah & The Sermon at the Temple Aligned with the KJV",
        "collation",
    ),
    "bom-poetic-and-chiasmus": (
        "variants",
        "The Book of Mormon",
        "POETRY & CHIASMUS EDITION",
        "Concentric Chiastic Structures, Hebraic Parallelisms & Prophetic Psalms",
        "collation",
    ),
    # Reading Guides
    "early-modern-english-quick-guide": (
        "guides",
        "Reading Old English Scripture",
        "PLAIN-LANGUAGE QUICK GUIDE",
        "A Practical Companion to Thou, Ye, -eth, Archaic Syntax & Vocabulary",
        "rose",
    ),
    "early-modern-english-scripture-guide": (
        "guides",
        "Early Modern English",
        "COMPREHENSIVE REFERENCE GUIDE",
        "Philological Grammar, Pronouns, Verbal Morphology & Hebraisms in Scripture",
        "rose",
    ),
    # Apocrypha & Ancient Texts
    "kjv-apocrypha": (
        "apocrypha",
        "The KJV Apocrypha",
        "1611 DEUTEROCANONICAL EDITION",
        "The Fifteen Books Placed Between the Old and New Testaments",
        "seal",
    ),
    "enoch-jubilees-jasher": (
        "apocrypha",
        "Enoch, Jubilees & Jasher",
        "ANCIENT APOCRYPHA OMNIBUS",
        "Three Foundational Extra-Canonical Books with Scholarly Notes",
        "seal",
    ),
    "complete-apocrypha-pseudepigrapha-compendium": (
        "apocrypha",
        "Apocrypha & Pseudepigrapha",
        "COMPLETE 99-BOOK COMPENDIUM",
        "Deuterocanon, Enochic Literature, Second Temple Texts & Provenance Dossiers",
        "seal",
    ),
    # Restoration Literature
    "foundational-lds-classics-anthology": (
        "literature",
        "Foundational Classics",
        "NINE-VOLUME DOCTRINAL OMNIBUS",
        "Landmark Works of Early Restoration Theology & Instruction",
        "arch",
    ),
    "complete-lds-literature-compendium": (
        "literature",
        "Restoration Literature",
        "COMPLETE 71-VOLUME COMPENDIUM",
        "Foundational Theology, History, Biographies & Discourses (1833–1927)",
        "arch",
    ),
}


def _resolve_cover_spec(work: Work) -> tuple[CoverPalette, str, str, str, str]:
    wid = work.id.lower()
    if wid in COVER_SPECS:
        pal_key, main_title, pill, sub, emb_ovr = COVER_SPECS[wid]
        pal = PALETTES[pal_key]
        return pal, main_title, pill, sub, (emb_ovr or pal.emblem_style)

    # Fallback resolution for any custom work
    theme = work.css_theme.lower()
    if "minimalist" in wid or "minimalist" in theme:
        pal = PALETTES["clean"]
        clean_t = re.sub(r"\s*\([^)]*\)", "", work.title).strip()
        return pal, clean_t, "", work.subtitle or "", pal.emblem_style

    pal = PALETTES["canon"]
    clean_t = re.sub(r"\s*\([^)]*\)", "", work.title).strip()
    pill = (work.edition_label or "").upper()
    sub = re.sub(r"[✦◈★Δ⇄\[\]]+", "", work.subtitle or "").strip()
    return pal, clean_t, pill, sub, pal.emblem_style


def _load_font(
    size: int,
    bold: bool = False,
    italic: bool = False,
    display: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load classical book typography (`Constantia` for display titles, `Palatino Linotype` for prose/subtitles)."""
    win_fonts = Path("C:/Windows/Fonts")
    if display:
        if bold and italic:
            candidates = ["constanz.ttf", "palabi.ttf", "timesbi.ttf"]
        elif bold:
            candidates = ["constanb.ttf", "palab.ttf", "timesbd.ttf"]
        elif italic:
            candidates = ["constani.ttf", "palai.ttf", "timesi.ttf"]
        else:
            candidates = ["constan.ttf", "pala.ttf", "times.ttf"]
    else:
        if bold and italic:
            candidates = ["palabi.ttf", "constanz.ttf", "timesbi.ttf"]
        elif bold:
            candidates = ["palab.ttf", "constanb.ttf", "timesbd.ttf"]
        elif italic:
            candidates = ["palai.ttf", "constani.ttf", "timesi.ttf"]
        else:
            candidates = ["pala.ttf", "constan.ttf", "times.ttf"]

    for fname in candidates:
        fpath = win_fonts / fname
        if fpath.exists():
            try:
                return ImageFont.truetype(str(fpath), size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def _measure_tracked_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    tracking: int = 0,
) -> tuple[int, int]:
    """Measure `(width, height)` of `text` when rendered with `tracking` pixels between characters."""
    if not text:
        return 0, 0
    if tracking == 0:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0], bb[3] - bb[1]
    total_w = 0
    max_h = 0
    for i, ch in enumerate(text):
        bb = draw.textbbox((0, 0), ch, font=font)
        cw = int(draw.textlength(ch, font=font))
        ch_h = bb[3] - bb[1]
        if ch_h > max_h:
            max_h = ch_h
        total_w += cw
        if i < len(text) - 1:
            total_w += tracking
    return total_w, max_h


def _draw_tracked_text(
    draw: ImageDraw.ImageDraw,
    cx: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int],
    tracking: int = 0,
) -> int:
    """Draw horizontally centered `text` at `(cx, y)` with `tracking` pixels between characters.
    Returns the rendered height of the line.
    """
    if not text:
        return 0
    if tracking == 0:
        bb = draw.textbbox((0, 0), text, font=font)
        w = bb[2] - bb[0]
        h = bb[3] - bb[1]
        draw.text((cx - w // 2, y), text, font=font, fill=fill)
        return h

    total_w, max_h = _measure_tracked_text(draw, text, font, tracking=tracking)
    curr_x = cx - total_w // 2
    for ch in text:
        draw.text((curr_x, y), ch, font=font, fill=fill)
        curr_x += int(draw.textlength(ch, font=font)) + tracking
    return max_h


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    curr = words[0]
    for w in words[1:]:
        test = f"{curr} {w}"
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            curr = test
        else:
            lines.append(curr)
            curr = w
    lines.append(curr)
    return lines


def _get_partitions(words: list[str], k: int):
    n = len(words)
    if k == 1:
        yield [" ".join(words)]
        return
    for cuts in itertools.combinations(range(1, n), k - 1):
        lines = []
        prev = 0
        for c in cuts:
            lines.append(" ".join(words[prev:c]))
            prev = c
        lines.append(" ".join(words[prev:]))
        yield lines


def _fit_title_layout(
    draw: ImageDraw.ImageDraw,
    clean_title: str,
    max_w: int = 1220,
    max_h: int = 580,
    start_size: int = 168,
    min_size: int = 104,
    tracking: int = 6,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int]:
    """Select an authoritative, balanced Constantia display size and line partition
    that reads clearly on Kindle thumbnails while leaving room for the centerpiece artwork.
    """
    clean_upper = clean_title.upper()
    words = clean_upper.split()
    n = len(words)
    if not words:
        return _load_font(140, bold=True, display=True), [], tracking

    # Natural semantic line breaks for common multi-word titles
    if clean_upper == "THE BOOK OF MORMON":
        for sz in range(start_size, min_size - 1, -4):
            f = _load_font(sz, bold=True, display=True)
            lines = ["THE BOOK", "OF MORMON"]
            widths = [_measure_tracked_text(draw, l, f, tracking)[0] for l in lines]
            if all(w <= max_w for w in widths):
                return f, lines, tracking
    elif clean_upper == "THE DOCTRINE AND COVENANTS":
        for sz in range(min(start_size, 148), min_size - 1, -4):
            f = _load_font(sz, bold=True, display=True)
            lines = ["THE DOCTRINE", "AND COVENANTS"]
            widths = [_measure_tracked_text(draw, l, f, tracking)[0] for l in lines]
            if all(w <= max_w for w in widths):
                return f, lines, tracking
    elif clean_upper == "THE PEARL OF GREAT PRICE":
        for sz in range(min(start_size, 152), min_size - 1, -4):
            f = _load_font(sz, bold=True, display=True)
            lines = ["THE PEARL", "OF GREAT PRICE"]
            widths = [_measure_tracked_text(draw, l, f, tracking)[0] for l in lines]
            if all(w <= max_w for w in widths):
                return f, lines, tracking
    elif clean_upper in ("THE OLD TESTAMENT", "THE NEW TESTAMENT", "THE STANDARD WORKS"):
        for sz in range(start_size, min_size - 1, -4):
            f = _load_font(sz, bold=True, display=True)
            lines = [words[0] + " " + words[1], words[2]] if clean_upper != "THE STANDARD WORKS" else ["THE STANDARD", "WORKS"]
            widths = [_measure_tracked_text(draw, l, f, tracking)[0] for l in lines]
            if all(w <= max_w for w in widths):
                return f, lines, tracking

    if n <= 2:
        allowed_k = [1, 2]
    elif n == 3:
        allowed_k = [2]
    elif n <= 5:
        allowed_k = [2, 3]
    else:
        allowed_k = [2, 3]

    for sz in range(min(start_size, 154), min_size - 1, -4):
        font = _load_font(sz, bold=True, display=True)
        best_at_sz = None
        for k in allowed_k:
            if k > n:
                continue
            for lines in _get_partitions(words, k):
                measures = [_measure_tracked_text(draw, l, font, tracking) for l in lines]
                widths = [m[0] for m in measures]
                if any(w > max_w for w in widths):
                    continue
                heights = [m[1] for m in measures]
                th = sum(int(h * 1.28) for h in heights)
                if th > max_h:
                    continue

                orphan_pen = 0
                for l in lines:
                    lw = l.split()
                    if len(lw) == 1 and len(lw[0]) <= 3:
                        orphan_pen += 40

                avg_w = sum(widths) / len(widths)
                var_w = sum((w - avg_w) ** 2 for w in widths) / len(widths)
                score = -orphan_pen * 100 - (var_w ** 0.5)

                if best_at_sz is None or score > best_at_sz[0]:
                    best_at_sz = (score, font, lines)

        if best_at_sz is not None:
            return best_at_sz[1], best_at_sz[2], tracking

    fallback_font = _load_font(min_size, bold=True, display=True)
    return fallback_font, _wrap_text(draw, clean_upper, fallback_font, max_w), 4


def _draw_centerpiece_illustration(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    radius: int,
    style: str,
    primary: tuple[int, int, int],
    secondary: tuple[int, int, int],
    bg_fill: tuple[int, int, int],
) -> None:
    """Render a large, intricate, fine-press centerpiece illustration at `(cx, cy)`."""
    # Outer architectural degree bezel (common to all medallions for cohesive series identity)
    r_outer = radius
    r_bezel = int(radius * 0.93)
    r_inner_ring = int(radius * 0.86)

    draw.ellipse((cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer), outline=primary, width=4)
    draw.ellipse((cx - r_bezel, cy - r_bezel, cx + r_bezel, cy + r_bezel), outline=secondary, width=2)
    draw.ellipse((cx - r_inner_ring, cy - r_inner_ring, cx + r_inner_ring, cy + r_inner_ring), fill=bg_fill, outline=primary, width=3)

    # 72 degree ticks inside the bezel ring
    for deg in range(0, 360, 5):
        ang = math.radians(deg)
        r1 = r_inner_ring if deg % 15 == 0 else int(radius * 0.89)
        r2 = r_bezel
        w_tick = 3 if deg % 45 == 0 else (2 if deg % 15 == 0 else 1)
        col = primary if deg % 15 == 0 else secondary
        draw.line(
            (cx + int(r1 * math.cos(ang)), cy + int(r1 * math.sin(ang)), cx + int(r2 * math.cos(ang)), cy + int(r2 * math.sin(ang))),
            fill=col,
            width=w_tick,
        )

    # Cardinal finial diamonds outside the outer ring
    for deg in (0, 90, 180, 270):
        ang = math.radians(deg)
        fx = cx + int((r_outer + 18) * math.cos(ang))
        fy = cy + int((r_outer + 18) * math.sin(ang))
        draw.polygon([(fx, fy - 10), (fx + 10, fy), (fx, fy + 10), (fx - 10, fy)], fill=primary)

    if style == "liahona":
        # Ornate Liahona / Celestial Astrolabe: 24 radiating meridian lines, interlocking squares, 8-point compass rose
        for deg in range(0, 360, 15):
            ang = math.radians(deg)
            draw.line(
                (cx + int(radius * 0.18 * math.cos(ang)), cy + int(radius * 0.18 * math.sin(ang)),
                 cx + int(radius * 0.84 * math.cos(ang)), cy + int(radius * 0.84 * math.sin(ang))),
                fill=secondary,
                width=1,
            )
        # Off-center astrolabe ecliptic circles
        for ang_deg in (0, 90, 180, 270):
            ang = math.radians(ang_deg)
            ecx = cx + int(radius * 0.22 * math.cos(ang))
            ecy = cy + int(radius * 0.22 * math.sin(ang))
            er = int(radius * 0.36)
            draw.ellipse((ecx - er, ecy - er, ecx + er, ecy + er), outline=secondary, width=2)

        # Two interlocking Melchizedek squares
        for offset in (0, 45):
            sq_pts = []
            r_sq = int(radius * 0.68)
            for i in range(4):
                ang = math.radians(offset + i * 90)
                sq_pts.append((cx + int(r_sq * math.cos(ang)), cy + int(r_sq * math.sin(ang))))
            draw.polygon(sq_pts, outline=primary, width=3)

        # 8-pointed sculpted compass star
        r_star_long = int(radius * 0.78)
        r_star_diagonal = int(radius * 0.56)
        r_star_waist = int(radius * 0.18)
        star_pts = []
        for i in range(16):
            ang = math.radians(i * 22.5 - 90)
            if i % 4 == 0:
                r_c = r_star_long
            elif i % 2 == 0:
                r_c = r_star_diagonal
            else:
                r_c = r_star_waist
            star_pts.append((cx + int(r_c * math.cos(ang)), cy + int(r_c * math.sin(ang))))
        draw.polygon(star_pts, fill=bg_fill, outline=primary, width=3)

        # Inner Liahona spindle rings & core sun
        r_mid = int(radius * 0.26)
        draw.ellipse((cx - r_mid, cy - r_mid, cx + r_mid, cy + r_mid), outline=primary, width=3)
        r_core = int(radius * 0.11)
        draw.ellipse((cx - r_core, cy - r_core, cx + r_core, cy + r_core), fill=primary)

    elif style == "codex":
        # Clean Fine-Press Emblem: Geometric Compass Diamond + Open Scripture Codex + Sunburst
        for deg in range(0, 360, 15):
            ang = math.radians(deg)
            draw.line(
                (cx + int(radius * 0.35 * math.cos(ang)), cy + int(radius * 0.35 * math.sin(ang)),
                 cx + int(radius * 0.78 * math.cos(ang)), cy + int(radius * 0.78 * math.sin(ang))),
                fill=secondary,
                width=1,
            )
        for scale, col, w in ((0.72, primary, 3), (0.65, secondary, 2)):
            d = int(radius * scale)
            draw.polygon([(cx, cy - d), (cx + d, cy), (cx, cy + d), (cx - d, cy)], outline=col, width=w)
            s = int(d * 0.7071)
            draw.rectangle((cx - s, cy - s, cx + s, cy + s), outline=secondary, width=2)

        r_center = int(radius * 0.44)
        draw.ellipse((cx - r_center, cy - r_center, cx + r_center, cy + r_center), fill=bg_fill, outline=primary, width=3)

        # Open Scripture Codex inside center medallion
        bw = int(radius * 0.26)
        bh = int(radius * 0.20)
        # Left & right pages
        draw.rectangle((cx - bw, cy - bh, cx - 3, cy + bh), fill=bg_fill, outline=primary, width=3)
        draw.rectangle((cx + 3, cy - bh, cx + bw, cy + bh), fill=bg_fill, outline=primary, width=3)
        # Ruling lines on both pages
        for ly in range(-bh + 22, bh - 14, 18):
            draw.line((cx - bw + 16, cy + ly, cx - 16, cy + ly), fill=secondary, width=2)
            draw.line((cx + 16, cy + ly, cx + bw - 16, cy + ly), fill=secondary, width=2)
        # Spine & bookmark ribbon
        draw.line((cx, cy - bh - 8, cx, cy + bh + 28), fill=primary, width=4)
        draw.polygon([(cx - 8, cy + bh + 28), (cx, cy + bh + 18), (cx + 8, cy + bh + 28), (cx, cy + bh + 38)], fill=primary)

    elif style == "tree":
        # Tree of Life Medallion: Radiant backdrop, spreading roots & boughs, 12 luminous fruits
        for deg in range(-160, 0, 12):
            ang = math.radians(deg)
            draw.line(
                (cx, cy + int(radius * 0.15),
                 cx + int(radius * 0.80 * math.cos(ang)), cy + int(radius * 0.80 * math.sin(ang))),
                fill=secondary,
                width=1,
            )
        # Gothic rose arch ring
        r_canopy = int(radius * 0.74)
        draw.ellipse((cx - r_canopy, cy - r_canopy, cx + r_canopy, cy + r_canopy), outline=secondary, width=2)

        # Ground horizon arc & roots
        ground_y = cy + int(radius * 0.42)
        draw.line((cx - int(radius * 0.56), ground_y, cx + int(radius * 0.56), ground_y), fill=primary, width=3)
        for rx_off, ry_off in ((-90, 75), (-45, 95), (0, 105), (45, 95), (90, 75)):
            draw.line((cx, ground_y, cx + rx_off, ground_y + ry_off), fill=secondary, width=3)

        # Trunk
        trunk_top = cy - int(radius * 0.12)
        draw.polygon(
            [(cx - 18, ground_y), (cx - 8, trunk_top), (cx + 8, trunk_top), (cx + 18, ground_y)],
            fill=primary,
        )

        # Symmetrical branches & 12 glowing fruits of the Tree of Life
        branch_nodes = [
            (0, -int(radius * 0.54)),
            (-int(radius * 0.24), -int(radius * 0.48)),
            (int(radius * 0.24), -int(radius * 0.48)),
            (-int(radius * 0.44), -int(radius * 0.34)),
            (int(radius * 0.44), -int(radius * 0.34)),
            (-int(radius * 0.16), -int(radius * 0.28)),
            (int(radius * 0.16), -int(radius * 0.28)),
            (-int(radius * 0.52), -int(radius * 0.12)),
            (int(radius * 0.52), -int(radius * 0.12)),
            (-int(radius * 0.32), -int(radius * 0.10)),
            (int(radius * 0.32), -int(radius * 0.10)),
            (0, -int(radius * 0.34)),
        ]
        for bx, by in branch_nodes:
            fx, fy = cx + bx, cy + by
            stem_y = trunk_top + abs(bx) // 4
            draw.line((cx, min(ground_y - 30, stem_y), fx, fy), fill=primary, width=3)
            fr = 16
            draw.ellipse((fx - fr, fy - fr, fx + fr, fy + fr), fill=bg_fill, outline=primary, width=3)
            draw.ellipse((fx - 8, fy - 8, fx + 8, fy + 8), fill=primary)

    elif style == "collation":
        # Chiastic Armillary Sphere & Intertextual Venn Collation
        # Concentric chiastic arcs (A-B-C-X-C'-B'-A')
        for step in range(1, 6):
            r_arc = int(radius * (0.14 * step))
            draw.arc((cx - r_arc, cy - r_arc, cx + r_arc, cy + r_arc), start=200, end=340, fill=primary, width=2)
            draw.arc((cx - r_arc, cy - r_arc, cx + r_arc, cy + r_arc), start=20, end=160, fill=primary, width=2)

        # Interlocking Venn circles representing parallel texts / editions
        offset = int(radius * 0.25)
        r_venn = int(radius * 0.48)
        draw.ellipse((cx - offset - r_venn, cy - r_venn, cx - offset + r_venn, cy + r_venn), outline=primary, width=3)
        draw.ellipse((cx + offset - r_venn, cy - r_venn, cx + offset + r_venn, cy + r_venn), outline=primary, width=3)

        # Chiastic X-axis diamond & meridian cross
        d_rad = int(radius * 0.74)
        draw.polygon([(cx, cy - d_rad), (cx + d_rad, cy), (cx, cy + d_rad), (cx - d_rad, cy)], outline=secondary, width=3)
        draw.line((cx - d_rad, cy, cx + d_rad, cy), fill=secondary, width=2)
        draw.line((cx, cy - d_rad, cx, cy + d_rad), fill=secondary, width=2)

        # Central pivot star
        r_piv = int(radius * 0.14)
        draw.ellipse((cx - r_piv, cy - r_piv, cx + r_piv, cy + r_piv), fill=bg_fill, outline=primary, width=3)
        draw.polygon([(cx, cy - 18), (cx + 18, cy), (cx, cy + 18), (cx - 18, cy)], fill=primary)

    elif style == "seal":
        # Ancient Twelve-Pointed Enochic / Temple Seal + Engraved Tablet
        for base_ang in (0, 30, 60):
            pts = []
            r_sq = int(radius * 0.76)
            for i in range(4):
                ang = math.radians(base_ang + i * 90)
                pts.append((cx + int(r_sq * math.cos(ang)), cy + int(r_sq * math.sin(ang))))
            draw.polygon(pts, outline=primary, width=3)

        # 12 tribe nodes around perimeter
        for i in range(12):
            ang = math.radians(i * 30)
            nx = cx + int(radius * 0.76 * math.cos(ang))
            ny = cy + int(radius * 0.76 * math.sin(ang))
            draw.ellipse((nx - 7, ny - 7, nx + 7, ny + 7), fill=primary)

        r_mid = int(radius * 0.46)
        draw.ellipse((cx - r_mid, cy - r_mid, cx + r_mid, cy + r_mid), fill=bg_fill, outline=primary, width=3)
        r_mid2 = int(radius * 0.41)
        draw.ellipse((cx - r_mid2, cy - r_mid2, cx + r_mid2, cy + r_mid2), outline=secondary, width=2)

        # Engraved Arched Stele / Tablet in center
        tw = int(radius * 0.20)
        th = int(radius * 0.24)
        draw.arc((cx - tw, cy - th - tw // 2, cx + tw, cy - th + tw // 2), start=180, end=360, fill=primary, width=3)
        draw.line((cx - tw, cy - th, cx - tw, cy + th), fill=primary, width=3)
        draw.line((cx + tw, cy - th, cx + tw, cy + th), fill=primary, width=3)
        draw.line((cx - tw, cy + th, cx + tw, cy + th), fill=primary, width=3)
        for ly in range(-th + 18, th - 8, 18):
            draw.line((cx - tw + 14, cy + ly, cx + tw - 14, cy + ly), fill=secondary, width=2)

    elif style == "arch":
        # Classical Keystone Arch, Fluted Columns & 24-Ray Dawn Sunburst
        for i in range(24):
            ang = math.radians(i * 15)
            x1 = cx + int(radius * 0.16 * math.cos(ang))
            y1 = cy + int(radius * 0.16 * math.sin(ang))
            x2 = cx + int(radius * 0.78 * math.cos(ang))
            y2 = cy + int(radius * 0.78 * math.sin(ang))
            draw.line((x1, y1, x2, y2), fill=secondary, width=2 if i % 2 == 0 else 1)

        aw = int(radius * 0.46)
        ah = int(radius * 0.44)
        base_y = cy + int(radius * 0.44)
        spring_y = cy - int(radius * 0.04)

        # Outer & inner arch rings
        draw.arc((cx - aw, spring_y - aw, cx + aw, spring_y + aw), start=180, end=360, fill=primary, width=4)
        iw = int(aw * 0.76)
        draw.arc((cx - iw, spring_y - iw, cx + iw, spring_y + iw), start=180, end=360, fill=secondary, width=3)

        # Twin columns
        col_w = aw - iw
        draw.rectangle((cx - aw, spring_y, cx - iw, base_y), fill=bg_fill, outline=primary, width=3)
        draw.rectangle((cx + iw, spring_y, cx + aw, base_y), fill=bg_fill, outline=primary, width=3)
        # Column fluting
        for fx in (cx - aw + col_w // 3, cx - aw + 2 * col_w // 3, cx + iw + col_w // 3, cx + iw + 2 * col_w // 3):
            draw.line((fx, spring_y + 10, fx, base_y - 10), fill=secondary, width=1)

        # Stepped podium base
        draw.rectangle((cx - aw - 22, base_y, cx + aw + 22, base_y + 18), fill=bg_fill, outline=primary, width=3)
        draw.rectangle((cx - aw - 38, base_y + 18, cx + aw + 38, base_y + 34), fill=primary)

        # Central sun orb inside the arch
        r_sun = int(radius * 0.14)
        draw.ellipse((cx - r_sun, spring_y - r_sun, cx + r_sun, spring_y + r_sun), fill=primary)

    else:
        # "rose": Renaissance Printer's Geometric Rose & Compass (Reading Guides / Philology)
        for i in range(16):
            ang = math.radians(i * 22.5)
            px = cx + int(radius * 0.34 * math.cos(ang))
            py = cy + int(radius * 0.34 * math.sin(ang))
            pr = int(radius * 0.34)
            draw.ellipse((px - pr, py - pr, px + pr, py + pr), outline=secondary, width=1)

        for offset in (0, 30, 60):
            pts = []
            r_sq = int(radius * 0.68)
            for i in range(4):
                ang = math.radians(offset + i * 90)
                pts.append((cx + int(r_sq * math.cos(ang)), cy + int(r_sq * math.sin(ang))))
            draw.polygon(pts, outline=primary, width=2)

        r_core_ring = int(radius * 0.28)
        draw.ellipse((cx - r_core_ring, cy - r_core_ring, cx + r_core_ring, cy + r_core_ring), fill=bg_fill, outline=primary, width=3)
        d_in = int(radius * 0.18)
        draw.polygon([(cx, cy - d_in), (cx + d_in, cy), (cx, cy + d_in), (cx - d_in, cy)], fill=primary)


def generate_cover_png_bytes(work: Work, save_copy_dir: Path | None = Path("dist/covers")) -> bytes:
    """Render a 1200×1920 high-DPI PNG cover image for `work` and return its raw PNG bytes."""
    W, H = 1600, 2560
    palette, clean_main_title, edition_pill, work_subtitle, emblem_style = _resolve_cover_spec(work)

    # Strip any special symbols that might not exist in Windows serif fonts
    work_subtitle = re.sub(r"[✦◈★Δ⇄\[\]]+", "", work_subtitle).strip()

    img = Image.new("RGB", (W, H), palette.bg_top)
    draw = ImageDraw.Draw(img)

    # 1. Smooth vertical background gradient + subtle fine-press woven texture
    r1, g1, b1 = palette.bg_top
    r2, g2, b2 = palette.bg_bottom
    for y in range(0, H, 2):
        t = y / H
        # Subtle woven bookcloth harmonic modulation (±2 RGB units)
        weave = int(1.5 * math.sin(y * 0.35))
        c = (
            max(0, min(255, int(r1 + (r2 - r1) * t) + weave)),
            max(0, min(255, int(g1 + (g2 - g1) * t) + weave)),
            max(0, min(255, int(b1 + (b2 - b1) * t) + weave)),
        )
        draw.rectangle((0, y, W, y + 2), fill=c)

    # 2. Outer & Inner Classical Borders with Stepped Corner Cartouches
    m_out = 64
    m_mid = 82
    m_in = 96
    if palette.card_bg is not None:
        draw.rectangle((m_mid, m_mid, W - m_mid, H - m_mid), fill=palette.card_bg)

    draw.rectangle((m_out, m_out, W - m_out, H - m_out), outline=palette.primary_accent, width=4)
    draw.rectangle((m_mid, m_mid, W - m_mid, H - m_mid), outline=palette.secondary_accent, width=2)
    draw.rectangle((m_in, m_in, W - m_in, H - m_in), outline=palette.secondary_accent, width=1)

    # Corner geometric ornaments
    cs = 36
    for cx_c, cy_c in [
        (m_out, m_out),
        (W - m_out - cs, m_out),
        (m_out, H - m_out - cs),
        (W - m_out - cs, H - m_out - cs),
    ]:
        draw.rectangle((cx_c, cy_c, cx_c + cs, cy_c + cs), fill=palette.bg_top, outline=palette.primary_accent, width=3)
        draw.rectangle((cx_c + 8, cy_c + 8, cx_c + cs - 8, cy_c + cs - 8), fill=palette.primary_accent)

    # 3. Standardized Top Series Header Band
    font_series = _load_font(26, bold=True, display=False)
    draw.line((180, 148, W - 180, 148), fill=palette.secondary_accent, width=1)
    _draw_tracked_text(draw, W // 2, 168, palette.series_banner, font_series, fill=palette.primary_accent, tracking=5)
    draw.line((180, 214, W - 180, 214), fill=palette.secondary_accent, width=2)
    draw.polygon([(W // 2, 206), (W // 2 + 8, 214), (W // 2, 222), (W // 2 - 8, 214)], fill=palette.primary_accent)

    # 4. Large, Tracked Display Main Title
    font_title, title_lines, title_tracking = _fit_title_layout(
        draw, clean_main_title, max_w=W - 340, max_h=560, start_size=164, min_size=104, tracking=6
    )

    line_heights = [_measure_tracked_text(draw, l, font_title, title_tracking)[1] for l in title_lines]
    total_title_h = sum(int(h * 1.28) for h in line_heights)

    curr_y = 285 if len(title_lines) >= 3 else (320 if len(title_lines) == 2 else 360)
    for tline in title_lines:
        lh = _draw_tracked_text(
            draw, W // 2, curr_y, tline, font_title, fill=palette.title_color, tracking=title_tracking
        )
        curr_y += int(lh * 1.28)

    # 5. Standardized Edition Pill / Badge (or Classical Divider for Clean Series)
    curr_y += 22
    if edition_pill:
        font_pill = _load_font(31, bold=True, display=False)
        pw, ph = _measure_tracked_text(draw, edition_pill, font_pill, tracking=5)
        pad_x, pad_y = 44, 16
        box_w = pw + pad_x * 2
        box_h = ph + pad_y * 2
        bx1 = (W - box_w) // 2
        by1 = curr_y
        bx2 = bx1 + box_w
        by2 = by1 + box_h

        # Flanking ornamental wings
        wing_y = (by1 + by2) // 2
        draw.line((190, wing_y, bx1 - 24, wing_y), fill=palette.primary_accent, width=2)
        draw.line((bx2 + 24, wing_y, W - 190, wing_y), fill=palette.primary_accent, width=2)
        draw.polygon([(bx1 - 24, wing_y - 7), (bx1 - 14, wing_y), (bx1 - 24, wing_y + 7), (bx1 - 34, wing_y)], fill=palette.primary_accent)
        draw.polygon([(bx2 + 24, wing_y - 7), (bx2 + 34, wing_y), (bx2 + 24, wing_y + 7), (bx2 + 14, wing_y)], fill=palette.primary_accent)

        draw.rectangle((bx1, by1, bx2, by2), fill=palette.pill_bg, outline=palette.primary_accent, width=3)
        _draw_tracked_text(draw, W // 2, by1 + pad_y - 2, edition_pill, font_pill, fill=palette.pill_text, tracking=5)
        curr_y = by2 + 36
    else:
        # Clean classical diamond rule
        draw.line((W // 2 - 280, curr_y, W // 2 - 28, curr_y), fill=palette.primary_accent, width=3)
        draw.polygon(
            [(W // 2, curr_y - 12), (W // 2 + 14, curr_y), (W // 2, curr_y + 12), (W // 2 - 14, curr_y)],
            fill=palette.primary_accent,
        )
        draw.line((W // 2 + 28, curr_y, W // 2 + 280, curr_y), fill=palette.primary_accent, width=3)
        curr_y += 40

    # 6. Subtitle (Palatino Italic)
    if work_subtitle:
        font_sub = _load_font(40, italic=True, display=False)
        sub_lines = _wrap_text(draw, work_subtitle, font_sub, max_width=W - 360)
        for sline in sub_lines[:3]:
            sb = draw.textbbox((0, 0), sline, font=font_sub)
            sw = sb[2] - bbox_left(sb)
            sh = sb[3] - sb[1]
            draw.text(((W - sw) // 2, curr_y), sline, font=font_sub, fill=palette.subtitle_color)
            curr_y += int(sh * 1.32)

    # 7. Large, Prominent Centerpiece Illustration (Radius ~ 280–345px)
    bottom_anchor = 2070
    avail_h = bottom_anchor - curr_y
    med_cy = curr_y + avail_h // 2
    med_radius = min(345, max(265, int(avail_h * 0.40)))

    # Soft radial ambient glow behind the medallion blended smoothly to the exact gradient at med_cy
    if palette.card_bg is not None:
        bg_base = palette.card_bg
    else:
        t_med = med_cy / H
        bg_base = (
            int(r1 + (r2 - r1) * t_med),
            int(g1 + (g2 - g1) * t_med),
            int(b1 + (b2 - b1) * t_med),
        )
    gr, gg, gb = palette.glow_color
    br, bg_g, bb = bg_base
    for step in range(24, 0, -1):
        frac = step / 24.0
        r_glow = int(med_radius * (1.0 + 0.34 * frac))
        t_blend = ((1.0 - frac) ** 2.0) * 0.50
        col_glow = (
            int(br + (gr - br) * t_blend),
            int(bg_g + (gg - bg_g) * t_blend),
            int(bb + (gb - bb) * t_blend),
        )
        draw.ellipse((W // 2 - r_glow, med_cy - r_glow, W // 2 + r_glow, med_cy + r_glow), fill=col_glow)

    _draw_centerpiece_illustration(
        draw,
        cx=W // 2,
        cy=med_cy,
        radius=med_radius,
        style=emblem_style,
        primary=palette.primary_accent,
        secondary=palette.secondary_accent,
        bg_fill=bg_base,
    )

    # 8. Author / Attribution Block
    auth_y = 2095
    authors_str = " • ".join(work.authors[:3])
    if len(work.authors) > 3:
        authors_str += " • et al."
    font_author = _load_font(38, bold=False, display=False)
    author_lines = _wrap_text(draw, authors_str, font_author, max_width=W - 320)
    for aline in author_lines[:2]:
        ab = draw.textbbox((0, 0), aline, font=font_author)
        aw = ab[2] - ab[0]
        draw.text(((W - aw) // 2, auth_y), aline, font=font_author, fill=palette.title_color)
        auth_y += 50

    # 9. Footer Colophon
    draw.line((220, 2265, W - 220, 2265), fill=palette.secondary_accent, width=2)
    font_colophon = _load_font(26, bold=True, display=False)
    _draw_tracked_text(
        draw, W // 2, 2305, "PROTEUS SCRIPTORIUM", font_colophon, fill=palette.primary_accent, tracking=6
    )

    font_subcol = _load_font(23, italic=True, display=False)
    subcol = "Kindle Enhanced Typesetting Edition"
    scb = draw.textbbox((0, 0), subcol, font=font_subcol)
    scw = scb[2] - scb[0]
    draw.text(((W - scw) // 2, 2350), subcol, font=font_subcol, fill=palette.subtitle_color)

    # Downsample to 1200×1920 with Lanczos filter
    final_img = img.resize((1200, 1920), resample=Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    final_img.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()

    if save_copy_dir is not None:
        save_copy_dir.mkdir(parents=True, exist_ok=True)
        (save_copy_dir / f"{work.id}.png").write_bytes(png_bytes)

    return png_bytes


def bbox_left(bbox: tuple[int, int, int, int]) -> int:
    return bbox[0]
