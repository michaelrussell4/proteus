"""Ingesters for the 2013 LDS Standard Works (`scriptures-json-master`)
and the 8 historical Book of Mormon printings (`bom-editions-main/public/data/en`).
"""

from __future__ import annotations

import json
from pathlib import Path

from proteus.core.models import BlockType, Book, Chapter, ContentBlock, Verse, Work
from proteus.core.references import make_canonical_ref, normalize_book_name, slugify
from proteus.core.typography import clean_prose_text


STANDARD_WORKS_FILES: dict[str, tuple[str, str]] = {
    "book-of-mormon": ("book-of-mormon.json", "The Book of Mormon"),
    "doctrine-and-covenants": ("doctrine-and-covenants.json", "The Doctrine and Covenants"),
    "pearl-of-great-price": ("pearl-of-great-price.json", "The Pearl of Great Price"),
    "old-testament": ("old-testament.json", "The Old Testament"),
    "new-testament": ("new-testament.json", "The New Testament"),
}

HISTORICAL_BOM_YEARS: list[str] = [
    "1830",
    "1837",
    "1840",
    "1841",
    "1879",
    "1920",
    "1981",
    "2013",
]

CANONICAL_BOM_BOOK_ORDER: list[tuple[str, str]] = [
    ("1-nephi", "1 Nephi"),
    ("2-nephi", "2 Nephi"),
    ("jacob", "Jacob"),
    ("enos", "Enos"),
    ("jarom", "Jarom"),
    ("omni", "Omni"),
    ("words-of-mormon", "Words of Mormon"),
    ("mosiah", "Mosiah"),
    ("alma", "Alma"),
    ("helaman", "Helaman"),
    ("3-nephi", "3 Nephi"),
    ("4-nephi", "4 Nephi"),
    ("mormon", "Mormon"),
    ("ether", "Ether"),
    ("moroni", "Moroni"),
]


def ingest_standard_work(
    volume_slug: str,
    raw_dir: Path = Path("data/raw/lds-standard-works"),
) -> Work:
    """Load one of the 5 canonical LDS Standard Works into a normalized `Work`."""
    if volume_slug not in STANDARD_WORKS_FILES:
        raise ValueError(f"Unknown standard work '{volume_slug}'. Valid: {list(STANDARD_WORKS_FILES)}")

    filename, default_title = STANDARD_WORKS_FILES[volume_slug]
    filepath = raw_dir / filename
    data = json.loads(filepath.read_text(encoding="utf-8"))

    title = clean_prose_text(data.get("title") or default_title)
    subtitle = clean_prose_text(data.get("subtitle", "")) or None

    front_matter: list[Chapter] = []

    # Title page block if present
    if "title_page" in data and isinstance(data["title_page"], dict):
        tp = data["title_page"]
        tp_blocks: list[ContentBlock] = []
        if tp.get("title"):
            tp_blocks.append(ContentBlock(block_type=BlockType.HEADING, text=clean_prose_text(tp["title"]), level=2))
        if tp.get("subtitle"):
            tp_blocks.append(ContentBlock(block_type=BlockType.SUBHEADING, text=clean_prose_text(tp["subtitle"]), level=3))
        for p_text in tp.get("text", []) if isinstance(tp.get("text"), list) else [tp.get("text", "")]:
            if p_text:
                tp_blocks.append(ContentBlock(block_type=BlockType.PARAGRAPH, text=clean_prose_text(p_text)))
        if tp.get("translated_by"):
            tp_blocks.append(ContentBlock(block_type=BlockType.SIGNATURE, text=clean_prose_text(tp["translated_by"])))
        if tp_blocks:
            front_matter.append(
                Chapter(
                    id=f"{volume_slug}-title-page",
                    title="Origin & Title Page",
                    is_front_matter=True,
                    blocks=tp_blocks,
                )
            )

    # Testimonies (Book of Mormon)
    for idx, test in enumerate(data.get("testimonies", []), start=1):
        t_title = clean_prose_text(test.get("title", f"Testimony {idx}"))
        t_blocks = [
            ContentBlock(block_type=BlockType.PARAGRAPH, text=clean_prose_text( test.get("text", "") ))
        ]
        for wit in test.get("witnesses", []):
            t_blocks.append(ContentBlock(block_type=BlockType.SIGNATURE, text=clean_prose_text(wit)))
        front_matter.append(
            Chapter(
                id=f"{volume_slug}-testimony-{idx}",
                title=t_title,
                is_front_matter=True,
                blocks=t_blocks,
            )
        )

    books: list[Book] = []

    if "books" in data:
        for b_data in data["books"]:
            b_name = normalize_book_name(b_data["book"])
            b_slug = slugify(b_name)
            b_full = clean_prose_text(b_data.get("full_title", "")) or None
            b_sub = clean_prose_text(b_data.get("subtitle", "")) or None
            b_head = clean_prose_text(b_data.get("heading", "")) or None

            chapters: list[Chapter] = []
            for c_data in b_data.get("chapters", []):
                ch_num = c_data["chapter"]
                ch_head = clean_prose_text(c_data.get("heading", "")) or None
                verses: list[Verse] = []
                for v_data in c_data.get("verses", []):
                    v_num = v_data["verse"]
                    v_text = clean_prose_text(v_data["text"])
                    verses.append(
                        Verse(
                            verse=v_num,
                            text=v_text,
                            canonical_ref=make_canonical_ref(b_name, ch_num, v_num),
                            citation_label=f"{b_name} {ch_num}:{v_num}",
                        )
                    )
                chapters.append(
                    Chapter(
                        id=f"{b_slug}-ch-{ch_num}",
                        number=ch_num,
                        title=f"Chapter {ch_num}" if len(b_data.get("chapters", [])) > 1 else b_name,
                        headnote=ch_head,
                        verses=verses,
                    )
                )

            books.append(
                Book(
                    id=b_slug,
                    title=b_name,
                    full_title=b_full,
                    subtitle=b_sub,
                    heading=b_head,
                    chapters=chapters,
                )
            )
    elif "sections" in data:
        # Doctrine and Covenants
        dc_chapters: list[Chapter] = []
        for s_data in data["sections"]:
            sec_num = s_data["section"]
            verses = [
                Verse(
                    verse=v_data["verse"],
                    text=clean_prose_text(v_data["text"]),
                    canonical_ref=make_canonical_ref("Doctrine and Covenants", sec_num, v_data["verse"]),
                    citation_label=f"D&C {sec_num}:{v_data['verse']}",
                )
                for v_data in s_data.get("verses", [])
            ]
            dc_chapters.append(
                Chapter(
                    id=f"dc-sec-{sec_num}",
                    number=sec_num,
                    title=f"Section {sec_num}",
                    verses=verses,
                )
            )
        books.append(
            Book(
                id="doctrine-and-covenants",
                title="Doctrine and Covenants",
                full_title=title,
                subtitle=subtitle,
                chapters=dc_chapters,
            )
        )

    return Work(
        id=volume_slug,
        title=title,
        subtitle=subtitle,
        authors=["The Church of Jesus Christ of Latter-day Saints"],
        edition_label="2013 Standard Works Edition",
        front_matter=front_matter,
        books=books,
    )


