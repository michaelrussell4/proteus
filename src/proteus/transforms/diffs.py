"""Phase 4 Advanced NLP, Multi-Edition Diffs, Intertextual Parallels & Poetic/Chiastic Structures.

Provides:
1. Historical Textual Variants Book of Mormon (1830–2013) (`build_historical_variants_bom`)
   - Aligns all 8 historical print editions (`1830, 1837, 1840, 1841, 1879, 1920, 1981, 2013`)
     at the word level using `difflib.SequenceMatcher`.
   - Renders inline `<del class="diff-del">` (1830 original reading) and `<ins class="diff-ins">`
     (2013 modern reading) whenever substantive lexical changes occur.
   - Attaches a `[Δ Year]` pop-up variant apparatus (`<aside epub:type="footnote">`) to every
     changed verse detailing the complete 8-edition chronological reading history (including
     1840 Joseph Smith revisions and 1981/2013 reversions).
2. Intertextual Parallels Comparative Reader (`build_intertextual_parallels_edition`)
   - Part I: Book of Mormon Isaiah vs. King James Version Isaiah (`2 Nephi 12–24` vs. `Isaiah 2–14`,
     `1 Nephi 20–21` vs. `Isaiah 48–49`, `2 Nephi 7–8` vs. `Isaiah 50–51`, `Mosiah 14` vs. `Isaiah 53`,
     `3 Nephi 22` vs. `Isaiah 54`).
   - Part II: The Sermon at the Temple vs. The Sermon on the Mount (`3 Nephi 12–14` vs. `Matthew 5–7`).
   - Highlights every word-level departure, italicization shift, and Nephite expansion with inline
     diff styling and pop-up comparative notes.
3. Poetic & Chiasmus Study Edition (`build_poetic_and_chiasmus_bom`)
   - Renders landmark chiastic structures (`Alma 36`, `Mosiah 3:18–19`, `Mosiah 5:10–12`,
     `1 Nephi 1`, `Alma 41:13–15`, `2 Nephi 29:13–14`) and prophetic poetry (`2 Nephi 4:15–35`
     "The Psalm of Nephi", `2 Nephi 9`, `3 Nephi 22`) with indented structural levels (`[A]`, `[B]`, `[C]`... `[C']`, `[B']`, `[A']`)
     and clause-parallel poetic stanzas.
"""

from __future__ import annotations

import difflib
import re
from copy import deepcopy
from pathlib import Path

from proteus.core.models import (
    Annotation,
    AnnotationType,
    BlockType,
    Book,
    Chapter,
    ContentBlock,
    Verse,
    Work,
)
from proteus.core.typography import escape_xhtml
from proteus.ingest.standard_works import (
    HISTORICAL_BOM_YEARS,
    ingest_bom_historical_edition,
    ingest_standard_work,
)


def _tokenize_words_for_diff(text: str) -> list[str]:
    """Split text into word + trailing-punctuation tokens for clean word-level diffs."""
    return re.findall(r"\S+", text)


def _normalize_word_token(tok: str) -> str:
    """Normalize a token by stripping punctuation and lowercasing to test if two tokens differ substantively."""
    return re.sub(r"[^a-z0-9]", "", tok.lower())


