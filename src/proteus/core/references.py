"""Canonical Scripture Reference & Slug Resolver.

Standardizes book names, abbreviations, slugs, and verse URN keys across:
- LDS Standard Works (`scriptures-json-master`)
- Historical Book of Mormon editions (`bom-editions-main`)
- BYU Scripture Citation Index (`scripture-citation/books.json`)
- BYU Book of Mormon Onomasticon (`onomasticon`)
- KJV Apocrypha / Deuterocanon & Pseudepigrapha (`apocrypha`, `extra-canon`, `gutenberg-apocrypha`)
"""

from __future__ import annotations

import re

# Map canonical book names to (volume_code, book_slug)
CANONICAL_BOOKS: dict[str, tuple[str, str]] = {
    # Old Testament
    "Genesis": ("ot", "gen"),
    "Exodus": ("ot", "ex"),
    "Leviticus": ("ot", "lev"),
    "Numbers": ("ot", "num"),
    "Deuteronomy": ("ot", "deut"),
    "Joshua": ("ot", "josh"),
    "Judges": ("ot", "judg"),
    "Ruth": ("ot", "ruth"),
    "1 Samuel": ("ot", "1-sam"),
    "2 Samuel": ("ot", "2-sam"),
    "1 Kings": ("ot", "1-kgs"),
    "2 Kings": ("ot", "2-kgs"),
    "1 Chronicles": ("ot", "1-chr"),
    "2 Chronicles": ("ot", "2-chr"),
    "Ezra": ("ot", "ezra"),
    "Nehemiah": ("ot", "neh"),
    "Esther": ("ot", "esth"),
    "Job": ("ot", "job"),
    "Psalms": ("ot", "ps"),
    "Psalm": ("ot", "ps"),
    "Proverbs": ("ot", "prov"),
    "Ecclesiastes": ("ot", "eccl"),
    "Song of Solomon": ("ot", "song"),
    "Isaiah": ("ot", "isa"),
    "Jeremiah": ("ot", "jer"),
    "Lamentations": ("ot", "lam"),
    "Ezekiel": ("ot", "ezek"),
    "Daniel": ("ot", "dan"),
    "Hosea": ("ot", "hosea"),
    "Joel": ("ot", "joel"),
    "Amos": ("ot", "amos"),
    "Obadiah": ("ot", "obad"),
    "Jonah": ("ot", "jonah"),
    "Micah": ("ot", "micah"),
    "Nahum": ("ot", "nahum"),
    "Habakkuk": ("ot", "hab"),
    "Zephaniah": ("ot", "zeph"),
    "Haggai": ("ot", "hag"),
    "Zechariah": ("ot", "zech"),
    "Malachi": ("ot", "mal"),
    # New Testament
    "Matthew": ("nt", "matt"),
    "Mark": ("nt", "mark"),
    "Luke": ("nt", "luke"),
    "John": ("nt", "john"),
    "Acts": ("nt", "acts"),
    "Romans": ("nt", "rom"),
    "1 Corinthians": ("nt", "1-cor"),
    "2 Corinthians": ("nt", "2-cor"),
    "Galatians": ("nt", "gal"),
    "Ephesians": ("nt", "eph"),
    "Philippians": ("nt", "philip"),
    "Colossians": ("nt", "col"),
    "1 Thessalonians": ("nt", "1-thes"),
    "2 Thessalonians": ("nt", "2-thes"),
    "1 Timothy": ("nt", "1-tim"),
    "2 Timothy": ("nt", "2-tim"),
    "Titus": ("nt", "titus"),
    "Philemon": ("nt", "philem"),
    "Hebrews": ("nt", "heb"),
    "James": ("nt", "james"),
    "1 Peter": ("nt", "1-pet"),
    "2 Peter": ("nt", "2-pet"),
    "1 John": ("nt", "1-jn"),
    "2 John": ("nt", "2-jn"),
    "3 John": ("nt", "3-jn"),
    "Jude": ("nt", "jude"),
    "Revelation": ("nt", "rev"),
    # Book of Mormon
    "1 Nephi": ("bofm", "1-ne"),
    "2 Nephi": ("bofm", "2-ne"),
    "Jacob": ("bofm", "jacob"),
    "Enos": ("bofm", "enos"),
    "Jarom": ("bofm", "jarom"),
    "Omni": ("bofm", "omni"),
    "Words of Mormon": ("bofm", "w-of-m"),
    "Mosiah": ("bofm", "mosiah"),
    "Alma": ("bofm", "alma"),
    "Helaman": ("bofm", "hel"),
    "3 Nephi": ("bofm", "3-ne"),
    "4 Nephi": ("bofm", "4-ne"),
    "Mormon": ("bofm", "morm"),
    "Ether": ("bofm", "ether"),
    "Moroni": ("bofm", "moro"),
    # Doctrine and Covenants
    "Doctrine and Covenants": ("dc", "dc"),
    "D&C": ("dc", "dc"),
    "Official Declaration": ("dc", "od"),
    # Pearl of Great Price
    "Moses": ("pgp", "moses"),
    "Abraham": ("pgp", "abr"),
    "Joseph Smith–Matthew": ("pgp", "js-m"),
    "Joseph Smith—Matthew": ("pgp", "js-m"),
    "Joseph Smith-Matthew": ("pgp", "js-m"),
    "JS–Matthew": ("pgp", "js-m"),
    "Joseph Smith–History": ("pgp", "js-h"),
    "Joseph Smith—History": ("pgp", "js-h"),
    "Joseph Smith-History": ("pgp", "js-h"),
    "JS–History": ("pgp", "js-h"),
    "Articles of Faith": ("pgp", "a-of-f"),
    # KJV Apocrypha / Deuterocanon
    "1 Esdras": ("apoc", "1-esd"),
    "The First Book of Esdras": ("apoc", "1-esd"),
    "2 Esdras": ("apoc", "2-esd"),
    "The Second Book of Esdras": ("apoc", "2-esd"),
    "Tobit": ("apoc", "tob"),
    "Tobias": ("apoc", "tob"),
    "The Book of Tobit": ("apoc", "tob"),
    "Judith": ("apoc", "jdt"),
    "The Book of Judith": ("apoc", "jdt"),
    "Additions to Esther": ("apoc", "add-esth"),
    "Rest of Esther": ("apoc", "add-esth"),
    "The Greek Additions to Esther": ("apoc", "add-esth"),
    "Wisdom of Solomon": ("apoc", "wis"),
    "Wisdom": ("apoc", "wis"),
    "The Book of Wisdom": ("apoc", "wis"),
    "Wisdom of Jesus Son of Sirach": ("apoc", "sir"),
    "Sirach": ("apoc", "sir"),
    "Ecclesiasticus": ("apoc", "sir"),
    "The Book of Sirach (Ecclesiasticus)": ("apoc", "sir"),
    "Baruch": ("apoc", "bar"),
    "The Book of Baruch": ("apoc", "bar"),
    "Letter of Jeremiah": ("apoc", "ep-jer"),
    "Epistle of Jeremiah": ("apoc", "ep-jer"),
    "The Epistle of Jeremiah": ("apoc", "ep-jer"),
    "Prayer of Azariah": ("apoc", "pr-azar"),
    "The Song of the Three Holy Children": ("apoc", "pr-azar"),
    "Susanna": ("apoc", "sus"),
    "The Book of Susanna": ("apoc", "sus"),
    "Bel and the Dragon": ("apoc", "bel"),
    "The History of the Destruction of Bel and the Dragon": ("apoc", "bel"),
    "Prayer of Manasseh": ("apoc", "pr-man"),
    "The Prayer of Manasses King of Judah": ("apoc", "pr-man"),
    "1 Maccabees": ("apoc", "1-macc"),
    "The First Book of the Maccabees": ("apoc", "1-macc"),
    "2 Maccabees": ("apoc", "2-macc"),
    "The Second Book of the Maccabees": ("apoc", "2-macc"),
}


