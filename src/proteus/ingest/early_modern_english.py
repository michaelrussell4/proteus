"""Early Modern English Guide to Reading the Scriptures (`early_modern_english.py`).

A concise, practical, example-driven guide to the Early Modern English of the
King James Bible and the KJV-style idiom of Restoration scripture (Book of Mormon,
Doctrine and Covenants, Pearl of Great Price). Every scriptural reference is linked
to a native Kindle pop-up footnote displaying the verbatim canonical verse, and each
citation is validated at build time against the scripture corpus.
"""

from __future__ import annotations

import re
import warnings

from proteus.core.models import (
    Annotation,
    AnnotationType,
    BlockType,
    Book,
    Chapter,
    ContentBlock,
    Work,
)
from proteus.core.references import make_canonical_ref
from proteus.core.typography import clean_prose_text, escape_xhtml
from proteus.ingest.standard_works import ingest_standard_work


class ScriptureCorpusLookup:
    """Fast in-memory lookup of verbatim canonical verses for pop-up footnotes."""

    def __init__(self) -> None:
        self.verses: dict[str, tuple[str, str]] = {}
        self._load()

    def _load(self) -> None:
        for slug in (
            "old-testament",
            "new-testament",
            "book-of-mormon",
            "doctrine-and-covenants",
            "pearl-of-great-price",
        ):
            try:
                work = ingest_standard_work(slug)
            except Exception as exc:  # pragma: no cover - surfaced via warning
                warnings.warn(
                    f"Early Modern English guide: could not load '{slug}' for pop-up verses ({exc!r}).",
                    stacklevel=2,
                )
                continue
            for bk in work.books:
                for ch in bk.chapters:
                    for v in ch.verses:
                        if v.canonical_ref:
                            self.verses[v.canonical_ref] = (
                                v.citation_label or v.canonical_ref,
                                v.text,
                            )

    def get_text(self, book: str, chapter: int, verse: int) -> str:
        """Return the verbatim verse text, or an empty string if it is not in the corpus."""
        return self.verses.get(make_canonical_ref(book, chapter, verse), ("", ""))[1]

    def get_popup_paragraphs(
        self,
        book: str,
        chapter: int,
        verse: int,
        note: str = "",
    ) -> tuple[str, list[str]]:
        ref = make_canonical_ref(book, chapter, verse)
        label, text = self.verses.get(ref, (f"{book} {chapter}:{verse}", ""))
        paras: list[str] = []
        if text:
            paras.append(f"“{escape_xhtml(text)}” ({escape_xhtml(label)})")
        if note:
            paras.append(escape_xhtml(note))
        if not paras:
            paras.append(escape_xhtml(label))
        return label, paras


class ChapterDraft:
    """Builder for a chapter with prose, tables, callouts, and Kindle pop-up footnotes."""

    def __init__(
        self,
        chapter_id: str,
        title: str,
        subtitle: str | None,
        headnote: str | None,
        corpus: ScriptureCorpusLookup,
        number: int | None = None,
        is_front_matter: bool = False,
    ) -> None:
        self.chapter_id = chapter_id
        self.title = title
        self.subtitle = subtitle
        self.headnote = headnote
        self.corpus = corpus
        self.number = number
        self.is_front_matter = is_front_matter
        self.blocks: list[ContentBlock] = []
        self.annotations: list[Annotation] = []
        self._fn_counter = 0

    def cite(
        self,
        book: str,
        chapter: int,
        verse: int,
        note: str = "",
        display_label: str | None = None,
        expect: str | None = None,
    ) -> str:
        """Create an `<a epub:type="noteref">` callout and register its `<aside epub:type="footnote">`.

        If ``expect`` is given, the build fails unless that phrase appears verbatim
        (case- and whitespace-insensitive) in the cited verse—guarding against
        citations that point at the wrong verse or misquote it.
        """
        _verify_citation(self.corpus, book, chapter, verse, expect)
        self._fn_counter += 1
        ann_id = f"{self.chapter_id}-fn-{self._fn_counter}"
        cite_title, paras = self.corpus.get_popup_paragraphs(
            book=book,
            chapter=chapter,
            verse=verse,
            note=note,
        )
        vis_label = display_label or cite_title
        ann = Annotation(
            id=ann_id,
            label=str(self._fn_counter),
            note_type=AnnotationType.FOOTNOTE,
            title=cite_title,
            paragraphs=paras,
        )
        self.annotations.append(ann)
        return (
            f'<sup class="fn-sup"><a class="noteref" epub:type="noteref" '
            f'id="ref-{ann_id}" href="#fn-{ann_id}">[{escape_xhtml(vis_label)}]</a></sup>'
        )

    def subheading(self, text: str) -> None:
        self.blocks.append(ContentBlock(block_type=BlockType.SUBHEADING, text=text, level=3))

    def para(self, html_or_text: str) -> None:
        plain = _strip_tags(html_or_text)
        self.blocks.append(
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=clean_prose_text(plain),
                html_text=html_or_text,
            )
        )

    def callout(self, title: str, paragraphs_html: list[str]) -> None:
        inner = f"<p><strong>{escape_xhtml(title)}</strong></p>" + "".join(
            f"<p>{p}</p>" for p in paragraphs_html
        )
        plain = title + " " + " ".join(_strip_tags(p) for p in paragraphs_html)
        self.blocks.append(
            ContentBlock(
                block_type=BlockType.CALLOUT,
                text=clean_prose_text(plain),
                html_text=inner,
            )
        )

    def table(self, headers: list[str], rows: list[list[str]]) -> None:
        thead = "<thead><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr></thead>"
        tbody_rows = []
        plain_parts = list(headers)
        for r in rows:
            tbody_rows.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
            for c in r:
                plain_parts.append(_strip_tags(c))
        tbody = "<tbody>" + "".join(tbody_rows) + "</tbody>"
        html = f'<table class="grammar-table">{thead}{tbody}</table>'
        self.blocks.append(
            ContentBlock(
                block_type=BlockType.TABLE,
                text=" ".join(plain_parts),
                html_text=html,
            )
        )

    def build(self) -> Chapter:
        return Chapter(
            id=self.chapter_id,
            number=self.number,
            title=self.title,
            subtitle=self.subtitle,
            headnote=self.headnote,
            is_front_matter=self.is_front_matter,
            blocks=self.blocks,
            annotations=self.annotations,
        )


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def _normalize_for_match(text: str) -> str:
    text = text.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip()


def _verify_citation(
    corpus: ScriptureCorpusLookup,
    book: str,
    chapter: int,
    verse: int,
    expect: str | None,
) -> None:
    """Fail the build if a cited verse is missing or does not contain the expected phrase."""
    if not corpus.verses:
        return  # corpus unavailable; a warning was already emitted during load
    text = corpus.get_text(book, chapter, verse)
    if not text:
        raise ValueError(f"Citation {book} {chapter}:{verse} not found in the scripture corpus.")
    if expect and _normalize_for_match(expect) not in _normalize_for_match(text):
        raise ValueError(
            f"Citation {book} {chapter}:{verse} does not contain expected phrase {expect!r}. "
            f"Verse text: {text!r}"
        )


def _build_front_matter(corpus: ScriptureCorpusLookup) -> list[Chapter]:
    preface = ChapterDraft(
        chapter_id="preface",
        title="How to Use This Guide",
        subtitle="Why Early Modern English Unlocks Scripture",
        headnote=None,
        corpus=corpus,
        is_front_matter=True,
    )
    preface.para(
        "The King James Bible (1611) is written in <strong>Early Modern English</strong>—the English of "
        "William Tyndale, William Shakespeare, and the 1611 translators—and Restoration scripture (the "
        "Book of Mormon, Doctrine and Covenants, and Pearl of Great Price) is written in the same "
        "scriptural idiom, closely modeled on the King James style. To modern ears, words like "
        "<em>thou</em>, <em>whither</em>, <em>suffer</em>, and <em>let</em> can feel like decorative "
        "archaisms or, worse, trip us into reading the exact opposite of what a verse means."
    )
    preface.para(
        "In reality, Early Modern English is often <strong>more precise</strong> than Modern English. "
        "It distinguishes one listener from a crowd (<em>thee</em> vs. <em>you</em>), location from "
        "direction (<em>here</em> vs. <em>hither</em> vs. <em>hence</em>), and conditional wishes from "
        "statements of fact (<em>if thou be</em> vs. <em>thou art</em>)."
    )
    preface.para(
        "This guide is built to be concise, practical, and immediately useful while you read. Every "
        "bracketed reference—such as "
        f"{preface.cite('Luke', 22, 31, 'Satan wants all the apostles (you = plural).', expect='desired to have you')}—is a clickable "
        "pop-up note containing the full verse so you can see each rule in action without leaving the page."
    )
    return [preface.build()]


