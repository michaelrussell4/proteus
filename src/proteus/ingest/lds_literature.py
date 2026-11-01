"""Hybrid Ingester for Historical Latter-day Saint Literature (`non-canon-lds-literature`).

Combines:
1. Clean chapter structure and metadata from `data/raw/non-canon-lds-literature/clean/*.jsonl`
2. Exact inline footnote callouts (`<sup>[1]</sup>`) and footnote definitions recovered directly
   from the original EPUB archives in `data/raw/non-canon-lds-literature/epub/*.epub` so that
   footnotes render as native Kindle modal pop-ups (`epub:type="noteref"` / `<aside epub:type="footnote">`).
3. Strict sequential chapter ordering, split-TOC deduplication, and sub-section consolidation
   so that every book's Table of Contents is 100% faithful to the original volume.
"""

from __future__ import annotations

import json
import re
import warnings
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from proteus.core.models import (
    Annotation,
    AnnotationType,
    BlockType,
    Book,
    Chapter,
    ContentBlock,
    Work,
)
from proteus.core.references import slugify
from proteus.core.typography import clean_prose_text, escape_xhtml

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

FOUNDATIONAL_LDS_CLASSICS: list[tuple[str, str, str]] = [
    ("the_lectures_on_faith", "The Lectures on Faith", "Joseph Smith Jr."),
    ("the_wentworth_letter", "The Wentworth Letter (1842)", "Joseph Smith Jr."),
    ("jesus_the_christ", "Jesus the Christ", "James E. Talmage"),
    ("articles_of_faith", "The Articles of Faith", "James E. Talmage"),
    ("the_house_of_the_lord", "The House of the Lord", "James E. Talmage"),
    ("key_to_the_science_of_theology", "Key to the Science of Theology", "Parley P. Pratt"),
    ("a_voice_of_warning", "A Voice of Warning", "Parley P. Pratt"),
    ("discourses_of_brigham_young", "Discourses of Brigham Young", "Brigham Young (comp. John A. Widtsoe)"),
    ("gospel_doctrine", "Gospel Doctrine", "Joseph F. Smith"),
]

