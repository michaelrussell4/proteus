"""Build the Proteus landing page into `site/`.

Reads the EPUBs in `dist/epubs` and covers in `dist/covers`, copies them into
`site/downloads` and `site/covers`, and writes `site/index.html` + `site/catalog.json`.

Usage:  uv run python scripts/build_site.py
Preview: python -m http.server -d site 8000
"""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_EPUBS = ROOT / "dist" / "epubs"
DIST_COVERS = ROOT / "dist" / "covers"
SITE = ROOT / "site"

# (collection id, title, blurb)
COLLECTIONS = [
    ("reading-guides", "Reading Guides", "Short helps for reading scripture with more confidence."),
    ("standard-works", "The Standard Works", "The core scriptures, cleanly formatted for e-readers."),
    ("minimalist", "Minimalist Editions", "Just chapters and verses: no footnotes, no clutter."),
    ("reading-editions", "Reading Editions", "Scripture as a flowing story, or with room for your own notes."),
    ("study-editions", "Study Editions", "Deeper study: speakers, name meanings, variants, parallels and poetry."),
    ("apocrypha", "Apocrypha & Ancient Texts", "Books outside the standard canon that shaped the biblical world."),
    ("literature", "Restoration Literature", "Historical books and sermons from the early Latter-day Saint era."),
]

# epub stem -> (collection, title, blurb)
ENTRIES: dict[str, tuple[str, str, str]] = {
    "early-modern-english-quick-guide": (
        "reading-guides", "Reading Old English Scripture: A Quick Guide",
        "Short and plain: thou/ye, -eth, old words and false friends in the KJV and Book of Mormon."),
    "early-modern-english-scripture-guide": (
        "reading-guides", "Early Modern English: The Full Reference",
        "The longer scholarly guide to pronouns, verbs, syntax, vocabulary and Hebraisms."),
    "book-of-mormon": ("standard-works", "The Book of Mormon", "The 2013 Standard Works edition."),
    "book-of-mormon-1830": ("standard-works", "The Book of Mormon (1830)", "The original Palmyra edition text."),
    "doctrine-and-covenants": ("standard-works", "The Doctrine and Covenants", "The 2013 Standard Works edition."),
    "pearl-of-great-price": ("standard-works", "The Pearl of Great Price", "The 2013 Standard Works edition."),
    "lds-standard-works-minimalist": (
        "minimalist", "The Standard Works (All Five Books)",
        "Old Testament, New Testament, Book of Mormon, D&C and Pearl of Great Price in one file."),
    "old-testament-minimalist": ("minimalist", "The Old Testament", "KJV, chapters and verses only."),
    "new-testament-minimalist": ("minimalist", "The New Testament", "KJV, chapters and verses only."),
    "book-of-mormon-minimalist": ("minimalist", "The Book of Mormon", "Chapters and verses only."),
    "doctrine-and-covenants-minimalist": ("minimalist", "The Doctrine and Covenants", "Sections and verses only."),
    "pearl-of-great-price-minimalist": ("minimalist", "The Pearl of Great Price", "Chapters and verses only."),
    "book-of-mormon-narrative": (
        "reading-editions", "The Book of Mormon: Narrative Edition",
        "Reads like a story, with tap-to-see verse ranges."),
    "book-of-mormon-1830-narrative": (
        "reading-editions", "The Book of Mormon (1830): Narrative Edition",
        "The original text as a continuous read."),
    "new-testament-narrative": (
        "reading-editions", "The New Testament: Narrative Edition", "KJV as a continuous read with verse pop-ups."),
    "book-of-mormon-study-notebook": (
        "reading-editions", "The Book of Mormon: Study Notebook", "Wide margins for your own notes."),
    "book-of-mormon-onomasticon": (
        "study-editions", "Book of Mormon: Names Study Edition", "Tap any name for its meaning and pronunciation."),
    "book-of-mormon-red-letter": (
        "study-editions", "Book of Mormon: Red-Letter Edition", "The words of Jesus Christ and the Lord highlighted."),
    "book-of-mormon-master-study": (
        "study-editions", "Book of Mormon: Master Study Edition",
        "Red-letter speech, name meanings and 19th-century public-domain citations combined."),
    "book-of-mormon-historical-variants": (
        "study-editions", "Book of Mormon: Textual Variants", "Compare the text across eight editions, 1830 to 2013."),
    "bom-intertextual-parallels": (
        "study-editions", "Book of Mormon: Parallels", "Isaiah beside the KJV, and 3 Nephi beside Matthew."),
    "bom-poetic-and-chiasmus": (
        "study-editions", "Book of Mormon: Poetry & Chiasmus", "Alma 36, Psalms and Hebrew-style parallelism."),
    "top-1000-cited-verses": (
        "study-editions", "The Top 1,000 Cited Verses", "The most-quoted verses in 19th-century Restoration sermons (JoD & TPJS, 1830–1886)."),
    "kjv-apocrypha": ("apocrypha", "The KJV Apocrypha", "The books printed between the Testaments in 1611."),
    "enoch-jubilees-jasher": ("apocrypha", "Enoch, Jubilees & Jasher", "Three ancient texts in one volume."),
    "complete-apocrypha-pseudepigrapha-compendium": (
        "apocrypha", "Complete Apocrypha & Pseudepigrapha", "72 public-domain extra-canonical works with provenance dossiers."),
    "foundational-lds-classics-anthology": (
        "literature", "Foundational Classics of the Restoration", "Nine doctrinal classics with pop-up notes."),
    "complete-lds-literature-compendium": (
        "literature", "Complete Restoration Literature", "71 historical books in a single large file."),
}