def _build_chapter_1_pronouns(corpus: ScriptureCorpusLookup) -> Chapter:
    ch = ChapterDraft(
        chapter_id="ch-1-pronouns",
        number=1,
        title="Chapter 1: Pronouns — Thou, Thee, Ye, You & Thy/Thine",
        subtitle="Why ‘Thou’ Is Personal (Not Formal) and ‘Ye’ Means All of You",
        headnote="Modern English uses ‘you’ for everything. Scripture preserves a sharper four-way grid.",
        corpus=corpus,
    )
    ch.para(
        "The single biggest grammatical advantage of Early Modern English is that it separates "
        "<strong>singular</strong> (one person) from <strong>plural</strong> (two or more people), and "
        "<strong>subject</strong> (the one doing the action) from <strong>object</strong> (the one "
        "receiving it)."
    )
    ch.table(
        headers=["Number", "Subject", "Object", "Possessive"],
        rows=[
            ["<strong>Singular (one person)</strong>", "<em>thou</em>", "<em>thee</em>", "<em>thy / thine</em>"],
            ["<strong>Plural (two or more)</strong>", "<em>ye</em>", "<em>you</em>", "<em>your / yours</em>"],
        ],
    )
    ch.callout(
        "Quick Memory Trick",
        [
            "<strong>T-words</strong> (<em>thou, thee, thy, thine</em>) are always <strong>singular</strong> (one person).",
            "<strong>Y-words</strong> (<em>ye, you, your, yours</em>) are plural throughout the King James Bible (multiple people).",
            "Notice the alphabetical pattern for plurals: <strong>Y</strong>e comes before <strong>Y</strong>ou, just like Subject comes before Object.",
        ],
    )
    ch.para(
        "<strong>A note on Restoration scripture:</strong> The Book of Mormon and especially the Doctrine and "
        "Covenants do not keep this grid perfectly. They sometimes use <em>you</em> for a single listener and "
        "mix <em>thee</em> and <em>you</em> in the same passage. When the Lord addresses Oliver Cowdery alone, "
        "for example, he says, “I say unto <strong>you</strong>, my son, that because <strong>you</strong> did "
        "not translate…” "
        f"{ch.cite('D&C', 9, 1, 'Singular “you” addressed to Oliver Cowdery alone.', expect='I say unto you, my son, that because you did not translate')}. "
        "In those books, let context decide."
    )

    ch.subheading("1. Why ‘Thou’ Addresses God")
    ch.para(
        "Many readers assume <em>thou</em> and <em>thee</em> are formal, reverent honorifics. Historically, "
        "the reverse was closer to the truth: in Tudor and Stuart English, <em>ye/you</em> had become the "
        "polite pronoun (and the only plural), while <em>thou/thee</em> was the singular used with family, "
        "close friends, children, and social inferiors. By 1611 <em>thou</em> was already fading from "
        "everyday speech. The translators kept it anyway for accuracy: Hebrew and Greek distinguish singular "
        "from plural “you,” and <em>thou</em> preserved that distinction. Because God is addressed as a "
        "single “you” in the original languages, prayer in the King James Bible uses <em>thou</em>, "
        "<em>thee</em>, and <em>thy</em> "
        f"{ch.cite('Matthew', 6, 9, 'Jesus teaches disciples to pray to God as singular “thy” and “art.”', expect='which art in heaven, Hallowed be thy name')}. "
        "The “reverent” feel that <em>thou</em> has today came later, once the word survived mainly in "
        "scripture and prayer."
    )

    ch.subheading("2. When Singular vs. Plural Changes the Verse")
    ch.para(
        "Because Modern English collapsed all four forms into <em>you</em>, modern translations sometimes "
        "blur who is being addressed. Watching the T-words and Y-words reveals sudden shifts:"
    )
    ch.para(
        f"• <strong>Luke 22:31–32</strong>: Jesus tells Peter, “Satan hath desired to have <strong>you</strong> "
        f"[plural: all the apostles], that he may sift <strong>you</strong> as wheat: But I have prayed for "
        f"<strong>thee</strong> [singular: Peter alone], that <strong>thy</strong> faith fail not” "
        f"{ch.cite('Luke', 22, 31, '“You” = all the apostles.', expect='Satan hath desired to have you, that he may sift you as wheat')}"
        f"{ch.cite('Luke', 22, 32, '“Thee” and “thy” = Peter specifically.', expect='I have prayed for thee, that thy faith fail not')}."
    )
    ch.para(
        f"• <strong>John 3:7</strong>: Speaking to Nicodemus alone, Jesus says, “Marvel not that I said unto "
        f"<strong>thee</strong> [singular: Nicodemus], <strong>Ye</strong> [plural: everyone] must be born "
        f"again” {ch.cite('John', 3, 7, 'Shifts from singular “thee” to universal plural “ye.”', expect='Marvel not that I said unto thee, Ye must be born again')}."
    )
    ch.para(
        f"• <strong>Mosiah 2:17</strong>: King Benjamin addresses his entire congregation with plural "
        f"pronouns: “when <strong>ye</strong> are in the service of <strong>your</strong> fellow beings "
        f"<strong>ye</strong> are only in the service of <strong>your</strong> God” "
        f"{ch.cite('Mosiah', 2, 17, 'Plural “ye” and “your” apply to the whole covenant community.', expect='when ye are in the service of your fellow beings ye are only in the service of your God')}."
    )

    ch.subheading("3. The ‘Thy / Thine’ and ‘My / Mine’ Sound Rule")
    ch.para(
        "<em>Thy</em> vs. <em>thine</em> (and <em>my</em> vs. <em>mine</em>) works much like <em>a</em> vs. "
        "<em>an</em> in Modern English. The King James Bible applies it as a strong tendency rather than an "
        "unbreakable rule:"
    )
    ch.para(
        f"• <strong>thy / my</strong> before consonant sounds: <em>thy closet</em>, <em>thy door</em> "
        f"{ch.cite('Matthew', 6, 6, '“thy closet” and “thy door” before consonants.', expect='enter into thy closet, and when thou hast shut thy door')}."
    )
    ch.para(
        f"• <strong>thine / mine</strong> before vowel sounds: "
        f"<em>mine eyes</em> {ch.cite('Psalms', 121, 1, '“mine eyes” before a vowel.', expect='lift up mine eyes')}, "
        f"<em>mine own hand</em> {ch.cite('Philemon', 1, 19, '“mine own” before a vowel.', expect='with mine own hand')}."
    )
    ch.para(
        "• Before words beginning with <em>h</em>, usage varies. The 1611 translators often wrote "
        f"<em>thine heart</em> {ch.cite('Deuteronomy', 6, 5, '“thine heart” before h, then “thy soul” and “thy might” before consonants.', expect='with all thine heart, and with all thy soul')}, "
        "but <em>thy hand</em> and <em>thine hand</em> both occur. Don’t read anything into the difference."
    )
    ch.para(
        "• <strong>thine / mine</strong> also stand alone without a following noun: "
        f"“The silver is <em>mine</em>” {ch.cite('Haggai', 2, 8, 'Standalone “mine.”', expect='The silver is mine')}, "
        f"“<em>thine</em> is the kingdom” {ch.cite('Matthew', 6, 13, 'Standalone “thine.”', expect='thine is the kingdom')}."
    )
    return ch.build()


