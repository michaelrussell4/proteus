"""Typography normalization and HTML/XHTML sanitization utilities.

Ensures publish-grade book typography across all corpora:
- Repairs upstream mojibake (`\\ufffd` -> `–`)
- Converts straight ASCII quotes (`"`, `'`) to typographic curly quotes (`“`, `”`, `‘`, `’`)
- Converts `--` and `---` to em-dashes (`—`)
- Normalizes ungrammatical capitalization following mid-sentence em-dashes (`—Believing` -> `—believing`)
- Cleans hard line wraps inside prose/verses while preserving paragraph breaks
"""

from __future__ import annotations

import html
import re


# Proper nouns, pronouns, and sacred titles that must remain capitalized after a mid-sentence punctuation mark
PROPER_AND_SACRED_WORDS: set[str] = {
    "i", "o", "oh", "god", "lord", "jesus", "christ", "messiah", "father", "son", "holy", "ghost", "spirit",
    "lamb", "almighty", "jehovah", "creator", "redeemer", "savior", "saviour", "supreme", "maker",
    "israel", "jerusalem", "jews", "jew", "gentiles", "gentile", "christian", "christians",
    "nephite", "nephites", "lamanite", "lamanites", "zoramite", "zoramites", "amalekite", "amalekites",
    "amlicite", "amlicites", "jaredite", "jaredites", "ishmaelite", "ishmaelites", "jacobite", "jacobites",
    "josephite", "josephites", "lemuelite", "lemuelites", "mulekite", "mulekites",
    "satan", "lucifer", "devil", "moses", "abraham", "isaac", "jacob", "joseph", "pharaoh", "egypt", "egyptian", "egyptians",
    "babylon", "chaldees", "chaldea", "assyria", "assyrian", "syria", "damascus", "samaria", "ephraim", "manasseh", "judah", "benjamin",
    "isaiah", "malachi", "zenock", "zenos", "ezias", "jeremiah", "noah", "adam", "eve", "cain", "abel", "enoch", "melchizedek", "salem",
    "mary", "john", "elias", "mount", "sinai", "horeb", "zion", "eden", "bashan", "lebanon", "tarshish", "ophir", "red", "galilee", "jordan",
    "romans", "greeks", "bible", "scriptures", "paul", "peter", "james", "matthew", "mark", "luke", "moroni", "mormon", "nephi", "lehi",
    "laman", "lemuel", "sam", "zoram", "sariah", "ishmael", "laban", "enos", "jarom", "omni", "mosiah", "zarahemla", "alma", "amulek",
    "zeezrom", "nephihah", "ammon", "aaron", "omner", "himni", "lamoni", "abish", "gideon", "korihor", "pahoran", "teancum", "helaman",
    "shiblon", "corianton", "amalickiah", "ammoron", "gadianton", "kishkumen", "samuel", "lachoneus", "gidgiddoni", "ether", "jared",
    "coriantumr", "shiz", "moron", "abinadi", "limhi", "zeniff", "gid", "amulon", "bountiful", "desolation", "cumeni", "middoni",
    "shilom", "shemlon", "manti", "jershon", "melek", "ammonihah", "sidom", "sidon", "cumorah", "ramah", "ripliancum", "antionum",
    "mulek", "jashon", "shem", "antiparah", "zerahemnah", "cumenihah", "sherrizah", "morianton", "lehi-nephi", "shurr", "comnor", "shiblom",
    "seymour", "david", "alpheus", "william", "hyrum", "carthage", "greek", "hebrew", "latin", "english", "america",
}

# Direct-speech introducers where a capital letter after `—` begins a formal direct quotation
DIRECT_QUOTE_INTRO_RE = re.compile(
    r"(?:say|saith|said|saidst|saying|spake|speak|speaking|cry|cried|crying|wrote\s+upon\s+it|written|"
    r"for\s+the\s+word|heard\s+the\s+words|give\s+you\s+a\s+sign|answer\s+to\s+the\s+question|"
    r"admonition\s+of\s+Paul|say\s+unto\s+this\s+people|say\s+unto\s+them|said\s+unto\s+me|"
    r"say\s+unto\s+the\s+earth|say\s+unto\s+this\s+mountain|say\s+unto\s+the\s+waters\s+of\s+the\s+great\s+deep|"
    r"say\s+unto\s+a\s+man|saith\s+the\s+Lord\s+unto\s+my\s+servant\s+[A-Za-z.\s]+|say\s+unto\s+Joseph\s+Smith,\s*Jun\.|"
    r"speak\s+unto\s+you,\s+the\s+Twelve|break\s+forth\s+into\s+joy|cry\s+went\s+forth\s+throughout\s+the\s+land|"
    r"manner\s+of\s+administering\s+the\s+wine|on\s+this\s+wise\s+shall\s+ye\s+baptize\s+them|"
    r"tell\s+this\s+people|say\s+within\s+yourselves|think\s+in\s+their\s+hearts|"
    r"said\s+the\s+Father\s+unto\s+Malachi|middle\s+aged|even\s+so\s+will\s+I\s+fulfil|"
    r"Revelation\s+20:12|thus\s+saith\s+the\s+Lord(?:\s+God)?|pointing\s+to\s+the\s+other|"
    r"voice\s+is\s+unto\s+men|Cry\s+unto\s+this\s+people)\s*$",
    re.I,
)


def should_keep_capital_after_continuation(word: str) -> bool:
    """Return True if `word` is a proper noun, sacred title, pronoun `I`/`O`, or all-caps."""
    if not word:
        return True
    if word.isupper() and len(word) > 1:
        return True
    clean_w = word.strip("“”‘’\"'(),.;:!?").lower()
    if clean_w in PROPER_AND_SACRED_WORDS:
        return True
    return False


