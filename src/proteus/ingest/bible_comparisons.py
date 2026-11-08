"""Bible Translation Comparisons & Cross-Reference Loader.

Provides fast cached access to verse-aligned parallel translations (BSB, ASV, BBE)
and curated scriptural cross-references from OpenBible / Treasury of Scripture Knowledge (TSK)
keyed by canonical scripture URN (e.g. 'ot:gen:1:1', 'nt:john:3:16').
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VerseComparison:
    urn: str
    bsb: str | None = None
    asv: str | None = None
    bbe: str | None = None
    xrefs: list[str] = field(default_factory=list)


_COMPARISONS_CACHE: dict[str, VerseComparison] | None = None


def load_bible_comparisons(
    data_path: Path = Path("data/raw/bible-comparisons/comparisons.json"),
) -> dict[str, VerseComparison]:
    """Load and cache the Bible parallel comparisons dataset keyed by canonical URN."""
    global _COMPARISONS_CACHE
    if _COMPARISONS_CACHE is not None:
        return _COMPARISONS_CACHE

    if not data_path.exists():
        # Fallback to empty if not yet generated
        _COMPARISONS_CACHE = {}
        return _COMPARISONS_CACHE

    raw = json.loads(data_path.read_text(encoding="utf-8"))
    res: dict[str, VerseComparison] = {}
    for urn, val in raw.items():
        res[urn] = VerseComparison(
            urn=urn,
            bsb=val.get("bsb"),
            asv=val.get("asv"),
            bbe=val.get("bbe"),
            xrefs=val.get("xrefs", []),
        )

    _COMPARISONS_CACHE = res
    return _COMPARISONS_CACHE