def _build_chapter_2_verbs(corpus: ScriptureCorpusLookup) -> Chapter:
    ch = ChapterDraft(
        chapter_id="ch-2-verbs",
        number=2,
        title="Chapter 2: Verbs — Endings, Moods & ‘Be’ vs. ‘Have’",
        subtitle="Decoding -est, -eth, Subjunctives, and ‘He Is Risen’",
        headnote="Verb endings aren’t decoration—they track person, mood, and whether an action’s result still stands.",
        corpus=corpus,
    )

    ch.subheading("1. Present-Tense Endings: -est and -eth")
    ch.table(
        headers=["Subject", "Regular Verb", "To Be", "To Have", "To Do"],
        rows=[
            ["<em>I</em>", "<em>love</em>", "<em>am</em>", "<em>have</em>", "<em>do</em>"],
            ["<em>Thou</em> (2nd sg.)", "<em>lov<strong>est</strong></em>", "<em>art</em>", "<em>hast</em>", "<em>dost / doest</em>"],
            ["<em>He / She / It</em> (3rd sg.)", "<em>lov<strong>eth</strong></em>", "<em>is</em>", "<em>hath</em>", "<em>doth / doeth</em>"],
            ["<em>We / Ye / They</em> (pl.)", "<em>love</em>", "<em>are</em>", "<em>have</em>", "<em>do</em>"],
        ],
    )
    ch.para(
        f"Notice how <strong>-est</strong> pairs with <em>thou</em> "
        f"{ch.cite('John', 21, 15, '“lovest thou me... thou knowest that I love thee.”', expect='lovest thou me')}, while "
        f"<strong>-eth</strong> pairs with singular third-person subjects (“charity <em>suffereth</em> long” "
        f"{ch.cite('1 Corinthians', 13, 4, 'Third-person singular -eth.', expect='Charity suffereth long')}). Plural subjects take no ending at all. "
        "(Don’t confuse the verb ending with the superlative <em>-est</em> on adjectives: <em>highest</em>, "
        "<em>greatest</em>.)"
    )
    ch.para(
        f"<strong>Dost/doth vs. doest/doeth:</strong> Generally, <em>dost/doth</em> acts as a helper verb "
        f"(“doth he cry?” {ch.cite('2 Nephi', 26, 25, 'Auxiliary “doth.”', expect='doth he cry')}), whereas <em>doest/doeth</em> "
        f"means “perform” or “practice” as the main verb (“That thou <em>doest</em>, do quickly” "
        f"{ch.cite('John', 13, 27, 'Main verb “doest” = what you are doing.', expect='That thou doest, do quickly')})."
    )

    ch.subheading("2. Shall vs. Will (Decree vs. Desire)")
    ch.para(
        "In Modern English, <em>will</em> is our default future tense. Early Modern English could use both "
        "verbs for the future, but each also kept a distinct flavor worth listening for:"
    )
    ch.para(
        f"• <strong>Shall / shalt</strong> often expresses obligation, prophetic certainty, or external decree: "
        f"“Thou <em>shalt</em> love the Lord” {ch.cite('Mark', 12, 30, 'Command/obligation with “shalt.”', expect='thou shalt love the Lord')}."
    )
    ch.para(
        f"• <strong>Will / wilt</strong> often keeps its root sense of personal desire, willingness, or refusal. "
        f"In Gethsemane, Jesus contrasts his own desire with the Father’s: “not as I <em>will</em>, but as "
        f"thou <em>wilt</em>” {ch.cite('Matthew', 26, 39, '“Wilt” = what thou desirest/willest.', expect='not as I will, but as thou wilt')}. Likewise, "
        f"“ye <em>will not</em> come to me” means “you <em>refuse / are unwilling</em> to come,” not merely a "
        f"prediction {ch.cite('John', 5, 40, '“Will not” = are unwilling to (Greek: ou thelete).', expect='ye will not come to me')}. "
        "When a <em>will</em> seems odd as a simple future, try reading it as “want to” or “am willing to.”"
    )

    ch.subheading("3. The Subjunctive Mood (Why Verbs Drop Their Endings)")
    ch.para(
        "When you see “If thou <strong>be</strong> the Son of God” instead of “If thou <em>art</em>,” that "
        "is not a typo—it is the <strong>subjunctive mood</strong>. Early Modern English drops the "
        "<em>-est</em> or <em>-eth</em> ending and uses the bare verb stem (<em>be, slay, come</em>) to mark "
        "uncertainty, conditions, concessions, or prayers:"
    )
    ch.para(
        f"• <strong>Condition:</strong> “If thou <em>be</em> the Son of God...” "
        f"{ch.cite('Matthew', 4, 3, 'Subjunctive “be” marks a hypothetical test.', expect='If thou be the Son of God')} (contrast with "
        f"<em>thou art</em> for stated fact)."
    )
    ch.para(
        f"• <strong>Concession:</strong> “Though he <em>slay</em> me, yet will I trust in him” "
        f"{ch.cite('Job', 13, 15, 'Subjunctive “slay” (not “slayeth”) after “though.”', expect='Though he slay me, yet will I trust in him')}."
    )
    ch.para(
        f"• <strong>Prayer / Wish:</strong> “Thy kingdom <em>come</em>. Thy will <em>be</em> done” "
        f"{ch.cite('Matthew', 6, 10, 'Optative subjunctive expressing prayerful desire.', expect='Thy kingdom come. Thy will be done')}."
    )

    ch.subheading("4. ‘Is Come’ and ‘Is Risen’ (Be + Past Participle)")
    ch.para(
        "With verbs of motion or change of state (<em>come, go, rise, fall, become</em>), Early Modern "
        "English frequently uses <strong>be</strong> instead of <strong>have</strong> as the helper verb. "
        "Whereas “he <em>has</em> risen” focuses on the past event, “he <em>is</em> risen” emphasizes the "
        "<strong>present resulting state</strong>—he is alive right now "
        f"{ch.cite('Matthew', 28, 6, '“He is risen” = he stands risen now.', expect='he is risen')}"
        f"{ch.cite('John', 10, 10, '“I am come” = I am here now.', expect='I am come')}."
    )

    ch.subheading("5. Common Archaic Past Forms")
    ch.table(
        headers=["Archaic Form", "Modern Equivalent", "Example"],
        rows=[
            ["<em>spake</em>", "spoke", ch.cite("Hebrews", 1, 1, "“Spake in time past.”", expect="spake")],
            [
                "<em>brake</em>",
                "broke",
                ch.cite("Matthew", 26, 26, "“Blessed it, and brake it.”", expect="brake it")
                + ch.cite("1 Corinthians", 11, 24, "“He brake it.”", expect="he brake it"),
            ],
            ["<em>gat</em>", "got", ch.cite("2 Samuel", 8, 13, "“David gat him a name.”", expect="David gat him a name")],
            [
                "<em>holpen</em>",
                "helped",
                ch.cite("Luke", 1, 54, "“He hath holpen his servant Israel.”", expect="hath holpen")
                + ch.cite("Psalms", 83, 8, "“They have holpen the children of Lot.”", expect="have holpen"),
            ],
            [
                "<em>wax / waxed</em>",
                "grow / grew",
                ch.cite("Luke", 1, 80, "“Waxed strong in spirit.”", expect="waxed strong in spirit")
                + ch.cite("2 Nephi", 4, 24, "“Have I waxed bold in mighty prayer.”", expect="waxed bold"),
            ],
            [
                "<em>wot / wist</em>",
                "know / knew",
                ch.cite("Genesis", 21, 26, "“I wot not” = I do not know.", expect="I wot not")
                + ch.cite("Luke", 2, 49, "“Wist ye not” = did you not know?", expect="wist ye not"),
            ],
        ],
    )
    return ch.build()


def _build_chapter_3_directionals(corpus: ScriptureCorpusLookup) -> Chapter:
    ch = ChapterDraft(
        chapter_id="ch-3-directionals",
        number=3,
        title="Chapter 3: Direction & Space — Hither, Thither, Whither & Hence",
        subtitle="The Nine-Word Spatial Grid That Modern English Lost",
        headnote="Modern English uses ‘here/there/where’ for both location and destination. Scripture keeps them distinct.",
        corpus=corpus,
    )
    ch.para(
        "Early Modern English had a remarkably neat 3×3 system for place and movement. Every set answers "
        "three different questions: <strong>Where at?</strong>, <strong>Where to?</strong>, and "
        "<strong>Where from?</strong>"
    )
    ch.table(
        headers=["Perspective", "Location (At / In)", "Motion Toward (To)", "Motion Away (From)"],
        rows=[
            ["<strong>Near me</strong>", "<em>here</em> (this place)", "<em><strong>hither</strong></em> (to here)", "<em><strong>hence</strong></em> (from here)"],
            ["<strong>Over there</strong>", "<em>there</em> (that place)", "<em><strong>thither</strong></em> (to there)", "<em><strong>thence</strong></em> (from there)"],
            ["<strong>Question / Relative</strong>", "<em>where</em> (what place)", "<em><strong>whither</strong></em> (to what place)", "<em><strong>whence</strong></em> (from what place)"],
        ],
    )
    ch.para(
        f"• <strong>Hither</strong> (to this place): “bring <em>hither</em>, and slay them before me” "
        f"{ch.cite('Luke', 19, 27, '“Bring hither” = bring them here.', expect='bring hither, and slay them before me')}."
    )
    ch.para(
        f"• <strong>Thither</strong> (to that place): “where I am, <em>thither</em> ye cannot come” "
        f"{ch.cite('John', 7, 34, '“Thither” = to that place.', expect='where I am, thither ye cannot come')}."
    )
    ch.para(
        f"• <strong>Whither</strong> (to what place / wherever): “<em>Whither</em> shall I go from thy spirit?” "
        f"{ch.cite('Psalms', 139, 7, '“Whither” = to what place?', expect='Whither shall I go from thy spirit')}; “<em>whither</em> thou goest, I will go” "
        f"{ch.cite('Ruth', 1, 16, '“Whither” = to whatever place.', expect='whither thou goest, I will go')}."
    )
    ch.para(
        f"• <strong>Hence / Thence / Whence</strong> (from here / from there / from where): "
        f"“Take these things <em>hence</em>” {ch.cite('John', 2, 16, '“Hence” = away from here.', expect='Take these things hence')}; "
        f"“scattered them abroad from <em>thence</em>” {ch.cite('Genesis', 11, 8, '“From thence” = from that place.', expect='scattered them abroad from thence')}; "
        f"“from <em>whence</em> cometh my help” {ch.cite('Psalms', 121, 1, '“Whence” = from where / what source.', expect='from whence cometh my help')}."
    )

    ch.subheading("Compound Words with There- and Where-")
    ch.para(
        "Words like <em>thereof, therein, thereby, therewith, wherefore, wherein, whereby</em> look "
        "intimidating, but the formula is effortless: <strong>there-</strong> means <em>that/it</em>, and "
        "<strong>where-</strong> means <em>which/what</em>. Just flip the halves around:"
    )
    ch.table(
        headers=["Word", "Simple Translation", "Word", "Simple Translation"],
        rows=[
            ["<em>thereof</em>", "of it / of that", "<em>whereof</em>", "of which / about what"],
            ["<em>therein</em>", "in it / in that", "<em>wherein</em>", "in which / in what"],
            ["<em>thereby</em>", "by it / by that", "<em>whereby</em>", "by which / how"],
            ["<em>therewith</em>", "with it / with that", "<em>wherewith</em>", "with which / with what"],
            ["<em>therefore</em>", "for that reason", "<em>wherefore</em>", "for which reason / <strong>why?</strong>"],
        ],
    )
    ch.callout(
        "Watch Out: ‘Wherefore’ Often Means ‘Why’",
        [
            "In a statement, <em>wherefore</em> means “for which reason / therefore.” In a question, it means "
            "<strong>why</strong>—not “where”: “O thou of little faith, <em>wherefore</em> didst thou doubt?” "
            f"{ch.cite('Matthew', 14, 31, '“Wherefore didst thou doubt?” = Why did you doubt?', expect='wherefore didst thou doubt')}.",
        ],
    )
    return ch.build()


