"""Canonical Pydantic v2 data schemas for Proteus.

Every upstream corpus (Standard Works, historical BoM printings, Apocrypha,
Pseudepigrapha, historical LDS literature, Onomasticon, and BYU Citation Index)
normalizes into these core models before any transformation or EPUB rendering.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class BlockType(str, Enum):
    """Semantic classification of a structural block within a chapter/section."""
    PARAGRAPH = "paragraph"
    VERSE = "verse"
    HEADING = "heading"
    SUBHEADING = "subheading"
    HEADNOTE = "headnote"
    BLOCKQUOTE = "blockquote"
    POETRY = "poetry"
    SIGNATURE = "signature"
    DIVIDER = "divider"
    TABLE = "table"
    CALLOUT = "callout"


class AnnotationType(str, Enum):
    """Type of pop-up footnote, endnote, or relational study note."""
    FOOTNOTE = "footnote"
    ENDNOTE = "endnote"
    CROSS_REFERENCE = "cross_reference"
    ONOMASTICON = "onomasticon"
    CITATION = "citation"
    VARIANT = "variant"


class Annotation(BaseModel):
    """A semantic footnote, endnote, or study pop-up note.

    Renders in EPUB3 as:
      - Callout: `<a class="noteref" epub:type="noteref" id="ref-{id}" href="#fn-{id}">{label}</a>`
      - Target:  `<aside class="footnote" epub:type="footnote" id="fn-{id}">...</aside>`
    """
    id: str = Field(..., description="Unique HTML-safe identifier within the document/chapter")
    label: str = Field(..., description="Visible callout marker, e.g. '1', 'a', '†', or name")
    note_type: AnnotationType = Field(default=AnnotationType.FOOTNOTE)
    title: str | None = Field(default=None, description="Optional bold title for study/endnote pop-ups")
    paragraphs: list[str] = Field(
        default_factory=list,
        description="Clean plain-text or inline-HTML paragraphs comprising the note body",
    )
    target_ref: str | None = Field(
        default=None,
        description="Canonical scripture reference or verse ID this note attaches to, if applicable",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class Verse(BaseModel):
    """A single canonical or apocryphal numbered verse."""
    verse: int | str = Field(..., description="Verse number or label (e.g. 1, 2, '1a')")
    text: str = Field(..., description="Clean normalized text of the verse")
    html_text: str | None = Field(
        default=None,
        description="Optional XHTML-enriched text (e.g. with inline noteref links, red-letter spans, or diffs)",
    )
    canonical_ref: str | None = Field(
        default=None,
        description="Standardized URN reference, e.g. 'bofm:1-ne:3:7' or 'ot:gen:1:26'",
    )
    citation_label: str | None = Field(
        default=None,
        description="Human-readable citation, e.g. '1 Nephi 3:7'",
    )
    annotations: list[Annotation] = Field(default_factory=list)


class ContentBlock(BaseModel):
    """A structural block of prose, poetry, heading, or grouped verses."""
    block_type: BlockType = Field(default=BlockType.PARAGRAPH)
    text: str = Field(default="", description="Plain text content of the block")
    html_text: str | None = Field(
        default=None,
        description="Optional inline-XHTML content (preserving <em>, <strong>, <a epub:type='noteref'>, etc.)",
    )
    level: int = Field(default=2, description="Heading level (2-4) when block_type is HEADING/SUBHEADING")
    verse_numbers: list[int | str] = Field(
        default_factory=list,
        description="Verse numbers consolidated into this paragraph block (for narrative editions)",
    )
    annotations: list[Annotation] = Field(default_factory=list)


class Chapter(BaseModel):
    """A single chapter, section, lecture, or treatise unit."""
    id: str = Field(..., description="Unique slug/identifier for this chapter")
    number: int | str | None = Field(default=None, description="Chapter or section number, if numbered")
    title: str = Field(..., description="Display title of the chapter (e.g. 'Chapter 1', 'Lecture I')")
    subtitle: str | None = Field(default=None, description="Optional subtitle or thematic heading")
    headnote: str | None = Field(default=None, description="Optional chapter summary or historical headnote")
    is_front_matter: bool = Field(default=False, description="True for prefaces, introductions, testimonies")
    verses: list[Verse] = Field(
        default_factory=list,
        description="Ordered list of discrete verses (for verse-structured scripture)",
    )
    blocks: list[ContentBlock] = Field(
        default_factory=list,
        description="Ordered list of prose/structural blocks (for non-verse works or narrative transforms)",
    )
    annotations: list[Annotation] = Field(
        default_factory=list,
        description="Chapter-level footnotes and endnotes rendered as <aside epub:type='footnote'>",
    )
    source_url: str | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def word_count(self) -> int:
        if self.blocks:
            return sum(len(b.text.split()) for b in self.blocks)
        return sum(len(v.text.split()) for v in self.verses)


class Book(BaseModel):
    """A distinct book within a volume (e.g. '1 Nephi', 'Tobit', or a standalone work in an anthology)."""
    id: str = Field(..., description="Unique slug for the book, e.g. '1-nephi' or 'jesus-the-christ'")
    title: str = Field(..., description="Short canonical title, e.g. '1 Nephi' or 'Jesus the Christ'")
    full_title: str | None = Field(
        default=None,
        description="Formal long title, e.g. 'The First Book of Nephi: His Reign and Ministry'",
    )
    subtitle: str | None = Field(default=None)
    author: str | None = Field(default=None, description="Author or translator of this specific book")
    heading: str | None = Field(default=None, description="Introductory book colophon or headnote")
    front_matter: list[Chapter] = Field(
        default_factory=list,
        description="Book-specific prefaces, introductions, or testimonies",
    )
    chapters: list[Chapter] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_words(self) -> int:
        fm_words = sum(c.word_count for c in self.front_matter)
        ch_words = sum(c.word_count for c in self.chapters)
        return fm_words + ch_words


class Work(BaseModel):
    """Top-level publishable volume or anthology ready for EPUB3 compilation."""
    id: str = Field(..., description="Unique volume identifier slug, e.g. 'kjv-apocrypha'")
    title: str = Field(..., description="Primary volume title")
    subtitle: str | None = Field(default=None)
    authors: list[str] = Field(default_factory=lambda: ["Proteus Publishing Pipeline"])
    language: str = Field(default="en")
    publisher: str = Field(default="Proteus Press")
    publication_date: str = Field(default="2026-10-31")
    rights: str = Field(default="Public Domain in the United States.")
    description: str | None = Field(default=None)
    edition_label: str | None = Field(default=None, description="e.g. '1830 Palmyra Edition', 'KFX Study Edition'")
    subjects: list[str] = Field(default_factory=list)
    front_matter: list[Chapter] = Field(
        default_factory=list,
        description="Volume-level front matter (Title Page, Prefaces, Testimonies, Editorial Introduction)",
    )
    books: list[Book] = Field(default_factory=list)
    css_theme: str = Field(default="classic.css", description="CSS theme filename in renderers/epub/styles/")
    images: dict[str, bytes] = Field(
        default_factory=dict,
        description="Additional PNG images keyed by filename inside OEBPS/images/ (e.g. 'fig_01.png')",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_words(self) -> int:
        fm_words = sum(c.word_count for c in self.front_matter)
        bk_words = sum(b.total_words for b in self.books)
        return fm_words + bk_words

    @property
    def total_chapters(self) -> int:
        return len(self.front_matter) + sum(len(b.front_matter) + len(b.chapters) for b in self.books)

