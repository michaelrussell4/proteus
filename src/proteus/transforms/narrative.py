"""Canonical Text-Transformation Filters for Phase 2 Reading & Study Editions.

Provides:
1. Continuous Narrative Paragraph Reconstruction (`transform_to_continuous_narrative`)
   - Reassembles discrete canonical verses into flowing literary paragraphs
   - Detects epistolary salutations, narrative transitions ("And it came to pass", "And now, behold"),
     chronological shifts ("And thus ended the ... year"), and terminal punctuation (`;`, `,`, `:` vs `.`, `!`, `?`)
   - Optionally embeds subtle inline verse range badges or pop-up verse locator notes
2. Minimalist Clean Scripture Transformation (`transform_to_minimalist`)
   - Strips verse numbers and modern editorial clutter while preserving clean paragraph/verse cadence
3. Wide-Margin / Study Notebook Transformation (`transform_to_study_notebook`)
   - Prepares structured two-column / wide-margin annotation blocks with ruled note spaces per passage
"""

from __future__ import annotations

import re
from copy import deepcopy

from proteus.core.models import (
    Annotation,
    AnnotationType,
    BlockType,
    Book,
    Chapter,
    ContentBlock,
    Work,
)
from proteus.core.typography import escape_xhtml, lowercase_continuation_start


# Discourse & narrative transition patterns that naturally open a new literary paragraph
# when the preceding verse ended with terminal sentence punctuation (`.`, `!`, `?`, `”`)
NARRATIVE_BREAK_PATTERNS: list[re.Pattern[str]] = [
    # Chronological / annalistic markers
    re.compile(r"^(?:And\s+)?thus\s+ended\s+the\s+", re.I),
    re.compile(r"^(?:And\s+)?in\s+the\s+[\w\s-]+year\s+of\s+the\s+reign\s+of\s+the\s+judges", re.I),
    re.compile(r"^(?:And\s+)?it\s+came\s+to\s+pass\s+in\s+the\s+[\w\s-]+year", re.I),
    # Major speaker / discourse shifts
    re.compile(r"^Now\s+these\s+are\s+the\s+words\s+", re.I),
    re.compile(r"^And\s+now\s+it\s+came\s+to\s+pass\s+", re.I),
    re.compile(r"^Now\s+it\s+came\s+to\s+pass\s+", re.I),
    re.compile(r"^And\s+now,\s+(?:my\s+beloved\s+brethren|behold|my\s+son)", re.I),
    re.compile(r"^Behold,\s+my\s+beloved\s+brethren", re.I),
    re.compile(r"^O\s+then,\s+my\s+beloved\s+brethren", re.I),
    re.compile(r"^Wherefore,\s+my\s+beloved\s+brethren", re.I),
    re.compile(r"^Hearken,\s+O\s+ye\s+", re.I),
    re.compile(r"^Verily,\s+thus\s+saith\s+the\s+Lord", re.I),
    # Epistolary salutations
    re.compile(r"^(?:My\s+dearly\s+beloved\s+brother|Beloved\s+brother|Behold,\s+I\s+Moroni|I,\s+Nephi,|I,\s+Mormon,|I,\s+Jacob,|I,\s+Enos,|Now\s+I,\s+Jarom,|Behold,\s+it\s+came\s+to\s+pass\s+that\s+I,\s+Omni)", re.I),
]

CONTINUATION_ENDINGS = (";", ",", ":", "—", "–", "-")


def _should_start_new_paragraph(
    prev_text: str,
    curr_text: str,
    verses_in_current_para: int,
    words_in_current_para: int,
) -> bool:
    """Heuristic deciding whether `curr_text` begins a new literary paragraph or continues the current one."""
    prev_stripped = prev_text.rstrip(" ”’\"')")
    if not prev_stripped:
        return True

    # Rule 1: Never break a sentence mid-clause! If the previous verse ended with `;`, `,`, `:`, or `—`,
    # the next verse MUST continue in the same paragraph (crucial for 1830 BoM and Paul/D&C clauses).
    if prev_stripped.endswith(CONTINUATION_ENDINGS):
        return False

    # Rule 2: If the current verse begins with a lowercase letter (common in 1830 BoM mid-sentence verse splits),
    # it is a continuation of the previous verse.
    first_alpha = re.search(r"[A-Za-z]", curr_text)
    if first_alpha and first_alpha.group(0).islower():
        return False

    # Rule 3: Explicit discourse / chronological / epistolary transition markers always start a new paragraph
    for pat in NARRATIVE_BREAK_PATTERNS:
        if pat.search(curr_text):
            return True

    # Rule 4: "And it came to pass" starts a new paragraph once the current paragraph has at least 2 verses or 65 words
    if re.match(r"^And\s+it\s+came\s+to\s+pass\b", curr_text, re.I):
        if verses_in_current_para >= 2 or words_in_current_para >= 65:
            return True

    # Rule 5: Natural paragraph cadence — if a paragraph has reached ~120+ words (or 4+ verses)
    # and the previous verse ended with a full stop, start a fresh paragraph on transitional conjunctions
    if words_in_current_para >= 115 or verses_in_current_para >= 4:
        if re.match(r"^(?:And\s+now|Now|Wherefore|Therefore|Behold|Nevertheless|But\s+behold|Then|Thus)\b", curr_text, re.I):
            return True

    # Rule 6: Cap maximum paragraph size around ~185 words if previous verse ended with a full stop
    if words_in_current_para >= 185:
        return True

    return False