def compute_inline_word_diff_xhtml(
    text_a: str,
    text_b: str,
    ignore_pure_punctuation_and_case: bool = True,
) -> tuple[str, int, list[tuple[str, str]]]:
    """Compare `text_a` (baseline, e.g. 1830 or KJV) and `text_b` (comparison, e.g. 2013 or BoM).

    Returns:
        `(xhtml_string, substantive_change_count, list_of_(old_phrase, new_phrase)_pairs)`
    """
    tokens_a = _tokenize_words_for_diff(text_a)
    tokens_b = _tokenize_words_for_diff(text_b)

    if ignore_pure_punctuation_and_case:
        keys_a = [_normalize_word_token(t) for t in tokens_a]
        keys_b = [_normalize_word_token(t) for t in tokens_b]
    else:
        keys_a = tokens_a
        keys_b = tokens_b

    matcher = difflib.SequenceMatcher(None, keys_a, keys_b, autojunk=False)
    out_parts: list[str] = []
    change_count = 0
    diff_pairs: list[tuple[str, str]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            # Use the modern/target tokens for equal spans so punctuation is clean
            span_b = " ".join(tokens_b[j1:j2])
            if span_b:
                out_parts.append(escape_xhtml(span_b, smart_typography=False))
        elif tag == "replace":
            old_str = " ".join(tokens_a[i1:i2])
            new_str = " ".join(tokens_b[j1:j2])
            change_count += 1
            diff_pairs.append((old_str, new_str))
            out_parts.append(
                f'<del class="diff-del">{escape_xhtml(old_str, False)}</del> '
                f'<ins class="diff-ins">{escape_xhtml(new_str, False)}</ins>'
            )
        elif tag == "delete":
            old_str = " ".join(tokens_a[i1:i2])
            change_count += 1
            diff_pairs.append((old_str, "∅"))
            out_parts.append(f'<del class="diff-del">{escape_xhtml(old_str, False)}</del>')
        elif tag == "insert":
            new_str = " ".join(tokens_b[j1:j2])
            change_count += 1
            diff_pairs.append(("∅", new_str))
            out_parts.append(f'<ins class="diff-ins">{escape_xhtml(new_str, False)}</ins>')

    return " ".join(out_parts), change_count, diff_pairs


# ==============================================================================
# 1. Build Target 1: Historical Textual Variants Book of Mormon (1830–2013)
# ==============================================================================

def build_historical_variants_bom(
    raw_dir: Path = Path("data/raw/bom-editions-main/public/data/en"),
) -> Work:
    """Compile The Historical Textual Variants Book of Mormon (1830–2013),
    tracking word-level changes across all 8 historical editions (1830, 1837, 1840, 1841, 1879, 1920, 1981, 2013)
    with inline `<del>`/`<ins>` markers and pop-up chronological variant apparatuses.
    """
    editions_by_year: dict[str, Work] = {
        yr: ingest_bom_historical_edition(yr, raw_dir=raw_dir)
        for yr in HISTORICAL_BOM_YEARS
    }

    # Index all verses across all 8 editions by `(book_id, chapter_num, verse_num)`
    verse_matrix: dict[tuple[str, int, int], dict[str, str]] = {}
    for yr, w in editions_by_year.items():
        for bk in w.books:
            for ch in bk.chapters:
                ch_num = int(ch.number or 1)
                for v in ch.verses:
                    v_num = int(v.verse)
                    verse_matrix.setdefault((bk.id, ch_num, v_num), {})[yr] = v.text

    # Use 2013 as the base structural skeleton
    base_work = deepcopy(editions_by_year["2013"])
    base_work.id = "book-of-mormon-historical-variants"
    base_work.title = "The Book of Mormon (Historical Textual Variants Edition, 1830–2013)"
    base_work.subtitle = "Word-Level Collation Across the 1830, 1837, 1840, 1841, 1879, 1920, 1981, and 2013 Printings"
    base_work.edition_label = "Proteus Critical Textual Apparatus Edition"
    base_work.css_theme = "variants.css"

    legend = Chapter(
        id="bom-variants-apparatus-guide",
        title="Guide to the Historical Variant Apparatus (1830–2013)",
        is_front_matter=True,
        blocks=[
            ContentBlock(
                block_type=BlockType.HEADING,
                text="How to Read the Critical Text & Pop-up Apparatus",
                level=2,
            ),
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text="This critical edition collates eight landmark published editions of the Book of Mormon: 1830 (Palmyra), 1837 (Kirtland), 1840 (Nauvoo), 1841 (Liverpool), 1879 (Salt Lake City / Orson Pratt), 1920 (James E. Talmage committee), 1981, and 2013.",
            ),
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text="Inline Diff Markers: Where the 1830 Palmyra text and the 2013 canonical text differ in wording, the 1830 reading appears in strikethrough and the 2013 reading appears in underlined bold insertion.",
                html_text=(
                    "<strong>1. Inline Diff Markers:</strong> Where the 1830 Palmyra text and the 2013 text differ in wording, "
                    'the 1830 reading is shown as <del class="diff-del">deleted text</del> and the 2013 reading as '
                    '<ins class="diff-ins">inserted text</ins>.'
                ),
            ),
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text="2. Chronological Pop-up Apparatus ([Δ Year]): Any verse that underwent lexical revision across ANY of the eight editions (including intermediate changes in 1837 or 1840 that were later reverted) carries a [Δ Year] pop-up badge showing the first year of divergence. Tap the badge to inspect the complete chronological history across all eight editions.",
            ),
        ],
    )
    base_work.front_matter.insert(0, legend)

    for bk in base_work.books:
        for ch in bk.chapters:
            ch_num = int(ch.number or 1)
            ch_anns: list[Annotation] = []
            var_counter = 0

            for v in ch.verses:
                v_num = int(v.verse)
                yr_readings = verse_matrix.get((bk.id, ch_num, v_num), {})
                text_1830 = yr_readings.get("1830", v.text)
                text_2013 = yr_readings.get("2013", v.text)

                # Group consecutive editions that share identical word tokens (ignoring pure punctuation)
                norm_by_yr = {
                    yr: " ".join(_normalize_word_token(t) for t in _tokenize_words_for_diff(yr_readings.get(yr, "")))
                    for yr in HISTORICAL_BOM_YEARS
                    if yr in yr_readings
                }
                distinct_word_states = len(set(norm_by_yr.values()))

                if distinct_word_states <= 1:
                    continue

                var_counter += 1
                ann_id = f"{ch.id}-var-{var_counter}"

                # Compute inline diff between 1830 and 2013
                diff_xhtml, chg_cnt, diff_pairs = compute_inline_word_diff_xhtml(
                    text_1830, text_2013, ignore_pure_punctuation_and_case=True
                )

                # Find the earliest edition year where a lexical change occurred relative to 1830
                first_change_yr = "1837"
                base_norm = norm_by_yr.get("1830", "")
                for yr in HISTORICAL_BOM_YEARS[1:]:
                    if norm_by_yr.get(yr, base_norm) != base_norm:
                        first_change_yr = yr
                        break

                # Build compact chronological apparatus grouping editions with identical lexical text
                grouped_runs: list[tuple[list[str], str]] = []
                for yr in HISTORICAL_BOM_YEARS:
                    if yr not in yr_readings:
                        continue
                    curr_norm = norm_by_yr[yr]
                    if grouped_runs and norm_by_yr[grouped_runs[-1][0][-1]] == curr_norm:
                        grouped_runs[-1][0].append(yr)
                    else:
                        grouped_runs.append(([yr], yr_readings[yr]))

                apparatus_paras: list[str] = []
                if diff_pairs:
                    pair_summary = "; ".join(f"“{old}” → “{new}”" for old, new in diff_pairs[:6])
                    apparatus_paras.append(f"Key Lexical Shifts (1830 → 2013): {pair_summary}.")
                else:
                    apparatus_paras.append(
                        "Intermediate Edition Variant: The 1830 and 2013 readings agree lexically, "
                        "but an intermediate printing differed."
                    )

                for yrs_list, sample_reading in grouped_runs:
                    yr_label = yrs_list[0] if len(yrs_list) == 1 else f"{yrs_list[0]}–{yrs_list[-1]}"
                    apparatus_paras.append(f"[{yr_label}]: {sample_reading}")

                ch_anns.append(
                    Annotation(
                        id=ann_id,
                        label=f"Δ {first_change_yr}",
                        title=f"{v.citation_label} — Edition Collation (1830–2013)",
                        note_type=AnnotationType.VARIANT,
                        paragraphs=apparatus_paras,
                    )
                )

                base_html = diff_xhtml if chg_cnt > 0 else escape_xhtml(text_2013, smart_typography=False)
                v.html_text = (
                    f"{base_html} "
                    f'<sup class="fn-sup"><a class="noteref var-badge" epub:type="noteref" '
                    f'id="ref-{ann_id}" href="#fn-{ann_id}">[Δ {first_change_yr}]</a></sup>'
                )

            ch.annotations = ch_anns

    return base_work


