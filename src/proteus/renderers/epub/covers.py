"""Proteus Scriptorium Programmatic Cover Art Engine (`covers.py`).

Generates high-resolution (1200×1920, 1:1.6 Kindle Paperwhite / KDP aspect ratio)
book covers with a cohesive classical-modern **Proteus Press / Scriptorium** visual identity.
Uses 2× supersampling with Lanczos downsampling for razor-sharp geometric medallions,
filigree borders, and classical serif typography.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from proteus.core.models import Work


@dataclass
class CoverPalette:
    bg_top: tuple[int, int, int]
    bg_bottom: tuple[int, int, int]
    card_bg: tuple[int, int, int] | None
    primary_accent: tuple[int, int, int]
    secondary_accent: tuple[int, int, int]
    title_color: tuple[int, int, int]
    subtitle_color: tuple[int, int, int]
    emblem_style: str  # "celestial", "seal", "arch", "minimal", "collation"
    series_banner: str


PALETTES: dict[str, CoverPalette] = {
    "canon": CoverPalette(
        bg_top=(14, 27, 46),
        bg_bottom=(8, 16, 28),
        card_bg=None,
        primary_accent=(214, 175, 75),
        secondary_accent=(145, 118, 52),
        title_color=(248, 244, 234),
        subtitle_color=(212, 204, 186),
        emblem_style="celestial",
        series_banner="PROTEUS SCRIPTORIUM • CANONICAL EDITIONS",
    ),
    "apocrypha": CoverPalette(
        bg_top=(56, 15, 24),
        bg_bottom=(30, 8, 13),
        card_bg=None,
        primary_accent=(222, 182, 98),
        secondary_accent=(158, 122, 58),
        title_color=(250, 244, 232),
        subtitle_color=(224, 206, 184),
        emblem_style="seal",
        series_banner="PROTEUS SCRIPTORIUM • APOCRYPHA & PSEUDEPIGRAPHA",
    ),
    "literature": CoverPalette(
        bg_top=(16, 42, 33),
        bg_bottom=(9, 24, 19),
        card_bg=None,
        primary_accent=(216, 180, 88),
        secondary_accent=(144, 118, 58),
        title_color=(247, 244, 235),
        subtitle_color=(208, 214, 198),
        emblem_style="arch",
        series_banner="PROTEUS SCRIPTORIUM • RESTORATION CLASSICS LIBRARY",
    ),
    "minimalist": CoverPalette(
        bg_top=(245, 240, 228),
        bg_bottom=(235, 228, 212),
        card_bg=(250, 247, 239),
        primary_accent=(140, 45, 25),
        secondary_accent=(95, 88, 76),
        title_color=(24, 24, 24),
        subtitle_color=(72, 68, 60),
        emblem_style="minimal",
        series_banner="PROTEUS PRESS • MINIMALIST PURE TYPOGRAPHY SERIES",
    ),
    "narrative": CoverPalette(
        bg_top=(24, 36, 48),
        bg_bottom=(14, 21, 30),
        card_bg=None,
        primary_accent=(214, 159, 92),
        secondary_accent=(138, 104, 64),
        title_color=(246, 242, 234),
        subtitle_color=(205, 198, 186),
        emblem_style="celestial",
        series_banner="PROTEUS PRESS • READERS & STUDY EDITIONS",
    ),
    "enriched": CoverPalette(
        bg_top=(32, 18, 44),
        bg_bottom=(16, 9, 24),
        card_bg=None,
        primary_accent=(229, 193, 88),
        secondary_accent=(178, 58, 58),
        title_color=(250, 246, 236),
        subtitle_color=(220, 210, 196),
        emblem_style="celestial",
        series_banner="PROTEUS SCRIPTORIUM • RELATIONAL & ENRICHED STUDY SERIES",
    ),
    "variants": CoverPalette(
        bg_top=(40, 26, 18),
        bg_bottom=(22, 14, 10),
        card_bg=None,
        primary_accent=(220, 188, 114),
        secondary_accent=(156, 128, 74),
        title_color=(248, 243, 232),
        subtitle_color=(216, 204, 184),
        emblem_style="collation",
        series_banner="PROTEUS SCRIPTORIUM • CRITICAL COLLATION & POETICS",
    ),
}


def _select_palette(work: Work) -> CoverPalette:
    wid = work.id.lower()
    theme = work.css_theme.lower()
    if "minimalist" in wid or "minimalist" in theme:
        return PALETTES["minimalist"]
    if any(k in wid for k in ("apocrypha", "enoch", "pseudepigrapha")):
        return PALETTES["apocrypha"]
    if any(k in wid for k in ("classics", "literature")):
        return PALETTES["literature"]
    if any(k in wid for k in ("variants", "parallels", "poetic", "chiasmus")) or "variants" in theme:
        return PALETTES["variants"]
    if any(k in wid for k in ("cited", "onomasticon", "red-letter", "master-study", "early-modern-english")) or "enriched" in theme:
        return PALETTES["enriched"]
    if any(k in wid for k in ("narrative", "notebook")) or "narrative" in theme or "study" in theme:
        return PALETTES["narrative"]
    return PALETTES["canon"]


def _load_font(size: int, bold: bool = False, italic: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load high-quality serif fonts on Windows (Georgia / Palatino / Times New Roman) with graceful fallback."""
    win_fonts = Path("C:/Windows/Fonts")
    candidates: list[str] = []
    if bold and italic:
        candidates = ["georgiabi.ttf", "palabi.ttf", "timesbi.ttf"]
    elif bold:
        candidates = ["georgiab.ttf", "palab.ttf", "timesbd.ttf"]
    elif italic:
        candidates = ["georgiai.ttf", "palai.ttf", "timesi.ttf"]
    else:
        candidates = ["georgia.ttf", "pala.ttf", "times.ttf"]

    for fname in candidates:
        fpath = win_fonts / fname
        if fpath.exists():
            try:
                return ImageFont.truetype(str(fpath), size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int) -> list[str]:
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


