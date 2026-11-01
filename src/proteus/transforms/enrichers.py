"""Phase 3 Relational & Linguistic Enrichers.

Provides:
1. Top 1,000 Most-Cited Verses Anthology (1839–1959) (`build_top_1000_cited_verses_anthology`)
   - Ranks all 20,758 cited verses across the 5 Standard Works by historical citation frequency
   - Attaches interactive pop-up footnotes listing the citing prophets/apostles, JoD/TPJS/GC references,
     and actual historical sermon excerpts from `talk_texts_pre_1960.jsonl`.
2. Book of Mormon Onomasticon Study Reader (`transform_with_onomasticon`)
   - Links proper nouns in the text to BYU Onomasticon pop-up notes containing IPA pronunciation,
     Deseret Alphabet glyphs (`𐐤𐐀𐐙𐐌`), Hebrew/Semitic reconstructions, and scholarly etymologies.
3. Red-Letter / Divine Speech Edition (`transform_with_divine_speech`)
   - Identifies direct words of Christ / Jehovah / the Father across the Book of Mormon (including
     the risen Christ's ministry in 3 Nephi 11–28, Moroni 8/12, Ether 3/12, 2 Nephi 29–31, etc.)
     and styles them with dark-mode-resilient rubrication and a `✦` Divine Speech margin indicator.
4. The Master Study Book of Mormon (`build_master_study_book_of_mormon`)
   - Unites all three enrichments (Divine Speech + Onomasticon Etymology + Historical Citation Index)
     into a single polyphonic study volume with distinct visual channels so they never collide.
"""

from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy

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
from proteus.ingest.relational import (
    HistoricalCitationRecord,
    OnomasticonEntry,
    get_discourse_excerpt_index,
    load_citations_by_canonical_ref,
    load_onomasticon_entries,
    select_representative_citations,
)
from proteus.ingest.standard_works import ingest_standard_work


# ==============================================================================
# 1. Divine Speech (Red-Letter) Identification Heuristics & Canonical Spans
# ==============================================================================

# Chapters in the Book of Mormon where the risen Christ or the Lord speaks across whole verse ranges
DIVINE_SPEECH_CHAPTER_RANGES: dict[tuple[str, int], list[tuple[int, int]]] = {
    ("1 Nephi", 2): [(19, 24)],
    ("1 Nephi", 14): [(26, 27)],
    ("1 Nephi", 17): [(13, 14)],
    ("2 Nephi", 3): [(5, 21)],
    ("2 Nephi", 7): [(1, 11)],
    ("2 Nephi", 8): [(1, 25)],
    ("2 Nephi", 10): [(7, 22)],
    ("2 Nephi", 27): [(15, 35)],
    ("2 Nephi", 28): [(29, 32)],
    ("2 Nephi", 29): [(1, 14)],
    ("2 Nephi", 31): [(10, 12), (14, 15)],
    ("2 Nephi", 32): [(4, 6)],
    ("Jacob", 2): [(23, 33)],
    ("Jacob", 5): [(3, 76)],
    ("Enos", 1): [(5, 8), (10, 10), (15, 18)],
    ("Mosiah", 3): [(23, 24)],
    ("Mosiah", 14): [(1, 12)],
    ("Mosiah", 23): [(10, 10)],
    ("Mosiah", 24): [(13, 14), (16, 16), (23, 23)],
    ("Mosiah", 26): [(15, 32)],
    ("Mosiah", 27): [(13, 16)],
    ("Alma", 5): [(33, 38)],
    ("Alma", 7): [(9, 9)],
    ("Alma", 8): [(15, 17)],
    ("Alma", 9): [(13, 24)],
    ("Alma", 10): [(7, 10)],
    ("Alma", 12): [(16, 18)],
    ("Alma", 14): [(11, 11)],
    ("Alma", 20): [(2, 4)],
    ("Alma", 36): [(8, 11)],
    ("Alma", 37): [(23, 25), (27, 31)],
    ("Helaman", 10): [(4, 11)],
    ("3 Nephi", 1): [(13, 14)],
    ("3 Nephi", 9): [(2, 22)],
    ("3 Nephi", 10): [(3, 7)],
    ("3 Nephi", 11): [(3, 7), (10, 11), (14, 14), (16, 16), (20, 41)],
    ("3 Nephi", 12): [(1, 48)],
    ("3 Nephi", 13): [(1, 34)],
    ("3 Nephi", 14): [(1, 27)],
    ("3 Nephi", 15): [(1, 10), (12, 24)],
    ("3 Nephi", 16): [(1, 20)],
    ("3 Nephi", 17): [(1, 4), (6, 8), (14, 14), (20, 20), (23, 23)],
    ("3 Nephi", 18): [(3, 16), (18, 25), (27, 35)],
    ("3 Nephi", 19): [(20, 23), (28, 29), (35, 36)],
    ("3 Nephi", 20): [(3, 3), (8, 8), (10, 46)],
    ("3 Nephi", 21): [(1, 29)],
    ("3 Nephi", 22): [(1, 17)],
    ("3 Nephi", 23): [(1, 5), (7, 11), (13, 13)],
    ("3 Nephi", 24): [(1, 18)],
    ("3 Nephi", 25): [(1, 6)],
    ("3 Nephi", 26): [(2, 2)],
    ("3 Nephi", 27): [(2, 22), (24, 33)],
    ("3 Nephi", 28): [(1, 3), (6, 11)],
    ("Mormon", 3): [(15, 16)],
    ("Ether", 1): [(40, 43)],
    ("Ether", 2): [(14, 15), (20, 20), (23, 25)],
    ("Ether", 3): [(7, 8), (11, 16), (21, 28)],
    ("Ether", 4): [(6, 19)],
    ("Ether", 12): [(26, 28), (35, 37)],
    ("Moroni", 7): [(33, 34)],
    ("Moroni", 8): [(8, 8)],
}