# ==============================================================================
# 2. Build Target 2: Intertextual Parallels Edition (BoM Isaiah vs KJV; 3 Nephi vs Matthew)
# ==============================================================================

ISAIAH_PARALLELS: list[tuple[str, int, str, int, str]] = [
    ("1 Nephi", 20, "Isaiah", 48, "1 Nephi 20 ↔ Isaiah 48 (Refined in the Furnace of Affliction)"),
    ("1 Nephi", 21, "Isaiah", 49, "1 Nephi 21 ↔ Isaiah 49 (Graven upon the Palms of My Hands)"),
    ("2 Nephi", 7, "Isaiah", 50, "2 Nephi 7 ↔ Isaiah 50 (The Tongue of the Learned)"),
    ("2 Nephi", 8, "Isaiah", 51, "2 Nephi 8 ↔ Isaiah 51 (Look unto the Rock Whence Ye Are Hewn)"),
    ("2 Nephi", 12, "Isaiah", 2, "2 Nephi 12 ↔ Isaiah 2 (The Mountain of the Lord’s House)"),
    ("2 Nephi", 13, "Isaiah", 3, "2 Nephi 13 ↔ Isaiah 3 (Judgments upon Judah and Jerusalem)"),
    ("2 Nephi", 14, "Isaiah", 4, "2 Nephi 14 ↔ Isaiah 4 (A Cloud and Smoke by Day)"),
    ("2 Nephi", 15, "Isaiah", 5, "2 Nephi 15 ↔ Isaiah 5 (Parable of the Vineyard & Six Woes)"),
    ("2 Nephi", 16, "Isaiah", 6, "2 Nephi 16 ↔ Isaiah 6 (Isaiah’s ThroneTheophany: Holy, Holy, Holy)"),
    ("2 Nephi", 17, "Isaiah", 7, "2 Nephi 17 ↔ Isaiah 7 (The Immanuel Prophecy to Ahaz)"),
    ("2 Nephi", 18, "Isaiah", 8, "2 Nephi 18 ↔ Isaiah 8 (Maher-shalal-hash-baz & A Stone of Stumbling)"),
    ("2 Nephi", 19, "Isaiah", 9, "2 Nephi 19 ↔ Isaiah 9 (Unto Us a Child Is Born)"),
    ("2 Nephi", 20, "Isaiah", 10, "2 Nephi 20 ↔ Isaiah 10 (Assyria, the Rod of Mine Anger)"),
    ("2 Nephi", 21, "Isaiah", 11, "2 Nephi 21 ↔ Isaiah 11 (A Rod Out of the Stem of Jesse)"),
    ("2 Nephi", 22, "Isaiah", 12, "2 Nephi 22 ↔ Isaiah 12 (Wells of Salvation)"),
    ("2 Nephi", 23, "Isaiah", 13, "2 Nephi 23 ↔ Isaiah 13 (The Burden of Babylon)"),
    ("2 Nephi", 24, "Isaiah", 14, "2 Nephi 24 ↔ Isaiah 14 (How Art Thou Fallen from Heaven, O Lucifer)"),
    ("Mosiah", 14, "Isaiah", 53, "Mosiah 14 ↔ Isaiah 53 (The Suffering Servant Song)"),
    ("3 Nephi", 22, "Isaiah", 54, "3 Nephi 22 ↔ Isaiah 54 (Enlarge the Place of Thy Tent)"),
]