def _draw_emblem(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    radius: int,
    style: str,
    primary: tuple[int, int, int],
    secondary: tuple[int, int, int],
    bg_fill: tuple[int, int, int],
) -> None:
    """Draw a high-precision geometric scriptorium medallion centered at (cx, cy)."""
    # Outer concentric rings
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=primary, width=4)
    r_inner = int(radius * 0.88)
    draw.ellipse((cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner), outline=secondary, width=2)

    if style == "celestial":
        # Eight-pointed Melchizedek / Celestial Star (two interlocking squares) + compass rays
        for angle_offset in (0, 45):
            pts = []
            r_sq = int(radius * 0.74)
            for i in range(4):
                ang = math.radians(angle_offset + i * 90)
                pts.append((cx + int(r_sq * math.cos(ang)), cy + int(r_sq * math.sin(ang))))
            draw.polygon(pts, outline=primary, width=3)
        # 8-point inner star
        r_star_out = int(radius * 0.56)
        r_star_in = int(radius * 0.22)
        star_pts = []
        for i in range(16):
            ang = math.radians(i * 22.5 - 90)
            r_cur = r_star_out if i % 2 == 0 else r_star_in
            star_pts.append((cx + int(r_cur * math.cos(ang)), cy + int(r_cur * math.sin(ang))))
        draw.polygon(star_pts, fill=bg_fill, outline=primary, width=3)
        r_core = int(radius * 0.12)
        draw.ellipse((cx - r_core, cy - r_core, cx + r_core, cy + r_core), fill=primary)

    elif style == "seal":
        # Ancient twelve-pointed seal + inner scroll/tablet motif
        for base_ang in (0, 30, 60):
            pts = []
            r_sq = int(radius * 0.76)
            for i in range(4):
                ang = math.radians(base_ang + i * 90)
                pts.append((cx + int(r_sq * math.cos(ang)), cy + int(r_sq * math.sin(ang))))
            draw.polygon(pts, outline=primary, width=3)
        r_mid = int(radius * 0.44)
        draw.ellipse((cx - r_mid, cy - r_mid, cx + r_mid, cy + r_mid), fill=bg_fill, outline=primary, width=4)
        # Inner tablet lines
        tw = int(radius * 0.22)
        th = int(radius * 0.28)
        draw.rectangle((cx - tw, cy - th, cx + tw, cy + th), outline=primary, width=3)
        for ly in (-th // 2, 0, th // 2):
            draw.line((cx - tw + 12, cy + ly, cx + tw - 12, cy + ly), fill=secondary, width=2)

    elif style == "arch":
        # Classical Keystone Arch & Sunburst Rays
        for i in range(12):
            ang = math.radians(i * 30)
            x1 = cx + int(radius * 0.30 * math.cos(ang))
            y1 = cy + int(radius * 0.30 * math.sin(ang))
            x2 = cx + int(radius * 0.80 * math.cos(ang))
            y2 = cy + int(radius * 0.80 * math.sin(ang))
            draw.line((x1, y1, x2, y2), fill=secondary, width=2)
        aw = int(radius * 0.46)
        ah = int(radius * 0.52)
        draw.arc((cx - aw, cy - ah, cx + aw, cy + ah), start=180, end=360, fill=primary, width=5)
        draw.line((cx - aw, cy, cx - aw, cy + ah // 2), fill=primary, width=5)
        draw.line((cx + aw, cy, cx + aw, cy + ah // 2), fill=primary, width=5)
        draw.line((cx - aw - 16, cy + ah // 2, cx + aw + 16, cy + ah // 2), fill=primary, width=4)
        r_core = int(radius * 0.14)
        draw.ellipse((cx - r_core, cy - r_core, cx + r_core, cy + r_core), fill=primary)

    elif style == "minimal":
        # Ultra-clean Swiss geometric compass & diamond
        d_rad = int(radius * 0.64)
        diamond = [(cx, cy - d_rad), (cx + d_rad, cy), (cx, cy + d_rad), (cx - d_rad, cy)]
        draw.polygon(diamond, outline=primary, width=4)
        r_mid = int(radius * 0.36)
        draw.ellipse((cx - r_mid, cy - r_mid, cx + r_mid, cy + r_mid), outline=secondary, width=3)
        draw.line((cx - int(radius * 0.78), cy, cx + int(radius * 0.78), cy), fill=primary, width=2)
        draw.line((cx, cy - int(radius * 0.78), cx, cy + int(radius * 0.78)), fill=primary, width=2)
        r_dot = int(radius * 0.09)
        draw.ellipse((cx - r_dot, cy - r_dot, cx + r_dot, cy + r_dot), fill=primary)

    else:
        # "collation": Interlocking Venn/Collation circles & Chiastic X-axis
        offset = int(radius * 0.26)
        r_sub = int(radius * 0.48)
        draw.ellipse((cx - offset - r_sub, cy - r_sub, cx - offset + r_sub, cy + r_sub), outline=primary, width=3)
        draw.ellipse((cx + offset - r_sub, cy - r_sub, cx + offset + r_sub, cy + r_sub), outline=primary, width=3)
        d_rad = int(radius * 0.72)
        draw.polygon([(cx, cy - d_rad), (cx + d_rad, cy), (cx, cy + d_rad), (cx - d_rad, cy)], outline=secondary, width=3)
        r_dot = int(radius * 0.10)
        draw.ellipse((cx - r_dot, cy - r_dot, cx + r_dot, cy + r_dot), fill=primary)


def generate_cover_png_bytes(work: Work, save_copy_dir: Path | None = Path("dist/covers")) -> bytes:
    """Render a 1200×1920 high-DPI PNG cover image for `work` and return its raw PNG bytes."""
    # Render at 1600×2560 and downsample to 1200×1920 for crisp anti-aliased geometry
    W, H = 1600, 2560
    palette = _select_palette(work)

    img = Image.new("RGB", (W, H), palette.bg_top)
    draw = ImageDraw.Draw(img)

    # 1. Vertical gradient background
    r1, g1, b1 = palette.bg_top
    r2, g2, b2 = palette.bg_bottom
    for y in range(0, H, 4):
        t = y / H
        c = (
            int(r1 + (r2 - r1) * t),
            int(g1 + (g2 - g1) * t),
            int(b1 + (b2 - b1) * t),
        )
        draw.rectangle((0, y, W, y + 4), fill=c)

    # 2. Outer & Inner Classical Borders
    m_out = 84
    m_in = 108
    if palette.card_bg is not None:
        draw.rectangle((m_in, m_in, W - m_in, H - m_in), fill=palette.card_bg)

    draw.rectangle((m_out, m_out, W - m_out, H - m_out), outline=palette.primary_accent, width=5)
    draw.rectangle((m_in, m_in, W - m_in, H - m_in), outline=palette.secondary_accent, width=2)

    # Corner geometric ornaments
    cs = 34
    for cx_c, cy_c in [
        (m_out, m_out),
        (W - m_out - cs, m_out),
        (m_out, H - m_out - cs),
        (W - m_out - cs, H - m_out - cs),
    ]:
        draw.rectangle((cx_c, cy_c, cx_c + cs, cy_c + cs), outline=palette.primary_accent, width=3)
        draw.rectangle((cx_c + 8, cy_c + 8, cx_c + cs - 8, cy_c + cs - 8), fill=palette.primary_accent)

    # 3. Top Series Header Banner
    font_series = _load_font(26, bold=True)
    banner_text = palette.series_banner
    bbox_b = draw.textbbox((0, 0), banner_text, font=font_series)
    bw = bbox_b[2] - bbox_b[0]
    draw.text(((W - bw) // 2, 168), banner_text, font=font_series, fill=palette.primary_accent)
    draw.line((220, 222, W - 220, 222), fill=palette.secondary_accent, width=2)

    # 4. Edition Label Pill (above title)
    font_edition = _load_font(28, italic=True)
    ed_text = work.edition_label
    bbox_ed = draw.textbbox((0, 0), ed_text, font=font_edition)
    ed_w = bbox_ed[2] - bbox_ed[0]
    draw.text(((W - ed_w) // 2, 275), ed_text, font=font_edition, fill=palette.subtitle_color)

    # 5. Main Title (auto-scaled & wrapped)
    clean_main_title = work.title
    # Strip parenthetical edition suffix if it's long so the main title breathes cleanly
    if "(" in clean_main_title and len(clean_main_title) > 34:
        base_part, paren_part = clean_main_title.split("(", 1)
        clean_main_title = base_part.strip()
        if not work.subtitle:
            work_subtitle = paren_part.rstrip(")").strip()
        else:
            work_subtitle = f"({paren_part.rstrip(')')}) • {work.subtitle}"
    else:
        work_subtitle = work.subtitle or ""

    title_font_size = 92 if len(clean_main_title) < 26 else (78 if len(clean_main_title) < 42 else 66)
    font_title = _load_font(title_font_size, bold=True)
    title_lines = _wrap_text(draw, clean_main_title.upper(), font_title, max_width=W - 340)

    curr_y = 365
    for tline in title_lines[:4]:
        tb = draw.textbbox((0, 0), tline, font=font_title)
        tw = tb[2] - tb[0]
        th = tb[3] - tb[1]
        draw.text(((W - tw) // 2, curr_y), tline, font=font_title, fill=palette.title_color)
        curr_y += int(th * 1.32)

    # Ornamental rule under title
    curr_y += 32
    draw.line((W // 2 - 240, curr_y, W // 2 - 24, curr_y), fill=palette.primary_accent, width=3)
    draw.polygon(
        [(W // 2, curr_y - 12), (W // 2 + 14, curr_y), (W // 2, curr_y + 12), (W // 2 - 14, curr_y)],
        fill=palette.primary_accent,
    )
    draw.line((W // 2 + 24, curr_y, W // 2 + 240, curr_y), fill=palette.primary_accent, width=3)
    curr_y += 42

    # 6. Subtitle
    if work_subtitle:
        font_sub = _load_font(36, italic=True)
        sub_lines = _wrap_text(draw, work_subtitle, font_sub, max_width=W - 380)
        for sline in sub_lines[:4]:
            sb = draw.textbbox((0, 0), sline, font=font_sub)
            sw = sb[2] - sb[0]
            sh = sb[3] - sb[1]
            draw.text(((W - sw) // 2, curr_y), sline, font=font_sub, fill=palette.subtitle_color)
            curr_y += int(sh * 1.38)

    # 7. Centerpiece Heraldic / Geometric Medallion
    medallion_cy = max(curr_y + 310, 1480)
    medallion_cy = min(medallion_cy, 1660)
    bg_center = palette.card_bg if palette.card_bg is not None else palette.bg_bottom
    _draw_emblem(
        draw,
        cx=W // 2,
        cy=medallion_cy,
        radius=245,
        style=palette.emblem_style,
        primary=palette.primary_accent,
        secondary=palette.secondary_accent,
        bg_fill=bg_center,
    )

    # 8. Author / Attribution Block near bottom
    authors_str = " • ".join(work.authors[:4])
    if len(work.authors) > 4:
        authors_str += " • et al."
    font_author = _load_font(34, bold=False)
    author_lines = _wrap_text(draw, authors_str, font_author, max_width=W - 360)
    auth_y = 2070
    for aline in author_lines[:2]:
        ab = draw.textbbox((0, 0), aline, font=font_author)
        aw = ab[2] - ab[0]
        draw.text(((W - aw) // 2, auth_y), aline, font=font_author, fill=palette.title_color)
        auth_y += 48

    # 9. Footer Colophon ("PROTEUS PRESS • KINDLE ENHANCED TYPESETTING")
    draw.line((260, 2275, W - 260, 2275), fill=palette.secondary_accent, width=2)
    font_colophon = _load_font(26, bold=True)
    colophon = "PROTEUS SCRIPTORIUM PRESS"
    cb = draw.textbbox((0, 0), colophon, font=font_colophon)
    cw = cb[2] - cb[0]
    draw.text(((W - cw) // 2, 2320), colophon, font=font_colophon, fill=palette.primary_accent)

    font_subcol = _load_font(22, italic=True)
    subcol = "Kindle Paperwhite Enhanced Typesetting Edition"
    scb = draw.textbbox((0, 0), subcol, font=font_subcol)
    scw = scb[2] - scb[0]
    draw.text(((W - scw) // 2, 2362), subcol, font=font_subcol, fill=palette.subtitle_color)

    # Downsample to 1200×1920 with Lanczos filter
    final_img = img.resize((1200, 1920), resample=Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    final_img.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()

    if save_copy_dir is not None:
        save_copy_dir.mkdir(parents=True, exist_ok=True)
        (save_copy_dir / f"{work.id}.png").write_bytes(png_bytes)

    return png_bytes

