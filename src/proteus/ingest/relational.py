"""Relational Dataset Loaders for Phase 3 (`onomasticon` & `scripture-citation`).

Includes:
- `load_onomasticon_entries()`: 419 canonical BYU Onomasticon entries with IPA, Hebrew reconstructions, and etymology.
- `load_citations_by_canonical_ref()`: Verse keys mapped to pre-1942 public-domain historical citations (`Journal of Discourses` 1839–1886 and `Teachings of the Prophet Joseph Smith` 1830–1844).
- `DiscourseExcerptIndex`: Fast contextual sermon excerpt extractor across all 1,821 pre-1942 public-domain discourses
  (`Journal of Discourses` and `Teachings of the Prophet Joseph Smith`, excluding post-1941 General Conference).
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


def _strip_deseret_references(text: str) -> str:
    """Remove Deseret Alphabet Unicode glyphs (U+10400..U+1044F) and inline Deseret Alphabet
    spelling notes that cannot render in Kindle system pop-up fonts.
    """
    if not text:
        return ""
    # Strip any SMP Deseret Alphabet characters
    s = re.sub(r"[\U00010400-\U0001044F]+", "", text)
    # Remove specific inline Deseret Alphabet clauses in BYU Onomasticon prose
    s = re.sub(r"\s*\(the Deseret Alphabet transcriptions are identical\)", "", s, flags=re.I)
    s = re.sub(r",?\s*according to the Deseret Alphabet spelling,?", "", s, flags=re.I)
    s = re.sub(r";\s*as\s+[^\s;]+\s+in the 1869 Deseret Alphabet", "", s, flags=re.I)
    s = re.sub(
        r",?\s*and the Deseret Alphabet spelling of the PN NEPHI,\s*,\s*\(IPA:\s*niːfaɪ\),\s*and\s*,\s*\(IPA:\s*neɪfaɪ\),",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(r"^See also Deseret Variant\s*$", "", s, flags=re.I)
    return s.strip()


def _clean_onomasticon_wikitext(wt: str) -> list[str]:
    """Clean MediaWiki markup from BYU Onomasticon pages into fine-press prose paragraphs."""
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", wt, flags=re.S)
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"\{\|.*?\|\}", "", s, flags=re.S)
    s = re.sub(r"\[\[Category:[^\]]+\]\]", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"'{2,5}", "", s)
    s = re.sub(r"==+[^=]+==+", "", s)
    s = re.sub(r"\[https?://[^\s\]]+(?:\s+([^\]]+))?\]", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    paras = [clean_prose_text(_strip_deseret_references(p)) for p in s.split("\n\n")]
    ignore_prefixes = ("Notes", "Bibliography", "----", "*", "index.php", "Category:", "See also")
    return [p for p in paras if p and not p.startswith(ignore_prefixes) and len(p) > 20]


def load_onomasticon_entries(
    onomasticon_dir: Path = Path("data/raw/bom-onomasticon"),
) -> dict[str, OnomasticonEntry]:
    """Load and normalize canonical BYU Onomasticon name entries (Book of Mormon & Pearl of Great Price)
    keyed by lowercase name.
    """
    names_path = onomasticon_dir / "names.json"
    raw_names = json.loads(names_path.read_text(encoding="utf-8"))

    # Load all_pages.jsonl to recover wikitext etymologies for Pearl of Great Price and unparsed entries
    all_pages_path = onomasticon_dir / "all_pages.jsonl"
    wiki_by_title: dict[str, str] = {}
    if all_pages_path.exists():
        for line in all_pages_path.open(encoding="utf-8"):
            d = json.loads(line)
            t = d.get("title", "").strip().upper()
            wt = d.get("wikitext", "")
            if t and wt:
                wiki_by_title[t] = wt

    # If KOLOB exists in all_pages.jsonl but missing in names.json, inject it
    if "KOLOB" in wiki_by_title and "KOLOB" not in raw_names:
        raw_names["KOLOB"] = {
            "name": "KOLOB",
            "classifications": ["Pearl of Great Price Names PN"],
            "ipa_pronunciation": "koʊlɒb",
            "etymology": {"clean_text": ""},
        }

    entries: dict[str, OnomasticonEntry] = {}
    for key, rec in raw_names.items():
        # Allow alphabetical names and hyphenated compound names (e.g. ENISH-GO-ON-DOSH, HAH-KO-KAU-BEAM)
        if not re.match(r"^[A-Za-z]+(?:-[A-Za-z]+)*$", key):
            continue

        raw_ipa = rec.get("ipa_pronunciation")
        clean_ipa: str | None = None
        if raw_ipa:
            clean_ipa = re.sub(r"(?:IPA:\s*|'+)", "", str(raw_ipa)).strip()

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
        ety_paras: list[str] = []
        if ety_raw:
            for p in ety_raw.split("\n\n"):
                p_scrubbed = _strip_deseret_references(p)
                p_clean = clean_prose_text(p_scrubbed)
                if p_clean and not p_clean.strip().startswith("----"):
                    ety_paras.append(p_clean)

        # Recover from wikitext if clean_text was missing (e.g. Pearl of Great Price entries)
        if not ety_paras and key.upper() in wiki_by_title:
            ety_paras = _clean_onomasticon_wikitext(wiki_by_title[key.upper()])

        if not ety_paras:
            ety_paras = ["Included in the BYU Book of Mormon & Scripture Onomasticon lexical database."]

        display_name = key.title()
        entries[key.lower()] = OnomasticonEntry(
            name_upper=key.upper(),
            display_name=display_name,
            ipa=clean_ipa,
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
    allowed_corpora: set[str] | None = None,
    max_year: int = 1941,
) -> dict[str, tuple[str, list[HistoricalCitationRecord]]]:
    """Load pre-1942 public-domain verse citation lists keyed by canonical URN (`ot:gen:1:26`, `bofm:1-ne:3:7`, etc.).

    By default restricts to pre-1942 public-domain corpora (`J` = Journal of Discourses 1839–1886,
    `T` = Teachings of the Prophet Joseph Smith 1830–1844), excluding `E` (1942–1959 General Conference).
    """
    if allowed_corpora is None:
        allowed_corpora = {"J", "T"}
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
            if it.get("corpus", "") in allowed_corpora
            and (int(it.get("year") or 0) <= max_year)
        ]
        if records:
            by_urn[urn] = (display_cite, records)

    return by_urn


RE_CID = re.compile(r'class="citation"\s+id="(\d+)"')
RE_CITATION_SPAN = re.compile(
    r'<span\s+class="citation"\s+id="(\d+)">.*?onclick="gs\(\d+\)">([^<]+)</a>\s*</span>',
    re.S,
)
RE_BREAK = re.compile(r'<div\s+class="break\s+(?:columnbreak|pagebreak)"[^>]*>.*?</div>', re.S)
RE_PAGE_STUB = re.compile(r'\[\s*p\.\s*\d+[a-z]?\s*\]')
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
                if corpus not in ("J", "T"):
                    continue
                raw_html = r.get("raw_html", "")

                if corpus == "J":
                    parts = re.split(r'<div\s+class="paragraph\s+jod"[^>]*>', raw_html)[1:]
                    raw_p_blocks = []
                    for pt in parts:
                        pt_nobreak = RE_BREAK.sub(" ", pt)
                        idx_close = pt_nobreak.find("</div>")
                        if idx_close != -1:
                            pt_nobreak = pt_nobreak[:idx_close]
                        pt_clean = RE_PAGE_STUB.sub("", pt_nobreak)
                        raw_p_blocks.append(pt_clean)
                    is_cont_first = False
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
                    p_matches = re.findall(
                        r'<p\s+class="(cont|std)"[^>]*>(.*?)</p>', raw_html, re.S
                    )
                    raw_p_blocks = []
                    is_cont_first = False
                    for p_i, (p_cls, p_body) in enumerate(p_matches):
                        if p_i == 0 and p_cls == "cont":
                            is_cont_first = True
                        raw_p_blocks.append(p_body)
                else:
                    idx_body = raw_html.find('<div class="gcbody">')
                    body_html = raw_html[idx_body:] if idx_body != -1 else raw_html
                    raw_p_blocks = re.findall(r"<p[^>]*>(.*?)</p>", body_html, re.S)
                    is_cont_first = False

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

                    # Stitch continuation across physical page breaks for TPJS
                    if corpus == "T" and is_cont_first and len(clean_ps) == 0:
                        prev_tid = tid - 1
                        if prev_tid in self.talk_paras and self.talk_paras[prev_tid]:
                            prev_tail = self.talk_paras[prev_tid][-1]
                            p_txt = prev_tail + " " + p_txt
                            self.talk_paras[prev_tid][-1] = p_txt

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

        # Include following paragraphs so the speaker's full exposition/application is captured.
        # For TPJS (talk_id >= 270000), each paragraph is often a distinct diary entry with a date/DHC attribution;
        # do not bleed into unrelated subsequent entries if the current entry is already substantial.
        is_tpjs = talk_id >= 270000
        if not is_tpjs:
            while end_idx + 1 < len(paras) and curr_words < target_min_words and (end_idx - start_idx) < 5:
                end_idx += 1
                curr_words += len(paras[end_idx].split())
        else:
            if curr_words < 60 and not re.search(r"DHC\s+\d+:\d+|\(\w+\.?\s+\d+,\s+\d{4}\.?\)", paras[end_idx]):
                while end_idx + 1 < len(paras) and curr_words < 120 and (end_idx - start_idx) < 2:
                    end_idx += 1
                    curr_words += len(paras[end_idx].split())

        selected = [re.sub(r"^[\.\s…]+", "", p).strip() for p in paras[start_idx : end_idx + 1] if p.strip()]
        if not selected:
            return []

        # Sentence-boundary guard: ensure selected[0] starts at the beginning of a complete sentence
        first_p = selected[0]
        if first_p and re.match(r"^[a-z]", first_p):
            m_sent = re.search(r"[.!?]\s+([A-Z“\"‘])", first_p)
            if m_sent:
                selected[0] = first_p[m_sent.start(1):]

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
        if end_idx < len(paras) - 1 and not (is_tpjs and re.search(r"DHC\s+\d+:\d+|\(\w+\.?\s+\d+,\s+\d{4}\.?\)", selected[-1])):
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
    max_excerpts: int = 6,
) -> list[HistoricalCitationRecord]:
    """Prioritize historical citations chronologically (oldest first) so Joseph Smith (TPJS)
    and the earliest 19th-century Journal of Discourses sermons are chosen first,
    avoiding duplicate excerpts from the same talk.
    """
    def _sort_key(r: HistoricalCitationRecord) -> tuple[int, int, int, int]:
        eff_year = r.year if (r.year and r.year > 0) else (1838 if r.corpus == "T" else 1900)
        return (
            eff_year,
            0 if r.corpus == "T" else 1,
            0 if "Joseph Smith" in r.speaker else 1,
            r.citation_id,
        )

    sorted_recs = sorted(recs, key=_sort_key)
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