# Inline Divine Speech introducer regexes for verses where narration introduces direct speech
DIVINE_SPEECH_INTRO_REGEX = re.compile(
    r"^(.*?(?:saith\s+the\s+Lord(?:\s+of\s+Hosts|\s+God)?|thus\s+saith\s+the\s+Lord(?:\s+God)?|"
    r"the\s+word\s+of\s+the\s+Lord\s+came[^,:;]+|the\s+voice\s+of\s+the\s+Lord\s+came[^,:;]+|"
    r"the\s+Lord\s+spake[^,:;]+|Jesus\s+spake[^,:;]+|he\s+spake\s+unto\s+them,\s+saying|"
    r"said\s+unto\s+(?:him|them|me),\s+saying|saying\s+unto\s+(?:him|them|me))[,:;]\s*)(.+)$",
    re.I,
)

# Direct first-person divine declarations inside a verse
DIVINE_FIRST_PERSON_REGEX = re.compile(
    r"\b(?:Behold,\s+I\s+am\s+Jesus\s+Christ|I\s+am\s+the\s+Lord\s+thy\s+God|I\s+am\s+Alpha\s+and\s+Omega|"
    r"saith\s+the\s+Father|saith\s+the\s+Lamb|I,\s+the\s+Lord,|for\s+I\s+the\s+Lord\s+have\s+spoken\s+it)\b",
    re.I,
)