# Complete 71-book thematic organization for The Complete Restoration Literature Compendium
COMPLETE_LDS_LITERATURE_CATALOGUE: list[tuple[str, str, str, str]] = [
    # Division I: Prophetic & Doctrinal Foundations
    ("the_lectures_on_faith", "The Lectures on Faith (1835)", "Joseph Smith Jr.", "I. Prophetic & Doctrinal Foundations"),
    ("the_wentworth_letter", "The Wentworth Letter (1842)", "Joseph Smith Jr.", "I. Prophetic & Doctrinal Foundations"),
    ("general_smiths_views_of_the_powers_and_policy_of_the_government_of_the_united_states", "Views of the Powers and Policy of the Government of the United States (1844)", "Joseph Smith Jr.", "I. Prophetic & Doctrinal Foundations"),
    ("jesus_the_christ", "Jesus the Christ (1915)", "James E. Talmage", "I. Prophetic & Doctrinal Foundations"),
    ("articles_of_faith", "The Articles of Faith (1899)", "James E. Talmage", "I. Prophetic & Doctrinal Foundations"),
    ("the_house_of_the_lord", "The House of the Lord (1912)", "James E. Talmage", "I. Prophetic & Doctrinal Foundations"),
    ("the_story_of_mormonism_and_the_philosophy_of_mormonism", "The Story and Philosophy of “Mormonism”", "James E. Talmage", "I. Prophetic & Doctrinal Foundations"),
    ("key_to_the_science_of_theology", "Key to the Science of Theology (1855)", "Parley P. Pratt", "I. Prophetic & Doctrinal Foundations"),
    ("a_voice_of_warning", "A Voice of Warning (1837)", "Parley P. Pratt", "I. Prophetic & Doctrinal Foundations"),
    ("the_government_of_god", "The Government of God (1852)", "John Taylor", "I. Prophetic & Doctrinal Foundations"),
    ("items_on_the_priesthood", "Items on the Priesthood", "John Taylor", "I. Prophetic & Doctrinal Foundations"),

    # Division II: Presidential & Apostolic Discourses
    ("discourses_of_brigham_young", "Discourses of Brigham Young", "Brigham Young (comp. John A. Widtsoe)", "II. Presidential & Apostolic Discourses"),
    ("gospel_doctrine", "Gospel Doctrine (1919)", "Joseph F. Smith", "II. Presidential & Apostolic Discourses"),
    ("gospel_themes", "Gospel Themes", "Orson F. Whitney", "II. Presidential & Apostolic Discourses"),
    ("the_strength_of_the_mormon_position", "The Strength of the “Mormon” Position", "Orson F. Whitney", "II. Presidential & Apostolic Discourses"),
    ("salvation_universal", "Salvation Universal", "Joseph Fielding Smith", "II. Presidential & Apostolic Discourses"),
    ("blood_atonement_and_the_origin_of_plural_marriage", "Blood Atonement and the Origin of Plural Marriage", "Joseph Fielding Smith & Richard C. Evans", "II. Presidential & Apostolic Discourses"),

    # Division III: Theological & Apologetic Treatises (B. H. Roberts & Orson Pratt)
    ("a_new_witness_for_god_volume_1", "A New Witness for God, Volume I", "B. H. Roberts", "III. Theological & Apologetic Treatises"),
    ("a_new_witness_for_god_volume_2", "New Witnesses for God, Volume II: The Book of Mormon", "B. H. Roberts", "III. Theological & Apologetic Treatises"),
    ("a_new_witness_for_god_volume_3", "New Witnesses for God, Volume III: Evidences of the Book of Mormon", "B. H. Roberts", "III. Theological & Apologetic Treatises"),
    ("defense_of_the_faith_and_the_saints_volume_1", "Defense of the Faith and the Saints, Volume I", "B. H. Roberts", "III. Theological & Apologetic Treatises"),
    ("defense_of_the_faith_and_the_saints_volume_2", "Defense of the Faith and the Saints, Volume II", "B. H. Roberts", "III. Theological & Apologetic Treatises"),
    ("the_gospel", "The Gospel: An Exposition of Its First Principles", "B. H. Roberts", "III. Theological & Apologetic Treatises"),
    ("the_mormon_doctrine_of_deity", "The Mormon Doctrine of Deity", "B. H. Roberts", "III. Theological & Apologetic Treatises"),
    ("the_seventys_course_in_theology", "The Seventy’s Course in Theology, First Year", "B. H. Roberts", "III. Theological & Apologetic Treatises"),
    ("an_interesting_account_of_several_remarkable_visions", "An Interesting Account of Several Remarkable Visions (1840)", "Orson Pratt", "III. Theological & Apologetic Treatises"),
    ("divine_authority", "Divine Authority; Or, Was Joseph Smith Sent of God?", "Orson Pratt", "III. Theological & Apologetic Treatises"),
    ("the_kingdom_of_god_part_1", "The Kingdom of God, Part I", "Orson Pratt", "III. Theological & Apologetic Treatises"),
    ("absurdities_of_immaterialism", "Absurdities of Immaterialism", "Orson Pratt", "III. Theological & Apologetic Treatises"),
    ("the_bible_and_polygamy", "The Bible and Polygamy", "Orson Pratt & J. P. Newman", "III. Theological & Apologetic Treatises"),
    ("the_myth_of_the_manuscript_found", "The Myth of the “Manuscript Found” (Spaulding Story)", "George Reynolds", "III. Theological & Apologetic Treatises"),

    # Division IV: Documentary History of the Church (Vols. 1–6) & Comprehensive Histories
    ("history_of_the_church_of_jesus_christ_of_latter_day_saints_volume_1", "History of the Church, Volume I (1805–1834)", "Joseph Smith Jr. (ed. B. H. Roberts)", "IV. Comprehensive & Documentary Church History"),
    ("history_of_the_church_of_jesus_christ_of_latter_day_saints_volume_2", "History of the Church, Volume II (1834–1837)", "Joseph Smith Jr. (ed. B. H. Roberts)", "IV. Comprehensive & Documentary Church History"),
    ("history_of_the_church_of_jesus_christ_of_latter_day_saints_volume_3", "History of the Church, Volume III (1838–1839)", "Joseph Smith Jr. (ed. B. H. Roberts)", "IV. Comprehensive & Documentary Church History"),
    ("history_of_the_church_of_jesus_christ_of_latter_day_saints_volume_4", "History of the Church, Volume IV (1839–1842)", "Joseph Smith Jr. (ed. B. H. Roberts)", "IV. Comprehensive & Documentary Church History"),
    ("history_of_the_church_of_jesus_christ_of_latter_day_saints_volume_5", "History of the Church, Volume V (1842–1843)", "Joseph Smith Jr. (ed. B. H. Roberts)", "IV. Comprehensive & Documentary Church History"),
    ("history_of_the_church_of_jesus_christ_of_latter_day_saints_volume_6", "History of the Church, Volume VI (1843–1844)", "Joseph Smith Jr. (ed. B. H. Roberts)", "IV. Comprehensive & Documentary Church History"),
    ("essentials_in_church_history", "Essentials in Church History", "Joseph Fielding Smith", "IV. Comprehensive & Documentary Church History"),
    ("the_missouri_persecutions", "The Missouri Persecutions", "B. H. Roberts", "IV. Comprehensive & Documentary Church History"),
    ("a_young_folks_history_of_the_church", "A Young Folks’ History of the Church", "Nephi Anderson", "IV. Comprehensive & Documentary Church History"),

    # Division V: Prophetic Biographies, Pioneer Journals & Frontier Memoirs
    ("history_of_the_prophet_joseph_by_his_mother", "History of the Prophet Joseph, by His Mother", "Lucy Mack Smith", "V. Biographies, Journals & Pioneer Memoirs"),
    ("the_autobiography_of_parley_parker_pratt", "The Autobiography of Parley Parker Pratt", "Parley P. Pratt", "V. Biographies, Journals & Pioneer Memoirs"),
    ("the_life_of_john_taylor", "The Life of John Taylor", "B. H. Roberts", "V. Biographies, Journals & Pioneer Memoirs"),
    ("life_of_heber_c_kimball", "Life of Heber C. Kimball, an Apostle", "Orson F. Whitney", "V. Biographies, Journals & Pioneer Memoirs"),
    ("president_heber_c_kimballs_journal", "President Heber C. Kimball’s Journal", "Heber C. Kimball", "V. Biographies, Journals & Pioneer Memoirs"),
    ("leaves_from_my_journal", "Leaves from My Journal", "Wilford Woodruff", "V. Biographies, Journals & Pioneer Memoirs"),
    ("william_claytons_journal", "William Clayton’s Journal (Pioneer Trek of 1846–1847)", "William Clayton", "V. Biographies, Journals & Pioneer Memoirs"),
    ("my_first_mission", "My First Mission", "George Q. Cannon", "V. Biographies, Journals & Pioneer Memoirs"),
    ("jacob_hamblin", "Jacob Hamblin: Frontiersman, Missionary to the Indians & Explorer", "Jacob Hamblin & James A. Little", "V. Biographies, Journals & Pioneer Memoirs"),
    ("forty_years_among_the_indians", "Forty Years Among the Indians", "Daniel W. Jones", "V. Biographies, Journals & Pioneer Memoirs"),
    ("life_of_a_pioneer", "Life of a Pioneer: Autobiography of James S. Brown", "James S. Brown", "V. Biographies, Journals & Pioneer Memoirs"),
    ("memoirs_of_john_r_young", "Memoirs of John R. Young, Utah Pioneer of 1847", "John R. Young", "V. Biographies, Journals & Pioneer Memoirs"),
    ("lydia_knights_history", "Lydia Knight’s History", "Susa Young Gates", "V. Biographies, Journals & Pioneer Memoirs"),

    # Division VI: The Faith-Promoting Series & Pioneer Testimony Anthologies
    ("a_string_of_pearls", "A String of Pearls (Faith-Promoting Series, Book 2)", "Various Pioneer Authors", "VI. Faith-Promoting Series & Testimony Anthologies"),
    ("fragments_of_experience", "Fragments of Experience (Faith-Promoting Series, Book 6)", "Various Pioneer Authors", "VI. Faith-Promoting Series & Testimony Anthologies"),
    ("early_scenes_in_church_history", "Early Scenes in Church History (Faith-Promoting Series, Book 8)", "Various Pioneer Authors", "VI. Faith-Promoting Series & Testimony Anthologies"),
    ("gems_for_the_young_folks", "Gems for the Young Folks (Faith-Promoting Series, Book 4)", "Various Pioneer Authors", "VI. Faith-Promoting Series & Testimony Anthologies"),
    ("scraps_of_biography", "Scraps of Biography (Faith-Promoting Series, Book 10)", "Various Pioneer Authors", "VI. Faith-Promoting Series & Testimony Anthologies"),
    ("heroines_of_mormondom", "Heroines of “Mormondom” (Noble Women’s Lives Series, Book 2)", "Various Pioneer Authors", "VI. Faith-Promoting Series & Testimony Anthologies"),
    ("labors_in_the_vineyard", "Labors in the Vineyard (Faith-Promoting Series, Book 12)", "Various Pioneer Authors", "VI. Faith-Promoting Series & Testimony Anthologies"),
    ("eventful_narratives", "Eventful Narratives (Faith-Promoting Series, Book 13)", "Robert Aveson et al.", "VI. Faith-Promoting Series & Testimony Anthologies"),
    ("helpful_visions", "Helpful Visions (Faith-Promoting Series, Book 14)", "Various Pioneer Authors", "VI. Faith-Promoting Series & Testimony Anthologies"),
    ("precious_memories", "Precious Memories", "Various Pioneer Authors", "VI. Faith-Promoting Series & Testimony Anthologies"),
    ("treasures_in_heaven", "Treasures in Heaven", "Various Pioneer Authors", "VI. Faith-Promoting Series & Testimony Anthologies"),
    ("gems_of_reminiscence", "Gems of Reminiscence", "Various Pioneer Authors", "VI. Faith-Promoting Series & Testimony Anthologies"),

    # Division VII: Scriptural Narrative, Epic Poetry & Home Literature
    ("the_life_of_nephi", "The Life of Nephi, the Son of Lehi", "George Q. Cannon", "VII. Scriptural Narrative, Poetry & Home Literature"),
    ("elias_an_epic_of_the_ages", "Elias: An Epic of the Ages", "Orson F. Whitney", "VII. Scriptural Narrative, Poetry & Home Literature"),
    ("the_millennium_and_other_poems", "The Millennium, and Other Poems", "Parley P. Pratt", "VII. Scriptural Narrative, Poetry & Home Literature"),
    ("added_upon", "Added Upon: A Story of Pre-Existence, Mortality & Eternal Progression", "Nephi Anderson", "VII. Scriptural Narrative, Poetry & Home Literature"),
    ("dorian", "Dorian", "Nephi Anderson", "VII. Scriptural Narrative, Poetry & Home Literature"),
    ("story_of_chester_lawrence", "The Story of Chester Lawrence", "Nephi Anderson", "VII. Scriptural Narrative, Poetry & Home Literature"),
]


