"""Narrative (Reader's Edition) transformation for the Latter-day Saint Standard Works.

Converts verse-per-line chapters into flowing, paragraph-structured prose with subtle
inline superscript verse numbers, preserving all front matter, chapter headnotes,
and canonical structure while keeping mid-sentence continuations seamless.
"""

from __future__ import annotations

from copy import deepcopy
import html
import re

from proteus.core.models import BlockType, Book, Chapter, ContentBlock, Verse, Work
from proteus.core.typography import lowercase_continuation_start
from proteus.ingest.standard_works import ingest_standard_work

# Sentence-ending punctuation (optionally followed by closing quotes/parens)
_SENTENCE_END_RE = re.compile(r'[.?!]["”’\')\]]*$')

# Discourse / narrative transition openers that naturally begin a new paragraph
_STRONG_PARA_OPENERS_RE = re.compile(
    r"^(?:"
    r"(?:And|Now|Wherefore,?|Therefore,?)\s+it\s+came\s+to\s+pass\b|"
    r"(?:And\s+)?[Aa]fter\s+these\s+things\b|"
    r"(?:And\s+)?[Ii]n\s+(?:the\s+beginning|those\s+days|that\s+(?:day|same\s+day|hour|season)|the\s+\w+\s+year)\b|"
    r"Now\s+(?:when|after|in\s+the|behold|I\b|it\b|there\b|these\b)|"
    r"Thus\s+saith\s+the\s+Lord\b|"
    r"Verily,?\s+verily,?\s+I\s+say\s+unto\s+you\b|"
    r"(?:Hearken|Listen),?\s+O\b"
    r")"
)

_MEDIUM_PARA_OPENERS_RE = re.compile(
    r"^(?:"
    r"And\s+now\b|"
    r"(?:Wherefore|Therefore|Moreover|Behold|Again|Then),?\s|"
    r"And\s+(?:the\s+Lord|God|Jesus|he|she|they)\s+(?:said|spake|answered)\b|"
    r"For\s+behold\b"
    r")"
)

_MIN_WORDS_BEFORE_SOFT_BREAK = 45
_SOFT_MAX_WORDS_PER_PARA = 135


def _ends_sentence(text: str) -> bool:
    """Return True if `text` ends with terminal sentence punctuation."""
    return bool(_SENTENCE_END_RE.search(text.rstrip()))


def _ends_with_em_dash_continuation(text: str) -> bool:
    """Return True if `text` ends with an em-dash continuing mid-sentence."""
    stripped = text.rstrip(" ”’\"')")
    return stripped.endswith("—") and not _ends_sentence(stripped[:-1])


def _is_paragraph_break(
    prev_text: str,
    next_text: str,
    para_verses: int,
    para_words: int,
) -> bool:
    """Decide whether to start a new narrative paragraph before `next_text`."""
    if not _ends_sentence(prev_text):
        return False

    # Speaker turn: previous verse ended a quotation and next opens a new sentence/quote
    prev_closed_quote = prev_text.rstrip().endswith(("”", "’", '"'))
    next_opens_quote = next_text.lstrip().startswith(("“", "‘", '"'))
    if prev_closed_quote and (next_opens_quote or _MEDIUM_PARA_OPENERS_RE.match(next_text)):
        return True

    if para_words >= _SOFT_MAX_WORDS_PER_PARA:
        return True

    if para_verses >= 2 and para_words >= _MIN_WORDS_BEFORE_SOFT_BREAK:
        if _STRONG_PARA_OPENERS_RE.match(next_text):
            return True

    if para_verses >= 3 and para_words >= 75:
        if _MEDIUM_PARA_OPENERS_RE.match(next_text):
            return True

    return False


