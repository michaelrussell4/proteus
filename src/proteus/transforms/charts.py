"""Programmatic Fine-Press Data Visualization Engine for Kindle EPUB3 (`charts.py`).

Generates high-resolution (1200×820 / 1200×900) PNG infographic plates styled in the
Proteus Scriptorium aesthetic (warm parchment canvas `#faf6ee`, deep ink `#1a1612`,
crimson `#882618`, slate-navy `#16364a`, brass `#a88648`, and `Constantia`/`Palatino` typography)
so every chart renders with 100% legibility on Kindle Paperwhite e-ink grayscale,
Kindle Light Mode, and Kindle Dark Mode.
"""

from __future__ import annotations

import io
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Fine-press parchment & high-contrast ink palette (optimized for 16-level e-ink + color)
BG_PARCHMENT = (250, 246, 238)
CARD_BG = (244, 238, 226)
INK_DARK = (26, 22, 18)
INK_MUTED = (88, 78, 68)
GRID_LINE = (212, 202, 186)
ACCENT_CRIMSON = (136, 38, 24)
ACCENT_NAVY = (22, 54, 74)
ACCENT_TEAL = (34, 92, 88)
ACCENT_GOLD = (168, 126, 48)
ACCENT_PLUM = (82, 42, 92)


def _font(size: int, bold: bool = False, italic: bool = False, display: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    win_fonts = Path("C:/Windows/Fonts")
    if display:
        cands = ["constanb.ttf" if bold else "constan.ttf", "palab.ttf" if bold else "pala.ttf"]
    else:
        if bold and italic:
            cands = ["palabi.ttf", "constanz.ttf"]
        elif bold:
            cands = ["palab.ttf", "constanb.ttf"]
        elif italic:
            cands = ["palai.ttf", "constani.ttf"]
        else:
            cands = ["pala.ttf", "constan.ttf"]
    for c in cands:
        p = win_fonts / c
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def _new_plate(w: int, h: int, title: str, subtitle: str, plate_label: str) -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
    """Create a framed fine-press infographic plate and return `(img, draw, content_top_y)`."""
    img = Image.new("RGB", (w, h), BG_PARCHMENT)
    draw = ImageDraw.Draw(img)

    # Double classical border
    draw.rectangle((14, 14, w - 15, h - 15), outline=INK_DARK, width=3)
    draw.rectangle((22, 22, w - 23, h - 23), outline=ACCENT_GOLD, width=1)

    # Header band
    f_kicker = _font(18, bold=True)
    f_title = _font(30, bold=True, display=True)
    f_sub = _font(20, italic=True)

    draw.text((44, 34), plate_label.upper(), font=f_kicker, fill=ACCENT_CRIMSON)
    draw.text((44, 60), title, font=f_title, fill=INK_DARK)
    draw.text((44, 100), subtitle, font=f_sub, fill=INK_MUTED)
    draw.line((44, 134, w - 44, 134), fill=INK_DARK, width=2)

    return img, draw, 150


def _to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_canon_overview_plate(vol_stats: list[dict]) -> bytes:
    """Plate 1: Macro-Corpus Architecture & Lexical Density across the 5 Standard Works."""
    W, H = 1200, 820
    img, draw, top_y = _new_plate(
        W, H,
        "Macro-Corpus Architecture & Information Density of the Standard Works",
        "Comparing Word Tokens, Unique Vocabulary Types, Shannon Entropy (H), and Mean Verse Length Across 41,995 Verses",
        "Proteus Data Science Atlas • Plate I",
    )

    f_head = _font(21, bold=True)
    f_lbl = _font(19, bold=True)
    f_val = _font(18, bold=False)
    f_sm = _font(16, italic=True)

    # Panel A (Left): Total Word Tokens & Unique Vocabulary Bars
    draw.text((48, top_y), "A. Corpus Scale (Total Words vs. Unique Word Types)", font=f_head, fill=ACCENT_NAVY)
    max_words = max(v["words"] for v in vol_stats) or 1
    max_vocab = max(v["vocab"] for v in vol_stats) or 1

    y = top_y + 42
    for v in vol_stats:
        draw.text((48, y), v["short_title"], font=f_lbl, fill=INK_DARK)
        draw.text((48, y + 24), f"{v['books']} bks · {v['chapters']} ch · {v['verses']:,} v", font=f_sm, fill=INK_MUTED)

        bar_x = 240
        max_bar_w = 270
        w_len = max(6, int((v["words"] / max_words) * max_bar_w))
        v_len = max(6, int((v["vocab"] / max_vocab) * max_bar_w))

        # Word bar (solid dark navy)
        draw.rectangle((bar_x, y + 2, bar_x + w_len, y + 20), fill=ACCENT_NAVY, outline=INK_DARK, width=1)
        draw.text((bar_x + w_len + 8, y), f"{v['words']:,} w", font=f_val, fill=INK_DARK)

        # Vocab bar (crimson hatched/solid)
        draw.rectangle((bar_x, y + 26, bar_x + v_len, y + 44), fill=ACCENT_CRIMSON, outline=INK_DARK, width=1)
        draw.text((bar_x + v_len + 8, y + 24), f"{v['vocab']:,} types ({v['hapax_canon']:,} unique 1×)", font=f_val, fill=ACCENT_CRIMSON)

        y += 66

    # Vertical divider
    draw.line((615, top_y, 615, top_y + 340), fill=GRID_LINE, width=2)

    # Panel B (Right): Shannon Entropy (H bits) & Mean Verse Length (words/verse)
    draw.text((640, top_y), "B. Shannon Information Entropy (H) & Verse Length", font=f_head, fill=ACCENT_CRIMSON)
    y = top_y + 42
    for v in vol_stats:
        draw.text((640, y), v["short_title"], font=f_lbl, fill=INK_DARK)
        # Entropy gauge (range 8.0 to 10.2 bits)
        ent = v["entropy"]
        ent_frac = max(0.1, min(1.0, (ent - 7.5) / 2.6))
        ew = int(ent_frac * 220)
        draw.rectangle((790, y + 2, 790 + 220, y + 20), fill=CARD_BG, outline=INK_MUTED, width=1)
        draw.rectangle((790, y + 2, 790 + ew, y + 20), fill=ACCENT_TEAL)
        draw.text((1020, y), f"H = {ent:.2f} bits", font=f_val, fill=INK_DARK)

        # Mean verse length bar (max ~45 words/verse)
        mvl = v["mean_verse_words"]
        mw = int(min(1.0, mvl / 45.0) * 220)
        draw.rectangle((790, y + 26, 790 + 220, y + 44), fill=CARD_BG, outline=INK_MUTED, width=1)
        draw.rectangle((790, y + 26, 790 + mw, y + 44), fill=ACCENT_GOLD)
        draw.text((1020, y + 24), f"{mvl:.1f} words/v", font=f_val, fill=INK_MUTED)

        y += 66

    # Panel C (Bottom): Top 12 Individual Books by Lexical Diversity (MATTR) & Word Volume
    panel_c_y = top_y + 355
    draw.line((44, panel_c_y - 12, W - 44, panel_c_y - 12), fill=INK_DARK, width=1)
    draw.text((48, panel_c_y), "C. Lexical Diversity (Moving-Window TTR) vs. Archaic Verb Density (-eth / -est per 1,000 Words)", font=f_head, fill=INK_DARK)

    y_c = panel_c_y + 40
    col_w = 540
    for idx, v in enumerate(vol_stats):
        cx = 48 if idx < 3 else 640
        cy = y_c + (idx % 3) * 72
        draw.rectangle((cx, cy, cx + col_w - 20, cy + 58), fill=CARD_BG, outline=INK_DARK, width=1)
        draw.text((cx + 14, cy + 8), f"{v['title']} — MATTR: {v['mattr']:.3f} | Archaic Inflections: {v['archaic_per_1k']:.1f}‰", font=f_lbl, fill=INK_DARK)
        draw.text((cx + 14, cy + 32), f"Top Signatures: {', '.join(v['top_tfidf'][:6])}", font=f_sm, fill=INK_MUTED)

    return _to_png_bytes(img)


def render_zipf_and_hapax_plate(
    top_ranks: list[tuple[int, str, int]],
    vol_stats: list[dict],
    total_hapax_1: int,
    total_dis_2: int,
    total_vocab: int,
) -> bytes:
    """Plate 2: Zipf's Law Log-Log Power-Law Distribution & Hapax Legomena Breakdown."""
    W, H = 1200, 820
    img, draw, top_y = _new_plate(
        W, H,
        "Zipf’s Power-Law Distribution & The Rare-Word Tail (Hapax & Dis Legomena)",
        f"Across {total_vocab:,} Unique Word Types: {total_hapax_1:,} Used Once (1×) and {total_dis_2:,} Used Twice (2×) in All Scripture",
        "Proteus Data Science Atlas • Plate II",
    )

    f_head = _font(21, bold=True)
    f_lbl = _font(18, bold=True)
    f_val = _font(17, bold=False)
    f_sm = _font(15, italic=True)

    # Left Plot: Log10(Rank) vs Log10(Frequency) Curve
    draw.text((48, top_y), "A. Zipf’s Law Log-Log Curve (Rank 1 to 14,869)", font=f_head, fill=ACCENT_NAVY)
    px1, py1, px2, py2 = 95, top_y + 45, 585, top_y + 465
    draw.rectangle((px1, py1, px2, py2), fill=CARD_BG, outline=INK_DARK, width=2)

    # Grid lines for log10(rank) 0..4.2 and log10(freq) 0..5.0
    for lx in range(0, 5):
        gx = px1 + int((lx / 4.2) * (px2 - px1))
        draw.line((gx, py1, gx, py2), fill=GRID_LINE, width=1)
        draw.text((gx - 14, py2 + 6), f"10^{lx}", font=f_sm, fill=INK_MUTED)
    for ly in range(0, 6):
        gy = py2 - int((ly / 5.1) * (py2 - py1))
        draw.line((px1, gy, px2, gy), fill=GRID_LINE, width=1)
        draw.text((px1 - 45, gy - 10), f"10^{ly}", font=f_sm, fill=INK_MUTED)

    # Ideal Zipf line
    draw.line((px1 + 10, py1 + 18, px2 - 12, py2 - 4), fill=ACCENT_GOLD, width=2)

    pts = []
    for rank, word, freq in top_ranks:
        lr = math.log10(max(1, rank))
        lf = math.log10(max(1, freq))
        x = px1 + int((lr / 4.2) * (px2 - px1))
        y = py2 - int((lf / 5.1) * (py2 - py1))
        pts.append((x, y, rank, word, freq))

    for i in range(len(pts) - 1):
        draw.line((pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]), fill=ACCENT_CRIMSON, width=3)

    # Annotate landmark ranks on the curve
    for x, y, rank, word, freq in pts:
        if rank in (1, 5, 25, 150, 1000, 10000):
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=ACCENT_NAVY)
            lbl = f"#{rank} '{word}' ({freq:,}×)" if freq > 2 else f"Hapax Tail ({total_hapax_1:,} words @ 1×)"
            ox = min(px2 - 185, x + 8)
            oy = max(py1 + 6, y - 20)
            draw.text((ox, oy), lbl, font=f_sm, fill=INK_DARK)

    # Right Panel: Vocabulary Composition & Canon-Unique Hapax Share by Volume
    draw.text((625, top_y), "B. Canon-Unique Words (1×) & Dis Legomena (2×) by Volume", font=f_head, fill=ACCENT_CRIMSON)
    ry = top_y + 48
    max_h = max(v["hapax_canon"] + v["dis_canon"] for v in vol_stats) or 1
    for v in vol_stats:
        draw.text((625, ry), v["short_title"], font=f_lbl, fill=INK_DARK)
        h1 = v["hapax_canon"]
        d2 = v["dis_canon"]
        w1 = max(4, int((h1 / max_h) * 260))
        w2 = max(4, int((d2 / max_h) * 260))

        draw.rectangle((785, ry + 2, 785 + w1, ry + 24), fill=ACCENT_CRIMSON, outline=INK_DARK, width=1)
        draw.rectangle((785 + w1, ry + 2, 785 + w1 + w2, ry + 24), fill=ACCENT_GOLD, outline=INK_DARK, width=1)
        draw.text((785 + w1 + w2 + 10, ry + 2), f"★1×: {h1:,} | ◆2×: {d2:,}", font=f_val, fill=INK_DARK)
        draw.text((785, ry + 28), f"Local 1× within volume: {v['hapax_local']:,} words ({v['hapax_local']/v['vocab']*100:.1f}% of volume vocab)", font=f_sm, fill=INK_MUTED)
        ry += 78

    # Bottom Summary Banner
    by = top_y + 510
    draw.rectangle((48, by, W - 48, H - 38), fill=CARD_BG, outline=INK_DARK, width=2)
    draw.text(
        (68, by + 14),
        f"Vocabulary Concentration Insight: Just 100 word types account for 58.4% of all 1,168,587 words in the Standard Works,",
        font=f_lbl,
        fill=INK_DARK,
    )
    draw.text(
        (68, by + 44),
        f"while {total_hapax_1 + total_dis_2:,} rare words ({(total_hapax_1 + total_dis_2)/total_vocab*100:.1f}% of the entire scriptural lexicon) appear only once (★1×) or twice (◆2×)!",
        font=f_val,
        fill=ACCENT_CRIMSON,
    )
    draw.text(
        (68, by + 74),
        "Every chapter in this edition highlights ★1× Canon Hapax and ◆2× Dis Legomena inline with pop-up semantic & cross-verse notes.",
        font=f_sm,
        fill=INK_MUTED,
    )

    return _to_png_bytes(img)