def _clean_chapter_heading(raw_title: str) -> str:
    """Clean upstream Gutenberg chapter headings (remove bracketed page numbers like `[457]`,
    fix `.:` punctuation, and normalize typography).
    """
    t = re.sub(r"\[\d+\]", "", raw_title)
    t = re.sub(r"\.:\s*", ": ", t)
    t = re.sub(r"::\s*", ": ", t)
    return clean_prose_text(t).strip()


def _extract_epub_paragraph_footnotes(
    epub_path: Path, book_slug: str
) -> tuple[dict[str, list[tuple[str, list[Annotation]]]], dict[str, str]]:
    """Parse a raw Gutenberg EPUB to build a FIFO queue lookup from normalized full paragraph alphanumeric string
    to `[(enriched_xhtml_paragraph, list_of_annotations_referenced), ...]`.
    """
    if not epub_path.exists():
        return {}, {}

    fn_defs: dict[str, str] = {}
    para_lookup: dict[str, list[tuple[str, list[Annotation]]]] = {}

    with zipfile.ZipFile(epub_path, "r") as zf:
        html_files = sorted([n for n in zf.namelist() if n.endswith((".html", ".xhtml", ".htm"))])
        soups: list[tuple[str, BeautifulSoup]] = []
        for hf in html_files:
            raw_bytes = zf.read(hf)
            soup = BeautifulSoup(raw_bytes.decode("utf-8", errors="replace"), "lxml")
            soups.append((hf, soup))

            # First pass: collect all footnote definitions
            for div in soup.find_all("div", class_="footnote"):
                a_id = div.find("a", id=True)
                if a_id:
                    txt = div.get_text(" ", strip=True)
                    txt = re.sub(r"^\[\d+\]\s*", "", txt)
                    fn_defs[a_id["id"]] = clean_prose_text(txt)

            for a_id in soup.find_all("a", id=True):
                aid = a_id["id"]
                if aid not in fn_defs and re.match(r"^chap\d+fn\d+$", aid, re.I):
                    if a_id.parent and a_id.parent.name == "p":
                        txt = a_id.parent.get_text(" ", strip=True)
                        txt = re.sub(r"^\d+\s*\.\s*", "", txt)
                        fn_defs[aid] = clean_prose_text(txt)

        if not fn_defs:
            return {}, {}

        # Second pass: find paragraphs containing inline footnote links
        fn_counter = 0
        for hf, soup in soups:
            for p in soup.find_all("p"):
                if p.find_parent("div", class_="footnote"):
                    continue
                first_a = p.find("a", id=True)
                if first_a and re.match(r"^chap\d+fn\d+$", first_a["id"], re.I):
                    continue

                links = p.find_all("a", href=True)
                matched_links = []
                for a in links:
                    href = a["href"]
                    if "#" in href:
                        frag = href.split("#", 1)[1]
                        if frag in fn_defs:
                            matched_links.append((a, frag))

                if not matched_links:
                    continue

                p_clone = BeautifulSoup(str(p), "lxml").find("p")
                for span_pg in p_clone.find_all("span", class_="x-ebookmaker-pageno"):
                    span_pg.decompose()
                for sup in p_clone.find_all("sup"):
                    sup.decompose()
                for a in p_clone.find_all("a", href=True):
                    if "#" in a["href"] and a["href"].split("#", 1)[1] in fn_defs:
                        a.decompose()

                stripped_text = clean_prose_text(p_clone.get_text(" ", strip=True), smart_typography=False)
                norm_key = re.sub(r"[^a-z0-9]", "", stripped_text.lower())[:55]
                if len(norm_key) < 15:
                    continue

                p_work = BeautifulSoup(str(p), "lxml").find("p")
                for span_pg in p_work.find_all("span", class_="x-ebookmaker-pageno"):
                    span_pg.decompose()

                p_annotations: list[Annotation] = []
                for a_tag in list(p_work.find_all("a", href=True)):
                    href = a_tag["href"]
                    if "#" in href:
                        frag = href.split("#", 1)[1]
                        if frag in fn_defs:
                            fn_counter += 1
                            ann_id = f"{book_slug}-fn-{fn_counter}"
                            raw_label = re.sub(r"[\[\]\s]", "", a_tag.get_text()) or str(fn_counter)
                            ann = Annotation(
                                id=ann_id,
                                label=raw_label,
                                note_type=AnnotationType.FOOTNOTE,
                                paragraphs=[fn_defs[frag]],
                            )
                            p_annotations.append(ann)

                            token = f"__PROTEUS_FN_{ann_id}_{raw_label}__"
                            sup_parent = a_tag.find_parent("sup")
                            if sup_parent:
                                sup_parent.replace_with(token)
                            else:
                                a_tag.replace_with(token)

                raw_with_tokens = p_work.get_text(" ", strip=True)
                escaped_html = escape_xhtml(raw_with_tokens, smart_typography=True)
                for ann in p_annotations:
                    token = f"__PROTEUS_FN_{ann.id}_{ann.label}__"
                    callout_xhtml = (
                        f'<sup class="fn-sup"><a class="noteref" epub:type="noteref" '
                        f'id="ref-{ann.id}" href="#fn-{ann.id}">[{ann.label}]</a></sup>'
                    )
                    escaped_html = escaped_html.replace(token, callout_xhtml)

                para_lookup.setdefault(norm_key, []).append((escaped_html, p_annotations))

    return para_lookup, fn_defs


