"""Proteus Master Relational Study Editions Engine (`master_study.py`).

Provides:
1. `build_master_study_edition(volume_slug)`: Builds an enriched Master Study edition for any
   individual Standard Work volume:
   - `old-testament-master-study`: KJV + Parallel Translations (BSB, ASV, BBE) + Cross-References + BYU Citation Index
   - `new-testament-master-study`: KJV + Parallel Translations (BSB, ASV, BBE) + Cross-References + BYU Citation Index
   - `book-of-mormon-master-study`: Canonical 2013 Text + BYU Onomasticon Etymology + BYU Citation Index
   - `doctrine-and-covenants-master-study`: Canonical 2013 Text + Onomasticon Terms + BYU Citation Index
   - `pearl-of-great-price-master-study`: Canonical 2013 Text + BYU Onomasticon (Kolob, Egyptus, etc.) + BYU Citation Index
2. `build_master_study_standard_works()`: Combines all five Standard Works into a single comprehensive
   Master Study edition with unified navigation, complete comparative apparatus, etymological gazetteers,
   and 19th-century historical discourse excerpts.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re

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
from proteus.core.scripture_linker import (
    ScriptureResolverMap,
    build_scripture_link_resolver,
    linkify_scripture_references,
    linkify_xref_list,
)
from proteus.core.typography import clean_prose_text, escape_xhtml
from proteus.ingest.bible_comparisons import VerseComparison, load_bible_comparisons
from proteus.ingest.relational import (
    DiscourseExcerptIndex,
    HistoricalCitationRecord,
    OnomasticonEntry,
    get_discourse_excerpt_index,
    load_citations_by_canonical_ref,
    load_onomasticon_entries,
    select_representative_citations,
)
from proteus.ingest.standard_works import ingest_standard_work


# Volume display titles and descriptions
VOLUME_CONFIGS: dict[str, dict[str, str]] = {
    "old-testament": {
        "slug": "old-testament-master-study",
        "title": "The Old Testament (Master Study Edition)",
        "subtitle": "KJV with Parallel Translations (BSB • ASV • BBE), Cross-References & 19th-Century Citations",
        "edition_label": "Proteus Relational Master Study Edition",
        "desc": (
            "The Old Testament in the Authorized King James Version, augmented with instant modal pop-ups "
            "for modern scholarly and simplified parallel translations (Berean Standard Bible, American Standard "
            "Version 1901, and Bible in Basic English), curated scriptural cross-references (OpenBible / TSK), "
            "and 19th-century Latter-day Saint sermon citations from the Journal of Discourses and TPJS."
        ),
    },
    "new-testament": {
        "slug": "new-testament-master-study",
        "title": "The New Testament (Master Study Edition)",
        "subtitle": "KJV with Parallel Translations (BSB • ASV • BBE), Cross-References & 19th-Century Citations",
        "edition_label": "Proteus Relational Master Study Edition",
        "desc": (
            "The New Testament in the Authorized King James Version, augmented with instant modal pop-ups "
            "for modern scholarly and simplified parallel translations (Berean Standard Bible, American Standard "
            "Version 1901, and Bible in Basic English), curated scriptural cross-references (OpenBible / TSK), "
            "and 19th-century Latter-day Saint sermon citations from the Journal of Discourses and TPJS."
        ),
    },
    "book-of-mormon": {
        "slug": "book-of-mormon-master-study",
        "title": "The Book of Mormon (Master Study Edition)",
        "subtitle": "Uniting BYU Onomasticon Etymologies (◈) and 19th-Century Discourse Citations ([★])",
        "edition_label": "Proteus Relational Master Study Edition",
        "desc": (
            "The 2013 canonical Book of Mormon with interactive BYU Onomasticon proper name etymologies (◈) "
            "and pre-1942 historical discourse citation badges ([★]) with extended sermon excerpts."
        ),
    },
    "doctrine-and-covenants": {
        "slug": "doctrine-and-covenants-master-study",
        "title": "The Doctrine and Covenants (Master Study Edition)",
        "subtitle": "Revelations of Joseph Smith with 19th-Century Citations ([★]) & Scriptural Etymologies (◈)",
        "edition_label": "Proteus Relational Master Study Edition",
        "desc": (
            "The 2013 Doctrine and Covenants with pre-1942 historical discourse citation badges ([★]) "
            "linking to Journal of Discourses and TPJS sermons, plus Onomasticon etymological pop-ups."
        ),
    },
    "pearl-of-great-price": {
        "slug": "pearl-of-great-price-master-study",
        "title": "The Pearl of Great Price (Master Study Edition)",
        "subtitle": "Moses, Abraham & Joseph Smith History with BYU Onomasticon (◈) & Discourse Citations ([★])",
        "edition_label": "Proteus Relational Master Study Edition",
        "desc": (
            "The 2013 Pearl of Great Price featuring complete BYU Onomasticon etymology pop-ups for ancient "
            "names and celestial terms (Kolob, Egyptus, Kokaubeam, Gnolaum, Elkenah, Olishem, etc.) and pre-1942 "
            "historical citation badges with discourse excerpts."
        ),
    },
}


def _create_master_study_legend_chapter(
    volume_slug: str,
    enable_comparisons: bool,
    enable_onomasticon: bool,
    enable_citations: bool,
) -> Chapter:
    """Generate the Front Matter Reader's Guide explaining all interactive study channels."""
    blocks: list[ContentBlock] = [
        ContentBlock(
            block_type=BlockType.HEADING,
            text="Reader’s Guide to the Master Study Features",
            level=2,
        ),
        ContentBlock(
            block_type=BlockType.PARAGRAPH,
            text=(
                "This Master Study Edition unites multiple scholarly, textual, and historical resources into "
                "a polyphonic, interactive Kindle EPUB3 reading experience. Features are rendered with clean "
                "typographic indicators that do not clutter the sacred text and open instant modal pop-up "
                "windows without losing your reading place."
            ),
        ),
    ]

    channel_idx = 1
    if enable_comparisons:
        blocks.append(
            ContentBlock(
                block_type=BlockType.SUBHEADING,
                text=f"{channel_idx}. Parallel Translations & Curated Cross-References ([⇄])",
                level=3,
            )
        )
        channel_idx += 1
        blocks.append(
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=(
                    "Every verse contains an interactive [⇄] comparison badge. Tapping this badge opens a "
                    "modal study pop-up displaying three prominent and reliable English translations alongside "
                    "curated cross-references from the Treasury of Scripture Knowledge (TSK) and OpenBible:\n\n"
                    "• BSB (Berean Standard Bible): A premier modern scholarly translation balancing formal and "
                    "functional equivalence, acclaimed for clarity and faithfulness to the original Hebrew and Greek texts.\n"
                    "• ASV (American Standard Version, 1901): The landmark scholarly formal-equivalence benchmark "
                    "produced by British and American biblical scholars, renowned for strict literal precision.\n"
                    "• BBE (Bible in Basic English, 1949/1964): Translated by Prof. S. H. Hooke using an accessible "
                    "fundamental vocabulary, providing a clear, simple reading / paraphrase perspective.\n"
                    "• Key Cross-References: High-relevance biblical passages shedding interpretive light on the text, "
                    "fully hyperlinked to navigate directly to each referenced passage."
                ),
            )
        )

    if enable_onomasticon:
        blocks.append(
            ContentBlock(
                block_type=BlockType.SUBHEADING,
                text=f"{channel_idx}. BYU Onomasticon Linguistic Etymologies (◈)",
                level=3,
            )
        )
        channel_idx += 1
        blocks.append(
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=(
                    "Proper nouns and ancient names (such as Nephi, Zarahemla, Kolob, Egyptus, Kokaubeam, and "
                    "Gnolaum) are marked on their first appearance in each chapter with a subtle dotted underline "
                    "and a diamond glyph (◈). Tapping the name opens a native pop-up note containing its IPA "
                    "pronunciation, Semitic / Egyptian reconstructions, and scholarly etymology from the Brigham "
                    "Young University Book of Mormon & Scripture Onomasticon Project (onoma.lib.byu.edu, edited "
                    "by Paul Y. Hoskisson; provided for educational, non-commercial study)."
                ),
            )
        )

    if enable_citations:
        blocks.append(
            ContentBlock(
                block_type=BlockType.SUBHEADING,
                text=f"{channel_idx}. Historical LDS Discourse Citations ([★ N])",
                level=3,
            )
        )
        channel_idx += 1
        blocks.append(
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=(
                    "Verses quoted in 19th-century Latter-day Saint sermons carry a bracketed star badge ([★ N]) "
                    "at the end of the verse showing the number of times that verse was cited in pre-1942 public-domain "
                    "sources: the 26-volume Journal of Discourses (1839–1886) and the Teachings of the Prophet Joseph "
                    "Smith (1830–1844), indexed via the BYU Scripture Citation Index (scriptures.byu.edu, Stephen W. "
                    "Liddle and Richard C. Galbraith). Tapping the badge displays citation frequency, top citing "
                    "prophets and apostles, primary source citations, and up to six extended multi-paragraph primary "
                    "sermon excerpts, with all internal scriptural references hyperlinked to their canonical text."
                ),
            )
        )

    return Chapter(
        id=f"{volume_slug}-master-study-legend",
        title="Interactive Study Key & Legend",
        is_front_matter=True,
        blocks=blocks,
    )


