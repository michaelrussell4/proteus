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
│   ├── covers/                            # 29 High-DPI (1200×1920) Proteus Scriptorium PNG covers
│   └── epubs/                             # 29 Validated EPUB3 volumes ready for Kindle Paperwhite / KFX
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

## Complete Catalogue of 29 Generated EPUB3 Editions (`dist/epubs/`)

### Phase 1: Foundational Canon, Mega-Compendiums, Apocrypha & Restoration Classics
| Edition Slug | Output File | Highlights |
| :--- | :--- | :--- |
| `complete-apocrypha-pseudepigrapha-compendium` | `dist/epubs/complete-apocrypha-pseudepigrapha-compendium.epub` | **72 public-domain extra-canonical books** (1,376 chapters, 1,169 pop-up notes) uniting `kjv-apocrypha/`, `apocrypha-ista/`, `apocrypha-gutenberg/`, and public-domain works from `https://www.pseudepigrapha.com/` with **zero duplicates** and a researched **Source, Provenance & Historical Veracity Dossier** at the start of every single book. |
| `complete-lds-literature-compendium` | `dist/epubs/complete-lds-literature-compendium.epub` | **All 71 historical Latter-day Saint books** (1,982 chapters, 5.91M words, 3,276 pop-up footnotes) organized across 7 thematic divisions (*Foundational Theology*, *Doctrinal Treatises*, *Church History*, *Biographies*, *Discourses*, *Defense & Polemics*, *Faith-Promoting Series*). |
| `foundational-lds-classics-anthology` | `dist/epubs/foundational-lds-classics-anthology.epub` | *Foundational Classics of the Restoration*: 9 landmark doctrinal works (*Lectures on Faith*, *Wentworth Letter*, *Jesus the Christ* [chapters 1–42 verified in exact sequential order], *Articles of Faith*, *House of the Lord*, *Key to the Science of Theology*, *A Voice of Warning*, *Discourses of Brigham Young*, *Gospel Doctrine*) with **3,276 recovered inline pop-up footnotes & endnotes**. |
| `kjv-apocrypha` | `dist/epubs/kjv-apocrypha.epub` | Complete 15-book King James Deuterocanon (1 Esdras through 2 Maccabees, including the Prayer of Manasseh and Additions to Esther/Daniel). |
| `enoch-jubilees-jasher` | `dist/epubs/enoch-jubilees-jasher.epub` | R. H. Charles *1 Enoch*, Richard Laurence 1883 *1 Enoch*, R. H. Charles *Book of Jubilees* (with **1,148 scholarly pop-up footnotes**), and the 1840 *Book of Jasher*. |
| `book-of-mormon` | `dist/epubs/book-of-mormon.epub` | 2013 Standard Works baseline edition (including Origin, Title Page, and Testimonies of the Three and Eight Witnesses). |
| `book-of-mormon-1830` | `dist/epubs/book-of-mormon-1830.epub` | Original 1830 Palmyra edition text arranged in modern chapter/verse structure (including Title Page and Witnesses). |
| `doctrine-and-covenants` | `dist/epubs/doctrine-and-covenants.epub` | 2013 Doctrine and Covenants baseline edition. |
| `pearl-of-great-price` | `dist/epubs/pearl-of-great-price.epub` | 2013 Pearl of Great Price with encoding repairs. |

### Phase 2: Canonical Transformations, Clean Editions & Structural Formatting
| Edition Slug | Output File | Highlights |
| :--- | :--- | :--- |
| `old-testament-minimalist` | `dist/epubs/old-testament-minimalist.epub` | Clean Old Testament (39 books, 929 chapters) keeping chapters and verse numbers intact with zero footnotes or study clutter. |
| `new-testament-minimalist` | `dist/epubs/new-testament-minimalist.epub` | Clean New Testament (27 books, 260 chapters) keeping chapters and verse numbers intact with zero footnotes. |
| `book-of-mormon-minimalist` | `dist/epubs/book-of-mormon-minimalist.epub` | Clean Book of Mormon (15 books, 239 chapters, plus Title Page & Testimonies of the Three and Eight Witnesses) keeping chapters and verse numbers intact with zero footnotes. |
| `doctrine-and-covenants-minimalist` | `dist/epubs/doctrine-and-covenants-minimalist.epub` | Clean Doctrine and Covenants (138 sections) keeping sections and verse numbers intact with zero footnotes. |
| `pearl-of-great-price-minimalist` | `dist/epubs/pearl-of-great-price-minimalist.epub` | Clean Pearl of Great Price (5 books, 16 chapters) keeping chapters and verse numbers intact with zero footnotes. |
| `lds-standard-works-minimalist` | `dist/epubs/lds-standard-works-minimalist.epub` | **Complete LDS Standard Works Clean Quad** combining all 5 Standard Works (OT + NT + BoM [with Witnesses] + D&C + PoGP; **87 books, 1,586 individually navigable chapters, 1.19M words**) with chapters and verse numbers preserved and zero footnotes. |
| `book-of-mormon-narrative` | `dist/epubs/book-of-mormon-narrative.epub` | Continuous narrative prose reassembled from punctuation/discourse heuristics with normalized mid-sentence capitalization, Witnesses front matter, and **1,953 `[¶v1–5]` pop-up verse-range locators**. |
| `book-of-mormon-1830-narrative` | `dist/epubs/book-of-mormon-1830-narrative.epub` | Continuous narrative edition of the 1830 Palmyra text with Witnesses front matter (**1,862 pop-up range locators**). |
| `new-testament-narrative` | `dist/epubs/new-testament-narrative.epub` | The Four Gospels through Revelation in flowing literary paragraphs (**1,165 pop-up range locators**). |
| `book-of-mormon-study-notebook` | `dist/epubs/book-of-mormon-study-notebook.epub` | Wide-margin layout with ruled reflection grids at the end of every chapter for Kindle Scribe / Paperwhite annotations. |