def _build_chapter_4_vernacular_connectors(corpus: ScriptureCorpusLookup) -> Chapter:
    ch = ChapterDraft(
        chapter_id="ch-4-vernacular",
        number=4,
        title="Chapter 4: Everyday Vernacular — 50+ Words & Logical Connectors",
        subtitle="Numbers, Everyday Early Modern Words, and the Hinges of Scriptural Sentences",
        headnote="Beyond grammar and false friends, scripture uses dozens of older English words and logical hinges that reward a quick gloss.",
        corpus=corpus,
    )

    ch.para(
        "Many words in the King James Bible and Restoration scripture aren’t tricky “false friends” (those "
        "get their own list in Chapter 6)—they are simply everyday Early Modern English words that dropped "
        "out of modern conversation. Here are roughly fifty of the most common, grouped by how they work."
    )

    ch.subheading("1. Numbers, Measures, People & Everyday Things")
    ch.table(
        headers=["Word", "Meaning", "Scripture Example"],
        rows=[
            [
                "<strong>twain</strong>",
                "two",
                f"“rent in <em>twain</em>” {ch.cite('Matthew', 27, 51, 'Torn in two.', expect='rent in twain')}; "
                f"“go with him <em>twain</em>” {ch.cite('Matthew', 5, 41, 'Go two miles.', expect='go with him twain')}",
            ],
            [
                "<strong>score</strong>",
                "twenty (<em>threescore</em> = 60, <em>fourscore</em> = 80)",
                f"“threescore years and ten” = 70 {ch.cite('Psalms', 90, 10, '3 × 20 + 10 = 70.', expect='threescore years and ten')}",
            ],
            [
                "<strong>cubit</strong>",
                "forearm length (roughly 18 inches)",
                f"“as it were two hundred <em>cubits</em>” {ch.cite('John', 21, 8, 'About 300 feet / 100 yards from shore.', expect='two hundred cubits')}",
            ],
            [
                "<strong>furlong</strong>",
                "one-eighth of a mile (~200 meters)",
                f"“about threescore <em>furlongs</em>” (~7.5 miles) {ch.cite('Luke', 24, 13, '60 furlongs ≈ 7.5 miles.', expect='threescore furlongs')}",
            ],
            [
                "<strong>naught / nought</strong>",
                "nothing, worthless",
                f"“set at <em>nought</em>” {ch.cite('Acts', 4, 11, '“Set at nought” = treated as worthless.', expect='set at nought')}",
            ],
            [
                "<strong>aught</strong> (often spelled <em>ought</em>)",
                "anything at all",
                f"“can ye say <em>aught</em> of yourselves?” {ch.cite('Mosiah', 2, 25, '“Aught” = anything.', expect='say aught of yourselves')}; "
                f"“hath <em>ought</em> against thee” {ch.cite('Matthew', 5, 23, '“Ought” here is the spelling of “aught” = anything.', expect='hath ought against thee')}",
            ],
            [
                "<strong>whit</strong>",
                "smallest bit (<em>every whit</em> = completely)",
                f"“made a man every <em>whit</em> whole” {ch.cite('John', 7, 23, '“Every whit whole” = completely whole.', expect='every whit whole')}",
            ],
            [
                "<strong>kine</strong>",
                "cows, cattle (old plural of <em>cow</em>)",
                f"“seven well favoured <em>kine</em>” {ch.cite('Genesis', 41, 2, '“Kine” = cows.', expect='seven well favoured kine')}",
            ],
            [
                "<strong>raiment</strong>",
                "clothing, garments",
                f"“for both food and <em>raiment</em>” {ch.cite('Mosiah', 4, 19, '“Raiment” = clothing.', expect='food and raiment')}",
            ],
            [
                "<strong>meat</strong>",
                "food in general (not only animal flesh)",
                f"“My <em>meat</em> is to do the will of him that sent me” {ch.cite('John', 4, 34, '“Meat” = sustenance, nourishment.', expect='My meat is to do the will')}",
            ],
            [
                "<strong>pottage</strong>",
                "thick stew or boiled soup",
                f"“Jacob <em>sod</em> [boiled] <em>pottage</em>” {ch.cite('Genesis', 25, 29, '“Sod” = boiled (past tense of seethe); “pottage” = stew.', expect='sod pottage')}",
            ],
            [
                "<strong>shambles</strong>",
                "meat market (place of slaughter/sale)",
                f"“Whatsoever is sold in the <em>shambles</em>, that eat” {ch.cite('1 Corinthians', 10, 25, '“Shambles” = meat market, not chaos.', expect='sold in the shambles')}",
            ],
            [
                "<strong>husbandman</strong>",
                "farmer, vinedresser, caretaker of a field",
                f"“my Father is the <em>husbandman</em>” {ch.cite('John', 15, 1, 'The gardener/vinedresser caring for the vine.', expect='my Father is the husbandman')}",
            ],
            [
                "<strong>publican</strong>",
                "tax collector (not a tavern keeper)",
                f"“do not even the <em>publicans</em> the same?” {ch.cite('Matthew', 5, 46, 'Local toll/tax collectors despised by neighbors.', expect='even the publicans the same')}",
            ],
            [
                "<strong>kindred</strong>",
                "extended family, clan, relatives",
                f"“every nation, <em>kindred</em>, tongue and people” {ch.cite('1 Nephi', 19, 17, '“Kindred” = clan, extended family line.', expect='every nation, kindred, tongue and people')}",
            ],
        ],
    )

    ch.subheading("2. Verbs — Actions, Speech & Duty")
    ch.table(
        headers=["Verb", "Meaning", "Scripture Example"],
        rows=[
            [
                "<strong>hearken</strong>",
                "listen closely and obey",
                f"“that you should <em>hearken</em> unto me” {ch.cite('Mosiah', 2, 9, 'More than hearing: attentive, obedient listening.', expect='hearken unto me')}",
            ],
            [
                "<strong>abide</strong>",
                "stay, remain, dwell, endure",
                f"“<em>Abide</em> in me, and I in you” {ch.cite('John', 15, 4, 'Remain steadily connected.', expect='Abide in me, and I in you')}",
            ],
            [
                "<strong>tarry</strong>",
                "wait, stay behind, linger",
                f"“<em>tarry</em> ye in the city of Jerusalem” {ch.cite('Luke', 24, 49, '“Tarry” = wait/stay.', expect='tarry ye in the city of Jerusalem')}",
            ],
            [
                "<strong>beseech</strong>",
                "plead earnestly, beg",
                f"“I <em>beseech</em> you therefore, brethren” {ch.cite('Romans', 12, 1, 'Strong, heartfelt pleading.', expect='I beseech you therefore, brethren')}",
            ],
            [
                "<strong>sojourn</strong>",
                "stay temporarily, live as a traveler or guest",
                f"“while we did <em>sojourn</em> in the wilderness” {ch.cite('1 Nephi', 17, 3, 'Live temporarily away from home.', expect='while we did sojourn in the wilderness')}",
            ],
            [
                "<strong>cleave</strong>",
                "cling closely, stick fast (context can also mean “split”)",
                f"“shall <em>cleave</em> unto his wife” {ch.cite('Genesis', 2, 24, 'Stick fast / bond closely.', expect='cleave unto his wife')}",
            ],
            [
                "<strong>gird</strong>",
                "fasten around the waist (belt, robe, or armor)",
                f"“I did <em>gird</em> on his armor about my loins” {ch.cite('1 Nephi', 4, 19, 'Strap or buckle on.', expect='gird on his armor')}",
            ],
            [
                "<strong>eschew</strong>",
                "shun, deliberately avoid",
                f"“Let him <em>eschew</em> evil, and do good” {ch.cite('1 Peter', 3, 11, 'Turn away from / avoid.', expect='eschew evil, and do good')}",
            ],
            [
                "<strong>ensue</strong>",
                "pursue, chase after (not merely “follow later”)",
                f"“let him seek peace, and <em>ensue</em> it” {ch.cite('1 Peter', 3, 11, '“Ensue” = actively pursue.', expect='seek peace, and ensue it')}",
            ],
            [
                "<strong>chasten</strong>",
                "discipline, correct, train",
                f"“whom the Lord loveth he <em>chasteneth</em>” {ch.cite('Hebrews', 12, 6, 'Formative correction, not spite.', expect='whom the Lord loveth he chasteneth')}",
            ],
            [
                "<strong>upbraid</strong>",
                "scold, reproach, find fault",
                f"“giveth to all men liberally, and <em>upbraideth</em> not” {ch.cite('James', 1, 5, 'Gives generously without scolding.', expect='upbraideth not')}",
            ],
            [
                "<strong>gainsay</strong>",
                "contradict, speak against, oppose",
                f"“not be able to <em>gainsay</em> nor resist” {ch.cite('Luke', 21, 15, 'Literally “say against.”', expect='able to gainsay nor resist')}",
            ],
            [
                "<strong>dissemble</strong>",
                "disguise one’s motives, act hypocritically",
                f"“the other Jews <em>dissembled</em> likewise” {ch.cite('Galatians', 2, 13, 'Put on a false front.', expect='dissembled likewise')}",
            ],
            [
                "<strong>succour</strong>",
                "run to help, relieve in distress",
                f"“able to <em>succour</em> them that are tempted” {ch.cite('Hebrews', 2, 18, 'Come to the aid of.', expect='succour them that are tempted')}",
            ],
            [
                "<strong>behoove</strong> (<em>behoved / behooveth</em>)",
                "be necessary or fitting for",
                f"“it <em>behooveth</em> the great Creator” {ch.cite('2 Nephi', 9, 5, 'It is fitting and necessary.', expect='it behooveth the great Creator')}; "
                f"“thus it <em>behoved</em> Christ to suffer” {ch.cite('Luke', 24, 46, 'It was necessary for Christ.', expect='thus it behoved Christ to suffer')}",
            ],
            [
                "<strong>impute</strong>",
                "credit or charge to someone’s account",
                f"“unto whom God <em>imputeth</em> righteousness” {ch.cite('Romans', 4, 6, 'Credits / reckons righteousness to.', expect='imputeth righteousness')}",
            ],
            [
                "<strong>occupy</strong>",
                "trade, invest, do business",
                f"“<em>Occupy</em> till I come” {ch.cite('Luke', 19, 13, 'Put the money to work, not merely “stay put.”', expect='Occupy till I come')}",
            ],
            [
                "<strong>trow</strong>",
                "suppose, think",
                f"“Doth he thank that servant…? I <em>trow</em> not.” {ch.cite('Luke', 17, 9, '“I trow not” = I should think not.', expect='I trow not')}",
            ],
        ],
    )

    ch.subheading("3. Descriptors, Time & Space (Adjectives, Adverbs & Prepositions)")
    ch.table(
        headers=["Word", "Meaning", "Scripture Example"],
        rows=[
            [
                "<strong>asunder</strong>",
                "apart, into separate pieces",
                f"“let not man put <em>asunder</em>” {ch.cite('Matthew', 19, 6, 'Separate / tear apart.', expect='let not man put asunder')}",
            ],
            [
                "<strong>sundry</strong>",
                "various, several (at different times)",
                f"“at <em>sundry</em> times” {ch.cite('Hebrews', 1, 1, 'At various times.', expect='at sundry times')}",
            ],
            [
                "<strong>divers</strong>",
                "various, different kinds of",
                f"“there are <em>divers</em> ways and means” {ch.cite('Mosiah', 4, 29, 'Many different kinds.', expect='divers ways and means')}",
            ],
            [
                "<strong>strait</strong>",
                "narrow, tight, hemmed in (distinct from <em>straight</em>)",
                f"“in this <em>strait</em> and narrow path” {ch.cite('2 Nephi', 31, 18, '“Strait” = tight, narrow; not a synonym for “unbent.”', expect='strait and narrow path')}",
            ],
            [
                "<strong>meet</strong>",
                "fitting, proper, appropriate",
                f"“it was not <em>meet</em> for him, Lehi” {ch.cite('1 Nephi', 7, 1, 'Not fitting or right.', expect='not meet for him')}; "
                f"“it is not <em>meet</em> that I should command in all things” {ch.cite('D&C', 58, 26, 'Not appropriate or wise.', expect='not meet that I should command')}",
            ],
            [
                "<strong>comely</strong>",
                "pleasant, decent, fitting",
                f"“is it <em>comely</em> that a woman pray unto God uncovered?” {ch.cite('1 Corinthians', 11, 13, '“Comely” = seemly, proper.', expect='is it comely')}",
            ],
            [
                "<strong>froward</strong>",
                "perverse, stubbornly contrary",
                f"“not only to the good and gentle, but also to the <em>froward</em>” {ch.cite('1 Peter', 2, 18, 'Difficult, perverse, contrary.', expect='also to the froward')}",
            ],
            [
                "<strong>wroth</strong>",
                "intensely angry, furious",
                f"“Herod… was exceeding <em>wroth</em>” {ch.cite('Matthew', 2, 16, 'Filled with wrath.', expect='exceeding wroth')}",
            ],
            [
                "<strong>wont</strong>",
                "accustomed, in the habit of",
                f"“the governor was <em>wont</em> to release unto the people a prisoner” {ch.cite('Matthew', 27, 15, 'Was in the habit of doing.', expect='governor was wont to release')}",
            ],
            [
                "<strong>fain</strong>",
                "gladly, eagerly (<em>would fain</em> = would gladly)",
                f"“we would <em>fain</em> be glad if we could command the rocks” {ch.cite('Alma', 12, 14, 'Would gladly / eagerly.', expect='we would fain be glad')}",
            ],
            [
                "<strong>sore</strong> (adverb)",
                "severely, intensely, greatly",
                f"“fell on their face, and were <em>sore</em> afraid” {ch.cite('Matthew', 17, 6, '“Sore afraid” = terrified.', expect='were sore afraid')}",
            ],
            [
                "<strong>clean</strong> (adverb)",
                "completely, entirely",
                f"“passed <em>clean</em> over Jordan” {ch.cite('Joshua', 3, 17, 'Crossed completely over.', expect='passed clean over Jordan')}",
            ],
            [
                "<strong>privily</strong>",
                "secretly, privately",
                f"“they sought to put them away <em>privily</em>” {ch.cite('Alma', 14, 3, 'In secret, out of public sight.', expect='put them away privily')}",
            ],
            [
                "<strong>haply</strong>",
                "perhaps, by chance (root of <em>perhaps</em>)",
                f"“if <em>haply</em> he might find any thing thereon” {ch.cite('Mark', 11, 13, '“If haply” = if perhaps.', expect='if haply he might find')}",
            ],
            [
                "<strong>forthwith</strong>",
                "immediately, without delay",
                f"“<em>forthwith</em> they sprung up” {ch.cite('Matthew', 13, 5, 'Immediately, right away.', expect='forthwith they sprung up')}",
            ],
            [
                "<strong>verily</strong>",
                "truly, certainly",
                f"“For <em>verily</em> I say unto you” {ch.cite('Matthew', 5, 18, 'Truly, solemnly (from the same root as “very”).', expect='verily I say unto you')}",
            ],
            [
                "<strong>ere</strong>",
                "before",
                f"“come down <em>ere</em> my child die” {ch.cite('John', 4, 49, 'Before my child dies.', expect='ere my child die')}",
            ],
            [
                "<strong>betwixt</strong>",
                "between",
                f"“judge, I pray you, <em>betwixt</em> me and my vineyard” {ch.cite('2 Nephi', 15, 3, 'Between me and my vineyard.', expect='betwixt me and my vineyard')}",
            ],
            [
                "<strong>nigh</strong>",
                "near, close",
                f"“summer is now <em>nigh</em> at hand” {ch.cite('D&C', 45, 37, 'Close at hand.', expect='summer is now nigh at hand')}",
            ],
            [
                "<strong>hard by / hard to</strong>",
                "right next to, very close to",
                f"“whose house joined <em>hard to</em> the synagogue” {ch.cite('Acts', 18, 7, 'Right next door to.', expect='joined hard to the synagogue')}",
            ],
            [
                "<strong>withal</strong>",
                "also, besides, with it",
                f"“and not <em>withal</em> to signify the crimes” {ch.cite('Acts', 25, 27, 'And not also specify.', expect='not withal to signify')}",
            ],
            [
                "<strong>aforetime / heretofore</strong>",
                "previously, before now",
                f"“him that <em>aforetime</em> was blind” {ch.cite('John', 9, 13, 'Previously blind.', expect='aforetime was blind')}; "
                f"“neither <em>heretofore</em>, nor since” {ch.cite('Exodus', 4, 10, 'Neither in the past nor since.', expect='neither heretofore, nor since')}",
            ],
        ],
    )

    ch.subheading("4. Logical Connectors and Pivots")
    ch.para(
        "Scriptural arguments turn on a handful of classic logical hinges. Knowing them keeps you from "
        "losing the thread in long sentences:"
    )
    ch.table(
        headers=["Connector", "Modern Meaning", "Scripture Example"],
        rows=[
            [
                "<strong>wherefore</strong>",
                "for which reason / therefore (in questions: why)",
                f"“<em>wherefore</em>, inasmuch as ye shall keep...” {ch.cite('1 Nephi', 17, 13, 'Draws a conclusion from what came before.', expect='wherefore, inasmuch as ye shall keep')}",
            ],
            [
                "<strong>inasmuch as / forasmuch as</strong>",
                "since, seeing that, to the degree that",
                f"“<em>inasmuch as</em> ye shall keep my commandments” {ch.cite('1 Nephi', 17, 13, 'States the condition or reason.', expect='inasmuch as ye shall keep my commandments')}; "
                f"“<em>Forasmuch as</em> this people refuseth” {ch.cite('2 Nephi', 18, 6, 'Seeing that / because.', expect='Forasmuch as this people refuseth')}",
            ],
            [
                "<strong>insomuch that</strong>",
                "so much so that, to such an extent that",
                f"“he did lust after it, <em>insomuch that</em> he thrust us out” {ch.cite('1 Nephi', 3, 25, 'Shows the result or degree.', expect='insomuch that he thrust us out')}",
            ],
            [
                "<strong>albeit</strong>",
                "although, even though",
                f"“<em>albeit</em> I do not say to thee...” {ch.cite('Philemon', 1, 19, 'Concedes a point (“even though I won’t mention...”).', expect='albeit I do not say to thee')}",
            ],
            [
                "<strong>peradventure</strong>",
                "perhaps, by chance, what if",
                f"“<em>Peradventure</em> there be fifty righteous” {ch.cite('Genesis', 18, 24, '“What if / perhaps there are fifty?”', expect='Peradventure there be fifty righteous')}",
            ],
            [
                "<strong>howbeit</strong>",
                "however, nevertheless",
                f"“<em>Howbeit</em> this kind goeth not out...” {ch.cite('Matthew', 17, 21, '“Howbeit” = however.', expect='Howbeit this kind goeth not out')}",
            ],
            [
                "<strong>nevertheless / notwithstanding</strong>",
                "even so, in spite of that",
                f"“<em>nevertheless</em> at thy word I will let down the net” {ch.cite('Luke', 5, 5, 'Even so, despite the failed night.', expect='nevertheless at thy word')}; "
                f"“<em>notwithstanding</em> we had suffered many afflictions” {ch.cite('1 Nephi', 17, 6, 'Even though / in spite of.', expect='notwithstanding we had suffered')}",
            ],
            [
                "<strong>whereas</strong>",
                "considering that; while on the contrary",
                f"“<em>whereas</em> I was blind, now I see” {ch.cite('John', 9, 25, 'Contrasts before and after.', expect='whereas I was blind, now I see')}",
            ],
            [
                "<strong>lest</strong>",
                "for fear that, so that ... not",
                f"“Watch ye and pray, <em>lest</em> ye enter into temptation” {ch.cite('Mark', 14, 38, '“Lest” = so that you do not.', expect='Watch ye and pray, lest ye enter into temptation')}",
            ],
            [
                "<strong>save / except</strong>",
                "unless, except (<em>save it be</em> = except)",
                f"“they have all gone astray <em>save</em> it be a few” {ch.cite('2 Nephi', 28, 14, '“Save it be a few” = except for a few.', expect='gone astray save it be a few')}; "
                f"“<em>Except</em> a man be born again” {ch.cite('John', 3, 3, '“Except” = unless.', expect='Except a man be born again')}",
            ],
        ],
    )
    return ch.build()