def _is_major_chapter_boundary(
    title: str,
    rec_type: str,
    idx: int,
    has_explicit_chapters: bool,
    in_appendix_or_plates: bool,
    book_id: str,
) -> bool:
    """Determine whether a JSONL record in `non-canon-lds-literature` is a true top-level
    chapter/lecture/preface or a sub-section that should be merged into the active chapter.
    """
    if in_appendix_or_plates:
        return False

    t_upper = title.upper().strip()

    # Special handling for William Clayton's Journal: group daily entries under Month/Year chapters
    if book_id == "william_claytons_journal":
        if re.match(
            r"^(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+\d{4}$",
            t_upper,
        ):
            return True
        if idx <= 3 and ("FOREWORD" in t_upper or "WILLIAM CLAYTON" in t_upper):
            return True
        return False

    if any(t_upper.startswith(p) for p in ("PREFACE", "FOREWORD", "PUBLISHER", "INTRODUCTION")):
        return True

    if any(
        t_upper.startswith(prefix)
        for prefix in (
            "CHAPTER ",
            "LECTURE ",
            "LECTURES ON ",
            "PART ",
            "SERMON ",
            "EPISTLE ",
            "CHURCH HISTORY",
            "THE WENTWORTH LETTER",
            "THE ARTICLES OF FAITH",
        )
    ):
        return True

    # Only allow 'DISCOURSE ' or 'SECTION ' to start a top-level chapter if the book does not use 'CHAPTER '
    if not has_explicit_chapters and any(t_upper.startswith(p) for p in ("DISCOURSE ", "SECTION ")):
        return True

    # Match patterns like "JESUS THE CHRIST... CHAPTER 1" or "Discourses of Brigham Young CHAPTER I"
    if re.search(r"\b(?:CHAPTER|LECTURE)\s+(?:[IVXLCDM]+|\d+)\b", t_upper):
        return True

    # If the book has no explicit CHAPTER/LECTURE markers at all (e.g. Faith-Promoting Series anthologies),
    # respect `rec_type == "chapter"` or `rec_type == "section"` with substantial length
    if not has_explicit_chapters:
        return True

    return False


