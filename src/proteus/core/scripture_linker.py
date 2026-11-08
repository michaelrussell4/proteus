"""Proteus Scripture Linker Engine (`scripture_linker.py`).

Provides high-precision parsing, validation, and relative EPUB3 hyperlink resolution for:
1. Curated cross-reference lists (`comp.xrefs` in comparative study badges `[⇄]`).
2. Parenthetical scriptural citations embedded inside 19th-century historical discourse excerpts (`[★ N]`).

Rules & Constraints:
- Relative links follow the deterministic Proteus EPUB3 chapter layout: `bk_{bk_idx:02d}_ch_{ch_idx:03d}.xhtml#v-{verse}`.
- If a referenced book/chapter is not included in the current volume (e.g. D&C cited inside an Old Testament
  edition), the reference is cleanly left as unlinked, XML-escaped text to ensure 0 broken links and 100%
  W3C EPUBCheck compliance.
- In combined multi-volume editions (`lds-standard-works-master-study`), all 87 canonical books are resolved
  across the entire standard works canon.
"""

from __future__ import annotations

import re
from xml.sax.saxutils import escape

from proteus.core.models import Book


# Comprehensive canonical books alias table: Canonical Book Name -> recognized aliases/abbreviations
BOOK_ALIASES: dict[str, list[str]] = {
    # Old Testament (39 books)
    "Genesis": ["Genesis", "Gen.", "Gen", "Ge."],
    "Exodus": ["Exodus", "Exod.", "Exod", "Ex.", "Ex"],
    "Leviticus": ["Leviticus", "Lev.", "Lev", "Le."],
    "Numbers": ["Numbers", "Num.", "Num", "Nu."],
    "Deuteronomy": ["Deuteronomy", "Deut.", "Deut", "De."],
    "Joshua": ["Joshua", "Josh.", "Josh"],
    "Judges": ["Judges", "Judg.", "Judg", "Jdg."],
    "Ruth": ["Ruth", "Rth."],
    "1 Samuel": ["1 Samuel", "1 Sam.", "1 Sam", "1 Sa.", "1Sa"],
    "2 Samuel": ["2 Samuel", "2 Sam.", "2 Sam", "2 Sa.", "2Sa"],
    "1 Kings": ["1 Kings", "1 Kgs.", "1 Kgs", "1 Ki.", "1Ki"],
    "2 Kings": ["2 Kings", "2 Kgs.", "2 Kgs", "2 Ki.", "2Ki"],
    "1 Chronicles": ["1 Chronicles", "1 Chron.", "1 Chron", "1 Chr.", "1 Chr", "1Ch"],
    "2 Chronicles": ["2 Chronicles", "2 Chron.", "2 Chron", "2 Chr.", "2 Chr", "2Ch"],
    "Ezra": ["Ezra", "Ezr."],
    "Nehemiah": ["Nehemiah", "Neh.", "Neh", "Ne."],
    "Esther": ["Esther", "Esth.", "Esth", "Est."],
    "Job": ["Job"],
    "Psalms": ["Psalms", "Psalm", "Ps.", "Ps", "Psa.", "Psa", "Pss."],
    "Proverbs": ["Proverbs", "Prov.", "Prov", "Pr."],
    "Ecclesiastes": ["Ecclesiastes", "Eccles.", "Eccl.", "Eccl", "Ecc."],
    "Song of Solomon": ["Song of Solomon", "Song of Sol.", "Song", "Cant."],
    "Isaiah": ["Isaiah", "Isa.", "Isa", "Is."],
    "Jeremiah": ["Jeremiah", "Jer.", "Jer", "Je."],
    "Lamentations": ["Lamentations", "Lam.", "Lam"],
    "Ezekiel": ["Ezekiel", "Ezek.", "Ezek", "Eze."],
    "Daniel": ["Daniel", "Dan.", "Dan", "Da."],
    "Hosea": ["Hosea", "Hos.", "Hos", "Ho."],
    "Joel": ["Joel", "Joe."],
    "Amos": ["Amos", "Am."],
    "Obadiah": ["Obadiah", "Obad.", "Obad", "Ob."],
    "Jonah": ["Jonah", "Jon.", "Jon"],
    "Micah": ["Micah", "Mic.", "Mic"],
    "Nahum": ["Nahum", "Nah.", "Nah"],
    "Habakkuk": ["Habakkuk", "Hab.", "Hab"],
    "Zephaniah": ["Zephaniah", "Zeph.", "Zeph", "Zep."],
    "Haggai": ["Haggai", "Hag.", "Hag"],
    "Zechariah": ["Zechariah", "Zech.", "Zech", "Zec."],
    "Malachi": ["Malachi", "Mal.", "Mal"],
    # New Testament (27 books)
    "Matthew": ["Matthew", "Matt.", "Matt", "Mat.", "Mt."],
    "Mark": ["Mark", "Mk."],
    "Luke": ["Luke", "Lk.", "Lu."],
    "John": ["John", "Jn.", "Jn", "Jhn."],
    "Acts": ["Acts", "Ac."],
    "Romans": ["Romans", "Rom.", "Rom", "Ro."],
    "1 Corinthians": ["1 Corinthians", "1 Cor.", "1 Cor", "1 Co."],
    "2 Corinthians": ["2 Corinthians", "2 Cor.", "2 Cor", "2 Co."],
    "Galatians": ["Galatians", "Gal.", "Gal", "Ga."],
    "Ephesians": ["Ephesians", "Eph.", "Eph", "Ep."],
    "Philippians": ["Philippians", "Phil.", "Phil", "Php.", "Philip."],
    "Colossians": ["Colossians", "Col.", "Col", "Co."],
    "1 Thessalonians": ["1 Thessalonians", "1 Thess.", "1 Thes.", "1 Thes", "1 Th."],
    "2 Thessalonians": ["2 Thessalonians", "2 Thess.", "2 Thes.", "2 Thes", "2 Th."],
    "1 Timothy": ["1 Timothy", "1 Tim.", "1 Tim", "1 Ti."],
    "2 Timothy": ["2 Timothy", "2 Tim.", "2 Tim", "2 Ti."],
    "Titus": ["Titus", "Tit.", "Tit"],
    "Philemon": ["Philemon", "Philem.", "Philem", "Phm."],
    "Hebrews": ["Hebrews", "Heb.", "Heb", "He."],
    "James": ["James", "Jas.", "Jas", "Jm."],
    "1 Peter": ["1 Peter", "1 Pet.", "1 Pet", "1 Pt."],
    "2 Peter": ["2 Peter", "2 Pet.", "2 Pet", "2 Pt."],
    "1 John": ["1 John", "1 Jn.", "1 Jn", "1 Jhn."],
    "2 John": ["2 John", "2 Jn.", "2 Jn", "2 Jhn."],
    "3 John": ["3 John", "3 Jn.", "3 Jn", "3 Jhn."],
    "Jude": ["Jude", "Jud."],
    "Revelation": ["Revelation", "Rev.", "Rev", "Rv."],
    # Book of Mormon (15 books)
    "1 Nephi": ["1 Nephi", "1 Ne.", "1 Ne", "1Ne"],
    "2 Nephi": ["2 Nephi", "2 Ne.", "2 Ne", "2Ne"],
    "Jacob": ["Jacob", "Jac."],
    "Enos": ["Enos", "En."],
    "Jarom": ["Jarom", "Jar."],
    "Omni": ["Omni", "Om."],
    "Words of Mormon": ["Words of Mormon", "W of M", "W. of M.", "W. of M"],
    "Mosiah": ["Mosiah"],
    "Alma": ["Alma", "Al."],
    "Helaman": ["Helaman", "Hel.", "Hel"],
    "3 Nephi": ["3 Nephi", "3 Ne.", "3 Ne", "3Ne"],
    "4 Nephi": ["4 Nephi", "4 Ne.", "4 Ne", "4Ne"],
    "Mormon": ["Mormon", "Morm.", "Morm"],
    "Ether": ["Ether", "Eth."],
    "Moroni": ["Moroni", "Moro.", "Moro"],
    # Doctrine and Covenants (1 book)
    "Doctrine and Covenants": [
        "Doctrine and Covenants",
        "Doctrine & Covenants",
        "D&C",
        "D. & C.",
        "D. and C.",
        "D & C",
        "DC",
    ],
    # Pearl of Great Price (5 books)
    "Moses": ["Moses"],
    "Abraham": ["Abraham", "Abr.", "Abr"],
    "Joseph Smith—Matthew": [
        "Joseph Smith—Matthew",
        "Joseph Smith–Matthew",
        "Joseph Smith-Matthew",
        "JS—M",
        "JS–M",
        "JS-M",
        "JS—Matt.",
        "JS–Matt.",
        "JS-Matt.",
        "JS—Matt",
        "JS–Matt",
        "JS-Matt",
    ],
    "Joseph Smith—History": [
        "Joseph Smith—History",
        "Joseph Smith–History",
        "Joseph Smith-History",
        "JS—H",
        "JS–H",
        "JS-H",
        "JS—Hist.",
        "JS–Hist.",
        "JS-Hist.",
        "JS—Hist",
        "JS–Hist",
        "JS-Hist",
        "JS—h",
        "JS–h",
        "JS-h",
    ],
    "Articles of Faith": ["Articles of Faith", "A of F", "A. of F.", "A. of F"],
}