def _build_chapter_5_syntax(corpus: ScriptureCorpusLookup) -> Chapter:
    ch = ChapterDraft(
        chapter_id="ch-5-syntax",
        number=5,
        title="Chapter 5: Sentence Structure — Questions, ‘Which,’ and ‘Did’",
        subtitle="Why Scripture Sounds Inverted (And Why ‘He Did Speak’ Isn’t Emphatic)",
        headnote="Early Modern English hadn’t yet made ‘do’ mandatory in questions and negatives—and used ‘did’ differently in statements.",
        corpus=corpus,
    )

    ch.subheading("1. Questions and Negatives Without ‘Do’")
    ch.para(
        "Modern English requires a helper <em>do</em> for almost every question and negative (“<em>Do</em> you "
        "know?”, “I <em>don’t</em> know”). Early Modern English simply flipped the verb and subject, or put "
        "<em>not</em> right after the main verb:"
    )
    ch.para(
        f"• <strong>Questions:</strong> “<em>Knowest thou</em> the condescension of God?” (= Do you know?) "
        f"{ch.cite('1 Nephi', 11, 16, 'Verb-subject inversion instead of “Do you know?”', expect='Knowest thou the condescension of God')}; “<em>Wist ye not</em>?” "
        f"(= Didn’t you know?) {ch.cite('Luke', 2, 49, 'Direct inversion in a negative question.', expect='wist ye not')}."
    )
    ch.para(
        f"• <strong>Negatives:</strong> “I <em>say not</em> unto thee” (= I don’t say) "
        f"{ch.cite('Matthew', 18, 22, 'Post-verbal “not” without “do.”', expect='I say not unto thee')}; “I <em>wot not</em>” (= I don’t know) "
        f"{ch.cite('Genesis', 21, 26, '“Wot not” = know not.', expect='I wot not')}."
    )

    ch.subheading("2. Unemphatic ‘Do’ and ‘Did’ in Statements")
    ch.para(
        "Today, “we <em>did</em> travel” sounds emphatic—as if someone doubted whether we traveled. "
        "In 16th-century English (and throughout the Book of Mormon), affirmative <em>do/did + verb</em> was "
        "usually a <strong>neutral, unemphatic past-tense marker</strong>—just an ordinary way to say "
        "“we traveled” or “God tested Abraham” "
        f"{ch.cite('1 Nephi', 17, 1, '“We did again take our journey… we did travel” = we journeyed, we traveled.', expect='we did again take our journey in the wilderness; and we did travel')}"
        f"{ch.cite('Genesis', 22, 1, '“God did tempt Abraham” = God tested Abraham.', expect='God did tempt Abraham')}."
    )

    ch.subheading("3. ‘Which’ Used for People")
    ch.para(
        "Today, we use <em>who</em> for people and <em>which</em> for things. In 1611, <em>which</em> "
        "regularly referred to people—including God: “Our Father <em>which</em> art in heaven” "
        f"{ch.cite('Matthew', 6, 9, 'Personal “which” = who.', expect='Our Father which art in heaven')}; “it is he <em>which</em> was ordained of God” "
        f"{ch.cite('Acts', 10, 42, '“Which” referring to Christ.', expect='it is he which was ordained of God')}."
    )

    ch.subheading("4. Double Superlatives for Emphasis")
    ch.para(
        "Early Modern English occasionally stacked <em>most</em> onto an <em>-est</em> superlative for "
        "extra force; it was accepted usage at the time, not a mistake. Paul describes living according to “the <em>most straitest</em> "
        "sect of our religion” "
        f"{ch.cite('Acts', 26, 5, 'Double superlative “most straitest” = the very strictest.', expect='the most straitest sect of our religion')}."
    )
    return ch.build()