def _chapter_verses_to_narrative_blocks(
    chapter: Chapter,
    include_subtle_verse_range_popups: bool = True,
) -> tuple[list[ContentBlock], list[Annotation]]:
    """Group `chapter.verses` into natural literary `ContentBlock` paragraphs."""
    if not chapter.verses:
        return list(chapter.blocks), list(chapter.annotations)

    blocks: list[ContentBlock] = []
    annotations: list[Annotation] = list(chapter.annotations)

    curr_texts: list[str] = []
    curr_vnums: list[int | str] = []
    curr_citations: list[str] = []
    curr_words = 0

    def _flush_paragraph(para_idx: int) -> None:
        nonlocal curr_texts, curr_vnums, curr_citations, curr_words
        if not curr_texts:
            return
        parts: list[str] = [curr_texts[0]]
        for nxt in curr_texts[1:]:
            prev_strip = parts[-1].rstrip(" ”’\"')")
            if prev_strip.endswith(("—", ";", ",")):
                nxt = lowercase_continuation_start(nxt)
            if parts[-1].endswith("—"):
                parts[-1] = parts[-1] + nxt
            else:
                parts.append(nxt)
        combined_text = " ".join(parts)
        html_str: str | None = None

        if include_subtle_verse_range_popups and curr_vnums:
            v_start = curr_vnums[0]
            v_end = curr_vnums[-1]
            range_label = f"{v_start}" if v_start == v_end else f"{v_start}–{v_end}"
            ann_id = f"{chapter.id}-p-{para_idx}"
            cite_title = curr_citations[0] if v_start == v_end else f"{curr_citations[0]}–{v_end}"
            ann = Annotation(
                id=ann_id,
                label=range_label,
                title=cite_title,
                note_type=AnnotationType.FOOTNOTE,
                paragraphs=[
                    f"Canonical Reference: {cite_title} ({len(curr_vnums)} {'verse' if len(curr_vnums) == 1 else 'verses'})."
                ],
            )
            annotations.append(ann)

            # Dropcap on very first paragraph of the chapter
            escaped = escape_xhtml(combined_text, smart_typography=False)
            if para_idx == 1 and len(escaped) > 1:
                # Wrap first letter in dropcap span
                m = re.match(r"^([“‘\"']?[A-Za-z])(.*)$", escaped, re.DOTALL)
                if m:
                    escaped = f'<span class="dropcap">{m.group(1)}</span>{m.group(2)}'

            html_str = (
                f"{escaped} "
                f'<sup class="fn-sup verse-range-sup"><a class="noteref verse-range-ref" '
                f'epub:type="noteref" id="ref-{ann_id}" href="#fn-{ann_id}">[{range_label}]</a></sup>'
            )

        blocks.append(
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=combined_text,
                html_text=html_str,
                verse_numbers=list(curr_vnums),
            )
        )
        curr_texts = []
        curr_vnums = []
        curr_citations = []
        curr_words = 0

    para_counter = 0
    for v in chapter.verses:
        v_text = v.text.strip()
        if not v_text:
            continue

        if curr_texts and _should_start_new_paragraph(
            curr_texts[-1], v_text, len(curr_texts), curr_words
        ):
            para_counter += 1
            _flush_paragraph(para_counter)

        curr_texts.append(v_text)
        curr_vnums.append(v.verse)
        curr_citations.append(v.citation_label or f"{chapter.title}:{v.verse}")
        curr_words += len(v_text.split())

    if curr_texts:
        para_counter += 1
        _flush_paragraph(para_counter)

    return blocks, annotations