# Precompute normalization dictionary: alias -> canonical book title
ALIAS_TO_CANONICAL: dict[str, str] = {}
for _canon, _aliases in BOOK_ALIASES.items():
    ALIAS_TO_CANONICAL[_canon.lower()] = _canon
    for _a in _aliases:
        ALIAS_TO_CANONICAL[_a.lower()] = _canon
        ALIAS_TO_CANONICAL[_a.lower().replace(".", "")] = _canon
        ALIAS_TO_CANONICAL[_a.lower().replace(" ", "")] = _canon
        ALIAS_TO_CANONICAL[_a.lower().replace("—", "-")] = _canon
        ALIAS_TO_CANONICAL[_a.lower().replace("–", "-")] = _canon

# Build high-efficiency regex matching any recognized book alias followed by chapter:verse
_all_alias_strings = sorted(
    {_a for _aliases in BOOK_ALIASES.values() for _a in _aliases} | set(BOOK_ALIASES.keys()),
    key=len,
    reverse=True,
)
_alias_group = "|".join(re.escape(_a) for _a in _all_alias_strings)

SCRIPTURE_REF_PATTERN = re.compile(
    r"\b(" + _alias_group + r")\s+(\d+)[:\.](\d+(?:[–\-]\d+)?(?:,\s*\d+(?:[–\-]\d+)?)*)\b",
    re.IGNORECASE,
)