SERMON_PARALLELS: list[tuple[str, int, str, int, str]] = [
    ("3 Nephi", 12, "Matthew", 5, "3 Nephi 12 ↔ Matthew 5 (The Beatitudes & Higher Law at the Temple)"),
    ("3 Nephi", 13, "Matthew", 6, "3 Nephi 13 ↔ Matthew 6 (Almsgiving, The Lord’s Prayer & Treasures in Heaven)"),
    ("3 Nephi", 14, "Matthew", 7, "3 Nephi 14 ↔ Matthew 7 (Judge Not, Ask and Ye Shall Receive & The Two Foundations)"),
]


def build_intertextual_parallels_edition() -> Work:
    """Compile the Intertextual Parallels Comparative Reader aligning Book of Mormon Isaiah
    with KJV Isaiah and 3 Nephi 12–14 with Matthew 5–7.
    """
    bom = ingest_standard_work("book-of-mormon")
    ot = ingest_standard_work("old-testament")
    nt = ingest_standard_work("new-testament")

    def _index_chapters(w: Work) -> dict[tuple[str, int], Chapter]:
        out: dict[tuple[str, int], Chapter] = {}
        for b in w.books:
            for c in b.chapters:
                out[(b.title, int(c.number or 1))] = c
        return out

    bom_map = _index_chapters(bom)
    bib_map = {**_index_chapters(ot), **_index_chapters(nt)}

    def _build_parallel_chapters(
        pairs: list[tuple[str, int, str, int, str]],
        part_prefix: str,
    ) -> list[Chapter]:
        chapters: list[Chapter] = []
        for idx, (bom_bk, bom_ch_num, bib_bk, bib_ch_num, title) in enumerate(pairs, start=1):
            c_bom = bom_map[(bom_bk, bom_ch_num)]
            c_bib = bib_map[(bib_bk, bib_ch_num)]

            max_v = max(len(c_bom.verses), len(c_bib.verses))
            out_verses: list[Verse] = []
            out_anns: list[Annotation] = []
            diff_counter = 0

            for v_i in range(max_v):
                v_bom = c_bom.verses[v_i] if v_i < len(c_bom.verses) else None
                v_bib = c_bib.verses[v_i] if v_i < len(c_bib.verses) else None

                v_num = v_i + 1
                bom_text = v_bom.text if v_bom else "[Verse not present in Book of Mormon chapter]"
                bib_text = v_bib.text if v_bib else "[Verse not present in KJV chapter]"

                diff_xhtml, chg_cnt, diff_pairs = compute_inline_word_diff_xhtml(
                    bib_text, bom_text, ignore_pure_punctuation_and_case=True
                )

                bom_label = f"{bom_bk} {bom_ch_num}:{v_num}"
                bib_label = f"{bib_bk} {bib_ch_num}:{v_num}"

                if chg_cnt > 0:
                    diff_counter += 1
                    ann_id = f"{part_prefix}-ch{idx}-v{v_num}"
                    out_anns.append(
                        Annotation(
                            id=ann_id,
                            label=f"⇄ {chg_cnt}",
                            title=f"{bom_label} vs. {bib_label}",
                            note_type=AnnotationType.VARIANT,
                            paragraphs=[
                                f"KJV Baseline ({bib_label}): {bib_text}",
                                f"Book of Mormon Reading ({bom_label}): {bom_text}",
                                "Word-Level Departures: "
                                + "; ".join(f"KJV “{old}” → BoM “{new}”" for old, new in diff_pairs[:8])
                                + ".",
                            ],
                        )
                    )
                    diff_unit = "diff" if chg_cnt == 1 else "diffs"
                    html_str = (
                        f'<strong>{bom_label} / {bib_label}</strong> '
                        f'<sup class="fn-sup"><a class="noteref var-badge" epub:type="noteref" '
                        f'id="ref-{ann_id}" href="#fn-{ann_id}">[⇄ {chg_cnt} {diff_unit}]</a></sup><br />'
                        f"{diff_xhtml}"
                    )
                else:
                    html_str = (
                        f"<strong>{bom_label} / {bib_label}</strong> "
                        f'<span class="identical-badge">[Identical]</span><br />'
                        f"{escape_xhtml(bom_text, False)}"
                    )

                out_verses.append(
                    Verse(
                        verse=v_num,
                        text=f"{bom_label} / {bib_label}: {bom_text}",
                        html_text=html_str,
                        citation_label=f"{bom_label} / {bib_label}",
                    )
                )

            chapters.append(
                Chapter(
                    id=f"{part_prefix}-ch-{idx:02d}",
                    number=idx,
                    title=title,
                    headnote=(
                        f"Collation of {bom_bk} {bom_ch_num} ({len(c_bom.verses)} verses) against KJV {bib_bk} {bib_ch_num} "
                        f"({len(c_bib.verses)} verses): {diff_counter} of {max_v} verses contain lexical differences."
                    ),
                    verses=out_verses,
                    annotations=out_anns,
                )
            )
        return chapters

    isaiah_book = Book(
        id="isaiah-parallels",
        title="Part I: Book of Mormon Isaiah vs. KJV Isaiah (19 Chapters)",
        full_title="Comparative Collation of Book of Mormon Isaiah Passages Against the King James Version",
        chapters=_build_parallel_chapters(ISAIAH_PARALLELS, "isa"),
    )

    sermon_book = Book(
        id="sermon-parallels",
        title="Part II: The Sermon at the Temple vs. The Sermon on the Mount",
        full_title="Comparative Collation of 3 Nephi 12–14 Against Matthew 5–7",
        chapters=_build_parallel_chapters(SERMON_PARALLELS, "serm"),
    )

    intro = Chapter(
        id="intertextual-parallels-intro",
        title="Guide to the Intertextual Collation",
        is_front_matter=True,
        blocks=[
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text="This volume aligns the major biblical parallel chapters in the Book of Mormon directly against the King James Version (KJV) text at the word level.",
            ),
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text="In every verse, the KJV serves as the baseline and the Book of Mormon as the target text: words present in the KJV but omitted or replaced in the Book of Mormon appear in strikethrough, while words added or modified in the Book of Mormon appear in bold underline. Tap any [⇄ diffs] badge to view both full verses side-by-side in a native Kindle modal pop-up.",
                html_text=(
                    "In every verse, the KJV serves as the baseline and the Book of Mormon as the target text: "
                    'words in the KJV omitted or replaced in the Book of Mormon appear as <del class="diff-del">KJV reading</del>, '
                    'while Nephite expansions or modifications appear as <ins class="diff-ins">Book of Mormon reading</ins>. '
                    "Tap any <strong>[⇄ diffs]</strong> badge to view both complete verses side-by-side in a native Kindle pop-up."
                ),
            ),
        ],
    )

    return Work(
        id="bom-intertextual-parallels",
        title="Book of Mormon Intertextual Parallels",
        subtitle="Word-Level Collation of Brass Plates Isaiah & The Sermon at the Temple Against the King James Bible",
        authors=["Proteus Intertextual Alignment Engine"],
        edition_label="Proteus Comparative Parallel Edition",
        front_matter=[intro],
        books=[isaiah_book, sermon_book],
        css_theme="variants.css",
    )