def _build_chapter_6_false_friends(corpus: ScriptureCorpusLookup) -> Chapter:
    ch = ChapterDraft(
        chapter_id="ch-6-false-friends",
        number=6,
        title="Chapter 6: ‘False Friends’ — Words Whose Meanings Shifted",
        subtitle="Familiar Words That Quietly Mislead Modern Readers",
        headnote="The trickiest words in scripture aren’t the ones you don’t recognize—they’re the ones you think you already know.",
        corpus=corpus,
    )
    ch.para(
        "A “false friend” is a word that still exists today, so your brain supplies its modern meaning—even "
        "though the 1611 or 1829 meaning was noticeably different. Mastering this list prevents more "
        "misreadings than any other single step."
    )

    ch.table(
        headers=["Word", "1611 / Scriptural Meaning", "Modern Trap", "Example"],
        rows=[
            ["<strong>suffer</strong>", "allow, permit", "feel pain", f"{ch.cite('Matthew', 19, 14, '“Suffer little children... to come unto me” = allow them.', expect='Suffer little children')}"],
            ["<strong>let</strong>", "hinder, restrain (also: allow)", "only “allow”", f"{ch.cite('Isaiah', 43, 13, '“Who shall let it?” = who can stop it?', expect='who shall let it')}{ch.cite('2 Thessalonians', 2, 7, '“He who now letteth” = he who now restrains.', expect='he who now letteth will let')}"],
            ["<strong>prevent</strong>", "go before, precede, anticipate", "stop from happening", f"{ch.cite('Psalms', 119, 148, '“Mine eyes prevent the night watches” = wake before them.', expect='Mine eyes prevent the night watches')}{ch.cite('1 Thessalonians', 4, 15, '“Shall not prevent” = shall not precede.', expect='shall not prevent them which are asleep')}"],
            ["<strong>conversation</strong>", "conduct, way of life, behavior", "talking", f"{ch.cite('1 Timothy', 4, 12, '“In word, in conversation” = in speech and in conduct.', expect='in word, in conversation')}"],
            ["<strong>condescension</strong>", "gracious stooping down by one of higher rank", "snobbishness", f"{ch.cite('1 Nephi', 11, 16, 'God’s gracious stooping down to mortals.', expect='condescension of God')}"],
            ["<strong>charity</strong>", "pure, self-giving divine love", "donating money", f"{ch.cite('1 Corinthians', 13, 4, 'Greek agapē, self-giving love.', expect='Charity suffereth long')}{ch.cite('Moroni', 7, 45, '“Charity suffereth long...”', expect='charity suffereth long')}"],
            ["<strong>peculiar</strong>", "personally owned, treasured", "weird, eccentric", f"{ch.cite('1 Peter', 2, 9, '“A peculiar people” = God’s own treasured possession.', expect='a peculiar people')}"],
            ["<strong>quick / quicken</strong>", "alive / make alive", "fast", f"{ch.cite('2 Timothy', 4, 1, '“The quick and the dead” = the living and the dead.', expect='judge the quick and the dead')}{ch.cite('Moses', 6, 65, '“Quickened in the inner man” = made spiritually alive.', expect='quickened in the inner man')}"],
            ["<strong>tempt</strong>", "test, put to the proof", "entice to sin", f"{ch.cite('Genesis', 22, 1, '“God did tempt Abraham” = God tested Abraham.', expect='God did tempt Abraham')}"],
            ["<strong>take no thought</strong>", "do not be anxious or worried", "don’t plan ahead", f"{ch.cite('Matthew', 6, 25, 'Command against anxiety, not prudence.', expect='Take no thought for your life')}"],
            ["<strong>careful</strong>", "anxious, full of worry", "cautious", f"{ch.cite('Philippians', 4, 6, '“Be careful for nothing” = do not worry about anything.', expect='Be careful for nothing')}"],
            ["<strong>betimes</strong>", "promptly, early, in good time", "sometimes", f"{ch.cite('D&C', 121, 43, '“Reproving betimes” = promptly/early, before resentment festers.', expect='Reproving betimes with sharpness')}"],
            ["<strong>by and by</strong>", "immediately, right now", "later, eventually", f"{ch.cite('Mark', 6, 25, '“Give me by and by” = right now, immediately.', expect='give me by and by')}"],
            ["<strong>anon / straightway</strong>", "at once, immediately", "soon / eventually", f"{ch.cite('Matthew', 13, 20, '“Anon” = immediately.', expect='anon with joy receiveth it')}{ch.cite('Mark', 1, 18, '“Straightway” = immediately.', expect='straightway they forsook their nets')}"],
            ["<strong>corn</strong>", "grain in general (in the Bible, chiefly wheat or barley)", "maize (American corn)", f"{ch.cite('Matthew', 12, 1, '“Ears of corn” = heads of grain.', expect='ears of corn')}"],
            ["<strong>cunning</strong>", "skillful, masterly", "sneaky, sly", f"{ch.cite('Exodus', 35, 35, '“Cunning workman” = skilled artisan.', expect='cunning workman')}"],
            ["<strong>bowels</strong>", "seat of deep compassion", "digestive tract", f"{ch.cite('Colossians', 3, 12, '“Bowels of mercies” = heartfelt compassion.', expect='bowels of mercies')}{ch.cite('Mosiah', 15, 9, '“Bowels of mercy.”', expect='bowels of mercy')}"],
            ["<strong>reins</strong>", "kidneys; figuratively, the innermost feelings and conscience", "horse straps", f"{ch.cite('Psalms', 7, 9, '“Trieth the hearts and reins.”', expect='trieth the hearts and reins')}"],
            ["<strong>virtue</strong>", "power, healing force", "moral purity only", f"{ch.cite('Mark', 5, 30, '“Virtue had gone out of him” = healing power.', expect='virtue had gone out of him')}"],
            ["<strong>leasing</strong>", "lying, falsehood", "renting", f"{ch.cite('Psalms', 4, 2, '“Seek after leasing” = seek after lies.', expect='seek after leasing')}"],
            ["<strong>halt</strong>", "limp, waver between two sides", "stop", f"{ch.cite('1 Kings', 18, 21, '“How long halt ye between two opinions?” = limp/waver.', expect='How long halt ye between two opinions')}"],
            ["<strong>usury</strong>", "any interest charged on a loan", "excessive interest", f"{ch.cite('Exodus', 22, 25, 'Charging any interest to the poor.', expect='neither shalt thou lay upon him usury')}"],
        ],
    )
    return ch.build()