def capitalize_verse_start(text: str) -> str:
    """Ensure a verse begins with an uppercase letter (ignoring leading quotes, brackets, or whitespace)."""
    if not text:
        return text
    m = re.match(r'^([\s“‘"\'(\[]*)([a-z])(.*)$', text, re.DOTALL)
    if not m:
        return text
    return f"{m.group(1)}{m.group(2).upper()}{m.group(3)}"


def lowercase_continuation_start(text: str) -> str:
    """Lowercase the leading word of `text` when it continues a sentence mid-paragraph after `—`,
    unless the leading word is a proper noun, sacred title, `I`, `O`, or opens a quotation.
    """
    m = re.match(r"^([A-Z][a-zA-Z']*)\b(.*)$", text, re.DOTALL)
    if not m:
        return text
    first_word, rest = m.group(1), m.group(2)
    if should_keep_capital_after_continuation(first_word):
        return text
    return first_word[0].lower() + first_word[1:] + rest


def normalize_em_dash_capitalization(text: str) -> str:
    """Repair archaic 19th-century capitalizations following mid-sentence em-dashes
    (such as `which is this—Believing` in Mosiah 10:12, the Book of Mormon Title Page,
    Alma 40:11, Alma 46:17, D&C 20:37–38/68, and 1830 mid-sentence dashes) where `:—`
    was shortened to `—` in 1920 without lowercasing the following non-proper word.
    """
    if "—" not in text:
        return text

    # 1. Remove archaic 1830 `.—` / `?—` / `!—` printer's dash after sentence-ending punctuation
    s = re.sub(r"([.?!])\s*—\s*(?=[A-Z“‘\"'])", r"\1 ", text)
    # 2. Tighten spaces around mid-sentence em-dashes between word characters
    s = re.sub(r"(?<=[A-Za-z,;:])\s*—\s*(?=[A-Za-z])", "—", s)

    def _repl(m: re.Match[str]) -> str:
        prefix = s[: m.start()]
        word = m.group(1)
        if should_keep_capital_after_continuation(word):
            return m.group(0)
        # Keep capital if preceded by terminal sentence punctuation or quote
        if re.search(r"[.?!\"”’]\s*$", prefix):
            return m.group(0)
        # Keep capital if preceded by a direct-quotation introducer
        if DIRECT_QUOTE_INTRO_RE.search(prefix):
            return m.group(0)
        return "—" + word[0].lower() + word[1:]

    return re.sub(r"—([A-Z][a-zA-Z']*)", _repl, s)


def fix_mojibake(text: str) -> str:
    """Repair known encoding glitches in upstream files."""
    if not text:
        return ""
    # In pearl-of-great-price.json, 'Joseph Smith–Matthew' and 'Joseph Smith–History' have \ufffd
    text = re.sub(r"Joseph Smith\ufffd(Matthew|History)", r"Joseph Smith–\1", text)
    text = text.replace("\ufffd", "—")
    # Remove zero-width and soft-hyphen artifacts
    text = text.replace("\ufeff", "").replace("\u200b", "")
    # Normalize non-breaking spaces to regular spaces
    text = text.replace("\xa0", " ").replace("\u202f", " ")
    return text


def smarten_quotes(text: str) -> str:
    """Convert straight quotes and double-hyphens into typographic book punctuation.

    Carefully avoids modifying anything inside HTML tags (`<...>`).
    """
    if not text:
        return ""

    # Split by HTML tags if present so attributes like class="foo" are never touched
    parts = re.split(r"(<[^>]+>)", text)
    out: list[str] = []

    for part in parts:
        if part.startswith("<") and part.endswith(">"):
            out.append(part)
            continue

        s = part
        # Em-dashes: --- or -- -> —
        s = re.sub(r"---?", "—", s)
        # Ellipses: . . . -> …
        s = re.sub(r"\.\s+\.\s+\.", "…", s)

        # Double quotes: opening after whitespace, start of string, or opening brackets/dashes
        s = re.sub(r'(^|[\s(\[{—–])"', r"\1“", s)
        # Remaining double quotes are closing
        s = s.replace('"', "”")

        # Apostrophes inside words (don't, king's, 'tis)
        s = re.sub(r"(\w)'(\w)", r"\1’\2", s)
        # Opening single quotes after whitespace or opening punctuation
        s = re.sub(r"(^|[\s(\[{—–“])'(?=\S)", r"\1‘", s)
        # Remaining single quotes are closing/apostrophes
        s = s.replace("'", "’")

        s = normalize_em_dash_capitalization(s)
        out.append(s)

    return "".join(out)


def clean_prose_text(text: str, smart_typography: bool = True) -> str:
    """Normalize whitespace, unwrap hard single-line breaks, and apply book typography."""
    if not text:
        return ""
    s = fix_mojibake(text)
    # Collapse single newlines (hard wraps) into spaces while keeping double newlines
    s = re.sub(r"(?<!\n)\n(?!\n)", " ", s)
    s = re.sub(r"[ \t]+", " ", s).strip()
    if smart_typography:
        s = smarten_quotes(s)
    return s


def escape_xhtml(text: str, smart_typography: bool = True) -> str:
    """Escape plain text for safe inclusion in strict XHTML5, applying smart typography."""
    cleaned = clean_prose_text(text, smart_typography=smart_typography)
    return html.escape(cleaned, quote=False)

