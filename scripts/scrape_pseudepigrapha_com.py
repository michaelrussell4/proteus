"""Scraper for unique Pseudepigrapha, Apocrypha, Ethiopian Canon, Dead Sea Scrolls,
and Nag Hammadi texts from https://www.pseudepigrapha.com/.

Saves clean, structured JSONL records to `data/raw/pseudepigrapha-com/pseudepigrapha_com.jsonl`
and writes a comprehensive documentation file at `data/raw/pseudepigrapha-com/summary.md`.
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup


BASE_URL = "https://www.pseudepigrapha.com/"

# 40 unique ancient works on https://www.pseudepigrapha.com/ that do NOT duplicate
# our existing KJV Deuterocanon (`extra-canon/`), ISTA (`apocrypha/`), or ANF Vol. 8 (`gutenberg-apocrypha/`) corpora.
PSEUDEPIGRAPHA_COM_TARGETS: list[dict[str, object]] = [
    # --- Septuagint & Ethiopian Orthodox Extended Canon ---
    {
        "id": "3-maccabees",
        "title": "The Third Book of the Maccabees (3 Maccabees)",
        "division": "I",
        "category": "Septuagint Deuterocanon",
        "urls": ["apocrypha_ot/3macc.htm"],
    },
    {
        "id": "4-maccabees",
        "title": "The Fourth Book of the Maccabees (4 Maccabees)",
        "division": "I",
        "category": "Septuagint Appendix",
        "urls": ["apocrypha_ot/4macc.htm"],
    },
    {
        "id": "psalm-151",
        "title": "Psalm 151 (Septuagint & Dead Sea Scrolls Supernumerary Psalm of David)",
        "division": "I",
        "category": "Septuagint & Qumran Psalter",
        "urls": ["apocrypha_ot/Pslm151.htm"],
    },
    {
        "id": "1-meqabyan",
        "title": "The First Book of Ethiopian Maccabees (1 Meqabyan)",
        "division": "I",
        "category": "Ethiopian Orthodox Tewahedo Canon",
        "urls": ["EtheopianBible/Etheopian1Meqabyan.html"],
    },
    {
        "id": "2-meqabyan",
        "title": "The Second Book of Ethiopian Maccabees (2 Meqabyan)",
        "division": "I",
        "category": "Ethiopian Orthodox Tewahedo Canon",
        "urls": ["EtheopianBible/Etheopian2Meqabyan.html"],
    },
    {
        "id": "3-meqabyan",
        "title": "The Third Book of Ethiopian Maccabees (3 Meqabyan)",
        "division": "I",
        "category": "Ethiopian Orthodox Tewahedo Canon",
        "urls": ["EtheopianBible/Etheopian3Meqabyan.html"],
    },
    # --- Enochic & Noachic Literature ---
    {
        "id": "book-of-noah",
        "title": "The Book of Noah (Ethiopic & Aramaic Noachic Fragments)",
        "division": "II",
        "category": "Antediluvian Pseudepigrapha",
        "urls": ["EtheopianBible/TheBookOfNoah.html"],
    },
    # --- Patriarchal, Mosaic, Prophetic & Second Temple Pseudepigrapha ---
    {
        "id": "slavonic-life-of-adam-and-eve",
        "title": "The Slavonic Life of Adam and Eve (Vita Adae et Evae)",
        "division": "III",
        "category": "Old Testament Pseudepigrapha",
        "urls": ["pseudepigrapha/slanev.htm"],
    },
    {
        "id": "eastern-book-of-adam",
        "title": "The Book of Adam (Eastern Syriac-Armenian Adamitic Tradition)",
        "division": "III",
        "category": "Old Testament Pseudepigrapha",
        "urls": ["pseudepigrapha/TheBookOfAdam.htm"],
    },
    {
        "id": "apocalypse-of-abraham",
        "title": "The Apocalypse of Abraham (Slavonic Pseudepigraphon)",
        "division": "III",
        "category": "Old Testament Apocalyptic",
        "urls": ["pseudepigrapha/Apocalypse_of_Abraham.html"],
    },
    {
        "id": "joseph-and-aseneth",
        "title": "Joseph and Aseneth (The Story and Confession of Asenath)",
        "division": "III",
        "category": "Second Temple Patriarchal Narrative",
        "urls": ["pseudepigrapha/TheStoryOfAsenath.html"],
    },
    {
        "id": "tales-of-the-patriarchs",
        "title": "Tales of the Patriarchs (Haggadic Chronicles of the Fathers)",
        "division": "III",
        "category": "Second Temple & Rabbinic Haggadah",
        "urls": ["pseudepigrapha/TalesOfThePatriarchs.html"],
    },
    {
        "id": "assumption-of-moses",
        "title": "The Assumption (Testament) of Moses",
        "division": "III",
        "category": "Old Testament Pseudepigrapha",
        "urls": ["pseudepigrapha/assumptionofmoses.html"],
    },
    {
        "id": "revelation-of-moses-hebrew",
        "title": "The Revelation of Moses (Hebrew Visions of the Seven Heavens)",
        "division": "III",
        "category": "Merkabah & Visionary Literature",
        "urls": ["pseudepigrapha/revmos2.htm"],
    },
    {
        "id": "martyrdom-and-ascension-of-isaiah",
        "title": "The Martyrdom and Ascension of Isaiah",
        "division": "III",
        "category": "Old Testament Apocalyptic",
        "urls": ["pseudepigrapha/amartis.htm", "pseudepigrapha/AscensionOfIsaiah.html"],
    },
    {
        "id": "2-baruch",
        "title": "The Syriac Apocalypse of Baruch (2 Baruch, with the Epistle of Baruch)",
        "division": "III",
        "category": "Second Temple Apocalyptic",
        "urls": ["pseudepigrapha/2Baruch.html"],
    },
    {
        "id": "3-baruch",
        "title": "The Greek Apocalypse of Baruch (3 Baruch)",
        "division": "III",
        "category": "Second Temple Apocalyptic",
        "urls": ["pseudepigrapha/3Baruch.html"],
    },
    {
        "id": "4-baruch",
        "title": "The Fourth Book of Baruch (Paraleipomena Jeremiou / Rest of the Words of Baruch)",
        "division": "III",
        "category": "Ethiopian & Second Temple Pseudepigrapha",
        "urls": ["EtheopianBible/ParaleipomenaJeremiouLong.html"],
    },
    {
        "id": "apocalypse-of-elijah",
        "title": "The Apocalypse of Elijah (Coptic Jewish-Christian Apocalypse)",
        "division": "III",
        "category": "Old Testament Apocalyptic",
        "urls": ["pseudepigrapha/TheApocalypseOfElijah.html"],
    },
    {
        "id": "words-of-gad-the-seer",
        "title": "The Words of Gad the Seer (Cochin Hebrew Manuscript)",
        "division": "III",
        "category": "Hebrew Prophetic Pseudepigrapha",
        "urls": ["WordsOfTheSeerGad.html"],
    },
    {
        "id": "damascus-zadokite-document",
        "title": "The Damascus Document (Fragments of a Zadokite Work — CDC / Dead Sea Scrolls)",
        "division": "IV",
        "category": "Dead Sea Scrolls & Cairo Genizah",
        "urls": ["pseudepigrapha/zadokite.html"],
    },
    {
        "id": "qumran-community-rule",
        "title": "The Community Rule (1QS — Manual of Discipline of the Qumran Essenes)",
        "division": "IV",
        "category": "Dead Sea Scrolls",
        "urls": ["apocrypha_nt/comr.htm"],
    },
    # --- Nag Hammadi, Gnostic & Coptic Sacred Literature ---
    {
        "id": "apocalypse-of-adam",
        "title": "The Apocalypse of Adam (Nag Hammadi Codex V, 5)",
        "division": "V",
        "category": "Nag Hammadi Library",
        "urls": ["pseudepigrapha/adam.htm"],
    },
    {
        "id": "second-treatise-of-the-great-seth",
        "title": "The Second Treatise of the Great Seth (Nag Hammadi Codex VII, 2)",
        "division": "V",
        "category": "Nag Hammadi Library",
        "urls": ["pseudepigrapha/2seth.html"],
    },
    {
        "id": "melchizedek-nhc",
        "title": "Melchizedek (Nag Hammadi Codex IX, 1)",
        "division": "V",
        "category": "Nag Hammadi Library",
        "urls": ["pseudepigrapha/Melchizedek.html"],
    },
    {
        "id": "apocryphon-of-john",
        "title": "The Apocryphon (Secret Book) of John (Nag Hammadi Codex II, 1)",
        "division": "V",
        "category": "Nag Hammadi Library",
        "urls": ["apocrypha_nt/apocjn.html"],
    },
    {
        "id": "apocryphon-of-james",
        "title": "The Apocryphon (Secret Book) of James (Nag Hammadi Codex I, 2)",
        "division": "V",
        "category": "Nag Hammadi Library",
        "urls": ["apocrypha_nt/jam.html"],
    },
    {
        "id": "book-of-thomas-the-contender",
        "title": "The Book of Thomas the Contender (Nag Hammadi Codex II, 7)",
        "division": "V",
        "category": "Nag Hammadi Library",
        "urls": ["apocrypha_nt/tomcntnd.htm"],
    },
    {
        "id": "letter-of-peter-to-philip",
        "title": "The Letter of Peter to Philip (Nag Hammadi Codex VIII, 2)",
        "division": "V",
        "category": "Nag Hammadi Library",
        "urls": ["apocrypha_nt/letpet.html"],
    },
    {
        "id": "gospel-of-mary-magdalene",
        "title": "The Gospel of Mary (Magdalene) (Berlin Codex BG 8502 & Greek Fragments)",
        "division": "V",
        "category": "Early Christian & Coptic Gospel",
        "urls": ["LostBooks/excerpts_GospelOfMary_Multi.html"],
    },
    {
        "id": "pistis-sophia",
        "title": "Pistis Sophia: A Gnostic Miscellany (Books I & II — Askew Codex)",
        "division": "V",
        "category": "Coptic Post-Resurrection Dialogue",
        "urls": [
            "PistisSophia/pistisSophia_intro.html",
            "PistisSophia/pistisSophia_Book1.html",
            "PistisSophia/pistisSophia_Book2.html",
        ],
    },
    # --- New Testament Apocrypha, Post-Resurrection Dialogues & Early Christian Texts ---
    {
        "id": "epistle-of-the-apostles",
        "title": "The Epistle of the Apostles (Epistula Apostolorum)",
        "division": "VI",
        "category": "Post-Resurrection Apostolic Dialogue",
        "urls": ["apocrypha_nt/episaps.htm"],
    },
    {
        "id": "questions-of-bartholomew",
        "title": "The Questions (Gospel) of Bartholomew",
        "division": "VI",
        "category": "New Testament Apocrypha",
        "urls": ["LostBooks/bartholomew.htm"],
    },
    {
        "id": "interrogatio-johannis",
        "title": "The Book (Secret Supper) of John the Evangelist",
        "division": "VI",
        "category": "Apocryphal Johannine Dialogue",
        "urls": ["apocrypha_nt/jonevan.htm"],
    },
    {
        "id": "secret-gospel-of-mark",
        "title": "The Secret Gospel of Mark (Letter of Clement of Alexandria to Theodore)",
        "division": "VI",
        "category": "Early Alexandrian Apocrypha",
        "urls": ["LostBooks/marksecret.htm"],
    },
    {
        "id": "ptolemy-john-prologue",
        "title": "Ptolemy's Commentary on the Gospel of John Prologue",
        "division": "VI",
        "category": "Early Patristic/Valentinian Exegesis",
        "urls": ["apocrypha_nt/ptl.htm"],
    },
    {
        "id": "gospel-of-marcion",
        "title": "The Gospel of the Lord (Marcion of Sinope's Evangelion Reconstruction)",
        "division": "VI",
        "category": "2nd-Century Patristic Reconstruction",
        "urls": ["LostBooks/marcion.htm"],
    },
    {
        "id": "apocalypse-of-pseudo-methodius",
        "title": "The Apocalypse of Pseudo-Methodius (From the Cave of Treasures to the Last Days)",
        "division": "VI",
        "category": "Syriac Christian Apocalyptic",
        "urls": ["pseudepigrapha/ApocalypseOfPseudoMethodius_01.html"],
    },
    {
        "id": "sentences-of-sextus",
        "title": "The Sentences of Sextus (2nd-Century Christian Wisdom Maxims)",
        "division": "VII",
        "category": "Early Christian Wisdom & Nag Hammadi XII, 1",
        "urls": ["apocrypha_nt/sentx.htm"],
    },
    {
        "id": "egyptian-book-of-breathings-and-gilgamesh",
        "title": "Comparative Ancient Near Eastern Texts: The Egyptian Book of Breathings & The Gilgamesh Flood Tablet",
        "division": "IV",
        "category": "Ancient Near Eastern Comparative Texts",
        "urls": ["egyptian/BookOfBreathings.htm", "pseudepigrapha/gilgamesh.html"],
    },
]


BOILERPLATE_PHRASES = (
    "bookstore",
    "f.a.q.",
    "is god real?",
    "the church of jesus christ of latter-day saints",
    "send feedback",
    "return to home page",
    "return to index",
    "back to index",
    "click here to",
    "www.pseudepigrapha.com",
    "copyright ©",
)


def fetch_html(rel_url: str) -> str:
    url = BASE_URL + rel_url.lstrip("/")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        },
    )
    raw = urllib.request.urlopen(req, timeout=25).read()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            if "\ufffd" not in text:
                return text
        except UnicodeDecodeError:
            continue
    return raw.decode("cp1252", errors="replace").replace("\ufffd", "—")


def clean_html_to_sections(html: str, default_title: str) -> list[dict[str, object]]:
    """Parse an HTML page from pseudepigrapha.com into clean chapter/section dicts."""
    soup = BeautifulSoup(html, "lxml")

    # Remove script, style, nav tables, and header links
    for tag in soup.find_all(["script", "style", "noscript", "iframe"]):
        tag.decompose()

    # Extract raw lines or paragraph blocks
    blocks: list[tuple[str, str]] = []  # (kind, text)
    body = soup.body or soup

    # First check if there are structured <p>, <h1>..<h4>, <blockquote>, <li> tags
    structured_tags = body.find_all(["h1", "h2", "h3", "h4", "p", "blockquote", "li", "pre"])
    if len(structured_tags) >= 5:
        for el in structured_tags:
            # Skip nested duplicates (e.g., <p> inside <blockquote> or <li>)
            if el.name == "p" and el.find_parent(["blockquote", "li"]):
                continue
            txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
            if not txt:
                continue
            low = txt.lower()
            if len(txt) < 90 and any(bp in low for bp in BOILERPLATE_PHRASES):
                continue
            if el.name in ("h1", "h2", "h3", "h4"):
                blocks.append(("heading", txt))
            elif el.name == "pre":
                for para in re.split(r"\n\s*\n", el.get_text()):
                    p_clean = re.sub(r"\s+", " ", para).strip()
                    if p_clean:
                        blocks.append(("para", p_clean))
            else:
                blocks.append(("para", txt))

    # Fallback or supplement if page uses <br> or raw text inside <body> / <td> without <p> tags
    total_para_chars = sum(len(t) for k, t in blocks if k == "para")
    raw_body_text = body.get_text("\n")
    if total_para_chars < len(raw_body_text.strip()) * 0.45:
        blocks = []
        # Replace <br> with double newline
        for br in body.find_all("br"):
            br.replace_with("\n\n")
        for ptag in body.find_all(["p", "div", "tr", "h1", "h2", "h3", "h4", "li"]):
            ptag.insert_before("\n\n")
            ptag.insert_after("\n\n")
        raw_text = body.get_text()
        chunks = re.split(r"\n\s*\n+", raw_text)
        for ch in chunks:
            txt = re.sub(r"\s+", " ", ch).strip()
            if not txt:
                continue
            low = txt.lower()
            if len(txt) < 95 and any(bp in low for bp in BOILERPLATE_PHRASES):
                continue
            if re.match(r"^(?:CHAPTER|BOOK|SECTION|PART|TABLET|PSALM|VISION)\s+(?:[IVXLCDM]+|\d+)\b", txt, re.I) and len(txt) < 120:
                blocks.append(("heading", txt))
            else:
                blocks.append(("para", txt))

    # Split blocks into chapters when explicit chapter headings occur
    sections: list[dict[str, object]] = []
    cur_title = default_title
    cur_paras: list[str] = []

    chapter_pat = re.compile(
        r"^(?:(?:CHAPTER|CHAP\.|BOOK|PART|SECTION|VISION|LETTER|EPISTLE|HOMILY|TABLET|PSALM)\s+(?:[IVXLCDM]+|\d+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)\b|[34]Mac\.\d+$|(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI|XVII|XVIII|XIX|XX)\.?$|The\s+(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh)\s+Heaven\.?$)",
        re.IGNORECASE,
    )

    for kind, txt in blocks:
        m_mac = re.match(r"^[34]Mac\.(\d+)$", txt, re.I)
        if m_mac:
            txt = f"Chapter {m_mac.group(1)}"
            kind = "heading"
        elif re.match(r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI|XVII|XVIII|XIX|XX)\.?$", txt):
            txt = f"Chapter {txt.rstrip('.')}"
            kind = "heading"

        # Check if a paragraph starts with "Chapter X" as a standalone line
        is_ch_heading = (
            (kind == "heading" and len(txt) < 120)
            or (chapter_pat.match(txt) is not None and len(txt) < 95)
        )
        if is_ch_heading:
            if cur_paras and sum(len(p) for p in cur_paras) > 250:
                sections.append({"title": cur_title, "paragraphs": cur_paras})
                cur_paras = []
            cur_title = txt
        else:
            # Avoid consecutive identical paragraphs
            if not cur_paras or cur_paras[-1] != txt:
                cur_paras.append(txt)

    if cur_paras:
        sections.append({"title": cur_title, "paragraphs": cur_paras})

    # Merge tiny header-only sections into the following section
    merged: list[dict[str, object]] = []
    for sec in sections:
        paras = list(sec["paragraphs"])  # type: ignore[arg-type]
        if merged and sum(len(p) for p in merged[-1]["paragraphs"]) < 220:  # type: ignore[arg-type]
            merged[-1]["paragraphs"].extend(paras)  # type: ignore[union-attr]
            if merged[-1]["title"] == default_title and sec["title"] != default_title:
                merged[-1]["title"] = sec["title"]
        else:
            merged.append(sec)

    return merged


def main() -> None:
    out_dir = Path("data/raw/apocrypha-pseudepigrapha-com")
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "pseudepigrapha_com.jsonl"

    all_records: list[dict[str, object]] = []
    summary_rows: list[str] = []

    for item in PSEUDEPIGRAPHA_COM_TARGETS:
        work_id = str(item["id"])
        title = str(item["title"])
        division = str(item["division"])
        category = str(item["category"])
        urls: list[str] = list(item["urls"])  # type: ignore[arg-type]

        work_sections: list[dict[str, object]] = []
        for u_idx, rel_url in enumerate(urls, start=1):
            html = fetch_html(rel_url)
            default_sec_title = title if len(urls) == 1 else f"{title} — Part {u_idx}"
            secs = clean_html_to_sections(html, default_sec_title)
            work_sections.extend(secs)

        total_words = sum(
            len(p.split())
            for s in work_sections
            for p in s["paragraphs"]  # type: ignore[union-attr]
        )
        record = {
            "id": work_id,
            "title": title,
            "division": division,
            "category": category,
            "source_urls": [BASE_URL + u.lstrip("/") for u in urls],
            "section_count": len(work_sections),
            "word_count": total_words,
            "sections": work_sections,
        }
        all_records.append(record)
        summary_rows.append(
            f"| `{work_id}` | {title} | {category} | {len(work_sections)} | {total_words:,} |"
        )
        print(f"Scraped {work_id:42s} | sections={len(work_sections):3d} | words={total_words:7,d}")

    with jsonl_path.open("w", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    total_corpus_words = sum(int(r["word_count"]) for r in all_records)
    summary_md = (
        "# Pseudepigrapha.com Scraped Corpus (`data/raw/pseudepigrapha-com/`)\n\n"
        f"- **Total Unique Works Scraped:** {len(all_records)}\n"
        f"- **Total Word Count:** {total_corpus_words:,} words\n"
        "- **Output File:** `pseudepigrapha_com.jsonl`\n"
        "- **Deduplication Policy:** Excludes works already present in `extra-canon/` (KJV Deuterocanon), "
        "`apocrypha/` (1 & 2 Enoch, Jubilees, Jasher, Forgotten Books of Eden, Lost Books of the Bible), "
        "and `gutenberg-apocrypha/` (Ante-Nicene Fathers Vol. 8).\n\n"
        "## Catalogue of Scraped Works\n\n"
        "| ID | Title | Category | Sections | Words |\n"
        "| :--- | :--- | :--- | ---: | ---: |\n"
        + "\n".join(summary_rows)
        + "\n"
    )
    (out_dir / "summary.md").write_text(summary_md, encoding="utf-8")
    print(f"\nSaved {len(all_records)} works ({total_corpus_words:,} words) to {jsonl_path}")


if __name__ == "__main__":
    main()