# Type alias for the link resolver map: (canonical_book_title, chapter_num) -> (xhtml_filename, set_of_valid_verses)
ScriptureResolverMap = dict[tuple[str, int], tuple[str, set[int]]]


def build_scripture_link_resolver(books: list[Book]) -> ScriptureResolverMap:
    """Build a lookup map matching canonical book titles and chapter numbers to their exact EPUB chapter filenames.

    Matches the exact naming formula of `proteus.renderers.epub.builder.EpubBuilder`:
      `bk_{bk_idx:02d}_ch_{ch_idx:03d}.xhtml#v-{verse_number}`
    """
    resolver: ScriptureResolverMap = {}

    for bk_idx, book in enumerate(books, start=1):
        canon_name = ALIAS_TO_CANONICAL.get(
            book.title.lower(),
            ALIAS_TO_CANONICAL.get(book.title.lower().replace("—", "-").replace("–", "-"), book.title),
        )
        for ch_idx, ch in enumerate(book.chapters, start=1):
            ch_filename = f"bk_{bk_idx:02d}_ch_{ch_idx:03d}.xhtml"
            verse_set: set[int] = set()
            for v in ch.verses:
                try:
                    verse_set.add(int(v.verse))
                except (ValueError, TypeError):
                    pass
            resolver[(canon_name, ch.number)] = (ch_filename, verse_set)
            # Also store with ch_idx in case ch.number differs
            resolver[(canon_name, ch_idx)] = (ch_filename, verse_set)

    return resolver