def enrich_books_master_study(
    books: list[Book],
    is_bible: bool,
    enable_comparisons: bool,
    enable_onomasticon: bool,
    enable_citations: bool,
    onomasticon_entries: dict[str, OnomasticonEntry] | None = None,
    citations_by_urn: dict[str, tuple[str, list[HistoricalCitationRecord]]] | None = None,
    comparisons_by_urn: dict[str, VerseComparison] | None = None,
    excerpt_index: DiscourseExcerptIndex | None = None,
    link_resolver: ScriptureResolverMap | None = None,
    is_combined_edition: bool = False,
) -> None:
    """Enrich a list of canonical `Book` objects in-place with parallel comparisons, Onomasticon, and citations."""
    if link_resolver is None:
        link_resolver = build_scripture_link_resolver(books)

    onoma_regex: re.Pattern[str] | None = None
    if enable_onomasticon and onomasticon_entries:
        # Sort names longest first so substrings aren't prematurely replaced
        sorted_names = sorted(onomasticon_entries.keys(), key=len, reverse=True)
        pattern_str = r"\b(" + "|".join(re.escape(n) for n in sorted_names) + r")\b"
        onoma_regex = re.compile(pattern_str, re.I)

    for book in books:
        for ch in book.chapters:
            ch_annotations: list[Annotation] = list(ch.annotations)
            seen_names_in_chapter: set[str] = set()
            cite_counter = 0

            for v in ch.verses:
                raw_text = v.text
                disp_cite_label = v.citation_label or f"{book.title} {ch.number}:{v.verse}"

                # 1. Onomasticon enrichment on text
                def _enrich_text(txt: str) -> str:
                    escaped = escape_xhtml(txt, smart_typography=False)
                    if not enable_onomasticon or onoma_regex is None or onomasticon_entries is None:
                        return escaped

                    def _replace_name(match: re.Match[str]) -> str:
                        word = match.group(0)
                        if not word[0].isupper():
                            return word
                        key = word.lower()
                        if key in seen_names_in_chapter or key not in onomasticon_entries:
                            return word

                        seen_names_in_chapter.add(key)
                        entry = onomasticon_entries[key]
                        ann_id = f"{ch.id}-onoma-{key}"

                        header_parts = [f"◈ {escape_xhtml(entry.name_upper, smart_typography=False)}"]
                        if entry.ipa:
                            header_parts.append(f"/{escape_xhtml(entry.ipa, smart_typography=False)}/")
                        if entry.classifications:
                            header_parts.append(f"({escape_xhtml(', '.join(entry.classifications), smart_typography=False)})")

                        paras = [" • ".join(header_parts)]
                        if entry.hebrew_summary:
                            paras.append(f"Ancient Reconstructions: {escape_xhtml(entry.hebrew_summary, smart_typography=False)}")
                        for etym in entry.etymology_paragraphs[:4]:
                            paras.append(escape_xhtml(etym, smart_typography=False))

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

                verse_html = _enrich_text(raw_text)

                # 2. Parallel Bible Translations & Cross-References ([⇄])
                if is_bible and enable_comparisons and comparisons_by_urn and v.canonical_ref in comparisons_by_urn:
                    comp = comparisons_by_urn[v.canonical_ref]
                    if comp.bsb or comp.asv or comp.bbe or comp.xrefs:
                        comp_ann_id = f"{ch.id}-comp-{v.verse}"
                        c_paras: list[str] = []
                        if comp.bsb:
                            c_paras.append(f"▸ BSB (Berean Standard Bible): “{escape_xhtml(comp.bsb, smart_typography=False)}”")
                        if comp.asv:
                            c_paras.append(f"▸ ASV (American Standard Version 1901): “{escape_xhtml(comp.asv, smart_typography=False)}”")
                        if comp.bbe:
                            c_paras.append(f"▸ BBE (Bible in Basic English): “{escape_xhtml(comp.bbe, smart_typography=False)}”")
                        if comp.xrefs:
                            xrefs_html = linkify_xref_list(comp.xrefs, link_resolver)
                            c_paras.append(f"▸ Key Scriptural Cross-References: {xrefs_html}.")

                        ch_annotations.append(
                            Annotation(
                                id=comp_ann_id,
                                label="⇄",
                                title=f"{disp_cite_label} — Comparative Translations & Cross-References",
                                note_type=AnnotationType.CROSS_REFERENCE,
                                paragraphs=c_paras,
                            )
                        )
                        verse_html = (
                            f"{verse_html} "
                            f'<sup class="fn-sup"><a class="noteref compare-badge" epub:type="noteref" '
                            f'id="ref-{comp_ann_id}" href="#fn-{comp_ann_id}">[⇄]</a></sup>'
                        )

                # 3. Historical Citation Index Badges ([★ N])
                if enable_citations and citations_by_urn and v.canonical_ref in citations_by_urn:
                    disp_cite, recs = citations_by_urn[v.canonical_ref]
                    if recs:
                        cite_counter += 1
                        total_c = len(recs)
                        cite_ann_id = f"{ch.id}-cite-{cite_counter}"

                        jod_c = sum(1 for r in recs if r.corpus == "J")
                        tpjs_c = sum(1 for r in recs if r.corpus == "T")
                        sp_counts = Counter(r.speaker for r in recs if r.speaker)
                        top_sp = ", ".join(f"{s} ({c}×)" for s, c in sp_counts.most_common(4))

                        # Sort citations chronologically (oldest first: TPJS 1830–1844 -> early JoD -> late JoD)
                        def _cite_sort_key(r: HistoricalCitationRecord) -> tuple[int, int, int, int]:
                            eff_y = r.year if (r.year and r.year > 0) else (1838 if r.corpus == "T" else 1900)
                            return (
                                eff_y,
                                0 if r.corpus == "T" else 1,
                                0 if "Joseph Smith" in r.speaker else 1,
                                r.citation_id,
                            )

                        sorted_recs = sorted(recs, key=_cite_sort_key)
                        header_recs = sorted_recs[:8]
                        ref_strs = []
                        for r in header_recs:
                            year_str = f", {r.year}" if (r.year and r.year > 0) else ""
                            ref_strs.append(f"{r.speaker} ({r.source_citation}{year_str})")
                        ref_line = "; ".join(ref_strs)
                        if len(sorted_recs) > 8:
                            ref_line += f"; and {len(sorted_recs) - 8} more"

                        c_paras = [
                            f"Cited {total_c} {'time' if total_c == 1 else 'times'} (1830–1886 Public Domain) — "
                            f"Journal of Discourses: {jod_c} | TPJS: {tpjs_c}.",
                            f"Frequent Citing Speakers: {escape_xhtml(top_sp, smart_typography=False)}.",
                            f"Primary References: {escape_xhtml(ref_line, smart_typography=False)}.",
                        ]
                        if excerpt_index is not None:
                            if is_combined_edition:
                                # User formula for Combined Standard Works edition:
                                # total_citations // 10 to a maximum of 3 citations
                                # (<10: 0 excerpts; 10–19: 1 excerpt; 20–29: 2 excerpts; 30+: 3 excerpts)
                                max_ex = min(total_c // 10, 3)
                            else:
                                # Individual editions: up to 6 excerpts, oldest first
                                max_ex = min(total_c, 6)
                            rep_recs = select_representative_citations(sorted_recs, max_excerpts=max_ex) if max_ex > 0 else []
                            for rep in rep_recs:
                                ex_paras = excerpt_index.extract_excerpt_paragraphs(rep.citation_id, rep.talk_id)
                                if ex_paras:
                                    year_part = f", {rep.year}" if (rep.year and rep.year > 0) else ""
                                    c_paras.append(
                                        f"▸ Discourse Excerpt — {escape_xhtml(rep.speaker, smart_typography=False)}, “{escape_xhtml(rep.title, smart_typography=False)}” ({escape_xhtml(rep.source_citation, smart_typography=False)}{year_part}):"
                                    )
                                    for ep in ex_paras:
                                        linked_ep = linkify_scripture_references(ep, link_resolver)
                                        c_paras.append(f"“{linked_ep}”")

                        ch_annotations.append(
                            Annotation(
                                id=cite_ann_id,
                                label=f"★{total_c}",
                                title=f"{disp_cite} — Historical Citations",
                                note_type=AnnotationType.CITATION,
                                paragraphs=c_paras,
                            )
                        )
                        sep = "" if "[⇄]" in verse_html else " "
                        verse_html = (
                            f"{verse_html}{sep}"
                            f'<sup class="fn-sup"><a class="noteref cite-badge" epub:type="noteref" '
                            f'id="ref-{cite_ann_id}" href="#fn-{cite_ann_id}">[★{total_c}]</a></sup>'
                        )

                if verse_html != escape_xhtml(raw_text, smart_typography=False):
                    v.html_text = verse_html

            ch.annotations = ch_annotations


def build_master_study_edition(volume_slug: str) -> Work:
    """Build an individual Master Study EPUB3 edition for any canonical Standard Work volume."""
    base_slug = volume_slug.replace("-master-study", "")
    if base_slug not in VOLUME_CONFIGS:
        raise ValueError(f"Unknown volume '{volume_slug}'. Valid: {list(VOLUME_CONFIGS)}")

    cfg = VOLUME_CONFIGS[base_slug]
    work = deepcopy(ingest_standard_work(base_slug))
    work.id = cfg["slug"]
    work.title = cfg["title"]
    work.subtitle = cfg["subtitle"]
    work.edition_label = cfg["edition_label"]
    work.description = cfg["desc"]
    work.css_theme = "enriched.css"

    is_bible = base_slug in ("old-testament", "new-testament")
    enable_comparisons = is_bible
    enable_onomasticon = base_slug in ("book-of-mormon", "pearl-of-great-price", "doctrine-and-covenants")
    enable_citations = True

    comparisons_by_urn = load_bible_comparisons() if enable_comparisons else None
    onomasticon_entries = load_onomasticon_entries() if enable_onomasticon else None
    citations_by_urn = load_citations_by_canonical_ref() if enable_citations else None
    excerpt_index = get_discourse_excerpt_index() if enable_citations else None

    # Insert study guide legend at beginning of front matter
    legend = _create_master_study_legend_chapter(
        volume_slug=work.id,
        enable_comparisons=enable_comparisons,
        enable_onomasticon=enable_onomasticon,
        enable_citations=enable_citations,
    )
    work.front_matter.insert(0, legend)

    enrich_books_master_study(
        books=work.books,
        is_bible=is_bible,
        enable_comparisons=enable_comparisons,
        enable_onomasticon=enable_onomasticon,
        enable_citations=enable_citations,
        onomasticon_entries=onomasticon_entries,
        citations_by_urn=citations_by_urn,
        comparisons_by_urn=comparisons_by_urn,
        excerpt_index=excerpt_index,
    )

    return work


def build_master_study_old_testament() -> Work:
    """Build The Old Testament (Master Study Edition)."""
    return build_master_study_edition("old-testament")


def build_master_study_new_testament() -> Work:
    """Build The New Testament (Master Study Edition)."""
    return build_master_study_edition("new-testament")


def build_master_study_book_of_mormon() -> Work:
    """Build The Book of Mormon (Master Study Edition)."""
    return build_master_study_edition("book-of-mormon")


def build_master_study_doctrine_and_covenants() -> Work:
    """Build The Doctrine and Covenants (Master Study Edition)."""
    return build_master_study_edition("doctrine-and-covenants")


def build_master_study_pearl_of_great_price() -> Work:
    """Build The Pearl of Great Price (Master Study Edition)."""
    return build_master_study_edition("pearl-of-great-price")


def build_master_study_standard_works() -> Work:
    """Build the grand combined Master Study Standard Works (all 5 canonical volumes united)."""
    work_id = "lds-standard-works-master-study"

    comparisons_by_urn = load_bible_comparisons()
    onomasticon_entries = load_onomasticon_entries()
    citations_by_urn = load_citations_by_canonical_ref()
    excerpt_index = get_discourse_excerpt_index()

    volume_order = [
        ("old-testament", True, False),
        ("new-testament", True, False),
        ("book-of-mormon", False, True),
        ("doctrine-and-covenants", False, True),
        ("pearl-of-great-price", False, True),
    ]

    combined_books: list[Book] = []
    volume_slices: list[tuple[int, int, bool, bool]] = []

    for v_slug, is_bible, is_restoration in volume_order:
        base_w = deepcopy(ingest_standard_work(v_slug))
        start_idx = len(combined_books)
        combined_books.extend(base_w.books)
        end_idx = len(combined_books)
        volume_slices.append((start_idx, end_idx, is_bible, is_restoration))

    # Grand combined link resolver across all 87 canonical books
    combined_resolver = build_scripture_link_resolver(combined_books)

    for start_idx, end_idx, is_bible, is_restoration in volume_slices:
        enrich_books_master_study(
            books=combined_books[start_idx:end_idx],
            is_bible=is_bible,
            enable_comparisons=is_bible,
            enable_onomasticon=is_restoration,
            enable_citations=True,
            onomasticon_entries=onomasticon_entries,
            citations_by_urn=citations_by_urn,
            comparisons_by_urn=comparisons_by_urn,
            excerpt_index=excerpt_index,
            link_resolver=combined_resolver,
            is_combined_edition=True,
        )

    legend = _create_master_study_legend_chapter(
        volume_slug=work_id,
        enable_comparisons=True,
        enable_onomasticon=True,
        enable_citations=True,
    )

    intro_chapter = Chapter(
        id=f"{work_id}-preface",
        title="Preface to the Master Study Standard Works",
        is_front_matter=True,
        blocks=[
            ContentBlock(
                block_type=BlockType.HEADING,
                text="The Standard Works of The Church of Jesus Christ of Latter-day Saints",
                level=2,
            ),
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=(
                    "This comprehensive Master Study Edition unites all five books of the Latter-day Saint "
                    "scriptural canon—the Holy Bible (Old and New Testaments), the Book of Mormon, the "
                    "Doctrine and Covenants, and the Pearl of Great Price—into a single digital volume (87 books, "
                    "1,582 chapters, 41,995 verses) optimized for Kindle Paperwhite e-readers and mobile devices."
                ),
            ),
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=(
                    "Every biblical verse is equipped with instant parallel translation comparison badges ([⇄]) "
                    "featuring the Berean Standard Bible (BSB), the American Standard Version (ASV 1901), the "
                    "Bible in Basic English (BBE), and curated cross-references from the Treasury of Scripture "
                    "Knowledge and OpenBible. Restoration scriptures feature BYU Onomasticon Hebrew, Semitic, "
                    "and Egyptian etymological pop-ups (◈). Across the entire canon, 19,364 cited verses carry "
                    "historical discourse badges ([★ N]) documenting their usage in pre-1942 sermons by "
                    "Latter-day prophets and apostles with extended primary source excerpts."
                ),
            ),
        ],
    )

    return Work(
        id=work_id,
        title="The Standard Works (Master Study Edition)",
        subtitle="Uniting Parallel Translations (BSB • ASV • BBE), BYU Onomasticon Etymologies & 19th-Century Discourse Citations",
        description=(
            "The complete five-volume Latter-day Saint scriptural canon (Old Testament, New Testament, "
            "Book of Mormon, Doctrine and Covenants, and Pearl of Great Price) in an integrated Master Study "
            "edition. Features parallel biblical translations (BSB, ASV, BBE), scriptural cross-references, "
            "BYU Onomasticon linguistic etymologies (◈), and 19th-century sermon citation analytics ([★ N])."
        ),
        authors=["Proteus Scriptural Publishing Engine", "King James Translators & Prophets of the Restoration"],
        edition_label="Proteus Relational Master Study Edition",
        css_theme="enriched.css",
        front_matter=[intro_chapter, legend],
        books=combined_books,
    )