def is_verse_divine_speech(book_title: str, chapter_num: int | str | None, verse_num: int | str, text: str) -> tuple[bool, str | None, str | None]:
    """Check if a verse contains direct words of Christ / Deity.

    Returns:
        `(is_divine, narrative_prefix, divine_body)`
        - If the entire verse is divine speech: `(True, None, text)`
        - If narration introduces divine speech: `(True, prefix, speech_part)`
        - Otherwise: `(False, None, None)`
    """
    if book_title == "Doctrine and Covenants":
        # Nearly all of the D&C is direct divine voice except historical sections like 102, 121-123, 127-128, 134, 135
        sec_num = int(chapter_num) if isinstance(chapter_num, int) or (isinstance(chapter_num, str) and chapter_num.isdigit()) else 0
        if sec_num not in (102, 113, 123, 127, 128, 130, 131, 134, 135, 138):
            return True, None, text

    ch_int = int(chapter_num) if isinstance(chapter_num, int) or (isinstance(chapter_num, str) and str(chapter_num).isdigit()) else 0
    v_int = int(verse_num) if isinstance(verse_num, int) or (isinstance(verse_num, str) and str(verse_num).isdigit()) else 0

    ranges = DIVINE_SPEECH_CHAPTER_RANGES.get((book_title, ch_int), [])
    in_canonical_range = any(lo <= v_int <= hi for lo, hi in ranges)

    # Check if the verse has an introductory narrative clause ("And Jesus spake unto them, saying: ...")
    m_intro = DIVINE_SPEECH_INTRO_REGEX.match(text)
    if m_intro and (in_canonical_range or DIVINE_FIRST_PERSON_REGEX.search(text) or "saith the Lord" in m_intro.group(1).lower() or "voice of the Lord" in m_intro.group(1).lower()):
        return True, m_intro.group(1), m_intro.group(2)

    if in_canonical_range:
        return True, None, text

    if DIVINE_FIRST_PERSON_REGEX.search(text):
        return True, None, text

    return False, None, None


# ==============================================================================
# 2. Target 1: Top 1,000 Most-Cited Verses Anthology (1839–1959)
# ==============================================================================

