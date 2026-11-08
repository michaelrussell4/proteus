# Proteus — Computational Scripture & Literature EPUB3 Publishing Engine

**Proteus** is a Python publishing pipeline and computational text-transformation engine that compiles commercial-grade, Kindle Paperwhite–optimized **EPUB3 volumes** across the Latter-day Saint (LDS) scriptural canon, biblical apocrypha and pseudepigrapha, historical print editions (1830–2013), Early Modern English philology, and 19th/early-20th-century Restoration literature.

Every generated volume includes a bespoke high-resolution **Proteus Scriptorium** cover (`1200×1920`, embedded at `OEBPS/images/cover.png` and archived in `dist/covers/`) and passes both custom structural/pop-up footnote verification (`lxml`) and the official **W3C `epubcheck 5.3.0`** validator with zero errors and zero warnings.

🌐 **Live Digital Library (GitHub Pages):** [https://michaelrussell4.github.io/proteus/](https://michaelrussell4.github.io/proteus/)

---

## Repository Structure

```text
proteus/
├── data/
│   └── raw/
│       ├── lds-standard-works/            # 2013 LDS Standard Works JSON (OT, NT, BoM, D&C, PoGP)
│       ├── bom-historical-editions/       # 8 Historical BoM printings (1830–2013) + OpenScripture data
│       ├── lds-historical-literature/     # 71 Historical Restoration books (clean/*.jsonl + epub/*.epub)
│       ├── kjv-apocrypha/                 # 15 King James Version Deuterocanonical JSONL books
│       ├── apocrypha-ista/                # 12 ISTA Apocrypha & Pseudepigrapha JSONL corpora
│       ├── apocrypha-gutenberg/           # Laurence 1883 1 Enoch & Ante-Nicene Fathers Vol. 8 JSONL
│       ├── apocrypha-pseudepigrapha-com/  # 40 Ancient works scraped from https://www.pseudepigrapha.com/
│       ├── bom-onomasticon/               # BYU Book of Mormon Onomasticon lexical database
│       └── scripture-citation-index/      # BYU Pre-1960 Scripture Citation Index & full discourse texts
├── dist/
│   ├── covers/                            # 17 High-DPI (1200×1920) Proteus Scriptorium PNG covers
│   └── epubs/                             # 17 Validated EPUB3 volumes ready for Kindle Paperwhite / KFX
├── site/                                  # Static GitHub Pages portal (deployed via .github/workflows/deploy.yml)
├── scripts/
│   ├── build_site.py                      # Static site & catalog generator (dist/ -> site/)
│   └── scrape_pseudepigrapha_com.py       # Reproducible scraper for https://www.pseudepigrapha.com/
├── src/
│   └── proteus/
│       ├── core/                          # Canonical AST models, URN resolver & smart typography engine
│       ├── ingest/                        # Corpus ingesters, provenance dossiers & EME reference guide
│       ├── transforms/                    # Narrative, Minimalist, Enriched, Variants & Poetics engines
│       ├── renderers/epub/                # Deterministic EPUB3 compiler, Jinja2 templates, CSS & Cover engine
│       ├── validation/                    # Two-tier lxml + W3C epubcheck 5.3.0 validation suite
│       └── cli.py                         # Typer + Rich command-line interface
├── pyproject.toml
└── README.md
```

---

## Key Architectural Features

1. **Unified Canonical AST (`src/proteus/core/`):**
   - Strict Pydantic v2 hierarchy (`Work` → `Book` → `Chapter` → `ContentBlock` / `Verse` + `Annotation`).
   - Canonical URN resolver (`bofm:1-ne:3:7`, `ot:isa:48:1`, `apoc:1-enoch:1:1`) that bridges historical printings, the BYU Scripture Citation Index, and the BYU Book of Mormon Onomasticon.
   - Smart typographic & grammar normalizer (`typography.py`) that repairs upstream encoding artifacts, converts straight quotes to curly quotes (`“ ”` / `‘ ’`), normalizes em-dashes (`—`), repairs ungrammatical mid-sentence capital letters following em-dashes and cross-verse continuations, and unwraps hard-wrapped Gutenberg lines.

2. **Kindle Paperwhite / KFX Enhanced Typesetting Engine (`src/proteus/renderers/epub/`):**
   - **Deterministic EPUB3 Packaging:** Uncompressed `mimetype` first byte, `META-INF/container.xml`, EPUB 3.3 `content.opf`, semantic `nav.xhtml` (`epub:type="toc"` + `landmarks`), and legacy `toc.ncx` fallback.
   - **Proteus Scriptorium Cover Generator (`covers.py`):** Programmatically renders supersampled (`1600×2560` → `1200×1920` Lanczos) fine-press covers with tracked `Constantia` & `Palatino Linotype` display typography, standardized series headers (`Clean Editions`, `Standard Works`, `Reader's Series`, `Study Series`, `Ancient Texts`, `Historical Library`, `Philology Series`), high-contrast edition pills, and large centerpiece illustrations (`codex`, `liahona`, `tree`, `collation`, `seal`, `arch`, `rose`).
   - **Native Kindle Pop-Up Footnotes:** Every footnote, multi-paragraph discourse excerpt, etymology entry, verse-range locator, and textual variant apparatus is rendered using bidirectional `<a epub:type="noteref" id="ref-..." href="#fn-...">` and `<aside epub:type="footnote" id="fn-...">` pairs for instant modal pop-ups on Kindle Paperwhite (scrubbed of unsupported SMP glyphs so every character renders cleanly on Kindle).
   - **6 Tailored Stylesheets (`styles/*.css`):** Resilient to Kindle dark mode (`@media (prefers-color-scheme: dark)`), e-ink grayscale contrast, drop caps, and user font/margin overrides.

3. **Two-Tier Automated Validation (`src/proteus/validation/epub_validator.py`):**
   - **Tier 1 (`lxml`):** Verifies strict XHTML5 well-formedness, zero broken internal `href="#..."` targets, zero duplicate XML IDs, and 100% pop-up footnote reciprocity.
   - **Tier 2 (`epubcheck 5.3.0`):** Runs the official W3C/IDPF Java EPUBCheck suite against every compiled `.epub`.

---

## CLI Usage (`uv`)

List all registered editions across Phases 1–4:

```powershell
uv run proteus list
```

Build a single edition, an entire phase (`phase1`, `phase2`, `phase3`, `phase4`), or `all`:

```powershell
uv run proteus build phase1
uv run proteus build phase2
uv run proteus build phase3
uv run proteus build phase4
uv run proteus build early-modern-english-scripture-guide
uv run proteus build all
```

Validate any generated `.epub` file or directory:

```powershell
uv run proteus validate dist/epubs/
```

---

## Complete Catalogue of 17 Generated EPUB3 Editions (`dist/epubs/`)

### Phase 1: Canonical Standard Works
| Edition Slug | Output File | Highlights |
| :--- | :--- | :--- |
| `old-testament` | `dist/epubs/old-testament.epub` | Complete 39-book King James Version Old Testament (929 chapters, 23,145 verses) with canonical 2013 chapter headnotes. |
| `new-testament` | `dist/epubs/new-testament.epub` | Complete 27-book King James Version New Testament (260 chapters, 7,957 verses) featuring Gospels, Acts, Epistles & Revelation with 2013 headnotes. |
| `book-of-mormon` | `dist/epubs/book-of-mormon.epub` | 2013 Standard Works canonical text (including Origin, Title Page, and Testimonies of the Three and Eight Witnesses). |
| `book-of-mormon-1830` | `dist/epubs/book-of-mormon-1830.epub` | Original 1830 Palmyra edition text arranged in modern chapter/verse structure (including Title Page and Witnesses). |
| `doctrine-and-covenants` | `dist/epubs/doctrine-and-covenants.epub` | 2013 Doctrine and Covenants canonical edition with section headnotes. |
| `pearl-of-great-price` | `dist/epubs/pearl-of-great-price.epub` | 2013 Pearl of Great Price with complete Moses, Abraham, JS—Matthew, JS—History, and Articles of Faith. |

### Phase 2: Apocrypha, Ancient Texts & Restoration Literature
| Edition Slug | Output File | Highlights |
| :--- | :--- | :--- |
| `kjv-apocrypha` | `dist/epubs/kjv-apocrypha.epub` | Complete 15-book King James Deuterocanon (1 Esdras through 2 Maccabees, including the Prayer of Manasseh and Additions to Esther/Daniel) prefaced by D&C 91. |
| `enoch-jubilees-jasher` | `dist/epubs/enoch-jubilees-jasher.epub` | R. H. Charles *1 Enoch*, Richard Laurence 1883 *1 Enoch*, R. H. Charles *Book of Jubilees* (with **1,148 scholarly pop-up footnotes**), and the 1840 *Book of Jasher*. |
| `complete-apocrypha-pseudepigrapha-compendium` | `dist/epubs/complete-apocrypha-pseudepigrapha-compendium.epub` | **72 public-domain extra-canonical books** (1,376 chapters, 1,169 pop-up notes) uniting `kjv-apocrypha/`, `apocrypha-ista/`, `apocrypha-gutenberg/`, and public-domain works from `https://www.pseudepigrapha.com/` with **zero duplicates** and a researched **Source, Provenance & Historical Veracity Dossier** at the start of every single book. |
| `foundational-lds-classics-anthology` | `dist/epubs/foundational-lds-classics-anthology.epub` | *Foundational Classics of the Restoration*: 9 landmark doctrinal works (*Lectures on Faith*, *Wentworth Letter*, *Jesus the Christ* [chapters 1–42 verified in exact sequential order], *Articles of Faith*, *House of the Lord*, *Key to the Science of Theology*, *A Voice of Warning*, *Discourses of Brigham Young*, *Gospel Doctrine*) with **3,276 recovered inline pop-up footnotes & endnotes**. |
| `complete-lds-literature-compendium` | `dist/epubs/complete-lds-literature-compendium.epub` | **All 71 historical Latter-day Saint books** (1,982 chapters, 5.91M words, 3,276 pop-up footnotes) organized across 7 thematic divisions (*Foundational Theology*, *Doctrinal Treatises*, *Church History*, *Biographies*, *Discourses*, *Defense & Polemics*, *Faith-Promoting Series*). |

### Phase 3: Relational, Historical Variants & Citations
| Edition Slug | Output File | Highlights |
| :--- | :--- | :--- |
| `book-of-mormon-master-study` | `dist/epubs/book-of-mormon-master-study.epub` | **Relational Master Study Edition** combining `◈` BYU Onomasticon inline etymology links and `[★N]` 19th-century Historical Citation badges (1830–1886 *Journal of Discourses* & *Teachings of the Prophet Joseph Smith*) with **up to 4 extended multi-paragraph discourse excerpts** per verse (**6,214 total pop-up notes**). |
| `top-1000-cited-verses` | `dist/epubs/top-1000-cited-verses.epub` | The 1,000 most frequently quoted verses across the OT, NT, BoM, D&C, and PoGP in 19th-century LDS discourse (**1,100 pop-up dossiers with up to 3 extended multi-paragraph discourse excerpts per verse**). |
| `book-of-mormon-historical-variants` | `dist/epubs/book-of-mormon-historical-variants.epub` | 8-Edition Collation (1830, 1837, 1840, 1841, 1879, 1920, 1981, 2013) with inline `<del>`/`<ins>` diffs and `[Δ Year]` chronological pop-up apparatuses (3,581 pop-up notes). |
| `bom-intertextual-parallels` | `dist/epubs/bom-intertextual-parallels.epub` | Word-level intertextual alignment of Book of Mormon Isaiah chapters vs. KJV Isaiah and the 3 Nephi 12–14 Sermon at the Temple vs. Matthew 5–7 (**395 diff pop-ups across 22 chapters**). |

### Phase 4: Philology & Data Science
| Edition Slug | Output File | Highlights |
| :--- | :--- | :--- |
| `early-modern-english-scripture-guide` | `dist/epubs/early-modern-english-scripture-guide.epub` | **An Early Modern English Guide to Reading the Scriptures**: Comprehensive philological manual covering the 2nd-person pronoun paradigm (*thou/thee* vs. *ye/you*), verbal morphology (*-est*, *-eth*, subjunctive mood), syntactic structures, a 100-word lexical glossary of archaic "false friends", Hebraisms, and **interactive pop-up scripture citations**. |
| `lds-standard-works-data-science` | `dist/epubs/lds-standard-works-data-science.epub` | **The Data Science Standard Works**: Complete 5-volume computational edition (87 books, 1,582 chapters, 1.17M words, **12,079 pop-up notes**) featuring **6 embedded high-DPI PNG data visualization plates**, chapter-level NLP telemetry ribbons (Shannon Entropy $H$, MATTR lexical diversity, affect sparkbar, 8-factor NMF topics, TF-IDF signatures), SPPMI-SVD distributional word embeddings, inline **Named Entity Recognition** (`▲` Geo-Locations, `◈` Personal Names, `▪` Peoples/Artifacts), inline **Canon Hapax Legomena (`★1×` used once in all scripture)** and **Dis Legomena (`◆2×` used twice, quoting the other verse)**, and hyperlinked Master Concordances. |

---

## Static Portal & GitHub Pages Deployment (`site/`)

To build the static web portal (`site/index.html`, `site/catalog.json`, `site/downloads/*.epub`, `site/covers/*.png`) after building EPUBs:

```powershell
uv run python scripts/build_site.py
```

Pushing to `main` automatically deploys `site/` to GitHub Pages via `.github/workflows/deploy.yml`.