def ingest_bom_historical_edition(
    edition_year: str,
    raw_dir: Path = Path("data/raw/bom-historical-editions/editions"),
) -> Work:
    """Ingest a specific historical Book of Mormon edition (1830-2013) while ignoring Next.js app boilerplate."""
    if edition_year not in HISTORICAL_BOM_YEARS:
        raise ValueError(f"Unsupported BoM edition year '{edition_year}'. Valid: {HISTORICAL_BOM_YEARS}")

    ed_dir = raw_dir / edition_year
    if not ed_dir.exists():
        raise FileNotFoundError(f"Historical BoM directory not found: {ed_dir}")

    books: list[Book] = []
    for book_slug, canonical_name in CANONICAL_BOM_BOOK_ORDER:
        bk_dir = ed_dir / book_slug
        if not bk_dir.exists():
            continue

        ch_files = sorted(bk_dir.glob("*.json"), key=lambda p: int(p.stem))
        chapters: list[Chapter] = []
        for ch_file in ch_files:
            ch_data = json.loads(ch_file.read_text(encoding="utf-8"))
            ch_num = ch_data["chapter"]
            verses: list[Verse] = []
            for v_data in ch_data.get("verses", []):
                v_num = v_data["verse"]
                # Preserve exact historical spelling/punctuation while applying clean curly quotes
                v_text = clean_prose_text(v_data["text"], smart_typography=True)
                verses.append(
                    Verse(
                        verse=v_num,
                        text=v_text,
                        canonical_ref=make_canonical_ref(canonical_name, ch_num, v_num),
                        citation_label=f"{canonical_name} {ch_num}:{v_num}",
                    )
                )
            chapters.append(
                Chapter(
                    id=f"bom-{edition_year}-{book_slug}-ch-{ch_num}",
                    number=ch_num,
                    title=f"Chapter {ch_num}" if len(ch_files) > 1 else canonical_name,
                    verses=verses,
                )
            )
        books.append(
            Book(
                id=book_slug,
                title=canonical_name,
                chapters=chapters,
            )
        )

    return Work(
        id=f"book-of-mormon-{edition_year}",
        title=f"The Book of Mormon ({edition_year} Edition)",
        subtitle="An Account Written by the Hand of Mormon upon Plates Taken from the Plates of Nephi",
        authors=["Joseph Smith Jr. (Translator)"],
        edition_label=f"{edition_year} Historical Printing",
        books=books,
    )

