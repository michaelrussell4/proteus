"""Relational Dataset Loaders for Phase 3 (`onomasticon` & `scripture-citation`).

Includes:
- `load_onomasticon_entries()`: 419 canonical BYU Onomasticon entries with IPA, Deseret Alphabet, Hebrew reconstructions, and etymology.
- `load_citations_by_canonical_ref()`: All 20,758 verse keys mapped to 67,165 pre-1960 historical citations.
- `DiscourseExcerptIndex`: Fast contextual sermon excerpt extractor across all 2,871 pre-1960 discourses
  (`Journal of Discourses`, `Teachings of the Prophet Joseph Smith`, and `General Conference 1942–1959`).
  Locates the exact paragraph where `citation_id` is anchored and extracts a complete multi-paragraph
  (or complete multi-sentence) window around the citation, never cutting off mid-sentence, with `…` ellipses.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from proteus.core.references import make_canonical_ref, normalize_book_name
from proteus.core.typography import clean_prose_text


@dataclass
class OnomasticonEntry:
    name_upper: str
    display_name: str
    ipa: str | None
    deseret: str | None
    classifications: list[str]
    hebrew_summary: str | None
    etymology_paragraphs: list[str]
    variants: list[str] = field(default_factory=list)
    plates: list[str] = field(default_factory=list)


@dataclass
class HistoricalCitationRecord:
    citation_id: int
    verses_cited: str
    talk_id: int
    corpus: str
    source_citation: str
    speaker: str
    title: str
    date: str
    year: int


def load_onomasticon_entries(
    onomasticon_dir: Path = Path("data/raw/bom-onomasticon"),
) -> dict[str, OnomasticonEntry]:
    """Load and normalize the 419 canonical BYU Onomasticon name entries keyed by lowercase name."""
    names_path = onomasticon_dir / "names.json"
    raw_names = json.loads(names_path.read_text(encoding="utf-8"))

    entries: dict[str, OnomasticonEntry] = {}
    for key, rec in raw_names.items():
        if not re.match(r"^[A-Za-z]{2,}$", key):
            continue

        raw_ipa = rec.get("ipa_pronunciation")
        clean_ipa: str | None = None
        if raw_ipa:
            clean_ipa = re.sub(r"(?:IPA:\s*|'+)", "", str(raw_ipa)).strip()

        deseret = rec.get("deseret_alphabet") or None
        classifications = rec.get("classifications") or []

        heb_dict = rec.get("hebrew_transcriptions")
        heb_parts: list[str] = []
        if isinstance(heb_dict, dict):
            for hk, label in [
                ("mt_hebrew", "MT Hebrew"),
                ("miller_hebrew", "Miller Reconstruction"),
                ("lds_hebrew", "LDS Hebrew"),
                ("irvine_lachmann", "Irvine/Lachmann"),
            ]:
                val = heb_dict.get(hk)
                if val:
                    heb_parts.append(f"{label}: {val}")
        hebrew_summary = " | ".join(heb_parts) if heb_parts else None

        ety_raw = rec.get("etymology", {}).get("clean_text", "")
        ety_paras = [
            clean_prose_text(p)
            for p in ety_raw.split("\n\n")
            if clean_prose_text(p) and not p.strip().startswith("----")
        ]
        if not ety_paras:
            ety_paras = ["Included in the BYU Book of Mormon Onomasticon lexical database."]

        display_name = key.title()
        entries[key.lower()] = OnomasticonEntry(
            name_upper=key.upper(),
            display_name=display_name,
            ipa=clean_ipa,
            deseret=deseret,
            classifications=classifications,
            hebrew_summary=hebrew_summary,
            etymology_paragraphs=ety_paras[:6],
            variants=rec.get("variants") or [],
            plates=rec.get("plates") or [],
        )

    return entries


def _normalize_citation_verse_key(raw_key: str) -> tuple[str, str]:
    """Convert a BYU `citations_by_verse_pre_1960.json` key (e.g. 'Joseph Smith--History 1:17')
    into `(canonical_ref_urn, clean_display_citation)`.
    """
    fixed = raw_key.replace("--", "–").strip()
    m = re.match(r"^(.+?)\s+(\d+):(\d+)$", fixed)
    if not m:
        return fixed, fixed
    bk, ch, v = m.group(1), int(m.group(2)), int(m.group(3))
    norm_bk = normalize_book_name(bk)
    urn = make_canonical_ref(norm_bk, ch, v)
    short_bk = "D&C" if norm_bk == "Doctrine and Covenants" else norm_bk
    return urn, f"{short_bk} {ch}:{v}"


def load_citations_by_canonical_ref(
    citation_dir: Path = Path("data/raw/scripture-citation-index"),
) -> dict[str, tuple[str, list[HistoricalCitationRecord]]]:
    """Load all 20,758 verse citation lists keyed by canonical URN (`ot:gen:1:26`, `bofm:1-ne:3:7`, etc.)."""
    cpath = citation_dir / "citations_by_verse_pre_1960.json"
    raw_map = json.loads(cpath.read_text(encoding="utf-8"))

    by_urn: dict[str, tuple[str, list[HistoricalCitationRecord]]] = {}
    for raw_key, items in raw_map.items():
        urn, display_cite = _normalize_citation_verse_key(raw_key)
        records = [
            HistoricalCitationRecord(
                citation_id=it.get("citation_id", 0),
                verses_cited=str(it.get("verses_cited", "")),
                talk_id=it.get("talk_id", 0),
                corpus=it.get("corpus", ""),
                source_citation=it.get("source_citation", ""),
                speaker=clean_prose_text(it.get("speaker", "Unknown")),
                title=clean_prose_text(it.get("title", "Untitled")),
                date=it.get("date", ""),
                year=int(it.get("year") or 0),
            )
            for it in items
        ]
        by_urn[urn] = (display_cite, records)

    return by_urn


RE_CID = re.compile(r'class="citation"\s+id="(\d+)"')
RE_CITATION_SPAN = re.compile(
    r'<span\s+class="citation"\s+id="(\d+)">.*?onclick="gs\(\d+\)">([^<]+)</a>\s*</span>',
    re.S,
)
RE_COLBREAK = re.compile(r'<div\s+class="break\s+columnbreak"[^>]*>.*?</div>', re.S)
RE_FOOTREF = re.compile(r'<span\s+class="footRef">(\d+)</span>')
RE_TAGS = re.compile(r"<[^>]+>")


class DiscourseExcerptIndex:
    """Indexes all 2,871 historical talks in `talk_texts_pre_1960.jsonl` by paragraph and `citation_id`
    anchor so we can extract complete, multi-paragraph (or multi-sentence) sermon excerpts around
    any scripture citation without ever cutting off mid-sentence.
    """

    def __init__(self, citation_dir: Path = Path("data/raw/scripture-citation-index")) -> None:
        self.talk_paras: dict[int, list[str]] = {}
        self.cid_location: dict[int, tuple[int, int]] = {}
        self._load(citation_dir / "talk_texts_pre_1960.jsonl")

    def _load(self, tpath: Path) -> None:
        if not tpath.exists():
            return
        with open(tpath, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                tid = r["talk_id"]
                corpus = r.get("corpus", "E")
                raw_html = r.get("raw_html", "")

                if corpus == "J":
                    parts = re.split(r'<div\s+class="paragraph\s+jod"[^>]*>', raw_html)[1:]
                    raw_p_blocks = []
                    for pt in parts:
                        pt_nocol = RE_COLBREAK.sub(" ", pt)
                        idx_close = pt_nocol.find("</div>")
                        if idx_close != -1:
                            pt_nocol = pt_nocol[:idx_close]
                        raw_p_blocks.append(pt_nocol)
                elif corpus == "T":
                    fn_blocks = re.findall(
                        r'<div\s+class="footnote">\s*(\d+)\.(.*?)</div>', raw_html, re.S
                    )
                    fn_to_cids: dict[str, list[tuple[int, str]]] = {}
                    for fn_num, fn_body in fn_blocks:
                        for m_c in RE_CITATION_SPAN.finditer(fn_body):
                            fn_to_cids.setdefault(fn_num, []).append(
                                (int(m_c.group(1)), m_c.group(2))
                            )
                    raw_p_blocks = re.findall(
                        r'<p\s+class="(?:cont|std)"[^>]*>(.*?)</p>', raw_html, re.S
                    )
                else:
                    idx_body = raw_html.find('<div class="gcbody">')
                    body_html = raw_html[idx_body:] if idx_body != -1 else raw_html
                    raw_p_blocks = re.findall(r"<p[^>]*>(.*?)</p>", body_html, re.S)

                clean_ps: list[str] = []
                for p_raw in raw_p_blocks:
                    cids_in_p: list[int] = [int(m) for m in RE_CID.findall(p_raw)]
                    if corpus == "T":
                        for fn_num in RE_FOOTREF.findall(p_raw):
                            for cid_val, _ in fn_to_cids.get(fn_num, []):
                                cids_in_p.append(cid_val)

                        def _repl_fn(m: re.Match[str]) -> str:
                            fnum = m.group(1)
                            pairs = fn_to_cids.get(fnum, [])
                            if pairs:
                                refs = "; ".join(dict.fromkeys(ref for _, ref in pairs))
                                return f" ({refs})"
                            return ""

                        p_sub = RE_FOOTREF.sub(_repl_fn, p_raw)
                    else:
                        p_sub = RE_CITATION_SPAN.sub(r" (\2)", p_raw)

                    p_txt = RE_TAGS.sub(" ", p_sub)
                    p_txt = clean_prose_text(p_txt)
                    p_txt = re.sub(r"\(\s*\(([^)]+)\)\s*\)", r"(\1)", p_txt)
                    if not p_txt:
                        continue
                    p_idx = len(clean_ps)
                    clean_ps.append(p_txt)
                    for cid in cids_in_p:
                        self.cid_location[cid] = (tid, p_idx)
                self.talk_paras[tid] = clean_ps

    def extract_excerpt_paragraphs(
        self,
        citation_id: int,
        talk_id: int,
        target_min_words: int = 260,
        max_single_para_words: int = 420,
    ) -> list[str]:
        """Extract a natural, complete multi-paragraph (or complete multi-sentence) window around
        `citation_id` in `talk_id`. Never cuts off mid-sentence, and adds leading/trailing `…`
        ellipses when excerpted from inside a longer discourse.
        """
        paras = self.talk_paras.get(talk_id, [])
        if not paras:
            return []

        loc = self.cid_location.get(citation_id)
        if loc is None:
            # Fallback: first 3–4 substantive body paragraphs
            min_b = 1 if len(paras) > 1 and len(paras[0].split()) < 25 else 0
            selected = paras[min_b : min_b + 4]
            if not selected:
                return []
            out = list(selected)
            if min_b > 0:
                out[0] = "… " + re.sub(r"^[\.\s…]+", "", out[0])
            if min_b + 4 < len(paras):
                out[-1] = out[-1].rstrip() + " …"
            return out

        _, idx = loc
        min_body_idx = 1 if len(paras) > 1 and len(paras[0].split()) < 22 else 0
        start_idx = idx
        end_idx = idx

        center_words = len(paras[idx].split())
        # Include 1–2 preceding paragraphs so the reader gets full lead-in context before the citation
        if start_idx > min_body_idx and (
            center_words < 220
            or paras[idx].startswith((".", "…", "“", '"'))
            or paras[start_idx - 1].endswith((":", ","))
        ):
            start_idx -= 1
            if start_idx > min_body_idx and (len(paras[start_idx].split()) + center_words) < 140:
                start_idx -= 1

        curr_words = sum(len(paras[i].split()) for i in range(start_idx, end_idx + 1))

        # Include following paragraphs so the speaker's full exposition/application is captured (up to 5–6 paragraphs / ~260+ words)
        while end_idx + 1 < len(paras) and curr_words < target_min_words and (end_idx - start_idx) < 5:
            end_idx += 1
            curr_words += len(paras[end_idx].split())

        selected = [re.sub(r"^[\.\s…]+", "", p).strip() for p in paras[start_idx : end_idx + 1] if p.strip()]
        if not selected:
            return []

        # If a single 19th-century paragraph is huge (> max_single_para_words), extract a complete 8–10 sentence window
        if len(selected) == 1 and len(selected[0].split()) > max_single_para_words:
            # Split only on true sentence boundaries (avoiding abbreviations like Pres., Mr., Dr., St., Vol., p., ch., v.)
            sentences = re.split(
                r"(?<!\bMr)(?<!\bDr)(?<!\bSt)(?<!\bJr)(?<!\bSr)(?<!\bvs)(?<!\bch)(?<!\bpp)(?<!\bNo)(?<!\b Pres)(?<!\bElder)(?<=[.!?])\s+(?=[A-Z“\"‘\[])",
                selected[0],
            )
            if len(sentences) > 9:
                s_idx = len(sentences) // 2
                for si, s in enumerate(sentences):
                    if re.search(r"\([1-4A-Za-z].*?\d+:\d+", s):
                        s_idx = si
                        break
                s_start = max(0, s_idx - 4)
                s_end = min(len(sentences), s_idx + 5)
                chunk = " ".join(sentences[s_start:s_end]).strip()
                prefix = "… " if (start_idx > min_body_idx or s_start > 0) else ""
                suffix = " …" if (end_idx < len(paras) - 1 or s_end < len(sentences)) else ""
                return [f"{prefix}{chunk}{suffix}"]

        if start_idx > min_body_idx:
            selected[0] = "… " + selected[0]
        if end_idx < len(paras) - 1:
            selected[-1] = selected[-1] + " …"

        return selected


_DISCOURSE_INDEX_CACHE: DiscourseExcerptIndex | None = None


def get_discourse_excerpt_index(
    citation_dir: Path = Path("data/raw/scripture-citation-index"),
) -> DiscourseExcerptIndex:
    """Return a cached singleton `DiscourseExcerptIndex` so multiple builds share the parsed index."""
    global _DISCOURSE_INDEX_CACHE
    if _DISCOURSE_INDEX_CACHE is None:
        _DISCOURSE_INDEX_CACHE = DiscourseExcerptIndex(citation_dir)
    return _DISCOURSE_INDEX_CACHE


def select_representative_citations(
    recs: list[HistoricalCitationRecord],
    max_excerpts: int = 4,
) -> list[HistoricalCitationRecord]:
    """Prioritize historical citations so Joseph Smith (TPJS), early Journal of Discourses sermons,
    and distinct speakers are chosen first, avoiding duplicate excerpts from the same talk.
    """
    corpus_priority = {"T": 0, "J": 1, "E": 2}
    sorted_recs = sorted(
        recs,
        key=lambda r: (
            0 if "Joseph Smith" in r.speaker else 1,
            corpus_priority.get(r.corpus, 3),
            r.year if r.year > 0 else 9999,
            r.citation_id,
        ),
    )
    chosen: list[HistoricalCitationRecord] = []
    seen_talks: set[int] = set()
    for r in sorted_recs:
        if r.talk_id in seen_talks:
            continue
        seen_talks.add(r.talk_id)
        chosen.append(r)
        if len(chosen) >= max_excerpts:
            break
    return chosen