def _should_skip_boilerplate_section(title: str, rec_type: str) -> bool:
    """Filter out redundant raw Tables of Contents, Indexes with page numbers, or title-card duplicates."""
    t_upper = title.upper().strip()
    if rec_type == "contents" or t_upper in (
        "CONTENTS",
        "CONTENTS.",
        "TABLE OF CONTENTS",
        "TABLE OF CONTENTS.",
        "INDEX",
        "INDEX.",
        "FOOTNOTES",
        "FOOTNOTES.",
        "ERRATA",
        "ERRATA.",
        ":",
    ):
        return True
    if t_upper.startswith(("INDEX:", "TABLE OF CONTENTS:", "ENTERED AT STATIONERS", "TRANSCRIBER")):
        return True
    return False


def ingest_lds_classic_book(
    book_id: str,
    clean_dir: Path = Path("data/raw/lds-historical-literature/clean"),
    epub_dir: Path = Path("data/raw/lds-historical-literature/epub"),
    custom_title: str | None = None,
    custom_author: str | None = None,
    extract_epub_footnotes: bool = True,
    max_chapters_per_book: int | None = None,
) -> Book:
    """Ingest a single book from `non-canon-lds-literature` with full inline pop-up footnote recovery,
    strictly sequential chapter ordering, split-TOC deduplication, and sub-section consolidation.
    """
    jsonl_path = clean_dir / f"{book_id}.jsonl"
    if not jsonl_path.exists():
        raise FileNotFoundError(f"Missing LDS literature JSONL: {jsonl_path}")

    epub_path = epub_dir / f"{book_id}.epub"
    if not epub_path.exists():
        alt = epub_dir / f"{book_id.replace('_', '-')}.epub"
        if alt.exists():
            epub_path = alt

    book_slug = slugify(book_id)
    para_fn_lookup: dict[str, list[tuple[str, list[Annotation]]]] = {}
    if extract_epub_footnotes:
        para_fn_lookup, _ = _extract_epub_paragraph_footnotes(epub_path, book_slug)

    records = [json.loads(line) for line in open(jsonl_path, "r", encoding="utf-8") if line.strip()]
    first_rec = records[0] if records else {}
    book_title = custom_title or clean_prose_text(first_rec.get("book_title", book_id))
    book_author = custom_author or clean_prose_text(first_rec.get("author", "Unknown"))

    # Pre-scan records to detect:
    # 1. Whether this book uses explicit CHAPTER / LECTURE headings
    # 2. Whether there is a split Table of Contents before a later PREFACE or real CHAPTER I
    has_explicit_chapters = any(
        re.search(
            r"\b(?:CHAPTER|LECTURE)\s+(?:[IVXLCDM]+|\d+|FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH)\b",
            r.get("chapter_title", "").upper(),
        )
        for r in records
        if r.get("word_count", 0) > 180
    )

    # Find the index of the first real CHAPTER 1 / CHAPTER I (word_count > 180)
    first_real_ch1_idx = -1
    for i, r in enumerate(records):
        tu = r.get("chapter_title", "").upper()
        if r.get("word_count", 0) > 180 and re.search(r"\b(?:CHAPTER|LECTURE)\s+(?:I|1|FIRST)\b", tu):
            first_real_ch1_idx = i
            break

    front_matter: list[Chapter] = []
    chapters: list[Chapter] = []
    active_chapter: Chapter | None = None
    endnote_counter = 0
    in_back_index = False
    in_appendix_or_plates = False
    seen_contents_header = False

    for idx, rec in enumerate(records):
        raw_title = rec.get("chapter_title", "").strip()
        rec_type = rec.get("type", "chapter")
        word_cnt = rec.get("word_count", 0)
        t_upper = raw_title.upper().strip()

        if rec_type == "contents" or "CONTENTS" in t_upper:
            seen_contents_header = True
            continue

        # Once we hit a back-matter alphabetical index at the end of the book, skip it and its A..Z sub-records
        if idx > len(records) // 2 and (
            (rec_type == "back_matter" and "INDEX" in t_upper)
            or t_upper in ("INDEX", "INDEX.")
            or t_upper.startswith("INDEX:")
        ):
            in_back_index = True
            continue
        if in_back_index:
            # Single-letter index sections ('B', 'C', ..., 'Z')
            if re.match(r"^[A-Z]\.?$", t_upper) or rec_type == "back_matter":
                continue
            in_back_index = False

        if _should_skip_boilerplate_section(raw_title, rec_type):
            continue

        # Skip pure title-card records (< 120 words at start of book that just repeat title/edition/author)
        if idx <= 3 and word_cnt < 125 and len(records) > 3:
            if not any(k in t_upper for k in ("PREFACE", "FOREWORD", "INTRODUCTION", "CHAPTER", "LECTURE")):
                continue

        # Skip split-TOC synopsis records (e.g. in Parley P. Pratt's books, Life of Heber C. Kimball, Essentials in Church History)
        # where tiny CHAPTER I..N or Part I..N records (< 150 words) appear after CONTENTS and before the real CHAPTER 1
        if seen_contents_header and first_real_ch1_idx != -1 and idx < first_real_ch1_idx:
            if word_cnt < 160 and not any(k in t_upper for k in ("PREFACE", "FOREWORD", "INTRODUCTION")):
                continue
        if idx < 15 and word_cnt < 120 and t_upper.startswith(("PART ", "CHAPTER ")) and any(
            idx2 > idx and r2.get("word_count", 0) > 250 and t_upper[:10] in r2.get("chapter_title", "").upper()
            for idx2, r2 in enumerate(records)
        ):
            continue

        clean_title = _clean_chapter_heading(raw_title)
        raw_paras = [p.strip() for p in rec.get("text", "").split("\n\n") if p.strip()]

        # Remove leading paragraph if it duplicates the heading
        if raw_paras and _clean_chapter_heading(raw_paras[0]).upper() == clean_title.upper():
            raw_paras = raw_paras[1:]

        # Special handling: if this section is "NOTES." (e.g. in Articles of Faith), attach its paragraphs
        # as numbered study notes/blocks at the end of the active lecture
        if clean_title.upper() in ("NOTES.", "NOTES") and active_chapter is not None:
            active_chapter.blocks.append(
                ContentBlock(block_type=BlockType.SUBHEADING, text="Lecture Study Notes", level=3)
            )
            for p_str in raw_paras:
                p_clean = clean_prose_text(p_str)
                norm_key = re.sub(r"[^a-z0-9]", "", clean_prose_text(p_str, smart_typography=False).lower())[:55]
                if para_fn_lookup.get(norm_key):
                    html_str, anns = para_fn_lookup[norm_key].pop(0)
                    active_chapter.blocks.append(
                        ContentBlock(block_type=BlockType.PARAGRAPH, text=p_clean, html_text=html_str)
                    )
                    active_chapter.annotations.extend(anns)
                else:
                    active_chapter.blocks.append(ContentBlock(block_type=BlockType.PARAGRAPH, text=p_clean))
            continue

        # Check if this record starts an Appendix (e.g. Articles of Faith) or Plates section (e.g. House of the Lord)
        starts_appendix_or_plates = False
        if clean_title.upper() in ("APPENDIX.", "APPENDIX") or clean_title.upper().startswith("PLATES ILLUSTRATIVE"):
            starts_appendix_or_plates = True
            in_appendix_or_plates = True

        is_major = starts_appendix_or_plates or _is_major_chapter_boundary(
            clean_title,
            rec_type,
            idx,
            has_explicit_chapters,
            in_appendix_or_plates and not starts_appendix_or_plates,
            book_id,
        )

        # Build content blocks and match inline footnotes
        sec_blocks: list[ContentBlock] = []
        sec_annotations: list[Annotation] = []

        for p_str in raw_paras:
            p_clean = clean_prose_text(p_str)
            if not p_clean:
                continue
            norm_key = re.sub(r"[^a-z0-9]", "", clean_prose_text(p_str, smart_typography=False).lower())[:55]
            if para_fn_lookup.get(norm_key):
                html_str, anns = para_fn_lookup[norm_key].pop(0)
                sec_blocks.append(ContentBlock(block_type=BlockType.PARAGRAPH, text=p_clean, html_text=html_str))
                sec_annotations.extend(anns)
            else:
                sec_blocks.append(ContentBlock(block_type=BlockType.PARAGRAPH, text=p_clean))

        # Check if this record also has end-of-chapter scholarly notes in `rec["footnotes"]`
        raw_json_fns: list[str] = rec.get("footnotes", [])
        if raw_json_fns and book_id == "jesus_the_christ":
            grouped_notes: list[tuple[str, str, list[str]]] = []
            for fn_item in raw_json_fns:
                fn_clean = clean_prose_text(fn_item)
                m = re.match(r"^(\d+)\.\s+([^—]+?)(?:—|\.--|—\s*)(.+)$", fn_clean)
                if m:
                    grouped_notes.append((m.group(1), m.group(2).strip(" ."), [m.group(3).strip()]))
                elif re.match(r"^(\d+)\.\s+(.+)$", fn_clean):
                    m2 = re.match(r"^(\d+)\.\s+(.+)$", fn_clean)
                    grouped_notes.append((m2.group(1), f"Note {m2.group(1)}", [m2.group(2).strip()]))
                elif grouped_notes:
                    grouped_notes[-1][2].append(fn_clean)
                else:
                    grouped_notes.append((str(len(grouped_notes) + 1), "Chapter Note", [fn_clean]))

            if grouped_notes:
                note_links: list[str] = []
                for n_num, n_title, n_paras in grouped_notes:
                    endnote_counter += 1
                    ann_id = f"{book_slug}-endnote-{endnote_counter}"
                    ann = Annotation(
                        id=ann_id,
                        label=f"Note {n_num}",
                        title=f"{n_num}. {n_title}",
                        note_type=AnnotationType.ENDNOTE,
                        paragraphs=n_paras,
                    )
                    sec_annotations.append(ann)
                    note_links.append(
                        f'<a class="noteref endnote-pill" epub:type="noteref" id="ref-{ann_id}" href="#fn-{ann_id}">'
                        f'Note {n_num}: {escape_xhtml(n_title)}</a>'
                    )
                sec_blocks.append(
                    ContentBlock(
                        block_type=BlockType.SUBHEADING,
                        text="Author’s Chapter Notes",
                        level=3,
                    )
                )
                sec_blocks.append(
                    ContentBlock(
                        block_type=BlockType.PARAGRAPH,
                        text="Select a note below to view James E. Talmage’s commentary:",
                        html_text=" &#8226; ".join(note_links),
                    )
                )

        if is_major or active_chapter is None:
            # CRITICAL INVARIANT: A chapter can ONLY be placed in `front_matter` if `len(chapters) == 0`
            # AND its title is NOT a numbered Chapter/Lecture/Part/Section/Discourse.
            # This guarantees no chapter (like Chapter 1 or Chapter 28 of Jesus the Christ) can ever be hoisted out of order!
            has_chapter_keyword = bool(
                re.search(r"\b(?:CHAPTER|LECTURE|PART|SECTION|DISCOURSE|SERMON)\b", clean_title.upper())
            )
            is_fm = (
                len(chapters) == 0
                and not has_chapter_keyword
                and (
                    rec_type == "front_matter"
                    or any(k in clean_title.upper() for k in ("PREFACE", "FOREWORD", "INTRODUCTION", "PUBLISHER"))
                )
            )
            ch_obj = Chapter(
                id=f"{book_slug}-ch-{len(front_matter) + len(chapters) + 1:03d}",
                title=clean_title,
                is_front_matter=is_fm,
                blocks=sec_blocks,
                annotations=sec_annotations,
            )
            if is_fm:
                front_matter.append(ch_obj)
            else:
                chapters.append(ch_obj)
            active_chapter = ch_obj
        else:
            # Merge this sub-section into the active chapter with a level-3 subheading
            active_chapter.blocks.append(
                ContentBlock(block_type=BlockType.SUBHEADING, text=clean_title, level=3)
            )
            active_chapter.blocks.extend(sec_blocks)
            active_chapter.annotations.extend(sec_annotations)

    # If `max_chapters_per_book` is set (e.g. for the 71-book Complete Restoration Literature Compendium),
    # consolidate chapters into balanced multi-chapter reading units so the omnibus spine stays nimble.
    if max_chapters_per_book and len(chapters) > max_chapters_per_book:
        chunk_size = max(2, (len(chapters) + max_chapters_per_book - 1) // max_chapters_per_book)
        consolidated: list[Chapter] = []
        for i in range(0, len(chapters), chunk_size):
            batch = chapters[i : i + chunk_size]
            first_c = batch[0]
            last_c = batch[-1]
            combined_blocks: list[ContentBlock] = []
            combined_anns: list[Annotation] = []
            for sub_c in batch:
                combined_blocks.append(
                    ContentBlock(block_type=BlockType.SUBHEADING, text=sub_c.title, level=2)
                )
                combined_blocks.extend(sub_c.blocks)
                combined_anns.extend(sub_c.annotations)
            part_num = len(consolidated) + 1
            title_range = first_c.title if len(batch) == 1 else f"Part {part_num}: {first_c.title[:40]} – {last_c.title[:40]}"
            consolidated.append(
                Chapter(
                    id=f"{book_slug}-part-{part_num:02d}",
                    title=title_range,
                    blocks=combined_blocks,
                    annotations=combined_anns,
                )
            )
        chapters = consolidated

    return Book(
        id=book_slug,
        title=book_title,
        full_title=clean_prose_text(first_rec.get("book_title", book_title)),
        author=book_author,
        front_matter=front_matter,
        chapters=chapters,
    )


def ingest_foundational_lds_classics_anthology(
    clean_dir: Path = Path("data/raw/lds-historical-literature/clean"),
    epub_dir: Path = Path("data/raw/lds-historical-literature/epub"),
) -> Work:
    """Compile the 9 Foundational Latter-day Saint Doctrinal Classics into a single omnibus `Work`."""
    books: list[Book] = []
    for book_id, title, author in FOUNDATIONAL_LDS_CLASSICS:
        bk = ingest_lds_classic_book(
            book_id=book_id,
            clean_dir=clean_dir,
            epub_dir=epub_dir,
            custom_title=title,
            custom_author=author,
        )
        books.append(bk)

    intro = Chapter(
        id="lds-classics-editorial-preface",
        title="Editorial Preface to the Anthology",
        is_front_matter=True,
        blocks=[
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=clean_prose_text(
                    "This omnibus volume unites nine foundational classics of Latter-day Saint theology, "
                    "revelation, christology, and apostolic instruction from the first century of the Restoration: "
                    "Joseph Smith's Lectures on Faith (1835) and Wentworth Letter (1842); "
                    "James E. Talmage's monumental trilogy—Jesus the Christ (1915), The Articles of Faith (1899), "
                    "and The House of the Lord (1912)—complete with restored interactive pop-up footnotes and "
                    "end-of-chapter scholarly commentary; Parley P. Pratt's Key to the Science of Theology (1855) "
                    "and A Voice of Warning (1837); the Discourses of Brigham Young; and President Joseph F. Smith's "
                    "Gospel Doctrine (1919)."
                ),
            )
        ],
    )

    return Work(
        id="foundational-lds-classics-anthology",
        title="Foundational Classics of the Restoration",
        subtitle="A Nine-Volume Doctrinal Omnibus of Early Latter-day Saint Theology & Apostolic Writings",
        authors=[
            "Joseph Smith Jr.",
            "James E. Talmage",
            "Parley P. Pratt",
            "Brigham Young",
            "Joseph F. Smith",
        ],
        edition_label="Proteus Annotated Omnibus Edition",
        description=(
            "Complete nine-book doctrinal anthology of foundational Latter-day Saint classics, "
            "featuring native Kindle pop-up footnotes and hierarchical multi-book navigation."
        ),
        subjects=[
            "Church of Jesus Christ of Latter-day Saints -- Doctrines",
            "Theology, Doctrinal",
            "Restoration Movement",
        ],
        front_matter=[intro],
        books=books,
    )


