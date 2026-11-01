"""Ingesters and normalizers for Biblical Apocrypha / Deuterocanon and Pseudepigrapha.

Combines the cleanest upstream sources across:
- `data/raw/extra-canon/` (15 KJV Deuterocanonical books with zero hard line-wraps)
- `data/raw/apocrypha/` (ISTA R.H. Charles *1 Enoch*, *Jubilees* with 925 scholarly notes, *Jasher*, *Forgotten Books of Eden*, *Lost Books of the Bible*)
- `data/raw/gutenberg-apocrypha/` (Richard Laurence's 105-chapter *1 Enoch* translation)
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
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
from proteus.core.references import make_canonical_ref, slugify
from proteus.core.typography import clean_prose_text, escape_xhtml


KJV_APOCRYPHA_ORDER: list[tuple[str, str, str]] = [
    ("1_esdras.jsonl", "1 Esdras", "The First Book of Esdras"),
    ("2_esdras.jsonl", "2 Esdras", "The Second Book of Esdras"),
    ("tobit.jsonl", "Tobit", "The Book of Tobit"),
    ("judith.jsonl", "Judith", "The Book of Judith"),
    ("additions_to_esther.jsonl", "Additions to Esther", "The Rest of the Chapters of the Book of Esther"),
    ("wisdom_of_solomon.jsonl", "Wisdom of Solomon", "The Wisdom of Solomon"),
    ("wisdom_of_jesus_son_of_sirach.jsonl", "Sirach", "The Wisdom of Jesus the Son of Sirach, or Ecclesiasticus"),
    ("baruch.jsonl", "Baruch", "The Book of Baruch"),
    ("letter_of_jeremiah.jsonl", "Letter of Jeremiah", "The Epistle of Jeremy"),
    ("prayer_of_azariah.jsonl", "Prayer of Azariah", "The Song of the Three Holy Children"),
    ("susanna.jsonl", "Susanna", "The History of Susanna"),
    ("bel_and_the_dragon.jsonl", "Bel and the Dragon", "The History of the Destruction of Bel and the Dragon"),
    ("prayer_of_manasseh.jsonl", "Prayer of Manasseh", "The Prayer of Manasses King of Juda"),
    ("1_maccabees.jsonl", "1 Maccabees", "The First Book of the Maccabees"),
    ("2_maccabees.jsonl", "2 Maccabees", "The Second Book of the Maccabees"),
]


def ingest_kjv_apocrypha(
    extra_canon_dir: Path = Path("data/raw/kjv-apocrypha"),
) -> Work:
    """Build the complete 15-book King James Version Apocrypha / Deuterocanon."""
    books: list[Book] = []

    for filename, short_title, full_title in KJV_APOCRYPHA_ORDER:
        fpath = extra_canon_dir / filename
        if not fpath.exists():
            continue

        by_chapter: dict[int, list[dict]] = defaultdict(list)
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    by_chapter[int(rec["chapter"])].append(rec)

        bk_slug = slugify(short_title)
        chapters: list[Chapter] = []
        multi_ch = len(by_chapter) > 1

        for ch_num in sorted(by_chapter.keys()):
            v_records = sorted(by_chapter[ch_num], key=lambda r: int(r["verse"]))
            verses: list[Verse] = []
            for vr in v_records:
                v_num = int(vr["verse"])
                v_text = clean_prose_text(vr["text"])
                verses.append(
                    Verse(
                        verse=v_num,
                        text=v_text,
                        canonical_ref=make_canonical_ref(short_title, ch_num, v_num),
                        citation_label=f"{short_title} {ch_num}:{v_num}",
                    )
                )

            chapters.append(
                Chapter(
                    id=f"{bk_slug}-ch-{ch_num}",
                    number=ch_num if multi_ch else None,
                    title=f"Chapter {ch_num}" if multi_ch else short_title,
                    verses=verses,
                )
            )

        books.append(
            Book(
                id=bk_slug,
                title=short_title,
                full_title=full_title,
                chapters=chapters,
            )
        )

    intro_chapter = Chapter(
        id="kjv-apocrypha-editorial-note",
        title="Editorial Note to the Apocrypha",
        is_front_matter=True,
        blocks=[
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=clean_prose_text(
                    "This volume presents the complete fifteen Deuterocanonical and Apocryphal books "
                    "originally translated for the 1611 Authorized King James Version of the Holy Bible. "
                    "In Latter-day Saint scripture, Doctrine and Covenants Section 91 instructs that the "
                    "Apocrypha 'is mostly translated correctly; There are many things contained therein that "
                    "are true, and it is mostly translated correctly... Therefore, whoso readeth it, let him "
                    "understand, for the Spirit manifesteth truth.'"
                ),
            )
        ],
    )

    return Work(
        id="kjv-apocrypha",
        title="The Apocrypha",
        subtitle="The Fifteen Deuterocanonical Books of the Authorized King James Version",
        authors=["King James Version Translators (1611)"],
        edition_label="Proteus Critical Reading Edition",
        description=(
            "Complete collection of the 15 Old Testament Apocryphal / Deuterocanonical books "
            "in the classic King James Version translation, formatted for Kindle Enhanced Typesetting."
        ),
        subjects=["Bible. O.T. Apocrypha", "Deuterocanonical works", "Latter-day Saint scripture study"],
        front_matter=[intro_chapter],
        books=books,
    )


def _attach_ista_footnotes_to_paragraphs(
    paragraphs: list[str],
    raw_footnotes: list[str],
    chapter_slug: str,
) -> tuple[list[ContentBlock], list[Annotation]]:
    """Parse ISTA footnotes (like `ix:1 Note text...` or `47:2 Note text...`) into `Annotation` objects
    and wire inline `<a epub:type="noteref">` callouts into the matching paragraph text.
    """
    annotations: list[Annotation] = []
    fn_by_num: dict[str, list[Annotation]] = defaultdict(list)

    for idx, raw_fn in enumerate(raw_footnotes, start=1):
        # Match patterns like "ix:1 ...", "47:2 ...", "[1] ...", or "1. ..."
        m = re.match(r"^(?:[ivxlcdmIVXLCDM0-9]+:(\d+)|\[(\d+)\]|(\d+)\.)\s*(.+)$", raw_fn.strip(), re.DOTALL)
        if m:
            fn_num = m.group(1) or m.group(2) or m.group(3) or str(idx)
            fn_body = clean_prose_text(m.group(4))
        else:
            fn_num = str(idx)
            fn_body = clean_prose_text(raw_fn)

        ann_id = f"{chapter_slug}-fn-{idx}"
        ann = Annotation(
            id=ann_id,
            label=fn_num,
            note_type=AnnotationType.FOOTNOTE,
            paragraphs=[fn_body],
        )
        annotations.append(ann)
        fn_by_num[fn_num].append(ann)

    blocks: list[ContentBlock] = []
    used_ann_ids: set[str] = set()

    for p_idx, p_raw in enumerate(paragraphs):
        p_clean = clean_prose_text(p_raw)
        if not p_clean:
            continue

        # Escape for XHTML first
        html_p = escape_xhtml(p_raw)

        # If there are unused footnotes for this chapter, check for standalone inline markers in ISTA text
        # ISTA often leaves ` 1 ` or `[1]` in text where a footnote callout stood
        if annotations:
            for fn_num, ann_list in list(fn_by_num.items()):
                if not ann_list:
                    continue
                # Look for `[fn_num]` or standalone ` fn_num ` not at the very beginning of a verse
                pattern = re.compile(rf"(?:\[{re.escape(fn_num)}\]|(?<=[a-zA-Z.,;”’])\s+{re.escape(fn_num)}(?=\s+[a-zA-Z“‘]))")
                if pattern.search(html_p):
                    ann = ann_list.pop(0)
                    used_ann_ids.add(ann.id)
                    callout = (
                        f'<sup class="fn-sup"><a class="noteref" epub:type="noteref" '
                        f'id="ref-{ann.id}" href="#fn-{ann.id}">[{ann.label}]</a></sup>'
                    )
                    html_p = pattern.sub(callout, html_p, count=1)

        blocks.append(
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=p_clean,
                html_text=html_p if html_p != escape_xhtml(p_raw) else None,
            )
        )

    # For any remaining footnotes whose inline number wasn't matched by regex, append a clean note reference bar
    # at the end of the final paragraph so every `<aside epub:type="footnote">` has a valid `noteref` trigger!
    unlinked = [a for a in annotations if a.id not in used_ann_ids]
    if unlinked and blocks:
        ref_links = " ".join(
            f'<sup class="fn-sup"><a class="noteref" epub:type="noteref" id="ref-{a.id}" href="#fn-{a.id}">[{a.label}]</a></sup>'
            for a in unlinked
        )
        last_block = blocks[-1]
        base_html = last_block.html_text or escape_xhtml(last_block.text)
        last_block.html_text = f"{base_html} {ref_links}"

    return blocks, annotations


def ingest_ista_jsonl_book(
    jsonl_path: Path,
    book_id: str,
    book_title: str,
    full_title: str | None = None,
    author: str | None = None,
) -> Book:
    """Ingest an ISTA Apocrypha/Pseudepigrapha `.jsonl` file into a normalized `Book`."""
    chapters: list[Chapter] = []
    front_matter: list[Chapter] = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    for idx, rec in enumerate(records, start=1):
        ch_title = clean_prose_text(rec.get("chapter_title") or f"Section {idx}")
        ch_slug = f"{book_id}-sec-{idx:03d}"
        raw_paras: list[str] = rec.get("paragraphs", [])
        raw_verses: list[dict] = rec.get("verses", [])
        raw_fns: list[str] = rec.get("footnotes", [])

        # Strip duplicate heading paragraph if paragraphs[0] merely repeats the chapter_title or headings
        headings_set = {clean_prose_text(h).lower() for h in rec.get("headings", [])}
        headings_set.add(ch_title.lower())
        filtered_paras: list[str] = []
        for p in raw_paras:
            if clean_prose_text(p).lower() in headings_set and len(filtered_paras) == 0:
                continue
            filtered_paras.append(p)

        is_fm = (
            len(chapters) == 0
            and any(
                kw in ch_title.lower()
                for kw in ["introduction", "preface", "title", "prologue", "front", "abbreviations", "versions", "date", "authorship"]
            )
            and idx <= 15
            and len(raw_verses) < 5
        )

        # Prefer structured verses when the chapter is primarily verse-numbered (e.g. Book of Jasher)
        if len(raw_verses) >= 5 and len(raw_verses) >= len(filtered_paras) * 0.7 and not raw_fns:
            verses = [
                Verse(
                    verse=v["verse"],
                    text=clean_prose_text(v["text"]),
                    canonical_ref=f"pseud:{book_id}:{rec.get('chapter', idx)}:{v['verse']}",
                    citation_label=f"{book_title} {rec.get('chapter', idx)}:{v['verse']}",
                )
                for v in raw_verses
            ]
            ch_obj = Chapter(
                id=ch_slug,
                number=rec.get("chapter"),
                title=ch_title,
                is_front_matter=is_fm,
                verses=verses,
                source_url=rec.get("source_url"),
            )
        else:
            blocks, annotations = _attach_ista_footnotes_to_paragraphs(
                filtered_paras if filtered_paras else [rec.get("text", "")],
                raw_fns,
                ch_slug,
            )
            ch_obj = Chapter(
                id=ch_slug,
                number=rec.get("chapter"),
                title=ch_title,
                is_front_matter=is_fm,
                blocks=blocks,
                annotations=annotations,
                source_url=rec.get("source_url"),
            )

        if is_fm:
            front_matter.append(ch_obj)
        else:
            chapters.append(ch_obj)

    return Book(
        id=book_id,
        title=book_title,
        full_title=full_title or book_title,
        author=author,
        front_matter=front_matter,
        chapters=chapters,
    )


def ingest_gutenberg_enoch_laurence(
    jsonl_path: Path = Path("data/raw/apocrypha-gutenberg/book_of_enoch_laurence.jsonl"),
) -> Book:
    """Ingest Archbishop Richard Laurence's 105-chapter 1883 translation of *The Book of Enoch*."""
    front_matter: list[Chapter] = []
    chapters: list[Chapter] = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    for idx, rec in enumerate(records, start=1):
        sec_title = clean_prose_text(rec.get("section_title") or f"Section {idx}")
        ch_slug = f"enoch-laurence-{idx:03d}"
        paras = [clean_prose_text(p) for p in rec.get("paragraphs", []) if clean_prose_text(p)]
        if paras and paras[0].lower() == sec_title.lower():
            paras = paras[1:]

        is_fm = not sec_title.upper().startswith("CHAP")
        blocks = [ContentBlock(block_type=BlockType.PARAGRAPH, text=p) for p in paras]
        ch = Chapter(
            id=ch_slug,
            title=sec_title,
            is_front_matter=is_fm,
            blocks=blocks,
        )
        if is_fm:
            front_matter.append(ch)
        else:
            chapters.append(ch)

    return Book(
        id="enoch-laurence",
        title="The Book of Enoch the Prophet (Laurence Translation)",
        full_title="The Book of Enoch the Prophet: Translated from an Ethiopic MS. in the Bodleian Library",
        author="Archbishop Richard Laurence (1883)",
        front_matter=front_matter,
        chapters=chapters,
    )