# ==============================================================================
# 3. Build Target 3: Poetic & Chiasmus Study Edition
# ==============================================================================

# Curated structural map of the most famous chiastic structures in the Book of Mormon
# (e.g., John W. Welch's landmark discoveries in Alma 36, Mosiah 3:18-19, Mosiah 5:10-12, Alma 41:13-15, 2 Nephi 29:13-14)
CHIASTIC_STRUCTURES: list[dict] = [
    {
        "id": "alma-36-master-chiasm",
        "title": "Alma 36:1–30 — Alma’s Conversion Testimony (The Master 17-Level Chiasm)",
        "headnote": (
            "Discovered by John W. Welch in 1967, Alma 36 forms a complete chapter-length concentric chiasm "
            "pivoting at verses 17–18 upon Jesus Christ, the Son of God, turning Alma's Harrowing Pain (A–P) "
            "into Exquisite Joy (P'–A')."
        ),
        "book": "Alma",
        "chapter": 36,
        "levels": [
            (0, "A", [1], "Keep the commandments of God and ye shall prosper in the land"),
            (1, "B", [2], "Do as I have done, in remembering the captivity of our fathers; for they were in bondage"),
            (2, "C", [3], "Whosoever shall put their trust in God shall be supported in their trials, and lifted up at the last day"),
            (3, "D", [4], "I would not that ye think that I know of myself—not of the temporal, but of the spiritual, not of the carnal mind, but of God"),
            (4, "E", [5, 6, 7], "Born of God; seeking to destroy the church of God; fell to the earth"),
            (5, "F", [8, 9], "Voice of the angel; limbs paralyzed: Even if thou wilt of thyself be destroyed, seek no more to destroy the church of God"),
            (6, "G", [10, 11, 12], "Fell to the earth for the space of three days and three nights; racked with eternal torment"),
            (7, "H", [13, 14, 15], "I did remember all my sins and iniquities, for which I was tormented with the pains of hell"),
            (8, "I (Pivot — Part 1)", [16, 17], "Racked with torment, while I was harrowed up by the memory of my many sins, behold, I remembered also to have heard my father prophesy concerning the coming of one Jesus Christ, a Son of God, to atone for the sins of the world"),
            (8, "I' (Pivot — Part 2)", [18, 19], "Now, as my mind caught hold upon this thought, I cried within my heart: O Jesus, thou Son of God, have mercy on me... and I could remember my pains no more; yea, I was not harrowed up by the memory of my sins any more"),
            (7, "H'", [20, 21], "Oh, what joy, and what marvelous light I did behold; yea, my soul was filled with joy as exceeding as was my pain"),
            (6, "G'", [22], "Longing to be with God, surrounded by numberless concourses of angels"),
            (5, "F'", [23], "My limbs did receive their strength again, and I stood upon my feet"),
            (4, "E'", [24, 25], "Labored without ceasing to bring souls unto repentance, that they might taste of the exceeding joy of which I did taste; that they might also be born of God"),
            (3, "D'", [26], "Therefore, my son, I have told thee these things that thou mayest learn wisdom; for I do know that whosoever shall put their trust in God shall be supported in their trials, and I know it of God"),
            (2, "C'", [27, 28], "Supported under trials and troubles of every kind; and I do know that he will raise me up at the last day"),
            (1, "B'", [29], "Retained in remembrance their captivity; and he has brought our fathers out of bondage"),
            (0, "A'", [30], "Inasmuch as ye shall keep the commandments of God ye shall prosper in the land"),
        ],
    },
    {
        "id": "mosiah-3-chiasm",
        "title": "Mosiah 3:18–19 — King Benjamin on Putting Off the Natural Man",
        "headnote": "A tight concentric chiasm contrasting the humiliation of the infant with the submission of the saint through the Atonement of Christ the Lord.",
        "book": "Mosiah",
        "chapter": 3,
        "levels": [
            (0, "A / B / C (v. 18)", [18], "Humble themselves → become as little children → salvation through the atoning blood of Christ, the Lord Omnipotent"),
            (1, "C' / B' / A' (v. 19)", [19], "Natural man is an enemy to God → yields to the enticings of the Holy Spirit & Atonement of Christ the Lord → becometh as a child, submissive, meek, humble"),
        ],
    },
    {
        "id": "mosiah-5-chiasm",
        "title": "Mosiah 5:8–12 — Taking Upon You the Name of Christ",
        "headnote": "King Benjamin’s covenant climax arranged around the central warning against transgression and being blotted out.",
        "book": "Mosiah",
        "chapter": 5,
        "levels": [
            (0, "A", [8], "There is no other name given whereby salvation cometh"),
            (1, "B", [9], "Know the voice by which ye shall be called, and also the name which he shall give unto you"),
            (2, "C (Center)", [10], "Whosoever shall not take upon them the name of Christ must be called by some other name; therefore, he findeth himself on the left hand of God"),
            (1, "B'", [11], "Remember also, that this is the name that I said I should give unto you that never should be blotted out, except it be through transgression"),
            (0, "A'", [12], "Retain the name written always in your hearts, that ye may hear and know the voice by which ye shall be called, and also, the name by which he shall call you"),
        ],
    },
    {
        "id": "alma-41-chiasm",
        "title": "Alma 41:13–15 — The Law of Restoration unto Corianton",
        "headnote": "Alma’s famous four-term lexical mirror: Wickedness/Righteousness/Good/Evil ↔ Evil/Good/Righteous/Wicked.",
        "book": "Alma",
        "chapter": 41,
        "levels": [
            (0, "A–D (v. 13)", [13], "[A] Meaning of the word restoration is to bring back again [B] evil for evil, or [C] carnal for carnal, or [D] devilish for devilish—[E] good for that which is good; [F] righteous for that which is righteous; [G] just for that which is just; [H] merciful for that which is merciful"),
            (1, "H'–E' (v. 14)", [14], "Therefore, my son, see that ye are [H'] merciful unto your brethren; [G'] deal justly, [F'] judge righteously, and [E'] do good continually; and if ye do all these things then shall ye receive your reward; yea, ye shall have [H''] mercy restored unto you again; ye shall have [G''] justice restored unto you again; ye shall have a [F''] righteous judgment restored unto you again; and ye shall have [E''] good rewarded unto you again"),
            (0, "D'–A' (v. 15)", [15], "For that which ye do send out shall return unto you again, and [A'] be restored; therefore, the word restoration more fully condemneth the sinner, and justifieth him not at all"),
        ],
    },
    {
        "id": "2-nephi-29-chiasm",
        "title": "2 Nephi 29:13–14 — The Gathering of the Three Scriptural Records",
        "headnote": "An inverted parallelism reversing the order of the Jews, the Nephites, and the Lost Tribes of Israel.",
        "book": "2 Nephi",
        "chapter": 29,
        "levels": [
            (0, "A -> B -> C (v. 13)", [13], "[A] The Jews shall have the words of the Nephites, and [B] the Nephites shall have the words of the Jews; and [C] the Nephites and the Jews shall have the words of the lost tribes of Israel; and [C'] the lost tribes of Israel shall have the words of [B'] the Nephites and [A'] the Jews"),
            (0, "Unity Climax (v. 14)", [14], "And it shall come to pass that my people, which are of the house of Israel, shall be gathered home unto the lands of their possessions; and my word also shall be gathered in one"),
        ],
    },
]