def linkify_scripture_references(text: str, resolver: ScriptureResolverMap) -> str:
    """Parse text for scriptural references and convert available targets into EPUB3 XHTML links.

    - References to books packaged in the current volume resolve to internal offline relative links
      (`bk_{bk_idx:02d}_ch_{ch_idx:03d}.xhtml#v-{verse}`).
    - Cross-volume references in single-volume editions (e.g. 2 Peter cited in an Old Testament volume)
      are cleanly retained as unlinked XML-escaped text to ensure 0 broken links and 100% W3C EPUBCheck
      compliance without external internet dependencies.
    - In combined editions (`lds-standard-works-master-study`), all 87 canonical books are packaged in the
      same volume and resolve to internal offline relative links.
    """
    last_idx = 0
    parts: list[str] = []

    for m in SCRIPTURE_REF_PATTERN.finditer(text):
        # Escape plain text prior to match
        parts.append(escape(text[last_idx:m.start()]))

        raw_bk, ch_str, v_part = m.group(1), m.group(2), m.group(3)
        ch_num = int(ch_str)
        canon = ALIAS_TO_CANONICAL.get(
            raw_bk.lower(),
            ALIAS_TO_CANONICAL.get(raw_bk.lower().replace(".", "").replace("—", "-").replace("–", "-")),
        )

        target = resolver.get((canon, ch_num)) if canon else None
        full_match = m.group(0)

        if not target:
            # Referenced book/chapter is not packaged in this EPUB; retain clean XML-escaped text
            parts.append(escape(full_match))
        else:
            filename, verses = target
            # Support comma-separated additional verses in the same chapter (e.g. "Moses 1:2, 31" or "1 Ne. 2:1-2, 19-20")
            if "," in full_match:
                sub_segments = full_match.split(",")
                first_seg = sub_segments[0].strip()
                m_first_v = re.search(r"[:\.](\d+)", first_seg)
                first_v = int(m_first_v.group(1)) if m_first_v else None
                anchor = f"#v-{first_v}" if (first_v is not None and first_v in verses) else ""
                parts.append(f'<a href="{filename}{anchor}" class="scripture-link">{escape(first_seg)}</a>')

                for sub in sub_segments[1:]:
                    sub_clean = sub.strip()
                    m_sub_v = re.search(r"\b(\d+)", sub_clean)
                    if m_sub_v:
                        sub_v = int(m_sub_v.group(1))
                        sub_anchor = f"#v-{sub_v}" if sub_v in verses else ""
                        parts.append(f', <a href="{filename}{sub_anchor}" class="scripture-link">{escape(sub_clean)}</a>')
                    else:
                        parts.append(f', {escape(sub_clean)}')
            else:
                m_v = re.search(r"(\d+)", v_part)
                first_v = int(m_v.group(1)) if m_v else None
                anchor = f"#v-{first_v}" if (first_v is not None and first_v in verses) else ""
                parts.append(f'<a href="{filename}{anchor}" class="scripture-link">{escape(full_match)}</a>')

        last_idx = m.end()

    parts.append(escape(text[last_idx:]))
    return "".join(parts)


def linkify_xref_list(xrefs: list[str], resolver: ScriptureResolverMap) -> str:
    """Format and linkify a list of cross-references (e.g. `['John 1:1–3', 'Heb 11:3']`)."""
    linked_items: list[str] = []
    for xr in xrefs:
        linked_items.append(linkify_scripture_references(xr, resolver))
    return "; ".join(linked_items)