### Phase 3: Enriched & Relational Compilations (With Extended Multi-Paragraph Sermon Excerpts)
| Edition Slug | Output File | Highlights |
| :--- | :--- | :--- |
| `book-of-mormon-master-study` | `dist/epubs/book-of-mormon-master-study.epub` | **Relational Master Study Edition** combining `◈` BYU Onomasticon inline etymology links and `[★N]` 19th-century Historical Citation badges (1830–1886 *Journal of Discourses* & *Teachings of the Prophet Joseph Smith*) with **up to 4 extended multi-paragraph discourse excerpts** per verse (**6,214 total pop-up notes**). |
| `top-1000-cited-verses` | `dist/epubs/top-1000-cited-verses.epub` | The 1,000 most frequently quoted verses across the OT, NT, BoM, D&C, and PoGP in 19th-century LDS discourse (**1,100 pop-up dossiers with up to 3 extended multi-paragraph discourse excerpts per verse**). |
| `book-of-mormon-onomasticon` | `dist/epubs/book-of-mormon-onomasticon.epub` | Links proper nouns on first occurrence per chapter to the BYU Book of Mormon Onomasticon (IPA pronunciation and ancient Hebrew/Egyptian etymologies; **3,604 pop-up entries**). |

### Phase 4: Computational Data Science, Language Models, Historical Variants, Poetics & Guides
| Edition Slug | Output File | Highlights |
| :--- | :--- | :--- |
| `lds-standard-works-data-science` | `dist/epubs/lds-standard-works-data-science.epub` | **The Data Science Standard Works**: Complete 5-volume computational edition (88 books, 1,587 chapters, 1.19M words, **12,079 pop-up notes**) featuring **6 embedded high-DPI PNG data visualization plates**, chapter-level NLP telemetry ribbons (Shannon Entropy $H$, MATTR lexical diversity, affect sparkbar, 8-factor NMF topics, TF-IDF signatures), SPPMI-SVD distributional word embeddings, inline **Named Entity Recognition** (`▲` Geo-Locations, `◈` Personal Names, `▪` Peoples/Artifacts), inline **Canon Hapax Legomena (`★1×` used once in all scripture)** and **Dis Legomena (`◆2×` used twice, quoting the other verse)**, and hyperlinked Master Concordances. |
| `bom-language-model-correlations` | `dist/epubs/bom-language-model-correlations.epub` | **The Book of Mormon: Language Model Biblical Correlation Edition**: Powered by a 4-channel Scriptural Language Model (Stemmed Phrase TF-IDF, Focal Top-IDF Clause Containment, KJV Cadence Trigrams, and 96-d SPPMI-SVD + LSA Embeddings) trained across all 41,995 canonical verses and empirically calibrated across a 3-Tier threshold regime ($r \ge 0.45$). Highlights shared stems inline, provides **3,250 pop-up footnotes** with full KJV verses and model telemetry, includes 2 calibration/density plates and a Top 120 Embedded Correlations leaderboard, and links bidirectionally to a complete **Correlated Old & New Testament Parallel Treasury**. |
| `book-of-mormon-historical-variants` | `dist/epubs/book-of-mormon-historical-variants.epub` | 8-Edition Collation (1830, 1837, 1840, 1841, 1879, 1920, 1981, 2013) with inline `<del>`/`<ins>` diffs and `[Δ Year]` chronological pop-up apparatuses. |
| `bom-intertextual-parallels` | `dist/epubs/bom-intertextual-parallels.epub` | Word-level intertextual alignment of Book of Mormon Isaiah chapters vs. KJV Isaiah and the 3 Nephi 12–14 Sermon at the Temple vs. Matthew 5–7 (`[⇄ diffs]` pop-ups). |
| `bom-poetic-and-chiasmus` | `dist/epubs/bom-poetic-and-chiasmus.epub` | Concentric structural typography for famous chiasms (including the 17-level Alma 36 masterwork, Mosiah 3:18–19, Mosiah 5:10–12, Alma 41:13–15, Helaman 6:10) plus 10 prophetic psalms and poems in indented parallel couplets. |
| `early-modern-english-scripture-guide` | `dist/epubs/early-modern-english-scripture-guide.epub` | **An Early Modern English Guide to Reading the Scriptures**: Comprehensive philological manual covering the 2nd-person pronoun paradigm (*thou/thee* vs. *ye/you*), verbal morphology (*-est*, *-eth*, subjunctive mood), syntactic structures, a 100-word lexical glossary of archaic "false friends", Hebraisms, and **interactive pop-up scripture citations**. |
| `early-modern-english-quick-guide` | `dist/epubs/early-modern-english-quick-guide.epub` | **Reading Old English Scripture: A Quick Guide**: Accessible, plain-language companion to *thou/ye*, *-eth/-est*, archaic syntax, and 100+ words whose meanings have shifted since 1611/1830. |

---

## Static Portal & GitHub Pages Deployment (`site/`)

To build the static web portal (`site/index.html`, `site/catalog.json`, `site/downloads/*.epub`, `site/covers/*.png`) after building EPUBs:

```powershell
uv run python scripts/build_site.py
```

Pushing to `main` automatically deploys `site/` to GitHub Pages via `.github/workflows/deploy.yml`.