POETIC_CHAPTERS: list[tuple[str, int, int, int, str]] = [
    ("1 Nephi", 2, 19, 24, "The Lord’s Covenant Poem to Nephi (1 Nephi 2:19–24)"),
    ("2 Nephi", 4, 15, 35, "The Psalm of Nephi (2 Nephi 4:15–35)"),
    ("2 Nephi", 9, 28, 52, "Jacob’s Ten Woes & Invitation to the Holy One of Israel (2 Nephi 9:28–52)"),
    ("2 Nephi", 26, 23, 33, "He Inviteth Them All to Come unto Him (2 Nephi 26:23–33)"),
    ("Mosiah", 18, 8, 10, "The Baptismal Covenant at the Waters of Mormon (Mosiah 18:8–10)"),
    ("Alma", 5, 14, 30, "Alma’s Song of Redeeming Love & Self-Examination (Alma 5:14–30)"),
    ("Alma", 26, 1, 16, "Ammon’s Hymn of Rejoicing in the Lord (Alma 26:1–16)"),
    ("Alma", 29, 1, 17, "O That I Were an Angel (Alma 29:1–17)"),
    ("Helaman", 12, 1, 26, "Mormon’s Lament on the Unsteadiness of the Children of Men (Helaman 12:1–26)"),
    ("Moroni", 7, 45, 48, "Mormon’s Hymn of Charity, the Pure Love of Christ (Moroni 7:45–48)"),
]