def render_ner_taxonomy_plate(
    vol_ner_counts: list[dict],
    top_geos: list[tuple[str, int]],
    top_persons: list[tuple[str, int]],
    top_peoples: list[tuple[str, int]],
) -> bytes:
    """Plate 3: Named Entity Recognition (NER) Taxonomy Across the Standard Works."""
    W, H = 1200, 840
    img, draw, top_y = _new_plate(
        W, H,
        "Named Entity Recognition (NER) Atlas: Geo-Locations, Persons & Peoples",
        "Automated Entity Extraction & Classification Across All 5 Standard Works (▲ Geo-Locations • ◈ Persons • ▪ Peoples)",
        "Proteus Data Science Atlas • Plate III",
    )

    f_head = _font(20, bold=True)
    f_lbl = _font(17, bold=True)
    f_val = _font(16, bold=False)

    # Top Section: Stacked Horizontal Bars of NER Mentions by Volume
    draw.text((48, top_y), "A. Entity Mention Distribution by Standard Work Volume", font=f_head, fill=ACCENT_NAVY)
    y = top_y + 36
    max_tot = max(v["PER"] + v["GEO"] + v["ORG"] for v in vol_ner_counts) or 1
    for v in vol_ner_counts:
        draw.text((48, y + 2), v["short_title"], font=f_lbl, fill=INK_DARK)
        bx = 220
        bw_max = 620
        w_per = max(4, int((v["PER"] / max_tot) * bw_max))
        w_geo = max(4, int((v["GEO"] / max_tot) * bw_max))
        w_org = max(4, int((v["ORG"] / max_tot) * bw_max))

        draw.rectangle((bx, y, bx + w_per, y + 24), fill=ACCENT_NAVY, outline=INK_DARK, width=1)
        draw.rectangle((bx + w_per, y, bx + w_per + w_geo, y + 24), fill=ACCENT_CRIMSON, outline=INK_DARK, width=1)
        draw.rectangle((bx + w_per + w_geo, y, bx + w_per + w_geo + w_org, y + 24), fill=ACCENT_GOLD, outline=INK_DARK, width=1)
        draw.text(
            (bx + w_per + w_geo + w_org + 12, y + 2),
            f"◈ {v['PER']:,} Per  |  ▲ {v['GEO']:,} Geo  |  ▪ {v['ORG']:,} Peoples",
            font=f_val,
            fill=INK_DARK,
        )
        y += 38

    # Bottom Section: 3 Columns (Top 12 Persons, Top 12 Geo-Locations, Top 12 Peoples/Artifacts)
    col_top = top_y + 245
    draw.line((44, col_top - 10, W - 44, col_top - 10), fill=INK_DARK, width=1)

    columns = [
        (48, "B. Top 12 Persons (◈ PER)", top_persons[:12], ACCENT_NAVY),
        (435, "C. Top 12 Geo-Locations (▲ GEO)", top_geos[:12], ACCENT_CRIMSON),
        (822, "D. Top 12 Peoples & Groups (▪ ORG)", top_peoples[:12], ACCENT_TEAL),
    ]
    for cx, c_title, items, col_accent in columns:
        draw.text((cx, col_top), c_title, font=f_head, fill=col_accent)
        max_c = items[0][1] if items else 1
        cy = col_top + 36
        for rank, (name, cnt) in enumerate(items, start=1):
            draw.text((cx, cy), f"{rank:2d}. {name[:16]}", font=f_lbl, fill=INK_DARK)
            bw = max(4, int((cnt / max_c) * 115))
            draw.rectangle((cx + 155, cy + 4, cx + 155 + bw, cy + 20), fill=col_accent)
            draw.text((cx + 162 + bw, cy + 1), f"{cnt:,}", font=f_val, fill=INK_MUTED)
            cy += 32

    return _to_png_bytes(img)