def build_top_1000_cited_verses_anthology() -> Work:
    """Compile the Top 1,000 Most-Cited Scripture Verses (1839–1959) across all 5 Standard Works,
    ranked by historical citation frequency in the Journal of Discourses, TPJS, and pre-1960 General Conference.
    """
    citations_by_urn = load_citations_by_canonical_ref()

    # Load all 5 Standard Works to map canonical URN -> Verse object & volume/book metadata
    volume_slugs = [
        "old-testament",
        "new-testament",
        "book-of-mormon",
        "doctrine-and-covenants",
        "pearl-of-great-price",
    ]
    verse_lookup: dict[str, tuple[str, str, Verse]] = {}
    for vs in volume_slugs:
        w = ingest_standard_work(vs)
        for bk in w.books:
            for ch in bk.chapters:
                for v in ch.verses:
                    if v.canonical_ref:
                        verse_lookup[v.canonical_ref] = (w.title, bk.title, v)

    # Filter to URNs that exist in our canonical verse lookup and sort descending by citation count
    ranked_urns = sorted(
        [(urn, disp, recs) for urn, (disp, recs) in citations_by_urn.items() if urn in verse_lookup],
        key=lambda item: (-len(item[2]), item[1]),
    )[:1000]

    excerpt_index = get_discourse_excerpt_index()

    # Organize the 1,000 verses into 2 complementary reading parts:
    # Book 1: The Top 100 Overall Ranked Passages (1–100 Countdown)
    # Books 2–6: The Top 1,000 Organized by Canonical Standard Work Volume
    books: list[Book] = []

    def _create_cited_verse_item(
        rank: int,
        urn: str,
        display_cite: str,
        recs: list[HistoricalCitationRecord],
        v_obj: Verse,
        ann_prefix: str,
    ) -> tuple[Verse, Annotation]:
        total_cites = len(recs)
        jod_cnt = sum(1 for r in recs if r.corpus == "J")
        tpjs_cnt = sum(1 for r in recs if r.corpus == "T")
        gc_cnt = sum(1 for r in recs if r.corpus == "E")

        speaker_counts = Counter(r.speaker for r in recs if r.speaker)
        top_speakers = ", ".join(f"{sp} ({cnt}×)" for sp, cnt in speaker_counts.most_common(5))

        ann_id = f"{ann_prefix}-r{rank}"
        note_paras: list[str] = [
            f"Rank #{rank} Overall • Cited {total_cites} times (1839–1959): "
            f"Journal of Discourses ({jod_cnt}), Teachings of the Prophet Joseph Smith ({tpjs_cnt}), "
            f"General Conference 1942–1959 ({gc_cnt}).",
            f"Frequent Citing Speakers: {top_speakers}.",
        ]

        # List up to 6 notable historical citations
        sample_lines = []
        for r in recs[:6]:
            sample_lines.append(f"{r.speaker}, “{r.title}” ({r.source_citation}, {r.year})")
        if sample_lines:
            note_paras.append("Selected Historical Citations: " + "; ".join(sample_lines) + ".")

        # Include up to 3 full contextual multi-paragraph sermon excerpts per verse in Top 1000
        rep_recs = select_representative_citations(recs, max_excerpts=3)
        for rep in rep_recs:
            ex_paras = excerpt_index.extract_excerpt_paragraphs(rep.citation_id, rep.talk_id)
            if ex_paras:
                note_paras.append(
                    f"▸ Excerpt — {rep.speaker}, “{rep.title}” ({rep.source_citation}, {rep.year}):"
                )
                for ep in ex_paras:
                    note_paras.append(f"“{ep}”")

        ann = Annotation(
            id=ann_id,
            label=f"★ {total_cites}×",
            title=f"{display_cite} — Historical Citation Profile",
            note_type=AnnotationType.CITATION,
            paragraphs=note_paras,
        )

        escaped_body = escape_xhtml(v_obj.text, smart_typography=False)
        html_str = (
            f'<span class="citation-rank-head"><strong>#{rank} — {escape_xhtml(display_cite, False)}</strong></span> '
            f'<sup class="fn-sup"><a class="noteref cite-badge" epub:type="noteref" '
            f'id="ref-{ann_id}" href="#fn-{ann_id}">[★ {total_cites} Citations]</a></sup><br />'
            f"{escaped_body}"
        )

        enriched_v = Verse(
            verse=rank,
            text=f"#{rank} — {display_cite} ({total_cites} citations): {v_obj.text}",
            html_text=html_str,
            canonical_ref=urn,
            citation_label=display_cite,
        )
        return enriched_v, ann

    # Part 1: Top 100 Countdown (in 2 chapters of 50 verses)
    top100_chapters: list[Chapter] = []
    for chunk_idx, start_i in enumerate((0, 50), start=1):
        ch_verses: list[Verse] = []
        ch_anns: list[Annotation] = []
        chunk = ranked_urns[start_i : start_i + 50]
        for offset, (urn, disp, recs) in enumerate(chunk, start=start_i + 1):
            _, _, v_obj = verse_lookup[urn]
            ev, ann = _create_cited_verse_item(offset, urn, disp, recs, v_obj, f"top100-c{chunk_idx}")
            ch_verses.append(ev)
            ch_anns.append(ann)
        top100_chapters.append(
            Chapter(
                id=f"top-100-part-{chunk_idx}",
                number=chunk_idx,
                title=f"Ranks #{start_i + 1} to #{start_i + len(chunk)}",
                headnote="Tap any [★ Citations] badge to open a native Kindle pop-up with speaker frequencies and sermon references.",
                verses=ch_verses,
                annotations=ch_anns,
            )
        )

    books.append(
        Book(
            id="top-100-overall",
            title="Part I: The Top 100 Most-Cited Verses (Ranked #1–#100)",
            full_title="The Top 100 Most-Cited Scripture Verses of the Restoration (1839–1959)",
            chapters=top100_chapters,
        )
    )

    # Parts 2–6: All 1,000 Verses Grouped by Standard Work Volume
    by_vol: dict[str, list[tuple[int, str, str, list[HistoricalCitationRecord], Verse]]] = {
        "The Old Testament": [],
        "The New Testament": [],
        "The Book of Mormon": [],
        "The Doctrine and Covenants": [],
        "The Pearl of Great Price": [],
    }
    for rank, (urn, disp, recs) in enumerate(ranked_urns, start=1):
        vol_title, _, v_obj = verse_lookup[urn]
        by_vol.setdefault(vol_title, []).append((rank, urn, disp, recs, v_obj))

    for vol_idx, (vol_title, items) in enumerate(by_vol.items(), start=2):
        if not items:
            continue
        vol_slug = f"vol-{vol_idx}"
        vol_chapters: list[Chapter] = []
        # Chunk into chapters of 50 verses for fast Kindle rendering
        for c_idx in range(0, len(items), 50):
            sub = items[c_idx : c_idx + 50]
            ch_verses = []
            ch_anns = []
            for rank, urn, disp, recs, v_obj in sub:
                ev, ann = _create_cited_verse_item(rank, urn, disp, recs, v_obj, f"{vol_slug}-c{c_idx}")
                ch_verses.append(ev)
                ch_anns.append(ann)
            vol_chapters.append(
                Chapter(
                    id=f"{vol_slug}-ch-{c_idx // 50 + 1}",
                    number=c_idx // 50 + 1,
                    title=f"{vol_title} — Top Cited Passages ({c_idx + 1}–{c_idx + len(sub)} of {len(items)})",
                    verses=ch_verses,
                    annotations=ch_anns,
                )
            )
        books.append(
            Book(
                id=vol_slug,
                title=f"{vol_title} ({len(items)} Verses in Top 1,000)",
                full_title=f"Most-Cited Passages in {vol_title} (1839–1959)",
                chapters=vol_chapters,
            )
        )

    intro = Chapter(
        id="top-1000-intro",
        title="Methodology & Historical Scope (1839–1959)",
        is_front_matter=True,
        blocks=[
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=(
                    "This anthology ranks the 1,000 most frequently cited scripture verses across the first "
                    "century of Latter-day Saint discourse (1839–1959), derived from 67,165 historical citations "
                    "across the 26-volume Journal of Discourses, Teachings of the Prophet Joseph Smith, and "
                    "General Conference addresses prior to 1960. Every verse includes an interactive [★ Citations] "
                    "pop-up badge detailing citation counts by corpus, top citing speakers, and primary source references."
                ),
            )
        ],
    )

    return Work(
        id="top-1000-cited-verses",
        title="The Top 1,000 Cited Verses of the Restoration",
        subtitle="Ranked by Historical Citation Frequency (1839–1959) with Interactive Sermon Profiles",
        authors=["Proteus Relational Scripture Engine", "BYU Scripture Citation Index (Pre-1960)"],
        edition_label="Proteus Relational Study Anthology",
        description=(
            "The 1,000 most frequently quoted scripture passages in early Latter-day Saint sermons (1839–1959), "
            "complete with native Kindle pop-up speaker analytics and historical discourse excerpts."
        ),
        front_matter=[intro],
        books=books,
        css_theme="enriched.css",
    )