def _verses_to_narrative_blocks(verses: list[Verse]) -> list[ContentBlock]:
    """Group a chapter's verses into natural narrative paragraphs with inline verse numbers."""
    if not verses:
        return []

    paragraphs: list[list[tuple[int | str, str]]] = []
    current_group: list[tuple[int | str, str]] = []
    current_words = 0
    prev_raw_text = ""

    for v in verses:
        v_text = v.text
        if current_group and _ends_with_em_dash_continuation(prev_raw_text):
            v_text = lowercase_continuation_start(v_text)

        if current_group and _is_paragraph_break(
            prev_raw_text,
            v_text,
            len(current_group),
            current_words,
        ):
            paragraphs.append(current_group)
            current_group = []
            current_words = 0

        current_group.append((v.verse, v_text))
        current_words += len(v_text.split())
        prev_raw_text = v.text

    if current_group:
        paragraphs.append(current_group)

    blocks: list[ContentBlock] = []
    for group in paragraphs:
        plain_parts: list[str] = []
        html_parts: list[str] = []
        v_nums: list[int | str] = []
        for idx, (v_num, v_txt) in enumerate(group):
            v_nums.append(v_num)
            plain_parts.append(v_txt)
            escaped = html.escape(v_txt, quote=False)
            num_span = f'<span class="verse-num" id="v-{v_num}">{v_num}</span>'
            if idx > 0 and _ends_with_em_dash_continuation(group[idx - 1][1]):
                # Join directly after em-dash without extra space before verse number
                html_parts[-1] = html_parts[-1] + num_span + escaped
            else:
                html_parts.append(f"{num_span}{escaped}")

        blocks.append(
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=" ".join(plain_parts),
                html_text=" ".join(html_parts),
                verse_numbers=v_nums,
            )
        )
    return blocks


def _convert_chapters_to_narrative(chapters: list[Chapter]) -> None:
    """Convert verse-list chapters into paragraph-block chapters in place."""
    for ch in chapters:
        if ch.verses:
            ch.blocks = _verses_to_narrative_blocks(ch.verses) + ch.blocks
            ch.verses = []


def _convert_books_to_narrative(books: list[Book]) -> None:
    """Convert all chapters across `books` to narrative paragraph blocks in place."""
    for bk in books:
        _convert_chapters_to_narrative(bk.front_matter)
        _convert_chapters_to_narrative(bk.chapters)


def _create_narrative_guide_chapter(work_id: str, scope_label: str) -> Chapter:
    """Create a concise front-matter reading note explaining the Narrative Edition format."""
    return Chapter(
        id=f"{work_id}-narrative-note",
        title="About This Narrative Edition",
        is_front_matter=True,
        blocks=[
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=(
                    f"This Narrative Edition presents {scope_label} in continuous, "
                    "paragraph-structured prose rather than one-verse-per-line formatting. "
                    "Paragraph breaks follow natural narrative shifts, speaker turns, and discourse "
                    "transitions, while mid-sentence em-dash continuations flow seamlessly across "
                    "verse boundaries."
                ),
            ),
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=(
                    "Subtle inline superscript verse numbers are preserved throughout the paragraphs "
                    "so you can still locate any chapter and verse reference without interrupting "
                    "the flow of reading."
                ),
            ),
        ],
    )


_NARRATIVE_METADATA: dict[str, tuple[str, str, str]] = {
    "old-testament": (
        "The Old Testament: Narrative Edition",
        "The King James Version in Flowing Paragraph Prose",
        "The Old Testament (2013 KJV Standard Works) formatted in continuous narrative paragraphs with subtle inline verse numbers.",
    ),
    "new-testament": (
        "The New Testament: Narrative Edition",
        "The King James Version in Flowing Paragraph Prose",
        "The New Testament (2013 KJV Standard Works) formatted in continuous narrative paragraphs with subtle inline verse numbers.",
    ),
    "book-of-mormon": (
        "The Book of Mormon: Narrative Edition",
        "Another Testament of Jesus Christ — Flowing Paragraph Prose",
        "The Book of Mormon (2013 Standard Works) formatted in continuous narrative paragraphs with subtle inline verse numbers.",
    ),
    "doctrine-and-covenants": (
        "The Doctrine and Covenants: Narrative Edition",
        "Revelations in Flowing Paragraph Prose",
        "The Doctrine and Covenants (2013 Standard Works) formatted in continuous narrative paragraphs with subtle inline verse numbers.",
    ),
    "pearl-of-great-price": (
        "The Pearl of Great Price: Narrative Edition",
        "Ancient & Restoration Scripture in Flowing Paragraph Prose",
        "The Pearl of Great Price (2013 Standard Works) formatted in continuous narrative paragraphs with subtle inline verse numbers.",
    ),
}