def human_size(n: int) -> str:
    return f"{n / 1_048_576:.1f} MB" if n >= 1_048_576 else f"{max(1, round(n / 1024))} KB"


def card(stem: str, coll: str, title: str, blurb: str, size: int, has_cover: bool) -> str:
    t, b = html.escape(title), html.escape(blurb)
    search = html.escape(f"{title} {blurb}".lower(), quote=True)
    cover = (
        f'<img src="covers/{stem}.png" alt="" width="160" height="240" loading="lazy">'
        if has_cover else ""
    )
    return (
        f'<article class="card" data-collection="{coll}" data-search="{search}">'
        f"{cover}"
        f'<h3><a class="card-link" href="downloads/{stem}.epub" download>{t}</a></h3>'
        f"<p>{b}</p>"
        f"<footer><span>EPUB · {human_size(size)}</span><span aria-hidden=\"true\">↓ Download</span></footer>"
        f"</article>"
    )


def main() -> None:
    (SITE / "downloads").mkdir(parents=True, exist_ok=True)
    (SITE / "covers").mkdir(parents=True, exist_ok=True)

    catalog: list[dict] = []
    sections: list[str] = []
    for cid, ctitle, cblurb in COLLECTIONS:
        cards = []
        for stem, (coll, title, blurb) in ENTRIES.items():
            if coll != cid:
                continue
            src = DIST_EPUBS / f"{stem}.epub"
            if not src.exists():
                print(f"skip (not built): {stem}")
                continue
            shutil.copy2(src, SITE / "downloads" / src.name)
            cover = DIST_COVERS / f"{stem}.png"
            has_cover = cover.exists()
            if has_cover:
                shutil.copy2(cover, SITE / "covers" / cover.name)
            size = src.stat().st_size
            catalog.append({"id": stem, "collection": cid, "title": title, "description": blurb,
                            "size_bytes": size, "file": f"downloads/{stem}.epub"})
            cards.append(card(stem, cid, title, blurb, size, has_cover))
        if cards:
            sections.append(
                f'<section class="collection" id="{cid}"><h2>{html.escape(ctitle)}</h2>'
                f'<p>{html.escape(cblurb)}</p><div class="grid">{"".join(cards)}</div></section>'
            )

    active = {c["collection"] for c in catalog}
    chips = '<button class="chip" data-filter="all" aria-pressed="true">All</button>' + "".join(
        f'<button class="chip" data-filter="{cid}" aria-pressed="false">{html.escape(t)}</button>'
        for cid, t, _ in COLLECTIONS if cid in active
    )
    total_mb = sum(c["size_bytes"] for c in catalog) / 1_048_576

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Proteus · Scripture EPUBs</title>
<meta name="description" content="E-reader-friendly EPUB editions of the standard works, apocrypha, study editions and reading guides.">
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="hero"><div class="wrap">
  <p class="eyebrow">Proteus Scriptorium · Free &amp; Non-Commercial</p>
  <h1>Scripture, ready for your e-reader</h1>
  <p class="lede">Free, non-profit EPUB editions of the standard works, public-domain apocrypha, and study resources—formatted for Kindle and modern e-readers.</p>
  <ul class="stats">
    <li><strong>{len(catalog)}</strong>editions</li>
    <li><strong>{len(active)}</strong>collections</li>
    <li><strong>{total_mb:,.0f} MB</strong>of reading</li>
  </ul>