# ==============================================================================
# 3. Target 2, 3, & 4: Enriched Book of Mormon Editions
#    - Onomasticon Study Reader
#    - Red-Letter / Divine Speech Edition
#    - The Master Study Edition (Combining All Three Visual & Pop-up Channels!)
# ==============================================================================

def build_enriched_book_of_mormon(
    enable_divine_speech: bool = False,
    enable_onomasticon: bool = False,
    enable_citations: bool = False,
    custom_id: str | None = None,
    custom_title: str | None = None,
    custom_subtitle: str | None = None,
    custom_edition_label: str | None = None,
) -> Work:
    """Build an enriched Book of Mormon with any combination of:
    1. Red-Letter / Divine Speech styling (`<span class="divine-speech">✦ ...</span>`)
    2. BYU Onomasticon proper-noun lexical pop-ups (`<a class="noteref onoma-link" ...>Nephi<sup class="onoma-glyph">◈</sup></a>`)
    3. Pre-1960 Historical Citation Index pop-up badges (`<a class="noteref cite-badge" ...>[★ 39]</a>`)
    """
    work = deepcopy(ingest_standard_work("book-of-mormon"))
    work.css_theme = "enriched.css"

    if custom_id:
        work.id = custom_id
    if custom_title:
        work.title = custom_title
    if custom_subtitle:
        work.subtitle = custom_subtitle
    if custom_edition_label:
        work.edition_label = custom_edition_label

    onoma_entries: dict[str, OnomasticonEntry] = {}
    onoma_regex: re.Pattern[str] | None = None
    if enable_onomasticon:
        onoma_entries = load_onomasticon_entries()
        # Sort names longest-first to avoid partial word matches
        sorted_names = sorted(onoma_entries.keys(), key=len, reverse=True)
        pattern_str = r"\b(" + "|".join(re.escape(n) for n in sorted_names) + r")\b"
        onoma_regex = re.compile(pattern_str, re.I)

    citations_by_urn: dict[str, tuple[str, list[HistoricalCitationRecord]]] = {}
    excerpt_index = None
    if enable_citations:
        citations_by_urn = load_citations_by_canonical_ref()
        excerpt_index = get_discourse_excerpt_index()

    # Add a clear Legend / Reader's Key in Front Matter explaining the visual & pop-up channels
    legend_blocks: list[ContentBlock] = [
        ContentBlock(
            block_type=BlockType.HEADING,
            text="Reader’s Guide to Interactive Study Features",
            level=2,
        )
    ]
    if enable_divine_speech:
        legend_blocks.append(
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text="1. Divine Speech (Red-Letter Channel): Direct words spoken by Jesus Christ, Jehovah, or the Father are marked with a leading four-point star (✦) and rendered in warm crimson/maroon typography (automatically adapting for high contrast on Kindle Paperwhite e-ink and dark mode).",
                html_text=(
                    '<strong>1. Divine Speech (Red-Letter Channel):</strong> Direct words spoken by Jesus Christ, Jehovah, '
                    'or the Eternal Father are marked with a leading star (<span class="divine-marker">✦</span>) and styled in '
                    '<span class="divine-speech">distinct divine-speech rubrication</span> resilient to both e-ink grayscale and dark mode.'
                ),
            )
        )
    if enable_onomasticon:
        legend_blocks.append(
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text="2. BYU Onomasticon Etymology (◈ Lexical Channel): The first appearance of any canonical proper name in a chapter is underlined with a subtle dotted border and marked with a diamond glyph (◈). Tap the name to open a native Kindle pop-up containing its IPA pronunciation, Deseret Alphabet transcription, Hebrew/Semitic reconstructions, and scholarly etymology.",
            )
        )
    if enable_citations:
        legend_blocks.append(
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text="3. Historical Citation Index ([★ N] Discourse Channel): Verses cited in early Latter-day Saint sermons (1839–1959) carry a bracketed star badge ([★ N]) at the end of the verse showing how many times that verse was quoted in the Journal of Discourses, Teachings of the Prophet Joseph Smith, and pre-1960 General Conference. Tap the badge to inspect the citing speakers and discourse references.",
            )
        )

    work.front_matter.insert(
        0,
        Chapter(
            id=f"{work.id}-study-legend",
            title="Interactive Study Key & Legend",
            is_front_matter=True,
            blocks=legend_blocks,
        ),
    )

    for book in work.books:
        for ch in book.chapters:
            ch_annotations: list[Annotation] = list(ch.annotations)
            # Track which Onomasticon names already have an `<aside>` in this chapter
            # We only link the FIRST occurrence of each name per chapter so the text stays clean and readable
            seen_names_in_chapter: set[str] = set()
            cite_counter = 0

            for v in ch.verses:
                raw_text = v.text
                is_div, nav_prefix, div_body = (
                    is_verse_divine_speech(book.title, ch.number, v.verse, raw_text)
                    if enable_divine_speech
                    else (False, None, None)
                )

                def _enrich_segment(segment_text: str) -> str:
                    escaped = escape_xhtml(segment_text, smart_typography=False)
                    if not enable_onomasticon or onoma_regex is None:
                        return escaped

                    def _replace_name(match: re.Match[str]) -> str:
                        word = match.group(0)
                        # Only match capitalized proper nouns in the text
                        if not word[0].isupper():
                            return word
                        key = word.lower()
                        if key in seen_names_in_chapter or key not in onoma_entries:
                            return word

                        seen_names_in_chapter.add(key)
                        entry = onoma_entries[key]
                        ann_id = f"{ch.id}-onoma-{key}"

                        header_parts = [f"◈ {entry.name_upper}"]
                        if entry.ipa:
                            header_parts.append(f"/{entry.ipa}/")
                        if entry.deseret:
                            header_parts.append(f"Deseret: {entry.deseret}")
                        if entry.classifications:
                            header_parts.append(f"({', '.join(entry.classifications)})")

                        paras = [" • ".join(header_parts)]
                        if entry.hebrew_summary:
                            paras.append(f"Ancient Reconstructions: {entry.hebrew_summary}")
                        paras.extend(entry.etymology_paragraphs[:3])

                        ch_annotations.append(
                            Annotation(
                                id=ann_id,
                                label=f"◈ {entry.display_name}",
                                title="BYU Onomasticon Etymology",
                                note_type=AnnotationType.ONOMASTICON,
                                paragraphs=paras,
                            )
                        )
                        return (
                            f'<a class="noteref onoma-link" epub:type="noteref" '
                            f'id="ref-{ann_id}" href="#fn-{ann_id}">{word}<sup class="onoma-glyph">◈</sup></a>'
                        )

                    return onoma_regex.sub(_replace_name, escaped)

                if is_div and div_body is not None:
                    if nav_prefix:
                        enriched_prefix = _enrich_segment(nav_prefix)
                        enriched_div = _enrich_segment(div_body)
                        verse_html = (
                            f'{enriched_prefix}<span class="divine-speech">'
                            f'<span class="divine-marker">✦</span>{enriched_div}</span>'
                        )
                    else:
                        enriched_div = _enrich_segment(div_body)
                        verse_html = (
                            f'<span class="divine-speech">'
                            f'<span class="divine-marker">✦</span>{enriched_div}</span>'
                        )
                else:
                    verse_html = _enrich_segment(raw_text)

                # Attach Historical Citation Index badge at the end of the verse if cited
                if enable_citations and v.canonical_ref and v.canonical_ref in citations_by_urn:
                    disp_cite, recs = citations_by_urn[v.canonical_ref]
                    if recs:
                        cite_counter += 1
                        total_c = len(recs)
                        ann_id = f"{ch.id}-cite-{cite_counter}"

                        jod_c = sum(1 for r in recs if r.corpus == "J")
                        tpjs_c = sum(1 for r in recs if r.corpus == "T")
                        gc_c = sum(1 for r in recs if r.corpus == "E")
                        sp_counts = Counter(r.speaker for r in recs if r.speaker)
                        top_sp = ", ".join(f"{s} ({c}×)" for s, c in sp_counts.most_common(4))

                        c_paras = [
                            f"Cited {total_c} {'time' if total_c == 1 else 'times'} (1839–1959) — "
                            f"JoD: {jod_c} | TPJS: {tpjs_c} | Conf. Era: {gc_c}.",
                            f"Citing Speakers: {top_sp}.",
                            "Primary References: "
                            + "; ".join(f"{r.speaker} ({r.source_citation}, {r.year})" for r in recs[:6])
                            + ".",
                        ]
                        if excerpt_index is not None:
                            rep_recs = select_representative_citations(recs, max_excerpts=4)
                            for rep in rep_recs:
                                ex_paras = excerpt_index.extract_excerpt_paragraphs(rep.citation_id, rep.talk_id)
                                if ex_paras:
                                    c_paras.append(
                                        f"▸ Discourse Excerpt — {rep.speaker}, “{rep.title}” ({rep.source_citation}, {rep.year}):"
                                    )
                                    for ep in ex_paras:
                                        c_paras.append(f"“{ep}”")
                        ch_annotations.append(
                            Annotation(
                                id=ann_id,
                                label=f"★{total_c}",
                                title=f"{disp_cite} — Historical Citations",
                                note_type=AnnotationType.CITATION,
                                paragraphs=c_paras,
                            )
                        )
                        verse_html = (
                            f"{verse_html} "
                            f'<sup class="fn-sup"><a class="noteref cite-badge" epub:type="noteref" '
                            f'id="ref-{ann_id}" href="#fn-{ann_id}">[★{total_c}]</a></sup>'
                        )

                if verse_html != escape_xhtml(raw_text, smart_typography=False):
                    v.html_text = verse_html

            ch.annotations = ch_annotations

    return work