def _format_verse_into_poetic_couplets(v_num: int | str, text: str) -> str:
    """Split a poetic verse on major clause boundaries (`;`, `:`, `—`, `, and `, `, yea, `, `, or `)
    into indented parallel poetic stichs.
    """
    clauses = re.split(r"(?<=[;:—])\s+|,\s+(?=(?:and|yea|or|neither|nor|but|for|wherefore|that)\b)", text)
    lines_html: list[str] = []
    for idx, cl in enumerate(clauses):
        cl_clean = cl.strip()
        if not cl_clean:
            continue
        indent_class = "poetic-line-a" if idx == 0 else ("poetic-line-b" if idx % 2 == 1 else "poetic-line-c")
        v_badge = f'<span class="verse-num">{v_num}</span>' if idx == 0 else ""
        lines_html.append(f'<span class="poetic-stich {indent_class}">{v_badge}{escape_xhtml(cl_clean, False)}</span>')
    return "<br />".join(lines_html)


def build_poetic_and_chiasmus_bom() -> Work:
    """Compile the Poetic & Chiasmus Study Edition of the Book of Mormon."""
    bom = ingest_standard_work("book-of-mormon")
    bom_map: dict[tuple[str, int], Chapter] = {}
    for b in bom.books:
        for c in b.chapters:
            bom_map[(b.title, int(c.number or 1))] = c

    # Part I: Chiastic Masterpieces
    chiasm_chapters: list[Chapter] = []
    for idx, ch_spec in enumerate(CHIASTIC_STRUCTURES, start=1):
        c_bom = bom_map[(ch_spec["book"], ch_spec["chapter"])]
        v_by_num = {int(v.verse): v for v in c_bom.verses}

        blocks: list[ContentBlock] = []
        anns: list[Annotation] = []

        for step_i, (depth, label, v_nums, summary) in enumerate(ch_spec["levels"], start=1):
            ann_id = f"{ch_spec['id']}-lvl-{step_i}"
            v_texts = [f"v. {vn}: {v_by_num[vn].text}" for vn in v_nums if vn in v_by_num]
            full_v_str = " ".join(v_by_num[vn].text for vn in v_nums if vn in v_by_num)

            anns.append(
                Annotation(
                    id=ann_id,
                    label=label,
                    title=f"Chiastic Level [{label}] — {ch_spec['book']} {ch_spec['chapter']}:{','.join(map(str, v_nums))}",
                    note_type=AnnotationType.FOOTNOTE,
                    paragraphs=[
                        f"Structural Theme: {summary}.",
                        *v_texts,
                    ],
                )
            )

            depth_clamped = min(depth, 8)
            html_str = (
                f'<span class="chiasm-step chiasm-indent-{depth_clamped}">'
                f'<a class="noteref chiasm-badge" epub:type="noteref" id="ref-{ann_id}" href="#fn-{ann_id}">[{escape_xhtml(label, False)}]</a> '
                f'<span class="verse-num">v. {",".join(map(str, v_nums))}</span> '
                f"{escape_xhtml(full_v_str, False)}"
                f"</span>"
            )
            blocks.append(
                ContentBlock(
                    block_type=BlockType.PARAGRAPH,
                    text=f"[{label}] (v. {','.join(map(str, v_nums))}) {full_v_str}",
                    html_text=html_str,
                )
            )

        chiasm_chapters.append(
            Chapter(
                id=ch_spec["id"],
                number=idx,
                title=ch_spec["title"],
                headnote=ch_spec["headnote"],
                blocks=blocks,
                annotations=anns,
            )
        )

    # Part II: Prophetic Psalms, Hymns & Parallel Stanzas
    poetic_chapters: list[Chapter] = []
    for idx, (bk_name, ch_num, v_start, v_end, title) in enumerate(POETIC_CHAPTERS, start=1):
        c_bom = bom_map[(bk_name, ch_num)]
        verses_sub = [v for v in c_bom.verses if v_start <= int(v.verse) <= v_end]
        poetic_verses: list[Verse] = []
        for v in verses_sub:
            poetic_verses.append(
                Verse(
                    verse=v.verse,
                    text=v.text,
                    html_text=_format_verse_into_poetic_couplets(v.verse, v.text),
                    citation_label=v.citation_label,
                )
            )
        poetic_chapters.append(
            Chapter(
                id=f"poetic-psalm-{idx:02d}",
                number=idx,
                title=title,
                headnote=f"Formatted in indented parallel stichs from {bk_name} {ch_num}:{v_start}–{v_end}.",
                verses=poetic_verses,
            )
        )

    # Part III: The Complete Book of Mormon in Clause-Parallel Poetic Cadence
    full_poetic_books: list[Book] = [
        Book(
            id="part-1-chiastic-masterpieces",
            title="Part I: Concentric Chiastic Structures (Indented Parallelisms)",
            full_title="Part I: Major Chiastic Structures in the Book of Mormon",
            chapters=chiasm_chapters,
        ),
        Book(
            id="part-2-prophetic-psalms",
            title="Part II: Prophetic Psalms, Hymns & Covenant Poems",
            full_title="Part II: Prophetic Psalms, Hymns, and Covenant Discourses",
            chapters=poetic_chapters,
        ),
    ]

    intro = Chapter(
        id="poetic-chiasmus-intro",
        title="Introduction to Hebraic Parallelism & Chiasmus",
        is_front_matter=True,
        blocks=[
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=(
                    "Ancient Hebrew and Near Eastern prophetic writing relies not on phonetic rhyme, "
                    "but on thought-rhyme (synonymous, antithetic, synthetic, and chiastic parallelism). "
                    "Part I of this study edition presents the landmark concentric chiasms of the Book of Mormon "
                    "with visual indentation levels ([A], [B], [C]... [C'], [B'], [A']) and interactive pop-up "
                    "structural notes. Part II presents ten celebrated prophetic psalms, hymns, and covenant poems "
                    "typeset in clause-level poetic couplets."
                ),
            )
        ],
    )

    return Work(
        id="bom-poetic-and-chiasmus",
        title="The Book of Mormon: Poetic & Chiasmus Study Edition",
        subtitle="Concentric Chiastic Structures, Hebraic Parallelisms & Prophetic Psalms",
        authors=["Proteus Structural Poetics Engine"],
        edition_label="Proteus Poetic & Chiastic Study Edition",
        front_matter=[intro],
        books=full_poetic_books,
        css_theme="variants.css",
    )