</div></header>
<div class="controls"><div class="wrap">
  <input class="search" id="search" type="search" placeholder="Search editions…" aria-label="Search editions" autocomplete="off">
  <div class="chips" role="group" aria-label="Filter by collection">{chips}</div>
</div></div>
<main class="wrap">
{"".join(sections)}
<p class="empty" id="empty" hidden>No editions match your search.</p>
<section class="howto" id="howto"><h2>How to read these on your device</h2><ul>
  <li><strong>Kindle:</strong> use <em>Send to Kindle</em> (email or app), then open the file from your library.</li>
  <li><strong>Apple Books, Kobo, Google Play Books:</strong> open the downloaded .epub directly.</li>
  <li><strong>Computer:</strong> any EPUB reader works, such as Calibre or Thorium.</li>
</ul></section>
<section class="howto" id="attribution"><h2>Sources, Attribution &amp; Non-Commercial Notice</h2><ul>
  <li><strong>Non-Profit &amp; Educational Purpose:</strong> All Proteus EPUB editions are distributed strictly free of charge for personal, non-commercial, and educational scripture study.</li>
  <li><strong>Public-Domain Texts:</strong> Canonical texts (1769 King James Bible, 1830–1920 Book of Mormon, pre-1929 Doctrine &amp; Covenants and Pearl of Great Price), 71 historical Restoration volumes (1833–1927, via Project Gutenberg and the Mormon Documentation Project), and all 72 works in the Apocrypha &amp; Pseudepigrapha Compendium (1611 KJV Apocrypha, R. H. Charles 1896–1917, M. R. James 1917–1924, Richard Laurence 1821/1883, Ante-Nicene Fathers Vol. VIII 1886, Archbishop William Wake 1693, Rutherford H. Platt 1926, and Prof. Robert A. Kraft’s 1987 CATSS Public Domain / Free Non-Commercial edition of 4 Baruch) are drawn from public-domain translations.</li>
  <li><strong>Academic &amp; Digital Archives:</strong> Grateful attribution is given to the <a href="https://onoma.lib.byu.edu/">BYU Book of Mormon Onomasticon Project</a> (ed. Paul Y. Hoskisson), the <a href="https://scriptures.byu.edu/">BYU Scripture Citation Index</a> (Stephen W. Liddle &amp; Richard C. Galbraith; restricted here to pre-1942 public-domain <em>Journal of Discourses</em> 1839–1886 and <em>Teachings of the Prophet Joseph Smith</em> 1830–1844), Grant Hardy’s BYU OpenScripture 1830–2013 Book of Mormon variant collation, the Internet Sacred Text Archive (John Bruno Hare), Early Jewish Writings (Peter Kirby), and the Wesley Center for Applied Theology.</li>
  <li><strong>No Official Affiliation:</strong> Proteus is an independent, non-profit educational project and is not affiliated with or endorsed by The Church of Jesus Christ of Latter-day Saints or Brigham Young University.</li>
</ul></section>
</main>
<footer><div class="wrap">Built with Proteus · Free for personal, non-commercial educational study.</div></footer>
<script src="app.js" type="module"></script>
</body>
</html>
"""
    (SITE / "index.html").write_text(page, encoding="utf-8")
    (SITE / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Built site with {len(catalog)} editions -> {SITE}")


if __name__ == "__main__":
    main()