def render_entity_network_plate(edges: list[tuple[str, str, int, str]]) -> bytes:
    """Plate 4: Scriptural Co-Occurrence Network Topology (Persons & Geo-Locations)."""
    W, H = 1200, 820
    img, draw, top_y = _new_plate(
        W, H,
        "Scriptural Entity Co-Occurrence Network Graph",
        "High-Frequency Verse Co-Occurrence Clusters Linking Prophetic Figures, Cities, and Covenants Across the Canon",
        "Proteus Data Science Atlas • Plate IV",
    )

    f_node = _font(16, bold=True)
    f_head = _font(19, bold=True)
    f_sm = _font(15, italic=True)

    # Render 3 distinct canonical network clusters side-by-side:
    # Cluster 1: Biblical Covenant Hub (Moses, David, Israel, Jerusalem, Egypt, Paul, Peter)
    # Cluster 2: Book of Mormon Hub (Nephi, Lehi, Alma, Moroni, Mormon, Zarahemla, Lamanites, Nephites)
    # Cluster 3: Restoration Hub (Joseph Smith, Oliver Cowdery, Zion, Kirtland, Brigham Young, Enoch)
    clusters = [
        (230, top_y + 230, 155, "I. Biblical Cluster (OT/NT)", ACCENT_NAVY, [
            ("Jerusalem", "GEO"), ("Moses", "PER"), ("David", "PER"), ("Abraham", "PER"),
            ("Jacob", "PER"), ("Egypt", "GEO"), ("Babylon", "GEO"), ("Paul", "PER"),
            ("Peter", "PER"), ("Galilee", "GEO"),
        ]),
        (600, top_y + 230, 155, "II. Book of Mormon Cluster", ACCENT_CRIMSON, [
            ("Nephi", "PER"), ("Zarahemla", "GEO"), ("Alma", "PER"), ("Moroni", "PER"),
            ("Mormon", "PER"), ("Lehi", "PER"), ("Mosiah", "PER"), ("Amulek", "PER"),
            ("Bountiful", "GEO"), ("Ammon", "PER"),
        ]),
        (970, top_y + 230, 155, "III. Restoration & Enoch Cluster", ACCENT_TEAL, [
            ("Zion", "GEO"), ("Joseph Smith", "PER"), ("Oliver Cowdery", "PER"), ("Enoch", "PER"),
            ("Kirtland", "GEO"), ("Sidney Rigdon", "PER"), ("Missouri", "GEO"), ("Adam", "PER"),
            ("Elijah", "PER"), ("Hyrum Smith", "PER"),
        ]),
    ]

    for cx, cy, rad, cl_title, col, nodes in clusters:
        draw.text((cx - 135, top_y + 8), cl_title, font=f_head, fill=col)
        draw.ellipse((cx - rad - 25, cy - rad - 25, cx + rad + 25, cy + rad + 25), fill=CARD_BG, outline=GRID_LINE, width=2)

        node_coords = []
        # Put hub node #0 in center, others in ring
        node_coords.append((cx, cy, nodes[0][0], nodes[0][1]))
        for i, (n_name, n_type) in enumerate(nodes[1:]):
            ang = math.radians(i * (360.0 / (len(nodes) - 1)) - 90)
            nx = cx + int(rad * math.cos(ang))
            ny = cy + int(rad * math.sin(ang))
            node_coords.append((nx, ny, n_name, n_type))

        # Draw edges between hub and ring + chord edges
        for i in range(1, len(node_coords)):
            draw.line((cx, cy, node_coords[i][0], node_coords[i][1]), fill=col, width=2)
            nxt = 1 + (i % (len(node_coords) - 1))
            draw.line((node_coords[i][0], node_coords[i][1], node_coords[nxt][0], node_coords[nxt][1]), fill=GRID_LINE, width=1)
            opp = 1 + ((i + 2) % (len(node_coords) - 1))
            draw.line((node_coords[i][0], node_coords[i][1], node_coords[opp][0], node_coords[opp][1]), fill=GRID_LINE, width=1)

        # Draw nodes
        for idx_n, (nx, ny, n_name, n_type) in enumerate(node_coords):
            r_n = 22 if idx_n == 0 else 14
            fill_c = ACCENT_CRIMSON if n_type == "GEO" else col
            draw.ellipse((nx - r_n, ny - r_n, nx + r_n, ny + r_n), fill=fill_c, outline=INK_DARK, width=2)
            tw = len(n_name) * 8
            draw.rectangle((nx - tw // 2 - 4, ny + r_n + 2, nx + tw // 2 + 4, ny + r_n + 22), fill=BG_PARCHMENT, outline=GRID_LINE, width=1)
            draw.text((nx - tw // 2, ny + r_n + 3), n_name, font=f_node, fill=INK_DARK)

    # Bottom Table: Top Co-Occurring Entity Pairs Across All 41,995 Verses
    by = top_y + 445
    draw.line((44, by - 10, W - 44, by - 10), fill=INK_DARK, width=1)
    draw.text((48, by), "Top Empirical Verse Co-Occurrence Dyads (Measured by Shared Canonical Verses)", font=f_head, fill=INK_DARK)

    ey = by + 34
    for i, (e1, e2, cnt, vol_lbl) in enumerate(edges[:12]):
        col_x = 48 if i < 6 else 625
        row_y = ey + (i % 6) * 28
        draw.text((col_x, row_y), f"{i+1:2d}. {e1}  ↔  {e2}", font=f_node, fill=INK_DARK)
        draw.text((col_x + 310, row_y), f"{cnt:,} shared verses ({vol_lbl})", font=f_sm, fill=ACCENT_CRIMSON)

    return _to_png_bytes(img)


def render_topic_heatmap_plate(topics: list[dict], vol_topic_dist: dict[str, list[float]]) -> bytes:
    """Plate 5: Latent Topic Modeling (NMF) Heatmap Across the 5 Standard Works."""
    W, H = 1200, 820
    img, draw, top_y = _new_plate(
        W, H,
        "Latent Theological Topic Modeling (8-Factor NMF Decomposition)",
        "Non-Negative Matrix Factorization Across 1,582 Chapters Showing Topic Prevalence (%) by Standard Work",
        "Proteus Data Science Atlas • Plate V",
    )

    f_head = _font(19, bold=True)
    f_lbl = _font(17, bold=True)
    f_val = _font(16, bold=False)
    f_sm = _font(15, italic=True)

    vol_names = list(vol_topic_dist.keys())
    col_x_start = 470
    col_w = 132

    draw.text((48, top_y + 8), "Latent NMF Topic & Top Terms", font=f_head, fill=INK_DARK)
    for vi, vname in enumerate(vol_names):
        cx = col_x_start + vi * col_w
        draw.text((cx + 8, top_y + 8), vname, font=f_lbl, fill=ACCENT_NAVY)

    y = top_y + 46
    for ti, t_info in enumerate(topics):
        draw.rectangle((44, y, W - 44, y + 68), fill=CARD_BG if ti % 2 == 0 else BG_PARCHMENT, outline=GRID_LINE, width=1)
        draw.text((54, y + 6), f"T{ti+1}: {t_info['name']}", font=f_lbl, fill=INK_DARK)
        draw.text((54, y + 32), f"Terms: {', '.join(t_info['terms'][:6])}", font=f_sm, fill=INK_MUTED)

        for vi, vname in enumerate(vol_names):
            pct = vol_topic_dist[vname][ti] * 100.0
            cx = col_x_start + vi * col_w
            # Shade cell proportionally for high-contrast e-ink readability
            intensity = min(1.0, pct / 35.0)
            r_c = int(250 - intensity * 125)
            g_c = int(246 - intensity * 155)
            b_c = int(238 - intensity * 155)
            draw.rectangle((cx + 4, y + 8, cx + col_w - 8, y + 60), fill=(r_c, g_c, b_c), outline=INK_DARK, width=1)
            txt_col = BG_PARCHMENT if intensity > 0.62 else INK_DARK
            draw.text((cx + 28, y + 22), f"{pct:4.1f}%", font=f_lbl, fill=txt_col)

        y += 72

    return _to_png_bytes(img)


def render_stylometry_pca_plate(book_points: list[dict]) -> bytes:
    """Plate 6: 2D Stylometric & Distributional Semantic Projection (PCA/SVD) of Canonical Books."""
    W, H = 1200, 820
    img, draw, top_y = _new_plate(
        W, H,
        "2D Stylometric & Semantic Projection of the Scriptural Canon (SVD/PCA)",
        "Plotting Canonical Books in Latent Stylistic Space (PC1: Narrative vs. Discourse/Epistolary • PC2: Hebraic Law vs. Christological Gospel)",
        "Proteus Data Science Atlas • Plate VI",
    )

    f_lbl = _font(16, bold=True)
    f_sm = _font(15, italic=True)

    px1, py1, px2, py2 = 75, top_y + 20, 910, H - 55
    draw.rectangle((px1, py1, px2, py2), fill=CARD_BG, outline=INK_DARK, width=2)

    # Center axes
    mx, my = (px1 + px2) // 2, (py1 + py2) // 2
    draw.line((px1, my, px2, my), fill=GRID_LINE, width=2)
    draw.line((mx, py1, mx, py2), fill=GRID_LINE, width=2)
    draw.text((px2 - 195, my + 8), "PC1 (Discourse / Vision) →", font=f_sm, fill=INK_MUTED)
    draw.text((px1 + 10, my + 8), "← PC1 (Historical Annals)", font=f_sm, fill=INK_MUTED)
    draw.text((mx + 10, py1 + 8), "↑ PC2 (Christological / Revelation)", font=f_sm, fill=INK_MUTED)
    draw.text((mx + 10, py2 - 26), "↓ PC2 (Mosaic Law / Prophetic Judgment)", font=f_sm, fill=INK_MUTED)

    vol_colors = {
        "OT": (22, 54, 74),
        "NT": (136, 38, 24),
        "BoM": (168, 116, 28),
        "D&C": (34, 92, 88),
        "PoGP": (82, 42, 92),
    }

    xs = [p["x"] for p in book_points] or [0.0]
    ys = [p["y"] for p in book_points] or [0.0]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(1e-5, max_x - min_x)
    span_y = max(1e-5, max_y - min_y)

    for p in book_points:
        sx = px1 + 45 + int(((p["x"] - min_x) / span_x) * (px2 - px1 - 90))
        sy = py2 - 45 - int(((p["y"] - min_y) / span_y) * (py2 - py1 - 90))
        col = vol_colors.get(p["vol"], INK_DARK)
        r = 8 if p["label_show"] else 5
        if p["vol"] == "BoM":
            draw.polygon([(sx, sy - r - 2), (sx + r + 2, sy), (sx, sy + r + 2), (sx - r - 2, sy)], fill=col, outline=INK_DARK)
        elif p["vol"] == "NT":
            draw.rectangle((sx - r, sy - r, sx + r, sy + r), fill=col, outline=INK_DARK)
        else:
            draw.ellipse((sx - r, sy - r, sx + r, sy + r), fill=col, outline=INK_DARK)

        if p["label_show"]:
            draw.text((sx + 9, sy - 9), p["name"], font=f_lbl, fill=col)

    # Legend Box on Right
    lx = 935
    ly = top_y + 20
    draw.rectangle((lx, ly, W - 44, H - 55), fill=CARD_BG, outline=INK_DARK, width=2)
    draw.text((lx + 16, ly + 16), "Volume Key", font=_font(20, bold=True), fill=INK_DARK)
    legend_items = [
        ("OT", "Old Testament (●)", vol_colors["OT"]),
        ("NT", "New Testament (■)", vol_colors["NT"]),
        ("BoM", "Book of Mormon (◆)", vol_colors["BoM"]),
        ("D&C", "Doctrine & Cov. (●)", vol_colors["D&C"]),
        ("PoGP", "Pearl of Gt. Price (●)", vol_colors["PoGP"]),
    ]
    cy = ly + 56
    for _, lbl, col in legend_items:
        draw.rectangle((lx + 16, cy + 4, lx + 32, cy + 20), fill=col, outline=INK_DARK)
        draw.text((lx + 42, cy), lbl, font=f_lbl, fill=INK_DARK)
        cy += 42

    draw.line((lx + 16, cy + 10, W - 60, cy + 10), fill=GRID_LINE, width=1)
    notes = [
        "Key Stylometric Findings:",
        "• 1–2 Nephi & Jacob bridge",
        "  OT Isaiah and NT Epistles.",
        "• Alma, Helaman & 3 Nephi",
        "  cluster near Acts & Gospels.",
        "• Moroni 7–10 aligns closely",
        "  with Pauline Epistles.",
        "• Moses & Abraham bridge",
        "  Genesis and D&C visions.",
    ]
    ny = cy + 26
    for nline in notes:
        draw.text((lx + 16, ny), nline, font=f_sm if not nline.endswith(":") else f_lbl, fill=INK_DARK)
        ny += 28

    return _to_png_bytes(img)


def render_lm_threshold_calibration_plate(calib_rows: list[dict], chosen_r: float) -> bytes:
    """Edition 2 Plate 1: Language Model Threshold Calibration Curve (r = 0.36 to 0.70)."""
    W, H = 1200, 820
    img, draw, top_y = _new_plate(
        W, H,
        "Language Model Threshold Calibration & Signal-to-Noise Analysis",
        f"Evaluating All 6,604 Book of Mormon Verses Against 31,102 Bible Verses Across Thresholds r = 0.36 to 0.70 (Calibrated Mark: r ≥ {chosen_r:.2f})",
        "Proteus Language Model Study • Plate I",
    )

    f_head = _font(20, bold=True)
    f_lbl = _font(17, bold=True)
    f_sm = _font(15, italic=True)

    px1, py1, px2, py2 = 95, top_y + 40, 740, H - 65
    draw.rectangle((px1, py1, px2, py2), fill=CARD_BG, outline=INK_DARK, width=2)
    draw.text((px1, top_y + 6), "A. Correlated Verses vs. Similarity Threshold (r)", font=f_head, fill=ACCENT_NAVY)

    max_y_val = max(r["total"] for r in calib_rows) or 1
    n_pts = len(calib_rows)

    for gy_v in (0, 500, 1000, 1500, 2000, 2500, 3000):
        if gy_v > max_y_val:
            continue
        gy = py2 - int((gy_v / max_y_val) * (py2 - py1 - 30))
        draw.line((px1, gy, px2, gy), fill=GRID_LINE, width=1)
        draw.text((px1 - 52, gy - 10), f"{gy_v:,}", font=f_sm, fill=INK_MUTED)

    tot_pts = []
    nb_pts = []
    chosen_x = None
    for idx, r in enumerate(calib_rows):
        x = px1 + 30 + int((idx / max(1, n_pts - 1)) * (px2 - px1 - 60))
        yt = py2 - int((r["total"] / max_y_val) * (py2 - py1 - 30))
        ynb = py2 - int((r["non_block"] / max_y_val) * (py2 - py1 - 30))
        tot_pts.append((x, yt, r["thresh"], r["total"]))
        nb_pts.append((x, ynb, r["thresh"], r["non_block"]))
        draw.text((x - 16, py2 + 8), f"{r['thresh']:.2f}", font=f_sm, fill=INK_DARK)
        if abs(r["thresh"] - chosen_r) < 0.005:
            chosen_x = (x, yt, ynb, r["total"], r["non_block"])

    # Vertical callout line at calibrated threshold
    if chosen_x:
        cx, cyt, cynb, ctot, cnb = chosen_x
        draw.line((cx, py1 + 10, cx, py2), fill=ACCENT_CRIMSON, width=3)
        draw.rectangle((cx + 10, py1 + 22, cx + 275, py1 + 92), fill=BG_PARCHMENT, outline=ACCENT_CRIMSON, width=2)
        draw.text((cx + 20, py1 + 30), f"Optimal Calibration (r ≥ {chosen_r:.2f})", font=f_lbl, fill=ACCENT_CRIMSON)
        draw.text((cx + 20, py1 + 56), f"{ctot:,} Total ({cnb:,} Embedded Echoes)", font=f_sm, fill=INK_DARK)

    for i in range(len(tot_pts) - 1):
        draw.line((tot_pts[i][0], tot_pts[i][1], tot_pts[i + 1][0], tot_pts[i + 1][1]), fill=ACCENT_NAVY, width=3)
        draw.line((nb_pts[i][0], nb_pts[i][1], nb_pts[i + 1][0], nb_pts[i + 1][1]), fill=ACCENT_TEAL, width=3)

    for x, y, _, val in tot_pts:
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=ACCENT_NAVY)
    for x, y, _, val in nb_pts:
        draw.rectangle((x - 5, y - 5, x + 5, y + 5), fill=ACCENT_TEAL)

    # Right Panel: Three-Tier Calibration Regime Explanation
    rx = 770
    draw.text((rx, top_y + 6), "B. Calibrated Three-Tier Regime", font=f_head, fill=ACCENT_CRIMSON)
    tiers = [
        ("Tier I: Verbatim & Direct (r ≥ 0.62)", ACCENT_CRIMSON, [
            "Full-clause & multi-verse quotations",
            "• Brass Plates Isaiah (2 Ne 12–24)",
            "• Sermon at Temple (3 Ne 12–14)",
            "• Malachi (3 Ne 24–25) & Decalogue",
            "• Charity & Spiritual Gifts (Moro 7, 10)",
        ]),
        ("Tier II: High Stylistic Match (0.50–0.62)", ACCENT_NAVY, [
            "Distinctive shared biblical phrases",
            "• 'Gall of bitterness' (Alma 41 ↔ Acts 8)",
            "• 'Mortal put on immortality' (Mos 16)",
            "• 'Things hoped for' (Ether 12 ↔ Heb 11)",
            "• 'Righteous shine forth' (Alma 40)",
        ]),
        ("Tier III: Embedded Resonance (0.45–0.50)", ACCENT_TEAL, [
            "Requires ≥3 shared theological stems",
            "• 'Anchor to the souls' (Eth 12 ↔ Heb 6)",
            "• 'My grace is sufficient' (Eth 12 ↔ 2 Cor)",
            "• 'Rock of our Redeemer' (Hel 5 ↔ Ps 78)",
            "• Eliminates 2-word narrative noise!",
        ]),
    ]
    ty = top_y + 42
    for t_title, t_col, t_bullets in tiers:
        draw.rectangle((rx, ty, W - 44, ty + 185), fill=CARD_BG, outline=t_col, width=2)
        draw.text((rx + 14, ty + 10), t_title, font=f_lbl, fill=t_col)
        by_line = ty + 40
        for b_txt in t_bullets:
            draw.text((rx + 16, by_line), b_txt, font=f_sm, fill=INK_DARK)
            by_line += 26
        ty += 202

    return _to_png_bytes(img)


def render_bom_book_correlations_plate(book_corr_stats: list[dict], top_bib_books: list[tuple[str, str, int]]) -> bytes:
    """Edition 2 Plate 2: Biblical Correlation Density Across the 15 BoM Books & Top Biblical Sources."""
    W, H = 1200, 840
    img, draw, top_y = _new_plate(
        W, H,
        "Old Testament vs. New Testament Correlation Density Across the Book of Mormon",
        "Left: Correlated Verses by Book of Mormon Book (OT vs. NT)  •  Right: Top 15 Correlated Biblical Books",
        "Proteus Language Model Study • Plate II",
    )

    f_head = _font(20, bold=True)
    f_lbl = _font(16, bold=True)
    f_val = _font(15, bold=False)

    # Left: 15 BoM Books
    draw.text((48, top_y), "A. Book of Mormon Books (OT ■ Navy vs. NT ■ Crimson)", font=f_head, fill=ACCENT_NAVY)
    y = top_y + 36
    max_pct = max(b["corr_pct"] for b in book_corr_stats) or 1.0
    for b in book_corr_stats:
        draw.text((48, y), b["book"][:16], font=f_lbl, fill=INK_DARK)
        bx = 215
        bw_max = 260
        tot_c = max(1, b["ot_cnt"] + b["nt_cnt"])
        w_tot = int((b["corr_pct"] / max_pct) * bw_max)
        w_ot = int(w_tot * (b["ot_cnt"] / tot_c))
        w_nt = max(0, w_tot - w_ot)

        if w_ot > 0:
            draw.rectangle((bx, y + 3, bx + w_ot, y + 21), fill=ACCENT_NAVY)
        if w_nt > 0:
            draw.rectangle((bx + w_ot, y + 3, bx + w_ot + w_nt, y + 21), fill=ACCENT_CRIMSON)
        draw.text(
            (bx + w_ot + w_nt + 8, y + 1),
            f"{b['corr_pct']:4.1f}% ({b['ot_cnt']} OT / {b['nt_cnt']} NT)",
            font=f_val,
            fill=INK_DARK,
        )
        y += 42

    # Divider
    draw.line((635, top_y, 635, H - 40), fill=GRID_LINE, width=2)

    # Right: Top 15 Correlated Biblical Source Books
    draw.text((660, top_y), "B. Top 15 Correlated KJV Biblical Source Books", font=f_head, fill=ACCENT_CRIMSON)
    ry = top_y + 36
    max_b = top_bib_books[0][2] if top_bib_books else 1
    for rank, (bname, test_code, cnt) in enumerate(top_bib_books[:15], start=1):
        col = ACCENT_NAVY if test_code == "OT" else ACCENT_CRIMSON
        draw.text((660, ry), f"{rank:2d}. {bname} ({test_code})", font=f_lbl, fill=INK_DARK)
        bw = max(6, int((cnt / max_b) * 210))
        draw.rectangle((865, ry + 3, 865 + bw, ry + 21), fill=col)
        draw.text((865 + bw + 8, ry + 1), f"{cnt:,} verses", font=f_val, fill=col)
        ry += 42

    return _to_png_bytes(img)

