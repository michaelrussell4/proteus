"""Typography normalization and HTML/XHTML sanitization utilities.

Ensures publish-grade book typography across all corpora:
- Repairs upstream mojibake (`\\ufffd` -> `–`)
- Converts straight ASCII quotes (`"`, `'`) to typographic curly quotes (`“`, `”`, `‘`, `’`)
- Converts `--` and `---` to em-dashes (`—`)
- Cleans hard line wraps inside prose/verses while preserving paragraph breaks
"""

from __future__ import annotations

import html
import re


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

