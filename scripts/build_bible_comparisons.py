"""Build the compact Bible comparisons dataset for Proteus Master Study Editions.

Extracts verse-aligned text from BSB (Berean Standard Bible), ASV (American Standard Version 1901),
and BBE (Bible in Basic English), along with top OpenBible/TSK cross-references, mapping them
directly to canonical Proteus verse URNs (e.g. 'ot:gen:1:1', 'nt:john:3:16').
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

# Paths to external repositories
BIBLE_DB_DIR = Path(r"C:\Users\Mike\Documents\GitHub\bible_databases")
OUT_DIR = Path("data/raw/bible-comparisons")
OUT_FILE = OUT_DIR / "comparisons.json"

# Map BSB/ASV/BBE book names to Proteus canonical names
NAME_MAP: dict[str, str] = {
    "Genesis": "Genesis",
    "Exodus": "Exodus",
    "Leviticus": "Leviticus",
    "Numbers": "Numbers",
    "Deuteronomy": "Deuteronomy",
    "Joshua": "Joshua",
    "Judges": "Judges",
    "Ruth": "Ruth",
    "I Samuel": "1 Samuel",
    "II Samuel": "2 Samuel",
    "I Kings": "1 Kings",
    "II Kings": "2 Kings",
    "I Chronicles": "1 Chronicles",
    "II Chronicles": "2 Chronicles",
    "Ezra": "Ezra",
    "Nehemiah": "Nehemiah",
    "Esther": "Esther",
    "Job": "Job",
    "Psalms": "Psalms",
    "Proverbs": "Proverbs",
    "Ecclesiastes": "Ecclesiastes",
    "Song of Solomon": "Song of Solomon",
    "Isaiah": "Isaiah",
    "Jeremiah": "Jeremiah",
    "Lamentations": "Lamentations",
    "Ezekiel": "Ezekiel",
    "Daniel": "Daniel",
    "Hosea": "Hosea",
    "Joel": "Joel",
    "Amos": "Amos",
    "Obadiah": "Obadiah",
    "Jonah": "Jonah",
    "Micah": "Micah",
    "Nahum": "Nahum",
    "Habakkuk": "Habakkuk",
    "Zephaniah": "Zephaniah",
    "Haggai": "Haggai",
    "Zechariah": "Zechariah",
    "Malachi": "Malachi",
    "Matthew": "Matthew",
    "Mark": "Mark",
    "Luke": "Luke",
    "John": "John",
    "Acts": "Acts",
    "Romans": "Romans",
    "I Corinthians": "1 Corinthians",
    "II Corinthians": "2 Corinthians",
    "Galatians": "Galatians",
    "Ephesians": "Ephesians",
    "Philippians": "Philippians",
    "Colossians": "Colossians",
    "I Thessalonians": "1 Thessalonians",
    "II Thessalonians": "2 Thessalonians",
    "I Timothy": "1 Timothy",
    "II Timothy": "2 Timothy",
    "Titus": "Titus",
    "Philemon": "Philemon",
    "Hebrews": "Hebrews",
    "James": "James",
    "I Peter": "1 Peter",
    "II Peter": "2 Peter",
    "I John": "1 John",
    "II John": "2 John",
    "III John": "3 John",
    "Jude": "Jude",
    "Revelation of John": "Revelation",
}

# Cross-reference 66 abbreviation mapping
XREF_ABBR_MAP: dict[str, str] = {
    "Gen": "Gen", "Exod": "Ex", "Lev": "Lev", "Num": "Num", "Deut": "Deut",
    "Josh": "Josh", "Judg": "Judg", "Ruth": "Ruth", "1Sam": "1 Sam", "2Sam": "2 Sam",
    "1Kgs": "1 Kgs", "2Kgs": "2 Kgs", "1Chr": "1 Chr", "2Chr": "2 Chr",
    "Ezra": "Ezra", "Neh": "Neh", "Esth": "Esth", "Job": "Job", "Ps": "Ps",
    "Prov": "Prov", "Eccl": "Eccl", "Song": "Song", "Isa": "Isa",
    "Jer": "Jer", "Lam": "Lam", "Ezek": "Ezek", "Dan": "Dan", "Hos": "Hos",
    "Joel": "Joel", "Amos": "Amos", "Obad": "Obad", "Jonah": "Jonah", "Mic": "Mic",
    "Nah": "Nah", "Hab": "Hab", "Zeph": "Zeph", "Hag": "Hag", "Zech": "Zech",
    "Mal": "Mal", "Matt": "Matt", "Mark": "Mark", "Luke": "Luke", "John": "John",
    "Acts": "Acts", "Rom": "Rom", "1Cor": "1 Cor", "2Cor": "2 Cor",
    "Gal": "Gal", "Eph": "Eph", "Phil": "Phil", "Col": "Col",
    "1Thess": "1 Thes", "2Thess": "2 Thes", "1Tim": "1 Tim", "2Tim": "2 Tim",
    "Titus": "Titus", "Phlm": "Philem", "Heb": "Heb", "Jas": "James", "1Pet": "1 Pet",
    "2Pet": "2 Pet", "1John": "1 Jn", "2John": "2 Jn", "3John": "3 Jn", "Jude": "Jude",
    "Rev": "Rev",
}

# Canonical books URN mapping
from proteus.core.references import CANONICAL_BOOKS, make_canonical_ref


def format_xref_target(raw_target: str) -> str:
    """Format e.g. 'Prov.8.22-Prov.8.30' -> 'Prov 8:22–30' or 'Acts.14.15' -> 'Acts 14:15'."""
    if "-" in raw_target:
        parts = raw_target.split("-")
        t1, t2 = parts[0], parts[1]
        p1 = t1.split(".")
        p2 = t2.split(".")
        b1 = XREF_ABBR_MAP.get(p1[0], p1[0])
        b2 = XREF_ABBR_MAP.get(p2[0], p2[0])
        ch1, v1 = p1[1], p1[2]
        ch2, v2 = p2[1], p2[2]
        if b1 == b2 and ch1 == ch2:
            return f"{b1} {ch1}:{v1}–{v2}"
        if b1 == b2:
            return f"{b1} {ch1}:{v1}–{ch2}:{v2}"
        return f"{b1} {ch1}:{v1}–{b2} {ch2}:{v2}"
    else:
        p = raw_target.split(".")
        if len(p) >= 3:
            b = XREF_ABBR_MAP.get(p[0], p[0])
            return f"{b} {p[1]}:{p[2]}"
        return raw_target


def xref_key_to_urn(raw_key: str) -> str | None:
    """Convert e.g. 'Gen.1.1' to 'ot:gen:1:1'."""
    p = raw_key.split(".")
    if len(p) < 3:
        return None
    abbr, ch, v = p[0], int(p[1]), int(p[2])
    # Full canonical name
    full_name = {
        "Gen": "Genesis", "Exod": "Exodus", "Lev": "Leviticus", "Num": "Numbers", "Deut": "Deuteronomy",
        "Josh": "Joshua", "Judg": "Judges", "Ruth": "Ruth", "1Sam": "1 Samuel", "2Sam": "2 Samuel",
        "1Kgs": "1 Kings", "2Kgs": "2 Kings", "1Chr": "1 Chronicles", "2Chr": "2 Chronicles",
        "Ezra": "Ezra", "Neh": "Nehemiah", "Esth": "Esther", "Job": "Job", "Ps": "Psalms",
        "Prov": "Proverbs", "Eccl": "Ecclesiastes", "Song": "Song of Solomon", "Isa": "Isaiah",
        "Jer": "Jeremiah", "Lam": "Lamentations", "Ezek": "Ezekiel", "Dan": "Daniel", "Hos": "Hosea",
        "Joel": "Joel", "Amos": "Amos", "Obad": "Obadiah", "Jonah": "Jonah", "Mic": "Micah",
        "Nah": "Nahum", "Hab": "Habakkuk", "Zeph": "Zephaniah", "Hag": "Haggai", "Zech": "Zechariah",
        "Mal": "Malachi", "Matt": "Matthew", "Mark": "Mark", "Luke": "Luke", "John": "John",
        "Acts": "Acts", "Rom": "Romans", "1Cor": "1 Corinthians", "2Cor": "2 Corinthians",
        "Gal": "Galatians", "Eph": "Ephesians", "Phil": "Philippians", "Col": "Colossians",
        "1Thess": "1 Thessalonians", "2Thess": "2 Thessalonians", "1Tim": "1 Timothy", "2Tim": "2 Timothy",
        "Titus": "Titus", "Phlm": "Philemon", "Heb": "Hebrews", "Jas": "James", "1Pet": "1 Peter",
        "2Pet": "2 Peter", "1John": "1 John", "2John": "2 John", "3John": "3 John", "Jude": "Jude",
        "Rev": "Revelation",
    }.get(abbr)
    if not full_name:
        return None
    return make_canonical_ref(full_name, ch, v)


def main() -> None:
    print("Reading Bible translations from bible_databases/formats/json/...")
    bsb_path = BIBLE_DB_DIR / "formats" / "json" / "BSB.json"
    asv_path = BIBLE_DB_DIR / "formats" / "json" / "ASV.json"
    bbe_path = BIBLE_DB_DIR / "formats" / "json" / "BBE.json"

    bsb = json.loads(bsb_path.read_text(encoding="utf-8"))
    asv = json.loads(asv_path.read_text(encoding="utf-8"))
    bbe = json.loads(bbe_path.read_text(encoding="utf-8"))

    comparisons: dict[str, dict[str, str | list[str]]] = collections.defaultdict(dict)

    def _ingest_translation(raw_dict: dict, code: str) -> None:
        for b in raw_dict["books"]:
            norm_name = NAME_MAP.get(b["name"], b["name"])
            for ch in b["chapters"]:
                ch_num = ch["chapter"]
                for v in ch["verses"]:
                    v_num = v["verse"]
                    urn = make_canonical_ref(norm_name, ch_num, v_num)
                    comparisons[urn][code] = v["text"].strip()

    print("Indexing BSB...")
    _ingest_translation(bsb, "bsb")
    print("Indexing ASV...")
    _ingest_translation(asv, "asv")
    print("Indexing BBE...")
    _ingest_translation(bbe, "bbe")

    print("Parsing OpenBible cross-references...")
    xrefs_file = BIBLE_DB_DIR / "sources" / "extras" / "cross_references.txt"
    raw_xrefs: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
    with xrefs_file.open(encoding="utf-8") as f:
        next(f)  # header
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                src, target, votes_str = parts[0], parts[1], parts[2]
                try:
                    votes = int(votes_str)
                except ValueError:
                    continue
                if votes > 0:
                    raw_xrefs[src].append((votes, target))

    for src, targets in raw_xrefs.items():
        urn = xref_key_to_urn(src)
        if not urn:
            continue
        # Sort targets by votes descending
        targets.sort(reverse=True)
        # Format top 5 targets
        formatted = [format_xref_target(t[1]) for t in targets[:5]]
        if formatted:
            comparisons[urn]["xrefs"] = formatted

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Writing {len(comparisons):,} verses to {OUT_FILE}...")
    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(comparisons, f, ensure_ascii=False, indent=None)

    file_size_mb = OUT_FILE.stat().st_size / (1024 * 1024)
    print(f"Successfully generated {OUT_FILE} ({file_size_mb:.2f} MB)")


if __name__ == "__main__":
    main()