def _build_chapter_7_hebraisms(corpus: ScriptureCorpusLookup) -> Chapter:
    ch = ChapterDraft(
        chapter_id="ch-7-hebraisms",
        number=7,
        title="Chapter 7: Hebrew Idioms in English Clothing",
        subtitle="Why the Scriptures Repeat Words, Stack ‘And,’ and Say ‘Of’",
        headnote="The 1611 translators often translated Hebrew phrasing word-for-word, giving scriptural English its distinctive cadence.",
        corpus=corpus,
    )
    ch.para(
        "Although we read the Bible and the Book of Mormon in English, many of their sentence patterns come "
        "straight from Hebrew. Four simple patterns explain most of the repetitive or unusual phrasing:"
    )
    ch.para(
        f"• <strong>“And it came to pass”</strong>: Not verbal padding—it translates the standard Hebrew "
        f"narrative hinge (<em>wayəhî</em>), which signals a new scene, time jump, or turning point, much "
        f"like a paragraph break or “Next...” {ch.cite('1 Nephi', 2, 6, 'Marks a narrative transition.', expect='And it came to pass')}."
    )
    ch.para(
        f"• <strong>Doubled words for certainty:</strong> Hebrew intensifies a verb by pairing it with itself. "
        f"In English this comes out as “in <em>blessing I will bless</em> thee, and in <em>multiplying I will "
        f"multiply</em> thy seed” (= I will <em>surely</em> bless and multiply) "
        f"{ch.cite('Genesis', 22, 17, 'Doubled verb = “surely / abundantly.”', expect='in blessing I will bless thee, and in multiplying I will multiply')}, or “thou shalt <em>surely</em> "
        f"die” (literally “dying thou shalt die” "
        f"{ch.cite('Genesis', 2, 17, 'The 1611 KJV margin reads: “Heb. dying thou shalt die.”', expect='thou shalt surely die')})."
    )
    ch.para(
        f"• <strong>“Of” phrases instead of adjectives:</strong> Hebrew has relatively few adjectives, so it "
        f"uses <em>noun + of + noun</em>: “bowels <em>of mercy</em>” (= merciful heart "
        f"{ch.cite('Mosiah', 15, 9, 'Noun-of-noun modifier.', expect='bowels of mercy')}), “rod <em>of iron</em>” (= iron rod "
        f"{ch.cite('1 Nephi', 8, 19, 'Noun-of-noun modifier.', expect='a rod of iron')}), and even in the Greek New Testament, which "
        f"absorbed the same Semitic habit, “man <em>of sin</em>” (= sinful man "
        f"{ch.cite('2 Thessalonians', 2, 3, 'Semitic-style genitive in New Testament Greek.', expect='that man of sin')})."
    )
    ch.para(
        f"• <strong>Body-part expressions:</strong> Hebrew grounds abstract actions in the body: "
        f"<em>“lift up mine eyes”</em> (= look "
        f"{ch.cite('Psalms', 121, 1, '“Lift up mine eyes” = look up.', expect='lift up mine eyes')}), <em>“before the face of”</em> "
        f"(= in front of), <em>“by the hand of”</em> (= through)."
    )
    return ch.build()