def transform_to_continuous_narrative(
    work: Work,
    edition_id_suffix: str = "narrative",
    include_verse_range_popups: bool = True,
    consolidate_chapters_per_book: bool = False,
) -> Work:
    """Transform a verse-structured `Work` into a Continuous Narrative Reader's Edition.

    - Reassembles discrete verses into natural literary paragraphs.
    - Strips disruptive inline verse numbers from the start of every sentence.
    - Optionally attaches a subtle `[1–4]` pop-up badge at the end of each paragraph so the reader
      can tap it to see the exact canonical chapter:verse reference in a Kindle modal pop-up.
    """
    out = deepcopy(work)
    out.id = f"{work.id}-{edition_id_suffix}"
    out.title = f"{work.title} (Continuous Narrative Edition)"
    out.edition_label = "Proteus Continuous Narrative Reader’s Edition"
    out.css_theme = "narrative.css"

    for book in out.books:
        if consolidate_chapters_per_book and len(book.chapters) > 1:
            # Combine chapters into a single continuous book flow with subtle section dividers
            merged_blocks: list[ContentBlock] = []
            merged_annotations: list[Annotation] = []
            for ch_idx, ch in enumerate(book.chapters, start=1):
                if ch_idx > 1:
                    merged_blocks.append(
                        ContentBlock(
                            block_type=BlockType.SUBHEADING,
                            text=f"§ {ch.number or ch_idx}",
                            level=3,
                        )
                    )
                ch_blocks, ch_anns = _chapter_verses_to_narrative_blocks(
                    ch, include_subtle_verse_range_popups=include_verse_range_popups
                )
                merged_blocks.extend(ch_blocks)
                merged_annotations.extend(ch_anns)

            book.chapters = [
                Chapter(
                    id=f"{book.id}-continuous",
                    title=book.title,
                    blocks=merged_blocks,
                    annotations=merged_annotations,
                )
            ]
        else:
            for ch in book.chapters:
                ch_blocks, ch_anns = _chapter_verses_to_narrative_blocks(
                    ch, include_subtle_verse_range_popups=include_verse_range_popups
                )
                ch.blocks = ch_blocks
                ch.annotations = ch_anns
                ch.verses = []
                # Strip editorial chapter headnotes in pure narrative mode
                ch.headnote = None

    return out


def transform_to_minimalist(
    work: Work,
    strip_verse_numbers: bool = False,
    strip_headnotes: bool = True,
) -> Work:
    """Transform a `Work` into a clean, simple Edition (super-clean typography, chapters and verse
    numbers preserved, canonical front matter & witnesses preserved, zero footnotes or extra editorial apparatus).
    """
    out = deepcopy(work)
    out.id = f"{work.id}-minimalist"
    out.title = work.title
    out.edition_label = None
    out.css_theme = "minimalist.css"
    for fm_ch in out.front_matter:
        fm_ch.annotations = []

    for book in out.books:
        book.front_matter = []
        if strip_headnotes:
            book.heading = None
        for ch in book.chapters:
            ch.annotations = []
            if strip_headnotes:
                ch.headnote = None
            if strip_verse_numbers and ch.verses:
                ch_blocks, _ = _chapter_verses_to_narrative_blocks(
                    ch, include_subtle_verse_range_popups=False
                )
                ch.blocks = ch_blocks
                ch.verses = []
            else:
                for v in ch.verses:
                    v.html_text = None

    return out


def transform_to_study_notebook(work: Work) -> Work:
    """Transform a `Work` into a Wide-Margin / Study Notebook Edition optimized for Kindle Paperwhite & Scribe."""
    out = deepcopy(work)
    out.id = f"{work.id}-study-notebook"
    out.title = f"{work.title} (Wide-Margin Study Edition)"
    out.edition_label = "Proteus Wide-Margin Study & Annotation Edition"
    out.css_theme = "study.css"
    return out


def combine_works_into_quad(works: list[Work], compact_book_chapters: bool = False) -> Work:
    """Combine all five Standard Works (Old Testament, New Testament, Book of Mormon,
    Doctrine and Covenants, and Pearl of Great Price) into a single clean Quad Edition
    with all chapters, verse numbers, and Book of Mormon Witnesses preserved individually
    for direct TOC navigation and zero editorial clutter.
    """
    all_books: list[Book] = []
    for w in works:
        clean_wid = w.id.replace("-minimalist", "")
        for b_idx, b in enumerate(w.books):
            b_copy = deepcopy(b)
            b_copy.id = f"{clean_wid}-{b.id}"
            if b_idx == 0 and w.front_matter:
                b_copy.front_matter = deepcopy(w.front_matter)
                for fm_ch in b_copy.front_matter:
                    fm_ch.annotations = []
            else:
                b_copy.front_matter = []
            b_copy.heading = None
            if not b_copy.subtitle:
                b_copy.subtitle = w.title

            for ch in b_copy.chapters:
                ch.annotations = []
                ch.headnote = None
                for v in ch.verses:
                    v.html_text = None

            all_books.append(b_copy)

    return Work(
        id="lds-standard-works-minimalist",
        title="The Standard Works",
        subtitle="The Old Testament • The New Testament • The Book of Mormon • The Doctrine and Covenants • The Pearl of Great Price",
        authors=["The Church of Jesus Christ of Latter-day Saints"],
        edition_label=None,
        description=(
            "The complete Standard Works: The Old Testament, The New Testament, "
            "The Book of Mormon, The Doctrine and Covenants, and The Pearl of Great Price, "
            "with chapters and verse numbers preserved in clean, distraction-free typography."
        ),
        books=all_books,
        css_theme="minimalist.css",
    )

