"""Early Modern English in Scripture — Comprehensive Philological & Grammatical Reference Guide (`early_modern_english.py`).

Compiles a 6-Division (6-Book) interactive EPUB3 study manual covering:
1. Book I: The Pronoun System, Case Grammar & the T–V Distinction
2. Book II: Verbal Morphology, Inflectional Suffixes, Aspect & Mood
3. Book III: Syntax, Clause Architecture & Early Modern Grammar
4. Book IV: The Lexical Glossary of "False Friends" & Archaic Terminology
5. Book V: Structural Semitic Calques & Hebraisms in Scriptural English (KJV & Book of Mormon)
6. Book VI: Practical Reference Matrices & Annotated Passage Walkthroughs

Every scriptural illustration and lexical entry is dynamically linked to native Kindle pop-up
footnotes (`<a epub:type="noteref">` -> `<aside epub:type="footnote">`) displaying verbatim
verses from the 2013 Standard Works and the 1830 Palmyra Book of Mormon corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

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
from proteus.ingest.standard_works import ingest_bom_historical_edition, ingest_standard_work


class ScriptureCorpusLookup:
    """Fast in-memory lookup of verbatim canonical verses (and 1830 BoM readings) for pop-up footnotes."""

    def __init__(self) -> None:
        self.verses_2013: dict[str, tuple[str, str]] = {}
        self.verses_1830: dict[str, str] = {}
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
                for bk in work.books:
                    for ch in bk.chapters:
                        for v in ch.verses:
                            if v.canonical_ref:
                                self.verses_2013[v.canonical_ref] = (v.citation_label or v.canonical_ref, v.text)
            except Exception:
                pass

        try:
            bom_1830 = ingest_bom_historical_edition("1830")
            for bk in bom_1830.books:
                for ch in bk.chapters:
                    for v in ch.verses:
                        if v.canonical_ref:
                            self.verses_1830[v.canonical_ref] = v.text
        except Exception:
            pass

    def get_popup_paragraphs(
        self,
        book: str,
        chapter: int,
        verse: int,
        gloss: str,
        include_1830: bool = False,
    ) -> tuple[str, list[str]]:
        ref = make_canonical_ref(book, chapter, verse)
        label, text_2013 = self.verses_2013.get(ref, (f"{book} {chapter}:{verse}", ""))
        paras: list[str] = []
        if text_2013:
            paras.append(f"“{text_2013}” ({label})")
        if include_1830 and ref in self.verses_1830:
            t_1830 = self.verses_1830[ref]
            if t_1830 and t_1830 != text_2013:
                paras.append(f"1830 Palmyra Reading: “{t_1830}”")
        if gloss:
            paras.append(f"Linguistic Note: {gloss}")
        if not paras:
            paras.append(gloss or label)
        return label, paras


class ChapterDraft:
    """Helper builder that accumulates prose, tables, callouts, and bidirectional Kindle pop-up footnotes."""

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
        gloss: str,
        include_1830: bool = False,
        display_label: str | None = None,
    ) -> str:
        """Create an `<a epub:type="noteref">` callout and register its corresponding `<aside epub:type="footnote">`."""
        self._fn_counter += 1
        ann_id = f"{self.chapter_id}-fn-{self._fn_counter}"
        cite_title, paras = self.corpus.get_popup_paragraphs(
            book=book,
            chapter=chapter,
            verse=verse,
            gloss=gloss,
            include_1830=include_1830,
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

    def note(self, title: str, body: str, badge: str | None = None) -> str:
        """Create a philological or historical pop-up footnote."""
        self._fn_counter += 1
        ann_id = f"{self.chapter_id}-fn-{self._fn_counter}"
        lbl = badge or str(self._fn_counter)
        ann = Annotation(
            id=ann_id,
            label=str(self._fn_counter),
            note_type=AnnotationType.FOOTNOTE,
            title=title,
            paragraphs=[clean_prose_text(body)],
        )
        self.annotations.append(ann)
        return (
            f'<sup class="fn-sup"><a class="noteref" epub:type="noteref" '
            f'id="ref-{ann_id}" href="#fn-{ann_id}">[{escape_xhtml(lbl)}]</a></sup>'
        )

    def subheading(self, text: str) -> None:
        self.blocks.append(ContentBlock(block_type=BlockType.SUBHEADING, text=text, level=3))

    def para(self, html_or_text: str, plain_fallback: str | None = None) -> None:
        plain = plain_fallback if plain_fallback is not None else _strip_tags(html_or_text)
        self.blocks.append(
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=clean_prose_text(plain),
                html_text=html_or_text,
            )
        )

    def callout(self, title: str, paragraphs_html: list[str]) -> None:
        inner = f"<p><strong>{escape_xhtml(title)}</strong></p>" + "".join(f"<p>{p}</p>" for p in paragraphs_html)
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
    import re
    return re.sub(r"<[^>]+>", "", html)


def _build_front_matter(corpus: ScriptureCorpusLookup) -> list[Chapter]:
    d = ChapterDraft(
        chapter_id="eme-guide-preface",
        title="Editorial Preface: Why Early Modern English Matters for Scripture Study",
        subtitle="Unlocking the Linguistic Architecture of the 1611 King James Bible and the 1830 Book of Mormon",
        headnote=(
            "Early Modern English (c. 1500–1700) forms the grammatical, lexical, and rhetorical bedrock of the "
            "Authorized King James Version of the Bible (1611) as well as the Restoration scriptures—most notably "
            "the 1830 Book of Mormon, the Doctrine and Covenants, and the Pearl of Great Price."
        ),
        corpus=corpus,
        is_front_matter=True,
    )

    c_luke = d.cite(
        "Luke",
        22,
        31,
        "Jesus addresses all the Apostles collectively using plural ‘you’ (‘Satan hath desired to have you, that he may sift you as wheat’), then immediately shifts in v. 32 to singular ‘thee/thy’ (‘But I have prayed for thee, that thy faith fail not’) to address Simon Peter individually.",
    )
    c_1thes = d.cite(
        "1 Thessalonians",
        4,
        15,
        "In 1611 English, ‘prevent’ (from Latin praevenire, ‘to come before’) meant ‘to precede’ or ‘go ahead of,’ not ‘to hinder or stop.’ Paul reassures believers that the living will not precede the resurrected dead.",
    )
    c_1ne = d.cite(
        "1 Nephi",
        11,
        16,
        "In Early Modern English, ‘condescension’ carried zero modern connotation of haughty superiority; it meant the voluntary, gracious descent of a divine being from heavenly majesty to dwell among and redeem mortal humanity.",
        include_1830=True,
    )

    d.para(
        "Early Modern English (EME) forms the linguistic bedrock of early English scripture translations—most "
        "notably William Tyndale’s New Testament (1526), the Geneva Bible (1560), and the 1611 Authorized King "
        "James Version (KJV)—as well as the 1830 Book of Mormon, which preserves and deploys this rich liturgical "
        "and philological register. Yet four centuries of continuous linguistic evolution have opened a silent "
        "chasm between the original meaning of scriptural words and the assumptions of twenty-first-century readers."
    )
    d.para(
        "When a language changes completely, readers know they must use a dictionary or translation. The peculiar "
        "hazard of Early Modern English is that it looks deceptively familiar. Modern readers recognize the "
        "spelling of words like <em>wherefore</em>, <em>suffer</em>, <em>prevent</em>, <em>conversation</em>, "
        "<em>careful</em>, <em>peculiar</em>, <em>meat</em>, <em>halt</em>, <em>pitiful</em>, <em>vile</em>, and "
        f"<em>condescension</em> {c_1ne}, or grammatical forms like <em>thou art</em>, <em>ye are</em>, "
        f"<em>he is come</em>, and <em>they did travel</em>, and unconsciously supply modern definitions and "
        f"modern pragmatics. The result is widespread, systematic misreading {c_luke} {c_1thes}."
    )
    d.callout(
        "How to Use This Interactive Kindle Reference Edition",
        [
            "1. <strong>Division-by-Division Grammatical Reference (Books I–III):</strong> Master the pronoun system and the sociolinguistic T–V distinction (<em>thou/thee</em> vs. <em>ye/you</em>), verbal morphology (<em>-est</em>, <em>-eth</em>, subjunctive mood, and <em>be</em>-perfects of motion), and clause syntax (human <em>which</em>, contact clauses, flat adverbs, and unemphatic periphrastic <em>do</em>).",
            "2. <strong>Comprehensive Lexical Glossary of “False Friends” (Book IV):</strong> Look up over 110 high-frequency scriptural words whose meanings have shifted, inverted, or narrowed since the 16th and 17th centuries.",
            "3. <strong>Structural Semitic Calques &amp; Hebraisms (Book V):</strong> Understand how Northwest Semitic (Biblical Hebrew) syntax—construct chains (<em>plates of brass</em>), narrative <em>wayəhî</em> (<em>and it came to pass</em>), cognate accusatives (<em>dreamed a dream</em>), and abstract plurals—shapes both the KJV and the Book of Mormon.",
            "4. <strong>Interactive Pop-Up Scripture Citations:</strong> Tap any bracketed scripture badge (such as <strong>[Luke 22:31]</strong> or <strong>[1 Nephi 11:16]</strong>) on your Kindle Paperwhite to open an instant modal pop-up containing the verbatim canonical verse, historical 1830 Palmyra comparisons where relevant, and a targeted philological commentary.",
        ],
    )
    return [d.build()]


def _build_book_1_pronouns(corpus: ScriptureCorpusLookup) -> Book:
    chapters: list[Chapter] = []

    # --- CHAPTER 1: THE GRAMMATICAL PARADIGM ---
    c1 = ChapterDraft(
        chapter_id="eme-bk1-ch1",
        number=1,
        title="Chapter 1: The Second-Person Pronoun Paradigm (Number & Case)",
        subtitle="Distinguishing Singular (Thou/Thee/Thy/Thine) from Plural (Ye/You/Your/Yours)",
        headnote=(
            "In Contemporary English, the single word ‘you’ performs six different grammatical jobs: singular subject, "
            "singular object, plural subject, plural object, formal address, and informal address. Early Modern English "
            "maintained strict morphological boundaries across both number and grammatical case."
        ),
        corpus=corpus,
    )

    c1.para(
        "The most widespread misunderstanding in scriptural reading involves second-person pronouns. Modern readers "
        "frequently interpret <em>thou</em>, <em>thee</em>, and <em>thine</em> as elevated, hyper-formal, or regal "
        "vocabulary reserved exclusively for God, while treating <em>ye</em> as a generic archaic synonym for singular "
        "<em>you</em>. Historically and grammatically, both assumptions are false."
    )
    c1.subheading("The Complete Early Modern English Pronoun Paradigm")
    c1.para(
        "In Early Modern English, the second-person pronoun system preserved strict distinctions between grammatical "
        "number (<strong>singular</strong>—addressing exactly one individual—versus <strong>plural</strong>—addressing "
        "two or more individuals) and grammatical case (<strong>nominative subject</strong> versus "
        "<strong>accusative/dative object</strong>):"
    )
    c1.table(
        headers=[
            "Person &amp; Number",
            "Subject (Nominative)",
            "Object (Accusative / Dative)",
            "Possessive Determiner (Genitive)",
            "Possessive Absolute (Independent)",
            "Reflexive",
        ],
        rows=[
            [
                "<strong>2nd Person Singular</strong> (One person)",
                "<strong>Thou</strong><br/>(<em>“Thou art…”</em>)",
                "<strong>Thee</strong><br/>(<em>“I give thee…”</em>)",
                "<strong>Thy / Thine</strong><br/>(<em>“Thy word / Thine eye”</em>)",
                "<strong>Thine</strong><br/>(<em>“It is thine”</em>)",
                "<strong>Thyself</strong><br/>(archaic <em>Theeself</em>)",
            ],
            [
                "<strong>2nd Person Plural</strong> (Multiple people)",
                "<strong>Ye</strong><br/>(<em>“Ye are…”</em>)",
                "<strong>You</strong><br/>(<em>“I say unto you…”</em>)",
                "<strong>Your</strong><br/>(<em>“Your fathers”</em>)",
                "<strong>Yours</strong><br/>(<em>“It is yours”</em>)",
                "<strong>Yourselves</strong>",
            ],
        ],
    )

    fn_matt5 = c1.cite(
        "Matthew",
        5,
        14,
        "‘Ye’ is the nominative plural subject addressing the multitude of disciples on the mount: ‘All of you together are the light of the world.’",
    )
    fn_john3 = c1.cite(
        "John",
        3,
        7,
        "Jesus speaks to one man at night (‘Marvel not that I said unto thee [singular object: Nicodemus alone]’), and then states a universal covenant requirement for all humanity (‘Ye [plural subject: all of you] must be born again’).",
    )
    fn_luke22_31 = c1.cite(
        "Luke",
        22,
        31,
        "Plural object ‘you’ twice: Satan has desired to have all twelve Apostles (‘you’) to sift them as wheat.",
    )
    fn_luke22_32 = c1.cite(
        "Luke",
        22,
        32,
        "Immediate shift to singular ‘thee’ and ‘thy’: Jesus has prayed specifically for Simon Peter (‘thee’) so that Peter’s individual faith (‘thy faith’) will not fail.",
    )
    fn_exod4 = c1.cite(
        "Exodus",
        4,
        15,
        "Speaking to Moses alone: ‘Thou shalt speak unto him, and put words in his mouth: and I will be with thy mouth, and with his mouth, and will teach you [plural object: both Moses and Aaron] what ye [plural subject: both of you] shall do.’",
    )

    c1.subheading("Case Division: Nominative Subject vs. Objective Complement")
    c1.para(
        "Just as modern English still distinguishes between <em>I</em> (subject: <em>“I saw him”</em>) and <em>me</em> "
        "(object: <em>“He saw me”</em>), or between <em>he/him</em>, <em>she/her</em>, and <em>they/them</em>, "
        "scriptural Early Modern English strictly enforces case on second-person pronouns:"
    )
    c1.callout(
        "The Easy Mnemonic Rule: The ‘T / Y’ Subject–Object Test",
        [
            "• <strong>Singular:</strong> <strong>Thou</strong> is the <em>Subject</em> (the one doing the action, like <em>I / he / she</em>). <strong>Thee</strong> is the <em>Object</em> (the one receiving the action or following a preposition like <em>unto, with, for, in, against</em>, like <em>me / him / her</em>).",
            "• <strong>Plural:</strong> <strong>Ye</strong> is the <em>Subject</em> (like <em>we / they</em>: <em>“Ye are the light of the world”</em> "
            f"{fn_matt5}). <strong>You</strong> is the <em>Object</em> (like <em>us / them</em>: <em>“I speak unto you”</em>).",
            "• <strong>Note on Historical Case Drift:</strong> In early Tudor English, <em>ye</em> was strictly the nominative plural subject and <em>you</em> was strictly the objective plural. By the late 16th and early 17th centuries, <em>you</em> began displacing <em>ye</em> in the subject position in colloquial London speech (and frequently in Shakespeare’s plays), but the 1611 King James translators rigorously maintained the classical grammatical division: <em>ye</em> for subjects, <em>you</em> for objects.",
        ],
    )

    c1.subheading("Why the Singular vs. Plural Distinction Changes Exegesis")
    c1.para(
        "Because Contemporary English collapsed <em>thou</em>, <em>thee</em>, <em>ye</em>, and <em>you</em> into the "
        "single word <em>you</em>, modern readers (and modern Bible translations that render everything as <em>you</em>) "
        "routinely miss crucial exegetical turning points where a speaker shifts between addressing an individual and "
        "addressing a collective community:"
    )
    c1.para(
        f"1. <strong>Jesus and Nicodemus ({fn_john3}):</strong> When Jesus tells Nicodemus, <em>“Marvel not that I said "
        "unto <strong>thee</strong>, <strong>Ye</strong> must be born again,”</em> the pronoun shift carries the entire "
        "theological point. Nicodemus is addressed individually as <em>thee</em>, but the imperative to be born from "
        "above is given in the plural (<em>Ye</em>)—encompassing the entire Pharisaic Sanhedrin and all Israel."
    )
    c1.para(
        f"2. <strong>The Sifting of the Twelve vs. The Prayer for Peter ({fn_luke22_31} {fn_luke22_32}):</strong> At "
        "the Last Supper, the Lord says, <em>“Simon, Simon, behold, Satan hath desired to have <strong>you</strong> "
        "[plural: all twelve apostles], that he may sift <strong>you</strong> [plural] as wheat: But I have prayed for "
        "<strong>thee</strong> [singular: Peter alone], that <strong>thy</strong> [singular] faith fail not: and when "
        "<strong>thou</strong> [singular] art converted, strengthen <strong>thy</strong> brethren.”</em> Without the "
        "EME distinction between plural <em>you</em> and singular <em>thee/thy/thou</em>, a reader cannot tell that "
        "Satan’s attack targeted the entire Quorum while Christ’s intercessory prayer focused specifically on Peter’s "
        "upcoming denial and leadership."
    )
    c1.para(
        f"3. <strong>Moses and Aaron Commissioned Together ({fn_exod4}):</strong> Within a single verse, the Lord "
        "shifts seamlessly from singular <em>thou/thy</em> (Moses alone) to plural <em>you/ye</em> (Moses and Aaron "
        "together): <em>“<strong>Thou</strong> shalt speak unto him… and I will be with <strong>thy</strong> mouth, "
        "and with his mouth, and will teach <strong>you</strong> [both of you] what <strong>ye</strong> [both of you] "
        "shall do.”</em>"
    )
    chapters.append(c1.build())

    # --- CHAPTER 2: THE SOCIOLINGUISTIC REALITY: THE T-V DISTINCTION ---
    c2 = ChapterDraft(
        chapter_id="eme-bk1-ch2",
        number=2,
        title="Chapter 2: Sociolinguistics of the T–V Distinction & Why ‘Thou’ Addresses God",
        subtitle="Covenantal Intimacy, Monotheistic Singular Fidelity, and the Inversion of Modern Assumptions",
        headnote=(
            "Why do scriptural translators address the Almighty as ‘Thou’ rather than ‘You’? Not to make God sound "
            "distant, aristocratic, or courtly—but because ‘thou’ was the grammatical singular of direct, familial intimacy."
        ),
        corpus=corpus,
    )

    c2.para(
        "Beginning in the Middle English period (c. 1250–1450) under the heavy sociolinguistic influence of Norman "
        "French—which contrasted familiar singular <em>tu</em> with formal/plural <em>vous</em> (the linguistic "
        "<strong>T–V distinction</strong>, named after Latin <em>tu</em> and <em>vos</em>)—spoken English developed "
        "a two-tiered social etiquette for addressing a single person:"
    )
    c2.table(
        headers=["Register Tier", "Pronouns Used", "Historical Sociolinguistic Function (c. 1300–1650)"],
        rows=[
            [
                "<strong>The T-Form</strong><br/>(Familiar / Singular)",
                "<em>Thou / Thee / Thy / Thine</em>",
                "Marked singular intimacy, close family affection, spiritual communion, social equality among commoners, or downward condescension/anger from a social superior to an inferior (e.g., parent to child, master to servant, judge to prisoner).",
            ],
            [
                "<strong>The V-Form</strong><br/>(Deferential / Plural)",
                "<em>Ye / You / Your / Yours</em>",
                "Marked plurality (more than one person), OR formal respect, courtly deference, polite distance, and social elevation when addressing a monarch, nobleman, parent, or stranger.",
            ],
        ],
    )

    coke_note = c2.note(
        "Sir Edward Coke’s 1603 Prosecution of Sir Walter Raleigh",
        "During the treason trial of Sir Walter Raleigh at Winchester Castle on November 17, 1603, Attorney General Sir Edward Coke deliberately dropped the polite courtly ‘you’ and weaponized the singular ‘thou’ as an explicit verbal degradation, coining the verb ‘to thou’: “All that he did was by thy instigation, thou viper; for I thou thee, thou traitor!” Shakespeare dramatizes this exact sociolinguistic rule in Twelfth Night (Act 3, Scene 2), where Sir Toby Belch advises Sir Andrew Aguecheek to provoke a duel by writing a challenge letter that calls his opponent ‘thou’: “If thou thou’st him some thrice, it shall not be amiss.”",
        badge="Historical Trial Note",
    )

    c2.para(
        "In Elizabethan and Jacobean society (the exact historical milieu of the 1611 King James translators), "
        "addressing a social superior—or even an equal gentleman outside one’s intimate circle—with singular "
        "<em>thou</em> was considered a calculated, provocative insult. This is famously illustrated in Attorney "
        "General Sir Edward Coke’s 1603 prosecution of Sir Walter Raleigh: <em>“All that he did was by <strong>thy</strong> "
        "instigation, <strong>thou</strong> viper; for I <strong>thou thee</strong>, <strong>thou</strong> traitor!”</em> "
        f"{coke_note}"
    )

    c2.subheading("Why Is ‘Thou’ Used for God in Scripture?")
    c2.para(
        "Crucially, scriptural English does <strong>not</strong> use the Norman French courtly T–V etiquette! In the "
        "King James Bible and the Book of Mormon, a servant addresses a king as <em>thou</em>, a child addresses a "
        "father as <em>thou</em>, and a mortal addresses God as <em>thou</em>. William Tyndale (1526), Miles Coverdale "
        "(1535), and the King James translators (1611) rejected courtly <em>you</em> for one-on-one address for two "
        "vital philological and theological reasons:"
    )

    fn_deut6 = c2.cite(
        "Deuteronomy",
        6,
        4,
        "The Shema (‘Hear, O Israel: The Lord our God is one Lord’) establishes the strict grammatical singularity of God in Hebrew biblical syntax.",
    )
    fn_matt6_9 = c2.cite(
        "Matthew",
        6,
        9,
        "In the Lord’s Prayer, Jesus instructs disciples to address the Father in the intimate, familial second-person singular (‘Our Father which art in heaven, Hallowed be thy name’), translating Koine Greek singular sou (‘thy’) rather than plural hymōn.",
    )

    c2.callout(
        "Two Foundational Reasons Scriptural Translators Chose ‘Thou’ for Deity",
        [
            f"1. <strong>Linguistic &amp; Theological Fidelity (Grammatical Singular):</strong> Both Biblical Hebrew (<em>’attāh</em>, אַתָּה) and Koine Greek (<em>sý</em>, σύ) possess strictly distinct singular and plural second-person pronouns—and neither ancient language ever used a plural pronoun as a polite singular honorific! When Tyndale and the 1611 scholars translated the Bible, their supreme rule was morphological accuracy: Hebrew and Greek singulars <strong>must</strong> be rendered with English singulars (<em>thou/thee/thy</em>), and Hebrew and Greek plurals <strong>must</strong> be rendered with English plurals (<em>ye/you/your</em>). To address God with plural <em>ye/you</em> would falsify the underlying ancient text and obscure the foundational monotheistic witness that God is an individual Person {fn_deut6}.",
            f"2. <strong>Covenantal Intimacy &amp; Familial Communion:</strong> In Early Modern English, the T-form (<em>thou/thee</em>) was the language of the hearth, the marriage covenant, and the bond between parent and child. Addressing God as <em>thou</em> {fn_matt6_9} placed the worshipper in the position of a beloved child speaking directly to an accessible, loving Father—rather than a distant subject petitioning an aloof earthly monarch through bureaucratic court etiquette.",
        ],
    )
    c2.para(
        "When modern worshippers use <em>thou</em>, <em>thee</em>, and <em>thy</em> under the impression that they "
        "are employing an ornate, aristocratic, or courtly title of distance, they completely invert the historical "
        "linguistics: <strong><em>thou</em> was chosen specifically because it was singular, direct, personal, and "
        "intimately familial.</strong> Only much later—after <em>thou</em> vanished from everyday 18th- and 19th-century "
        "street conversation while surviving in liturgy and scripture—did English speakers retroactively reassociate "
        "<em>thou</em> with solemn reverence."
    )
    chapters.append(c2.build())

    # --- CHAPTER 3: PHONOLOGICAL RULE: THY VS THINE & MY VS MINE ---
    c3 = ChapterDraft(
        chapter_id="eme-bk1-ch3",
        number=3,
        title="Chapter 3: The Phonological Rule — ‘Thy’ vs. ‘Thine’ and ‘My’ vs. ‘Mine’",
        subtitle="Prevocalic Euphony vs. Independent Possessive Pronouns",
        headnote=(
            "Why do the scriptures say ‘thy faith’ and ‘my servant,’ but ‘thine eye,’ ‘thine heart,’ and ‘mine iniquity’? "
            "The choice is governed by the exact same phonetic rule as modern ‘a’ versus ‘an.’"
        ),
        corpus=corpus,
    )

    fn_matt6_22 = c3.cite(
        "Matthew",
        6,
        22,
        "Notice ‘thine eye’ (before vowel sound) and ‘thy whole body’ (before consonant sound /h/ in ‘whole’, pronounced /w/ or aspirated) in the exact same sentence!",
    )
    fn_prov3_5 = c3.cite(
        "Proverbs",
        3,
        5,
        "‘Trust in the Lord with all thine heart; and lean not unto thine own understanding.’ Both ‘heart’ (weak/unaspirated h in EME) and ‘own’ (vowel) trigger prevocalic ‘thine’.",
    )
    fn_ps23 = c3.cite(
        "Psalms",
        23,
        5,
        "‘Thou preparest a table before me in the presence of mine enemies: thou anointest my head with oil; my cup runneth over.’ Observe ‘mine enemies’ (before vowel) right beside ‘my head’ and ‘my cup’ (before consonants)!",
    )
    fn_john17_10 = c3.cite(
        "John",
        17,
        10,
        "Independent (predicative/absolute) possessive usage: ‘And all mine are thine, and thine are mine; and I am glorified in them.’",
    )
    fn_mosiah4_16 = c3.cite(
        "Mosiah",
        4,
        16,
        "King Benjamin’s speech preserves prevocalic ‘thine’ and ‘mine’: ‘ye will not suffer that the beggar putteth up his petition to you in vain, and turn him out to perish.’ Compare Mosiah 4:11–12 and Enos 1:4 (‘my soul hungered… before my Maker… in mighty prayer and supplication for mine own soul’).",
        include_1830=True,
    )

    c3.para(
        "Many readers assume that <em>thine</em> and <em>mine</em> are only used as standalone pronouns at the end of "
        "a clause (as in modern English <em>“The book is mine”</em>), and feel puzzled when they encounter phrases "
        "like <em>“thine eyes,”</em> <em>“thine heart,”</em> or <em>“mine enemies”</em> directly in front of a noun. "
        "In fact, <em>mine</em> (Old English <em>mīn</em>) and <em>thine</em> (Old English <em>þīn</em>) were the "
        "original historic forms! During the Middle English period, the final <em>-n</em> dropped off before words "
        "beginning with a consonant sound, producing <em>my</em> and <em>thy</em>—in the exact same way that the "
        "indefinite article <em>an</em> shortened to <em>a</em> before consonants."
    )
    c3.table(
        headers=[
            "Phonological Environment",
            "1st Person Singular",
            "2nd Person Singular",
            "Canonical Scriptural Examples",
        ],
        rows=[
            [
                "<strong>1. Before a Consonant Sound</strong><br/>(Attributive Determiner)",
                "<strong>my</strong>",
                "<strong>thy</strong>",
                "<em>thy faith</em>, <em>thy brother</em>, <em>thy whole body</em>, <em>my servant</em>, <em>my people</em>, <em>my cup</em>",
            ],
            [
                "<strong>2. Before a Vowel Sound</strong><br/>(or silent / weak <em>h-</em>)",
                "<strong>mine</strong>",
                "<strong>thine</strong>",
                f"<em>thine eye</em> {fn_matt6_22}, <em>thine ear</em>, <em>thine inheritance</em>, <em>thine heart</em> {fn_prov3_5}, <em>thine honor</em>, <em>mine eyes</em>, <em>mine enemies</em> {fn_ps23}, <em>mine iniquity</em>, <em>mine own hand</em>, <em>mine house</em>",
            ],
            [
                "<strong>3. Independent / Predicative</strong><br/>(Standing alone without a following noun)",
                "<strong>mine</strong>",
                "<strong>thine</strong>",
                f"<em>“All things that the Father hath are <strong>mine</strong>”</em>; <em>“And all <strong>mine</strong> are <strong>thine</strong>, and <strong>thine</strong> are <strong>mine</strong>”</em> {fn_john17_10}; <em>“For <strong>thine</strong> is the kingdom”</em>",
            ],
        ],
    )
    c3.para(
        "Why does scriptural English frequently write <em>“thine heart,”</em> <em>“mine house,”</em> or <em>“thine "
        "hand”</em> when <em>heart</em>, <em>house</em>, and <em>hand</em> begin with the letter <em>h</em>? Because "
        "in 16th- and early 17th-century southern English, initial <em>h-</em> was weakly aspirated or silent in many "
        "unstressed prosodic environments (just as modern English still says <em>an hour</em>, <em>an heir</em>, and "
        "often <em>an historical</em>). Whenever the adjective <em>own</em> intervened between the possessive and a "
        "consonant-initial noun, the vowel of <em>own</em> immediately triggered <em>mine/thine</em>: hence "
        f"<em>“mine own soul”</em> and <em>“thine own understanding”</em> {fn_mosiah4_16}."
    )
    chapters.append(c3.build())

    # --- CHAPTER 4: PRONOMINAL DYNAMICS IN THE BOOK OF MORMON & D&C ---
    c4 = ChapterDraft(
        chapter_id="eme-bk1-ch4",
        number=4,
        title="Chapter 4: Pronominal Shifts & Discourse Register in the Book of Mormon",
        subtitle="How Singular/Plural Transitions Illumination Prophetic Dialogues in the 1830 & 2013 Text",
        headnote=(
            "The Book of Mormon frequently shifts between ‘ye/you’ and ‘thou/thee’ inside a single speech. Far from "
            "being grammatical errors, these shifts reflect classical rhetorical apostrophe, corporate-to-individual "
            "covenant accountability, and Hebraic enallage."
        ),
        corpus=corpus,
    )

    fn_mosiah12_27 = c4.cite(
        "Mosiah",
        12,
        27,
        "Abinadi addresses all the priests of King Noah using plural ‘ye’ (‘Ye have not applied your hearts to understand; therefore, ye have not been wise. Therefore, what teach ye this people?’).",
        include_1830=True,
    )
    fn_mosiah12_30 = c4.cite(
        "Mosiah",
        12,
        30,
        "Just three verses later, Abinadi pivots from plural ‘ye’ to singular ‘thou’ (‘Knowest thou not that I speak the truth?’) as he singles out the chief spokesman or King Noah personally, or addresses the priesthood collectively as a single corporate moral agent.",
        include_1830=True,
    )
    fn_alma32_27 = c4.cite(
        "Alma",
        32,
        27,
        "In Alma’s famous discourse on the seed of faith, he moves from addressing the Zoramite multitude in the plural (‘if ye will awake and arouse your faculties…’) to coaching the individual experimenter in the singular when describing the intimate interior sensation of spiritual growth.",
        include_1830=True,
    )
    fn_3ne11_14 = c4.cite(
        "3 Nephi",
        11,
        14,
        "At the Temple in Bountiful, the risen Christ addresses the 2,500 Nephites collectively with plural ‘ye/you’ (‘Arise and come forth unto me, that ye may thrust your hands into my side’), inviting each individual within the multitude to come forward one by one.",
        include_1830=True,
    )

    c4.para(
        "Attentive readers of the Book of Mormon often notice passages where a prophet addresses an audience using "
        "plural <em>ye/you/your</em> and then suddenly shifts to singular <em>thou/thee/thy</em>—or vice versa—within "
        "the same paragraph. Skeptical nineteenth-century critics sometimes dismissed these transitions as rural "
        "grammatical slips. However, modern historical linguistics and biblical philology demonstrate that this "
        "phenomenon—known in classical rhetoric and Hebrew grammar as <strong>pronominal <em>enallage</em></strong> "
        "(shifting grammatical number for rhetorical focus)—is a hallmark of both Deuteronomy and prophetic discourse."
    )
    c4.callout(
        "Three Exegetical Patterns of Pronoun Shifting in the Book of Mormon",
        [
            f"1. <strong>Crowd-to-Spokesman / Challenger Pivot ({fn_mosiah12_27} {fn_mosiah12_30}):</strong> During Abinadi’s trial before King Noah’s priests, Abinadi indicts the entire council in the plural: <em>“<strong>Ye</strong> have not applied <strong>your</strong> hearts to understand… Therefore, what teach <strong>ye</strong> this people?”</em> Moments later, when one priest challenges him or when he confronts the king directly, he narrows the beam to the singular: <em>“Knowest <strong>thou</strong> not that I speak the truth? Yea, <strong>thou</strong> knowest that I speak the truth; and <strong>you</strong> [plural: the whole court] ought to tremble before God.”</em>",
            f"2. <strong>Public Exhortation to Personal Spiritual Experiment ({fn_alma32_27}):</strong> In Alma 32–33, Alma addresses the poor Zoramites collectively as <em>ye/you</em> while inviting them to plant the word in their hearts, then shifts to singular <em>thou/thy</em> when describing the deeply personal, solitary act of nourishing the tree of faith and quoting Zenos’s intimate personal prayer (<em>“O God, <strong>thou</strong> art merciful…”</em>).",
            f"3. <strong>Deuteronomic Corporate Singular (Hebraic Enallage):</strong> In Biblical Hebrew (especially throughout Deuteronomy 4–28 and Isaiah), Moses and the prophets constantly alternate between addressing Israel as plural <em>‘attem</em> (<em>ye</em>—all the individual citizens) and singular <em>‘attāh</em> (<em>thou</em>—Israel personified as a single covenant bride or son) {fn_3ne11_14}. The Book of Mormon mirrors this exact Semitic oscillation between collective plurality and covenantal singularity.",
        ],
    )
    chapters.append(c4.build())

    return Book(
        id="book-1-pronoun-system",
        title="Book I: The Pronoun System & the T–V Distinction",
        full_title="Book I: The Second-Person Pronoun System, Case Grammar, Phonological Conditioning, and the Sociolinguistic T–V Distinction",
        subtitle="Thou, Thee, Thy, Thine, Ye, You, Your, Yours",
        chapters=chapters,
    )


def _build_book_2_verbs(corpus: ScriptureCorpusLookup) -> Book:
    chapters: list[Chapter] = []

    # --- CHAPTER 1: INFLECTIONAL SUFFIXES (-EST AND -ETH) ---
    c1 = ChapterDraft(
        chapter_id="eme-bk2-ch1",
        number=1,
        title="Chapter 1: Verbal Inflectional Suffixes (-est / -st and -eth / -th)",
        subtitle="Person-and-Number Agreement in the Present and Past Indicative",
        headnote=(
            "Early Modern English verbs carried explicit person-and-number endings that have largely vanished from "
            "modern English. Mastering ‘-est’ and ‘-eth’ makes complex scriptural sentences immediately transparent."
        ),
        corpus=corpus,
    )

    fn_john21_17 = c1.cite(
        "John",
        21,
        17,
        "Peter’s famous reply to the risen Lord stacks three 2nd-person singular ‘-est/-st’ verbs in a single breath: ‘Lord, thou knowest all things; thou knowest that I love thee.’ And in v. 18: ‘when thou wast young, thou girdedst thyself, and walkedst whither thou wouldest.’",
    )
    fn_1cor13_4 = c1.cite(
        "1 Corinthians",
        13,
        4,
        "Paul’s hymn to Charity uses a continuous chain of 3rd-person singular present indicative ‘-eth’ verbs (‘Charity suffereth long, and is kind; charity envieth not; charity vaunteth not itself…’) describing habitual, timeless present action.",
    )
    fn_mosiah2_21 = c1.cite(
        "Mosiah",
        2,
        21,
        "Note how ‘-eth’ attaches ONLY to 3rd-person singular subjects (‘God, who has created you, and has kept and preserved you… doth require that ye should do as he hath commanded you’), never to plural ‘ye’ or ‘they’ in standard EME.",
        include_1830=True,
    )

    c1.subheading("1. Second-Person Singular Agreement: -est / -st")
    c1.para(
        "Whenever <strong>thou</strong> functions as the grammatical subject of an indicative clause, the verb in the "
        "present tense—and, remarkably, in the <strong>past tense</strong> as well—takes the inflectional suffix "
        f"<strong>-est</strong> or <strong>-st</strong> {fn_john21_17}:"
    )
    c1.table(
        headers=["Tense &amp; Verb Class", "1st Person (I)", "2nd Person Singular (Thou)", "Modern Equivalent"],
        rows=[
            ["Present Regular", "I know / believe", "<strong>Thou knowest / believest</strong>", "You know / believe"],
            ["Present Syncopated", "I have / do / say", "<strong>Thou hast / dost / sayest</strong>", "You have / do / say"],
            ["Weak Past Indicative (<em>-ed + -st</em>)", "I walked / loved / girded", "<strong>Thou walkedst / lovedst / girdedst</strong>", "You walked / loved / girded"],
            ["Strong Past Indicative", "I went / gave / knew / spake", "<strong>Thou wentest / gavest / knewest / spakest</strong>", "You went / gave / knew / spoke"],
        ],
    )
    c1.para(
        "Notice how dense consonant clusters arise in weak past-tense verbs with <em>thou</em>—such as "
        "<em>thou girdedst</em>, <em>thou buildedst</em>, or <em>thou receivedst</em>—where the past suffix "
        "<em>-ed</em> is immediately followed by the second-person singular suffix <em>-st</em>. Whenever you "
        "encounter a verb ending in <strong>-edst</strong>, it is simply the normal past tense (<em>“you [singular] "
        "verb-ed”</em>)."
    )

    c1.subheading("2. Third-Person Singular Agreement: -eth / -th")
    c1.para(
        "In the southern and London literary dialects of Early Modern English that formed the basis of the 1611 King "
        "James Bible, the third-person singular present indicative suffix (with <em>he</em>, <em>she</em>, <em>it</em>, "
        "or any singular noun like <em>the Lord</em>, <em>a man</em>, <em>charity</em>) was <strong>-eth</strong> "
        f"(or <strong>-th</strong> after stems ending in a vowel), where modern English uses <strong>-s</strong> {fn_1cor13_4} {fn_mosiah2_21}:"
    )
    c1.callout(
        "Translating -eth / -th Directly into Modern Present-Tense -s",
        [
            "• <em>He walketh</em> = “He walks” &#160;|&#160; <em>She saith</em> (pronounced <em>seth</em>) = “She says”",
            "• <em>It cometh</em> = “It comes” &#160;|&#160; <em>The wind bloweth</em> = “The wind blows”",
            "• <em>He hath</em> = “He has” &#160;|&#160; <em>He doth</em> (pronounced <em>duth</em>) = “He does”",
            "• <strong>Pronunciation &amp; Historical Transition Note:</strong> In older Tudor verse and deliberate liturgical reading, <em>-eth</em> was pronounced as a full syllable (<em>lov-eth</em>, <em>mak-eth</em>). However, by 1611 in everyday London speech (and throughout Shakespeare’s late plays), the Northern/Midland suffix <em>-s</em> (<em>walks, says, comes</em>) had largely replaced <em>-eth</em> in spoken pronunciation, even when scribes and printers continued writing <em>-eth</em> on the page as the dignified literary spelling.",
            "• <strong>Plural Caution:</strong> Standard KJV grammar uses <em>-eth</em> only for singular subjects (<em>“the wicked man flee<strong>th</strong>”</em>) and uses zero ending for plural subjects (<em>“the wicked flee”</em>). However, in broader Southern and West Country Early Modern English (and occasionally in the 1830 Book of Mormon), <em>-eth</em> could also function as a historic plural suffix (from Old English plural <em>-aþ</em>), as in 1830 passages where a plural subject takes <em>doth</em> or <em>hath</em>.",
        ],
    )
    chapters.append(c1.build())

    # --- CHAPTER 2: IRREGULAR, AUXILIARY & MODAL VERB PARADIGMS ---
    c2 = ChapterDraft(
        chapter_id="eme-bk2-ch2",
        number=2,
        title="Chapter 2: Irregular, Auxiliary & Modal Verb Paradigms",
        subtitle="To Be, To Have, To Do (Dost vs. Doest / Doth vs. Doeth), and Modal Polarity (Shall vs. Wilt)",
        headnote=(
            "Did you know that the King James Bible and Book of Mormon systematically distinguish between ‘dost’ and "
            "‘doest,’ and between ‘doth’ and ‘doeth’? One is a helper verb; the other is an action verb."
        ),
        corpus=corpus,
    )

    c2.para(
        "High-frequency auxiliary and modal verbs preserve the oldest Indo-European and Germanic inflectional patterns "
        "in English. The table below provides the complete paradigm for scriptural reading:"
    )
    c2.table(
        headers=[
            "Verb",
            "Infinitive",
            "1st Pres. (I)",
            "2nd Pres. (Thou)",
            "3rd Pres. (He/She/It)",
            "2nd Past (Thou)",
        ],
        rows=[
            ["<strong>To Be</strong>", "be", "am", "<strong>art</strong> (subj. <em>be</em>)", "is (subj. <em>be</em>)", "<strong>wast</strong> (subj. <strong>wert</strong>)"],
            ["<strong>To Have</strong>", "have", "have", "<strong>hast</strong>", "<strong>hath</strong>", "<strong>hadst</strong>"],
            ["<strong>To Do (Aux.)</strong>", "do", "do", "<strong>dost</strong>", "<strong>doth</strong>", "<strong>didst</strong>"],
            ["<strong>To Do (Main)</strong>", "do", "do", "<strong>doest</strong>", "<strong>doeth</strong>", "<strong>didst</strong>"],
            ["<strong>Shall</strong>", "—", "shall", "<strong>shalt</strong>", "shall", "<strong>shouldst / shouldest</strong>"],
            ["<strong>Will</strong>", "—", "will", "<strong>wilt</strong>", "will", "<strong>wouldst / wouldest</strong>"],
            ["<strong>Can</strong>", "—", "can", "<strong>canst</strong>", "can", "<strong>couldst / couldest</strong>"],
            ["<strong>May</strong>", "—", "may", "<strong>mayest / mayst</strong>", "may", "<strong>mightest / mightst</strong>"],
            ["<strong>To Wit (Know)</strong>", "to wit", "<strong>wot</strong>", "<strong>wottest</strong>", "<strong>wot / wotteth</strong>", "<strong>wist</strong> (all persons)"],
            ["<strong>Dare</strong>", "dare", "dare", "<strong>darest / durst</strong>", "dare / <strong>durst</strong>", "<strong>durst</strong>"],
        ],
    )

    fn_gen4_7 = c2.cite(
        "Genesis",
        4,
        7,
        "Full lexical action verb ‘doest’: ‘If thou doest well [i.e., if you act righteously], shalt thou not be accepted? and if thou doest not well, sin lieth at the door.’",
    )
    fn_1jn3_7 = c2.cite(
        "1 John",
        3,
        7,
        "Full lexical action verb ‘doeth’: ‘Little children, let no man deceive you: he that doeth righteousness [performs/practices righteousness] is righteous.’",
    )
    fn_john20_15 = c2.cite(
        "John",
        20,
        15,
        "Auxiliary helper verb ‘dost’: ‘Woman, why weepest thou? whom seekest thou?’ Compare Ruth 1:16 or 1 Kings 19:9 (‘What doest thou here, Elijah?’ = ‘What action are you performing here?’) vs. auxiliary ‘Why dost thou weep?’",
    )
    fn_mosiah4_10 = c2.cite(
        "Mosiah",
        4,
        10,
        "Both auxiliary ‘doth’ and lexical ‘doeth’ appear in the Book of Mormon in exact conformity with 1611 EME rules: e.g., ‘if ye do not watch yourselves, and your thoughts, and your words, and your deeds, and observe the commandments of God… ye must perish.’",
        include_1830=True,
    )

    c2.subheading("The Crucial Distinction: Dost/Doth vs. Doest/Doeth")
    c2.callout(
        "Auxiliary Helper (Dost / Doth) vs. Lexical Action Verb (Doest / Doeth)",
        [
            f"• <strong>Dost</strong> and <strong>Doth</strong> (pronounced <em>dust</em> and <em>duth</em>, one syllable) function almost exclusively as <strong>auxiliary (helping) verbs</strong> coupled with another verb’s infinitive: <em>“Why <strong>dost</strong> thou weep?”</em> {fn_john20_15}, <em>“He <strong>doth</strong> lead me,”</em> <em>“The Lord <strong>doth</strong> grant unto them.”</em>",
            f"• <strong>Doest</strong> and <strong>Doeth</strong> (pronounced <em>doo-est</em> and <em>doo-eth</em>, two full syllables) function as <strong>full lexical main verbs</strong> denoting the performance of a deed or action: <em>“If thou <strong>doest</strong> well”</em> {fn_gen4_7} (= “If you perform well”), <em>“What <strong>doest</strong> thou?”</em> (= “What action are you performing?”), <em>“He that <strong>doeth</strong> righteousness is righteous”</em> {fn_1jn3_7} {fn_mosiah4_10}.",
        ],
    )

    c2.subheading("Shall / Shalt vs. Will / Wilt: Prophetic Determination vs. Volition")
    c2.para(
        "Modern American English uses <em>will</em> for nearly all future statements, treating <em>shall</em> as a "
        "stiff legalism. In Early Modern English, however, <strong>will / wilt</strong> retained its original Germanic "
        "meaning of <em>personal volition, wish, or desire</em> (cf. <em>“if thou wilt, thou canst make me clean”</em> "
        "= “if you are willing / if you choose to”), whereas <strong>shall / shalt</strong> expressed <em>binding "
        "obligation, divine decree, or inevitable future certainty</em> (hence the Ten Commandments: <em>“Thou "
        "<strong>shalt</strong> not…”</em>)."
    )
    chapters.append(c2.build())

    # --- CHAPTER 3: SUBJUNCTIVE MOOD INFLECTION ---
    c3 = ChapterDraft(
        chapter_id="eme-bk2-ch3",
        number=3,
        title="Chapter 3: The Subjunctive Mood in Conditional, Concessive & Optative Clauses",
        subtitle="Why ‘-eth’ and ‘-est’ Disappear After ‘If,’ ‘Though,’ ‘Lest,’ ‘Except,’ and in Blessings",
        headnote=(
            "When a reader sees ‘Though he slay me,’ ‘If thou be the Son of God,’ or ‘Except a man be born of water,’ "
            "the uninflected verb is not broken grammar—it is the Early Modern English Subjunctive Mood."
        ),
        corpus=corpus,
    )

    fn_job13_15 = c3.cite(
        "Job",
        13,
        15,
        "Concessive subjunctive ‘slay’ (not indicative ‘slayeth’): ‘Though he slay me, yet will I trust in him: but I will maintain mine own ways before him.’",
    )
    fn_matt4_3 = c3.cite(
        "Matthew",
        4,
        3,
        "Conditional subjunctive ‘be’ (not indicative ‘art’): ‘If thou be the Son of God, command that these stones be made bread.’",
    )
    fn_john3_5 = c3.cite(
        "John",
        3,
        5,
        "Conditional subjunctive after ‘except’ (= unless): ‘Verily, verily, I say unto thee, Except a man be born of water and of the Spirit, he cannot enter into the kingdom of God.’",
    )
    fn_num6_24 = c3.cite(
        "Numbers",
        6,
        24,
        "Optative (blessing/prayer) subjunctive in the main clause: ‘The Lord bless thee, and keep thee’ (not ‘blesseth’ or ‘keepeth’—it is a priestly invocation: ‘May the Lord bless thee!’).",
    )
    fn_ether12_27 = c3.cite(
        "Ether",
        12,
        27,
        "Notice how Ether 12:27 uses the EME subjunctive ‘come’ and ‘humble’: ‘if men come unto me I will show unto them their weakness… if they humble themselves before me, and have faith in me, then will I make weak things become strong unto them.’",
        include_1830=True,
    )

    c3.para(
        "In Contemporary English, the subjunctive mood is nearly extinct, surviving only in fossilized phrases like "
        "<em>“God bless you,”</em> <em>“if I were you,”</em> or <em>“so be it.”</em> In Early Modern English, however, "
        "the subjunctive mood was vibrant and obligatory across four major syntactic environments: "
        "<strong>conditionals</strong> (after <em>if, unless, except, in case</em>), <strong>concessives</strong> "
        "(after <em>though, although, albeit</em>), <strong>negative purpose clauses</strong> (after <em>lest</em>), "
        "and <strong>optative prayers/blessings</strong>."
    )
    c3.para(
        "Morphologically, the present subjunctive is formed by using the <strong>uninflected base stem</strong> of the "
        "verb—dropping the third-person singular <em>-eth</em> and the second-person singular <em>-est</em>, and using "
        "<strong>be</strong> instead of <em>am/art/is/are</em> (and <strong>wert / were</strong> for the past counterfactual):"
    )
    c3.table(
        headers=["Clause Type", "Indicative (Statement of Fact)", "Subjunctive (Hypothetical / Contingent / Prayer)"],
        rows=[
            [
                "<strong>3rd Person Singular Conditional</strong>",
                "“He <strong>knoweth</strong> the truth.”<br/>“A man <strong>is</strong> born again.”",
                f"“If he <strong>know</strong> the truth…”<br/>“Except a man <strong>be</strong> born of water…” {fn_john3_5}",
            ],
            [
                "<strong>3rd Person Singular Concessive</strong>",
                "“He <strong>slayeth</strong> me.”",
                f"“Though he <strong>slay</strong> me, yet will I trust in him.” {fn_job13_15}",
            ],
            [
                "<strong>2nd Person Singular Conditional</strong>",
                "“Thou <strong>art</strong> a prophet.”<br/>“Thou <strong>wast</strong> dead.”",
                f"“If thou <strong>be</strong> the Son of God…” {fn_matt4_3}<br/>“Though thou <strong>wert</strong> dead…”",
            ],
            [
                "<strong>Negative Purpose (<em>Lest</em>)</strong>",
                "“He <strong>falleth</strong> into temptation.”",
                "“Take heed <strong>lest</strong> he <strong>fall</strong>.” (= “so that he may not fall”)",
            ],
            [
                "<strong>Optative Blessing / Petition</strong>",
                "“The Lord <strong>blesseth</strong> thee.”",
                f"“The Lord <strong>bless</strong> thee, and <strong>keep</strong> thee.” {fn_num6_24}<br/>“Hallowed <strong>be</strong> thy name. Thy kingdom <strong>come</strong>.”",
            ],
        ],
    )
    c3.para(
        "Whenever you read the Lord’s Prayer—<em>“Hallowed <strong>be</strong> thy name. Thy kingdom "
        "<strong>come</strong>. Thy will <strong>be</strong> done”</em>—those three verbs are third-person singular "
        "<strong>optative subjunctives</strong> meaning: <em>“May thy name be sanctified; may thy kingdom come; may "
        f"thy will be accomplished!”</em> {fn_ether12_27}"
    )
    chapters.append(c3.build())

    # --- CHAPTER 4: PERFECT ASPECT WITH MOTION VERBS (BE VS HAVE) ---
    c4 = ChapterDraft(
        chapter_id="eme-bk2-ch4",
        number=4,
        title="Chapter 4: Perfect Aspect with Motion & Change-of-State Verbs (‘Be’ vs. ‘Have’)",
        subtitle="Why Scriptural English Says ‘He Is Come,’ ‘He Is Risen,’ and ‘They Are Fallen’",
        headnote=(
            "Modern readers often misread ‘He is come’ or ‘The sun was risen’ as passive voice or awkward present "
            "tense. In fact, Early Modern English preserved the classic Germanic split-auxiliary perfect tense."
        ),
        corpus=corpus,
    )

    fn_matt28_6 = c4.cite(
        "Matthew",
        28,
        6,
        "‘He is not here: for he is risen, as he said.’ In EME, ‘is risen’ is the active present perfect of the intransitive motion verb ‘rise’ (= ‘He has risen, and now stands in a risen state’).",
    )
    fn_mark4_35 = c4.cite(
        "Mark",
        4,
        35,
        "Pluperfect of change-of-state with ‘to be’: ‘when the even was come’ (= ‘when evening had arrived’).",
    )
    fn_exod32_1 = c4.cite(
        "Exodus",
        32,
        1,
        "‘for as for this Moses, the man that brought us up out of the land of Egypt, we wot not what is become of him’ (= ‘we do not know what has happened to him’).",
    )
    fn_1ne8_8 = c4.cite(
        "1 Nephi",
        8,
        8,
        "The Book of Mormon regularly uses the EME ‘be’-perfect with verbs of motion and time: e.g., ‘after I had traveled for the space of many hours in darkness…’ alongside ‘they are fallen,’ ‘the time is come,’ ‘he is gone.’",
        include_1830=True,
    )

    c4.para(
        "In Contemporary English, every verb forms its present perfect and past perfect (pluperfect) tenses using the "
        "auxiliary verb <strong>to have</strong>: <em>“He has arrived,” “They have fallen,” “The sun had risen,” “What "
        "has become of him?”</em>"
    )
    c4.para(
        "Early Modern English, however—just like modern German (<em>sein</em> vs. <em>haben</em>), French "
        "(<em>être</em> vs. <em>avoir</em>), and Italian (<em>essere</em> vs. <em>avere</em>)—maintained the historic "
        "<strong>Germanic split-auxiliary perfect</strong>:"
    )
    c4.callout(
        "The Split-Auxiliary Perfect Rule: Transitive ‘Have’ vs. Intransitive Motion ‘Be’",
        [
            "• <strong>Transitive &amp; Non-Motion Verbs take <em>To Have</em>:</strong> <em>“They <strong>have heard</strong> the word,” “I <strong>have fought</strong> a good fight,” “He <strong>hath spoken</strong>.”</em>",
            f"• <strong>Intransitive Verbs of Motion, Arrival, Departure, or Change of State take <em>To Be</em>:</strong> Verbs such as <em>come, go, arrive, depart, return, enter, ascend, descend, rise, fall, flee, pass, grow, wax, become,</em> and <em>befall</em> formed their perfect aspect with <strong>am / art / is / are / was / were + past participle</strong> {fn_1ne8_8}.",
        ],
    )
    c4.table(
        headers=[
            "Scriptural EME Perfect (<em>Be + Participle</em>)",
            "Grammatical Tense / Aspect",
            "Exact Contemporary English Translation",
        ],
        rows=[
            ["<em>“He <strong>is come</strong> unto the city.”</em>", "Present Perfect of Motion", "<strong>“He has arrived / has come to the city.”</strong>"],
            [f"<em>“He is not here: for he <strong>is risen</strong>.”</em> {fn_matt28_6}", "Present Perfect (Resultative)", "<strong>“He has risen (and is now alive).”</strong>"],
            ["<em>“They <strong>are fallen</strong> to the ground.”</em>", "Present Perfect of Motion", "<strong>“They have fallen to the ground.”</strong>"],
            ["<em>“The sun <strong>was risen</strong> upon the earth.”</em>", "Past Perfect (Pluperfect)", "<strong>“The sun had risen upon the earth.”</strong>"],
            [f"<em>“When the even <strong>was come</strong>…”</em> {fn_mark4_35}", "Past Perfect (Pluperfect)", "<strong>“When evening had come / had arrived…”</strong>"],
            [f"<em>“We wot not what <strong>is become</strong> of him.”</em> {fn_exod32_1}", "Present Perfect of Change-of-State", "<strong>“We do not know what has become of him.”</strong>"],
            ["<em>“Miriam <strong>was</strong> leprous, <strong>grown</strong> white as snow.”</em>", "Resultative Perfect", "<strong>“Miriam had turned white as snow.”</strong>"],
        ],
    )
    c4.para(
        "Notice the subtle semantic richness of the Early Modern English <em>be</em>-perfect: whereas <em>“he hath "
        "come”</em> emphasizes the past act of traveling, <em>“he <strong>is</strong> come”</em> and <em>“he "
        "<strong>is</strong> risen”</em> unite the completed past action with the enduring present state that results "
        "from it."
    )
    chapters.append(c4.build())

    # --- CHAPTER 5: ARCHAIC STRONG PRETERITES & PAST PARTICIPLES ---
    c5 = ChapterDraft(
        chapter_id="eme-bk2-ch5",
        number=5,
        title="Chapter 5: Archaic Strong Preterites & Past Participles (KJV & 1830 Book of Mormon)",
        subtitle="Spake, Brake, Bare, Sware, Clave, Drave, Holpen, Waxen, Sodden, Bestead & Arriven",
        headnote=(
            "Both the 1611 King James Bible and the 1830 Book of Mormon preserve older Germanic strong verb ablaut "
            "grades (‘spake,’ ‘brake,’ ‘bare,’ ‘holpen,’ ‘arriven’) that have since leveled or shifted in modern English."
        ),
        corpus=corpus,
    )

    fn_luke1_54 = c5.cite(
        "Luke",
        1,
        54,
        "In the Magnificat, Mary sings: ‘He hath holpen his servant Israel, in remembrance of his mercy.’ ‘Holpen’ is the historic Germanic strong past participle of ‘help’ (Old English holpen).",
    )
    fn_2ne18_21 = c5.cite(
        "2 Nephi",
        18,
        21,
        "Parallel to Isaiah 8:21: ‘And they shall pass through it, hardly bestead and hungry.’ ‘Hardly bestead’ means ‘severely beset, distressed, or hard-pressed in circumstance.’",
        include_1830=True,
    )
    fn_mosiah10_15 = c5.cite(
        "Mosiah",
        10,
        15,
        "In the 1830 Palmyra edition of the Book of Mormon (and Original/Printer’s Manuscripts), Zeniff records: ‘thus when we had arriven in the land of Lehi-Nephi…’ ‘Arriven’ is an authentic 16th/17th-century Early Modern English strong past participle (modeled on driven/striven) that was later edited to ‘arrived’ in 1837.",
        include_1830=True,
    )

    c5.para(
        "Germanic languages form the past tense (preterite) and past participle of core verbs through internal vowel "
        "alternation (<em>ablaut</em>, as in <em>sing / sang / sung</em>). Between 1600 and 1900, many English strong "
        "verbs either leveled their preterite vowel to match the participle (changing <em>spake → spoke</em> and "
        "<em>brake → broke</em>) or converted into regular <em>-ed</em> weak verbs (changing <em>holpen → helped</em> "
        "and <em>waxen → waxed</em>). The reference table below decodes the major archaic preterites and participles "
        "encountered in the KJV and Book of Mormon:"
    )
    c5.table(
        headers=[
            "Archaic EME Verb Form",
            "Grammatical Form &amp; Root Verb",
            "Modern English Equivalent &amp; Scriptural Usage",
        ],
        rows=[
            ["<strong>Spake</strong>", "Past tense of <em>speak</em>", "<strong>Spoke</strong> (<em>“And the Lord spake unto Moses”</em>)"],
            ["<strong>Brake</strong>", "Past tense of <em>break</em>", "<strong>Broke</strong> (<em>“Jesus took bread, and blessed it, and brake it”</em>)"],
            ["<strong>Bare</strong>", "Past tense of <em>bear</em>", "<strong>Bore / Carried / Gave birth to</strong> (<em>“She bare a son”</em>; <em>“He bare the sin of many”</em>)"],
            ["<strong>Sware</strong>", "Past tense of <em>swear</em>", "<strong>Swore</strong> (<em>“The Lord sware unto David in truth”</em>)"],
            ["<strong>Tare</strong>", "Past tense of <em>tear</em>", "<strong>Tore</strong> (<em>“The spirit tare him”</em>)"],
            ["<strong>Clave</strong>", "Past tense of <em>cleave</em>", "<strong>Clung / Adhered to</strong> OR <strong>Split apart</strong> (<em>“Ruth clave unto her”</em>; <em>“He clave the rock”</em>)"],
            ["<strong>Drave</strong>", "Past tense of <em>drive</em>", "<strong>Drove</strong> (<em>“He drave them all out of the temple”</em>)"],
            ["<strong>Gat</strong>", "Past tense of <em>get</em>", "<strong>Got / Obtained / Went</strong> (<em>“He gat him up into the mount”</em>)"],
            ["<strong>Smote / Smitten</strong>", "Past &amp; participle of <em>smite</em>", "<strong>Struck / Afflicted / Defeated</strong>"],
            [f"<strong>Holpen</strong> {fn_luke1_54}", "Past participle of <em>help</em>", "<strong>Helped / Succored</strong> (<em>“He hath holpen his servant Israel,”</em> Luke 1:54; Ps. 83:8; Dan. 11:34)"],
            ["<strong>Holden</strong>", "Past participle of <em>hold</em>", "<strong>Held / Restrained / Bound</strong> (<em>“It was not possible that he should be holden of it,”</em> Acts 2:24)"],
            ["<strong>Waxen</strong>", "Past participle of <em>wax</em>", "<strong>Grown / Become</strong> (<em>“This people’s heart is waxen gross,”</em> Matt. 13:15)"],
            ["<strong>Stricken</strong>", "Past participle of <em>strike</em>", "<strong>Afflicted / Advanced</strong> (<em>“well stricken in years”</em> = very advanced in age)"],
            ["<strong>Sod / Sodden</strong>", "Past &amp; participle of <em>seethe</em>", "<strong>Boiled / Stewed</strong> (<em>“Jacob sod pottage,”</em> Gen. 25:29 = Jacob boiled stew)"],
            ["<strong>Laden / Laded</strong>", "Participle &amp; past of <em>lade</em>", "<strong>Loaded / Burdened</strong> (<em>“Come unto me, all ye that labour and are heavy laden”</em>)"],
            ["<strong>Molten</strong>", "Past participle of <em>melt</em>", "<strong>Cast in melted metal</strong> (<em>“a molten calf,”</em> <em>“molten plates of ore”</em>)"],
            [f"<strong>Bestead</strong> {fn_2ne18_21}", "Past participle of <em>bested</em>", "<strong>Situated / Beset / Hard-pressed</strong> (<em>“hardly bestead and hungry,”</em> Isa. 8:21; 2 Ne. 18:21)"],
            [f"<strong>Arriven</strong> {fn_mosiah10_15}", "1830 BoM strong participle of <em>arrive</em>", "<strong>Arrived</strong> (<em>“when we had arriven,”</em> 1830 Mosiah 10:15; 16th/17th-c. EME strong participle)"],
        ],
    )
    chapters.append(c5.build())

    return Book(
        id="book-2-verbal-morphology",
        title="Book II: Verbal Morphology, Suffixes, Aspect & Mood",
        full_title="Book II: Early Modern English Verbal Morphology, Inflectional Suffixes, Auxiliary Paradigms, Subjunctive Mood, and Perfect Aspect",
        subtitle="-est, -eth, Dost vs. Doest, Subjunctive Clauses, and ‘Be’-Perfects of Motion",
        chapters=chapters,
    )


def _build_book_3_syntax(corpus: ScriptureCorpusLookup) -> Book:
    chapters: list[Chapter] = []

    # --- CHAPTER 1: RELATIVIZERS: HUMAN WHICH & ZERO RELATIVES ---
    c1 = ChapterDraft(
        chapter_id="eme-bk3-ch1",
        number=1,
        title="Chapter 1: Relativization — Human ‘Which,’ Compound Relatives & Contact Clauses",
        subtitle="Why ‘Our Father Which Art in Heaven’ and Dropped Relative Pronouns Are Authentic EME",
        headnote=(
            "Modern school grammar insists on ‘who/whom’ for people and ‘which’ for inanimate objects. In Early Modern "
            "English, however, ‘which’ was completely neutral regarding animacy and referred freely to persons, angels, and God."
        ),
        corpus=corpus,
    )

    fn_matt6_9 = c1.cite(
        "Matthew",
        6,
        9,
        "‘Our Father which art in heaven, Hallowed be thy name.’ Note both human/divine ‘which’ and second-person verb agreement ‘art’ matching the vocative antecedent ‘Our Father [thou]’!",
    )
    fn_acts3_2 = c1.cite(
        "Acts",
        3,
        2,
        "Personal ‘which’ + compound relative ‘the which’: in EME, ‘the man which was healed’ or ‘they which’ is standard personal relativization.",
    )
    fn_mosiah18_8 = c1.cite(
        "Mosiah",
        18,
        8,
        "In the 1830 Palmyra edition of the Book of Mormon, hundreds of personal relative clauses originally used ‘which’ or ‘that’ (e.g., ‘those which,’ ‘he which’), many of which were later standardized by Joseph Smith or later editors to ‘who’.",
        include_1830=True,
    )

    c1.subheading("1. Personal ‘Which’ for Human and Divine Antecedents")
    c1.para(
        "In Contemporary English, using <em>which</em> for a person (<em>*“The man which spoke to me”</em>) is "
        "stigmatized as an error, and <em>who</em> or <em>whom</em> is required for human antecedents. In Early Modern "
        "English, however, <strong>which</strong> (along with <strong>that</strong>) was completely neutral with "
        "respect to animacy and was used universally for objects, animals, mortal human beings, and Deity:"
    )
    c1.callout(
        "Human &amp; Divine ‘Which’ in the KJV and 1830 Book of Mormon",
        [
            f"• <em>“Our Father <strong>which</strong> art in heaven…”</em> {fn_matt6_9} (Modern: <em>“Our Father <strong>who</strong> is in heaven”</em>). Far from dehumanizing God, <em>which</em> was the elevated literary relative pronoun of 16th- and 17th-century prose.",
            f"• <em>“The man <strong>which</strong> was healed wist not who it was.”</em> {fn_acts3_2} (Modern: <em>“The man <strong>who</strong> was healed did not know…”</em>).",
            f"• <em>“Blessed are they <strong>which</strong> do hunger and thirst after righteousness.”</em> (Modern: <em>“Blessed are those <strong>who</strong> hunger…”</em>) {fn_mosiah18_8}.",
            "• <strong>Agreement Across the Relative Pronoun:</strong> Notice that in <em>“Our Father which <strong>art</strong> in heaven”</em> or <em>“I that <strong>speak</strong> unto thee,”</em> the verb inside the relative clause agrees in person (<em>art</em> = 2nd person; <em>speak</em> = 1st person) with the pronoun or vocative antecedent!",
        ],
    )

    c1.subheading("2. Zero Relatives (Subject Contact Clauses)")
    c1.para(
        "Modern English allows a speaker to drop a relative pronoun when it functions as the <em>object</em> of the "
        "relative clause (<em>“This is the land [which] I promised unto your fathers”</em>), but strictly forbids "
        "dropping a relative pronoun when it functions as the <em>subject</em> of the relative clause. Early Modern "
        "English, by contrast, frequently dropped subject relative pronouns (producing <strong>subject contact "
        "clauses</strong>):"
    )
    c1.callout(
        "Examples of EME Subject Contact Clauses (Zero Relative)",
        [
            "• <em>“There were many [who] could not understand.”</em>",
            "• <em>“Who is this [that] cometh from Edom?”</em> (Isa. 63:1)",
            "• <em>“In this city there was a man [who] was called Alma.”</em>",
        ],
    )
    chapters.append(c1.build())

    # --- CHAPTER 2: NEGATION, INTERROGATION & UNEMPHATIC PERIPHRASTIC DO ---
    c2 = ChapterDraft(
        chapter_id="eme-bk3-ch2",
        number=2,
        title="Chapter 2: Negation, Interrogation & Unemphatic Periphrastic ‘Do’",
        subtitle="Why ‘I Know Not’ Lacks ‘Do,’ While ‘They Did Travel’ Uses ‘Did’ Without Emphasis",
        headnote=(
            "Modern English and Early Modern English use the auxiliary verb ‘do/did’ in exact mirror-image ways: "
            "where Modern English requires ‘do’ (questions and negatives), EME omits it; where Modern English reserves "
            "‘did’ for heavy emphasis (affirmative statements), EME uses it as a calm, unemphatic past-tense marker."
        ),
        corpus=corpus,
    )

    fn_john1_21 = c2.cite(
        "John",
        1,
        21,
        "Direct verb inversion in interrogation (‘Art thou Elias?’) and post-verbal negation (‘I am not’) without dummy ‘do’.",
    )
    fn_1ne2_14 = c2.cite(
        "1 Nephi",
        2,
        14,
        "Affirmative periphrastic ‘did’ in narrative prose: ‘And it came to pass that my father did speak unto them in the valley of Lemuel, with power, being filled with the Spirit, until their frames did shake before him.’ Here ‘did speak’ and ‘did shake’ are normal past-tense narrative verbs (‘spoke’, ‘shook’).",
        include_1830=True,
    )
    fn_mosiah1_6 = c2.cite(
        "Mosiah",
        1,
        6,
        "Notice how post-verbal negation (‘would not’) and periphrastic narrative ‘did’ work together seamlessly in Book of Mormon syntax.",
        include_1830=True,
    )

    c2.subheading("1. Negation and Interrogation Without ‘Do-Support’")
    c2.para(
        "Contemporary English strictly requires the dummy auxiliary verb <strong>do / does / did</strong> (known in "
        "linguistics as <em>do-support</em>) whenever forming a question or a negative statement with a lexical verb:"
    )
    c2.table(
        headers=["Syntactic Construction", "Modern English (Mandatory Do-Support)", "Early Modern English (Direct Inversion / Post-Verbal Not)"],
        rows=[
            ["<strong>Direct Question</strong>", "<em>“<strong>Do</strong> you know the way?”</em><br/><em>“<strong>Did</strong> you understand these words?”</em>", "<em>“<strong>Knowest thou</strong> the way?”</em><br/><em>“<strong>Understood ye</strong> these words?”</em>"],
            ["<strong>Negative Statement</strong>", "<em>“I <strong>do not</strong> know.”</em><br/><em>“He <strong>did not</strong> speak.”</em><br/><em>“They <strong>did not</strong> fear the king.”</em>", f"<em>“I <strong>know not</strong>.”</em> {fn_john1_21}<br/><em>“He <strong>spake not</strong>.”</em><br/><em>“They <strong>feared not</strong> the king.”</em>"],
            ["<strong>Negative Imperative</strong>", "<em>“<strong>Do not</strong> be afraid!”</em><br/><em>“<strong>Do not</strong> marvel!”</em>", "<em>“<strong>Fear not</strong>!” / “<strong>Be not</strong> afraid!”</em><br/><em>“<strong>Marvel not</strong>!”</em>"],
        ],
    )

    c2.subheading("2. Unemphatic Periphrastic ‘Do’ and ‘Did’ in Affirmative Prose")
    c2.para(
        "Conversely, when Contemporary English uses <em>do</em> or <em>did</em> in a positive statement (<em>“I "
        "<strong>did</strong> lock the door!”</em> or <em>“He <strong>really did</strong> build it!”</em>), it carries "
        "heavy contrastive or defensive stress. When modern readers read the Book of Mormon or 16th-century English "
        "chronicles aloud, they often mistakenly stress every <em>did</em>—reading <em>“And they <strong>DID</strong> "
        "travel in the wilderness”</em> as though the narrator were arguing with a skeptic!"
    )
    c2.callout(
        "How to Read Affirmative ‘Did + Infinitive’ in the Book of Mormon",
        [
            f"• In 16th- and early 17th-century Early Modern English (peaking between c. 1530 and 1610 in writers like William Tyndale, John Bourchier, and Robert Fabian), <strong>affirmative periphrastic <em>do / did</em></strong> functioned as a completely neutral, <strong>unemphatic tense carrier</strong> {fn_1ne2_14} {fn_mosiah1_6}:",
            "• <em>“And they <strong>did travel</strong> in the wilderness”</em> = <strong>“And they traveled in the wilderness.”</strong>",
            "• <em>“The Lord <strong>did speak</strong> unto them”</em> = <strong>“The Lord spoke unto them.”</strong>",
            "• <em>“We <strong>did pitch</strong> our tents”</em> = <strong>“We pitched our tents.”</strong>",
            "• Why did Early Modern English use unemphatic <em>did + verb</em>? First, for <strong>rhythmic and prosodic balance</strong> in oral reading; second, to place the tense marker right after the subject so the main lexical verb could sit in clause-prominent position without awkward consonant clusters (such as <em>*pitch’d</em> or <em>*prophesy’d</em>).",
        ],
    )
    chapters.append(c2.build())

    # --- CHAPTER 3: FLAT ADVERBS, PREPOSITIONS & CONJUNCTIONAL IDIOMS ---
    c3 = ChapterDraft(
        chapter_id="eme-bk3-ch3",
        number=3,
        title="Chapter 3: Flat Adverbs, Archaic Prepositions & Conjunctional Idioms",
        subtitle="Exceeding Glad, Sore Afraid, For To, Albeit, Howbeit, Lest, Save, Or Ever, and To God-Ward",
        headnote=(
            "Why do the scriptures say ‘exceeding glad’ and ‘sore afraid’ without ‘-ly’? And what do connectors like "
            "‘for to,’ ‘howbeit,’ ‘or ever,’ ‘against,’ and ‘save’ mean in clause structure?"
        ),
        corpus=corpus,
    )

    fn_matt2_10 = c3.cite(
        "Matthew",
        2,
        10,
        "Flat adverb ‘exceeding’: ‘When they saw the star, they rejoiced with exceeding great joy.’ Compare 1 Nephi 8:12 (‘I beheld that it was most sweet, above all that I ever before tasted’).",
    )
    fn_luke2_9 = c3.cite(
        "Luke",
        2,
        9,
        "Flat adverb ‘sore’ (= severely, intensely): ‘and the glory of the Lord shone round about them: and they were sore afraid.’",
    )
    fn_matt15_22 = c3.cite(
        "Matthew",
        15,
        22,
        "Flat adverb ‘grievous’ (= grievously, severely): ‘Have mercy on me, O Lord, thou son of David; my daughter is grievously vexed with a devil’ (and in parallel passages ‘grievous tormented’).",
    )
    fn_dan6_24 = c3.cite(
        "Daniel",
        6,
        24,
        "‘Or ever’ (= before ever): ‘and the lions had the mastery of them, and brake all their bones in pieces or ever they came at the bottom of the den.’",
    )

    c3.subheading("1. Flat Adverbs (Adverbs Without -ly)")
    c3.para(
        "In Old English, adverbs were regularly formed from adjectives by adding a final vowel <em>-e</em> (e.g., "
        "adjective <em>sār</em> → adverb <em>sāre</em>). When unstressed final <em>-e</em> became silent in late Middle "
        "English, the adverb and the adjective became identical in spelling—creating what linguists call "
        "<strong>flat adverbs</strong>. Unlike 18th-century prescriptive grammarians who demanded <em>-ly</em> on "
        "every adverb, Early Modern English used flat adverbs constantly:"
    )
    c3.table(
        headers=["Scriptural Flat Adverb", "Modern Equivalent", "Canonical Examples"],
        rows=[
            [f"<strong>Exceeding</strong> {fn_matt2_10}", "<strong>Exceedingly / Extremely</strong>", "<em>“They were <strong>exceeding</strong> glad”</em>; <em>“an <strong>exceeding</strong> great army”</em>; <em>“<strong>exceeding</strong> fine”</em> (1830 BoM)"],
            [f"<strong>Sore</strong> {fn_luke2_9}", "<strong>Severely / Intensely / Deeply</strong>", "<em>“They were <strong>sore</strong> afraid”</em>; <em>“Hannah wept <strong>sore</strong>”</em>; <em>“the famine was <strong>sore</strong> in the land”</em>"],
            [f"<strong>Grievous</strong> {fn_matt15_22}", "<strong>Grievously / Painfully</strong>", "<em>“The city was <strong>grievous</strong> tormented”</em>"],
            ["<strong>Clear</strong>", "<strong>Completely / Entirely</strong>", "<em>“The water ran <strong>clear</strong> away”</em>"],
            ["<strong>Scarce</strong>", "<strong>Scarcely / Barely</strong>", "<em>“With these sayings <strong>scarce</strong> restrained they the people”</em> (Acts 14:18)"],
            ["<strong>marvelous</strong>", "<strong>Marvelously / Wonderfully</strong>", "<em>“He was <strong>marvelous</strong> helped”</em> (2 Chr. 26:15); <em>“did do <strong>marvelous</strong> works”</em>"],
        ],
    )

    c3.subheading("2. Archaic Prepositional & Conjunctional Idioms")
    c3.para(
        "Scriptural clauses are held together by prepositional and conjunctional hinges whose meanings are often "
        "opaque to modern readers:"
    )
    c3.table(
        headers=["EME Connector / Idiom", "Exact Meaning", "Scriptural Illustration"],
        rows=[
            ["<strong>For to</strong> + infinitive", "<strong>In order to / To</strong> (purpose)", "<em>“What went ye out into the wilderness <strong>for to</strong> see?”</em> (Matt. 11:7; 1 Ne. 8:5)"],
            ["<strong>Howbeit</strong> / <strong>Albeit</strong>", "<strong>Nevertheless / However / Although</strong>", "<em>“<strong>Howbeit</strong> this kind goeth not out but by prayer and fasting”</em> (Matt. 17:21)"],
            ["<strong>Lest</strong> (+ subjunctive)", "<strong>For fear that / So that… not</strong>", "<em>“Ye shall not eat of it… <strong>lest</strong> ye die”</em> (Gen. 3:3)"],
            ["<strong>Except</strong> (+ subjunctive)", "<strong>Unless / If… not</strong>", "<em>“<strong>Except</strong> the Lord build the house, they labour in vain”</em> (Ps. 127:1)"],
            ["<strong>Save</strong> / <strong>Saving</strong>", "<strong>Except for / Other than</strong>", "<em>“No man knoweth the Son, <strong>save</strong> the Father”</em> (Matt. 11:27)"],
            ["<strong>Insomuch that</strong>", "<strong>To such a degree that / So that</strong>", "<em>“<strong>Insomuch that</strong> the multitude wondered”</em> (Matt. 15:31; ubiquitous in BoM)"],
            [f"<strong>Or ever</strong> {fn_dan6_24}", "<strong>Before ever</strong> (<em>or</em> = Old Eng. <em>ǣr</em> ‘ere’)", "<em>“<strong>Or ever</strong> the silver cord be loosed”</em> (Eccl. 12:6; Song 6:12; Dan. 6:24)"],
            ["<strong>Against</strong> (conj./prep.)", "<strong>In preparation for / By the time that</strong>", "<em>“They made ready the present <strong>against</strong> Joseph came at noon”</em> (Gen. 43:25)"],
            ["<strong>Touching / As touching</strong>", "<strong>Concerning / Regarding</strong>", "<em>“Now <strong>as touching</strong> things offered unto idols…”</em> (1 Cor. 8:1)"],
            ["<strong>To … -ward</strong> (Tmesis)", "<strong>Toward …</strong>", "<em>“<strong>To God-ward</strong>”</em> (= toward God, 2 Cor. 3:4); <em>“<strong>To us-ward</strong>”</em> (= toward us, Ps. 40:5; Eph. 1:19)"],
        ],
    )
    chapters.append(c3.build())

    # --- CHAPTER 4: ROYAL SKOUSEN'S CRITICAL TEXT FINDINGS IN THE 1830 BOOK OF MORMON ---
    c4 = ChapterDraft(
        chapter_id="eme-bk3-ch4",
        number=4,
        title="Chapter 4: Early Modern English in the Original 1830 Book of Mormon",
        subtitle="Syntactic & Lexical Discoveries from the Book of Mormon Critical Text Project",
        headnote=(
            "One of the most remarkable philological discoveries of the past thirty years—led by linguist Royal Skousen "
            "and Stanford Carmack—is that the earliest text of the Book of Mormon contains authentic 16th- and 17th-century "
            "English grammar and vocabulary that do not appear in the King James Bible and were extinct by 1830."
        ),
        corpus=corpus,
    )

    fn_1ne17_50 = c4.cite(
        "1 Nephi",
        17,
        50,
        "‘If it so be that’ + subjunctive: ‘If God had commanded me to do all things I could do them. If he should command me that I should say unto this water, be thou earth, it should be earth.’ Notice also EME ‘command that [subject] should [verb]’!",
        include_1830=True,
    )
    fn_hel6_21 = c4.cite(
        "Helaman",
        6,
        21,
        "‘The more part’ (= ‘the majority,’ matching Acts 19:32 & 27:12 and 16th-century English chronicles): ‘But behold, Satan did stir up the hearts of the more part of the Nephites, insomuch that they did unite with those bands of robbers.’",
        include_1830=True,
    )
    fn_alma24_18 = c4.cite(
        "Alma",
        24,
        18,
        "Notice how in the 1830 text, ‘do away’ / ‘done away’ and ‘impart of their substance’ preserve 16th-century legal and religious English idioms.",
        include_1830=True,
    )

    c4.para(
        "For generations, readers assumed that the archaic English of the Book of Mormon was simply an imitation of the "
        "1611 King James Bible mixed with 19th-century American frontier dialect. However, exhaustive collation of the "
        "Original Manuscript (O) and Printer’s Manuscript (P) by Professor Royal Skousen (<em>The Book of Mormon "
        "Critical Text Project</em>) and corpus linguist Stanford Carmack (comparing the text against the <em>Oxford "
        "English Dictionary</em> and the 70,000-book <em>Early English Books Online [EEBO]</em> corpus) has overturned "
        "that assumption."
    )
    c4.para(
        "The dictated 1829 manuscript of the Book of Mormon systematically deploys <strong>non-KJV Early Modern English "
        "constructions</strong> that flourished between 1530 and 1680:"
    )
    c4.table(
        headers=["1830 Book of Mormon Construction", "Historical Period in English (EEBO / OED)", "Linguistic Explanation &amp; Significance"],
        rows=[
            [
                f"<strong>Command Syntax:</strong><br/><em>“commanded X that he should [verb]”</em> {fn_1ne17_50}",
                "Peak: 1480–1620<br/>(Rare in KJV; extinct in 1830)",
                "The KJV almost always uses the infinitive after <em>command</em> (<em>“commanded him to go”</em>). The Book of Mormon predominantly uses finite <em>that + should</em> clauses (<em>“commanded him that he should go”</em>), which was standard in 15th- and 16th-century Tudor prose (such as Caxton and Sir Thomas Malory).",
            ],
            [
                f"<strong>“The more part”</strong><br/>(= the majority) {fn_hel6_21}",
                "Peak: 1500–1610<br/>(Only 2× in KJV Acts; 26× in BoM)",
                "Used 26 times in the Book of Mormon (including the unique 16th-century variant <em>“the more parts of the Nephites”</em> in 1830 Helaman 6:32, attested in Holinshed’s 1577 <em>Chronicles</em>).",
            ],
            [
                "<strong>“If it so be that…”</strong>",
                "Peak: 1520–1650<br/>(0× in KJV; 41× in BoM)",
                "This exact five-word conditional conjunction never appears in the King James Bible (which uses <em>if so be that</em>), yet appears 41 times in the Book of Mormon and was widespread in 16th-century Reformation treatises.",
            ],
            [
                "<strong>Archaic Lexical Senses:</strong><br/><em>“depart”</em> = divide/part asunder;<br/><em>“extinct”</em> = extinguished (of life);<br/><em>“counsel”</em> = consult",
                "1500–1660",
                f"In Helaman 8:11, Moses gets power <em>“to smite upon the waters of the Red Sea and they <strong>departed</strong> hither and thither”</em>—using the 16th-century transitive/reflexive sense of <em>depart</em> meaning ‘divide/separate’ (as in the 1549 Book of Common Prayer marriage vow: <em>“till death us depart”</em>, later altered in 1662 to <em>“till death us do part”</em>!) {fn_alma24_18}.",
            ],
            [
                "<strong>Personal “Who / Which + That”</strong><br/>(<em>“they which that…”</em>) &amp; <strong>Pleonastic “That”</strong>",
                "1450–1620",
                "Early Modern English regularly attached pleonastic <em>that</em> after subordinating conjunctions (<em>because that, after that, before that, since that, how that, if so be that</em>) and relative pronouns. In reading, simply mentally drop the extra <em>that</em>.",
            ],
            [
                "<strong>“Counsel the Lord”</strong> (Alma 37:37 1830)<br/>= <strong>“Consult the Lord”</strong>",
                "1530–1680",
                "In the Original Manuscript and 1830 edition of Alma 37:37 (<em>“Counsel the Lord in all thy doings”</em>, changed in 1920 to <em>“Counsel with the Lord”</em>), transitive <em>counsel</em> carried its documented 16th/17th-century OED meaning: <strong>‘to consult, ask advice of, or seek counsel from’</strong>—not to give advice to God!",
            ],
            [
                "<strong>“But if”</strong> (Mosiah 3:19 1830)<br/>= <strong>“Unless”</strong>",
                "1380–1590",
                "In the 1830 text of Mosiah 3:19 (<em>“for the natural man is an enemy to God… and will be, forever and ever, <strong>but if</strong> he yieldeth to the enticings of the Holy Spirit”</em>), <em>but if</em> is the classic late Middle / early Tudor compound conjunction meaning <strong>‘unless’</strong>.",
            ],
            [
                "<strong>“Marred”</strong> (1 Ne. 13:34), <strong>“Deranged”</strong> (Alma 56:16) &amp; <strong>“Give away to”</strong> (Alma 27:9)",
                "1540–1690",
                "In 16th-century English, <em>mar</em> meant ‘to hinder, balk, or stop one’s progress’; military <em>deranged</em> (from French <em>déranger</em>) meant ‘thrown out of battle rank/array’ (not mentally insane!); and <em>give away to</em> meant ‘yield / give way to’.",
            ],
        ],
    )
    chapters.append(c4.build())

    return Book(
        id="book-3-syntax-and-grammar",
        title="Book III: Syntax, Clause Architecture & Early Modern Grammar",
        full_title="Book III: Early Modern English Syntax, Relativization, Negation, Periphrastic ‘Do,’ Flat Adverbs, and 1830 Book of Mormon Philology",
        subtitle="Human ‘Which,’ Contact Clauses, Unemphatic ‘Did,’ and Royal Skousen’s Critical Text Findings",
        chapters=chapters,
    )


def _build_book_4_glossary(corpus: ScriptureCorpusLookup) -> Book:
    chapters: list[Chapter] = []

    # --- CHAPTER 1: CONNECTIVES, DIRECTIONALS, TEMPORALS & INTERROGATIVES ---
    c1 = ChapterDraft(
        chapter_id="eme-bk4-ch1",
        number=1,
        title="Chapter 1: Lexical Glossary I — Connectives, Directionals, Temporals & Interrogatives",
        subtitle="Wherefore, Whither, Whence, Twain, Anon, Presently, Straightway, and By and By",
        headnote=(
            "False friends in directional and temporal adverbs routinely invert the meaning of a sentence: ‘wherefore’ "
            "never means ‘where,’ and ‘presently,’ ‘anon,’ and ‘by and by’ mean ‘immediately,’ not ‘later on.’"
        ),
        corpus=corpus,
    )

    fn_2ne9_51 = c1.cite(
        "2 Nephi",
        9,
        51,
        "‘Wherefore, do not spend money for that which is of no worth, nor your labor for that which cannot satisfy.’ Comparing Isaiah 55:2 (‘Wherefore do ye spend money for that which is not bread?’): in Isaiah 55:2, ‘wherefore’ is interrogative (‘Why do you spend money…?’); in 2 Nephi 9:51, Jacob uses it illatively (‘Therefore / For this reason, do not spend money…’).",
        include_1830=True,
    )
    fn_matt5_41 = c1.cite(
        "Matthew",
        5,
        41,
        "‘And whosoever shall compel thee to go a mile, go with him twain.’ (Compare 3 Nephi 12:41.) ‘Twain’ = two.",
    )
    fn_john13_36 = c1.cite(
        "John",
        13,
        36,
        "Simon Peter asks: ‘Lord, whither goest thou?’ (= ‘Lord, to what place are you going?’).",
    )
    fn_matt13_20 = c1.cite(
        "Matthew",
        13,
        20,
        "‘But he that received the seed into stony places, the same is he that heareth the word, and anon with joy receiveth it.’ ‘Anon’ = immediately, at once.",
    )
    fn_matt26_53 = c1.cite(
        "Matthew",
        26,
        53,
        "In Gethsemane, Jesus says: ‘Thinkest thou that I cannot now pray to my Father, and he shall presently give me more than twelve legions of angels?’ ‘Presently’ = instantly, at this very moment (not ‘after a while’).",
    )
    fn_luke21_9 = c1.cite(
        "Luke",
        21,
        9,
        "‘But when ye shall hear of wars and commotions, be not terrified: for these things must first come to pass; but the end is not by and by.’ Here ‘not by and by’ means ‘the end is NOT immediate / does NOT follow right away’!",
    )

    c1.subheading("1. The Directional Triad: Where / Whither / Whence (and Here / Hither / Hence)")
    c1.para(
        "Early Modern English possessed a symmetrical three-way system of spatial adverbs indicating "
        "<strong>static location</strong>, <strong>motion toward</strong>, and <strong>motion from</strong>:"
    )
    c1.table(
        headers=["Spatial Dimension", "Interrogative / Relative (‘Where’)", "Proximal (‘Here’)", "Distal (‘There’)"],
        rows=[
            ["<strong>Static Location</strong> (At what place)", "<strong>Where</strong><br/>(<em>“Where dwellest thou?”</em>)", "<strong>Here</strong><br/>(in this place)", "<strong>There</strong><br/>(in that place)"],
            [f"<strong>Destination</strong> (To what place) {fn_john13_36}", "<strong>Whither</strong><br/>(<em>“Whither goest thou?”</em> = To where?)", "<strong>Hither</strong><br/>(<em>“Come hither”</em> = Come to this place)", "<strong>Thither</strong><br/>(<em>“Go thither”</em> = Go to that place)"],
            ["<strong>Origin / Source</strong> (From what place)", "<strong>Whence</strong><br/>(<em>“Whence comest thou?”</em> = From where?)", "<strong>Hence</strong><br/>(<em>“Depart hence”</em> = Leave from here)", "<strong>Thence</strong><br/>(<em>“He departed thence”</em> = From there)"],
        ],
    )

    c1.subheading("2. High-Frequency Connectives, Numerals & Temporal False Friends")
    c1.table(
        headers=["Scriptural Term", "Part of Speech", "Actual Early Modern Meaning", "Modern Error &amp; Exegetical Notes"],
        rows=[
            [
                f"<strong>Wherefore</strong> {fn_2ne9_51}",
                "Adverb / Conjunction",
                "<strong>Why? / For what reason?</strong> (in questions); OR <strong>Therefore / Consequently</strong> (in statements)",
                "<strong>Modern Error:</strong> Confused with <em>where</em> (location). In Shakespeare’s <em>“O Romeo, Romeo! wherefore art thou Romeo?”</em> Juliet is asking <em>why</em> he bears the enemy name Montague. In scripture, <em>“Wherefore did ye doubt?”</em> means <em>“Why did you doubt?”</em>",
            ],
            [
                f"<strong>Twain</strong> {fn_matt5_41}",
                "Numeral / Noun",
                "<strong>Two</strong> (Old English masculine <em>twēġen</em>)",
                "<em>“Go with him twain”</em> = go two miles; <em>“they twain shall be one flesh”</em> = the two of them; <em>“rent in twain”</em> = torn in two.",
            ],
            [
                f"<strong>Anon</strong> {fn_matt13_20}",
                "Adverb",
                "<strong>Immediately / At once / Straightway</strong>",
                "From Old English <em>on ān</em> (‘into one [moment]’). Later drifted to mean ‘soon / before long,’ but in the KJV it denotes instant response.",
            ],
            [
                f"<strong>Presently</strong> {fn_matt26_53}",
                "Adverb",
                "<strong>Instantly / Immediately / Right now</strong>",
                "<strong>Modern Error:</strong> Taken to mean ‘in a little while’ or ‘currently.’ When the fig tree withered <em>presently</em> (Matt. 21:19), it withered on the spot, instantaneously.",
            ],
            [
                "<strong>Straightway</strong>",
                "Adverb",
                "<strong>Immediately / Without delay</strong>",
                "From <em>straight</em> (‘direct, unswerving’), referring to time rather than geometry (e.g., Mark 1:18: <em>“And straightway they forsook their nets”</em>).",
            ],
            [
                f"<strong>By and by</strong> {fn_luke21_9}",
                "Adverbial Phrase",
                "<strong>Immediately / At once</strong>",
                "<strong>Modern Error:</strong> Assumed to mean ‘eventually’ or ‘after a long delay.’ In Mark 6:25, Salome demands the head of John the Baptist <em>“by and by in a charger”</em> (= right this instant on a platter!).",
            ],
            [
                "<strong>Betimes</strong>",
                "Adverb",
                "<strong>Early in the morning / Seasonably / Promptly</strong>",
                "E.g., Genesis 26:31: <em>“And they rose up betimes in the morning, and sware one to another.”</em>",
            ],
            [
                "<strong>Peradventure / Haply</strong>",
                "Adverb",
                "<strong>Perhaps / By chance / Possibly</strong>",
                "<em>Peradventure</em> is from French <em>par aventure</em> (‘by chance’); <em>haply</em> is from Old Norse <em>happ</em> (‘chance/luck’—not ‘happily’!).",
            ],
        ],
    )
    chapters.append(c1.build())

    # --- CHAPTER 2: VERBS & BEHAVIORAL DESCRIPTIONS ---
    c2 = ChapterDraft(
        chapter_id="eme-bk4-ch2",
        number=2,
        title="Chapter 2: Lexical Glossary II — Verbs & Behavioral False Friends",
        subtitle="Suffer, Prevent, Let, Tempt, Prove, Conversation, Careful, Thought, Wot/Wist, Halt & Condescend",
        headnote=(
            "Several verbs and behavioral terms in the KJV and Book of Mormon mean the exact opposite of their "
            "twenty-first-century definitions: ‘let’ can mean ‘hinder,’ ‘prevent’ means ‘precede,’ ‘suffer’ means "
            "‘allow,’ and ‘conversation’ means one’s entire moral conduct and citizenship."
        ),
        corpus=corpus,
    )

    fn_matt19_14 = c2.cite(
        "Matthew",
        19,
        14,
        "‘But Jesus said, Suffer little children, and forbid them not, to come unto me: for of such is the kingdom of heaven.’ (Compare 3 Nephi 17:1–11 and Mark 10:14.) ‘Suffer’ = permit, allow.",
    )
    fn_1thes4_15 = c2.cite(
        "1 Thessalonians",
        4,
        15,
        "‘that we which are alive and remain unto the coming of the Lord shall not prevent them which are asleep.’ ‘Prevent’ (Latin praevenire) = go before, precede.",
    )
    fn_rom1_13 = c2.cite(
        "Romans",
        1,
        13,
        "‘oftentimes I purposed to come unto you, (but was let hitherto,)’! Here ‘let’ (from Old English lettan, ‘to hinder/delay,’ surviving in tennis ‘let ball’ and legal ‘without let or hindrance’) means the exact opposite of modern ‘allow’: Paul says he was HINDERED/PREVENTED from coming!",
    )
    fn_phil1_27 = c2.cite(
        "Philippians",
        1,
        27,
        "‘Only let your conversation be as it becometh the gospel of Christ.’ Here ‘conversation’ (translating Greek politeuesthe, ‘conduct yourselves as citizens’) means your entire moral lifestyle, conduct, and community behavior—not merely spoken words.",
    )
    fn_phil4_6 = c2.cite(
        "Philippians",
        4,
        6,
        "‘Be careful for nothing; but in every thing by prayer and supplication with thanksgiving let your requests be made known unto God.’ ‘Be careful for nothing’ = ‘Do not be anxious or worried about anything’ (Greek merimnate).",
    )
    fn_matt6_25 = c2.cite(
        "Matthew",
        6,
        25,
        "‘Therefore I say unto you, Take no thought for your life, what ye shall eat, or what ye shall drink.’ (Compare 3 Nephi 13:25.) Jesus is not forbidding prudent planning! In 16th-century English, ‘take thought’ meant ‘suffer crippling anxiety / be consumed by worry.’",
    )
    fn_exod34_29 = c2.cite(
        "Exodus",
        34,
        29,
        "‘Moses wist not that the skin of his face shone while he talked with him.’ ‘Wist’ is the past tense of ‘to wit’ (= ‘Moses did not know’). Compare Joshua 2:4 and Mark 9:6 (‘for he wist not what to say’).",
    )
    fn_1kgs18_21 = c2.cite(
        "1 Kings",
        18,
        21,
        "Elijah on Mount Carmel: ‘How long halt ye between two opinions? if the Lord be God, follow him: but if Baal, then follow him.’ ‘Halt’ does not mean ‘stop’; it means ‘to be lame, crippled, or limp unsteadily from one foot to the other’!",
    )
    fn_gen22_1 = c2.cite(
        "Genesis",
        22,
        1,
        "‘And it came to pass after these things, that God did tempt Abraham.’ In 1611 English, ‘tempt’ (translating Hebrew nissāh) meant ‘to test, prove, or put to the trial’—not to entice to sin (cf. James 1:13).",
    )
    fn_john1_5 = c2.cite(
        "John",
        1,
        5,
        "‘And the light shineth in darkness; and the darkness comprehended it not.’ Translating Greek katalambanō, ‘comprehended’ means both ‘understood/grasped’ and ‘overcame/seized/extinguished.’",
    )

    c2.table(
        headers=["Scriptural Term", "EME Meaning", "Modern Misreading &amp; Canonical Context"],
        rows=[
            [
                f"<strong>Suffer</strong> {fn_matt19_14}",
                "<strong>To permit, allow, or tolerate</strong> (as well as to endure pain)",
                "From Latin <em>sufferre</em> (‘to bear/undergo/allow’). <em>“Suffer little children to come unto me”</em> = “Allow the little children to come.” In the Book of Mormon, <em>“God suffereth it”</em> = “God permits it.”",
            ],
            [
                f"<strong>Prevent</strong> {fn_1thes4_15}",
                "<strong>To go before, precede, anticipate, or meet early</strong>",
                "From Latin <em>prae-</em> (‘before’) + <em>venire</em> (‘to come’). In Psalm 119:147, <em>“I prevented the dawning of the morning”</em> means “I rose before dawn.” In 1 Thess. 4:15, the living <em>“shall not prevent [precede] them which are asleep.”</em>",
            ],
            [
                f"<strong>Let</strong> (Verb II) {fn_rom1_13}",
                "<strong>To hinder, obstruct, restrain, or hold back</strong>",
                "Early Modern English had two homographic verbs spelled <em>let</em>: (1) Old English <em>lǣtan</em> (‘to allow’), and (2) Old English <em>lettan</em> (‘to make late, hinder, obstruct’). In Isa. 43:13 (<em>“I will work, and who shall let it?”</em>), Rom. 1:13, and 2 Thess. 2:7 (<em>“he who now letteth will let”</em>), it means <strong>hinder/restrain</strong>!",
            ],
            [
                f"<strong>Conversation</strong> {fn_phil1_27}",
                "<strong>Conduct, manner of life, moral behavior, or citizenship</strong>",
                "From Latin <em>conversari</em> (‘to live among, associate with’). Never restricted to verbal speech in the KJV! When 1 Peter 3:1 speaks of wives winning unbelieving husbands <em>“without the word”</em> by their <em>“conversation,”</em> it means by their righteous daily conduct.",
            ],
            [
                f"<strong>Careful / Carefulness</strong> {fn_phil4_6}",
                "<strong>Anxious, worried, full of mental anguish</strong>",
                "Literally ‘full of care (grief/anxiety).’ In Luke 10:41, Jesus tells Martha, <em>“Thou art careful and troubled about many things”</em> (= anxious and distressed), not ‘conscientious and cautious.’",
            ],
            [
                f"<strong>Take thought</strong> {fn_matt6_25}",
                "<strong>To be consumed with anxiety or despair</strong>",
                "In 16th-century English, <em>thought</em> meant heavy melancholic worry (in 1597, a London coroner recorded that a citizen <em>“died of thought”</em>!). <em>“Take no thought for the morrow”</em> means “Do not be anxious about tomorrow.”",
            ],
            [
                f"<strong>Wot / Wist</strong> {fn_exod34_29}",
                "Present <strong>wot</strong> = <strong>know / knows</strong>;<br/>Past <strong>wist</strong> = <strong>knew</strong>",
                "From the Germanic verb <em>to wit</em> (Old English <em>witan</em>, ‘to know’). <em>“I wot that he whom thou blessest is blessed”</em> (Num. 22:6); <em>“He wist not that the Lord was departed from him”</em> (Judg. 16:20; 1 Ne. 11:17).",
            ],
            [
                f"<strong>Halt</strong> {fn_1kgs18_21}",
                "<strong>Lame, crippled, limping, or faltering</strong>",
                "As a noun/adjective, <em>“the blind, the halt, and the withered”</em> (John 5:3) means the lame/disabled. As a verb, <em>“How long halt ye between two opinions?”</em> means “How long will you limp unsteadily between two allegiances?”",
            ],
            [
                f"<strong>Tempt</strong> {fn_gen22_1} &amp; <strong>Prove</strong>",
                "<strong>To test, assay, examine, or put to the trial</strong>",
                "In Genesis 22:1, God <em>tested</em> Abraham’s covenant fidelity. Similarly, <em>prove</em> in Malachi 3:10 / 3 Nephi 24:10 (<em>“prove me now herewith”</em>) and Abraham 3:25 (<em>“we will prove them herewith”</em>) means “test and try their faithfulness.”",
            ],
            [
                f"<strong>Comprehend</strong> {fn_john1_5}",
                "<strong>To grasp, encompass, contain, or overcome</strong>",
                "In Isaiah 40:12, God <em>“comprehended the dust of the earth in a measure”</em> (= contained/encompassed). In John 1:5, the darkness neither understood nor overpowered the Light.",
            ],
            [
                "<strong>List</strong> (Verb)",
                "<strong>To choose, please, or desire</strong>",
                "In John 3:8, <em>“The wind bloweth where it <strong>listeth</strong>”</em> means “where it pleases / chooses.” In Matt. 17:12, <em>“they have done unto him whatsoever they <strong>listed</strong>.”</em>",
            ],
            [
                "<strong>Trow</strong>",
                "<strong>To think, suppose, or believe</strong>",
                "In Luke 17:9, <em>“Doth he thank that servant… I <strong>trow</strong> not”</em> (= “I think not”).",
            ],
            [
                "<strong>Quicken</strong>",
                "<strong>To make alive, vivify, or resurrect</strong>",
                "From <em>quick</em> (‘living’). Never means ‘to speed up’ in scripture! <em>“The Spirit quickeneth”</em> (John 6:63) = “The Spirit gives life.”",
            ],
            [
                "<strong>Cumber</strong>",
                "<strong>To overburden, weigh down, or encumber</strong>",
                "Luke 10:40: <em>“Martha was <strong>cumbered</strong> about much serving.”</em> Luke 13:7: <em>“why <strong>cumbereth</strong> it the ground?”</em>",
            ],
            [
                "<strong>Wink at</strong>",
                "<strong>To close one’s eyes to / overlook in mercy</strong>",
                "Acts 17:30: <em>“And the times of this ignorance God <strong>winked at</strong>; but now commandeth all men every where to repent.”</em> God patiently overlooked prior gentile ignorance—He was not giving a conspiratorial wink!",
            ],
            [
                "<strong>Condescend / Condescension</strong>",
                "<strong>To descend voluntarily from high estate to dwell with or rescue the lowly</strong>",
                "In 1 Nephi 11:16–26, the <em>“condescension of God”</em> has zero modern taint of patronizing arrogance; it celebrates the infinite grace of the Eternal Father and the Son descending into mortality to redeem humanity.",
            ],
        ],
    )
    chapters.append(c2.build())

    # --- CHAPTER 3: MORAL, SPIRITUAL & DESCRIPTIVE NOUNS/ADJECTIVES ---
    c3 = ChapterDraft(
        chapter_id="eme-bk4-ch3",
        number=3,
        title="Chapter 3: Lexical Glossary III — Nouns & Adjectives of Character & Spirit",
        subtitle="Peculiar, Charity, Quick, Froward, Leasing, Concupiscence, Pitiful, Vile, Curious & Silly",
        headnote=(
            "Calling God ‘very pitiful’ (James 5:11), calling saints a ‘peculiar people’ (1 Peter 2:9), or calling "
            "mortal bodies ‘our vile body’ (Philippians 3:21) sounds shocking until we restore their 1611 meanings."
        ),
        corpus=corpus,
    )

    fn_1pet2_9 = c3.cite(
        "1 Peter",
        2,
        9,
        "‘But ye are a chosen generation, a royal priesthood, an holy nation, a peculiar people.’ Translating Hebrew segullāh (Exod. 19:5; Deut. 14:2) and Greek laos eis peripoiēsin, ‘peculiar’ (from Latin peculium, private personal treasure/flock) means ‘God’s own treasured, specially purchased possession’—NOT weird or eccentric!",
    )
    fn_moro7_47 = c3.cite(
        "Moroni",
        7,
        47,
        "‘But charity is the pure love of Christ, and it endureth forever; and whoso is found possessed of it at the last day, it shall be well with him.’",
        include_1830=True,
    )
    fn_heb4_12 = c3.cite(
        "Hebrews",
        4,
        12,
        "‘For the word of God is quick, and powerful, and sharper than any twoedged sword.’ ‘Quick’ = living, alive (Greek zōn).",
    )
    fn_ps4_2 = c3.cite(
        "Psalms",
        4,
        2,
        "‘O ye sons of men, how long will ye turn my glory into shame? how long will ye love vanity, and seek after leasing?’ ‘Leasing’ (Old English lēasung) = lying, falsehood, deceit.",
    )
    fn_james5_11 = c3.cite(
        "James",
        5,
        11,
        "‘that the Lord is very pitiful, and of tender mercy.’ In 1611, ‘pitiful’ meant ‘full of pity, overflowing with compassion’—the exact opposite of modern ‘pathetic’!",
    )
    fn_phil3_21 = c3.cite(
        "Philippians",
        3,
        21,
        "‘Who shall change our vile body, that it may be fashioned like unto his glorious body.’ Translating Greek to sōma tēs tapeinōseōs hēmōn (‘the body of our humble/lowly mortal state’), ‘vile’ meant ‘humble, lowly, subject to decay’—not morally wicked or disgusting!",
    )
    fn_1ne16_10 = c3.cite(
        "1 Nephi",
        16,
        10,
        "Describing the Liahona: ‘I beheld upon the ground a round ball of curious workmanship; and it was of fine brass.’ In EME, ‘curious’ (from Latin cura, ‘care/skill’) meant ‘exquisitely wrought, artistically intricate, crafted with masterly skill’ (cf. Exod. 28:8, ‘the curious girdle of the ephod’).",
        include_1830=True,
    )

    c3.table(
        headers=["Scriptural Term", "EME Meaning", "Modern Misreading &amp; Canonical Context"],
        rows=[
            [
                f"<strong>Peculiar</strong> {fn_1pet2_9}",
                "<strong>Specially owned, private treasure, distinctive personal possession</strong>",
                "From Latin <em>peculium</em> (‘private property/cattle’). <strong>Modern Error:</strong> Assumed to mean odd, bizarre, or eccentric. A <em>“peculiar people”</em> (Exod. 19:5; Titus 2:14; 1 Pet. 2:9) is a treasured covenant people belonging exclusively to the Lord.",
            ],
            [
                f"<strong>Charity</strong> {fn_moro7_47}",
                "<strong>Pure, unconditional Christian love</strong> (Greek <em>agapē</em>, Latin <em>caritas</em>)",
                "<strong>Modern Error:</strong> Narrowed to benevolent almsgiving or tax-exempt relief organizations. As Mormon defines it in Moroni 7:47, <em>“charity is the pure love of Christ.”</em>",
            ],
            [
                f"<strong>Quick</strong> {fn_heb4_12} &amp; <strong>Lively</strong>",
                "<strong>Living, alive, animated with breath</strong>",
                "<em>“The quick and the dead”</em> (Acts 10:42; 1 Pet. 4:5; M. of F. / D&amp;C) means “the living and the dead.” Similarly, <em>“lively stones”</em> (1 Pet. 2:5) and <em>“a lively hope”</em> (1 Pet. 1:3) mean “living stones” and “a living hope.”",
            ],
            [
                "<strong>Froward</strong>",
                "<strong>Perverse, willfully contrary, ungovernable, rebellious</strong>",
                "Etymologically <em>fro-ward</em> (‘turned away from’), the exact structural opposite of <em>to-ward</em> (‘turned toward’). E.g., Prov. 3:32: <em>“For the froward is abomination to the Lord”</em>; Alma 17:14.",
            ],
            [
                f"<strong>Leasing</strong> {fn_ps4_2}",
                "<strong>Lying, deceit, or falsehood</strong>",
                "From Old English <em>lēasung</em> (‘falsehood’). Has nothing to do with renting property! E.g., Psalm 5:6: <em>“Thou shalt destroy them that speak leasing.”</em>",
            ],
            [
                "<strong>Concupiscence</strong>",
                "<strong>Ardent lust, unrestrained sensual appetite, covetous desire</strong>",
                "Used in Romans 7:8, Colossians 3:5, 1 Thessalonians 4:5, and Jacob 3:12 (<em>“fornication and lasciviousness, and every kind of sin”</em>).",
            ],
            [
                f"<strong>Pitiful</strong> {fn_james5_11}",
                "<strong>Full of compassionate pity, merciful, tenderhearted</strong>",
                "In James 5:11 (<em>“the Lord is very pitiful”</em>) and 1 Peter 3:8 (<em>“love as brethren, be pitiful, be courteous”</em>), it means deeply compassionate—never ‘contemptible’ or ‘pathetic.’",
            ],
            [
                f"<strong>Vile</strong> {fn_phil3_21} &amp; <strong>Base</strong>",
                "<strong>Lowly, humble in station, mortal, inexpensive</strong>",
                "In Philippians 3:21, <em>“our vile body”</em> translates the Greek for “the body of our humble/mortal estate.” In James 2:2, a poor man in <em>“vile raiment”</em> is simply wearing cheap, shabby clothes.",
            ],
            [
                f"<strong>Curious</strong> {fn_1ne16_10}",
                "<strong>Skillfully wrought, intricately crafted, made with great care</strong>",
                "In 1 Nephi 16:10 and Ether 10:27 (<em>“workmanship thereof was exceedingly curious”</em>), it means finely engineered or masterfully crafted—not ‘inquisitive’ or ‘strange.’ (Exception: <em>“curious arts”</em> in Acts 19:19 means occult magic/divination.)",
            ],
            [
                "<strong>Silly</strong>",
                "<strong>Helpless, innocent, undefended, gullible</strong>",
                "From Old English <em>sǣlig</em> (‘blessed → innocent → defenseless’). In Hosea 7:11 (<em>“Ephraim also is like a silly dove without heart”</em>) and 2 Timothy 3:6, it means naive/helpless.",
            ],
            [
                "<strong>Naughty</strong>",
                "<strong>Worthless, corrupt, wicked, or ruined</strong>",
                "Literally ‘of naught (nothing).’ In Jeremiah 24:2, the prophet sees a basket of <em>“very naughty figs, which could not be eaten, they were so bad”</em> (= completely rotten/ruined figs). In Proverbs 6:12, <em>“a naughty person”</em> translates <em>’ādām bəlîya‘al</em> (a man of Belial / utter wickedness).",
            ],
            [
                "<strong>Virtue</strong>",
                "<strong>Miraculous divine power, healing strength, or moral excellence</strong>",
                "From Latin <em>virtus</em> (translating Greek <em>dynamis</em>, ‘power’). When Jesus says in Luke 8:46, <em>“Somebody hath touched me: for I perceive that <strong>virtue</strong> is gone out of me,”</em> He means healing power went forth from Him—not that He lost moral purity!",
            ],
            [
                "<strong>Admiration</strong>",
                "<strong>Astonishment, amazement, or wonder</strong> (neutral or horrified, not necessarily approval)",
                "In Revelation 17:6, when John sees the great harlot of Babylon drunk with the blood of the martyrs, he writes: <em>“and when I saw her, I wondered with great <strong>admiration</strong>”</em> (= I was utterly astonished/appalled!).",
            ],
            [
                "<strong>Riot / Riotous / Rioting</strong>",
                "<strong>Dissolute, prodigal wastefulness and drunken revelry</strong>",
                "Not a violent street protest! In Luke 15:13, the Prodigal Son <em>“wasted his substance with <strong>riotous</strong> living”</em> (= extravagant, dissolute living). See also Romans 13:13 and 2 Peter 2:13.",
            ],
        ],
    )
    chapters.append(c3.build())

    # --- CHAPTER 4: CONCRETE NOUNS, ANATOMY, EVERYDAY OBJECTS & WARFARE ---
    c4 = ChapterDraft(
        chapter_id="eme-bk4-ch4",
        number=4,
        title="Chapter 4: Lexical Glossary IV — Anatomy, Food, Everyday Objects & Warfare",
        subtitle="Meat, Corn, Bowels, Reins, Besom, Shambles, Closet, Mansions, Carriage & Artillery",
        headnote=(
            "In 1611 English, a ‘meat offering’ contained no animal flesh, ‘corn’ meant wheat or barley, ‘shambles’ "
            "was a butcher’s market, ‘carriages’ were hand-luggage, and Jonathan’s ‘artillery’ was a bow and arrows."
        ),
        corpus=corpus,
    )

    fn_lev2_1 = c4.cite(
        "Leviticus",
        2,
        1,
        "‘And when any will offer a meat offering unto the Lord, his offering shall be of fine flour; and he shall pour oil upon it, and put frankincense thereon.’ A ‘meat offering’ (Hebrew minhāh) was a grain and olive-oil offering containing zero animal flesh!",
    )
    fn_alma7_12 = c4.cite(
        "Alma",
        7,
        12,
        "‘and he will take upon him their infirmities, that his bowels may be filled with mercy, according to the flesh, that he may know according to the flesh how to succor his people according to their infirmities.’",
        include_1830=True,
    )
    fn_2ne24_23 = c4.cite(
        "2 Nephi",
        24,
        23,
        "Parallel to Isaiah 14:23: ‘I will also make it a possession for the bittern, and pools of water: and I will sweep it with the besom of destruction, saith the Lord of Hosts.’ ‘Besom’ = a broom made of bundled twigs.",
        include_1830=True,
    )
    fn_1cor10_25 = c4.cite(
        "1 Corinthians",
        10,
        25,
        "‘Whatsoever is sold in the shambles, that eat, asking no question for conscience sake.’ ‘The shambles’ = the public meat market or butcher’s stalls.",
    )
    fn_1sam20_40 = c4.cite(
        "1 Samuel",
        20,
        40,
        "‘And Jonathan gave his artillery unto his lad, and said unto him, Go, carry them to the city.’ Having just shot three arrows as a signal to David, Jonathan hands his bow, quiver, and arrows (‘his artillery’, from Old French artiller, ‘to equip with projectile gear’) to his servant boy!",
    )
    fn_acts21_15 = c4.cite(
        "Acts",
        21,
        15,
        "‘And after those days we took up our carriages, and went up to Jerusalem.’ In 1611, ‘carriage’ meant ‘that which is carried’—namely, baggage, bundles, and hand-luggage! (In the 1560 Geneva Bible, this verse read ‘we trussed up our fardels’.)",
    )
    fn_john14_2 = c4.cite(
        "John",
        14,
        2,
        "‘In my Father’s house are many mansions: if it were not so, I would have told you. I go to prepare a place for you.’ Tyndale’s ‘mansions’ (from Vulgate mansiones, translating Greek monai) meant ‘dwelling rooms, abiding places, or suites within the Father’s royal household’—not separate suburban estates.",
    )

    c4.table(
        headers=["Scriptural Term", "EME Meaning", "Modern Misreading &amp; Canonical Context"],
        rows=[
            [
                f"<strong>Meat</strong> {fn_lev2_1}",
                "<strong>Solid food of any kind</strong> (as opposed to drink)",
                "From Old English <em>mete</em> (‘food, sustenance’). Animal flesh was specifically called <em>flesh</em>. Thus <em>“meat and drink”</em> means “food and drink,” <em>“sat at meat”</em> means “sat down to a meal,” and the Levitical <em>“meat offering”</em> was a grain/flour offering.",
            ],
            [
                "<strong>Corn</strong>",
                "<strong>Any cereal grain</strong> (wheat, barley, rye, oats, or New World maize)",
                "In British and Early Modern English, <em>corn</em> was the generic term for the staple grain kernel of a region (cognate with <em>kernel</em>). When Jesus’ disciples plucked <em>“ears of corn”</em> in Galilee (Matt. 12:1), they were plucking heads of wheat or barley. In the Book of Mormon (Mosiah 9:9), <em>corn</em> sits alongside wheat and barley.",
            ],
            [
                f"<strong>Bowels</strong> {fn_alma7_12}",
                "<strong>The innermost seat of tender mercy, empathy, and maternal/paternal compassion</strong>",
                "Translating Hebrew <em>raḥămîm</em> (cognate with <em>reḥem</em>, ‘womb’) and Greek <em>splanchna</em> (the inward vital organs). When scripture speaks of <em>“bowels of mercies”</em> (Col. 3:12; Alma 7:12; 34:15; D&amp;C 121:4), it denotes the deepest visceral core of Christlike compassion.",
            ],
            [
                "<strong>Reins</strong>",
                "<strong>Literally the kidneys; figuratively the deepest conscience, desires, and inner mind</strong>",
                "From Latin <em>renes</em> (‘kidneys’). In Hebrew psychology, the <em>heart</em> (<em>lēb</em>) was the seat of intellect/thought, while the <em>reins</em> (<em>kəlāyôt</em>) were the seat of deepest secret conscience: <em>“I the Lord search the heart, I try the <strong>reins</strong>”</em> (Jer. 17:10; Ps. 7:9; Rev. 2:23).",
            ],
            [
                f"<strong>Besom</strong> {fn_2ne24_23}",
                "<strong>A broom</strong> (a bundle of twigs tied around a staff for sweeping)",
                "Used in Isaiah 14:23 and 2 Nephi 24:23: <em>“I will sweep it with the <strong>besom</strong> of destruction.”</em>",
            ],
            [
                f"<strong>Shambles</strong> {fn_1cor10_25}",
                "<strong>A butcher’s meat market</strong> or slaughterhouse counter",
                "From Old English <em>scamel</em> (‘bench/table for displaying meat’). Only later did the blood and clutter of a butcher’s stall give rise to the modern idiom ‘in a shambles’ (messy chaos).",
            ],
            [
                "<strong>Closet</strong>",
                "<strong>A private inner room or bedchamber</strong>",
                "In Matthew 6:6 / 3 Nephi 13:6 (<em>“enter into thy <strong>closet</strong>, and when thou hast shut thy door, pray to thy Father”</em>), a <em>closet</em> was not a tiny wardrobe for hanging coats; in Tudor architecture it was a private study or inner room.",
            ],
            [
                f"<strong>Mansions</strong> {fn_john14_2}",
                "<strong>Abiding places, rooms, or dwelling quarters within a large household</strong>",
                "From Latin <em>manere</em> (‘to remain/abide’) and Greek <em>monai</em>. In John 14:2 and Enos 1:27, the image is of an expansive patriarchal house with ample rooms so all the Father’s children can dwell together in His presence.",
            ],
            [
                f"<strong>Carriage / Carriages</strong> {fn_acts21_15}",
                "<strong>Baggage, luggage, or portable gear carried by travelers</strong>",
                "In 1 Samuel 17:22 (<em>“David left his <strong>carriage</strong> in the hand of the keeper of the carriage”</em>) and Acts 21:15 (<em>“we took up our <strong>carriages</strong>”</em>), nobody is riding in a wheeled horse-drawn coach—they are picking up their backpacks and supplies!",
            ],
            [
                f"<strong>Artillery</strong> {fn_1sam20_40}",
                "<strong>Bows, arrows, and projectile weapons</strong>",
                "Pre-gunpowder meaning of French <em>artillerie</em>. In 1 Samuel 20:40, Jonathan’s <em>artillery</em> is his bow and quiver of arrows.",
            ],
            [
                "<strong>Habergeon</strong>, <strong>Target</strong> &amp; <strong>Greaves</strong>",
                "<strong>Coat of chainmail / armor</strong> (<em>habergeon</em>); <strong>small shield or javelin</strong> (<em>target</em>); <strong>shin-armor</strong> (<em>greaves</em>)",
                "Used in the armor descriptions of Goliath (1 Sam. 17:5–6) and throughout Old Testament and Book of Mormon military accounts.",
            ],
            [
                "<strong>Scrip</strong>",
                "<strong>A traveler’s or shepherd’s leather pouch / wallet</strong>",
                "1 Samuel 17:40 (David puts five smooth stones in his <em>scrip</em>); Matthew 10:10 (<em>“Nor <strong>scrip</strong> for your journey”</em>).",
            ],
            [
                "<strong>Cockatrice</strong>, <strong>Dragon</strong> &amp; <strong>Unicorn</strong>",
                "<strong>Venomous viper / adder</strong> (<em>cockatrice</em>); <strong>jackal, serpent, or sea monster</strong> (<em>dragon</em>); <strong>wild ox / aurochs</strong> (<em>unicorn</em>)",
                "KJV translators used heraldic European fauna terms for Hebrew animal names: <em>tannîn / tannîm</em> (‘serpent/jackal’ → <em>dragon</em>), <em>ṣepa‘</em> (‘horned viper’ → <em>cockatrice</em>, 2 Ne. 24:29; 30:14), and <em>rə’ēm</em> (‘two-horned wild ox’ → <em>unicorn</em>, Num. 23:22).",
            ],
        ],
    )
    chapters.append(c4.build())

    return Book(
        id="book-4-lexical-glossary",
        title="Book IV: Lexical Glossary of False Friends & Archaic Vocabulary",
        full_title="Book IV: The Comprehensive Lexical Glossary of Early Modern English False Friends and Archaic Scriptural Terminology",
        subtitle="Connectives, Directionals, Verbs, Moral Terms, Anatomy, Food, and Material Culture",
        chapters=chapters,
    )


def _build_book_5_hebraisms(corpus: ScriptureCorpusLookup) -> Book:
    chapters: list[Chapter] = []

    # --- CHAPTER 1: THE CONSTRUCT STATE (SMIKHUT) ---
    c1 = ChapterDraft(
        chapter_id="eme-bk5-ch1",
        number=1,
        title="Chapter 1: The Hebraic Construct State (Genitive Phrasing with ‘Of’)",
        subtitle="Why Scriptural English Says ‘Plates of Brass,’ ‘Rod of Iron,’ and ‘Words of Plainness’",
        headnote=(
            "A defining stylistic signature of both the King James Bible and the Book of Mormon is the presence of "
            "Northwest Semitic calques—syntactic structures native to Biblical Hebrew mirrored directly in English."
        ),
        corpus=corpus,
    )

    fn_1ne3_3 = c1.cite(
        "1 Nephi",
        3,
        3,
        "‘For behold, Laban hath the record of the Jews and also a genealogy of my forefathers, and they are engraven upon plates of brass.’ In standard English, one writes ‘brass plates’; in Hebrew construct syntax (luḥôt neḥōšet), the head noun precedes the material genitive (‘plates of brass’).",
        include_1830=True,
    )
    fn_1ne8_19 = c1.cite(
        "1 Nephi",
        8,
        19,
        "‘And I beheld a rod of iron, and it extended along the bank of the river, and led to the tree by which I stood.’ Compare Psalm 2:9 (‘Thou shalt break them with a rod of iron’; Hebrew šēbeṭ barzel).",
        include_1830=True,
    )
    fn_2ne31_3 = c1.cite(
        "2 Nephi",
        31,
        3,
        "‘For my soul delighteth in plainness; for after this manner doth the Lord God work among the children of men.’ Compare Jacob 4:13 (‘words of plainness’) and 1 Nephi 13:29 (‘plain and precious’).",
        include_1830=True,
    )

    c1.para(
        "Biblical Hebrew possesses relatively few true adjectives and almost never forms English-style pre-nominal "
        "compound noun phrases (like <em>“brass plates”</em> or <em>“iron rod”</em>) or Saxon <em>’s</em> possessives "
        "(like <em>“my father’s house”</em>). Instead, Northwest Semitic languages bind two or more nouns together in "
        "the <strong>construct state</strong> (Hebrew <em>smikhut</em>, סְמִיכוּת), where the first noun is phonetically "
        "shortened and bound directly to the following genitive noun—indicating material, quality, origin, or possession."
    )
    c1.callout(
        "Structural Comparison: Standard English Adjectival Syntax vs. Hebraic Construct State",
        [
            "• <strong>Standard English Adjectival / Saxon Genitive:</strong> <code>[Adjective / Possessor] + [Head Noun]</code> → <em>“Brass plates”</em> | <em>“Iron rod”</em> | <em>“Plain words”</em> | <em>“My father’s house”</em>",
            "• <strong>Hebraic Construct / Genitive Calque:</strong> <code>[Head Noun] + OF + [Modifier / Possessor Noun]</code> → <em>“Plates of brass”</em> | <em>“Rod of iron”</em> | <em>“Words of plainness”</em> | <em>“House of my father”</em>",
        ],
    )
    c1.table(
        headers=[
            "Scriptural / Hebraic Construct Form",
            "Underlying Semitic Function",
            "Standard Modern English Equivalent",
        ],
        rows=[
            [f"<em>Plates of brass</em> {fn_1ne3_3} / <em>Plates of gold</em>", "Genitive of Material", "Brass plates / Gold plates"],
            ["<em>Sword of steel</em> (1 Ne. 4:9)", "Genitive of Material", "Steel sword"],
            [f"<em>Rod of iron</em> {fn_1ne8_19} (Ps. 2:9; 1 Ne. 8:19)", "Genitive of Material", "Iron rod"],
            ["<em>Altar of stones</em> (1 Ne. 2:7)", "Genitive of Material", "Stone altar"],
            [f"<em>Words of plainness</em> {fn_2ne31_3} (Jacob 4:13)", "Attributive Genitive of Quality", "Plain words"],
            ["<em>Mist of darkness</em> (1 Ne. 8:23)", "Attributive Genitive of Quality", "Dark mist"],
            ["<em>Walls of stone</em> (Alma 48:8)", "Genitive of Material", "Stone walls"],
            ["<em>Voice of the people</em> (Mosiah 29:26)", "Subjective Genitive", "The people’s voice"],
            ["<em>House of my father</em> / <em>Land of our inheritance</em>", "Possessive Construct Chain", "My father’s house / Our inherited land"],
        ],
    )
    chapters.append(c1.build())

    # --- CHAPTER 2: NARRATIVE TEMPORAL ANCHOR (AND IT CAME TO PASS) & COGNATE ACCUSATIVES ---
    c2 = ChapterDraft(
        chapter_id="eme-bk5-ch2",
        number=2,
        title="Chapter 2: Narrative Temporal Anchors (‘And It Came to Pass’) & Cognate Accusatives",
        subtitle="Hebrew Wayəhî, Paratactic ‘And’ Chains, and ‘Dreamed a Dream’",
        headnote=(
            "Mark Twain famously joked that if ‘And it came to pass’ were removed from the Book of Mormon, it would "
            "only be a pamphlet. Yet in classical Hebrew historiography, wayəhî (‘and it came to pass’) is the mandatory "
            "grammatical hinge of past-tense narrative progression."
        ),
        corpus=corpus,
    )

    fn_gen37_5 = c2.cite(
        "Genesis",
        37,
        5,
        "‘And Joseph dreamed a dream, and he told it his brethren: and they hated him yet the more.’ Classic Hebrew cognate accusative: ַוַּיחֲלֹם יוֹסֵף חֲלוֹם (wayyaḥălōm Yôsēp ḥălôm).",
    )
    fn_1ne8_2 = c2.cite(
        "1 Nephi",
        8,
        2,
        "Lehi opens his Tree of Life account with the exact double Hebrew cognate accusative: ‘Behold, I have dreamed a dream; or, in other words, I have seen a vision.’",
        include_1830=True,
    )
    fn_jonah1_10 = c2.cite(
        "Jonah",
        1,
        10,
        "‘Then were the men exceedingly afraid’ (Hebrew wayyîrə’û hā’ănāšîm yir’āh gədôlāh = literally ‘And the men feared a great fear’, as rendered in the KJV margin and Luke 2:9!).",
    )
    fn_2ne1_7 = c2.cite(
        "2 Nephi",
        1,
        7,
        "‘wherefore, if iniquity shall abound cursed shall be the land for their sakes, but unto the righteous it shall be blessed forever.’ Compare Jacob 2:29 and Alma 37:28 (‘cursed with a sore curse’).",
        include_1830=True,
    )

    c2.subheading("1. The Narrative Temporal Anchor: ‘And It Came to Pass’ (Wayəhî)")
    c2.para(
        "In classical Biblical Hebrew narrative prose (Genesis through 2 Kings), sequential past events are introduced "
        "by the <em>waw</em>-consecutive (converted imperfect) form of the verb ‘to be’ (<em>hāyāh</em>): "
        "<strong>וַיְהִי</strong> (<em>wayəhî</em>), literally translated <em>“and it was”</em> or <em>“and it came to "
        "pass”</em> (alongside its prophetic future counterpart <strong>וְהָיָה</strong>, <em>wəhāyāh</em>, "
        "<em>“and it shall come to pass”</em>)."
    )
    c2.callout(
        "Why Scriptural Prose Preserves ‘And It Came to Pass’",
        [
            "• <strong>Discourse Transition Marker:</strong> In ancient Hebrew and Egyptian (which lacked modern punctuation marks, paragraph indentations, and chapter breaks), <em>wayəhî</em> functioned as a structural scene-change and chronological advancement marker.",
            "• <strong>Polysyndeton (Parataxis):</strong> Whereas Greek and Latin prose subordinates clauses using complex participles (hypotaxis), Hebrew links clauses end-to-end with the prefix <strong>וְ</strong> (<em>wa- / we-</em>, ‘and’). This explains why almost every verse in KJV historical books and the Book of Mormon begins with <em>And</em>, <em>But</em>, <em>For</em>, or <em>Now</em>.",
        ],
    )

    c2.subheading("2. Cognate Accusatives (Internal Objects)")
    c2.para(
        "Semitic syntax regularly intensifies a verb by placing a noun derived from the <strong>exact same triliteral "
        "root</strong> directly after the verb as its internal direct object (the <strong>cognate accusative</strong>). "
        "Modern English teachers normally red-pencil this as redundant, preferring an adverb (<em>“I dreamed vividly”</em> "
        "or <em>“They were terrified”</em>), but scriptural English preserves the nominal Hebrew emphasis:"
    )
    c2.table(
        headers=["Scriptural Cognate Accusative", "Shared Root Pattern", "Canonical Citations"],
        rows=[
            [f"<em>“I have <strong>dreamed a dream</strong>”</em> {fn_gen37_5} {fn_1ne8_2}", "Verb <em>dream</em> + Noun <em>dream</em>", "Gen. 37:5; Dan. 2:3; 1 Ne. 8:2"],
            [f"<em>“They <strong>feared a great fear</strong>”</em> {fn_jonah1_10}", "Verb <em>fear</em> + Noun <em>fear</em>", "Ps. 14:5; Jonah 1:10 (Heb.); Mark 4:41; Luke 2:9 (Grk.)"],
            ["<em>“<strong>Judge</strong> righteous <strong>judgment</strong>”</em>", "Verb <em>judge</em> + Noun <em>judgment</em>", "John 7:24; Mosiah 29:12; Moroni 7:18"],
            [f"<em>“<strong>Cursed</strong> with a sore/grievous <strong>curse</strong>”</em> {fn_2ne1_7}", "Verb <em>curse</em> + Noun <em>curse</em>", "Mal. 3:9; 1 Kgs. 2:8; Jacob 3:3; Alma 37:28"],
            ["<em>“<strong>Work a work</strong> in your days”</em>", "Verb <em>work</em> + Noun <em>work</em>", "Hab. 1:5; Acts 13:41; 1 Ne. 14:7; 3 Ne. 21:9"],
            ["<em>“<strong>Sinned a great sin</strong>”</em>", "Verb <em>sin</em> + Noun <em>sin</em>", "Exod. 32:30–31"],
            ["<em>“<strong>Dying thou shalt die</strong>”</em> → <em>“Thou shalt <strong>surely die</strong>”</em>", "Hebrew <strong>Infinitive Absolute</strong> (<em>môt tāmût</em>) preceding finite verb of same root", "Gen. 2:17; 2 Ne. 2:15; Heb. 6:14 (<em>“Blessing I will bless thee”</em>)"],
        ],
    )
    chapters.append(c2.build())

    # --- CHAPTER 3: RESUMPTIVE PRONOUNS, ABSTRACT PLURALS & COMPOUND PREPOSITIONS ---
    c3 = ChapterDraft(
        chapter_id="eme-bk5-ch3",
        number=3,
        title="Chapter 3: Resumptive Pronouns, Abstract Plurals & Compound Prepositions",
        subtitle="Casus Pendens, Plural of Majesty/Intensity, and ‘By the Hand Of’",
        headnote=(
            "Why does Nephi write ‘And I, Nephi, being exceedingly young, nevertheless I was large in stature’? "
            "And why does scripture pluralize abstract nouns like ‘mercies,’ ‘condescensions,’ and ‘salvations’?"
        ),
        corpus=corpus,
    )

    fn_1ne2_16 = c3.cite(
        "1 Nephi",
        2,
        16,
        "Left-dislocation (casus pendens) with a resumptive pronoun after an intervening clause: ‘And it came to pass that I, Nephi, being exceedingly young, nevertheless being large in stature, and also having great desires to know of the mysteries of God, wherefore, I did cry unto the Lord.’",
        include_1830=True,
    )
    fn_1ne4_12 = c3.cite(
        "1 Nephi",
        4,
        12,
        "In the 1830 Palmyra edition, 1 Nephi 4:12 read: ‘And it came to pass that the Spirit said unto me again: Slay him, for the Lord hath delivered him into thy hands; Behold the Lord slayeth the wicked to bring forth his righteous purposes.’ Elsewhere (such as 1830 1 Nephi 17:52; Helaman 16:12), resumptive subject pronouns (‘the Lord, he…’) abound.",
        include_1830=True,
    )
    fn_1ne1_14 = c3.cite(
        "1 Nephi",
        1,
        14,
        "Abstract plural of intensity: ‘Great and marvelous are thy works, O Lord God Almighty! Thy throne is high in the heavens, and thy power, and goodness, and mercy are over all the inhabitants of the earth; and, because thou art merciful, thou wilt not suffer those who come unto thee that they shall perish!’ (Compare Lam. 3:22, ‘the Lord’s mercies’ = ḥăsādîm, and 1 Ne. 19:10, ‘condescensions’ in the Original MS).",
        include_1830=True,
    )
    fn_mosiah2_11 = c3.cite(
        "Mosiah",
        2,
        11,
        "Compound body-part prepositions (‘by the hand of the Lord’, translating Hebrew bəyad YHWH): ‘I was chosen by this people, and consecrated by my father, and was suffered by the hand of the Lord that I should be a ruler and a king over this people.’",
        include_1830=True,
    )

    c3.subheading("1. Resumptive & Pleonastic Pronouns (Casus Pendens)")
    c3.para(
        "Because Biblical Hebrew relative clauses (introduced by the indeclinable particle <em>’ăšer</em>, אֲשֶׁר) and "
        "long topicalized openings (<em>casus pendens</em> / left-dislocation) cannot inflect for case on the relative "
        "marker itself, Hebrew grammar places a <strong>resumptive pronoun</strong> inside the main clause to pick up "
        f"the subject or object {fn_1ne2_16} {fn_1ne4_12}:"
    )
    c3.callout(
        "Examples of Resumptive &amp; Pleonastic Pronouns in KJV &amp; 1830 Book of Mormon",
        [
            "• <em>“And the Lord, <strong>he</strong> shall lead thee”</em> (Deut. 31:8: <em>“And the Lord, <strong>he</strong> it is that doth go before thee”</em>).",
            "• <em>“As for God, <strong>his</strong> way is perfect”</em> (Ps. 18:30).",
            "• <em>“And I, Nephi, being exceedingly young, nevertheless… <strong>I</strong> did cry unto the Lord”</em> (1 Ne. 2:16).",
            "• In the 1830 Palmyra Book of Mormon, dozens of pure Hebraic resumptive pronouns were printed verbatim (e.g., <em>“Zeniff, he being over-zealous…”</em>; <em>“their sons and their daughters, they did…”</em>), many of which were smoothed out in the 1837 and 1920 editions to conform to standard schoolroom English.",
        ],
    )

    c3.subheading("2. Pluralization of Abstract Concepts")
    c3.para(
        "Biblical Hebrew regularly pluralizes abstract nouns—not because there are multiple separate items, but to "
        "express <strong>intensity, abundance, totality, or divine majesty</strong> (the <em>pluralis intensivus</em>). "
        f"This carries directly into Early Modern scriptural prose {fn_1ne1_14}:"
    )
    c3.table(
        headers=["Scriptural Abstract Plural", "Underlying Hebrew Concept", "Meaning in Context"],
        rows=[
            ["<strong>Mercies / Tender mercies</strong>", "<em>ḥăsādîm</em> (חֲסָדִים) / <em>raḥămîm</em> (רַחֲמִים)", "Abundant, covenantal lovingkindness and deep compassion (Ps. 89:1; 1 Ne. 1:20)"],
            ["<strong>Condescensions</strong>", "Plural of majesty / repeated grace", "The manifold gracious acts of God descending to aid humanity (1 Ne. 19:10 OMS)"],
            ["<strong>Righteousnesses</strong>", "<em>ṣədāqôt</em> (צְדָקוֹת)", "Mighty saving acts of covenant justice (Isa. 64:6; Dan. 9:18)"],
            ["<strong>Statures / Releases / Salvations</strong>", "<em>yəšû‘ôt</em> (יְשׁוּעוֹת)", "Complete, multifaceted deliverance and stature"],
        ],
    )

    c3.subheading("3. Compound Body-Part Prepositions")
    c3.para(
        "Where English uses simple abstract prepositions (<em>through, before, according to, from</em>), Biblical "
        f"Hebrew constructs compound prepositions out of human anatomy {fn_mosiah2_11}:"
    )
    c3.table(
        headers=["Hebraic Anatomical Preposition", "Hebrew Equivalent", "Idiomatic Meaning"],
        rows=[
            ["<strong>By the hand of</strong>", "<em>bəyad</em> (בְּיַד)", "<strong>Through the agency / instrumentality of</strong> (<em>“spoken by the hand of Moses”</em>)"],
            ["<strong>Before the face of</strong>", "<em>lipnê</em> (לִפְנֵי)", "<strong>In the presence of / Before</strong>"],
            ["<strong>In the eyes of</strong>", "<em>bə‘ênê</em> (בְּעֵינֵי)", "<strong>In the judgment / estimation of</strong> (<em>“find grace in the eyes of the Lord”</em>)"],
            ["<strong>Out of the mouth of</strong>", "<em>mippî</em> (מִפִּי)", "<strong>Spoken / testified by</strong>"],
        ],
    )
    chapters.append(c3.build())

    return Book(
        id="book-5-semitic-calques",
        title="Book V: Structural Semitic Calques & Hebraisms",
        full_title="Book V: Structural Semitic Calques and Hebraisms in the King James Bible and the Book of Mormon",
        subtitle="The Construct State, Narrative Wayəhî, Cognate Accusatives, Resumptive Pronouns & Abstract Plurals",
        chapters=chapters,
    )


def _build_book_6_matrices_and_walkthroughs(corpus: ScriptureCorpusLookup) -> Book:
    chapters: list[Chapter] = []

    # --- CHAPTER 1: PRACTICAL REFERENCE MATRIX ---
    c1 = ChapterDraft(
        chapter_id="eme-bk6-ch1",
        number=1,
        title="Chapter 1: Master Quick-Reference Matrix — Common Errors at a Glance",
        subtitle="Thirty-Two High-Frequency Scriptural Expressions Decoded Side by Side",
        headnote=(
            "Use this rapid-lookup diagnostic matrix whenever a familiar word or clause in the King James Bible or "
            "Book of Mormon seems puzzling or counterintuitive."
        ),
        corpus=corpus,
    )

    c1.table(
        headers=[
            "If the Text Reads:",
            "Readers Often Mistakenly Think It Means:",
            "The Actual Early Modern Grammatical / Lexical Meaning Is:",
        ],
        rows=[
            ["<strong>“Wherefore”</strong>", "“Where?” or “From where?”", "<strong>“Why?”</strong>, <strong>“For what reason?”</strong>, or <strong>“Therefore”</strong>"],
            ["<strong>“Thou art”</strong>", "A royal, distant, high-status address to a monarch", "<strong>“You are” (Intimate / singular)</strong>, speaking to an individual, child, or close friend"],
            ["<strong>“Ye are”</strong>", "Archaic singular (“Old-fashioned you”)", "<strong>“All of you are” (Plural subject)</strong>, addressing a crowd or group"],
            ["<strong>“Thine eyes / Mine heart”</strong>", "Fancy poetic or random inflection", "Phonological rule: <strong>“Your eyes / My heart”</strong> (<em>thine/mine</em> before a vowel or weak <em>h</em>)"],
            ["<strong>“Suffer them”</strong>", "Make them feel misery or physical pain", "<strong>“Allow them”</strong> or <strong>“Permit them”</strong>"],
            ["<strong>“Shall not prevent them”</strong>", "Shall not stop or block them", "<strong>“Shall not precede / go ahead of them”</strong> (Latin <em>praevenire</em>)"],
            ["<strong>“Was let hitherto”</strong>", "Was allowed up to now", "<strong>“Was hindered / obstructed up to now”</strong> (Old English <em>lettan</em>)"],
            ["<strong>“He is come / He is risen”</strong>", "Broken grammar or passive tense", "Perfect aspect of motion: <strong>“He has arrived / He has risen”</strong>"],
            ["<strong>“Our Father which…”</strong>", "Dehumanizing God as an inanimate object", "EME convention: <strong>“Which” referred universally to people, angels, and things</strong>"],
            ["<strong>“Peculiar people”</strong>", "A strange, weird, or eccentric group", "<strong>“A treasured personal possession / covenant property”</strong> (Latin <em>peculium</em>)"],
            ["<strong>“Exceeding glad / Sore afraid”</strong>", "Missing a word or suffix", "Flat adverbs: <strong>“Exceedingly glad / Severely afraid”</strong>"],
            ["<strong>“He did build / They did travel”</strong>", "Heavy, defensive emphasis (“He <em>really</em> built it!”)", "Unemphatic past narrative: <strong>“He built / They traveled”</strong>"],
            ["<strong>“Chaste conversation”</strong>", "Polite verbal small talk", "<strong>“Pure moral conduct, lifestyle, and citizenship”</strong>"],
            ["<strong>“Be careful for nothing”</strong>", "Be careless or reckless", "<strong>“Do not be anxious or worried about anything”</strong>"],
            ["<strong>“Take no thought”</strong>", "Never plan ahead or think", "<strong>“Do not be consumed with crippling anxiety”</strong>"],
            ["<strong>“The Lord is very pitiful”</strong>", "Pathetic or weak", "<strong>“Overflowing with compassionate pity and tender mercy”</strong>"],
            ["<strong>“Our vile body”</strong>", "Our wicked, loathsome body", "<strong>“Our humble, lowly mortal body”</strong> (Phil. 3:21)"],
            ["<strong>“Curious workmanship”</strong>", "Odd or puzzling design", "<strong>“Exquisitely wrought, masterfully crafted workmanship”</strong>"],
            ["<strong>“The quick and the dead”</strong>", "The fast-moving and the dead", "<strong>“The living and the dead”</strong>"],
            ["<strong>“Meat offering”</strong>", "Animal flesh sacrifice", "<strong>“Grain, flour, and olive-oil offering”</strong> (<em>meat</em> = solid food)"],
            ["<strong>“Ears of corn”</strong>", "New World sweet maize on the cob", "<strong>“Heads of grain (wheat or barley)”</strong>"],
            ["<strong>“How long halt ye”</strong>", "How long will you stand still", "<strong>“How long will you limp/falter unsteadily”</strong> between two allegiances"],
            ["<strong>“Wot not / Wist not”</strong>", "Wanted not / Wished not", "<strong>“Know not / Knew not”</strong> (from the verb <em>to wit</em>)"],
            ["<strong>“Anon / Presently / By and by”</strong>", "After a while / Eventually", "<strong>“Immediately / Instantly / At once”</strong>"],
            ["<strong>“Whither / Whence”</strong>", "Both mean “Where?”", "<strong>“To where?”</strong> (<em>whither</em>) vs. <strong>“From where?”</strong> (<em>whence</em>)"],
            ["<strong>“Bowels of mercy”</strong>", "Crude anatomical reference", "Semitic idiom: <strong>“The deepest inner seat of tender compassion”</strong>"],
            ["<strong>“Seek after leasing”</strong>", "Renting property or land", "<strong>“Pursuing lies, deceit, and falsehood”</strong> (Ps. 4:2)"],
            ["<strong>“Sold in the shambles”</strong>", "Sold in a chaotic ruin", "<strong>“Sold in the public butcher’s meat market”</strong> (1 Cor. 10:25)"],
            ["<strong>“Took up our carriages”</strong>", "Boarded horse-drawn coaches", "<strong>“Picked up our hand-luggage / baggage”</strong> (Acts 21:15)"],
            ["<strong>“Jonathan’s artillery”</strong>", "Cannons or heavy weaponry", "<strong>“Jonathan’s bow, quiver, and arrows”</strong> (1 Sam. 20:40)"],
            ["<strong>“Condescension of God”</strong>", "Patronizing superiority", "<strong>“God’s gracious voluntary descent from heaven to redeem the lowly”</strong>"],
            ["<strong>“If thou be / Though he slay”</strong>", "Uninflected grammar error", "<strong>Early Modern English Subjunctive Mood</strong> in conditional/concessive clauses"],
        ],
    )
    chapters.append(c1.build())

    # --- CHAPTER 2: ANNOTATED PASSAGE WALKTHROUGHS ---
    c2 = ChapterDraft(
        chapter_id="eme-bk6-ch2",
        number=2,
        title="Chapter 2: Line-by-Line Linguistic Walkthroughs of Famous Passages",
        subtitle="Applying Pronominal, Verbal, Lexical & Hebraic Analysis to Canonical Texts",
        headnote=(
            "To see how every principle in this manual works together in real time, let us walk through four "
            "landmark scriptural passages with interactive pop-up annotations."
        ),
        corpus=corpus,
    )

    fn_w1 = c2.cite(
        "Matthew",
        6,
        6,
        "‘But thou [2nd-person singular subject: addressing the individual disciple], when thou prayest [2nd-person singular present indicative -est], enter into thy [prevocalic rule: consonant c-] closet [Tudor private inner chamber], and when thou hast [2nd-person singular perfect auxiliary] shut thy door, pray to thy Father which [personal relative pronoun] is in secret.’ (Compare 3 Nephi 13:6.)",
    )
    fn_w2 = c2.cite(
        "1 Nephi",
        11,
        17,
        "‘And I said unto him: I know that he loveth [3rd-person singular present indicative -eth] his children; nevertheless, I do not know the meaning of all things.’ In v. 16, the angel asks: ‘Knowest thou [direct verb-inversion question without do-support + 2nd-person singular -est] the condescension [gracious voluntary descent] of God?’",
        include_1830=True,
    )
    fn_w3 = c2.cite(
        "Mosiah",
        4,
        16,
        "‘And also, ye [2nd-person plural nominative subject] yourselves will succor those that stand in need of your succor; ye will administer of your substance unto him that standeth [3rd-person singular -eth] in need; and ye will not suffer [EME verb: permit/allow] that the beggar putteth up his petition to you [2nd-person plural object] in vain.’",
        include_1830=True,
    )
    fn_w4 = c2.cite(
        "1 Corinthians",
        13,
        4,
        "‘Charity [pure covenant love of Christ, Greek agapē] suffereth long [endures patiently], and is kind; charity envieth not [post-verbal negation without do-support]; charity vaunteth not itself, is not puffed up.’ And in v. 12: ‘For now we see through a glass [polished bronze mirror], darkly; but then face to face: now I know in part; but then shall I know even as also I am known.’",
    )

    c2.subheading("Walkthrough 1: Secret Prayer & The Sermon on the Mount (Matthew 6:6 / 3 Nephi 13:6)")
    c2.callout(
        "Annotated Text & Grammatical Breakdown",
        [
            f"<strong>Text:</strong> <em>“But <strong>thou</strong>, when <strong>thou prayest</strong>, enter into <strong>thy closet</strong>, and when <strong>thou hast</strong> shut <strong>thy</strong> door, pray to <strong>thy</strong> Father <strong>which</strong> is in secret; and <strong>thy</strong> Father <strong>which seeth</strong> in secret shall reward <strong>thee</strong> openly.”</em> {fn_w1}",
            "• <strong>Thou / Thy / Thee:</strong> In Matthew 6:5, Jesus warned against the hypocrites using plural <em>ye/you</em>. In verse 6, He deliberately switches to singular <em>thou/thy/thee</em> so that secret prayer is framed as a solitary, one-on-one encounter between one child and the Father.",
            "• <strong>Closet:</strong> Not a clothes cupboard, but a private Tudor inner chamber or study.",
            "• <strong>Father which:</strong> Standard EME personal relative <em>which</em> referring to God.",
        ],
    )

    c2.subheading("Walkthrough 2: Nephi’s Vision & The Condescension of God (1 Nephi 11:16–17)")
    c2.callout(
        "Annotated Text & Grammatical Breakdown",
        [
            f"<strong>Text:</strong> <em>“And he said unto me: <strong>Knowest thou</strong> the <strong>condescension of God</strong>? And I said unto him: I know that he <strong>loveth</strong> his children; nevertheless, I do not know the meaning of all things.”</em> {fn_w2}",
            "• <strong>Knowest thou:</strong> Direct verb-subject inversion forming a question without modern dummy <em>do</em>-support (“Do you know…?”), inflected with 2nd-person singular <em>-est</em>.",
            "• <strong>Condescension of God:</strong> Both a lexical false friend (<em>condescension</em> = gracious voluntary descent from heavenly majesty to dwell among mortals) and a Hebraic genitive construct phrase.",
        ],
    )

    c2.subheading("Walkthrough 3: King Benjamin on Succoring the Poor (Mosiah 4:16)")
    c2.callout(
        "Annotated Text & Grammatical Breakdown",
        [
            f"<strong>Text:</strong> <em>“And also, <strong>ye</strong> yourselves will <strong>succor</strong> those that stand in need of <strong>your</strong> succor; <strong>ye</strong> will administer of <strong>your</strong> substance unto him that <strong>standeth</strong> in need; and <strong>ye</strong> will not <strong>suffer</strong> that the beggar <strong>putteth</strong> up his petition to <strong>you</strong> in vain…”</em> {fn_w3}",
            "• <strong>Ye vs. You:</strong> Notice the impeccable case grammar: plural nominative <em>ye</em> is used three times for the subject of the verbs (<em>ye will succor, ye will administer, ye will not suffer</em>), while plural objective <em>you</em> is used after the preposition <em>to</em> (<em>to you</em>)!",
            "• <strong>Succor:</strong> From Latin <em>succurrere</em> (‘to run to the aid of / relieve in distress’).",
            "• <strong>Suffer:</strong> Means <em>permit</em> or <em>allow</em> (“you will not allow the beggar’s petition to go in vain”).",
        ],
    )

    c2.subheading("Walkthrough 4: Paul’s Hymn to Charity (1 Corinthians 13:4–12 & Moroni 7:45–47)")
    c2.callout(
        "Annotated Text & Grammatical Breakdown",
        [
            f"<strong>Text:</strong> <em>“<strong>Charity suffereth</strong> long, and is kind; charity <strong>envieth not</strong>; charity <strong>vaunteth not</strong> itself… For now we see through a <strong>glass</strong>, darkly…”</em> {fn_w4}",
            "• <strong>Charity:</strong> Pure, covenantal Christlike love (Greek <em>agapē</em>), not merely donating to the poor (which v. 3 explicitly contrasts with charity: <em>“though I bestow all my goods to feed the poor… and have not charity, it profiteth me nothing”</em>!).",
            "• <strong>Envieth not / Vaunteth not:</strong> EME third-person singular <em>-eth</em> combined with post-verbal negation (no <em>does not</em>).",
            "• <strong>Through a glass, darkly:</strong> In 1611, a <em>glass</em> meant a <strong>looking-glass (mirror)</strong> made of polished Corinthian bronze, not a windowpane or magnifying lens! And <em>darkly</em> translates Greek <em>en ainigmati</em> (‘in a riddle / dim reflection’).",
        ],
    )
    chapters.append(c2.build())

    return Book(
        id="book-6-reference-matrices-and-walkthroughs",
        title="Book VI: Practical Reference Matrices & Passage Walkthroughs",
        full_title="Book VI: Practical Reference Matrices and Line-by-Line Linguistic Walkthroughs of Canonical Passages",
        subtitle="Common Misreadings at a Glance & Annotated Case Studies from the KJV and Book of Mormon",
        chapters=chapters,
    )


def ingest_early_modern_english_guide() -> Work:
    """Compile the complete 6-Book Early Modern English Scriptural Reference Manual into a normalized `Work`."""
    corpus = ScriptureCorpusLookup()

    front_matter = _build_front_matter(corpus)
    books = [
        _build_book_1_pronouns(corpus),
        _build_book_2_verbs(corpus),
        _build_book_3_syntax(corpus),
        _build_book_4_glossary(corpus),
        _build_book_5_hebraisms(corpus),
        _build_book_6_matrices_and_walkthroughs(corpus),
    ]

    return Work(
        id="early-modern-english-scripture-guide",
        title="An Early Modern English Guide to Reading the Scriptures",
        subtitle=(
            "A Philological Reference Manual to the Pronouns, Verbal Morphology, Syntax, False Friends, "
            "and Semitic Idioms of the King James Bible and the Book of Mormon"
        ),
        authors=["Proteus Scriptorium Philological Press"],
        edition_label="Proteus Philological & Scriptural Reference Edition",
        description=(
            "Comprehensive 6-division reference guide to reading Early Modern English in the 1611 King James "
            "Bible and the 1830/2013 Book of Mormon, covering the pronoun system and T-V distinction (thou/thee "
            "vs. ye/you), verbal morphology (-est, -eth, dost vs. doest, subjunctive mood, and be-perfects of "
            "motion), syntactic structures, Royal Skousen's Critical Text Project findings, an extensive lexical "
            "glossary of archaic 'false friends', structural Semitic calques (Hebraisms), and interactive Kindle "
            "pop-up scripture citations."
        ),
        subjects=[
            "English language — Early modern, 1500-1700 — Grammar",
            "Bible. English — Authorized — Language, style",
            "Book of Mormon — Language, style",
            "Hebrew language — Idioms",
        ],
        front_matter=front_matter,
        books=books,
        css_theme="classic.css",
    )


build_early_modern_english_scripture_guide = ingest_early_modern_english_guide