def ingest_complete_lds_literature_compendium(
    clean_dir: Path = Path("data/raw/lds-historical-literature/clean"),
    epub_dir: Path = Path("data/raw/lds-historical-literature/epub"),
) -> Work:
    """Compile all 71 historical Latter-day Saint books and treatises (6.0 million words) into a
    single organized, seven-division master library (`complete-lds-literature-compendium.epub`).
    """
    books: list[Book] = []
    seen_ids: set[str] = set()

    # Build catalogued books in thematic order
    div_summary_lines: list[str] = []
    current_div = ""
    for book_id, title, author, division in COMPLETE_LDS_LITERATURE_CATALOGUE:
        if division != current_div:
            current_div = division
            div_summary_lines.append(f"• {division}")
        seen_ids.add(book_id)
        bk = ingest_lds_classic_book(
            book_id=book_id,
            clean_dir=clean_dir,
            epub_dir=epub_dir,
            custom_title=f"[{division.split('.')[0]}] {title}",
            custom_author=author,
            extract_epub_footnotes=(book_id in {b[0] for b in FOUNDATIONAL_LDS_CLASSICS}),
            max_chapters_per_book=None,
        )
        bk.subtitle = f"Division {division} — Author: {author}"
        books.append(bk)

    # Ensure any remaining JSONL book in `clean_dir` not in our explicit list is also included
    for p in sorted(clean_dir.glob("*.jsonl")):
        if p.stem in ("non-canon-lds-literature", "non-canon-lds-literature-chapters"):
            continue
        if p.stem not in seen_ids:
            bk = ingest_lds_classic_book(
                book_id=p.stem,
                clean_dir=clean_dir,
                epub_dir=epub_dir,
                extract_epub_footnotes=False,
                max_chapters_per_book=None,
            )
            books.append(bk)

    preface_blocks = [
        ContentBlock(
            block_type=BlockType.PARAGRAPH,
            text=clean_prose_text(
                f"The Complete Restoration Literature Compendium unites all {len(books)} historical Latter-day Saint "
                "books, theological treatises, documentary histories, apostolic biographies, pioneer journals, "
                "and Faith-Promoting Series anthologies (spanning more than 6,000,000 words) into a single, "
                "systematically organized digital library."
            ),
        ),
        ContentBlock(
            block_type=BlockType.SUBHEADING,
            text="Seven-Division Thematic Architecture",
            level=3,
        ),
        ContentBlock(
            block_type=BlockType.PARAGRAPH,
            text=" | ".join(div_summary_lines),
        ),
    ]

    for div_name in dict.fromkeys(d[3] for d in COMPLETE_LDS_LITERATURE_CATALOGUE):
        div_books = [
            f"“{t}” ({a})"
            for _, t, a, dv in COMPLETE_LDS_LITERATURE_CATALOGUE
            if dv == div_name
        ]
        preface_blocks.append(
            ContentBlock(block_type=BlockType.SUBHEADING, text=div_name, level=3)
        )
        preface_blocks.append(
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text="; ".join(div_books) + ".",
            )
        )

    intro = Chapter(
        id="complete-lds-compendium-guide",
        title="Reader’s Guide & Seven-Division Catalogue (71 Volumes)",
        is_front_matter=True,
        blocks=preface_blocks,
    )

    return Work(
        id="complete-lds-literature-compendium",
        title="The Complete Restoration Literature Compendium",
        subtitle="All 71 Historical Volumes of Early Latter-day Saint Theology, Documentary History, Journals & Pioneer Literature",
        authors=[
            "Joseph Smith Jr.",
            "Brigham Young",
            "John Taylor",
            "Wilford Woodruff",
            "Joseph F. Smith",
            "James E. Talmage",
            "B. H. Roberts",
            "Parley P. Pratt",
            "Orson Pratt",
            "Orson F. Whitney",
            "Joseph Fielding Smith",
            "George Q. Cannon",
            "Lucy Mack Smith",
        ],
        edition_label="Proteus Complete 71-Volume Master Library",
        description=(
            "Comprehensive 71-volume omnibus of 19th and early 20th-century Latter-day Saint literature "
            "(over 6 million words), organized into seven thematic and historical divisions."
        ),
        subjects=[
            "Church of Jesus Christ of Latter-day Saints -- History",
            "Church of Jesus Christ of Latter-day Saints -- Doctrines",
            "Latter-day Saint Literature",
        ],
        front_matter=[intro],
        books=books,
    )