def slugify(value: str) -> str:
    """Convert any title or identifier into a clean lowercase ASCII hyphenated slug."""
    cleaned = value.replace("\ufffd", "-")
    cleaned = re.sub(r"[^\w\s-]", "", cleaned.lower())
    cleaned = re.sub(r"[\s_]+", "-", cleaned).strip("-")
    return cleaned or "item"


def normalize_book_name(raw_name: str) -> str:
    """Fix upstream mojibake (such as 'Joseph Smith\\ufffdMatthew') and standardize book names."""
    fixed = raw_name.replace("\ufffd", "–").strip()
    if fixed == "D&C":
        return "Doctrine and Covenants"
    if fixed == "Psalm":
        return "Psalms"
    return fixed


def make_canonical_ref(book: str, chapter: int | str, verse: int | str | None = None) -> str:
    """Generate a standardized URN reference like 'bofm:1-ne:3:7' or 'apoc:tob:1:1'."""
    norm_book = normalize_book_name(book)
    if norm_book in CANONICAL_BOOKS:
        vol, bk_slug = CANONICAL_BOOKS[norm_book]
    else:
        vol, bk_slug = "work", slugify(norm_book)

    if verse is not None:
        return f"{vol}:{bk_slug}:{chapter}:{verse}"
    return f"{vol}:{bk_slug}:{chapter}"