def ingest_patriarchs_and_prophets_apocrypha(
    apocrypha_dir: Path = Path("data/raw/apocrypha-ista"),
    gutenberg_dir: Path = Path("data/raw/apocrypha-gutenberg"),
) -> Work:
    """Compile the major Old Testament Pseudepigrapha & Apocryphal Patriarchs Collection:
    1. The Book of Enoch (1 Enoch — R. H. Charles Critical Edition)
    2. The Book of Enoch the Prophet (1 Enoch — Richard Laurence 1883 Edition)
    3. The Book of Jubilees (R. H. Charles Edition with full scholarly pop-up footnotes)
    4. The Book of Jasher (Complete 91-chapter Midrashic History)
    """
    enoch_charles = ingest_ista_jsonl_book(
        apocrypha_dir / "book_of_enoch_charles.jsonl",
        book_id="enoch-charles",
        book_title="The Book of Enoch (R. H. Charles Edition)",
        full_title="The Book of Enoch (1 Enoch): Translated from the Ethiopic by R. H. Charles (1917)",
        author="R. H. Charles, D.Litt., D.D.",
    )
    enoch_laurence = ingest_gutenberg_enoch_laurence(gutenberg_dir / "book_of_enoch_laurence.jsonl")
    jubilees = ingest_ista_jsonl_book(
        apocrypha_dir / "book_of_jubilees.jsonl",
        book_id="book-of-jubilees",
        book_title="The Book of Jubilees",
        full_title="The Book of Jubilees, or the Little Genesis: Translated from the Ethiopic by R. H. Charles",
        author="R. H. Charles, D.Litt., D.D.",
    )
    jasher = ingest_ista_jsonl_book(
        apocrypha_dir / "book_of_jasher.jsonl",
        book_id="book-of-jasher",
        book_title="The Book of Jasher",
        full_title="The Book of Jasher: Referred to in Joshua and Second Samuel (1840 M. M. Noah / Gould Edition)",
        author="Mordecai M. Noah & A. S. Gould (1840)",
    )

    intro = Chapter(
        id="apocryphal-patriarchs-intro",
        title="Editorial Introduction",
        is_front_matter=True,
        blocks=[
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=clean_prose_text(
                    "This omnibus volume gathers four foundational works of Old Testament Pseudepigrapha "
                    "and patriarchal literature of deep historical and scriptural interest: "
                    "R. H. Charles's 1917 critical edition of The Book of Enoch (1 Enoch), "
                    "Archbishop Richard Laurence's landmark 1821/1883 translation of The Book of Enoch the Prophet, "
                    "R. H. Charles's annotated edition of The Book of Jubilees ('The Little Genesis') complete with "
                    "interactive pop-up footnotes, and the 91-chapter Book of Jasher published in New York in 1840."
                ),
            )
        ],
    )

    return Work(
        id="enoch-jubilees-jasher",
        title="Enoch, Jubilees & Jasher",
        subtitle="The Apocryphal Patriarchs Collection (Critical & Historical Editions)",
        authors=["R. H. Charles", "Richard Laurence", "Mordecai M. Noah"],
        edition_label="Proteus Annotated Omnibus Edition",
        description=(
            "Complete omnibus of 1 Enoch (both Charles and Laurence translations), The Book of Jubilees "
            "with scholarly pop-up footnotes, and The Book of Jasher."
        ),
        subjects=["Pseudepigrapha", "Book of Enoch", "Book of Jubilees", "Book of Jasher"],
        front_matter=[intro],
        books=[enoch_charles, enoch_laurence, jubilees, jasher],
    )

