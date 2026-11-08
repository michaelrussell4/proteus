"""Build the Proteus Scriptorium static portal into `site/` (and optionally sync `../proteus-project`).

Reads the compiled EPUBs in `dist/epubs` and covers in `dist/covers`, copies them into
`site/downloads` and `site/covers`, and writes `site/index.html` + `site/catalog.json`
with the full interactive `<dialog>` modal catalog, light/dark theme support, and instant search.

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

COLLECTIONS = [
    ("all", "All Editions"),
    ("standard-works", "Standard Works"),
    ("study-editions", "Study Editions"),
    ("apocrypha", "Apocrypha & Ancient Texts"),
    ("literature", "Restoration Literature"),
    ("reading-guides", "Reading Guides"),
]

COLLECTION_LABELS = dict(COLLECTIONS)

# Detailed metadata for all 17 active Proteus editions
EDITION_CATALOG_SPECS: list[dict] = [
    # --- Standard Works (Canonical & 1830 Historical) ---
    {
        "id": "old-testament",
        "title": "The Old Testament",
        "subtitle": "The Authorized King James Version with Canonical 2013 Chapter Headnotes",
        "collection": "standard-works",
        "badge": "39 Canonical Books",
        "creator": "King James Translators & Prophets of Ancient Israel",
        "short_desc": "The complete 39-book King James Version Old Testament with canonical 2013 chapter headnotes.",
        "full_desc": "The canonical 2013 Latter-day Saint edition of the Old Testament in the King James Version (Genesis through Malachi; 39 books, 929 chapters, 23,145 verses). Optimized for Kindle Paperwhite with clean chapter and verse typography and canonical chapter headnotes.",
        "highlights": [
            "Complete 39 books of the Old Testament (929 chapters, 610,000+ words)",
            "Includes canonical 2013 chapter headnotes",
            "Fine-press typography tuned for Kindle e-ink displays",
        ],
        "contents_summary": "The Law (Genesis–Deuteronomy), History (Joshua–Esther), Poetry & Wisdom (Job–Song of Solomon), and the Prophets (Isaiah–Malachi).",
    },
    {
        "id": "new-testament",
        "title": "The New Testament",
        "subtitle": "The Authorized King James Version with Canonical 2013 Chapter Headnotes",
        "collection": "standard-works",
        "badge": "27 Canonical Books",
        "creator": "King James Translators & Apostles of the Lord Jesus Christ",
        "short_desc": "The complete 27-book King James Version New Testament with canonical 2013 chapter headnotes.",
        "full_desc": "The canonical 2013 Latter-day Saint edition of the New Testament in the King James Version (Matthew through Revelation; 27 books, 260 chapters, 7,957 verses). Features the Four Gospels, the Acts of the Apostles, the Pauline and General Epistles, and the Revelation of St. John with full canonical headnotes.",
        "highlights": [
            "Complete 27 books of the New Testament (260 chapters, 180,000+ words)",
            "The Four Gospels, Acts, Epistles, and Revelation",
            "Canonical 2013 chapter headnotes and clean Kindle typesetting",
        ],
        "contents_summary": "The Four Gospels (Matthew–John), Acts of the Apostles, Pauline Epistles (Romans–Hebrews), General Epistles (James–Jude), and Revelation.",
    },
    {
        "id": "book-of-mormon",
        "title": "The Book of Mormon",
        "subtitle": "Another Testament of Jesus Christ",
        "collection": "standard-works",
        "badge": "Standard Edition",
        "creator": "Translated by Joseph Smith, Jun.",
        "short_desc": "The complete 2013 Standard Works edition with chapter synopses, Title Page, and Testimonies of the Three and Eight Witnesses.",
        "full_desc": "The canonical 2013 edition of the Book of Mormon, complete with introductory front matter (Origin, Title Page, Testimonies of the Three and Eight Witnesses), book headnotes, chapter synopses, and smart typographic normalization.",
        "highlights": [
            "Complete 2013 canonical text with chapter synopses",
            "Includes Title Page and Testimonies of the Three and Eight Witnesses",
            "Normalized em-dash capitalization and smart typography",
        ],
        "contents_summary": "Origin of the Book of Mormon, Title Page, Testimonies of the Three and Eight Witnesses, and 1 Nephi through Moroni (15 books, 239 chapters).",
    },
    {
        "id": "book-of-mormon-1830",
        "title": "The Book of Mormon (1830 Palmyra Edition)",
        "subtitle": "An Account Written by the Hand of Mormon, Upon Plates Taken from the Plates of Nephi",
        "collection": "standard-works",
        "badge": "1830 Palmyra Text",
        "creator": "Joseph Smith, Jun. (Author and Proprietor)",
        "short_desc": "The historic 1830 E. B. Grandin Palmyra printing with the Title Page, Witnesses, and canonical verse anchors.",
        "full_desc": "The original 1830 Palmyra edition of the Book of Mormon printed by E. B. Grandin, preserving early 19th-century diction and readings alongside canonical chapter/verse reference anchors and the Testimonies of the Three and Eight Witnesses.",
        "highlights": [
            "Authentic 1830 Palmyra text from the BYU OpenScripture collation",
            "Includes Title Page and Testimonies of the Three and Eight Witnesses",
            "Canonical chapter and verse locators for easy comparison",
        ],
        "contents_summary": "Title Page, Testimony of Three Witnesses, Testimony of Eight Witnesses, and 1 Nephi through Moroni (1830 Palmyra text).",
    },
    {
        "id": "doctrine-and-covenants",
        "title": "The Doctrine and Covenants",
        "subtitle": "Of The Church of Jesus Christ of Latter-day Saints",
        "collection": "standard-works",
        "badge": "Standard Edition",
        "creator": "Joseph Smith Jr., et al.",
        "short_desc": "The complete 2013 Standard Works edition of the Doctrine and Covenants with full introductory and section headnotes.",
        "full_desc": "The complete 2013 Standard Works text of the Doctrine and Covenants, including the Explanatory Introduction, Chronological Order of Contents, Section headnotes, Sections 1–138, and Official Declarations 1 and 2.",
        "highlights": [
            "Complete Sections 1–138 and Official Declarations 1 & 2",
            "Full historical section headnotes and chronological index",
            "Smart typography and corrected em-dash capitalization",
        ],
        "contents_summary": "Explanatory Introduction, Chronological Order of Contents, Sections 1–138, Official Declarations 1 and 2.",
    },
    {
        "id": "pearl-of-great-price",
        "title": "The Pearl of Great Price",
        "subtitle": "Selections from the Revelations, Translations, and Narrations of Joseph Smith",
        "collection": "standard-works",
        "badge": "Standard Edition",
        "creator": "Joseph Smith Jr.",
        "short_desc": "The complete 2013 Standard Works edition of the Pearl of Great Price with full chapter headnotes.",
        "full_desc": "The canonical 2013 edition of the Pearl of Great Price, including the Introductory Note, Book of Moses, Book of Abraham, Joseph Smith—Matthew, Joseph Smith—History, and the Articles of Faith.",
        "highlights": [
            "Complete text of Moses, Abraham, JS—Matthew, JS—History, and Articles of Faith",
            "Includes canonical chapter headnotes and introductory material",
        ],
        "contents_summary": "Introductory Note, Moses (8 chapters), Abraham (5 chapters), JS—Matthew, JS—History, Articles of Faith.",
    },
    # --- Study & Critical Editions ---
    {
        "id": "lds-standard-works-data-science",
        "title": "The Data Science Standard Works",
        "subtitle": "NLP, Named Entity Recognition, Hapax Legomena & Visual Analytics Across All Five Standard Works",
        "collection": "study-editions",
        "badge": "Data Science & NLP",
        "creator": "Proteus Computational Linguistics Lab",
        "short_desc": "Complete 5-volume Standard Works with inline NER (▲ Geo, ◈ Names, ▪ Peoples), ★1× Hapax Legomena, 6 data visual plates, and NLP chapter telemetry.",
        "full_desc": "A complete five-volume computational edition of the Old Testament, New Testament, Book of Mormon, Doctrine and Covenants, and Pearl of Great Price (87 books, 1,582 chapters, 41,995 verses, 1,168,587 words). Features 6 high-resolution fine-press PNG data visualization plates, chapter-level NLP telemetry ribbons (word count, Shannon entropy H, MATTR lexical diversity, affect sparkbar, 8-factor NMF topic, and TF-IDF signature terms), SPPMI-SVD distributional word embeddings, and interactive Kindle pop-up footnotes for Geo-Locations (▲), Personal Names (◈), Peoples/Artifacts (▪), Canon Hapax Legomena (★1× used only once in all scripture), and Dis Legomena (◆2× used only twice, quoting the other occurrence).",
        "highlights": [
            "6 high-DPI e-ink-optimized PNG data visualization plates & statistical tables",
            "Inline Named Entity Recognition (▲ Geo-Locations, ◈ Persons, ▪ Peoples) with BYU Onomasticon roots",
            "Highlights ★1× Canon Hapax Legomena (4,465 words) and ◆2× Dis Legomena (1,988 words) with cross-verse pop-ups",
            "Chapter-level NLP telemetry ribbon (Shannon Entropy H, 8-Factor NMF Topics, TF-IDF signatures)",
            "Master hyperlinked NER Gazetteers and Rare-Word Concordances",
        ],
        "contents_summary": "Part I: Computational Scripture Atlas, 6 Data Visualization Plates & Master NER/Hapax Indexes; Parts II–VI: Complete Old Testament, New Testament, Book of Mormon, Doctrine & Covenants, and Pearl of Great Price with inline NLP apparatus.",
    },
    {
        "id": "old-testament-master-study",
        "title": "The Old Testament (Master Study Edition)",
        "subtitle": "KJV with Parallel Translations (BSB • ASV • BBE), Cross-References & 19th-Century Citations",
        "collection": "study-editions",
        "badge": "Parallel & Historical Apparatus",
        "creator": "King James Translators & Proteus Publishing Engine",
        "short_desc": "The Old Testament with instant modal pop-ups for parallel translations (BSB, ASV, BBE), cross-references, and 19th-century sermon citations.",
        "full_desc": "The Old Testament in the Authorized King James Version (39 books, 929 chapters, 23,145 verses) augmented with two multi-tier interactive study channels: 1) Instant modal pop-ups for parallel translations comparing the KJV against modern scholarly (Berean Standard Bible), literal (American Standard Version 1901), and simplified paraphrase (Bible in Basic English) editions, along with curated Treasury of Scripture Knowledge cross-references ([⇄]), and 2) BYU Scripture Citation Index badges ([★ N]) documenting historical sermon citations in the Journal of Discourses (1839–1886) and Teachings of the Prophet Joseph Smith with primary discourse excerpts.",
        "highlights": [
            "Complete 39 Old Testament books with canonical 2013 chapter headnotes",
            "Parallel translation pop-ups ([⇄]) for Berean Standard Bible (BSB), ASV (1901), and Basic English (BBE)",
            "Curated Treasury of Scripture Knowledge & OpenBible scriptural cross-references",
            "Over 7,300 historical sermon citation badges ([★]) with extended primary discourse excerpts",
        ],
        "contents_summary": "Interactive Study Key, Genesis through Malachi with parallel translation ([⇄]) and historical citation ([★]) modal apparati.",
    },
    {
        "id": "new-testament-master-study",
        "title": "The New Testament (Master Study Edition)",
        "subtitle": "KJV with Parallel Translations (BSB • ASV • BBE), Cross-References & 19th-Century Citations",
        "collection": "study-editions",
        "badge": "Parallel & Historical Apparatus",
        "creator": "King James Translators & Proteus Publishing Engine",
        "short_desc": "The New Testament with instant modal pop-ups for parallel translations (BSB, ASV, BBE), cross-references, and 19th-century sermon citations.",
        "full_desc": "The New Testament in the Authorized King James Version (27 books, 260 chapters, 7,957 verses) augmented with two multi-tier interactive study channels: 1) Instant modal pop-ups for parallel translations comparing the KJV against modern scholarly (Berean Standard Bible), literal (American Standard Version 1901), and simplified paraphrase (Bible in Basic English) editions, along with curated Treasury of Scripture Knowledge cross-references ([⇄]), and 2) BYU Scripture Citation Index badges ([★ N]) documenting historical sermon citations in the Journal of Discourses (1839–1886) and Teachings of the Prophet Joseph Smith with primary discourse excerpts.",
        "highlights": [
            "Complete 27 New Testament books with canonical 2013 chapter headnotes",
            "Parallel translation pop-ups ([⇄]) for Berean Standard Bible (BSB), ASV (1901), and Basic English (BBE)",
            "Curated Treasury of Scripture Knowledge & OpenBible scriptural cross-references",
            "Over 5,000 historical sermon citation badges ([★]) with extended primary discourse excerpts",
        ],
        "contents_summary": "Interactive Study Key, Matthew through Revelation with parallel translation ([⇄]) and historical citation ([★]) modal apparati.",
    },
    {
        "id": "book-of-mormon-master-study",
        "title": "The Book of Mormon (Master Study Edition)",
        "subtitle": "With BYU Onomasticon Etymologies & 19th-Century Discourse Citations",
        "collection": "study-editions",
        "badge": "Flagship Study Edition",
        "creator": "Proteus Relational Publishing Engine",
        "short_desc": "The flagship relational study volume uniting BYU Onomasticon name etymologies (◈) and 19th-century Restoration sermon citations ([★]).",
        "full_desc": "The flagship relational study edition of the Book of Mormon. Unites two deep scholarly layers into a seamless Kindle Paperwhite reading experience: 1) BYU Book of Mormon Onomasticon etymology notes, IPA pronunciations, and ancient Semitic/Egyptian reconstructions for every proper name and toponym (◈), and 2) 19th-century public-domain discourse citations ([★]) connecting verses directly to early sermons in the Journal of Discourses (1839–1886) and Teachings of the Prophet Joseph Smith (1830–1844).",
        "highlights": [
            "BYU Onomasticon linguistic root definitions & IPA pronunciations for proper names",
            "19th-century sermon citation statistics and contextual discourse excerpts",
            "Includes Title Page and Testimonies of the Three and Eight Witnesses",
            "Over 6,200 interactive Kindle pop-up footnotes with zero missing glyphs",
        ],
        "contents_summary": "Interactive Study Key, Title Page, Testimonies of the Three and Eight Witnesses, and complete 2013 canonical text with Onomasticon and Citation Index pop-up apparati.",
    },
    {
        "id": "doctrine-and-covenants-master-study",
        "title": "The Doctrine and Covenants (Master Study Edition)",
        "subtitle": "Revelations of Joseph Smith with 19th-Century Citations ([★]) & Scriptural Etymologies (◈)",
        "collection": "study-editions",
        "badge": "Historical Citation Apparatus",
        "creator": "Joseph Smith, Jun. & Proteus Publishing Engine",
        "short_desc": "The 2013 Doctrine and Covenants with pre-1942 historical discourse citation badges ([★]) and Onomasticon etymology pop-ups (◈).",
        "full_desc": "The 2013 canonical Doctrine and Covenants (138 sections, 2 official declarations) enriched with interactive citation badges ([★ N]) connecting revelations directly to sermons in the Journal of Discourses and Teachings of the Prophet Joseph Smith, plus BYU Onomasticon linguistic etymological pop-ups for proper names and sacred terms.",
        "highlights": [
            "Complete 138 sections and Official Declarations 1 & 2 with section headnotes",
            "3,162 historical sermon citation badges ([★]) with extended multi-paragraph primary excerpts",
            "BYU Onomasticon linguistic root definitions and ancient etymologies (◈)",
            "Optimized Kindle pop-up footnotes and clean typographic formatting",
        ],
        "contents_summary": "Interactive Study Key, Sections 1 through 138, Official Declarations 1 & 2 with historical citation and Onomasticon apparati.",
    },
    {
        "id": "pearl-of-great-price-master-study",
        "title": "The Pearl of Great Price (Master Study Edition)",
        "subtitle": "Moses, Abraham & Joseph Smith History with BYU Onomasticon (◈) & Discourse Citations ([★])",
        "collection": "study-editions",
        "badge": "Onomasticon & Citation Apparatus",
        "creator": "Joseph Smith, Jun. & Proteus Publishing Engine",
        "short_desc": "The 2013 Pearl of Great Price with complete BYU Onomasticon etymologies (Kolob, Egyptus, Kokaubeam) and 19th-century citation badges.",
        "full_desc": "The 2013 canonical Pearl of Great Price (Moses, Abraham, Joseph Smith—Matthew, Joseph Smith—History, Articles of Faith) augmented with 1) Full BYU Onomasticon linguistic etymology pop-ups (◈) for ancient names and celestial terms (Kolob, Egyptus, Kokaubeam, Gnolaum, Elkenah, Olishem, etc.), and 2) 19th-century sermon citation badges ([★ N]) linking verses to discourses in the Journal of Discourses and TPJS.",
        "highlights": [
            "Complete Pearl of Great Price books: Moses, Abraham, JS—Matthew, JS—History, Articles of Faith",
            "Comprehensive BYU Onomasticon linguistic etymologies (◈) for proper names and astronomy terms",
            "620 historical sermon citation badges ([★]) with extended primary discourse excerpts",
            "Clean Kindle Paperwhite enhanced typesetting and reciprocal pop-up notes",
        ],
        "contents_summary": "Interactive Study Key, Moses, Abraham, Joseph Smith—Matthew, Joseph Smith—History, and Articles of Faith with Onomasticon and Citation apparati.",
    },
    {
        "id": "lds-standard-works-master-study",
        "title": "The Standard Works (Master Study Edition)",
        "subtitle": "Complete Five-Volume Canon with Parallel Bible Translations, BYU Onomasticon & 19th-Century Citations",
        "collection": "study-editions",
        "badge": "Grand Canon Master Study",
        "creator": "King James Translators, Ancient Prophets & Proteus Publishing Engine",
        "short_desc": "The complete 5-volume Standard Works (87 books, 1,582 chapters) uniting parallel Bible translations, BYU Onomasticon, and 19,300+ citation badges.",
        "full_desc": "The monumental combined Master Study Edition uniting all five volumes of the Latter-day Saint scriptural canon (Old Testament, New Testament, Book of Mormon, Doctrine and Covenants, Pearl of Great Price; 87 books, 1,582 chapters, 41,995 verses) into a single cohesive Kindle EPUB3 edition. Combines parallel translation comparison pop-ups ([⇄]) on biblical verses (BSB, ASV, BBE, and cross-references), BYU Onomasticon linguistic root etymologies (◈) across Restoration scriptures, and over 19,300 historical citation badges ([★ N]) linking verses to 19th-century sermons with extended primary source excerpts.",
        "highlights": [
            "All five Standard Works united in a single volume (87 books, 1,582 chapters, 1.17M words)",
            "Parallel translation pop-ups ([⇄]) for Berean Standard Bible, ASV (1901), and Basic English (BBE)",
            "Comprehensive BYU Onomasticon linguistic and etymological pop-up apparati (◈)",
            "Over 19,300 historical sermon citation badges ([★]) with extended primary discourse excerpts",
            "Canonical 2013 chapter headnotes and clean Kindle Paperwhite enhanced typesetting",
        ],
        "contents_summary": "Preface, Interactive Study Key, Old Testament (39 books), New Testament (27 books), Book of Mormon (15 books), Doctrine and Covenants, and Pearl of Great Price (5 books) with integrated study apparati.",
    },
    {
        "id": "book-of-mormon-historical-variants",
        "title": "The Book of Mormon (Historical Textual Variants)",
        "subtitle": "Word-Level Collation Across Eight Landmark Print Editions (1830–2013)",
        "collection": "study-editions",
        "badge": "Critical Apparatus",
        "creator": "Grant Hardy (Collation) & Proteus Publishing Engine",
        "short_desc": "Comprehensive critical collation comparing the Book of Mormon text across eight historic editions from 1830 to 2013.",
        "full_desc": "Built from Grant Hardy's BYU OpenScripture collation data, this critical edition tracks textual variations across the 1830, 1837, 1840, 1841, 1879, 1920, 1981, and 2013 printings. Tap any variant badge to view an instant Kindle pop-up apparatus detailing how the wording evolved across all eight editions.",
        "highlights": [
            "Collates 8 landmark print editions: 1830, 1837, 1840, 1841, 1879, 1920, 1981, and 2013",
            "3,581 inline critical apparatus pop-up notes",
            "Includes Title Page and Testimonies of the Three and Eight Witnesses",
            "Highlights verses where the 1840 Nauvoo edition uniquely diverges",
        ],
        "contents_summary": "Scholarly Methodology & Edition Key, Title Page, Testimonies of the Three and Eight Witnesses, and 1 Nephi through Moroni with embedded variant apparatus.",
    },
    {
        "id": "bom-intertextual-parallels",
        "title": "Book of Mormon Intertextual Parallels",
        "subtitle": "Word-Level Collation of Brass Plates Isaiah & 3 Nephi Against the King James Bible",
        "collection": "study-editions",
        "badge": "Intertextual Collation",
        "creator": "Proteus Intertextual Alignment Engine",
        "short_desc": "Word-level textual collation of Brass Plates Isaiah (2 Nephi 12–24) and the Sermon at the Temple (3 Nephi 12–14) against the KJV.",
        "full_desc": "A specialized critical edition exploring word-level textual parallels and divergences between the Book of Mormon and the King James Bible. Highlights unique insertions, omissions, and substitutions in the Brass Plates Isaiah chapters and the Sermon at the Temple, with instant Kindle pop-up notes showing the full KJV comparison.",
        "highlights": [
            "395 word-level diff pop-ups across 22 parallel chapters",
            "Compares 1 & 2 Nephi / Mosiah / Moroni against KJV Isaiah, Malachi & 1 Corinthians",
            "Compares 3 Nephi 12–14 against the Sermon on the Mount (Matthew 5–7)",
        ],
        "contents_summary": "Part I: Brass Plates Isaiah Collation; Part II: The Sermon at the Temple vs. Matthew 5–7; Part III: Malachi & Pauline Parallels.",
    },
    {
        "id": "top-1000-cited-verses",
        "title": "The Top 1,000 Cited Verses of the Restoration",
        "subtitle": "Ranked by 19th-Century Citation Frequency (1830–1886) with Public-Domain Sermon Profiles",
        "collection": "study-editions",
        "badge": "Historical Analytics",
        "creator": "Proteus Relational Scripture Engine & BYU Citation Index",
        "short_desc": "The 1,000 most-quoted scriptures in 19th-century Restoration sermons (JoD & TPJS, 1830–1886), with pop-up discourse excerpts.",
        "full_desc": "Ranks the top 1,000 most frequently cited scripture verses across 19th-century Latter-day Saint discourse (1830–1886), restricted strictly to pre-1942 public-domain sources: the 26-volume Journal of Discourses (1839–1886) and Teachings of the Prophet Joseph Smith (1830–1844). Tap any verse badge to view speaker frequencies and contextual sermon excerpts.",
        "highlights": [
            "Countdown of the Top 100 Overall + all 1,000 verses grouped by Standard Work",
            "1,100 interactive pop-up profiles with speaker counts and sermon excerpts",
            "100% public-domain 19th-century discourse corpus (1830–1886)",
        ],
        "contents_summary": "Part I: The Top 100 Most-Cited Verses (#1–#100); Parts II–VI: All 1,000 Ranked Verses Organized by Standard Work Volume.",
    },
    # --- Apocrypha & Ancient Texts ---
    {
        "id": "complete-apocrypha-pseudepigrapha-compendium",
        "title": "Complete Apocrypha & Pseudepigrapha Compendium",
        "subtitle": "Deuterocanon, Enochic Literature, Second Temple Texts & Provenance Dossiers",
        "collection": "apocrypha",
        "badge": "72 Ancient Works",
        "creator": "R. H. Charles, M. R. James, Richard Laurence, William Wake (Translators)",
        "short_desc": "72 deduplicated public-domain ancient works (1,376 chapters) with a Source, Provenance & Historical Veracity dossier for every book.",
        "full_desc": "A monumental extra-canonical compendium uniting 72 deduplicated public-domain works across the 1611 KJV Apocrypha, Enochic & Patriarchal Literature (1 Enoch, 2 Enoch, Jubilees, Jasher, Testaments of the Twelve Patriarchs), Old Testament Pseudepigrapha, New Testament Apocrypha, and the Apostolic Fathers. Every single book opens with a scholarly 'Source, Provenance & Historical Veracity' dossier.",
        "highlights": [
            "72 complete public-domain ancient books across 1,376 chapters",
            "1,169 interactive pop-up translator and manuscript footnotes",
            "Dedicated Source, Provenance & Historical Veracity dossier before every book",
            "Strict public-domain compliance (pre-1929 translations + Kraft 1987 PD release)",
        ],
        "contents_summary": "Division I: KJV Deuterocanon (15 books); Division II: Enochic & Patriarchal (18 books); Division III: OT Pseudepigrapha (16 books); Division IV: NT Apocrypha (12 books); Division V: Apostolic Fathers & Early Christian Texts (11 books).",
    },
    {
        "id": "kjv-apocrypha",
        "title": "The Complete KJV Apocrypha",
        "subtitle": "The Fifteen Deuterocanonical Books of the 1611 Authorized King James Bible",
        "collection": "apocrypha",
        "badge": "15 KJV Books",
        "creator": "1611 King James Translators",
        "short_desc": "All 15 Deuterocanonical books placed between the Old and New Testaments in the original 1611 King James Bible (including 1 & 2 Esdras).",
        "full_desc": "Contains all 15 books of the King James Apocrypha (1 Esdras, 2 Esdras, Tobit, Judith, Rest of Esther, Wisdom of Solomon, Ecclesiasticus / Sirach, Baruch with the Epistle of Jeremy, Song of the Three Holy Children, Susanna, Bel and the Dragon, Prayer of Manasses, and 1 & 2 Maccabees), introduced by Doctrine and Covenants Section 91.",
        "highlights": [
            "All 15 complete books (178 chapters) including 1 & 2 Esdras",
            "Prefaced with D&C Section 91 on reading the Apocrypha by the Spirit",
            "Clean chapter and verse formatting tuned for Kindle",
        ],
        "contents_summary": "D&C 91 Preface, 1 Esdras, 2 Esdras, Tobit, Judith, Rest of Esther, Wisdom, Ecclesiasticus, Baruch, Song of the Three Children, Susanna, Bel and the Dragon, Prayer of Manasses, 1 Maccabees, 2 Maccabees.",
    },
    {
        "id": "enoch-jubilees-jasher",
        "title": "The Books of Enoch, Jubilees & Jasher",
        "subtitle": "Patriarchal & Second Temple Apocrypha with R. H. Charles & Richard Laurence Translations",
        "collection": "apocrypha",
        "badge": "Patriarchal Omnibus",
        "creator": "R. H. Charles, Richard Laurence, Mordecai Manuel Noah (Translators)",
        "short_desc": "Both historic translations of 1 Enoch (Charles 1917 & Laurence 1883), the Book of Jubilees (with 1,148 pop-up notes), and the Book of Jasher.",
        "full_desc": "Unites the four foundational patriarchal extra-canonical volumes prized by students of the Book of Moses and ancient scripture: R. H. Charles's 1917 translation of 1 Enoch, Archbishop Richard Laurence's 1821/1883 translation of 1 Enoch, R. H. Charles's 1917 Book of Jubilees (complete with 1,148 interactive pop-up footnotes), and the 1840 English translation of Sefer haYashar (Book of Jasher).",
        "highlights": [
            "Includes both R. H. Charles (1917) and Richard Laurence (1883) translations of 1 Enoch",
            "1,169 interactive Kindle pop-up footnotes in Jubilees and Enoch",
            "Complete 91-chapter 1840 Book of Jasher",
        ],
        "contents_summary": "1. The Book of Enoch (R. H. Charles, 1917); 2. The Book of Enoch (Richard Laurence, 1883); 3. The Book of Jubilees (R. H. Charles, 1917); 4. The Book of Jasher (1840).",
    },
    # --- Restoration Literature ---
    {
        "id": "foundational-lds-classics-anthology",
        "title": "Foundational Classics of the Restoration",
        "subtitle": "Nine Landmark Doctrinal Works with 3,276 Interactive Pop-Up Footnotes",
        "collection": "literature",
        "badge": "9 Doctrinal Classics",
        "creator": "Joseph Smith Jr., James E. Talmage, Parley P. Pratt, Brigham Young, Joseph F. Smith",
        "short_desc": "Nine essential doctrinal books—including Lectures on Faith, Jesus the Christ, and Key to the Science of Theology—with 3,276 pop-up notes.",
        "full_desc": "A curated 9-volume doctrinal omnibus uniting the foundational classics of early Latter-day Saint theology: Lectures on Faith (1835), The Wentworth Letter (1842), Jesus the Christ (1915, chapters 1–42 in strict numerical order), The Articles of Faith (1899), The House of the Lord (1912), Key to the Science of Theology (1855), A Voice of Warning (1837), Discourses of Brigham Young (1925), and Gospel Doctrine (1919).",
        "highlights": [
            "9 complete foundational volumes (320 chapters, 1.24M words)",
            "3,276 recovered inline pop-up footnotes and endnotes",
            "Verified chapter sequence for Jesus the Christ (Chapters 1–42)",
        ],
        "contents_summary": "Lectures on Faith, Wentworth Letter, Jesus the Christ, Articles of Faith, House of the Lord, Key to the Science of Theology, Voice of Warning, Discourses of Brigham Young, Gospel Doctrine.",
    },
    {
        "id": "complete-lds-literature-compendium",
        "title": "The Complete Restoration Literature Compendium",
        "subtitle": "All 71 Public-Domain Historical Volumes of Early Latter-day Saint Theology & History",
        "collection": "literature",
        "badge": "71-Book Compendium",
        "creator": "Joseph Smith Jr., B. H. Roberts, James E. Talmage, Parley P. Pratt, Orson Pratt, et al.",
        "short_desc": "All 71 public-domain historical Restoration books (5.91M words, 1,982 chapters) organized into seven thematic divisions.",
        "full_desc": "An unprecedented single-volume library containing all 71 public-domain works of 19th and early-20th-century Restoration history, theology, biography, and discourse. Organized into 7 thematic divisions with a master linked Table of Contents and 3,276 interactive pop-up footnotes.",
        "highlights": [
            "All 71 historical books across 1,982 chapters (5.91M words)",
            "Organized into 7 thematic divisions with clickable overview directory",
            "3,276 interactive Kindle pop-up footnotes",
        ],
        "contents_summary": "Divisions I–VII: Foundational Theology, Doctrinal Treatises, Church History, Biographies, Sermons & Discourses, Defense & Apologetics, and the Faith-Promoting Series.",
    },
    # --- Reading Guides ---
    {
        "id": "early-modern-english-scripture-guide",
        "title": "Early Modern English Guide to the Scriptures",
        "subtitle": "Comprehensive Grammar, Pronouns, Verb Inflections, Hebraisms & 100-Word Lexicon",
        "collection": "reading-guides",
        "badge": "Comprehensive Guide",
        "creator": "Proteus Philological Series",
        "short_desc": "In-depth philological companion to the grammar, syntax, Hebraisms, and lexicon of the King James Bible and Book of Mormon.",
        "full_desc": "A comprehensive 9-chapter philological reference exploring the Early Modern English of the 1611/1769 King James Bible and the 1830/2013 Book of Mormon. Covers the pronoun system, verb morphology, subjunctive and imperative moods, syntactic inversion, Hebraisms (parataxis, cognates, 'and it came to pass'), a 100+ entry lexicon, and annotated side-by-side walkthroughs.",
        "highlights": [
            "9 comprehensive chapters with grammatical tables and scripture examples",
            "25 interactive pop-up philological notes",
            "Side-by-side annotated walkthroughs of complex KJV and Book of Mormon passages",
        ],
        "contents_summary": "Chapters 1–9: Historical Background, Pronoun System, Verb Morphology, Mood & Tense, Syntax, Hebraisms, 100-Word Lexicon, Annotated Passages, and Quick Reference.",
    },
]


def human_size(n: int) -> str:
    return f"{n / 1_048_576:.2f} MB" if n >= 1_048_576 else f"{max(1, round(n / 1024))} KB"


def main() -> None:
    (SITE / "downloads").mkdir(parents=True, exist_ok=True)
    (SITE / "covers").mkdir(parents=True, exist_ok=True)
    (SITE / ".nojekyll").write_text("", encoding="utf-8")

    # Remove any obsolete downloads or covers not in active catalog
    valid_ids = {spec["id"] for spec in EDITION_CATALOG_SPECS}
    for file in (SITE / "downloads").glob("*.epub"):
        if file.stem not in valid_ids:
            file.unlink()
    for file in (SITE / "covers").glob("*.png"):
        if file.stem not in valid_ids:
            file.unlink()

    catalog: list[dict] = []
    for spec in EDITION_CATALOG_SPECS:
        stem = spec["id"]
        src_epub = DIST_EPUBS / f"{stem}.epub"
        if not src_epub.exists():
            print(f"skip (not built): {stem}")
            continue

        shutil.copy2(src_epub, SITE / "downloads" / src_epub.name)
        src_cover = DIST_COVERS / f"{stem}.png"
        if src_cover.exists():
            from PIL import Image
            with Image.open(src_cover) as im:
                web_im = im.resize((600, 960), resample=Image.Resampling.LANCZOS).quantize(
                    colors=256, method=Image.Quantize.FASTOCTREE
                )
                web_im.save(SITE / "covers" / src_cover.name, format="PNG", optimize=True)

        size_bytes = src_epub.stat().st_size
        col_id = spec["collection"]
        download_url = f"https://raw.githubusercontent.com/michaelrussell4/proteus/main/site/downloads/{stem}.epub"
        entry = {
            "id": stem,
            "slug": stem,
            "title": spec["title"],
            "subtitle": spec["subtitle"],
            "collection": col_id,
            "collection_label": COLLECTION_LABELS.get(col_id, col_id),
            "badge": spec["badge"],
            "file": download_url,
            "cover": f"covers/{stem}.png",
            "size_bytes": size_bytes,
            "size_human": human_size(size_bytes),
            "creator": spec["creator"],
            "short_desc": spec["short_desc"],
            "full_desc": spec["full_desc"],
            "highlights": spec["highlights"],
            "contents_summary": spec["contents_summary"],
        }
        catalog.append(entry)

    categories = [
        {
            "id": cid,
            "label": clabel,
            "count": len(catalog) if cid == "all" else sum(1 for b in catalog if b["collection"] == cid),
        }
        for cid, clabel in COLLECTIONS
    ]

    total_mb = sum(b["size_bytes"] for b in catalog) / (1024 * 1024)

    cards_html = []
    for book in catalog:
        search_terms = (
            f"{book['title']} {book['subtitle']} {book['short_desc']} "
            f"{book['collection_label']} {book['badge']} {' '.join(book.get('highlights', []))}"
        ).lower()
        search_terms_escaped = html.escape(search_terms, quote=True)
        title_esc = html.escape(book["title"])
        subtitle_esc = html.escape(book["subtitle"])
        short_desc_esc = html.escape(book["short_desc"])
        badge_esc = html.escape(book["badge"])
        col_esc = html.escape(book["collection"])
        col_label_esc = html.escape(book["collection_label"])
        size_human = html.escape(book["size_human"])
        cover_path = html.escape(book["cover"])
        file_path = html.escape(book["file"])
        book_id = html.escape(book["id"])

        cards_html.append(f"""
        <article class="book-card" data-id="{book_id}" data-collection="{col_esc}" data-search="{search_terms_escaped}">
          <div class="book-cover-wrap">
            <img class="book-cover" src="{cover_path}" alt="Cover art for {title_esc}" width="240" height="384" loading="lazy">
            <span class="book-badge">{badge_esc}</span>
          </div>
          <div class="book-content">
            <div class="book-meta-top">
              <span class="book-collection-tag">{col_label_esc}</span>
              <span class="book-size-tag"><svg class="icon-inline" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 2a.75.75 0 01.75.75v8.69l2.72-2.72a.75.75 0 111.06 1.06l-4 4a.75.75 0 01-1.06 0l-4-4a.75.75 0 011.06-1.06l2.72 2.72V2.75A.75.75 0 0110 2zM3 13.75A.75.75 0 013.75 13h12.5a.75.75 0 010 1.5H3.75A.75.75 0 013 13.75z" clip-rule="evenodd"/></svg>{size_human}</span>
            </div>
            <h3 class="book-title"><a href="{file_path}" download>{title_esc}</a></h3>
            <p class="book-subtitle">{subtitle_esc}</p>
            <p class="book-description">{short_desc_esc}</p>
            <div class="book-actions">
              <a class="btn btn-primary" href="{file_path}" download title="Download {title_esc}">
                <svg class="icon" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 2a.75.75 0 01.75.75v8.69l2.72-2.72a.75.75 0 111.06 1.06l-4 4a.75.75 0 01-1.06 0l-4-4a.75.75 0 011.06-1.06l2.72 2.72V2.75A.75.75 0 0110 2zM3 13.75A.75.75 0 013.75 13h12.5a.75.75 0 010 1.5H3.75A.75.75 0 013 13.75z" clip-rule="evenodd"/></svg>
                <span>Download EPUB</span>
              </a>
              <button type="button" class="btn btn-secondary btn-details" data-open-modal="{book_id}" aria-label="View details for {title_esc}">
                <span>Details</span>
              </button>
            </div>
          </div>
        </article>
        """)

    filter_chips_html = []
    for c in categories:
        pressed = "true" if c["id"] == "all" else "false"
        filter_chips_html.append(
            f'<button class="chip" data-filter="{c["id"]}" aria-pressed="{pressed}">'
            f'{c["label"]} <span class="chip-count">({c["count"]})</span></button>'
        )

    html_content = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Proteus Scriptorium · Curated Scripture &amp; Study EPUB Editions</title>
  <meta name="description" content="Download handcrafted, Kindle Paperwhite-optimized EPUB3 editions of Latter-day Saint scripture, critical study collations, biblical apocrypha, and Restoration classics.">
  <meta name="theme-color" content="#1c1917">
  
  <!-- Open Graph / Social Sharing -->
  <meta property="og:type" content="website">
  <meta property="og:title" content="Proteus Scriptorium · Curated Scripture &amp; Study EPUBs">
  <meta property="og:description" content="Free, non-commercial digital library of computational scripture, textual collations, and public-domain Restoration classics. Optimized for Kindle Paperwhite &amp; modern e-readers.">
  <meta property="og:image" content="covers/book-of-mormon-master-study.png">

  <link rel="stylesheet" href="style.css">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📜</text></svg>">
</head>
<body>
  <!-- Header / Nav -->
  <nav class="top-nav">
    <div class="wrap top-nav-inner">
      <a class="nav-brand" href="#top">
        <span class="brand-crest">✦</span>
        <span class="brand-name">Proteus <span>Scriptorium</span></span>
      </a>
      <div class="nav-links">
        <a href="#editions">Editions</a>
        <a href="#how-to-read">E-Reader Guide</a>
        <a href="#about">About</a>
        <a href="#attribution">Attribution</a>
        <button id="theme-toggle" class="btn-theme-toggle" type="button" aria-label="Toggle light or dark theme" title="Toggle theme">
          <span class="theme-icon-light" aria-hidden="true">☀️</span>
          <span class="theme-icon-dark" aria-hidden="true">🌙</span>
        </button>
      </div>
    </div>
  </nav>

  <!-- Hero Section -->
  <header id="top" class="hero">
    <div class="wrap hero-inner">
      <div class="hero-content">
        <div class="hero-pill">
          <span class="pill-dot"></span>
          <span>Free &amp; Non-Commercial Digital Library</span>
        </div>
        <h1 class="hero-title">Scripture &amp; Classics,<br>Engineered for Your E-Reader</h1>
        <p class="hero-lede">
          Curated, fine-press EPUB3 editions of the Latter-day Saint scriptural canon, intertextual collations, extra-canonical apocrypha, and 19th-century classics.
          Every volume is hand-crafted and validated with zero errors for <strong>Amazon Kindle Paperwhite</strong> and modern reading devices.
        </p>

        <div class="hero-stats">
          <div class="stat-item">
            <span class="stat-number">{len(catalog)}</span>
            <span class="stat-label">Curated Volumes</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-number">{total_mb:.1f} MB</span>
            <span class="stat-label">Total Library Size</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-number">100%</span>
            <span class="stat-label">Public Domain &amp; Free</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-number">EPUB3</span>
            <span class="stat-label">Kindle Pop-Up Notes</span>
          </div>
        </div>

        <div class="hero-cta-row">
          <a class="btn btn-primary btn-hero" href="#editions">Browse Editions ↓</a>
          <button type="button" id="btn-download-all-hero" class="btn btn-secondary btn-hero" data-download-all="all">
            <svg class="icon" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 2a.75.75 0 01.75.75v8.69l2.72-2.72a.75.75 0 111.06 1.06l-4 4a.75.75 0 01-1.06 0l-4-4a.75.75 0 011.06-1.06l2.72 2.72V2.75A.75.75 0 0110 2zM3 13.75A.75.75 0 013.75 13h12.5a.75.75 0 010 1.5H3.75A.75.75 0 013 13.75z" clip-rule="evenodd"/></svg>
            <span class="btn-download-all-label">Download All ({len(catalog)} EPUBs · {total_mb:.0f} MB)</span>
          </button>
          <a class="btn btn-outline btn-hero" href="#how-to-read">Send-to-Kindle Guide</a>
        </div>
      </div>
    </div>
  </header>

  <!-- Main Catalog Controls -->
  <section id="editions" class="catalog-section">
    <div class="controls-bar">
      <div class="wrap controls-inner">
        <div class="search-box">
          <svg class="search-icon" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clip-rule="evenodd"/>
          </svg>
          <input type="search" id="catalog-search" class="search-input" placeholder="Search by title, series, topic, author, or keyword…" aria-label="Search editions" autocomplete="off">
          <button type="button" id="search-clear" class="search-clear" aria-label="Clear search" hidden>×</button>
        </div>

        <div class="filter-chips" role="group" aria-label="Filter by collection">
          {"".join(filter_chips_html)}
        </div>

        <div class="catalog-summary-bar">
          <span id="results-count">Showing <strong>{len(catalog)}</strong> editions</span>
          <div class="catalog-summary-actions">
            <button type="button" id="btn-download-visible" class="btn btn-secondary btn-sm" data-download-all="visible">
              <svg class="icon" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 2a.75.75 0 01.75.75v8.69l2.72-2.72a.75.75 0 111.06 1.06l-4 4a.75.75 0 01-1.06 0l-4-4a.75.75 0 011.06-1.06l2.72 2.72V2.75A.75.75 0 0110 2zM3 13.75A.75.75 0 013.75 13h12.5a.75.75 0 010 1.5H3.75A.75.75 0 013 13.75z" clip-rule="evenodd"/></svg>
              <span id="btn-download-visible-label">Download All ({len(catalog)} EPUBs)</span>
            </button>
            <div class="sort-wrapper">
              <label for="catalog-sort">Sort by:</label>
              <select id="catalog-sort" class="sort-select">
                <option value="featured">Featured Selections</option>
                <option value="title">Title (A–Z)</option>
                <option value="size-desc">File Size (Largest first)</option>
                <option value="size-asc">File Size (Smallest first)</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Editions Grid -->
    <div class="wrap">
      <div id="books-grid" class="books-grid">
        {"".join(cards_html)}
      </div>

      <div id="empty-state" class="empty-state" hidden>
        <div class="empty-icon">🔍</div>
        <h3>No matching editions found</h3>
        <p>Try searching with another keyword or resetting the category filter.</p>
        <button type="button" id="reset-filters" class="btn btn-secondary">Reset Filters</button>
      </div>
    </div>
  </section>

  <!-- How to Read / Send to Kindle Guide -->
  <section id="how-to-read" class="guide-section">
    <div class="wrap">
      <div class="section-header">
        <span class="section-eyebrow">Device Compatibility</span>
        <h2 class="section-title">How to Read on Your Device</h2>
        <p class="section-lede">All editions are packaged according to official W3C EPUB 3.3 standards with bidirectional pop-up footnote markup and high-resolution covers.</p>
      </div>

      <div class="guide-grid">
        <div class="guide-card">
          <div class="guide-icon">📱</div>
          <h3>Amazon Kindle (Paperwhite, Oasis, Scribe, App)</h3>
          <p>The fastest way to load onto your Kindle is via Amazon's official web tool:</p>
          <ol>
            <li>Download the desired <code>.epub</code> from this page.</li>
            <li>Go to <a href="https://www.amazon.com/sendtokindle" target="_blank" rel="noopener">amazon.com/sendtokindle</a> and sign in.</li>
            <li>Drag &amp; drop the <code>.epub</code> file. In 1–2 minutes, it will automatically sync to your Kindle library with covers and native pop-up notes!</li>
          </ol>
          <div class="guide-tip">
            <strong>Pro-tip:</strong> You can also send the file as an email attachment directly to your <code>@kindle.com</code> email address.
          </div>
        </div>

        <div class="guide-card">
          <div class="guide-icon">🍎</div>
          <h3>Apple Books (iPhone, iPad, Mac)</h3>
          <p>Seamless one-tap integration with iOS and macOS devices:</p>
          <ol>
            <li>Click <strong>Download EPUB</strong> on your iPhone, iPad, or Mac.</li>
            <li>When prompted, tap <em>Open in Books</em>.</li>
            <li>The book is automatically added to your library and syncs across all your Apple devices via iCloud with progress and bookmark saving.</li>
          </ol>
        </div>

        <div class="guide-card">
          <div class="guide-icon">📖</div>
          <h3>Kobo, Android &amp; Third-Party Readers</h3>
          <p>Compatible with all modern e-ink readers and mobile apps:</p>
          <ol>
            <li><strong>Kobo:</strong> Connect via USB and drag into the Kobo drive, or download directly via the browser.</li>
            <li><strong>Android:</strong> Open directly in apps like <em>Google Play Books</em>, <em>ReadEra</em>, <em>Moon+ Reader</em>, or <em>PocketBook</em>.</li>
          </ol>
        </div>

        <div class="guide-card">
          <div class="guide-icon">💻</div>
          <h3>PC &amp; Mac Desktop Reading</h3>
          <p>For research and reference on desktop computers:</p>
          <ol>
            <li><strong>Thorium Reader</strong> (Recommended, free &amp; open-source): Built specifically for accessibility and pure EPUB3 conformance.</li>
            <li><strong>Calibre</strong>: Great for managing large digital libraries and inspecting chapters.</li>
          </ol>
        </div>
      </div>
    </div>
  </section>

  <!-- Technical Standards / About Proteus -->
  <section id="about" class="about-section">
    <div class="wrap">
      <div class="section-header">
        <span class="section-eyebrow">Publishing Technology</span>
        <h2 class="section-title">The Proteus Publishing Standard</h2>
        <p class="section-lede">What makes these editions fundamentally different from raw scans or automated web exports?</p>
      </div>

      <div class="features-grid">
        <div class="feature-item">
          <div class="feature-icon">✨</div>
          <h4>Kindle Paperwhite Pop-Up Footnotes</h4>
          <p>Every scripture cross-reference, textual variant, and Hebrew/Semitic etymology uses reciprocal <code>&lt;a epub:type="noteref"&gt;</code> and <code>&lt;aside epub:type="footnote"&gt;</code> pairs. Tap any note to see an instant modal card on your Kindle without losing your reading location.</p>
        </div>

        <div class="feature-item">
          <div class="feature-icon">🎨</div>
          <h4>Proteus Scriptorium Cover Suite</h4>
          <p>Each volume carries a bespoke high-DPI (1200×1920) cover rendered with supersampled Lanczos filtering, classical Constantia tracked typography, large centerpiece medallion illustrations, and standardized series headers.</p>
        </div>

        <div class="feature-item">
          <div class="feature-icon">🛡️</div>
          <h4>W3C epubcheck 5.3.0 Verified</h4>
          <p>Every compiled volume passes the official W3C / IDPF Java EPUBCheck validation suite with zero errors and zero warnings. Valid XHTML5, verified internal links, and strict XML well-formedness.</p>
        </div>

        <div class="feature-item">
          <div class="feature-icon">🔤</div>
          <h4>Smart Typography &amp; Grammar Engine</h4>
          <p>Clean typographic normalizations: curly quotation marks, proper em-dashes with grammatical mid-sentence capitalization, non-breaking spaces before verse locators, and dark-mode resilient styling.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Attribution & Public Domain -->
  <section id="attribution" class="attribution-section">
    <div class="wrap">
      <div class="section-header">
        <span class="section-eyebrow">Academic Heritage &amp; Notice</span>
        <h2 class="section-title">Sources, Attribution &amp; Non-Commercial Notice</h2>
      </div>

      <div class="attribution-card">
        <ul class="attribution-list">
          <li>
            <strong>Non-Profit &amp; Educational Mission:</strong> All Proteus editions hosted here are distributed strictly free of charge for personal, non-commercial, and educational study.
          </li>
          <li>
            <strong>Public-Domain Textual Foundations:</strong> Canonical texts (1769 King James Bible, 1830–1920 Book of Mormon, pre-1929 Doctrine &amp; Covenants and Pearl of Great Price), historical Restoration volumes (1833–1927, via Project Gutenberg and the Mormon Documentation Project), and the Apocrypha &amp; Pseudepigrapha corpora (R. H. Charles, M. R. James, Richard Laurence, Ante-Nicene Fathers, William Wake, and Robert A. Kraft's 1987 public-domain 4 Baruch) are derived from public-domain sources.
          </li>
          <li>
            <strong>Academic Project Attribution:</strong> We express deep gratitude to the <a href="https://onoma.lib.byu.edu/" target="_blank" rel="noopener">BYU Book of Mormon Onomasticon Project</a> (ed. Paul Y. Hoskisson), the <a href="https://scriptures.byu.edu/" target="_blank" rel="noopener">BYU Scripture Citation Index</a> (Stephen W. Liddle &amp; Richard C. Galbraith; restricted to pre-1942 public-domain discourses), Grant Hardy's OpenScripture 1830–2013 collation, and the Internet Sacred Text Archive.
          </li>
          <li>
            <strong>Independent Status:</strong> Proteus is an independent, non-commercial educational project. It is not affiliated with, endorsed by, or sponsored by The Church of Jesus Christ of Latter-day Saints or Brigham Young University.
          </li>
        </ul>
      </div>
    </div>
  </section>

  <!-- Footer -->
  <footer class="site-footer">
    <div class="wrap footer-inner">
      <div class="footer-left">
        <p class="footer-brand">✦ Proteus Scriptorium</p>
        <p class="footer-tagline">Crafted for serious scripture study and distraction-free digital reading.</p>
      </div>
      <div class="footer-right">
        <p>100% Free &amp; Open Source · Hosted on GitHub Pages</p>
        <p><a href="https://github.com/michaelrussell4/proteus" target="_blank" rel="noopener">View GitHub Repository</a> · <a href="#top">Back to Top ↑</a></p>
      </div>
    </div>
  </footer>

  <!-- Book Details Modal (Native HTML <dialog>) -->
  <dialog id="book-modal" class="book-modal" aria-labelledby="modal-book-title" closedby="any">
    <div class="modal-card">
      <header class="modal-header">
        <span id="modal-book-badge" class="book-badge"></span>
        <button type="button" class="modal-close-btn" id="modal-close" aria-label="Close dialog">×</button>
      </header>
      
      <div class="modal-body">
        <div class="modal-cover-column">
          <img id="modal-book-cover" class="modal-cover" src="" alt="Book cover">
          <a id="modal-download-btn" class="btn btn-primary btn-full-width" href="" download>
            <svg class="icon" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 2a.75.75 0 01.75.75v8.69l2.72-2.72a.75.75 0 111.06 1.06l-4 4a.75.75 0 01-1.06 0l-4-4a.75.75 0 011.06-1.06l2.72 2.72V2.75A.75.75 0 0110 2zM3 13.75A.75.75 0 013.75 13h12.5a.75.75 0 010 1.5H3.75A.75.75 0 013 13.75z" clip-rule="evenodd"/></svg>
            <span id="modal-download-text">Download EPUB</span>
          </a>
          <span id="modal-book-size" class="modal-file-size"></span>
        </div>

        <div class="modal-info-column">
          <div class="modal-meta-row">
            <span id="modal-book-collection" class="book-collection-tag"></span>
            <span id="modal-book-creator" class="modal-creator-tag"></span>
          </div>

          <h2 id="modal-book-title" class="modal-title"></h2>
          <p id="modal-book-subtitle" class="modal-subtitle"></p>

          <div class="modal-section">
            <h4 class="modal-section-title">Overview</h4>
            <p id="modal-book-desc" class="modal-desc"></p>
          </div>

          <div class="modal-section">
            <h4 class="modal-section-title">Key Highlights</h4>
            <ul id="modal-book-highlights" class="modal-highlights-list"></ul>
          </div>

          <div class="modal-section">
            <h4 class="modal-section-title">Contents &amp; Scope</h4>
            <p id="modal-book-contents" class="modal-contents-desc"></p>
          </div>
        </div>
      </div>
    </div>
  </dialog>

  <!-- Embed catalog JSON for instantaneous client-side access -->
  <script type="application/json" id="catalog-data">
{json.dumps(catalog, indent=2)}
  </script>

  <script src="app.js" type="module"></script>
</body>
</html>
"""
    (SITE / "index.html").write_text(html_content, encoding="utf-8")
    (SITE / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Built site with {len(catalog)} editions ({total_mb:.1f} MB) -> {SITE}")


if __name__ == "__main__":
    main()