def build_narrative_edition(volume_slug: str) -> Work:
    """Build a standalone Narrative Edition for a single Standard Work."""
    if volume_slug not in _NARRATIVE_METADATA:
        raise ValueError(f"Unsupported narrative volume '{volume_slug}'.")

    title, subtitle, desc = _NARRATIVE_METADATA[volume_slug]
    work = deepcopy(ingest_standard_work(volume_slug))
    _convert_books_to_narrative(work.books)

    work_id = f"{volume_slug}-narrative"
    guide = _create_narrative_guide_chapter(work_id, work.title)

    return Work(
        id=work_id,
        title=title,
        subtitle=subtitle,
        authors=work.authors,
        edition_label="Proteus Narrative Edition",
        description=desc,
        subjects=work.subjects + ["Narrative Scripture"],
        front_matter=[guide] + work.front_matter,
        books=work.books,
        css_theme="classic.css",
    )


def build_narrative_old_testament() -> Work:
    """Build The Old Testament: Narrative Edition."""
    return build_narrative_edition("old-testament")


def build_narrative_new_testament() -> Work:
    """Build The New Testament: Narrative Edition."""
    return build_narrative_edition("new-testament")


def build_narrative_book_of_mormon() -> Work:
    """Build The Book of Mormon: Narrative Edition."""
    return build_narrative_edition("book-of-mormon")


def build_narrative_doctrine_and_covenants() -> Work:
    """Build The Doctrine and Covenants: Narrative Edition."""
    return build_narrative_edition("doctrine-and-covenants")


def build_narrative_pearl_of_great_price() -> Work:
    """Build The Pearl of Great Price: Narrative Edition."""
    return build_narrative_edition("pearl-of-great-price")


def build_narrative_standard_works() -> Work:
    """Build the combined Standard Works: Narrative Edition (all 5 volumes)."""
    work_id = "lds-standard-works-narrative"
    volume_order = [
        "old-testament",
        "new-testament",
        "book-of-mormon",
        "doctrine-and-covenants",
        "pearl-of-great-price",
    ]

    combined_books: list[Book] = []
    for v_slug in volume_order:
        base_w = deepcopy(ingest_standard_work(v_slug))
        _convert_books_to_narrative(base_w.books)
        # Preserve Book of Mormon Title Page & Witnesses as front-matter chapters before 1 Nephi
        if v_slug == "book-of-mormon" and base_w.front_matter:
            combined_books.append(
                Book(
                    id="bom-front-matter",
                    title="Book of Mormon Front Matter",
                    full_title="Title Page and Testimonies of the Witnesses",
                    chapters=base_w.front_matter,
                )
            )
        combined_books.extend(base_w.books)

    guide = _create_narrative_guide_chapter(work_id, "all five Latter-day Saint Standard Works")

    return Work(
        id=work_id,
        title="The Standard Works: Narrative Edition",
        subtitle="Old Testament, New Testament, Book of Mormon, Doctrine & Covenants, and Pearl of Great Price in Flowing Prose",
        authors=["The Church of Jesus Christ of Latter-day Saints"],
        edition_label="Proteus Complete Narrative Edition",
        description=(
            "All five Latter-day Saint Standard Works (87 canonical books) unified in a single "
            "paragraph-structured Narrative Edition with subtle inline verse numbers."
        ),
        subjects=["Scriptures", "Standard Works", "Narrative Scripture"],
        front_matter=[guide],
        books=combined_books,
        css_theme="classic.css",
    )
