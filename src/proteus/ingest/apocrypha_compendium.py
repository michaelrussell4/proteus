"""The Complete Apocrypha & Pseudepigrapha Mega-Compendium Ingester (`apocrypha_compendium.py`).

Unites and deduplicates all non-canonical ancient and historical biblical texts across:
1. `data/raw/extra-canon/*.jsonl` (15 KJV Deuterocanonical books)
2. `data/raw/apocrypha/*.jsonl` (ISTA Pseudepigrapha, Forgotten Books of Eden, Lost Books of the Bible, Nag Hammadi & Apostolic Fathers)
3. `data/raw/gutenberg-apocrypha/*.jsonl` (Laurence 105-ch 1 Enoch & Ante-Nicene Fathers Volume 8 unique Apocrypha/Pseudepigrapha)

Every work in the compendium includes a researched **"Source, Provenance & Historical Veracity Dossier"**
detailing its date of composition, manuscript tradition, translator, and critical scholarly evaluation
of its historical authenticity and Latter-day Saint reception.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from proteus.core.models import (
    Annotation,
    BlockType,
    Book,
    Chapter,
    ContentBlock,
    Work,
)
from proteus.core.references import slugify
from proteus.core.typography import clean_prose_text, escape_xhtml
from proteus.ingest.apocrypha import (
    KJV_APOCRYPHA_ORDER,
    ingest_gutenberg_enoch_laurence,
    ingest_ista_jsonl_book,
    ingest_kjv_apocrypha,
)


@dataclass
class ProvenanceDossier:
    date_and_origin: str
    manuscripts_and_language: str
    translation_source: str
    veracity_and_assessment: str


# Comprehensive scholarly provenance & veracity database keyed by normalized work key
PROVENANCE_DATABASE: dict[str, ProvenanceDossier] = {
    # --- DIVISION I: KJV DEUTEROCANON (15 BOOKS) ---
    "1-esdras": ProvenanceDossier(
        date_and_origin="c. 150–100 BC (Hellenistic Judea or Alexandria).",
        manuscripts_and_language="Compiled in Koine Greek from Hebrew/Aramaic sources; preserved in the Septuagint (Codices Vaticanus and Alexandrinus).",
        translation_source="1611 Authorized King James Version Apocrypha.",
        veracity_and_assessment="Presents an alternative Greek parallel to 2 Chronicles 35–36, Ezra, and Nehemiah, adding the famous Hellenistic 'Contest of the Three Bodyguards' of King Darius (ch. 3–4: 'Great is Truth, and mighty above all things'). Valued by Josephus as a literary source, though its chronology conflates Persian kings; per D&C 91, it contains historical and moral truth mixed with later scribal interpolation.",
    ),
    "2-esdras": ProvenanceDossier(
        date_and_origin="Core Jewish Apocalypse (4 Ezra, ch. 3–14) written c. AD 90–100 after the Roman destruction of Jerusalem; Christian framework (2 Ezra ch. 1–2 and 6 Ezra ch. 15–16) added in the 2nd–3rd centuries AD.",
        manuscripts_and_language="Core composed in Hebrew or Aramaic, translated into Greek, and preserved complete in Latin, Syriac, Ethiopic, Arabic, and Armenian versions.",
        translation_source="1611 Authorized King James Version Apocrypha (translated from the Latin Vulgate Appendix).",
        veracity_and_assessment="Pseudepigraphally attributed to Ezra the Scribe. Not a historical record of the 5th century BC, but one of the most profound Jewish apocalyptic Theodicies of the 1st century AD, wrestling with why God permits the righteous to suffer and describing the restoration of twenty-four canonical books plus seventy esoteric books reserved for the wise (2 Esdras 14). Note also its famous reference to the Ten Tribes migrating to 'Arsareth' (13:40–45).",
    ),
    "tobit": ProvenanceDossier(
        date_and_origin="c. 225–175 BC (Eastern Diaspora or Hellenistic Palestine).",
        manuscripts_and_language="Composed in Aramaic (four Aramaic and one Hebrew fragment discovered in Qumran Cave 4: 4Q196–200); preserved complete in Greek Septuagint codices.",
        translation_source="1611 Authorized King James Version Apocrypha.",
        veracity_and_assessment="A didactic religious novella set during the 8th-century BC Assyrian exile. While containing geographical and historical anachronisms proving it is pious wisdom fiction rather than a contemporary chronicle, its Qumran fragments confirm its authentic Second Temple Jewish antiquity and rich angelology (Raphael) and family piety.",
    ),
    "judith": ProvenanceDossier(
        date_and_origin="c. 150–100 BC (Hasmonean Judea).",
        manuscripts_and_language="Composed in Hebrew or Greek; preserved in the Greek Septuagint, Old Latin, and Syriac Peshitta.",
        translation_source="1611 Authorized King James Version Apocrypha.",
        veracity_and_assessment="A patriotic historical parable rather than literal history: its opening verse intentionally blends eras by calling 'Nebuchadnezzar' the king of the 'Assyrians' reigning in 'Nineveh' after the return from exile. Composed during the Maccabean era to inspire Jewish covenant fidelity and courage against foreign tyranny.",
    ),
    "additions-to-esther": ProvenanceDossier(
        date_and_origin="c. 140–114 BC (Hellenistic Egypt / Alexandria).",
        manuscripts_and_language="Composed in Koine Greek as six expansions interspersed throughout the Septuagint Book of Esther.",
        translation_source="1611 Authorized King James Version Apocrypha (following Jerome's Vulgate placement as Chapters 10:4–16:24).",
        veracity_and_assessment="Because the Hebrew canonical Book of Esther never explicitly mentions the name of God or prayer, Hellenistic Jewish editors added Mordecai's dream, royal edicts, and the prayers of Mordecai and Esther. Secondary pious expansions rather than original Persian-period archives.",
    ),
    "wisdom-of-solomon": ProvenanceDossier(
        date_and_origin="c. 50 BC – AD 40 (Alexandria, Egypt).",
        manuscripts_and_language="Composed directly in sophisticated rhetorical Koine Greek; preserved in major Septuagint uncials.",
        translation_source="1611 Authorized King James Version Apocrypha.",
        veracity_and_assessment="Pseudepigraphally attributed to King Solomon as a literary device, though written nine centuries after Solomon by an Alexandrian Jewish philosopher. Highly significant for Second Temple theology on immortality, the pre-existence of the soul (Wisdom 8:19–20), and personified Divine Wisdom (Sophia).",
    ),
    "sirach": ProvenanceDossier(
        date_and_origin="Written in Hebrew c. 190–180 BC in Jerusalem by Yeshua ben Eleazar ben Sira; translated into Greek in Egypt by his grandson in 132 BC.",
        manuscripts_and_language="Original Hebrew (~68% recovered from the Cairo Genizah, Masada, and Qumran); complete text in the Greek Septuagint.",
        translation_source="1611 Authorized King James Version Apocrypha.",
        veracity_and_assessment="Authentic, non-pseudepigraphic Second Temple Jewish wisdom treatise by a named Jerusalem scribe. One of the most historically reliable and earliest extra-canonical witnesses to Jewish liturgy, ethics, and the 'Praise of the Fathers' (ch. 44–50).",
    ),
    "baruch": ProvenanceDossier(
        date_and_origin="Composite work compiled c. 200–60 BC from earlier Hebrew and Greek units.",
        manuscripts_and_language="Preserved in the Greek Septuagint; Parts 1–2 likely translated from a Hebrew original.",
        translation_source="1611 Authorized King James Version Apocrypha.",
        veracity_and_assessment="Attributed to Baruch ben Neriah, scribe of Jeremiah (6th century BC), though compiled in the Hellenistic period combining penitential liturgy, a wisdom poem, and prophetic consolation modeled on Deutero-Isaiah.",
    ),
    "letter-of-jeremiah": ProvenanceDossier(
        date_and_origin="c. 300–100 BC (Babylonian Diaspora or Hellenistic Judea).",
        manuscripts_and_language="Composed in Hebrew, Aramaic, or Greek; a Greek fragment (7Q2) was discovered among the Dead Sea Scrolls at Qumran.",
        translation_source="1611 Authorized King James Version Apocrypha (often appended as Baruch Chapter 6).",
        veracity_and_assessment="An extended homiletic satire against Babylonian idolatry inspired by Jeremiah 10:11 and 29:1. While framed as a letter from Jeremiah to the captives entering Babylon, scholars date it to the late Persian or early Hellenistic period.",
    ),
    "prayer-of-azariah": ProvenanceDossier(
        date_and_origin="c. 2nd century BC (Hellenistic Judea).",
        manuscripts_and_language="Likely composed in Hebrew or Aramaic; preserved in the Septuagint and Theodotion Greek texts of Daniel 3.",
        translation_source="1611 Authorized King James Version Apocrypha ('The Song of the Three Holy Children').",
        veracity_and_assessment="Liturgical hymn and penitential prayer inserted into Daniel 3 between verses 23 and 24 while Shadrach, Meshach, and Abednego walk in the fiery furnace. Second Temple liturgical expansion rather than part of the Masoretic Hebrew/Aramaic Book of Daniel.",
    ),
    "susanna": ProvenanceDossier(
        date_and_origin="c. 150–100 BC.",
        manuscripts_and_language="Preserved in two Greek recensions (Old Greek Septuagint and Theodotion), placed before Daniel 1 or as Daniel 13.",
        translation_source="1611 Authorized King James Version Apocrypha.",
        veracity_and_assessment="A court tale celebrating the young Daniel's inspired judicial cross-examination in rescuing the innocent Susanna from two corrupt elders. Contains famous Greek wordplay on tree names (mastich/schinos and holm-oak/prinos), indicating Greek literary composition or heavy Greek reworking.",
    ),
    "bel-and-the-dragon": ProvenanceDossier(
        date_and_origin="c. 150–100 BC.",
        manuscripts_and_language="Preserved in Old Greek and Theodotion Greek as Daniel 14.",
        translation_source="1611 Authorized King James Version Apocrypha.",
        veracity_and_assessment="Two polemical tales mocking Babylonian idol worship (exposing the priests of Bel who secretly eat the idol's offerings, and slaying a revered serpent/dragon). Popular Second Temple apologetic folklore.",
    ),
    "prayer-of-manasseh": ProvenanceDossier(
        date_and_origin="c. 2nd–1st century BC (or 1st century AD).",
        manuscripts_and_language="Composed in Greek (or Semitic original); preserved in the Syriac Didascalia Apostolorum, Apostolic Constitutions, and Codex Alexandrinus.",
        translation_source="1611 Authorized King James Version Apocrypha.",
        veracity_and_assessment="Composed to supply the penitential prayer of King Manasseh mentioned in 2 Chronicles 33:12–19. Though pseudepigraphical, it is universally praised by scholars as one of the finest liturgical prayers of repentance from antiquity.",
    ),
    "1-maccabees": ProvenanceDossier(
        date_and_origin="c. 100 BC (Judea, late Hasmonean period).",
        manuscripts_and_language="Originally written in biblical Hebrew (attested by Origen and Jerome); survives in the Greek Septuagint.",
        translation_source="1611 Authorized King James Version Apocrypha.",
        veracity_and_assessment="HIGH HISTORICAL VERACITY: One of the most trustworthy primary historical sources from antiquity covering the Seleucid persecution under Antiochus IV Epiphanes, the Maccabean Revolt, the rededication of the Temple (Hanukkah), and Hasmonean rule from 175 to 134 BC.",
    ),
    "2-maccabees": ProvenanceDossier(
        date_and_origin="c. 124 BC (abridgment of a 5-volume history by Jason of Cyrene).",
        manuscripts_and_language="Composed directly in Hellenistic Greek; preserved in Codex Alexandrinus and Codex Venetus.",
        translation_source="1611 Authorized King James Version Apocrypha.",
        veracity_and_assessment="Covers 180–161 BC with a strong theological emphasis on martyrdom, resurrection of the dead, intercession, and creation ex nihilo (2 Maccabees 7:28). Historical core supplemented by supernatural apparitions and rhetorical pathos.",
    ),

    # --- DIVISION II: MAJOR OT PSEUDEPIGRAPHA & REWRITTEN BIBLE ---
    "1-enoch-charles": ProvenanceDossier(
        date_and_origin="Composite five-part Jewish apocalyptic work composed between c. 300 BC and the 1st century BC (Book of the Watchers ch. 1–36; Similitudes/Parables ch. 37–71; Astronomical Book ch. 72–82; Dream Visions ch. 83–90; Epistle of Enoch ch. 91–108).",
        manuscripts_and_language="Originally composed in Aramaic (eleven Aramaic manuscripts found in Qumran Cave 4: 4Q201–212), translated into Greek (Akhmim & Chester Beatty papyri), and preserved complete only in Ge'ez (Classical Ethiopic) by the Ethiopian Orthodox Tewahedo Church.",
        translation_source="R. H. Charles, D.Litt., D.D. (1912/1917 Oxford Critical Edition).",
        veracity_and_assessment="CRITICAL ANTIQUITY & LDS SIGNIFICANCE: Quoted directly in the New Testament (Jude 1:14–15). While pseudepigraphally attributed to the antediluvian patriarch Enoch, its Qumran Aramaic fragments prove it predates Christianity by centuries. Exhibits striking parallels with Joseph Smith's 1830 Book of Moses (Moses 6–7)—including the 'Son of Man' title, Mahijah/Mahaway, weeping heavens, and the Watchers—even though Qumran's Aramaic Book of Giants wasn't discovered until 1948.",
    ),
    "enoch-laurence": ProvenanceDossier(
        date_and_origin="Ancient composite (3rd–1st century BC); English translation first published in 1821 at Oxford by Archbishop Richard Laurence from the Bodleian Ethiopic manuscript brought from Abyssinia by Scottish explorer James Bruce in 1773.",
        manuscripts_and_language="Translated from a single Ge'ez Ethiopic manuscript in the Bodleian Library, Oxford.",
        translation_source="Archbishop Richard Laurence (1821; 1883 Kegan Paul edition, 105 chapters).",
        veracity_and_assessment="Included alongside R. H. Charles's critical edition because Laurence's 1821 translation was the historic first English rendering of 1 Enoch and was referenced by early Latter-day Saint writers (such as Parley P. Pratt and John Taylor) in the 1840s after the Book of Moses had already been revealed in 1830.",
    ),
    "the-book-of-the-secrets-of-enoch": ProvenanceDossier(
        date_and_origin="c. 1st century AD (prior to AD 70, likely in Hellenistic Egypt/Alexandria, with later Christian and Byzantine expansions).",
        manuscripts_and_language="Likely composed in Greek; survives only in Old Church Slavonic recensions (Long and Short recensions) discovered in Russian and Serbian monasteries in the late 19th century.",
        translation_source="W. R. Morfill & R. H. Charles (1896 Oxford edition; reprinted in Rutherford H. Platt's Forgotten Books of Eden, 1926).",
        veracity_and_assessment="Known in scholarship as '2 Enoch' or 'Slavonic Enoch.' Describes Enoch's ascent through Ten Heavens, his anointing with luminous oil before the throne of God, creation secrets, and the miraculous priestly birth of Melchizedek (ch. 68–73). Contains authentic 1st-century Jewish mystical (Merkabah) traditions alongside medieval Slavonic scribal glosses.",
    ),
    "book-of-jubilees": ProvenanceDossier(
        date_and_origin="c. 160–150 BC (Hasmonean Judea).",
        manuscripts_and_language="Originally written in Hebrew (fifteen fragmentary Hebrew scrolls discovered at Qumran in Caves 1, 2, 3, 4, and 11); translated into Greek and Latin; survives complete in Ge'ez Ethiopic (where it is canonical in the Ethiopian Orthodox Church as Mashafa Kufale).",
        translation_source="R. H. Charles (1902/1917 Critical Edition with 925 scholarly notes).",
        veracity_and_assessment="HIGH ANTIQUITY ('Little Genesis'): Retells Genesis 1 through Exodus 19 organized into 49-year Jubilee cycles as dictated to Moses on Mount Sinai by the 'Angel of the Presence' from heavenly tablets. Its fifteen Dead Sea Scrolls manuscripts prove it was authoritative among the Qumran community. Shares notable Enochic, Abrahamic (Ur, Terah's idolatry, Abraham's astronomy), and covenantal themes with the Pearl of Great Price.",
    ),
    "book-of-jasher": ProvenanceDossier(
        date_and_origin="Medieval Hebrew Midrash (Sefer ha-Yashar), first printed in Venice in 1625 and compiled in Southern Italy or Spain between the 11th and 16th centuries AD from older rabbinic midrashim, Josippon, and Arabic chronicles.",
        manuscripts_and_language="Rabbinic Hebrew (1625 Venice editio princeps by Joseph ben Samuel ha-Qatan).",
        translation_source="Moses Samuel & Mordecai Manuel Noah (New York, 1840 English translation).",
        veracity_and_assessment="CRITICAL HISTORICAL DISTINCTION: This is NOT the ancient pre-exilic biblical 'Book of Jasher' cited in Joshua 10:13 and 2 Samuel 1:18 (nor is it Jacob Ilive's 1751 English forgery). Rather, it is a medieval Jewish Midrashic compilation (*Sefer ha-Yashar*) translated into English in 1840 in New York, acquired by Joseph Smith and John Taylor in Nauvoo, and frequently quoted in early LDS publications (*Times and Seasons*) for its rich extra-biblical narratives of Enoch, Noah, Nimrod, Abraham, and Joseph in Egypt.",
    ),
    "biblical-antiquities-of-philo": ProvenanceDossier(
        date_and_origin="c. AD 50–100 (1st-century Jewish Palestine).",
        manuscripts_and_language="Originally composed in Hebrew, translated into Greek, and preserved in 4th-century Latin manuscripts (*Liber Antiquitatum Biblicarum*) where it was mistakenly bundled with the works of Philo of Alexandria.",
        translation_source="M. R. James (1917 SPCK translation).",
        veracity_and_assessment="Known in modern scholarship as 'Pseudo-Philo' (since Philo of Alexandria did not write it). However, it is a genuine 1st-century AD Palestinian Jewish 'Rewritten Bible' spanning from Adam to the death of King Saul, invaluable for understanding 1st-century Jewish scriptural exegesis contemporaneous with Jesus and the Apostles.",
    ),
    "the-first-book-of-adam-and-eve": ProvenanceDossier(
        date_and_origin="c. 5th–6th century AD (Christian Egypt or Syria), incorporating earlier Jewish and Syriac *Cave of Treasures* traditions.",
        manuscripts_and_language="Composed in Arabic or Syriac and translated into Ge'ez Ethiopic (*Gadla Adan wa-Hewan*, 'The Conflict of Adam and Eve with Satan').",
        translation_source="Rev. Solomon Caesar Malan (1882 translation from the Ethiopic; reprinted in Platt 1926).",
        veracity_and_assessment="Late antique Christian-Oriental pseudepigraphon recounting Adam and Eve's life in the 'Cave of Treasures' after their expulsion from Eden, Satan's repeated disguises as an angel of light to deceive them, and God's promise of redemption after 5,500 years. Not an ancient Hebrew text, though it preserves striking ritual and narrative parallels to early Christian and Latter-day Saint Adam-and-Eve traditions.",
    ),
    "the-second-book-of-adam-and-eve": ProvenanceDossier(
        date_and_origin="c. 5th–6th century AD (continuation of the Ethiopic *Conflict of Adam and Eve with Satan*).",
        manuscripts_and_language="Ge'ez Ethiopic & Arabic manuscript tradition.",
        translation_source="Rev. Solomon Caesar Malan (1882).",
        veracity_and_assessment="Traces the patriarchal generations from Seth to Enoch and Methuselah, depicting how the righteous 'children of Seth' dwelt on the Holy Mountain until they were lured down into the valley of iniquity by the 'children of Cain' through music and illicit unions.",
    ),
    "books-of-adam-and-eve": ProvenanceDossier(
        date_and_origin="c. 1st century BC – 1st century AD (Jewish core with early Christian transmission).",
        manuscripts_and_language="Latin recension (*Vita Adae et Evae*), translated from a Greek original that likely rested on a Semitic substratum.",
        translation_source="R. H. Charles (1913 Oxford *Apocrypha and Pseudepigrapha of the Old Testament*).",
        veracity_and_assessment="Much earlier and more historically grounded than the 6th-century Ethiopic *Conflict*. Preserves the famous account of Adam and Eve's penitence in the Jordan and Tigris rivers, Satan's refusal to bow to Adam as the 'image of God' (cf. Moses 4:1–4), and Seth's quest for the 'oil of mercy' from the Tree of Life.",
    ),
    "slavonic-life-of-adam-and-eve": ProvenanceDossier(
        date_and_origin="Ancient 1st-century Jewish/Christian core; Old Church Slavonic recension compiled in the medieval Balkans/Russia.",
        manuscripts_and_language="Old Church Slavonic translated from Byzantine Greek.",
        translation_source="W. R. Morfill & R. H. Charles (1913).",
        veracity_and_assessment="Presents the distinctive Slavonic chapters (sections XXVIII–XL) of the *Life of Adam and Eve*, including the 'Cheirograph' (handwritten contract) by which Satan claimed dominion over Adam's posterity until Christ's descent and baptism in the Jordan.",
    ),
    "apocalypse-of-moses": ProvenanceDossier(
        date_and_origin="c. 1st century AD (Jewish/early Christian Palestine or Diaspora).",
        manuscripts_and_language="Koine Greek recension of the *Life of Adam and Eve* (mistitled 'Apocalypse of Moses' by Tischendorf from its opening prologue).",
        translation_source="Alexander Walker (*Ante-Nicene Fathers*, Vol. 8).",
        veracity_and_assessment="The oldest surviving Greek witness to the primary Adam and Eve literature, recounting the Fall, Adam's sickness, Eve's confession, and the burial of Adam and Abel by the archangels Michael, Gabriel, Uriel, and Raphael in Paradise.",
    ),
    "testament-of-abraham": ProvenanceDossier(
        date_and_origin="c. 1st century AD (Egyptian Jewish Diaspora, likely Alexandria).",
        manuscripts_and_language="Composed in Koine Greek (surviving in Long Recension A and Short Recension B), with Coptic, Slavonic, Romanian, Arabic, and Ethiopic versions.",
        translation_source="W. A. Craigie (*Ante-Nicene Fathers*, Vol. 8).",
        veracity_and_assessment="HIGHLY SIGNIFICANT SECOND TEMPLE PSEUDEPIGRAPHON: Tells how the Archangel Michael takes Abraham in a heavenly chariot to view the entire inhabited world and the judgment of souls before two gates (broad and narrow) and the weighing of deeds. Studied extensively by LDS scholars for its structural and visionary parallels to Abraham's cosmic vision in the Book of Abraham.",
    ),
    "narrative-of-zosimus": ProvenanceDossier(
        date_and_origin="Core chapters c. 1st–2nd century AD (Jewish/Judaeo-Christian), framed by a 4th–5th century Christian monastic prologue and epilogue.",
        manuscripts_and_language="Greek, Syriac, Ethiopic, and Slavonic manuscripts (also known in scholarship as *The History of the Rechabites*).",
        translation_source="W. A. Craigie (*Ante-Nicene Fathers*, Vol. 8).",
        veracity_and_assessment="HIGH LDS SCHOLARLY INTEREST: Describes how the righteous monk Zosimus is led through the wilderness and across a dark mist/ocean to the land of the 'Blessed Ones' (descendants of Jonadab son of Rechab), who fled Jerusalem during the reign of King Zedekiah after Jeremiah warned them of Jerusalem's impending destruction, were guided by angels across great waters to a promised land of fragrant fruit-bearing trees, and recorded their history on stone/metal tablets. Frequently compared by scholars (such as John W. Welch and Donald W. Parry) to 1 Nephi 1–11.",
    ),

    # --- DIVISION III: THE TESTAMENTS OF THE TWELVE PATRIARCHS (12 BOOKS) ---
    "testaments-of-the-twelve-patriarchs": ProvenanceDossier(
        date_and_origin="Jewish ethical and apocalyptic testaments composed c. 200–100 BC (with Aramaic *Testament of Levi* and Hebrew *Testament of Naphtali* fragments discovered at Qumran and the Cairo Genizah), redacted by Christian scribes in the 2nd century AD.",
        manuscripts_and_language="Preserved complete in Byzantine Greek, Armenian, and Slavonic manuscripts; first brought to Western Europe by Bishop Robert Grosseteste of Lincoln in 1242.",
        translation_source="R. H. Charles (1908/1913 translation).",
        veracity_and_assessment="Structured on the pattern of Jacob's deathbed blessings in Genesis 49 (and Lehi's deathbed blessings to his sons in 2 Nephi 1–4). Each of Jacob's twelve sons recounts his life, confesses a specific moral failing (e.g., Reuben on unchastity, Simeon on envy, Judah on wine and avarice, Joseph on chastity and forgiveness), exhorts his descendants to virtue, and prophesies of a dual priesthood-and-kingship Messiah from Levi and Judah.",
    ),

    # --- DIVISION IV: SECOND TEMPLE WISDOM, ODES, APOCALYPSES & ORACLES ---
    "the-psalms-of-solomon": ProvenanceDossier(
        date_and_origin="c. 63–40 BC (Jerusalem, composed shortly after the Roman general Pompey captured Jerusalem in 63 BC and died in Egypt in 48 BC).",
        manuscripts_and_language="Composed in Hebrew and translated into Koine Greek (preserved in eleven Greek and four Syriac manuscripts).",
        translation_source="G. Buchanan Gray (1913).",
        veracity_and_assessment="HIGH HISTORICAL IMPORTANCE: Eighteen liturgical hymns falsely attributed to Solomon in later manuscripts, but actually written by devout 1st-century BC Judean Jews reacting to Hasmonean corruption and Roman occupation. Chapters 17 and 18 contain the most important pre-Christian Jewish prayers for the coming righteous Davidic 'Messiah' (*Christos Kyrios*) who will purge Jerusalem by the word of his mouth.",
    ),
    "the-odes-of-solomon": ProvenanceDossier(
        date_and_origin="c. AD 70–125 (Syria / Antioch or Edessa).",
        manuscripts_and_language="Composed in Syriac or Greek; five odes quoted in the Coptic *Pistis Sophia*, and the nearly complete Syriac manuscript discovered by J. Rendel Harris in 1909.",
        translation_source="J. Rendel Harris (1909/1926).",
        veracity_and_assessment="THE EARLIEST CHRISTIAN HYMNAL: Forty-two ecstatic, mystical hymns celebrating baptismal anointing, crowning, garments of light, Christ's descent into Sheol to liberate the dead, and the Bridal Chamber. Widely regarded by patristic scholars as authentic late-1st or early-2nd-century Judaeo-Christian liturgical poetry.",
    ),
    "the-letter-of-aristeas": ProvenanceDossier(
        date_and_origin="c. 150–100 BC (Alexandria, Egypt).",
        manuscripts_and_language="Composed in literary Koine Greek; preserved in over twenty Greek manuscripts and quoted extensively by Josephus and Eusebius.",
        translation_source="H. T. Andrews (1913).",
        veracity_and_assessment="Purports to be a contemporary letter by Aristeas, a courtier of King Ptolemy II Philadelphus (285–247 BC), describing how High Priest Eleazar of Jerusalem sent 72 elders (six from each of the Twelve Tribes) to Alexandria to translate the Hebrew Torah into Greek (hence 'Septuagint' = 70). While written a century after the event as Hellenistic Jewish apologetics, it preserves priceless historical descriptions of the Jerusalem Temple and Ptolemaic Alexandria.",
    ),
    "fourth-book-of-maccabees": ProvenanceDossier(
        date_and_origin="c. AD 20–54 (Antioch or Alexandria).",
        manuscripts_and_language="Composed in rhetorical Koine Greek; included in the appendix of Codex Sinaiticus and Codex Alexandrinus.",
        translation_source="C. W. Emmet (1913).",
        veracity_and_assessment="A philosophical homily combining Stoic philosophy with Torah piety ('Devout Reason is sovereign over the passions'), illustrated by the heroic martyrdoms of the aged priest Eleazar and the mother with her seven sons from 2 Maccabees 6–7.",
    ),
    "the-story-of-ahikar": ProvenanceDossier(
        date_and_origin="c. 7th–5th century BC (Ancient Near Eastern Aramaic wisdom tale; oldest papyrus copy found at Elephantine, Egypt, dated to c. 420 BC).",
        manuscripts_and_language="Composed in Imperial Aramaic; translated into Syriac, Arabic, Armenian, Ethiopic, Greek (incorporated into the *Life of Aesop*), and Slavonic.",
        translation_source="J. Rendel Harris, F. C. Conybeare & Agnes Smith Lewis (1913).",
        veracity_and_assessment="AUTHENTIC ANCIENT NEAR EASTERN WISDOM TEXT: One of the oldest non-canonical stories in world literature, explicitly referenced in the Deuterocanonical Book of Tobit (Tobit 1:21–22; 14:10), where Ahikar is identified as Tobit's nephew and cupbearer to King Esarhaddon of Assyria.",
    ),
    "sibylline-oracles": ProvenanceDossier(
        date_and_origin="Composite anthology compiled from the 2nd century BC to the 6th century AD by Alexandrian Jews (especially Books III–V) and early Christians (Books I–II, VI–VIII).",
        manuscripts_and_language="Composed in Homeric Greek dactylic hexameters; preserved in two Byzantine manuscript families.",
        translation_source="Milton S. Terry (1899 blank-verse translation, Books I–XIV).",
        veracity_and_assessment="Pious literary pseudepigrapha in which Jewish and Christian apologists placed monotheistic history, denunciations of Greco-Roman idolatry, and messianic/apocalyptic prophecies into the mouth of the pagan 'Sibyl' so Greco-Roman readers would heed them. Quoted frequently by early Christian Fathers (Justin Martyr, Clement of Alexandria, Lactantius, Augustine).",
    ),
    "apocalypse-of-esdras": ProvenanceDossier(
        date_and_origin="c. 2nd–9th century AD (Christian Byzantine compilation drawing on earlier Jewish 4 Ezra traditions).",
        manuscripts_and_language="Koine/Byzantine Greek (first published by Tischendorf in 1866 from a Paris manuscript).",
        translation_source="Alexander Walker (*Ante-Nicene Fathers*, Vol. 8).",
        veracity_and_assessment="Christian apocalyptic dialogue in which Esdras (Ezra) boldly pleads with God to spare sinful humanity from the torments of Tartarus, describes the physiognomy of the Antichrist, and surrenders his soul to God.",
    ),
    "apocalypse-of-sedrach": ProvenanceDossier(
        date_and_origin="c. 2nd–5th century AD (compiled in its surviving Byzantine form c. 10th century).",
        manuscripts_and_language="Preserved in a single Greek manuscript in the Bodleian Library (Codex Misc. Gr. 56).",
        translation_source="Andrew Rutherford (*Ante-Nicene Fathers*, Vol. 8).",
        veracity_and_assessment="Closely related to the Greek *Apocalypse of Esdras*. Opens with a profound homily on Divine Love (*Agape*) before depicting Sedrach debating God over human frailty, free will, and repentance.",
    ),

    # --- DIVISION V: NEW TESTAMENT APOCRYPHAL GOSPELS & INFANCY NARRATIVES ---
    "gospel-of-thomas": ProvenanceDossier(
        date_and_origin="c. AD 60–140 (Syria / Edessa; Greek Oxyrhynchus Papyri 1, 654, 655 date to c. AD 130–200; Coptic Nag Hammadi Codex II dates to c. AD 340).",
        manuscripts_and_language="Originally composed in Greek; complete collection of 114 *logia* (sayings) discovered in Coptic at Nag Hammadi, Egypt, in December 1945.",
        translation_source="Translated from the Coptic Nag Hammadi Codex II & Oxyrhynchus Greek Papyri.",
        veracity_and_assessment="MAJOR EARLY CHRISTIAN DISCOVERY: A non-narrative 'Sayings Gospel' (*logia*) attributed to Didymos Judas Thomas ('Secret sayings which the living Jesus spoke').Roughly half of its 114 sayings parallel canonical Synoptic parables and aphorisms (sometimes in very archaic, independent form), while the other half reflect early Syrian ascetic and proto-Gnostic theology.",
    ),
    "gospel-of-mary": ProvenanceDossier(
        date_and_origin="c. AD 120–180.",
        manuscripts_and_language="Composed in Greek (3rd-century Greek fragments Rylands Papyrus 463 and Oxyrhynchus Papyrus 3525); primary witness is the 5th-century Coptic Berlin Gnostic Codex (BG 8502), acquired in Cairo in 1896.",
        translation_source="Translated from the Coptic Berlin Papyrus 8502.",
        veracity_and_assessment="2nd-century Gnostic dialogue in which Mary Magdalene comforts the grieving apostles after the Resurrection and recounts a visionary teaching of the Savior concerning the ascent of the soul past cosmic powers, prompting a debate between Peter, Levi, and Andrew over revelation given to women.",
    ),
    "the-lost-gospel-according-to-peter": ProvenanceDossier(
        date_and_origin="c. AD 110–160 (Syria; explicitly condemned around AD 190 by Bishop Serapion of Antioch for docetic tendencies).",
        manuscripts_and_language="Koine Greek; rediscovered in winter 1886–1887 by French archaeologists in the tomb of an 8th-century Christian monk at Akhmim (Panopolis), Upper Egypt.",
        translation_source="Rutherford H. Platt / J. Armitage Robinson (Akhmim Fragment).",
        veracity_and_assessment="Preserves a striking 2nd-century Passion and Resurrection narrative that shifts blame from Pontius Pilate to Herod Antipas and dramatically depicts the Resurrection itself: two towering angels descend from heaven, support the risen Christ emerging from the sepulchre while their heads reach the clouds, and a walking, speaking Cross answers a voice from heaven ('Hast thou preached to them that sleep?' — 'Yea').",
    ),
    "the-protevangelion": ProvenanceDossier(
        date_and_origin="c. AD 145–170 (referred to by Origen and Clement of Alexandria).",
        manuscripts_and_language="Koine Greek (over 140 surviving Greek manuscripts, plus Syriac, Ethiopic, Georgian, and Slavonic translations; earliest papyrus is 3rd-century Papyrus Bodmer V).",
        translation_source="William Hone / Jeremiah Jones (*Lost Books of the Bible*).",
        veracity_and_assessment="Known in scholarship as the *Protoevangelium of James*. Pseudepigraphally attributed to James the Lord's brother. Not a 1st-century historical chronicle, but the foundational 2nd-century text for Christian tradition regarding Mary's parents (Joachim and Anna), Mary's upbringing in the Temple, Joseph as an elderly widower chosen by the budding rod, and Jesus' birth in a cave near Bethlehem.",
    ),
    "gospel-of-pseudo-matthew": ProvenanceDossier(
        date_and_origin="c. AD 600–625 (Latin compilation synthesizing the *Protevangelion of James* and the *Infancy Gospel of Thomas*).",
        manuscripts_and_language="Medieval Latin (*Liber de Ortu Beatae Mariae et Infantia Salvatoris*).",
        translation_source="Alexander Walker (*Ante-Nicene Fathers*, Vol. 8).",
        veracity_and_assessment="Prefaced with forged letters between Bishops Cromatius and Heliodorus and St. Jerome to lend it authority in the Latin West. Historically late, it introduced the famous Christmas imagery of the ox and the ass adoring the infant Jesus in the manger (ch. 14) and palm trees bowing to feed the Holy Family during the Flight into Egypt (ch. 20).",
    ),
    "the-gospel-of- the-birth-of-mary": ProvenanceDossier(
        date_and_origin="c. 9th century AD (Carolingian Latin adaptation of *Pseudo-Matthew* ch. 1–12, traditionally attributed to Paschasius Radbertus).",
        manuscripts_and_language="Medieval Latin (*De Nativitate Mariae*; incorporated into Jacobus de Voragine's *Golden Legend*).",
        translation_source="Jeremiah Jones / William Hone (*Lost Books of the Bible*).",
        veracity_and_assessment="A streamlined medieval Latin devotional rewriting of the early chapters of *Pseudo-Matthew*, stripping out the more extravagant folkloric miracles to harmonize with canonical scripture.",
    ),
    "history-of-joseph-the-carpenter": ProvenanceDossier(
        date_and_origin="c. 4th–5th century AD (Byzantine Egypt).",
        manuscripts_and_language="Composed in Greek; survives in Sahidic and Bohairic Coptic and Arabic translations.",
        translation_source="Alexander Walker (*Ante-Nicene Fathers*, Vol. 8).",
        veracity_and_assessment="Framed as Jesus on the Mount of Olives recounting to the Apostles the righteous life and peaceful death of His stepfather Joseph at age 111, followed by Joseph's soul being escorted to heaven by Michael and Gabriel. Reflects 4th-century Egyptian Christian veneration of St. Joseph.",
    ),
    "the-first-gospel-of-the-infancy-of-jesus-christ": ProvenanceDossier(
        date_and_origin="c. 5th–6th century AD (Syriac compilation drawing on the *Protevangelion*, *Infancy Thomas*, and Eastern folklore).",
        manuscripts_and_language="Syriac and Arabic (first published in Arabic and Latin by Henry Sike at Utrecht in 1697).",
        translation_source="Henry Sike (1697) / William Hone (*Lost Books of the Bible*).",
        veracity_and_assessment="Known as the *Arabic Infancy Gospel*. Combines early 2nd-century infancy traditions with extravagant Eastern miracle tales during the Holy Family's sojourn in Egypt. Notably preserves the story of the infant Jesus speaking from the cradle (ch. 1), which later entered the Quran (Surah 19:29–33).",
    ),
    "thomass-gospel-of-the-infancy-of-jesus-christ": ProvenanceDossier(
        date_and_origin="c. AD 150–180 (known to Irenaeus of Lyons c. AD 180).",
        manuscripts_and_language="Koine Greek, Syriac, Latin, Ethiopic, and Georgian recensions.",
        translation_source="William Hone (*Lost Books of the Bible*).",
        veracity_and_assessment="Known as the *Infancy Gospel of Thomas* (distinct from the Coptic sayings *Gospel of Thomas*). Folkloric cycle depicting the boy Jesus (ages 5 to 12) fashioning twelve live sparrows out of clay on the Sabbath, confounding his schoolmasters over the mystical meaning of the Greek alphabet, and performing healings, concluding with the canonical Luke 2 visit to the Temple at age twelve.",
    ),
    "the-gospel-of-nicodemus-formerly-called-the-acts-of-pontius-pilate": ProvenanceDossier(
        date_and_origin="Compiled in the 4th–5th century AD from two older parts: the *Acts of Pilate* (Part I, ch. 1–11) and Christ's *Descensus ad Inferos* / Harrowing of Hell (Part II, ch. 12–22).",
        manuscripts_and_language="Koine Greek and Latin (hundreds of medieval manuscripts across all European and Eastern languages).",
        translation_source="William Wake / William Hone (*Lost Books of the Bible*).",
        veracity_and_assessment="While not written by the historical Nicodemus, Part II (the *Harrowing of Hell*) is one of the most dramatic and doctrinally intriguing documents of early Christianity: Karinus and Leucius, two sons of Simeon raised from the dead at Christ's resurrection, write on scrolls how a great light shone into Hades, the bronze gates were shattered, and Christ took Adam by the right hand and delivered the righteous patriarchs and prophets—strikingly resonant with 1 Peter 3:18–20 and Doctrine and Covenants 138.",
    ),
    "pilate-passion-cycle": ProvenanceDossier(
        date_and_origin="c. 4th–7th centuries AD (Byzantine and Latin Christian apologetic cycle).",
        manuscripts_and_language="Greek and Latin (*Anaphora Pilati*, *Paradosis Pilati*, *Mors Pilati*, *Vindicta Salvatoris*, *Narrative of Joseph of Arimathea*).",
        translation_source="Alexander Walker (*Ante-Nicene Fathers*, Vol. 8) & William Hone.",
        veracity_and_assessment="Unhistorical late-antique Christian legends composed to imagine official Roman archival reports from Pontius Pilate to Emperor Tiberius regarding the miracles, crucifixion, darkness, and resurrection of Jesus, followed by Tiberius summoning Pilate to Rome for trial.",
    ),
    "assumption-of-mary": ProvenanceDossier(
        date_and_origin="c. 4th–5th century AD (*Transitus Mariae* literature).",
        manuscripts_and_language="Greek (attributed to St. John the Theologian), Latin (attributed to Melito of Sardis), Syriac, Coptic, and Arabic.",
        translation_source="Alexander Walker (*Ante-Nicene Fathers*, Vol. 8).",
        veracity_and_assessment="Devotional late-antique Dormition narrative describing how the Apostles are miraculously transported on clouds from their missionary fields to Jerusalem to witness the passing of Mary and the translation of her body to Paradise.",
    ),

    # --- DIVISION VI: APOCRYPHAL ACTS, EPISTLES & CHRISTIAN APOCALYPSES ---
    "the-epistles-of-jesus-christ-and-abgarus-king-of-edessa": ProvenanceDossier(
        date_and_origin="c. late 3rd century AD (found in the Syriac archives of Edessa and translated into Greek by Eusebius of Caesarea in *Church History* I.13 c. AD 324; expanded in the 5th-century Syriac *Doctrine of Addai*).",
        manuscripts_and_language="Syriac and Greek.",
        translation_source="William Wake / B. P. Pratten (*Lost Books of the Bible* & *Ante-Nicene Fathers*, Vol. 8).",
        veracity_and_assessment="Pious royal legend created by the Syriac church of Edessa (modern Urfa) to trace its conversion under King Abgar V Ukkama (4 BC – AD 50) directly to a personal letter from Jesus and the mission of Thaddaeus (Addai), one of the Seventy.",
    ),
    "the-acts-of-paul-and-thecla": ProvenanceDossier(
        date_and_origin="c. AD 160–180 (composed in Asia Minor; Tertullian *On Baptism* 17 records that a presbyter in Asia composed it 'out of love for Paul').",
        manuscripts_and_language="Koine Greek, Latin, Syriac, Coptic, Armenian, Slavonic, and Ethiopic.",
        translation_source="Jeremiah Jones / Alexander Walker.",
        veracity_and_assessment="An authentic 2nd-century Christian novelistic romance (originally part of the larger *Acts of Paul*). Celebrates the noble virgin Thecla of Iconium who converts upon hearing Paul preach the Beatitudes of continence, survives martyrdom in the arena, and baptizes and teaches in Seleucia. Also contains the famous earliest physical description of the Apostle Paul (ch. 1:7).",
    ),
    "apocryphal-acts-of-the-apostles": ProvenanceDossier(
        date_and_origin="2nd to 5th centuries AD (*Acts of John* c. AD 150–180; *Acts of Peter* c. AD 180–190; *Acts of Andrew* c. AD 180–200; *Acts of Thomas* c. AD 200–240; later *Acts of Philip*, *Matthew*, *Bartholomew*, *Barnabas*, *Thaddaeus*, and *Xanthippe*). The five major early Acts were collected as the 'Leucian Acts.'",
        manuscripts_and_language="Greek, Syriac (especially *Acts of Thomas*), Latin, Coptic, and Armenian.",
        translation_source="Alexander Walker (*Ante-Nicene Fathers*, Vol. 8).",
        veracity_and_assessment="Imaginative 2nd–4th century Christian romances blending historical memories (such as Thomas traveling to Parthia/India under King Gondophares, confirmed by numismatic evidence, and Peter's martyrdom in Rome) with miracle contests and ascetic/Gnostic hymns—most famously the sublime Syriac **'Hymn of the Pearl'** in the *Acts of Thomas*, a poetic allegory of the pre-mortal soul sent from its heavenly royal parents into mortality to recover the pearl from the serpent and return in its celestial garment of glory.",
    ),
    "pauline-apocrypha": ProvenanceDossier(
        date_and_origin="*Epistle to the Laodiceans*: c. 2nd–4th century AD; *Correspondence of Paul and Seneca*: c. 4th century AD (mentioned by Jerome in *De Viris Illustribus* 12 in AD 392).",
        manuscripts_and_language="Latin (found in numerous Western Vulgate manuscripts, including the 6th-century Codex Fuldensis, and included in Wycliffe's English Bible).",
        translation_source="William Wake / William Hone (*Lost Books of the Bible*).",
        veracity_and_assessment="*Laodiceans* is a harmless patchwork of Pauline phrases (mostly from Philippians) composed to fill the perceived gap left by Colossians 4:16 ('read the epistle from Laodicea'). The *Fourteen Letters of Paul and Seneca* are 4th-century rhetorical exercises imagining a friendship between the Apostle Paul and Nero's Stoic tutor Lucius Annaeus Seneca.",
    ),
    "christian-apocalypses": ProvenanceDossier(
        date_and_origin="*Apocalypse of Peter*: c. AD 110–135 (counted as semi-canonical in the 2nd-century Muratorian Fragment and by Clement of Alexandria); *Apocalypse of Paul (Visio Pauli)*: c. AD 250–380; *Apocalypses of John and the Virgin*: 5th–9th centuries AD.",
        manuscripts_and_language="Greek, Ge'ez Ethiopic, Latin, Syriac, and Coptic.",
        translation_source="Andrew Rutherford & Alexander Walker (*Ante-Nicene Fathers*, Vol. 8).",
        veracity_and_assessment="The *Apocalypse of Peter* is the earliest Christian vision of heaven and hell, and both it and the 4th-century *Apocalypse of Paul* (expanding 2 Corinthians 12:2–4, Paul's ascent to the Third Heaven) directly shaped medieval Christian cosmology through Dante's *Inferno*. Interestingly, the *Apocalypse of Peter* (Ethiopic text) and *Apocalypse of Paul* also preserve early traditions regarding the post-mortal spirit world and baptism/mercy for the dead.",
    ),

    # --- DIVISION VII: THE APOSTOLIC FATHERS & EARLY CHURCH ORDERS ---
    "the-didache": ProvenanceDossier(
        date_and_origin="c. AD 50–100 (Syria or Palestine; widely dated by modern scholars to the late 1st century AD).",
        manuscripts_and_language="Koine Greek; lost for centuries until rediscovered in 1873 by Metropolitan Philotheos Bryennios in the Jerusalem Codex (dated AD 1056) in Constantinople.",
        translation_source="Charles H. Hoole (1894 translation with Greek notes).",
        veracity_and_assessment="AUTHENTIC 1ST-CENTURY CHRISTIAN MANUAL: The oldest surviving non-canonical Christian catechism and church order ('The Teaching of the Lord to the Gentiles by the Twelve Apostles'). Contains the 'Two Ways' moral catechism (ch. 1–6), the earliest post-New Testament instructions on baptism by immersion in 'living (running) water' (ch. 7), fasting and the Lord's Prayer (ch. 8), Eucharistic prayers over the broken bread and cup (ch. 9–10), testing itinerant apostles and prophets (ch. 11–13), and ordaining bishops and deacons (ch. 15).",
    ),
    "1-clement": ProvenanceDossier(
        date_and_origin="c. AD 95–96 (Rome, at the close of Emperor Domitian's reign).",
        manuscripts_and_language="Koine Greek; preserved in the 5th-century Biblical Codex Alexandrinus, the 11th-century Constantinople Jerusalem Codex, and Latin, Syriac, and Coptic versions.",
        translation_source="Archbishop William Wake (*Lost Books of the Bible*).",
        veracity_and_assessment="AUTHENTIC 1ST-CENTURY EPISTLE: Written by Clement, presiding bishop/elder of the church at Rome, in the name of the Roman church to the church at Corinth after younger members had deposed their duly appointed presbyters. Read publicly as near-scripture in early churches; primary historical witness to the martyrdoms of Peter and Paul (ch. 5) and the doctrine of apostolic succession and priesthood order (ch. 40–44).",
    ),
    "2-clement": ProvenanceDossier(
        date_and_origin="c. AD 120–150 (Corinth or Rome).",
        manuscripts_and_language="Koine Greek (preserved alongside 1 Clement in Codex Alexandrinus and the Jerusalem Codex).",
        translation_source="Archbishop William Wake (*Lost Books of the Bible*).",
        veracity_and_assessment="Not written by Clement of Rome, but nonetheless the oldest surviving complete Christian sermon (homily) outside the New Testament, exhorting believers to repentance, purity of the flesh as the temple of the Spirit, and keeping baptismal covenants intact.",
    ),
    "epistle-of-barnabas": ProvenanceDossier(
        date_and_origin="c. AD 70–132 (Alexandria, Egypt; composed after the destruction of the Jerusalem Temple in AD 70 and before the Bar Kokhba revolt in AD 132).",
        manuscripts_and_language="Koine Greek; included in full directly after the New Testament in the 4th-century Codex Sinaiticus (and in the Jerusalem Codex).",
        translation_source="Archbishop William Wake (*Lost Books of the Bible*).",
        veracity_and_assessment="Early Alexandrian theological treatise (attributed in antiquity to Paul's companion Barnabas, though anonymous in the text itself) applying allegorical/typological interpretation to the Mosaic Law and concluding with the 'Two Ways' of Light and Darkness (ch. 18–21). Revered as canonical or deuterocanonical by Clement of Alexandria and Origen.",
    ),
    "epistles-of-ignatius": ProvenanceDossier(
        date_and_origin="c. AD 107–115 (written along the road from Antioch through Smyrna and Troas as Bishop Ignatius of Antioch was taken in chains by ten Roman soldiers to be martyred in the Colosseum at Rome under Emperor Trajan).",
        manuscripts_and_language="Koine Greek (Middle Recension of the seven genuine epistles authenticated by J. B. Lightfoot and Theodor Zahn).",
        translation_source="Archbishop William Wake (*Lost Books of the Bible*).",
        veracity_and_assessment="AUTHENTIC EARLY 2ND-CENTURY LETTERS: Seven letters (to the Ephesians, Magnesians, Trallians, Romans, Philadelphians, Smyrnaeans, and to Polycarp) written by a disciple of the Apostles. Provide our earliest witness to the three-fold local ministry of bishop, presbyters, and deacons, and vigorous defense of the physical flesh and resurrection of Jesus Christ against Docetism.",
    ),
    "epistle-of-polycarp": ProvenanceDossier(
        date_and_origin="c. AD 110–135 (Smyrna, Asia Minor).",
        manuscripts_and_language="Koine Greek and early Latin translation.",
        translation_source="Archbishop William Wake (*Lost Books of the Bible*).",
        veracity_and_assessment="AUTHENTIC APOSTOLIC FATHER EPISTLE: Written by Polycarp, Bishop of Smyrna (AD 69–155)—who had personally been taught by the Apostle John (as attested by Polycarp's pupil Irenaeus)—to the church at Philippi, quoting extensively from the Gospels, Paul's epistles, 1 Peter, and 1 John.",
    ),
    "shepherd-of-hermas": ProvenanceDossier(
        date_and_origin="c. AD 100–145 (Rome; the Muratorian Fragment notes it was written by Hermas, brother of Pius, Bishop of Rome).",
        manuscripts_and_language="Koine Greek (included in the 4th-century Codex Sinaiticus, Codex Athous, and numerous early Egyptian papyri), plus two ancient Latin translations and an Ethiopic version.",
        translation_source="Archbishop William Wake (*Lost Books of the Bible*: Book I Visions, Book II Commands, Book III Similitudes).",
        veracity_and_assessment="AUTHENTIC 2ND-CENTURY PROPHETIC APOCALYPSE: The most popular non-canonical Christian book of the 2nd and 3rd centuries, bound inside Codex Sinaiticus as part of the Christian Bible. Consists of five Visions, twelve Mandates (Commands), and ten Similitudes (Parables), featuring the allegory of the Church as a Great Tower built upon the waters of baptism—including the famous declaration in Similitude IX.16 that the Apostles and teachers descended after death to preach and administer the seal of baptism to the righteous dead who had died before Christ.",
    ),

    # --- ADDITIONAL SEPTUAGINT, ETHIOPIAN CANON, DEAD SEA SCROLLS & NAG HAMMADI TEXTS (PSEUDEPIGRAPHA.COM) ---
    "3-maccabees": ProvenanceDossier(
        date_and_origin="1st century BC (composed in Ptolemaic Alexandria, Egypt, c. 100–30 BC).",
        manuscripts_and_language="Koine Greek; preserved in the Septuagint (Codex Alexandrinus and Codex Venetus) and Syriac Peshitta.",
        translation_source="Cyril W. Emmet / R. H. Charles (*Apocrypha and Pseudepigrapha of the Old Testament*, 1913).",
        veracity_and_assessment="Canonical in the Eastern Orthodox and Armenian Churches. Despite its name, it does not concern the Maccabean revolt, but narrates the persecution and miraculous deliverance of the Jews of Egypt under King Ptolemy IV Philopator (221–204 BC) after he attempted to enter the Holy of Holies in Jerusalem (ch. 1–2) and subsequently ordered intoxicated war elephants to trample the Jews in the Alexandrian hippodrome before two angels intervened (ch. 5–6).",
    ),
    "4-maccabees": ProvenanceDossier(
        date_and_origin="Early 1st century AD (c. AD 18–54, composed in Antioch or Alexandria prior to the destruction of the Second Temple).",
        manuscripts_and_language="Koine Greek; preserved in the major Septuagint codices (Codex Sinaiticus and Codex Alexandrinus) and as an appendix to the Eastern Orthodox Bible.",
        translation_source="R. B. Townshend / R. H. Charles (*Apocrypha and Pseudepigrapha of the Old Testament*, 1913).",
        veracity_and_assessment="Anciently attributed to Flavius Josephus by Eusebius and Jerome, though modern scholars attribute it to a Hellenistic Jewish orator trained in Stoic philosophy. Uses the martyrdoms of the aged priest Eleazar and the mother with seven sons (from 2 Maccabees 6–7) to prove that 'devout reason is sovereign over the passions' and affirms the immediate immortality and glorification of the righteous martyrs with Abraham, Isaac, and Jacob.",
    ),
    "psalm-151": ProvenanceDossier(
        date_and_origin="Hellenistic / Second Temple period (3rd–2nd century BC; Hebrew original confirmed at Qumran).",
        manuscripts_and_language="Biblical Hebrew (discovered in the Great Psalms Scroll 11QPs_a at Qumran in 1956) and Koine Greek (Septuagint Codices Sinaiticus, Vaticanus, and Alexandrinus).",
        translation_source="Septuagint / R. H. Charles translation.",
        veracity_and_assessment="AUTHENTIC SECOND TEMPLE HEBREW PSALM: Canonical in the Eastern Orthodox, Oriental Orthodox, and Church of the East Psalters. Celebrates David's election as the youngest shepherd son of Jesse, his anointing by Samuel, and his slaying of Goliath with the giant's own sword.",
    ),
    "1-meqabyan": ProvenanceDossier(
        date_and_origin="Late Antiquity / Early Medieval Ge'ez composition drawing on earlier Semitic/Jewish-Christian martyrological traditions.",
        manuscripts_and_language="Classical Ethiopic (Ge'ez); preserved exclusively in the 81-book biblical canon of the Ethiopian and Eritrean Orthodox Tewahedo Churches.",
        translation_source="Feqade Selassie English translation from the Ge'ez Ethiopic.",
        veracity_and_assessment="CANONICAL IN THE ETHIOPIAN ORTHODOX BIBLE: Completely distinct in content from the Greek 1–4 Maccabees. Spanning 36 chapters, 1 Meqabyan tells of a tyrannical Median/Moabite ruler named Tsrutsaydan who demands idol worship, and of a righteous Benjamite named Meqabis and his sons (Abya, Seela, and Pantera) who resist idolatry, proclaim the coming Messiah and bodily resurrection, and triumph through faith.",
    ),
    "2-meqabyan": ProvenanceDossier(
        date_and_origin="Late Antiquity / Ge'ez Ethiopian canonical tradition.",
        manuscripts_and_language="Classical Ethiopic (Ge'ez); part of the narrower and broader Ethiopian Orthodox Tewahedo Old Testament canon.",
        translation_source="Feqade Selassie English translation from the Ge'ez Ethiopic.",
        veracity_and_assessment="CANONICAL IN THE ETHIOPIAN ORTHODOX BIBLE: Across 21 chapters, 2 Meqabyan recounts how King Moab of Midian made war against Israel during the Babylonian exile, and how he was later brought to repentance and instructed in the law of God, the creation, and the immortality of the soul.",
    ),
    "3-meqabyan": ProvenanceDossier(
        date_and_origin="Late Antiquity / Ge'ez Ethiopian canonical tradition.",
        manuscripts_and_language="Classical Ethiopic (Ge'ez); part of the Ethiopian Orthodox Tewahedo Old Testament canon.",
        translation_source="Feqade Selassie English translation from the Ge'ez Ethiopic.",
        veracity_and_assessment="CANONICAL IN THE ETHIOPIAN ORTHODOX BIBLE: A 10-chapter theological and eschatological homily expounding the pre-mortal rebellion and fall of Satan (Mastema/Diabolos), the testing of Adam, Job, and David, and the physical resurrection of the dead proved from the histories of the Patriarchs.",
    ),
    "book-of-noah": ProvenanceDossier(
        date_and_origin="3rd–2nd century BC (Aramaic original attested in Dead Sea Scrolls 1Q19, 4Q534–536, and 1QapGen).",
        manuscripts_and_language="Reconstructed from Ge'ez Ethiopic (embedded within 1 Enoch 6–11, 54–55, 60, 65–69, 106–107 and Jubilees 7, 10), Qumran Aramaic fragments, and medieval Hebrew *Sefer Noah*.",
        translation_source="R. H. Charles reconstruction from the Ethiopic Enoch and Jubilees.",
        veracity_and_assessment="In both *Jubilees* (10:13; 21:10) and the *Testament of Levi* (Mount Athos Greek MS addition to 18:2), an ancient *Book of Noah* is explicitly cited as an authoritative written source. R. H. Charles isolated these distinct Noachic chapters—describing Noah's miraculous birth, his journey to the ends of the earth to consult his translated great-grandfather Enoch regarding the shaking of the earth, the oath of the fallen Watchers, and the Flood.",
    ),
    "slavonic-life-of-adam-and-eve": ProvenanceDossier(
        date_and_origin="1st century BC – 1st century AD Jewish core (translated via a lost Greek intermediary into Old Church Slavonic in the 10th–11th centuries).",
        manuscripts_and_language="Old Church Slavonic (*Zhitie Adama i Evy*); supplemented by the Latin *Vita Adae et Evae*.",
        translation_source="W. R. Morfill & R. H. Charles (1896 / 1913 translation).",
        veracity_and_assessment="Preserves sections of the ancient Adam and Eve cycle absent from the Greek *Apocalypse of Moses*—most notably Satan's narrative of why he was cast out of heaven (refusing to worship Adam as the image of God), Adam and Eve's forty-day penitence standing up to their necks in the Jordan and Tigris rivers, and the story of the cheirograph (handwritten bond) which Satan required of Adam until the coming of Christ.",
    ),
    "eastern-book-of-adam": ProvenanceDossier(
        date_and_origin="3rd–7th century AD Near Eastern (Syriac, Coptic, and Mandaean/Gnostic Adam traditions).",
        manuscripts_and_language="Syriac, Arabic, and Mandaean Aramaic (*Ginza Rabba* / *Codex Nasaraeus*).",
        translation_source="19th-century Orientalist compilation (drawing on M. Norberg's Latin translation of the *Book of Adam* and Eastern Christian Adamitic hexameral traditions).",
        veracity_and_assessment="Reflects the rich Mesopotamian and Eastern Christian literary fascination with Adam as the primordial priest-king, receiver of angelic instruction, and prophet of the world's ages.",
    ),
    "apocalypse-of-abraham": ProvenanceDossier(
        date_and_origin="Late 1st century AD (c. AD 70–115, composed in Judea in Hebrew or Aramaic shortly after the Roman destruction of the Second Temple).",
        manuscripts_and_language="Preserved solely in Old Church Slavonic (in six 14th–17th century Russian codices, the Sylvester Codex being the oldest), translated from a Greek intermediary of a Semitic original.",
        translation_source="G. H. Box & J. I. Landsman (1918 SPCK translation, with critical notes).",
        veracity_and_assessment="HIGHLY SIGNIFICANT SECOND TEMPLE APOCALYPSE: Divided into two parts: (1) Chapters 1–8, a narrative midrash on Abraham's youth in Ur, his discovery of the absurdity of his father Terah's wooden and stone idols (Marumath and Barisat), and his call by the voice of God as fire consumes Terah's house; and (2) Chapters 9–32, an apocalyptic vision in which the angel Iaoel (bearing the Ineffable Name) guides Abraham to Mount Horeb ('the high mountain'), teaches him a celestial hymn, defeats the fallen spirit Azazel, and opens a vision of the Seventh Heaven, the divine Chariot-Throne, the firmament of stars, and the pre-mortal spirits ('those who were marked out beforehand by Me').",
    ),
    "joseph-and-aseneth": ProvenanceDossier(
        date_and_origin="1st century BC – early 2nd century AD (composed in Greek in Hellenistic Egypt).",
        manuscripts_and_language="Koine Greek (over 16 manuscripts), plus ancient Syriac, Armenian, Slavonic, and Latin versions.",
        translation_source="E. W. Brooks (1918 SPCK translation).",
        veracity_and_assessment="A masterpiece of Second Temple Jewish literature expanding Genesis 41:45 (Pharaoh giving Joseph 'Asenath the daughter of Poti-pherah priest of On to wife'). Explains how the pious Joseph could marry the daughter of an Egyptian priest: Asenath renounces her idols, fasts in sackcloth and ashes for seven days, is visited by the Chief of the House of the Lord (who resembles Joseph in glory), partakes of a sacred honeycomb of immortality ('bread of life, cup of immortality, and ointment of incorruption'), and becomes the bride of Joseph and 'City of Refuge' for all proselytes.",
    ),
    "tales-of-the-patriarchs": ProvenanceDossier(
        date_and_origin="Late Second Temple to Rabbinic / Medieval Midrashic period.",
        manuscripts_and_language="Hebrew and Aramaic haggadic sources.",
        translation_source="Classical English haggadic compilation.",
        veracity_and_assessment="Collects extra-biblical Jewish narrative traditions surrounding the lives, trials, and hospitality of Abraham, Isaac, Jacob, and Moses.",
    ),
    "assumption-of-moses": ProvenanceDossier(
        date_and_origin="Early 1st century AD (c. AD 7–30, composed in Hebrew or Aramaic in Palestine during the lifetimes of Jesus and the Apostles).",
        manuscripts_and_language="Survives in a single 6th-century Latin palimpsest manuscript discovered by Antonio Ceriani in the Ambrosian Library at Milan in 1861 (translated from a Greek version of a Semitic original).",
        translation_source="R. H. Charles (*The Assumption of Moses*, 1897 / *APOT*, 1913).",
        veracity_and_assessment="AUTHENTIC 1ST-CENTURY PALESTINIAN PSEUDEPIGRAPHON: Written during the rule of Herod the Great's sons (ch. 6 explicitly describes Herod's 34-year reign and Varus's partial burning of the Temple in 4 BC). Presents Moses's farewell prophetic charge to Joshua before ascending Mount Nebo, handing over the sacred books to be anointed with cedar oil and preserved in earthen vessels until the end of days. Patristic writers (Clement of Alexandria, Origen, Didymus the Blind) explicitly identify this work (or its lost ending) as the source of Jude 1:9 (Michael the Archangel contending with the devil over the body of Moses).",
    ),
    "revelation-of-moses-hebrew": ProvenanceDossier(
        date_and_origin="Late Antique / Early Medieval Hebrew Merkabah period (*Gedullat Moshe* / Visions of Heaven and Hell).",
        manuscripts_and_language="Hebrew (first printed in Salonika in 1727 from older manuscript traditions).",
        translation_source="Moses Gaster (1893 *Journal of the Royal Asiatic Society* translation).",
        veracity_and_assessment="A classic Hebrew *Hekhalot* (Heavenly Palaces) vision in which Metatron, the Angel of the Presence, transforms Moses's flesh into torches of fire and guides him through the Seven Heavens—where Moses sees the angels of every firmament, the Temple on high, the Patriarchs, and the state of the wicked and righteous dead.",
    ),
    "martyrdom-and-ascension-of-isaiah": ProvenanceDossier(
        date_and_origin="*Martyrdom of Isaiah* (ch. 1–5): 2nd–1st century BC Second Temple Jewish narrative (later combined with the Christian *Vision/Ascension of Isaiah*).",
        manuscripts_and_language="Preserved complete in Ge'ez Ethiopic, with Greek (4th-century Amherst Papyrus), Latin, and Old Church Slavonic witnesses.",
        translation_source="R. H. Charles (*The Apocrypha and Pseudepigrapha of the Old Testament*, Oxford, 1913, Vol. II).",
        veracity_and_assessment="HIGHLY SIGNIFICANT SECOND TEMPLE PSEUDEPIGRAPHON: Chapters 1–5 narrate how the wicked King Manasseh, incited by the false prophet Belkira (Beliar/Sammael), had the prophet Isaiah sawn in sunder with a wood-saw while Isaiah's lips spoke with the Holy Spirit—preserving the ancient Jewish tradition explicitly referenced in Hebrews 11:37 ('they were sawn asunder'). (Note: Only R. H. Charles's 1913 public-domain translation of Chapters 1–5 is included here.)",
    ),
    "2-baruch": ProvenanceDossier(
        date_and_origin="Late 1st century AD (c. AD 90–110, composed in Judea in Hebrew or Aramaic alongside 4 Ezra in the generation after the AD 70 destruction of Jerusalem).",
        manuscripts_and_language="Classical Syriac (discovered by Antonio Ceriani in a 6th-century Syriac Bible codex in the Ambrosian Library at Milan in 1866); a 4th-century Greek fragment was later found at Oxyrhynchus (P.Oxy. 403). Chapters 78–87 (the *Epistle of Baruch*) were preserved in numerous Syriac Bibles.",
        translation_source="R. H. Charles (*The Apocalypse of Baruch*, 1896 / *APOT*, Oxford, 1913, Vol. II, pp. 481–524).",
        veracity_and_assessment="ONE OF THE GREATEST 1ST-CENTURY JEWISH APOCALYPSES: Narrates how four angels first hid the sacred Temple vessels (the veil, ephod, mercy-seat, and Urim and Thummim) inside the earth before the Chaldeans could seize them (ch. 6)—so they might be restored when Jerusalem is renewed—and records Baruch's sevenfold fasts, theological dialogues with the Lord on the fall of Adam ('each of us has been the Adam of his own soul,' 54:19), the vision of the twelve alternating dark and bright waters (ch. 53–74), the nature of the resurrection body (ch. 49–51), and Baruch's epistle to the lost Nine and a Half Tribes beyond the Euphrates (ch. 78–87).",
    ),
    "3-baruch": ProvenanceDossier(
        date_and_origin="Late 1st to 2nd century AD (composed in Greek after AD 70, with minor Christian redactions).",
        manuscripts_and_language="Koine Greek (two manuscripts) and Old Church Slavonic.",
        translation_source="H. M. Hughes in R. H. Charles (*APOT*, Oxford, 1913, Vol. II).",
        veracity_and_assessment="As Baruch weeps over the ruined Temple by the river Kidron, the angel Phanuel ('Interpreter of Revelations') takes him through Five Heavens—showing him the builders of the Tower of Babel in the first and second heavens, the cosmic serpent/Hades and the Phoenix shading the sun in the third heaven, the lake of birds where the souls of the righteous assemble in the fourth heaven, and the Archangel Michael receiving the virtues and prayers of humans in golden bowls in the fifth heaven to carry before God.",
    ),
    "4-baruch": ProvenanceDossier(
        date_and_origin="Early 2nd century AD (c. AD 118–136, composed in Hebrew/Aramaic or Greek in Palestine prior to the Bar Kokhba revolt, later lightly Christianized in the final chapter).",
        manuscripts_and_language="Koine Greek (*Paraleipomena Jeremiou* — 'Things Omitted from Jeremiah'), Ge'ez Ethiopic (where it is canonical in the Ethiopian Orthodox Bible as *Säqoqawä Eremyas* / Rest of the Words of Baruch), Armenian, and Slavonic.",
        translation_source="Robert A. Kraft & Ann Elizabeth Purintun (1987 CATSS Public Domain / Free Non-Commercial Edition, University of Pennsylvania).",
        veracity_and_assessment="CANONICAL IN THE ETHIOPIAN ORTHODOX BIBLE: Shares with 2 Baruch the hiding of the Temple vessels inside the earth before the Babylonian army enters Jerusalem, and tells how Jeremiah sent Abimelech (Ebed-Melech the Ethiopian of Jeremiah 38) to gather figs from the estate of Agrippa—where Abimelech fell asleep beneath a tree for 66 years, awaking with the figs still dripping fresh milk after the Exile had ended, and how an eagle carried Baruch's letter and fifteen figs to Jeremiah in Babylon to revive the dead and lead the exiles home.",
    ),
    "apocalypse-of-elijah": ProvenanceDossier(
        date_and_origin="Late 1st to 3rd century AD (composed in Egypt; combines a Jewish prophetic base with early Egyptian Christian eschatology).",
        manuscripts_and_language="Sahidic and Akhmimic Coptic (4th-century papyrus manuscripts discovered in Upper Egypt in 1893 and edited by Georg Steindorff), plus a Greek fragment.",
        translation_source="Georg Steindorff / early 20th-century English translation.",
        veracity_and_assessment="Patristic writers (Origen and Jerome) noted that Paul's quotation in 1 Corinthians 2:9 ('Eye hath not seen, nor ear heard...') came from an ancient *Apocalypse of Elijah*. The surviving Coptic text opens with the call to fast with a pure heart, describes the thrones, crowns, and white garments awaiting the overcomers, and gives one of the earliest detailed accounts of the final Antichrist ('the Son of Lawlessness' / 'Shameless One'), the martyrdom of the virgin Tabitha, and the return of Elijah and Enoch from heaven to slay the Antichrist before the Millennial reign.",
    ),
    "words-of-gad-the-seer": ProvenanceDossier(
        date_and_origin="Disputed: ranges from a 1st–3rd century AD Jewish-Christian Hebrew composition (Meir Bar-Ilan) to a medieval Jewish mystical/apocalyptic pseudepigraphon.",
        manuscripts_and_language="Biblical-style vocalized Hebrew; preserved in a single manuscript (Cambridge University Library MS Oo.1.20) acquired by Claudius Buchanan from the Black Jews of Cochin, India in 1806.",
        translation_source="Prof. Meir Bar-Ilan (first critical English translation).",
        veracity_and_assessment="Takes its title from 1 Chronicles 29:29 ('Now the acts of David the king, first and last, behold, they are written in the book of Samuel the seer, and in the book of Nathan the prophet, and in the book of Gad the seer'). Across 14 chapters, it includes apocalyptic visions of the lamb crowned by God on the altar (remarkable for its parallel to the Book of Revelation inside a synagogue Hebrew codex), David's census and the threshing-floor of Araunah the Jebusite, a Psalm against Edom (ch. 4), and King Solomon's prayer at Gibeon.",
    ),
    "damascus-zadokite-document": ProvenanceDossier(
        date_and_origin="c. 100 BC (original Second Temple Essene composition).",
        manuscripts_and_language="Biblical Hebrew; first discovered in 1896 by Solomon Schechter in two medieval manuscripts (10th and 12th century AD) in the Cairo Genizah of the Ben Ezra Synagogue, and spectacularly authenticated in 1947–1952 when ten ancient copies (4Q266–273, 5Q12, 6Q15) dating to the 1st century BC were found in the Dead Sea Scrolls caves at Qumran!",
        translation_source="R. H. Charles (*Fragments of a Zadokite Work*, 1912 / *APOT*, 1913).",
        veracity_and_assessment="AUTHENTIC DEAD SEA SCROLLS DOCUMENT (4QD / CD): The only major sectarian scroll of the Qumran community discovered *before* 1947. Divided into the *Exhortation* (recounting how God visited a faithful remnant 390 years after Nebuchadnezzar, raised up for them a 'Teacher of Righteousness' to lead them in the 'New Covenant in the land of Damascus,' and warned against the 'Man of Scoffing' and the 'Three Nets of Belial') and the *Statutes* (governing Sabbath observance, oaths, purity, and the Council of the Camp overseen by the *Mebaqqer* / Guardian).",
    ),
    "qumran-community-rule": ProvenanceDossier(
        date_and_origin="c. 150–100 BC (Qumran Cave 1 parchment scroll 1QS).",
        manuscripts_and_language="Hebrew; discovered in Cave 1 at Qumran by Bedouin shepherds in 1947 (now housed in the Shrine of the Book, Israel Museum, Jerusalem).",
        translation_source="Selected excerpt translation of the Qumran *Serekh ha-Yahad* (Manual of Discipline).",
        veracity_and_assessment="AUTHENTIC DEAD SEA SCROLL (1QS): The foundational constitution of the Qumran *Yahad* ('Community'), setting forth the covenant entry ceremony of the Priests and Levites, the treatise on the Two Spirits (the Prince of Light vs. the Angel of Darkness), and the communal order of the Twelve Men and Three Priests who prepare the way of the Lord in the wilderness.",
    ),
    "apocalypse-of-adam": ProvenanceDossier(
        date_and_origin="1st to 2nd century AD (widely considered by scholars such as George MacRae and Pheme Perkins to be a pre-Christian or non-Christian Jewish-Gnostic Sethian apocalypse).",
        manuscripts_and_language="Sahidic Coptic (discovered in 1945 in the Nag Hammadi Library, Codex V, Tractate 5; translated from a Greek original).",
        translation_source="George W. MacRae.",
        veracity_and_assessment="AUTHENTIC NAG HAMMADI TRACTATE (NHC V, 5): Presented as the deathbed revelation given by Adam in the 700th year of his life to his son Seth, recounting how Adam and Eve initially walked in a glory higher than the creator-archon until their glory was divided, how three majestic celestial men appeared to Adam in a sleep of instruction to reveal the future Flood, the preservation of the seed of Seth, and the coming of the 'Illuminator of Knowledge.'",
    ),
    "second-treatise-of-the-great-seth": ProvenanceDossier(
        date_and_origin="Late 2nd to 3rd century AD (composed in Greek in Alexandria or Syria).",
        manuscripts_and_language="Sahidic Coptic (discovered in 1945 in Nag Hammadi Codex VII, Tractate 2).",
        translation_source="Roger A. Bullard & Joseph A. Gibbons.",
        veracity_and_assessment="AUTHENTIC NAG HAMMADI TRACTATE (NHC VII, 2): A Gnostic Christian discourse spoken in the first person by the heavenly Christ ('the Great Seth') describing His descent from the Pleroma into the world, a Docetic interpretation of the Passion (in which Simon of Cyrene bore the cross in place of the living Savior), and a call to unity in the bridal chamber of light.",
    ),
    "melchizedek-nhc": ProvenanceDossier(
        date_and_origin="Late 2nd to 3rd century AD (composed in Greek in Egypt).",
        manuscripts_and_language="Sahidic Coptic (fragmentary papyrus tractate preserved in Nag Hammadi Codex IX, Tractate 1).",
        translation_source="Birger A. Pearson & Søren Giversen.",
        veracity_and_assessment="AUTHENTIC NAG HAMMADI TRACTATE (NHC IX, 1): A remarkable Coptic Christian-Gnostic apocalypse in which the angel Gamaliel appears to Melchizedek, 'Priest of God Most High,' revealing to him beforehand the future incarnation, real physical suffering, crucifixion, and third-day resurrection of Jesus Christ (explicitly refuting Docetism!), and instructing Melchizedek in his eternal high-priestly baptism and offering in the heavenly sanctuary.",
    ),
    "apocryphon-of-john": ProvenanceDossier(
        date_and_origin="c. AD 120–180 (known to and summarized by Irenaeus of Lyons in *Against Heresies* 1.29 around AD 180).",
        manuscripts_and_language="Sahidic Coptic; survives in four ancient codices—three in the Nag Hammadi Library (Codices II, III, and IV, discovered in 1945) and one in the 5th-century Berlin Gnostic Codex (BG 8502).",
        translation_source="Frederik Wisse (*The Nag Hammadi Library in English*).",
        veracity_and_assessment="FOUNDATIONAL NAG HAMMADI TRACTATE (NHC II, 1): Opens shortly after the Ascension as John the brother of James goes up to the Temple, is challenged by a Pharisee named Arimanios, and turns aside in grief to the desert mountain—where the heavens open and the Savior appears in a threefold luminous form (Child, Elder, and Servant) declaring, 'John, John, why do you doubt, and why are you afraid? ... I am the Father, I am the Mother, I am the Son,' before unfolding the classic Sethian cosmogony of the Invisible Spirit, Barbelo, Sophia, and the awakening of Adam.",
    ),
    "apocryphon-of-james": ProvenanceDossier(
        date_and_origin="Early to mid-2nd century AD (c. AD 100–150; many scholars such as Ron Cameron and Helmut Koester note that its sayings tradition is independent of the canonical Gospels).",
        manuscripts_and_language="Subakhmimic Coptic (preserved in the Jung Codex—Nag Hammadi Codex I, Tractate 2).",
        translation_source="Francis E. Williams.",
        veracity_and_assessment="AUTHENTIC NAG HAMMADI TRACTATE (NHC I, 2): Framed as a secret epistle originally written in Hebrew characters by James explaining how, 550 days after rising from the dead, the twelve disciples were sitting together recalling what the Savior had taught each of them and 'putting their books in order,' when Jesus appeared and drew James and Peter aside to fill them with the Spirit, exhorting them with parables (the Palm Shoot, the Grain of Wheat, the Ear of Grain) not to fear martyrdom and to 'be filled with the Spirit' before James and Peter ascend in spirit to hear the hymns of the Third Heaven.",
    ),
    "book-of-thomas-the-contender": ProvenanceDossier(
        date_and_origin="First half of the 3rd century AD (composed in Greek in eastern Syria, the center of the Judas Thomas tradition).",
        manuscripts_and_language="Sahidic Coptic (Nag Hammadi Codex II, Tractate 7, bound in the same codex as the *Gospel of Thomas*).",
        translation_source="John D. Turner.",
        veracity_and_assessment="AUTHENTIC NAG HAMMADI TRACTATE (NHC II, 7): Begins: 'The secret words that the savior spoke to Judas Thomas which I, even I, Mathaias, wrote down, while I was walking, listening to them speak with one another.' Features a dialogue between the risen Jesus and His 'twin brother' Thomas on self-knowledge, conquering the consuming fire of bodily passions, and a closing series of Beatitudes and Woes.",
    ),
    "letter-of-peter-to-philip": ProvenanceDossier(
        date_and_origin="Late 2nd century AD (c. AD 180–200, composed in Greek).",
        manuscripts_and_language="Sahidic Coptic (preserved in Nag Hammadi Codex VIII, Tractate 2, and a second copy discovered in the 5th-century Codex Tchacos alongside the *Gospel of Judas*).",
        translation_source="Marvin W. Meyer.",
        veracity_and_assessment="AUTHENTIC NAG HAMMADI TRACTATE (NHC VIII, 2): Opens with a letter from Peter to Philip calling him to rejoin the other Apostles as they gather on the Mount of Olives according to the command of the risen Christ. As they pray on the mountain, a great light appears and the voice of Jesus answers their questions regarding the deficiency of the aeons, how to contend against the archons, and why Christ suffered in the flesh for their sakes, before the Apostles return to Jerusalem to heal and preach in the Temple portico.",
    ),
    "gospel-of-mary-magdalene": ProvenanceDossier(
        date_and_origin="Early to mid-2nd century AD (c. AD 120–160, composed in Greek).",
        manuscripts_and_language="Sahidic Coptic (5th-century Berlin Codex BG 8502, purchased in Cairo in 1896 by Carl Reinhardt, with pages 1–6 and 11–14 missing) and two 3rd-century Greek papyrus fragments from Egypt (Papyrus Rylands 463 and Papyrus Oxyrhynchus 3525).",
        translation_source="George W. MacRae & R. McL. Wilson (with multi-version comparison).",
        veracity_and_assessment="AUTHENTIC 2ND-CENTURY CHRISTIAN DIALOGUE GOSPEL: After the risen Savior commissions the disciples to preach the Gospel of the Kingdom and departs, the disciples weep in fear of persecution until Mary Magdalene stands up, comforts them, and—at Peter's invitation—relates a vision and teaching the Lord had given her regarding the ascent of the soul past the cosmic powers. When Andrew and Peter question whether the Savior would have spoken privately to a woman, Levi defends Mary: 'If the Savior made her worthy, who are you indeed to reject her?'",
    ),
    "pistis-sophia": ProvenanceDossier(
        date_and_origin="3rd century AD (composed in Greek in Egypt; Books I–III c. AD 250–300, Book IV slightly earlier).",
        manuscripts_and_language="Sahidic Coptic; survives in a single 346-page parchment codex (the Askew Codex, British Library MS Add. 5114) purchased by the British Museum in 1785.",
        translation_source="G. R. S. Mead (1921 revised edition from the Coptic).",
        veracity_and_assessment="THE MOST EXTENSIVE SURVIVING COPTIC POST-RESURRECTION DIALOGUE: Opens with the remarkable declaration that after Jesus rose from the dead, He spent **eleven years** instructing His disciples up to the regions of the First Mystery, and that in the twelfth year, as He sat with them on the Mount of Olives, a blinding Vesture of Light descended upon Him from the Treasury of Light. He ascends through the firmaments and returns to explain to Mary Magdalene, Peter, John, Philip, Matthew, and Martha the Thirteen Repentances of Pistis Sophia (who sang praises matched by the canonical Psalms and Odes of Solomon) and the mysteries of the ineffable ordinances and tokens of the Light-Kingdom.",
    ),
    "epistle-of-the-apostles": ProvenanceDossier(
        date_and_origin="Mid-2nd century AD (c. AD 140–170, composed in Greek in Asia Minor or Egypt).",
        manuscripts_and_language="Complete text preserved in Ge'ez Ethiopic (five manuscripts edited by Louis Guerrier in 1913) and a 4th/5th-century Achmimic Coptic papyrus codex in Cairo (edited by Carl Schmidt in 1919), plus a 5th-century Latin palimpsest leaf in Vienna.",
        translation_source="M. R. James (*The Apocryphal New Testament*, 1924, combining the Coptic and Ethiopic texts).",
        veracity_and_assessment="HIGHLY SIGNIFICANT 2ND-CENTURY ORTHODOX POST-RESURRECTION DIALOGUE: Written in the name of the Eleven Apostles against the Gnostics Simon and Cerinthus. Remarkably uses the literary form of a **40-day post-resurrection dialogue** not for Gnosticism, but to defend the physical bodily resurrection of Jesus ('Handle me, that I am no bodiless ghost'), the Descent of Christ into the Spirit World (ch. 27, where the Lord explicitly states that He preached to the righteous dead and gave them with His right hand **'the baptism of life and forgiveness'**), and the celebration of the Agape and Eucharist until cockcrow.",
    ),
    "questions-of-bartholomew": ProvenanceDossier(
        date_and_origin="2nd to 4th century AD (mentioned by Jerome in his *Commentary on Matthew* in AD 398).",
        manuscripts_and_language="Koine Greek (two manuscripts in Vienna and Jerusalem), Latin (two recensions), and Old Church Slavonic.",
        translation_source="M. R. James (*The Apocryphal New Testament*, 1924).",
        veracity_and_assessment="A vivid post-resurrection apocryphon in five chapters: (1) Bartholomew asks the risen Lord where He went when He vanished from the cross, and Jesus reveals His Harrowing of Hades to rescue Adam and the Patriarchs while chaining Beliar; (2) the Apostles gently entreat Mary the Mother of the Lord to tell them how she conceived the Incomprehensible One in the Temple; (3) the Apostles gaze into the abyss from the Mount of Olives; and (4) Jesus commands Beliar to come up bound before Bartholomew and recount how he was first created as Satanael before refusing to reverence Adam, the image of God.",
    ),
    "interrogatio-johannis": ProvenanceDossier(
        date_and_origin="6th–11th century AD Byzantine/Slavonic dualist Christian apocryphon (drawing on older 2nd–4th century Greek apocalyptic traditions).",
        manuscripts_and_language="Latin (two manuscripts preserved in the Inquisition archives of Carcassonne and in Vienna, brought from Bulgaria to Italy c. 1190). Also known as *The Secret Supper*.",
        translation_source="M. R. James (*The Apocryphal New Testament*, 1924).",
        veracity_and_assessment="Framed around John 13:23–25 as the Apostle John leans on Jesus's breast at the Last Supper and asks the Lord about the state of heaven before the fall of Satan, the Seven Heavens, the creation of Adam, the mission of Enoch, and the Final Judgment. Served as the primary scriptural book of the medieval Bogomils and Cathars.",
    ),
    "secret-gospel-of-mark": ProvenanceDossier(
        date_and_origin="Contested: Either an authentic late-2nd-century letter of Clement of Alexandria (c. AD 150–215) quoting an expanded Alexandrian 'mystic' edition of the Gospel of Mark, or an elaborate late-antique/modern pastiche.",
        manuscripts_and_language="Koine Greek; discovered in 1958 by Columbia University professor Morton Smith handwritten in an 18th-century hand on the blank end-leaves of a 1646 printed edition of the *Letters of Ignatius* in the Monastery of Mar Saba in the Judean wilderness.",
        translation_source="Morton Smith (1973 translation of the Mar Saba Letter of Clement to Theodore).",
        veracity_and_assessment="In the letter, Clement of Alexandria writes to a believer named Theodore explaining that when Mark came to Alexandria after Peter's martyrdom, he expanded his first Gospel with additional 'spiritual' actions for those being initiated into the greater mysteries, but that the libertine heretic Carpocrates had obtained a copy by deceit and polluted it. Clement quotes two passages from this 'Secret Mark' (inserted after Mark 10:34 and 10:46), describing Jesus raising a rich young man from a rock-cut tomb at Bethany and instructing him by night six days later while the youth wore a linen cloth.",
    ),
    "ptolemy-john-prologue": ProvenanceDossier(
        date_and_origin="c. AD 150–170 (Rome or Alexandria).",
        manuscripts_and_language="Koine Greek and Latin; preserved verbatim by Irenaeus of Lyons in *Against Heresies* 1.8.5 (written c. AD 180).",
        translation_source="Robert M. Grant / Ante-Nicene Fathers translation.",
        veracity_and_assessment="AUTHENTIC 2ND-CENTURY EXEGESIS: The earliest surviving verse-by-verse commentary on the Prologue of the Gospel of John (John 1:1–18), written by Ptolemy, the foremost Italian disciple of Valentinus, interpreting the Logos, Life, Light, Grace, and Only-Begotten as the primordial syzygies of the divine Ogdoad.",
    ),
    "gospel-of-marcion": ProvenanceDossier(
        date_and_origin="c. AD 140–144 (Rome; compiled by the shipowner and theologian Marcion of Sinope).",
        manuscripts_and_language="Koine Greek (no direct manuscript survives; painstakingly reconstructed from the extensive verbatim citations in Tertullian's *Against Marcion* Book IV and Epiphanius's *Panarion* 42).",
        translation_source="Patristic reconstruction from Tertullian and Epiphanius.",
        veracity_and_assessment="AUTHENTIC RECONSTRUCTION OF THE FIRST PUBLISHED NEW TESTAMENT CANON'S GOSPEL: In AD 140, Marcion compiled the earliest known fixed two-part Christian canon (*Evangelion* and *Apostolikon* of ten Pauline letters). His *Gospel of the Lord* corresponds closely to the Gospel of Luke (beginning at Luke 3:1 / 4:31 without the infancy narratives).",
    ),
    "apocalypse-of-pseudo-methodius": ProvenanceDossier(
        date_and_origin="Late 7th century AD (c. AD 691–692, composed in Syriac at Sinjar in northern Mesopotamia, attributed pseudonymously to the 4th-century martyr Bishop Methodius of Olympus).",
        manuscripts_and_language="Classical Syriac (Vatican Syriac MS 58), rapidly translated into Greek, Latin, Slavonic, and Arabic.",
        translation_source="Paul J. Alexander / Francisco Javier Martinez critical translation.",
        veracity_and_assessment="One of the most influential apocalyptic works of the Middle Ages. Its first half (Chapters 1–7) incorporates rich pre-Islamic Syriac Christian legends from the *Cave of Treasures* regarding Adam and Eve's departure from Paradise, the birth of Cain and Abel's twin sisters (Calmana and Debora), Enoch, Noah's Ark, and Nimrod, while its second half (Chapters 8–14) prophesies the Arab conquests, the enclosing of Gog and Magog behind the Gates of the North by Alexander the Great, and the Last World Emperor laying his crown upon the Cross at Golgotha.",
    ),
    "sentences-of-sextus": ProvenanceDossier(
        date_and_origin="Late 2nd century AD (c. AD 180–200, Alexandria; cited with high praise by Origen in *Against Celsus* 8.30 and *Commentary on Matthew* 15.3 as a book cherished by the majority of Christians).",
        manuscripts_and_language="Koine Greek (Patmos MS 263 and Vatican MS 742), Latin (translated by Rufinus of Aquileia c. AD 397), Syriac, Armenian, and Sahidic Coptic (discovered in 1945 in **Nag Hammadi Codex XII, Tractate 1**!).",
        translation_source="Richard A. Edwards & Robert A. Wild.",
        veracity_and_assessment="AUTHENTIC 2ND-CENTURY CHRISTIAN WISDOM MAXIMS (AND NAG HAMMADI TRACTATE XII, 1): A collection of 451 concise moral aphorisms adapted by a 2nd-century Christian sage from Neopythagorean and Stoic gnomologies, teaching purity of mind as the true temple of God, self-mastery, truthfulness, and becoming worthy of God.",
    ),
    "egyptian-book-of-breathings-and-gilgamesh": ProvenanceDossier(
        date_and_origin="*Book of Breathings (Shai en Sensen)*: Late Period to Ptolemaic/Roman Period Egypt (c. 350 BC – AD 100, Thebes); *Epic of Gilgamesh Tablet XI*: Standard Babylonian version by Sin-leqi-unninni (c. 1200 BC, discovered in the Library of Ashurbanipal at Nineveh in 1853/1872).",
        manuscripts_and_language="*Book of Breathings*: Hieratic and hieroglyphic Egyptian papyri (including Louvre Papyrus N 3284 and the Joseph Smith Papyri I, X, and XI from Thebes); *Gilgamesh*: Akkadian cuneiform clay tablets.",
        translation_source="P. J. de Horrack (1877 translation of the Louvre *Book of Breathings*) and George Smith / R. Campbell Thompson (translation of the *Gilgamesh* Deluge Tablet).",
        veracity_and_assessment="AUTHENTIC ANCIENT NEAR EASTERN MONUMENTS: The *Book of Breathings Made by Isis* is a Ptolemaic Theban funerary composition praying that the deceased priest's soul may be washed by Ptah and Thoth, enter the Hall of the Two Truths (Ma'at), and breathe and live forever among the gods—famous in Latter-day Saint history because the Theban papyrus scroll of the priest Hor (JSP I, X–XI) acquired by Joseph Smith in Kirtland in July 1835 was a *Book of Breathings*. Paired here with the cuneiform Mesopotamian Flood account of Utnapishtim from Tablet XI of the *Epic of Gilgamesh*.",
    ),
}


def _make_provenance_block(dossier: ProvenanceDossier, book_title: str) -> ContentBlock:
    """Create a styled HTML provenance & historical veracity box for the start of a book."""
    html_box = (
        f"<strong>📜 Source, Provenance &amp; Historical Veracity — {escape_xhtml(book_title)}</strong><br/>"
        f"<strong>• Date &amp; Origin:</strong> {escape_xhtml(dossier.date_and_origin)}<br/>"
        f"<strong>• Language &amp; Manuscripts:</strong> {escape_xhtml(dossier.manuscripts_and_language)}<br/>"
        f"<strong>• Translation Source:</strong> {escape_xhtml(dossier.translation_source)}<br/>"
        f"<strong>• Veracity &amp; Scholarly Assessment:</strong> {escape_xhtml(dossier.veracity_and_assessment)}"
    )
    plain_text = (
        f"Source, Provenance & Historical Veracity — {book_title} | "
        f"Date & Origin: {dossier.date_and_origin} | "
        f"Language & Manuscripts: {dossier.manuscripts_and_language} | "
        f"Translation Source: {dossier.translation_source} | "
        f"Veracity & Scholarly Assessment: {dossier.veracity_and_assessment}"
    )
    return ContentBlock(
        block_type=BlockType.HEADNOTE,
        text=plain_text,
        html_text=html_box,
    )


def _attach_dossier_to_book(book: Book, dossier_key: str) -> Book:
    dossier = PROVENANCE_DATABASE.get(dossier_key)
    if not dossier:
        return book
    book.heading = (
        f"Date & Origin: {dossier.date_and_origin} — "
        f"Translation: {dossier.translation_source} — "
        f"Veracity: {dossier.veracity_and_assessment}"
    )
    # Also prepend the rich HTML box into the first chapter or front_matter chapter so readers
    # who jump directly to Chapter 1 via the TOC see the provenance & veracity box immediately.
    target_ch = book.front_matter[0] if book.front_matter else (book.chapters[0] if book.chapters else None)
    if target_ch is not None:
        prov_block = _make_provenance_block(dossier, book.title)
        if target_ch.blocks:
            target_ch.blocks.insert(0, prov_block)
        else:
            # If the chapter uses `verses` (like Tobit or Jasher), put the provenance summary into `headnote`
            target_ch.headnote = (
                f"[Source & Historical Veracity] Date & Origin: {dossier.date_and_origin} • "
                f"Manuscripts: {dossier.manuscripts_and_language} • "
                f"Translation: {dossier.translation_source} • "
                f"Assessment: {dossier.veracity_and_assessment}"
            )
    return book


def _consolidate_book_into_single_chapter_if_needed(book: Book, max_chapters: int = 4) -> Book:
    """Ensure all chapters (front_matter + chapters) of the book are preserved in sequential order."""
    for ch in book.front_matter:
        ch.is_front_matter = False
    book.chapters = book.front_matter + book.chapters
    book.front_matter = []
    return book


def _collect_compendium_books(
    extra_canon_dir: Path,
    apocrypha_dir: Path,
    gutenberg_dir: Path,
    pseudepigrapha_com_path: Path,
    divisions: set[str] | None = None,
) -> list[Book]:
    """Collect deduplicated extra-canonical books for the requested compendium divisions (`I`–`VII`)."""
    active_divs = divisions or {"I", "II", "III", "IV", "V", "VI", "VII"}
    books: list[Book] = []

    # Pre-load verified Public Domain / Free Non-Commercial works from `pseudepigrapha_com.jsonl`
    # (Excludes post-1929 copyrighted translations such as 1977/1990 Nag Hammadi Library, 1983-1985 OTP,
    # NRSV 3 Maccabees/Psalm 151, Qimron 1QS, Speiser ANET, Rhodes, and Garstad Pseudo-Methodius)
    pcom_allowed_ids = {
        "book-of-noah",  # R. H. Charles (1913)
        "assumption-of-moses",  # R. H. Charles (1897/1913)
        "revelation-of-moses-hebrew",  # Moses Gaster (1893) / Alexander Walker (1870)
        "martyrdom-and-ascension-of-isaiah",  # Sec 0 only: R. H. Charles (1913 Martyrdom of Isaiah ch. 1-5)
        "2-baruch",  # R. H. Charles (1896/1913 Syriac Apocalypse of Baruch)
        "3-baruch",  # H. M. Hughes in R. H. Charles (1913 Greek Apocalypse of Baruch)
        "4-baruch",  # Robert A. Kraft (1987 CATSS Public Domain / Free Non-Commercial edition)
        "damascus-zadokite-document",  # R. H. Charles (1912/1913 Fragments of a Zadokite Work)
        "epistle-of-the-apostles",  # M. R. James (1924 The Apocryphal New Testament)
        "questions-of-bartholomew",  # M. R. James (1924 The Apocryphal New Testament)
        "interrogatio-johannis",  # M. R. James (1924 The Apocryphal New Testament)
        "gospel-of-marcion",  # 19th-century patristic reconstruction
    }
    pcom_by_div: dict[str, list[dict]] = defaultdict(list)
    if pseudepigrapha_com_path.exists():
        with open(pseudepigrapha_com_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    if rec.get("id") in pcom_allowed_ids:
                        pcom_by_div[rec.get("division", "II")].append(rec)

    div_prefix_map = {
        "I": "[I. Deuterocanon]",
        "II": "[II. OT Pseudepigrapha]",
        "III": "[II. OT Pseudepigrapha]",
        "IV": "[IV. Wisdom & Qumran]",
        "V": "[V. Apocryphal Gospels]",
        "VI": "[VI. Acts, Dialogues & Apocalypses]",
        "VII": "[VII. Apostolic Fathers]",
    }

    _BOILERPLATE_SUBSTRINGS = (
        "html layout,",
        "adam jerome",
        "scanned and edited by joshua williams",
        "red numbers identify chapters",
        "black numbers within the text refer to verses",
        "edited and adapted by george lyons",
        "edited by wesley caspers",
        "edited by diane morgan",
        "wesley center for applied theology",
        "at northwest nazarene university",
        "text may be freely used for personal or scholarly purposes",
        "copyright 2000",
        "[and they helped us when we sinned], finish",
    )

    def _clean_pcom_paragraphs(wid: str, raw_paras: list[str], stitle: str) -> list[str]:
        cleaned: list[str] = []
        for p in raw_paras:
            cp = clean_prose_text(p)
            if not cp:
                continue
            low = cp.lower()
            # Keep Robert A. Kraft's required 1987 CATSS Public Domain header in 4-baruch
            if wid != "4-baruch" and any(b in low for b in _BOILERPLATE_SUBSTRINGS):
                continue
            if wid == "2-baruch" and low in (
                "for the",
                "the apocrypha and pseudepigrapha of the old testament in english",
                "(oxford: oxford university press, 1913) 2: 481-524",
            ):
                continue
            if not cleaned and low == stitle.lower():
                continue
            # Deduplicate consecutively identical paragraphs (e.g. in 2-baruch)
            if cleaned and cleaned[-1] == cp:
                continue
            cleaned.append(cp)
        return cleaned

    def _build_pcom_books_for_div(div_code: str) -> list[Book]:
        out: list[Book] = []
        prefix = div_prefix_map.get(div_code, f"[{div_code}]")
        for rec in pcom_by_div.get(div_code, []):
            wid = str(rec["id"])
            wtitle = clean_prose_text(str(rec["title"]))
            if wid == "martyrdom-and-ascension-of-isaiah":
                wtitle = "The Martyrdom of Isaiah (Chapters 1–5, R. H. Charles 1913 Translation)"
            wcat = clean_prose_text(str(rec.get("category", "Pseudepigrapha")))
            raw_sections = rec.get("sections", [])
            if wid == "martyrdom-and-ascension-of-isaiah":
                # Keep only Section 0 (R. H. Charles 1913 Martyrdom of Isaiah ch. 1-5);
                # exclude Section 1 (M. A. Knibb 1985 Ascension of Isaiah ch. 6-11).
                raw_sections = raw_sections[:1]
            chs: list[Chapter] = []
            for s_idx, sec in enumerate(raw_sections, start=1):
                stitle = clean_prose_text(str(sec.get("title") or f"Section {s_idx}"))
                paras = _clean_pcom_paragraphs(wid, sec.get("paragraphs", []), stitle)
                blocks = [ContentBlock(block_type=BlockType.PARAGRAPH, text=p) for p in paras]
                if blocks:
                    chs.append(Chapter(id=f"{wid}-sec-{s_idx:03d}", title=stitle, blocks=blocks))
            if not chs:
                continue
            bk_obj = Book(
                id=wid,
                title=f"{prefix} {wtitle}",
                full_title=wtitle,
                author=wcat,
                chapters=chs,
            )
            _attach_dossier_to_book(bk_obj, wid)
            out.append(bk_obj)
        return out

    # ==========================================================================
    # DIVISION I: THE 15 KJV DEUTEROCANONICAL BOOKS (`extra-canon/`)
    # ==========================================================================
    if "I" in active_divs:
        kjv_work = ingest_kjv_apocrypha(extra_canon_dir)
        for bk in kjv_work.books:
            bk.title = f"[I. Deuterocanon] {bk.title}"
            _attach_dossier_to_book(bk, bk.id)
            _consolidate_book_into_single_chapter_if_needed(bk, max_chapters=2)
            books.append(bk)
        books.extend(_build_pcom_books_for_div("I"))

    # Load `forgotten_books_of_eden.jsonl` records grouped by book (used in Divisions II, III, IV)
    fbe_by_book: dict[str, list[dict]] = defaultdict(list)
    if active_divs & {"II", "III", "IV"}:
        with open(apocrypha_dir / "forgotten_books_of_eden.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    fbe_by_book[r.get("book", "Unknown")].append(r)

    # ==========================================================================
    # DIVISION II: MAJOR OLD TESTAMENT PSEUDEPIGRAPHA & REWRITTEN BIBLE
    # ==========================================================================
    if "II" in active_divs:
        # 1. 1 Enoch (R. H. Charles)
        b_enoch_ch = ingest_ista_jsonl_book(
            apocrypha_dir / "book_of_enoch_charles.jsonl",
            "1-enoch-charles",
            "[II. OT Pseudepigrapha] 1 Enoch (R. H. Charles Critical Translation)",
            "The Book of Enoch (Ethiopic Apocalypse of Enoch — R. H. Charles Edition)",
            "R. H. Charles (tr., 1917)",
        )
        _attach_dossier_to_book(b_enoch_ch, "1-enoch-charles")
        _consolidate_book_into_single_chapter_if_needed(b_enoch_ch, max_chapters=3)
        books.append(b_enoch_ch)

        # 2. 1 Enoch (Richard Laurence 1883 105-chapter Gutenberg edition)
        b_enoch_laur = ingest_gutenberg_enoch_laurence(gutenberg_dir / "book_of_enoch_laurence.jsonl")
        b_enoch_laur.title = "[II. OT Pseudepigrapha] 1 Enoch (Richard Laurence 1821/1883 Translation)"
        _attach_dossier_to_book(b_enoch_laur, "enoch-laurence")
        _consolidate_book_into_single_chapter_if_needed(b_enoch_laur, max_chapters=3)
        books.append(b_enoch_laur)

    def _build_fbe_book(raw_bk_name: str, display_title: str, dossier_key: str, max_ch: int = 2) -> Book:
        recs = fbe_by_book.get(raw_bk_name, [])
        bslug = slugify(raw_bk_name)
        chs: list[Chapter] = []
        for idx, rec in enumerate(recs, start=1):
            ctitle = clean_prose_text(rec.get("chapter_title") or f"Chapter {idx}")
            paras = [clean_prose_text(p) for p in rec.get("paragraphs", []) if clean_prose_text(p)]
            if paras and paras[0].lower() == ctitle.lower():
                paras = paras[1:]
            blocks = [ContentBlock(block_type=BlockType.PARAGRAPH, text=p) for p in paras]
            chs.append(Chapter(id=f"{bslug}-ch-{idx:03d}", title=ctitle, blocks=blocks))
        bk_obj = Book(
            id=bslug,
            title=display_title,
            full_title=raw_bk_name,
            author="Rutherford H. Platt Jr. (ed., 1926)",
            chapters=chs,
        )
        _attach_dossier_to_book(bk_obj, dossier_key)
        return _consolidate_book_into_single_chapter_if_needed(bk_obj, max_chapters=max_ch)

    if "II" in active_divs:
        # 3. 2 Enoch (Book of the Secrets of Enoch)
        books.append(
            _build_fbe_book(
                "The Book of the Secrets of Enoch",
                "[II. OT Pseudepigrapha] 2 Enoch (Book of the Secrets of Enoch / Slavonic Enoch)",
                "the-book-of-the-secrets-of-enoch",
                max_ch=2,
            )
        )

        # 4. Book of Jubilees
        b_jub = ingest_ista_jsonl_book(
            apocrypha_dir / "book_of_jubilees.jsonl",
            "book-of-jubilees",
            "[II. OT Pseudepigrapha] The Book of Jubilees (R. H. Charles Edition)",
            "The Book of Jubilees, or the Little Genesis",
            "R. H. Charles (tr., 1917)",
        )
        _attach_dossier_to_book(b_jub, "book-of-jubilees")
        _consolidate_book_into_single_chapter_if_needed(b_jub, max_chapters=4)
        books.append(b_jub)

        # 5. Book of Jasher
        b_jash = ingest_ista_jsonl_book(
            apocrypha_dir / "book_of_jasher.jsonl",
            "book-of-jasher",
            "[II. OT Pseudepigrapha] The Book of Jasher (1840 Translation of 1625 Venice Midrash)",
            "The Book of Jasher (Sefer ha-Yashar)",
            "Mordecai Manuel Noah & Moses Samuel (tr., 1840)",
        )
        _attach_dossier_to_book(b_jash, "book-of-jasher")
        _consolidate_book_into_single_chapter_if_needed(b_jash, max_chapters=4)
        books.append(b_jash)

        # 6. Biblical Antiquities of Philo (Pseudo-Philo)
        b_philo = ingest_ista_jsonl_book(
            apocrypha_dir / "biblical_antiquities_of_philo.jsonl",
            "biblical-antiquities-of-philo",
            "[II. OT Pseudepigrapha] The Biblical Antiquities of Pseudo-Philo (Liber Antiquitatum Biblicarum)",
            "The Biblical Antiquities of Philo (Pseudo-Philo)",
            "M. R. James (tr., 1917)",
        )
        _attach_dossier_to_book(b_philo, "biblical-antiquities-of-philo")
        _consolidate_book_into_single_chapter_if_needed(b_philo, max_chapters=3)
        books.append(b_philo)

        # 7 & 8. First & Second Books of Adam and Eve (deduplicated: loaded once from Forgotten Books of Eden)
        books.append(
            _build_fbe_book(
                "The First Book of Adam and Eve",
                "[II. OT Pseudepigrapha] The First Book of Adam and Eve (Conflict of Adam and Eve with Satan, Part I)",
                "the-first-book-of-adam-and-eve",
                max_ch=2,
            )
        )
        books.append(
            _build_fbe_book(
                "The Second Book of Adam and Eve",
                "[II. OT Pseudepigrapha] The Second Book of Adam and Eve (Conflict of Adam and Eve with Satan, Part II)",
                "the-second-book-of-adam-and-eve",
                max_ch=1,
            )
        )

        # 9 & 10. Latin & Slavonic Lives of Adam and Eve
        b_vita = ingest_ista_jsonl_book(
            apocrypha_dir / "books_of_adam_and_eve.jsonl",
            "books-of-adam-and-eve",
            "[II. OT Pseudepigrapha] The Latin Life of Adam and Eve (Vita Adae et Evae)",
            "The Books of Adam and Eve (Latin Recension)",
            "R. H. Charles (tr., 1913)",
        )
        _attach_dossier_to_book(b_vita, "books-of-adam-and-eve")
        books.append(b_vita)

        b_slav_ae = ingest_ista_jsonl_book(
            apocrypha_dir / "slavonic_life_of_adam_and_eve.jsonl",
            "slavonic-life-of-adam-and-eve",
            "[II. OT Pseudepigrapha] The Slavonic Life of Adam and Eve",
            "The Slavonic Vita Adae et Evae",
            "W. R. Morfill & R. H. Charles (tr., 1913)",
        )
        _attach_dossier_to_book(b_slav_ae, "slavonic-life-of-adam-and-eve")
        books.append(b_slav_ae)

    # Load `early_church_fathers.jsonl` where `author == "Apocrypha"` for unique ANF Vol. 8 works
    anf_apoc_by_work: dict[str, list[dict]] = defaultdict(list)
    ecf_path = gutenberg_dir / "early_church_fathers.jsonl"
    if ecf_path.exists():
        with open(ecf_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                if r.get("author") == "Apocrypha":
                    anf_apoc_by_work[r.get("work", "Unknown")].append(r)

    def _build_anf_work(
        work_names: list[str],
        book_slug: str,
        display_title: str,
        dossier_key: str,
    ) -> Book | None:
        chs: list[Chapter] = []
        sec_idx = 0
        for wname in work_names:
            for rec in anf_apoc_by_work.get(wname, []):
                sec_idx += 1
                stitle = clean_prose_text(rec.get("section_title") or wname)
                if len(work_names) > 1 and wname.split("(")[0].strip().lower() not in stitle.lower():
                    stitle = f"{clean_prose_text(wname)}: {stitle}"
                paras = [clean_prose_text(p) for p in rec.get("paragraphs", []) if clean_prose_text(p)]
                blocks = [ContentBlock(block_type=BlockType.PARAGRAPH, text=p) for p in paras]
                chs.append(Chapter(id=f"{book_slug}-sec-{sec_idx:03d}", title=stitle, blocks=blocks))
        if not chs:
            return None
        bk_obj = Book(
            id=book_slug,
            title=display_title,
            full_title=display_title,
            author="Ante-Nicene Fathers, Volume VIII",
            chapters=chs,
        )
        _attach_dossier_to_book(bk_obj, dossier_key)
        return _consolidate_book_into_single_chapter_if_needed(bk_obj, max_chapters=2)

    # 11. Apocalypse of Moses (Greek Life of Adam and Eve)
    if "II" in active_divs:
        for b_opt in [
            _build_anf_work(
                ["Apocalypse of Moses (unknown date)"],
                "apocalypse-of-moses",
                "[II. OT Pseudepigrapha] The Apocalypse of Moses (Greek Life of Adam and Eve)",
                "apocalypse-of-moses",
            ),
            _build_anf_work(
                ["Testament of Abraham (unknown date)"],
                "testament-of-abraham",
                "[II. OT Pseudepigrapha] The Testament of Abraham (Recensions A & B)",
                "testament-of-abraham",
            ),
            _build_anf_work(
                ["Narrative of Zosimus (unknown date)"],
                "narrative-of-zosimus",
                "[II. OT Pseudepigrapha] The Narrative of Zosimus (History of the Rechabites / Blessed Ones)",
                "narrative-of-zosimus",
            ),
        ]:
            if b_opt:
                books.append(b_opt)
        books.extend(_build_pcom_books_for_div("II"))
        books.extend(_build_pcom_books_for_div("III"))

    # ==========================================================================
    # DIVISION III: THE TESTAMENTS OF THE TWELVE PATRIARCHS (Consolidated into 1 12-Part Book)
    # ==========================================================================
    if "III" in active_divs:
        patriarch_names = [
            "The Testaments of the Twelve Patriarchs",
            "Testament of Reuben",
            "Testament of Simeon",
            "Testament of Levi",
            "The Testament of Judah",
            "The Testament of Issachar",
            "The Testament of Zebulun",
            "The Testament of Dan",
            "The Testament of Naphtali",
            "The Testament Of Gad",
            "The Testament of Asher",
            "The Testament of Joseph",
            "The Testament of Benjamin",
        ]
        pat_chapters: list[Chapter] = []
        for p_idx, pname in enumerate(patriarch_names, start=1):
            recs = fbe_by_book.get(pname, [])
            if not recs:
                continue
            p_blocks: list[ContentBlock] = []
            for r in recs:
                sub_t = clean_prose_text(r.get("chapter_title", ""))
                if sub_t and sub_t.lower() != pname.lower():
                    p_blocks.append(ContentBlock(block_type=BlockType.SUBHEADING, text=sub_t, level=3))
                for p_str in r.get("paragraphs", []):
                    pc = clean_prose_text(p_str)
                    if pc and pc.lower() != sub_t.lower():
                        p_blocks.append(ContentBlock(block_type=BlockType.PARAGRAPH, text=pc))
            pat_chapters.append(
                Chapter(
                    id=f"twelve-patriarchs-{p_idx:02d}",
                    title=clean_prose_text(pname),
                    blocks=p_blocks,
                )
            )
        b_patriarchs = Book(
            id="testaments-of-the-twelve-patriarchs",
            title="[III. Twelve Patriarchs] The Testaments of the Twelve Patriarchs (Reuben through Benjamin)",
            full_title="The Testaments of the Twelve Patriarchs, the Sons of Jacob",
            author="R. H. Charles (tr., 1908)",
            chapters=pat_chapters,
        )
        _attach_dossier_to_book(b_patriarchs, "testaments-of-the-twelve-patriarchs")
        _consolidate_book_into_single_chapter_if_needed(b_patriarchs, max_chapters=3)
        books.append(b_patriarchs)

    # ==========================================================================
    # DIVISION IV: SECOND TEMPLE WISDOM, ODES, APOCALYPSES & ORACLES
    # ==========================================================================
    if "IV" in active_divs:
        for raw_n, disp_t, d_key in [
            ("The Psalms of Solomon", "[IV. Wisdom & Oracles] The Psalms of Solomon (19 Psalms)", "the-psalms-of-solomon"),
            ("The Odes of Solomon", "[IV. Wisdom & Oracles] The Odes of Solomon (42 Early Christian Odes)", "the-odes-of-solomon"),
            ("The Letter of Aristeas", "[IV. Wisdom & Oracles] The Letter of Aristeas (Origin of the Septuagint)", "the-letter-of-aristeas"),
            ("Fourth Book of Maccabees", "[IV. Wisdom & Oracles] The Fourth Book of Maccabees", "fourth-book-of-maccabees"),
            ("The Story of Ahikar", "[IV. Wisdom & Oracles] The Story and Wisdom of Ahikar", "the-story-of-ahikar"),
        ]:
            books.append(_build_fbe_book(raw_n, disp_t, d_key, max_ch=2))

        b_sib = ingest_ista_jsonl_book(
            apocrypha_dir / "sibylline_oracles.jsonl",
            "sibylline-oracles",
            "[IV. Wisdom & Oracles] The Sibylline Oracles (Books I–XIV)",
            "The Sibylline Oracles: Translated from the Greek into English Blank Verse",
            "Milton S. Terry (tr., 1899)",
        )
        _attach_dossier_to_book(b_sib, "sibylline-oracles")
        _consolidate_book_into_single_chapter_if_needed(b_sib, max_chapters=3)
        books.append(b_sib)

        for b_opt in [
            _build_anf_work(
                ["Apocalypse of Esdras (unknown date)"],
                "apocalypse-of-esdras",
                "[IV. Wisdom & Oracles] The Greek Apocalypse of Esdras",
                "apocalypse-of-esdras",
            ),
            _build_anf_work(
                ["Apocalypse of Sedrach (unknown date; very late)"],
                "apocalypse-of-sedrach",
                "[IV. Wisdom & Oracles] The Apocalypse of Sedrach",
                "apocalypse-of-sedrach",
            ),
        ]:
            if b_opt:
                books.append(b_opt)
        books.extend(_build_pcom_books_for_div("IV"))

    # Load `lost_books_of_the_bible.jsonl` records keyed by `book` (used in Divisions V, VI, VII)
    lbob_by_book: dict[str, list[dict]] = defaultdict(list)
    if active_divs & {"V", "VI", "VII"}:
        with open(apocrypha_dir / "lost_books_of_the_bible.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    lbob_by_book[r.get("book", "Unknown")].append(r)

    def _build_lbob_book(
        raw_names: list[str],
        book_slug: str,
        display_title: str,
        dossier_key: str,
    ) -> Book | None:
        chs: list[Chapter] = []
        idx = 0
        for rname in raw_names:
            for rec in lbob_by_book.get(rname, []):
                idx += 1
                ctitle = clean_prose_text(rec.get("chapter_title") or rname)
                paras = [clean_prose_text(p) for p in rec.get("paragraphs", []) if clean_prose_text(p)]
                if paras and paras[0].lower() == ctitle.lower():
                    paras = paras[1:]
                blocks = [ContentBlock(block_type=BlockType.PARAGRAPH, text=p) for p in paras]
                chs.append(Chapter(id=f"{book_slug}-ch-{idx:02d}", title=ctitle, blocks=blocks))
        if not chs:
            return None
        bk_obj = Book(
            id=book_slug,
            title=display_title,
            full_title=display_title,
            author="Archbishop William Wake & Jeremiah Jones (tr.)",
            chapters=chs,
        )
        _attach_dossier_to_book(bk_obj, dossier_key)
        return _consolidate_book_into_single_chapter_if_needed(bk_obj, max_chapters=2)

    # ==========================================================================
    # DIVISION V: NEW TESTAMENT APOCRYPHAL GOSPELS & INFANCY NARRATIVES
    # (Note: Post-1929 copyrighted Nag Hammadi translations of Gospel of Thomas
    #  and Gospel of Mary are excluded so this volume remains 100% Public Domain.)
    # ==========================================================================
    if "V" in active_divs:
        for b_opt in [
            _build_lbob_book(
                ["The Lost Gospel According to Peter"],
                "the-lost-gospel-according-to-peter",
                "[V. Apocryphal Gospels] The Lost Gospel According to Peter (Akhmim Fragment)",
                "the-lost-gospel-according-to-peter",
            ),
            _build_lbob_book(
                ["The Protevangelion"],
                "the-protevangelion",
                "[V. Apocryphal Gospels] The Protevangelion of James",
                "the-protevangelion",
            ),
            _build_anf_work(
                ["Gospel of Pseudo-Matthew (c. 400)"],
                "gospel-of-pseudo-matthew",
                "[V. Apocryphal Gospels] The Gospel of Pseudo-Matthew",
                "gospel-of-pseudo-matthew",
            ),
            _build_lbob_book(
                ["The Gospel of the Birth of Mary"],
                "the-gospel-of-the-birth-of-mary",
                "[V. Apocryphal Gospels] The Gospel of the Birth of Mary",
                "the-gospel-of- the-birth-of-mary",
            ),
            _build_anf_work(
                ["History of Joseph the Carpenter (c. 400)"],
                "history-of-joseph-the-carpenter",
                "[V. Apocryphal Gospels] The History of Joseph the Carpenter",
                "history-of-joseph-the-carpenter",
            ),
            _build_lbob_book(
                ["The First Gospel of the Infancy of Jesus Christ"],
                "the-first-gospel-of-the-infancy-of-jesus-christ",
                "[V. Apocryphal Gospels] The First Gospel of the Infancy of Jesus Christ (Arabic Infancy Gospel)",
                "the-first-gospel-of-the-infancy-of-jesus-christ",
            ),
            _build_lbob_book(
                ["Thomas's Gospel of the Infancy of Jesus Christ"],
                "thomass-gospel-of-the-infancy-of-jesus-christ",
                "[V. Apocryphal Gospels] Thomas’s Gospel of the Infancy of Jesus Christ",
                "thomass-gospel-of-the-infancy-of-jesus-christ",
            ),
            _build_lbob_book(
                ["The Gospel of Nicodemus, Formerly Called the Acts of Pontius Pilate"],
                "the-gospel-of-nicodemus-formerly-called-the-acts-of-pontius-pilate",
                "[V. Apocryphal Gospels] The Gospel of Nicodemus (Acts of Pontius Pilate & Descent into Hades)",
                "the-gospel-of-nicodemus-formerly-called-the-acts-of-pontius-pilate",
            ),
            _build_anf_work(
                [
                    "Report of Pontius Pilate (unknown date; late)",
                    "Giving Up of Pontius Pilate (unknown date; late)",
                    "Letter of Pontius Pilate (unknown date; late)",
                    "Death of Pilate (unknown date; late)",
                    "Narrative of Joseph of Arimathea (unknown date; late)",
                    "Avenging of the Saviour (c. 700)",
                ],
                "pilate-passion-cycle",
                "[V. Apocryphal Gospels] The Pontius Pilate & Joseph of Arimathea Cycle",
                "pilate-passion-cycle",
            ),
            _build_anf_work(
                ["Assumption of Mary (c. 400)"],
                "assumption-of-mary",
                "[V. Apocryphal Gospels] The Assumption (Dormition) of Mary",
                "assumption-of-mary",
            ),
        ]:
            if b_opt:
                books.append(b_opt)
        books.extend(_build_pcom_books_for_div("V"))

    # ==========================================================================
    # DIVISION VI: APOCRYPHAL ACTS, EPISTLES & CHRISTIAN APOCALYPSES
    # ==========================================================================
    if "VI" in active_divs:
        for b_opt in [
            _build_lbob_book(
                ["The Epistles of Jesus Christ and Abgarus King of Edessa"],
                "the-epistles-of-jesus-christ-and-abgarus-king-of-edessa",
                "[VI. Acts & Apocalypses] The Epistles of Jesus Christ and Abgarus King of Edessa",
                "the-epistles-of-jesus-christ-and-abgarus-king-of-edessa",
            ),
            _build_anf_work(
                ["The Doctrine of Addai (c. 400)"],
                "the-doctrine-of-addai",
                "[VI. Acts & Apocalypses] The Doctrine of Addai the Apostle",
                "the-epistles-of-jesus-christ-and-abgarus-king-of-edessa",
            ),
            _build_lbob_book(
                ["The Acts of Paul and Thecla"],
                "the-acts-of-paul-and-thecla",
                "[VI. Acts & Apocalypses] The Acts of Paul and Thecla",
                "the-acts-of-paul-and-thecla",
            ),
            _build_anf_work(
                [
                    "Acts of Peter and Paul (c. 200)",
                    "Acts of John",
                    "Acts of Andrew (c. 260)",
                    "Acts of Thomas (c. 240)",
                    "Acts of Philip (c. 350)",
                    "Acts and Martyrdom of St. Matthew the Apostle (c. 550)",
                    "Acts of Bartholomew (c. 500)",
                    "Acts of Barnabas (c. 500)",
                    "Acts of Thaddaeus (c. 250)",
                    "Acts of Xanthippe and Polyxena (c. 270)",
                ],
                "apocryphal-acts-of-the-apostles",
                "[VI. Acts & Apocalypses] The Apocryphal Acts of the Apostles (Peter, John, Andrew, Thomas, Philip, Matthew, Bartholomew, Barnabas & Thaddaeus)",
                "apocryphal-acts-of-the-apostles",
            ),
            _build_lbob_book(
                [
                    "The Epistle of Paul the Apostle to the Laodiceans",
                    "The Epistles of Paul the Apostle to Seneca, with Seneca's to Paul",
                    "Letters of Herod and Pilate",
                ],
                "pauline-apocrypha",
                "[VI. Acts & Apocalypses] The Apocryphal Epistles (Paul to the Laodiceans, Paul & Seneca, Herod & Pilate)",
                "pauline-apocrypha",
            ),
            _build_anf_work(
                [
                    "The Apocalypse of Peter",
                    "Apocalypse of Paul (c. 380)",
                    "Apocalypse of John (unknown date; late)",
                    "Apocalypse of the Virgin (unknown date; very late)",
                ],
                "christian-apocalypses",
                "[VI. Acts & Apocalypses] The Early Christian Apocalypses (Peter, Paul, John & the Virgin)",
                "christian-apocalypses",
            ),
        ]:
            if b_opt:
                books.append(b_opt)
        books.extend(_build_pcom_books_for_div("VI"))

    # ==========================================================================
    # DIVISION VII: THE APOSTOLIC FATHERS & EARLY CHURCH ORDERS
    # ==========================================================================
    if "VII" in active_divs:
        b_didache = ingest_ista_jsonl_book(
            apocrypha_dir / "the_didache.jsonl",
            "the-didache",
            "[VII. Apostolic Fathers] The Didache (The Teaching of the Twelve Apostles)",
            "The Didache, or Teaching of the Twelve Apostles",
            "Charles H. Hoole (tr., 1894)",
        )
        _attach_dossier_to_book(b_didache, "the-didache")
        books.append(b_didache)

        for b_opt in [
            _build_lbob_book(
                ["The First Epistle of Clement to the Corinthians"],
                "1-clement",
                "[VII. Apostolic Fathers] The First Epistle of Clement to the Corinthians (c. AD 96)",
                "1-clement",
            ),
            _build_lbob_book(
                ["The Second Epistle of Clement to the Corinthians"],
                "2-clement",
                "[VII. Apostolic Fathers] The Second Epistle of Clement to the Corinthians",
                "2-clement",
            ),
            _build_lbob_book(
                ["The General Epistle of Barnabas"],
                "epistle-of-barnabas",
                "[VII. Apostolic Fathers] The General Epistle of Barnabas",
                "epistle-of-barnabas",
            ),
            _build_lbob_book(
                [
                    "The Epistle of Ignatius to the Ephesians",
                    "The Epistle of Ignatius to the Magnesians",
                    "The Epistle of Ignatius to the Trallians",
                    "The Epistle of Ignatius to the Romans",
                    "The Epistle of Ignatius to the Philadelphians",
                    "The Epistle of Ignatius to the Smyrn\ufffdans",
                    "The Epistle of Ignatius to the Smyrnaeans",
                    "The Epistle of Ignatius to Polycarp",
                ],
                "epistles-of-ignatius",
                "[VII. Apostolic Fathers] The Seven Epistles of Ignatius of Antioch",
                "epistles-of-ignatius",
            ),
            _build_lbob_book(
                ["The Epistle of Polycarp to the Philippians"],
                "epistle-of-polycarp",
                "[VII. Apostolic Fathers] The Epistle of Polycarp to the Philippians",
                "epistle-of-polycarp",
            ),
            _build_lbob_book(
                [
                    "The Shepherd of Hermas",
                    "The Second Book of Hermas, Called His Commands",
                    "The Third Book of Hermas, Which Is Called His Similitudes",
                ],
                "shepherd-of-hermas",
                "[VII. Apostolic Fathers] The Shepherd of Hermas (Book I: Visions, Book II: Commands, Book III: Similitudes)",
                "shepherd-of-hermas",
            ),
        ]:
            if b_opt:
                books.append(b_opt)
        books.extend(_build_pcom_books_for_div("VII"))

    return books


def ingest_complete_apocrypha_and_pseudepigrapha_compendium(
    extra_canon_dir: Path = Path("data/raw/kjv-apocrypha"),
    apocrypha_dir: Path = Path("data/raw/apocrypha-ista"),
    gutenberg_dir: Path = Path("data/raw/apocrypha-gutenberg"),
    pseudepigrapha_com_path: Path = Path("data/raw/apocrypha-pseudepigrapha-com/pseudepigrapha_com.jsonl"),
) -> Work:
    """Build the Complete Apocrypha & Pseudepigrapha Mega-Compendium uniting all non-canonical
    biblical, Second Temple, Enochic, Ethiopian Orthodox, Dead Sea Scrolls, Nag Hammadi,
    New Testament Apocrypha, and Apostolic Fathers texts across `extra-canon/`, `apocrypha/`,
    `gutenberg-apocrypha/`, and `pseudepigrapha-com/` with zero duplication and a scholarly
    Source, Provenance & Veracity dossier for every work.
    """
    books = _collect_compendium_books(
        extra_canon_dir=extra_canon_dir,
        apocrypha_dir=apocrypha_dir,
        gutenberg_dir=gutenberg_dir,
        pseudepigrapha_com_path=pseudepigrapha_com_path,
    )

    intro = Chapter(
        id="apocrypha-compendium-guide",
        title="Editorial Guide to Provenance, Public-Domain Licensing & Historical Veracity",
        is_front_matter=True,
        blocks=[
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=(
                    f"This Master Compendium unites {len(books)} distinct extra-canonical works across seven "
                    "historical divisions: (I) The 15 Old Testament Deuterocanonical books of the 1611 King James "
                    "Version; (II) Major Old Testament Pseudepigrapha, Enochic literature, Jubilees, Jasher, "
                    "Pseudo-Philo, the Adam and Eve cycle, the Testament of Abraham, the Narrative of Zosimus, "
                    "the Assumption of Moses, the Martyrdom of Isaiah, and 2–4 Baruch; "
                    "(III) The Testaments of the Twelve Patriarchs; (IV) Second Temple Wisdom, the Psalms and Odes "
                    "of Solomon, Aristeas, 4 Maccabees, Ahikar, the Sibylline Oracles, and the Qumran/Cairo Damascus "
                    "Zadokite Document; (V) New Testament Apocryphal Gospels (including the Gospel of Peter, "
                    "Protevangelion of James, Infancy Gospels, and Gospel of Nicodemus); (VI) The Apocryphal Acts "
                    "of the Apostles, the Epistle of the Apostles, the Questions of Bartholomew, and Early Christian "
                    "Apocalypses; and (VII) The Apostolic Fathers (The Didache, 1–2 Clement, Barnabas, Ignatius, "
                    "Polycarp, and The Shepherd of Hermas)."
                ),
            ),
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=(
                    "Strict Deduplication & Scholarly Provenance Dossiers: Every duplicate file across the upstream "
                    "archives has been eliminated so each text appears once (with both landmark translations of 1 Enoch—R. H. Charles "
                    "and Archbishop Richard Laurence—explicitly distinguished). Because ancient extra-canonical texts vary widely "
                    "from authentic 1st-century BC/AD documents and Dead Sea Scrolls witnesses to late-antique romances and "
                    "medieval Midrash, every single work in this volume opens with a dedicated 'Source, Provenance & Historical "
                    "Veracity Dossier' detailing its date of composition, original language, manuscript tradition, translator, "
                    "and critical historical evaluation."
                ),
            ),
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=(
                    "Public-Domain & Non-Commercial Attribution Notice: Every translation included in this compendium is "
                    "drawn from verified pre-1929 public-domain editions—principally the 1611 King James Version Apocrypha, "
                    "R. H. Charles's Oxford editions (1896–1917), M. R. James's Biblical Antiquities of Philo (1917) and "
                    "Apocryphal New Testament (1924), Archbishop Richard Laurence (1821/1883), Mordecai M. Noah (1840), "
                    "the Ante-Nicene Fathers Vol. VIII (1886), Milton S. Terry (1899), Charles H. Hoole (1894), Archbishop "
                    "William Wake (1693), William Hone (1820), and Rutherford H. Platt Jr. (1926)—together with Prof. Robert A. "
                    "Kraft's 1987 CATSS Public Domain / Free Non-Commercial edition of 4 Baruch (Paraleipomena Jeremiou, "
                    "Center for Computer Analysis of Texts, University of Pennsylvania). Digital transcriptions of R. H. Charles's "
                    "1913 editions prepared by the Internet Sacred Text Archive (John Bruno Hare) and the Wesley Center for Applied "
                    "Theology at Northwest Nazarene University are gratefully acknowledged for personal and non-commercial scholarly study."
                ),
            ),
        ],
    )

    return Work(
        id="complete-apocrypha-pseudepigrapha-compendium",
        title="The Complete Apocrypha & Pseudepigrapha Compendium",
        subtitle="Deuterocanon, Enochic Literature, Second Temple Pseudepigrapha, New Testament Apocrypha & Apostolic Fathers — With Historical Veracity Dossiers",
        authors=[
            "R. H. Charles (tr.)",
            "M. R. James (tr.)",
            "Richard Laurence (tr.)",
            "Archbishop William Wake (tr.)",
            "King James Version Translators (1611)",
        ],
        edition_label="Proteus Critical Provenance & Veracity Master Compendium",
        description=(
            "Complete deduplicated public-domain library of Biblical Apocrypha, Old Testament Pseudepigrapha, Dead Sea Scrolls parallels, "
            "New Testament Apocrypha, and the Apostolic Fathers, featuring a scholarly Source, Provenance & Historical "
            "Veracity dossier for every work."
        ),
        subjects=[
            "Apocryphal books",
            "Pseudepigrapha",
            "Apostolic Fathers",
            "Dead Sea Scrolls -- Parallels",
        ],
        front_matter=[intro],
        books=books,
        css_theme="classic.css",
    )


def ingest_pseudepigrapha(
    extra_canon_dir: Path = Path("data/raw/kjv-apocrypha"),
    apocrypha_dir: Path = Path("data/raw/apocrypha-ista"),
    gutenberg_dir: Path = Path("data/raw/apocrypha-gutenberg"),
    pseudepigrapha_com_path: Path = Path("data/raw/apocrypha-pseudepigrapha-com/pseudepigrapha_com.jsonl"),
) -> Work:
    """Build the standalone Old Testament Pseudepigrapha edition uniting Enochic & Patriarchal
    literature (1 Enoch Charles & Laurence, 2 Enoch, Jubilees, Jasher), Major OT Pseudepigrapha,
    the Testaments of the Twelve Patriarchs, and Second Temple Wisdom, Odes, Apocalypses & Qumran
    parallels—with deduplicated public-domain translations and Provenance & Veracity dossiers.
    """
    books = _collect_compendium_books(
        extra_canon_dir=extra_canon_dir,
        apocrypha_dir=apocrypha_dir,
        gutenberg_dir=gutenberg_dir,
        pseudepigrapha_com_path=pseudepigrapha_com_path,
        divisions={"II", "III", "IV"},
    )
    # Renumber division prefixes for standalone Pseudepigrapha (II->I, III->II, IV->III)
    for bk in books:
        if bk.title.startswith("[II. "):
            bk.title = "[I. " + bk.title[5:]
        elif bk.title.startswith("[III. "):
            bk.title = "[II. " + bk.title[6:]
        elif bk.title.startswith("[IV. "):
            bk.title = "[III. " + bk.title[5:]

    intro = Chapter(
        id="pseudepigrapha-editorial-guide",
        title="Editorial Guide to Provenance, Public-Domain Licensing & Historical Veracity",
        is_front_matter=True,
        blocks=[
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=(
                    f"This standalone Pseudepigrapha edition unites {len(books)} deduplicated extra-canonical "
                    "Old Testament and Second Temple works across three divisions: "
                    "(I) Major Old Testament Pseudepigrapha & Rewritten Bible (including both landmark translations "
                    "of 1 Enoch—R. H. Charles and Richard Laurence—2 Enoch, the Book of Jubilees, the Book of Jasher, "
                    "Pseudo-Philo's Biblical Antiquities, the Adam and Eve cycle, Apocalypse of Moses, Testament of Abraham, "
                    "Narrative of Zosimus, Book of Noah, Assumption of Moses, Martyrdom of Isaiah, and 2–4 Baruch); "
                    "(II) The Testaments of the Twelve Patriarchs; and "
                    "(III) Second Temple Wisdom, Odes, Apocalypses & Qumran Parallels (the Psalms and Odes of Solomon, "
                    "Letter of Aristeas, 4 Maccabees, Story of Ahikar, Sibylline Oracles, Greek Apocalypse of Esdras, "
                    "Apocalypse of Sedrach, and the Cairo Damascus Zadokite Document)."
                ),
            ),
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=(
                    "Scholarly Provenance & Historical Veracity Dossiers: Because Second Temple and late-antique "
                    "pseudepigraphal texts span authentic pre-Christian Jewish works, Dead Sea Scrolls witnesses, "
                    "Christianized redactions, and medieval Midrash, every book opens with a dedicated 'Source, "
                    "Provenance & Historical Veracity Dossier' detailing its date of composition, original language, "
                    "manuscript tradition, translator, and critical historical evaluation."
                ),
            ),
            ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=(
                    "Public-Domain & Non-Commercial Attribution Notice: Every translation in this volume is drawn "
                    "from verified pre-1929 public-domain editions—principally R. H. Charles's Oxford editions "
                    "(1896–1917), M. R. James's Biblical Antiquities of Philo (1917), Archbishop Richard Laurence "
                    "(1821/1883), Mordecai M. Noah (1840), the Ante-Nicene Fathers Vol. VIII (1886), Milton S. Terry "
                    "(1899), and Rutherford H. Platt Jr. (1926)—together with Prof. Robert A. Kraft's 1987 CATSS "
                    "Public Domain / Free Non-Commercial edition of 4 Baruch (Paraleipomena Jeremiou, University of "
                    "Pennsylvania)."
                ),
            ),
        ],
    )

    return Work(
        id="pseudepigrapha",
        title="The Complete Pseudepigrapha",
        subtitle="Enochic Literature, Jubilees, Jasher, Patriarchal Testaments & Second Temple Texts — With Historical Veracity Dossiers",
        authors=[
            "R. H. Charles (tr.)",
            "M. R. James (tr.)",
            "Richard Laurence (tr.)",
            "Mordecai Manuel Noah (tr.)",
        ],
        edition_label="Proteus Critical Provenance & Veracity Standalone Edition",
        description=(
            "Complete standalone public-domain library of Old Testament Pseudepigrapha, Enochic & Patriarchal "
            "literature (1 & 2 Enoch, Jubilees, Jasher, Testaments of the Twelve Patriarchs), Second Temple wisdom "
            "and apocalypses, and Dead Sea Scrolls parallels—each with a scholarly Provenance & Veracity dossier."
        ),
        subjects=[
            "Pseudepigrapha",
            "Old Testament Pseudepigrapha",
            "Apocryphal books (Old Testament)",
            "Dead Sea Scrolls -- Parallels",
        ],
        front_matter=[intro],
        books=books,
        css_theme="classic.css",
    )