def _build_chapter_8_verses_unlocked(corpus: ScriptureCorpusLookup) -> Chapter:
    ch = ChapterDraft(
        chapter_id="ch-8-verses-unlocked",
        number=8,
        title="Chapter 8: Crucial Verses Unlocked",
        subtitle="Six Passages Where Knowing Early Modern English Changes the Meaning",
        headnote="See how a single pronoun, verb, or false friend transforms a familiar verse.",
        corpus=corpus,
    )

    ch.subheading("1. Luke 22:31–32 — Satan Wants All of You; I Prayed for You, Peter")
    ch.para(
        f"<em>“Satan hath desired to have <strong>you</strong>... But I have prayed for <strong>thee</strong>, "
        f"that <strong>thy</strong> faith fail not.”</em> "
        f"{ch.cite('Luke', 22, 31, 'Plural “you” = all the apostles.', expect='desired to have you')}"
        f"{ch.cite('Luke', 22, 32, 'Singular “thee” and “thy” = Peter alone.', expect='prayed for thee, that thy faith fail not')}"
    )
    ch.para(
        "<strong>Why it matters:</strong> Modern English flattens both into “you,” hiding the contrast. Jesus "
        "warns Simon Peter that Satan has asked to sift <em>all the apostles</em>—and then reassures Peter "
        "personally (<em>thee</em>) that he has prayed for Peter’s faith so Peter can strengthen the rest."
    )

    ch.subheading("2. John 5:40 — Refusal, Not a Prediction")
    ch.para(
        f"<em>“And ye <strong>will not</strong> come to me, that ye might have life.”</em> "
        f"{ch.cite('John', 5, 40, '“Will not” = are unwilling to.', expect='ye will not come to me')}"
    )
    ch.para(
        "<strong>Why it matters:</strong> Jesus is not predicting the future (“you won’t come”). Here "
        "<em>will</em> carries its root sense of <em>desire/choose</em>, matching the Greek <em>ou thelete</em> "
        "(“you are not willing”). He is diagnosing their choice: "
        "“You <em>refuse</em> / are <em>unwilling</em> to come to me.”"
    )

    ch.subheading("3. Matthew 6:25 & Philippians 4:6 — Anxiety, Not Irresponsibility")
    ch.para(
        f"<em>“<strong>Take no thought</strong> for your life”</em> "
        f"{ch.cite('Matthew', 6, 25, '“Thought” = anxious worry.', expect='Take no thought for your life')} and <em>“Be <strong>careful</strong> "
        f"for nothing”</em> {ch.cite('Philippians', 4, 6, '“Careful” = full of anxiety.', expect='Be careful for nothing')}."
    )
    ch.para(
        "<strong>Why it matters:</strong> Neither Jesus nor Paul is commanding recklessness or forbidding "
        "planning. Both <em>thought</em> and <em>careful</em> meant “consumed by anxious worry.” Read both "
        "as: “Do not be anxious about your life” and “Do not worry about anything.”"
    )

    ch.subheading("4. 1 Nephi 11:16, 26 — The Condescension of God")
    ch.para(
        f"<em>“Knowest thou the <strong>condescension</strong> of God?”</em> "
        f"{ch.cite('1 Nephi', 11, 16, 'Voluntary, loving descent from heaven to earth.', expect='Knowest thou the condescension of God')}"
        f"{ch.cite('1 Nephi', 11, 26, 'Points directly to the birth and ministry of Christ.', expect='condescension of God')}"
    )
    ch.para(
        "<strong>Why it matters:</strong> Today, “condescending” means talking down to someone with arrogance. "
        "In earlier English, <em>condescension</em> was a virtue: a royal or divine figure <em>voluntarily "
        "stepping down</em> in grace and love to meet others on their level. Both senses involve a superior "
        "lowering himself; what changed is whether we hear it as gracious or as patronizing."
    )

    ch.subheading("5. 1 Thessalonians 4:15 & 2 Thessalonians 2:7 — ‘Prevent’ and ‘Let’")
    ch.para(
        f"<em>“We which are alive... shall not <strong>prevent</strong> them which are asleep”</em> "
        f"{ch.cite('1 Thessalonians', 4, 15, '“Prevent” = precede, go ahead of.', expect='shall not prevent them which are asleep')} and "
        f"<em>“only he who now <strong>letteth</strong> will <strong>let</strong>”</em> "
        f"{ch.cite('2 Thessalonians', 2, 7, '“Let” = restrain, hinder.', expect='only he who now letteth will let')}."
    )
    ch.para(
        "<strong>Why it matters:</strong> Both words flipped nearly 180 degrees. In 1 Thessalonians, the "
        "living will not <em>precede</em> (go ahead of) the resurrected dead. In 2 Thessalonians, the one who "
        "<em>restrains</em> lawlessness will continue to <em>hold it back</em> until he is removed."
    )

    ch.subheading("6. Doctrine and Covenants 121:43 — Reproving ‘Betimes’")
    ch.para(
        f"<em>“Reproving <strong>betimes</strong> with sharpness, when moved upon by the Holy Ghost...”</em> "
        f"{ch.cite('D&C', 121, 43, '“Betimes” = early, promptly, in good time.', expect='Reproving betimes with sharpness, when moved upon by the Holy Ghost')}"
    )
    ch.para(
        "<strong>Why it matters:</strong> Many readers hear <em>betimes</em> as “sometimes” or “occasionally.” "
        "In Early Modern English, <em>betimes</em> means <strong>early, promptly, before a problem grows</strong> "
        "(from <em>by time</em>). Many teachers also read “sharpness” as clarity and precision rather than "
        "harshness. That is an interpretation rather than a dictionary definition, but it fits the verse’s "
        "call to follow the reproof with “an increase of love.”"
    )
    return ch.build()


def _build_chapter_9_cheat_sheet(corpus: ScriptureCorpusLookup) -> Chapter:
    ch = ChapterDraft(
        chapter_id="ch-9-cheat-sheet",
        number=9,
        title="Chapter 9: Quick-Reference Cheat Sheet",
        subtitle="One-Page Tables for Reading Beside Your Scriptures",
        headnote="Keep these four compact tables handy whenever a verse feels tangled.",
        corpus=corpus,
    )

    ch.subheading("Pronouns at a Glance")
    ch.table(
        headers=["", "Subject", "Object", "Possessive"],
        rows=[
            ["<strong>One person</strong>", "<em>thou</em>", "<em>thee</em>", "<em>thy</em> (<em>thine</em> before a vowel; standalone <em>thine</em>)"],
            ["<strong>Two or more</strong>", "<em>ye</em>", "<em>you</em>", "<em>your / yours</em>"],
        ],
    )

    ch.subheading("Verb Signals at a Glance")
    ch.table(
        headers=["Form", "Meaning / Signal"],
        rows=[
            ["<em>-est / -st</em> on a verb", "Matches <em>thou</em> (singular you)"],
            ["<em>-eth / -th</em>", "Matches <em>he / she / it</em> (singular third person)"],
            ["Bare verb (<em>if thou be</em>)", "Subjunctive: condition, wish, or uncertainty"],
            ["<em>is risen / am come</em>", "Present resulting state (“is here now”)"],
            ["<em>wilt / will not</em>", "Often desire or willingness (“want to / refuse to”), not just future tense"],
            ["<em>wherefore?</em>", "Why?"],
        ],
    )

    ch.subheading("Directionals at a Glance")
    ch.table(
        headers=["At", "To", "From"],
        rows=[
            ["<em>here</em>", "<em>hither</em>", "<em>hence</em>"],
            ["<em>there</em>", "<em>thither</em>", "<em>thence</em>"],
            ["<em>where</em>", "<em>whither</em>", "<em>whence</em>"],
        ],
    )

    ch.subheading("Top 12 False Friends")
    ch.table(
        headers=["Word", "Means", "Word", "Means"],
        rows=[
            ["<em>suffer</em>", "allow", "<em>peculiar</em>", "treasured, own"],
            ["<em>let</em> (sometimes)", "hinder, stop", "<em>quick / quicken</em>", "alive / make alive"],
            ["<em>prevent</em>", "go before, precede", "<em>tempt</em>", "test, prove"],
            ["<em>conversation</em>", "conduct, way of life", "<em>careful / thought</em>", "anxious / worry"],
            ["<em>condescension</em>", "gracious descent", "<em>betimes</em>", "promptly, early"],
            ["<em>charity</em>", "pure divine love", "<em>by and by / anon</em>", "immediately"],
        ],
    )
    return ch.build()


def ingest_early_modern_english_guide() -> Work:
    """Compile the concise 9-Chapter Early Modern English Scriptural Guide into a normalized `Work`."""
    corpus = ScriptureCorpusLookup()
    front_matter = _build_front_matter(corpus)
    chapters = [
        _build_chapter_1_pronouns(corpus),
        _build_chapter_2_verbs(corpus),
        _build_chapter_3_directionals(corpus),
        _build_chapter_4_vernacular_connectors(corpus),
        _build_chapter_5_syntax(corpus),
        _build_chapter_6_false_friends(corpus),
        _build_chapter_7_hebraisms(corpus),
        _build_chapter_8_verses_unlocked(corpus),
        _build_chapter_9_cheat_sheet(corpus),
    ]

    book = Book(
        id="early-modern-english-guide",
        title="Early Modern English Guide to the Scriptures",
        full_title="An Early Modern English Guide to Reading the Scriptures",
        subtitle="Pronouns, Verbs, Directionals, False Friends & Crucial Verses Unlocked",
        chapters=chapters,
    )

    return Work(
        id="early-modern-english-scripture-guide",
        title="Early Modern English Guide to the Scriptures",
        subtitle="A Concise Reader’s Companion to the Language of the KJV & Restoration Scripture",
        authors=["Proteus Scriptorium Press"],
        edition_label="Proteus Reader’s Edition",
        description=(
            "A concise, example-driven 9-chapter guide to Early Modern English in the scriptures: "
            "pronouns (thou/thee vs. ye/you), verb endings and moods, spatial directionals "
            "(hither/thither/whither/hence), everyday vernacular (twain, asunder, sundry), "
            "high-impact false friends, Hebrew idioms, and crucial verses unlocked—with clickable "
            "pop-up scripture citations."
        ),
        subjects=[
            "English language — Early modern, 1500-1700 — Grammar",
            "Bible. English — Authorized — Language, style",
            "Book of Mormon — Language, style",
        ],
        front_matter=front_matter,
        books=[book],
        css_theme="classic.css",
    )


build_early_modern_english_scripture_guide = ingest_early_modern_english_guide
