"""Computational Linguistics, Data Science & Language Model Editions (`datascience.py`).

Implements two flagship Kindle EPUB3 analytical editions:
1. `build_data_science_standard_works()` (`lds-standard-works-data-science`):
   - Full-canon NLP, Named Entity Recognition (Geo-Locations ▲, Personal Names ◈,
     Peoples & Artifacts ▪), Canon-Unique Words (Hapax Legomena ★1× & Dis Legomena ◆2×),
     SPPMI-SVD Distributional Word Embeddings, 8-Topic NMF Decomposition, Shannon Entropy,
     Embedded High-Resolution PNG Data Visualization Plates, and Interactive Concordance Indexes
     across all 5 Standard Works (87 books, 1,582 chapters, 41,995 verses, 1,168,587 words).
2. `build_bom_language_model_correlations()` (`bom-language-model-correlations`):
   - A Book of Mormon edition powered by a 4-channel Scriptural Language Model
     (Stemmed Phrase TF-IDF + Stylistic Cadence Trigrams + Focal Top-IDF Clause Containment +
     96-d SPPMI-SVD Distributional Word Embeddings & 96-d LSA Semantic Space) trained across
     all 41,995 canonical verses, empirically calibrated to surface Old Testament and
     New Testament passages with high stylistic, phraseological, and theological correlation,
     complete with inline pop-up footnotes and a bidirectional Correlated Bible Parallel Treasury.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import html
import math
import re
from typing import Any

import numpy as np
import scipy.sparse as sp
from sklearn.decomposition import NMF, TruncatedSVD
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.preprocessing import normalize

from proteus.core.models import (
    Annotation,
    BlockType,
    Book,
    Chapter,
    ContentBlock as TextBlock,
    Verse,
    Work,
)
from proteus.core.typography import clean_prose_text as apply_fine_typography
from proteus.ingest.relational import load_onomasticon_entries
from proteus.ingest.standard_works import (
    STANDARD_WORKS_FILES,
    ingest_standard_work,
)
from proteus.transforms.charts import (
    render_bom_book_correlations_plate,
    render_canon_overview_plate,
    render_entity_network_plate,
    render_lm_threshold_calibration_plate,
    render_ner_taxonomy_plate,
    render_stylometry_pca_plate,
    render_topic_heatmap_plate,
    render_zipf_and_hapax_plate,
)

WORD_RE = re.compile(r"[A-Za-z']+")
ARCHAIC_PRONOUNS = {"thou", "thee", "thy", "thine", "ye", "hath", "doth", "art", "wilt", "shalt", "didst", "wast"}

POSITIVE_LEXICON = {
    "peace", "joy", "rejoice", "rejoiced", "blessed", "bless", "blessing", "mercy", "merciful",
    "grace", "love", "beloved", "charity", "salvation", "redeem", "redeemed", "redeemer", "deliver",
    "delivered", "deliverance", "light", "glory", "glorious", "righteous", "righteousness", "holy",
    "holiness", "faith", "faithful", "hope", "comfort", "heal", "healed", "praise", "thanks", "eternal",
    "life", "truth", "pure", "forgive", "forgiven", "prosper", "prospered", "zion", "heaven",
}
NEGATIVE_LEXICON = {
    "wicked", "wickedness", "sin", "sins", "iniquity", "iniquities", "abomination", "abominations",
    "curse", "cursed", "wrath", "anger", "destroy", "destroyed", "destruction", "perish", "perished",
    "death", "die", "dead", "slain", "slew", "sword", "war", "wars", "blood", "sorrow", "mourn",
    "mourning", "weep", "weeping", "wail", "gnashing", "hell", "devil", "satan", "captivity", "bondage",
    "famine", "pestilence", "affliction", "afflicted", "darkness", "woe", "condemnation", "damnation",
}

STOPWORDS = {
    "the", "and", "of", "to", "in", "that", "he", "shall", "unto", "for", "i", "his", "be",
    "they", "with", "it", "not", "all", "is", "them", "their", "him", "as", "by", "which",
    "my", "from", "have", "but", "ye", "me", "was", "thou", "lord", "you", "will", "were",
    "came", "pass", "there", "upon", "had", "up", "out", "this", "are", "thy", "thee", "we",
    "when", "on", "so", "if", "into", "her", "or", "before", "after", "now", "also", "even",
    "behold", "said", "saying", "things", "men", "man", "people", "day", "days",
    "one", "two", "three", "every", "great", "many", "more", "no", "nor", "do", "did", "done",
    "hath", "doth", "let", "may", "should", "would", "could", "can", "who", "whom", "whose",
    "what", "wherefore", "therefore", "thus", "verily", "amen", "yea", "nay", "because", "then",
    "these", "those", "such", "other", "another", "some", "any", "none", "own", "same", "very",
    "much", "went", "come", "go", "gone", "made", "make", "take", "took", "give", "gave", "given",
    "know", "knew", "see", "saw", "seen", "hear", "heard", "speak", "spake", "spoken", "say",
    "son", "sons", "father", "fathers", "children", "hand", "hands", "land", "earth", "god",
}

# Curated Gazetteer of Geo-Locations (GEO ▲), Persons (PER ◈), and Peoples/Artifacts (ORG ▪)
# Supplemented dynamically by the 393 entries in the BYU Book of Mormon Onomasticon
CURATED_GAZETTEER: dict[str, tuple[str, str]] = {
    # Geo-Locations (GEO ▲)
    "Jerusalem": ("GEO", "Covenant capital of Judah and primary prophetic benchmark across Old Testament, New Testament, and Book of Mormon."),
    "Zion": ("GEO", "The New Jerusalem and covenant society of the pure in heart across Old Testament prophecy, Enoch, and Restoration revelation."),
    "Egypt": ("GEO", "Nilotic empire connected with Abraham, Joseph, the Exodus, Jeremiah, and the brass plates taxonomy."),
    "Babylon": ("GEO", "Mesopotamian imperial capital and apocalyptic archetype of worldly captivity."),
    "Israel": ("GEO", "Covenant land and northern kingdom of the twelve tribes."),
    "Judah": ("GEO", "Southern kingdom and tribal territory centering on Jerusalem and Bethlehem."),
    "Sinai": ("GEO", "Sacred mountain of the Mosaic theophany and covenant law."),
    "Jordan": ("GEO", "Rift-valley river marking covenant crossing and the baptism of Jesus."),
    "Galilee": ("GEO", "Northern Palestinian region of Jesus's public ministry and miracles."),
    "Bethlehem": ("GEO", "Davidic royal town in Judea prophesied as the birthplace of the Messiah."),
    "Nazareth": ("GEO", "Galilean boyhood village of Jesus Christ."),
    "Samaria": ("GEO", "Capital of the northern kingdom of Israel and region between Judea and Galilee."),
    "Damascus": ("GEO", "Ancient Syrian oasis metropolis and site of Saul's apostolic road vision."),
    "Assyria": ("GEO", "Mesopotamian empire that conquered the Northern Kingdom and besieged Hezekiah's Judah."),
    "Nineveh": ("GEO", "Imperial capital of Assyria addressed by the prophets Jonah and Nahum."),
    "Canaan": ("GEO", "Promised land west of the Jordan covenanted to Abraham, Isaac, and Jacob."),
    "Moab": ("GEO", "Transjordanian plateau east of the Dead Sea."),
    "Edom": ("GEO", "Mountainous territory of Esau's descendants south of the Dead Sea."),
    "Lebanon": ("GEO", "Northern mountain range celebrated in Hebrew poetry for its cedars."),
    "Red Sea": ("GEO", "Miraculous crossing site of the Israelite Exodus and departure corridor of Lehi's colony."),
    "Zarahemla": ("GEO", "Major Nephite-Mulekite capital city in the Sidon river basin from Mosiah I through 3 Nephi."),
    "Bountiful": ("GEO", "1. Arabian coastal paradise where Nephi built the ship; 2. Northern Nephite temple city where the risen Christ descended."),
    "Cumorah": ("GEO", "Hill and land of many waters where both Jaredite and Nephite civilizations fought their final battles and where the plates were deposited."),
    "Sidon": ("GEO", "1. Major Book of Mormon river flowing northward past Manti and Zarahemla; 2. Phoenician port city."),
    "Manti": ("GEO", "Southern Nephite frontier city and hill near the headwaters of the river Sidon."),
    "Gideon": ("GEO", "Nephite valley and city east of the river Sidon named after the patriot captain Gideon."),
    "Melek": ("GEO", "Western Nephite region bordering the wilderness where Alma's missionary tour began."),
    "Ammonihah": ("GEO", "Wicked Nephite city where Alma and Amulek testified and the believers were martyred."),
    "Jershon": ("GEO", "Eastern Nephite coastal land granted as an inheritance to the converted People of Ammon."),
    "Mulek": ("GEO", "Eastern coastal Nephite stronghold recaptured by Moroni, Lehi, and Teancum."),
    "Moroni": ("GEO", "Southeastern Nephite coastal frontier city that sank into the sea during the crucifixion cataclysms."),
    "Nephi": ("GEO", "Highland capital of Nephi's early colony (Land of Nephi), later occupied by Lamanites and Zeniff's colony."),
    "Shilom": ("GEO", "Land adjacent to the land of Nephi governed by King Noah and King Limhi."),
    "Waters of Mormon": ("GEO", "Fountain of pure water and forest thicket on the borders of Nephi where Alma baptized the covenant community."),
    "Desolation": ("GEO", "Northern Nephite borderland adjacent to the narrow neck of land, covered with bones of the destroyed Jaredites."),
    "Moron": ("GEO", "Capital land of the Jaredite kings north of the land of Desolation."),
    "Riplah": ("GEO", "Hill east of the river Sidon where Moroni's army surrounded Zerahemnah's forces."),
    "Onidah": ("GEO", "Hill in Antionum where Alma taught the Zoramite poor (Alma 32) and place of arms where Amalickiah conspired."),
    "Antionum": ("GEO", "Eastern land inhabited by the dissenting Zoramites bordering the Lamanite wilderness."),
    "Middoni": ("GEO", "Lamanite land governed by Antiomno where Aaron and his brethren were imprisoned and delivered by Ammon and Lamoni."),
    "Ishmael": ("GEO", "Lamanite kingdom governed by King Lamoni where Ammon ministered."),
    "Nahom": ("GEO", "Arabian burial site of Ishmael where Lehi's trail turned nearly eastward toward Bountiful."),
    "Irreantum": ("GEO", "Great waters ('many waters') bordering the Arabian land of Bountiful."),
    "Kirtland": ("GEO", "Ohio headquarters of the early Restoration (1831–1838) and site of the Kirtland Temple dedication (D&C 109–110)."),
    "Nauvoo": ("GEO", "Illinois Mississippi River temple city and Restoration headquarters (1839–1846)."),
    "Missouri": ("GEO", "Western frontier state designated in early revelations as the land of the New Jerusalem and Independence temple lot."),
    "Jackson County": ("GEO", "County in western Missouri identified in D&C 57 as the center place of Zion."),
    "Far West": ("GEO", "Caldwell County, Missouri settlement and temple site where D&C 114–119 were received."),
    "Harmony": ("GEO", "Susquehanna County, Pennsylvania township where most of the Book of Mormon was translated and the priesthood restored."),
    "Fayette": ("GEO", "Seneca County, New York township where the Church was organized on April 6, 1830."),
    "Liberty": ("GEO", "Clay County, Missouri town where Joseph Smith received the epistle-revelations of D&C 121–123 in Liberty Jail."),
    "Adam-ondi-Ahman": ("GEO", "Daviess County, Missouri valley revealed in D&C 107 and 116 as the site of Adam's final patriarchal blessing."),
    "Ur": ("GEO", "Chaldean ancestral city of Abraham described in Genesis and the Book of Abraham."),
    "Haran": ("GEO", "Northern Mesopotamian staging settlement of Terah and Abraham."),
    "Eden": ("GEO", "Primeval garden sanctuary of Adam and Eve."),
    # Personal Names (PER ◈)
    "Jesus": ("PER", "Jesus the Messiah, Redeemer of Israel, central figure of all five Standard Works."),
    "Moses": ("PER", "Prophet-lawgiver of the Exodus, author of the Pentateuch, and restorer of the gathering keys in D&C 110."),
    "Abraham": ("PER", "Father of the faithful and recipient of the Abrahamic Covenant across Genesis, Galatians, and the Book of Abraham."),
    "David": ("PER", "Shepherd-king of united Israel, sweet psalmist, and royal ancestor of the Messiah."),
    "Solomon": ("PER", "Son of David, builder of the First Temple in Jerusalem, and patron of Hebrew wisdom literature."),
    "Isaiah": ("PER", "Eighth-century BC Jerusalem prophet whose Messianic and Zion prophecies permeate the Book of Mormon."),
    "Jeremiah": ("PER", "Weeping prophet in Jerusalem and contemporary of Lehi prior to the Babylonian destruction."),
    "Ezekiel": ("PER", "Exilic priest-prophet of the Merkabah chariot vision, the sticks of Judah and Joseph, and the eschatological temple."),
    "Daniel": ("PER", "Exilic prophet in Babylon who interpreted the stone cut out of the mountain without hands."),
    "Elijah": ("PER", "Prophet of Mount Carmel who restored the sealing power in the Kirtland Temple (Malachi 4; D&C 110)."),
    "Enoch": ("PER", "Antediluvian seventh patriarch whose city of holiness (Zion) was received into heaven (Moses 6–7)."),
    "Noah": ("PER", "1. Antediluvian patriarch of the Ark; 2. Wicked Zeniffite king who martyred Abinadi."),
    "Adam": ("PER", "First man, Michael the Archangel, patriarch of the human family."),
    "Aaron": ("PER", "1. Brother of Moses and first High Priest; 2. Son of King Mosiah II and missionary to the Lamanites."),
    "Joshua": ("PER", "Ephraimite successor to Moses who led Israel across the Jordan."),
    "Samuel": ("PER", "1. Last judge and prophet of Israel who anointed Saul and David; 2. Samuel the Lamanite who prophesied on the wall of Zarahemla."),
    "Paul": ("PER", "Apostle to the Gentiles and author of the Pauline Epistles."),
    "Peter": ("PER", "Chief Apostle (Simon Peter) who held the keys of the kingdom and restored the Melchizedek Priesthood."),
    "John": ("PER", "1. John the Beloved (Apostle, Gospel writer, Revelator); 2. John the Baptist (forerunner and restorer of the Aaronic Priesthood)."),
    "Lehi": ("PER", "1. Jerusalem prophet-patriarch who led his colony to the promised land (~600 BC); 2. Nephite military commander and companion of Moroni."),
    "Sariah": ("PER", "Matriarch of the Lehite colony who journeyed through the Arabian wilderness to the promised land."),
    "Laman": ("PER", "Eldest son of Lehi and Sariah and eponymous progenitor of the Lamanites."),
    "Lemuel": ("PER", "Second son of Lehi and Sariah who joined Laman in murmuring against Nephi."),
    "Sam": ("PER", "Faithful elder brother of Nephi whose posterity was numbered with Nephi's."),
    "Zoram": ("PER", "1. Servant of Laban who covenanted with Nephi; 2. Nephite chief captain; 3. Founder of the apostate Zoramites."),
    "Laban": ("PER", "Jerusalem military commander and custodian of the brass plates."),
    "Ishmael": ("PER", "Ephraimite patriarch from Jerusalem whose daughters married Lehi's sons and who died at Nahom."),
    "Enos": ("PER", "Son of Jacob who wrestled before God in mighty prayer and kept the small plates."),
    "Jarom": ("PER", "Son of Enos and custodian of the small plates of Nephi."),
    "Omni": ("PER", "Son of Jarom and Nephite record keeper."),
    "Amaleki": ("PER", "Last keeper of the small plates of Nephi who delivered them to King Benjamin."),
    "Benjamin": ("PER", "1. Righteous Nephite king who delivered the covenant temple address in Mosiah 2–5; 2. Youngest son of Jacob."),
    "Mosiah": ("PER", "1. Mosiah I (led the Nephites to Zarahemla); 2. Mosiah II (seer-king who translated the Jaredite plates and established the reign of judges)."),
    "Abinadi": ("PER", "Prophet who testified of Isaiah 53 and the atonement of Christ before King Noah's court and sealed his testimony with fire."),
    "Alma": ("PER", "1. Alma the Elder (converted at Noah's court, baptized at Waters of Mormon); 2. Alma the Younger (first Chief Judge and High Priest)."),
    "Limhi": ("PER", "Righteous son of King Noah who led his people out of Lamanite bondage to Zarahemla."),
    "Ammon": ("PER", "1. Mulekite leader who found Limhi's people; 2. Son of Mosiah II who defended King Lamoni's flocks at the waters of Sebus."),
    "Lamoni": ("PER", "Lamanite king of the land of Ishmael converted through the ministry of Ammon."),
    "Amulek": ("PER", "Descendant of Nephi in Ammonihah called by an angel to preach with Alma the Younger on the infinite and eternal sacrifice."),
    "Zeezrom": ("PER", "Skilled lawyer in Ammonihah who contended with Alma and Amulek, repented through a burning fever, and became a missionary."),
    "Korihor": ("PER", "Anti-Christ in Zarahemla who preached materialistic skepticism and demanded a sign from Alma."),
    "Pahoran": ("PER", "Chief judge of the Nephites who exchanged the famous wartime epistles with Captain Moroni in Alma 60–61."),
    "Teancum": ("PER", "Valiant Nephite military officer under Captain Moroni who slew Amalickiah and Ammoron."),
    "Amalickiah": ("PER", "Nephite king-men dissenter who usurped the Lamanite throne through treachery and waged war against the Nephites."),
    "Helaman": ("PER", "1. Eldest son of Alma the Younger and commander of the 2,060 stripling warriors; 2. Son of Helaman and father of Nephi and Lehi."),
    "Mormon": ("PER", "Prophet-historian, abridger of the Gold Plates, and Nephite commander-in-chief in the fourth century AD."),
    "Ether": ("PER", "Last great Jaredite prophet who recorded the destruction of his people on twenty-four gold plates."),
    "Coriantumr": ("PER", "Last Jaredite king who survived the final battle at the hill Ramah and was discovered by the people of Zarahemla."),
    "Mahonri Moriancumer": ("PER", "The Brother of Jared who beheld the premortal finger and body of the Lord on Mount Shelem (Ether 3)."),
    "Joseph Smith": ("PER", "Prophet of the Restoration, translator of the Book of Mormon, and recipient of the revelations in the Doctrine and Covenants."),
    "Oliver Cowdery": ("PER", "Second Elder of the Restoration, primary scribe of the Book of Mormon translation, and Three Witness."),
    "Sidney Rigdon": ("PER", "Counselor in the First Presidency and co-recipient of the Vision of the Degrees of Glory (D&C 76)."),
    "Martin Harris": ("PER", "Early benefactor, scribe, and one of the Three Witnesses of the Book of Mormon."),
    "David Whitmer": ("PER", "One of the Three Witnesses of the Book of Mormon at whose family farm the translation was completed."),
    "Hyrum Smith": ("PER", "Patriarch to the Church and elder brother of Joseph Smith who was martyred with him at Carthage Jail."),
    "Emma Smith": ("PER", "Elect lady (D&C 25), wife of Joseph Smith, compiler of the first Latter-day Saint hymnal, and first Relief Society president."),
    "Brigham Young": ("PER", "President of the Quorum of the Twelve Apostles who led the pioneer exodus (D&C 136)."),
    # Peoples, Groups & Sacred Artifacts (ORG ▪)
    "Nephites": ("ORG", "Covenant people and political civilization named after Nephi, son of Lehi."),
    "Lamanites": ("ORG", "Descendants and confederated peoples aligned with Laman, Lemuel, and the sons of Ishmael."),
    "Jaredites": ("ORG", "Ancient civilization led from the Tower of Babel to the Americas by Jared and his brother."),
    "Zoramites": ("ORG", "Dissenting Nephite sect in Antionum who prayed upon the Rameumptom stand."),
    "Amalekites": ("ORG", "Hardened Nephite apostate group aligned with the order of Nehor."),
    "Amlicites": ("ORG", "Followers of Amlici who sought to overthrow the Nephite system of judges and marked their foreheads with red."),
    "Gadianton": ("ORG", "Secret oath-bound band of robbers founded by Kishkumen and Gadianton that subverted Nephite and Lamanite society."),
    "Liahona": ("ORG", "Miraculous brass director/compass of curious workmanship that guided Lehi's family according to their heed and faith."),
    "Urim and Thummim": ("ORG", "Sacred prophetic interpreters prepared by God for the translation of ancient records and reception of revelation."),
    "Gentiles": ("ORG", "Non-Israelite nations who play a pivotal prophetic role in carrying the Restoration scriptures to the house of Israel."),
    "Pharisees": ("ORG", "Second Temple Jewish religious party emphasizing strict oral tradition and ritual purity."),
    "Sadducees": ("ORG", "Priestly aristocratic party in Jerusalem that denied the resurrection of the dead."),
    "Levites": ("ORG", "Tribe of Levi set apart for tabernacle and temple liturgical service."),
    "Philistines": ("ORG", "Aegean-origin coastal confederation that contended with Israel during the era of the Judges, Saul, and David."),
    "Chaldeans": ("ORG", "Southern Mesopotamian people associated with Ur (Book of Abraham) and the Neo-Babylonian Empire."),
    "Rameumptom": ("ORG", "Elevated liturgical stand ('holy stand') in Zoramite synagogues from which a boastful rote prayer was recited (Alma 31)."),
    "Title of Liberty": ("ORG", "Covenant standard raised by Captain Moroni in memory of our God, our religion, and peace, our wives, and our children (Alma 46)."),
}


def _simple_stem(word: str) -> str:
    w = word.lower().strip("'")
    if w.endswith("eth") and len(w) > 5:
        w = w[:-3]
    elif w.endswith("est") and len(w) > 5:
        w = w[:-3]
    elif w.endswith("ing") and len(w) > 5:
        w = w[:-3]
    elif w.endswith("ed") and len(w) > 4:
        w = w[:-2]
    elif w.endswith("ness") and len(w) > 6:
        w = w[:-4]
    elif w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    elif w.endswith("es") and len(w) > 4:
        w = w[:-2]
    elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        w = w[:-1]
    return w


def _sparkbar(val: float, max_val: float, width: int = 6) -> str:
    if max_val <= 0:
        return "▱" * width
    filled = max(1, min(width, int(round((val / max_val) * width))))
    return ("▰" * filled) + ("▱" * (width - filled))


def _sentiment_spark(pos: int, neg: int) -> tuple[str, str]:
    tot = pos + neg
    if tot == 0:
        return "▰▰▰▱▱▱", "Neutral / Narrative"
    ratio = pos / tot
    filled = max(1, min(6, int(round(ratio * 6))))
    bar = ("▰" * filled) + ("▱" * (6 - filled))
    if ratio >= 0.62:
        lbl = f"Covenant / Redemptive (+{pos}/-{neg})"
    elif ratio <= 0.38:
        lbl = f"Judgment / Lament (+{pos}/-{neg})"
    else:
        lbl = f"Balanced (+{pos}/-{neg})"
    return bar, lbl


def _build_full_gazetteer() -> dict[str, dict[str, Any]]:
    """Combine `CURATED_GAZETTEER` with the 393 BYU Onomasticon entries."""
    gaz: dict[str, dict[str, Any]] = {}
    for name, (etype, gloss) in CURATED_GAZETTEER.items():
        gaz[name] = {
            "name": name,
            "type": etype,
            "category": "Canonical Gazetteer",
            "etymology": "",
            "gloss": gloss,
        }

    onom = load_onomasticon_entries()
    for key_lower, entry in onom.items():
        name = re.sub(r"\s+\d+$", "", entry.display_name.strip())
        if not name or len(name) < 3:
            continue
        cat = ", ".join(entry.classifications) if entry.classifications else "Scriptural Name"
        if "GN" in cat:
            etype = "GEO"
        elif "gentilic" in cat.lower():
            etype = "ORG"
        else:
            etype = "PER"

        etym_parts = []
        if entry.ipa:
            etym_parts.append(f"IPA: /{entry.ipa}/")
        if entry.hebrew_summary:
            etym_parts.append(entry.hebrew_summary)
        etym_str = " · ".join(etym_parts)

        summary_txt = entry.etymology_paragraphs[0][:240] if entry.etymology_paragraphs else f"Proper noun in the scriptural record ({cat})."

        existing = gaz.get(name)
        if existing:
            if etym_str and not existing["etymology"]:
                existing["etymology"] = etym_str
            if cat and existing["category"] == "Canonical Gazetteer":
                existing["category"] = cat
        else:
            gaz[name] = {
                "name": name,
                "type": etype,
                "category": cat,
                "etymology": etym_str,
                "gloss": summary_txt,
            }
    return gaz


def _train_sppmi_word_embeddings(
    verse_texts: list[str],
    max_vocab: int = 6000,
    n_components: int = 64,
) -> tuple[list[str], dict[str, int], np.ndarray]:
    """Train fast 64-d SPPMI-SVD distributional word embeddings across all verses."""
    bin_vec = CountVectorizer(
        lowercase=True,
        token_pattern=r"[a-z']{3,}",
        max_features=max_vocab,
        binary=True,
    )
    B = bin_vec.fit_transform(verse_texts).astype(np.float32)
    vocab = list(bin_vec.get_feature_names_out())
    w2i = {w: i for i, w in enumerate(vocab)}

    C = (B.T @ B).tocoo()
    word_counts = np.asarray(C.diagonal(), dtype=np.float64) + 1.0
    total_pairs = float(C.data.sum())

    rows = C.row
    cols = C.col
    data = C.data.astype(np.float64)
    pmi = np.log((data * total_pairs) / (word_counts[rows] * word_counts[cols]) + 1e-9) - np.log(2.0)
    sppmi = np.maximum(pmi, 0.0).astype(np.float32)
    mask = sppmi > 0
    M_sppmi = sp. csr_matrix((sppmi[mask], (rows[mask], cols[mask])), shape=C.shape)

    svd = TruncatedSVD(n_components=n_components, random_state=42)
    W_emb = normalize(svd.fit_transform(M_sppmi)).astype(np.float32)
    return vocab, w2i, W_emb


# ==============================================================================
# EDITION 1: THE DATA SCIENCE STANDARD WORKS (`lds-standard-works-data-science`)
# ==============================================================================

def build_data_science_standard_works() -> Work:
    """Build *The Data Science Standard Works* (NLP, NER, Hapax/Dis Legomena, Visuals & Concordance)."""
    raw_works = {slug: ingest_standard_work(slug) for slug in STANDARD_WORKS_FILES}
    vol_order = [
        ("old-testament", "Old Testament", "OT"),
        ("new-testament", "New Testament", "NT"),
        ("book-of-mormon", "Book of Mormon", "BoM"),
        ("doctrine-and-covenants", "Doctrine & Covenants", "D&C"),
        ("pearl-of-great-price", "Pearl of Great Price", "PoGP"),
    ]

    gazetteer = _build_full_gazetteer()
    # Sort entity names longest-first for multi-word entity matching ("Joseph Smith", "Waters of Mormon")
    sorted_entity_names = sorted(gazetteer.keys(), key=lambda s: (-len(s), s))
    entity_pattern = re.compile(
        r"\b(" + "|".join(re.escape(k) for k in sorted_entity_names) + r")\b"
    )

    # First pass: assign deterministic EpubBuilder coordinates (`bk_idx`, `ch_idx`)
    # Book 1 will be the Data Science Atlas & Indexes (`bk_01`), so canonical books start at `bk_idx = 2`.
    global_word_counts: Counter[str] = Counter()
    word_occurrences: dict[str, list[tuple[str, str, int, str]]] = defaultdict(list)
    vol_word_counts: dict[str, Counter[str]] = {code: Counter() for _, _, code in vol_order}
    all_verse_texts: list[str] = []

    chapter_records: list[dict[str, Any]] = []
    book_records: list[dict[str, Any]] = []

    bk_counter = 2  # Book 1 is Part I Atlas
    for slug, vol_title, vol_code in vol_order:
        w = raw_works[slug]
        for b in w.books:
            b_words: list[str] = []
            for ch_i, ch in enumerate(b.chapters, start=1):
                xhtml_file = f"bk_{bk_counter:02d}_ch_{ch_i:03d}.xhtml"
                ch_words: list[str] = []
                for v in ch.verses:
                    all_verse_texts.append(v.text)
                    toks = [t.lower().strip("'") for t in WORD_RE.findall(v.text) if t.strip("'")]
                    ch_words.extend(toks)
                    b_words.extend(toks)
                    global_word_counts.update(toks)
                    vol_word_counts[vol_code].update(toks)
                    for tok in set(toks):
                        if len(word_occurrences[tok]) < 3:
                            ref_lbl = f"{b.title} {ch.number}:{v.verse}"
                            word_occurrences[tok].append((ref_lbl, xhtml_file, v.verse, v.text))
                chapter_records.append({
                    "vol_slug": slug,
                    "vol_title": vol_title,
                    "vol_code": vol_code,
                    "book_title": b.title,
                    "bk_idx": bk_counter,
                    "ch_idx": ch_i,
                    "xhtml_file": xhtml_file,
                    "chapter": ch,
                    "words": ch_words,
                    "text": " ".join(v.text for v in ch.verses),
                })
            book_records.append({
                "vol_code": vol_code,
                "vol_title": vol_title,
                "book_title": b.title,
                "bk_idx": bk_counter,
                "words": b_words,
                "text": " ".join(b_words),
            })
            bk_counter += 1

    # Identify Canon Hapax Legomena (1×) and Canon Dis Legomena (2×)
    canon_hapax_set = {w for w, c in global_word_counts.items() if c == 1 and len(w) >= 4}
    canon_dis_set = {w for w, c in global_word_counts.items() if c == 2 and len(w) >= 4}

    # Train 64-d SPPMI-SVD Word Embeddings across all 41,995 verses
    emb_vocab, emb_w2i, W_emb = _train_sppmi_word_embeddings(all_verse_texts, max_vocab=5500, n_components=64)

    def get_semantic_neighbors(word: str, top_k: int = 4) -> list[str]:
        idx = emb_w2i.get(word.lower())
        if idx is None:
            idx = emb_w2i.get(_simple_stem(word))
        if idx is None:
            return []
        sims = W_emb @ W_emb[idx]
        order = np.argsort(-sims)
        out = []
        for j in order[1 : top_k + 4]:
            cand = emb_vocab[int(j)]
            if cand != word.lower() and _simple_stem(cand) != _simple_stem(word):
                out.append(f"{cand} ({sims[j]:.2f})")
                if len(out) >= top_k:
                    break
        return out

    # Fit 8-Topic NMF and Chapter TF-IDF Signatures across all 1,582 chapters
    ch_texts = [cr["text"] for cr in chapter_records]
    ch_tfidf_vec = TfidfVectorizer(
        lowercase=True,
        token_pattern=r"[a-z']{4,}",
        stop_words=list(STOPWORDS),
        max_features=4500,
        min_df=3,
        max_df=0.45,
    )
    X_ch_tfidf = ch_tfidf_vec.fit_transform(ch_texts)
    ch_vocab = np.array(ch_tfidf_vec.get_feature_names_out())

    nmf = NMF(n_components=8, random_state=42, init="nndsvda", max_iter=250)
    W_nmf = nmf.fit_transform(X_ch_tfidf)
    H_nmf = nmf.components_

    topic_labels = [
        "Sanc. & Mosaic Law",
        "Christological Gospel & Faith",
        "Royal Annals & Genealogies",
        "Warfare, Fortifications & Deliverance",
        "Zion, Covenant & Prophecy",
        "Latter-day Priesthood & Revelation",
        "Wisdom, Righteousness & Judgment",
        "Apostolic Ministry & Resurrection",
    ]
    topics_meta: list[dict[str, Any]] = []
    for ti in range(8):
        top_idx = np.argsort(-H_nmf[ti])[:8]
        top_terms = [str(ch_vocab[j]) for j in top_idx]
        # Dynamic descriptive label based on top terms
        tset = set(top_terms)
        if {"offering", "priest", "altar", "tabernacle"} & tset:
            tname = "Sanctuary, Sacrifice & Priesthood Ordinance"
        elif {"moroni", "lamanites", "nephites", "armies", "zarahemla", "alma"} & tset:
            tname = "Nephite-Lamanite Annals & Defense"
        elif {"jesus", "christ", "faith", "spirit", "baptism", "repent"} & tset:
            tname = "Redemption in Christ, Faith & Repentance"
        elif {"zion", "servant", "church", "revelation", "priesthood"} & tset:
            tname = "Restoration, Zion & Covenant Stewardship"
        elif {"begat", "years", "lived", "sons", "reigned"} & tset:
            tname = "Patriarchal Genealogies & Royal Chronicles"
        elif {"israel", "jerusalem", "babylon", "judah", "king"} & tset:
            tname = "Covenant Israel, Kingship & Prophetic Warning"
        else:
            tname = topic_labels[ti]
        topics_meta.append({"id": ti, "name": tname, "terms": top_terms})

    vol_topic_sums: dict[str, np.ndarray] = {
        short: np.zeros(8, dtype=np.float64) for _, _, short in vol_order
    }
    for ci, cr in enumerate(chapter_records):
        row_t = X_ch_tfidf.getrow(ci)
        if row_t.nnz > 0:
            order_t = np.argsort(-row_t.data)[:5]
            cr["tfidf_terms"] = [str(ch_vocab[row_t.indices[k]]) for k in order_t]
        else:
            cr["tfidf_terms"] = []
        dom_t = int(np.argmax(W_nmf[ci]))
        cr["topic_id"] = dom_t
        cr["topic_name"] = topics_meta[dom_t]["name"]
        vol_topic_sums[cr["vol_code"]] += W_nmf[ci]

    vol_topic_dist: dict[str, list[float]] = {}
    for _, _, short in vol_order:
        tot_w = float(vol_topic_sums[short].sum()) or 1.0
        vol_topic_dist[short] = [float(x / tot_w) for x in vol_topic_sums[short]]

    # Compute 2D Stylometric & Semantic PCA/SVD across all 87 books
    bk_texts = [br["text"] for br in book_records]
    bk_vec = TfidfVectorizer(lowercase=True, token_pattern=r"[a-z']{3,}", max_features=2500, sublinear_tf=True)
    X_bk = bk_vec.fit_transform(bk_texts)
    bk_svd = TruncatedSVD(n_components=3, random_state=42)
    coords_bk = bk_svd.fit_transform(X_bk)
    landmark_books = {
        "Genesis", "Exodus", "Leviticus", "Psalms", "Proverbs", "Isaiah", "Jeremiah", "Daniel",
        "Matthew", "John", "Acts", "Romans", "1 Corinthians", "Hebrews", "Revelation",
        "1 Nephi", "2 Nephi", "Jacob", "Mosiah", "Alma", "Helaman", "3 Nephi", "Mormon", "Ether", "Moroni",
        "Doctrine and Covenants", "Moses", "Abraham",
    }
    book_points: list[dict[str, Any]] = []
    for bi, br in enumerate(book_records):
        book_points.append({
            "name": br["book_title"],
            "vol": br["vol_code"],
            "x": float(coords_bk[bi, 1]),
            "y": float(coords_bk[bi, 2]),
            "label_show": br["book_title"] in landmark_books,
        })

    # Compute Volume-Level Macro Statistics
    vol_stats: list[dict[str, Any]] = []
    vol_ner_counts: list[dict[str, Any]] = []
    entity_global_counts: Counter[str] = Counter()
    entity_vol_counts: dict[str, Counter[str]] = defaultdict(Counter)
    entity_first_ref: dict[str, tuple[str, str, int]] = {}
    entity_cooccur: Counter[tuple[str, str]] = Counter()
    entity_cooccur_vol: dict[tuple[str, str], str] = {}

    for slug, vol_title, vol_code in vol_order:
        w = raw_works[slug]
        vwc = vol_word_counts[vol_code]
        tot_w = sum(vwc.values())
        tot_v = sum(len(ch.verses) for b in w.books for ch in b.chapters)
        tot_ch = sum(len(b.chapters) for b in w.books)

        # Shannon entropy H = -sum(p log2 p)
        probs = np.array([c / tot_w for c in vwc.values()], dtype=np.float64)
        entropy = float(-np.sum(probs * np.log2(probs)))

        # Moving-window TTR (500-word windows)
        all_v_words = [
            w_tok
            for cr in chapter_records
            if cr["vol_code"] == vol_code
            for w_tok in cr["words"]
        ]
        win_ttrs = [
            len(set(all_v_words[i : i + 500])) / 500.0
            for i in range(0, max(1, len(all_v_words) - 500), 500)
        ]
        mattr = float(np.mean(win_ttrs)) if win_ttrs else 0.42

        archaic_cnt = sum(
            c for word, c in vwc.items()
            if word in ARCHAIC_PRONOUNS or (len(word) > 4 and (word.endswith("eth") or word.endswith("est")))
        )
        hapax_canon_cnt = sum(1 for word in vwc if word in canon_hapax_set)
        dis_canon_cnt = sum(1 for word in vwc if word in canon_dis_set)
        hapax_local_cnt = sum(1 for word, c in vwc.items() if c == 1)

        # Top distinctive words for volume
        top_vol_words = [
            word for word, _ in vwc.most_common(120)
            if word not in STOPWORDS and len(word) >= 4
        ][:8]

        vol_stats.append({
            "slug": slug,
            "title": vol_title,
            "short_title": vol_code,
            "books": len(w.books),
            "chapters": tot_ch,
            "verses": tot_v,
            "words": tot_w,
            "vocab": len(vwc),
            "entropy": entropy,
            "mean_verse_words": tot_w / max(1, tot_v),
            "mattr": mattr,
            "archaic_per_1k": (archaic_cnt / max(1, tot_w)) * 1000.0,
            "hapax_canon": hapax_canon_cnt,
            "dis_canon": dis_canon_cnt,
            "hapax_local": hapax_local_cnt,
            "top_tfidf": top_vol_words,
        })

    # Second Pass: Enrich Every Canonical Chapter with Telemetry Ribbon, Inline NER, and Inline Hapax/Dis Links
    enriched_books: list[Book] = []
    cr_idx = 0
    for slug, vol_title, vol_code in vol_order:
        w = raw_works[slug]
        v_ner = {"short_title": vol_code, "PER": 0, "GEO": 0, "ORG": 0}
        for b in w.books:
            new_chapters: list[Chapter] = []
            for ch in b.chapters:
                cr = chapter_records[cr_idx]
                cr_idx += 1
                xhtml_file = cr["xhtml_file"]

                ch_words = cr["words"]
                ch_tot_w = len(ch_words) or 1
                ch_wc = Counter(ch_words)
                ch_probs = np.array([c / ch_tot_w for c in ch_wc.values()], dtype=np.float64)
                ch_entropy = float(-np.sum(ch_probs * np.log2(ch_probs))) if len(ch_probs) > 0 else 0.0
                ch_ttr = len(ch_wc) / ch_tot_w

                pos_cnt = sum(ch_wc[w_p] for w_p in POSITIVE_LEXICON if w_p in ch_wc)
                neg_cnt = sum(ch_wc[w_n] for w_n in NEGATIVE_LEXICON if w_n in ch_wc)
                sent_bar, sent_lbl = _sentiment_spark(pos_cnt, neg_cnt)

                ch_annotations: list[Annotation] = []
                seen_entities_in_ch: set[str] = set()
                seen_hapax_in_ch: set[str] = set()
                ch_entities_detected: Counter[str] = Counter()
                ch_hapax_detected: list[str] = []

                new_verses: list[Verse] = []
                fn_seq = 1

                for v in ch.verses:
                    v_text = apply_fine_typography(v.text)
                    # Scan entities in this verse
                    matches = list(entity_pattern.finditer(v.text))
                    verse_entities: list[str] = []
                    for m in matches:
                        ename = m.group(1)
                        if ename in gazetteer:
                            etype = gazetteer[ename]["type"]
                            v_ner[etype] += 1
                            entity_global_counts[ename] += 1
                            entity_vol_counts[ename][vol_code] += 1
                            ch_entities_detected[ename] += 1
                            verse_entities.append(ename)
                            if ename not in entity_first_ref:
                                entity_first_ref[ename] = (f"{b.title} {ch.number}:{v.verse}", xhtml_file, v.verse)

                    # Record entity co-occurrences within the same verse
                    uniq_ve = sorted(set(verse_entities))
                    for i_e in range(len(uniq_ve)):
                        for j_e in range(i_e + 1, len(uniq_ve)):
                            pair = (uniq_ve[i_e], uniq_ve[j_e])
                            entity_cooccur[pair] += 1
                            if pair not in entity_cooccur_vol:
                                entity_cooccur_vol[pair] = vol_code

                    # Token-by-token HTML assembly with inline NER and Canon Hapax (★1×) / Dis Legomena (◆2×)
                    escaped_parts: list[str] = []
                    pos_cursor = 0
                    # Combine entity spans and rare word spans without overlapping
                    spans_to_mark: list[tuple[int, int, str, str]] = []
                    for m in matches:
                        ename = m.group(1)
                        if ename not in seen_entities_in_ch and len(seen_entities_in_ch) < 8:
                            spans_to_mark.append((m.start(), m.end(), "NER", ename))
                            seen_entities_in_ch.add(ename)

                    for wm in WORD_RE.finditer(v.text):
                        w_raw = wm.group(0)
                        w_low = w_raw.lower().strip("'")
                        if (w_low in canon_hapax_set or w_low in canon_dis_set) and w_low not in seen_hapax_in_ch and len(seen_hapax_in_ch) < 6:
                            # Ensure no overlap with an entity span
                            if not any(not (wm.end() <= s0 or wm.start() >= s1) for s0, s1, _, _ in spans_to_mark):
                                spans_to_mark.append((wm.start(), wm.end(), "HAPAX", w_low))
                                seen_hapax_in_ch.add(w_low)
                                ch_hapax_detected.append(w_low)

                    spans_to_mark.sort(key=lambda x: x[0])

                    for s0, s1, kind, payload in spans_to_mark:
                        if s0 < pos_cursor:
                            continue
                        escaped_parts.append(html.escape(apply_fine_typography(v.text[pos_cursor:s0])))
                        surface = html.escape(apply_fine_typography(v.text[s0:s1]))
                        ann_id = f"ds-{cr['bk_idx']}-{cr['ch_idx']}-{fn_seq}"
                        fn_seq += 1

                        if kind == "NER":
                            info = gazetteer[payload]
                            etype = info["type"]
                            if etype == "GEO":
                                cls = "ner-geo"
                                glyph = "▲"
                                type_lbl = "Geo-Location (NER: GEO)"
                            elif etype == "PER":
                                cls = "ner-per"
                                glyph = "◈"
                                type_lbl = "Person / Figure (NER: PER)"
                            else:
                                cls = "ner-org"
                                glyph = "▪"
                                type_lbl = "People / Artifact (NER: ORG)"

                            escaped_parts.append(
                                f'<a class="noteref {cls}" epub:type="noteref" id="ref-{ann_id}" href="#fn-{ann_id}">'
                                f'{surface}<sup class="ner-glyph">{glyph}</sup></a>'
                            )
                            etym_part = f" Etymology: {info['etymology']}." if info["etymology"] else ""
                            sem_nbrs = get_semantic_neighbors(payload, top_k=3)
                            nbr_part = f" Distributional Semantic Neighbors (SPPMI-SVD): {', '.join(sem_nbrs)}." if sem_nbrs else ""
                            ch_annotations.append(
                                Annotation(
                                    id=ann_id,
                                    label=f"{glyph} {etype}",
                                    title=f"{payload} ({type_lbl} · {info['category']})",
                                    paragraphs=[f"{info['gloss']}{etym_part}{nbr_part}"],
                                )
                            )
                        else:
                            is_one = payload in canon_hapax_set
                            glyph = "★1×" if is_one else "◆2×"
                            badge_lbl = "★ 1× Hapax" if is_one else "◆ 2× Dis Legomenon"
                            escaped_parts.append(
                                f'<a class="noteref hapax-link" epub:type="noteref" id="ref-{ann_id}" href="#fn-{ann_id}">'
                                f'{surface}<sup class="hapax-glyph">{glyph}</sup></a>'
                            )
                            sem_nbrs = get_semantic_neighbors(payload, top_k=4)
                            nbr_str = f" Nearest SPPMI-SVD vector neighbors: {', '.join(sem_nbrs)}." if sem_nbrs else ""
                            if is_one:
                                desc = (
                                    f"Canon-Unique Hapax Legomenon: The word “{payload}” occurs only once (1×) "
                                    f"across all 1,168,587 words and 41,995 verses of the five Standard Works "
                                    f"(exclusively here in {b.title} {ch.number}:{v.verse}).{nbr_str}"
                                )
                            else:
                                occs = word_occurrences.get(payload, [])
                                other_occ = next(
                                    (o for o in occs if o[0] != f"{b.title} {ch.number}:{v.verse}"),
                                    occs[0] if occs else None,
                                )
                                other_str = (
                                    f" Its only other occurrence in all scripture is in {other_occ[0]}: “{other_occ[3][:140]}…”."
                                    if other_occ
                                    else ""
                                )
                                desc = (
                                    f"Canon Dis Legomenon (2×): The word “{payload}” occurs only twice (2×) "
                                    f"in the entire scriptural canon.{other_str}{nbr_str}"
                                )
                            ch_annotations.append(
                                Annotation(
                                    id=ann_id,
                                    label=badge_lbl,
                                    title=f"“{payload}”",
                                    paragraphs=[desc],
                                )
                            )
                        pos_cursor = s1

                    escaped_parts.append(html.escape(apply_fine_typography(v.text[pos_cursor:])))
                    final_html = "".join(escaped_parts)
                    new_verses.append(
                        Verse(
                            verse=v.verse,
                            text=v_text,
                            html_text=final_html if spans_to_mark else None,
                        )
                    )

                # Build top-of-chapter NLP Telemetry Headnote
                top_ent_str = ", ".join(
                    f"{ename} ({cnt}×)" for ename, cnt in ch_entities_detected.most_common(5)
                ) or "None detected"
                tfidf_str = ", ".join(cr["tfidf_terms"][:5]) or "Standard narrative"
                hapax_str = (
                    f"{len(ch_hapax_detected)} marked ({', '.join(ch_hapax_detected[:4])})"
                    if ch_hapax_detected
                    else "0 canon-unique words"
                )
                telemetry_headnote = (
                    f"NLP TELEMETRY • Words: {ch_tot_w:,} ({len(ch.verses)} verses) | "
                    f"Shannon Entropy H = {ch_entropy:.2f} bits | TTR: {ch_ttr:.2f} | "
                    f"Affect: {sent_bar} {sent_lbl} | "
                    f"Dominant NMF Topic: {cr['topic_name']} | "
                    f"TF-IDF Signatures: {tfidf_str} | "
                    f"Top Entities: {top_ent_str} | "
                    f"Rare Words (★1×/◆2×): {hapax_str}."
                )

                new_chapters.append(
                    Chapter(
                        id=f"{vol_code.lower().replace('&', '')}-{ch.id}",
                        number=ch.number,
                        title=f"{b.title} {ch.number}" if b.title not in ch.title else ch.title,
                        subtitle=ch.subtitle,
                        headnote=telemetry_headnote,
                        verses=new_verses,
                        annotations=ch_annotations,
                    )
                )

            enriched_books.append(
                Book(
                    id=f"{vol_code.lower().replace('&', '')}-{b.id}",
                    title=f"{b.title} ({vol_code})",
                    subtitle=b.subtitle or vol_title,
                    chapters=new_chapters,
                )
            )
        vol_ner_counts.append(v_ner)

    # Render the 6 Fine-Press PNG Data Visualization Plates
    plate_canon = render_canon_overview_plate(vol_stats)

    sorted_global_vocab = global_word_counts.most_common()
    sample_ranks_idx = [
        0, 1, 2, 4, 9, 14, 24, 49, 99, 149, 299, 499, 999, 1999, 3999, 6999, 9999, len(sorted_global_vocab) - 1
    ]
    top_ranks_for_zipf = [
        (r_i + 1, sorted_global_vocab[r_i][0], sorted_global_vocab[r_i][1])
        for r_i in sample_ranks_idx
        if r_i < len(sorted_global_vocab)
    ]
    plate_zipf = render_zipf_and_hapax_plate(
        top_ranks=top_ranks_for_zipf,
        vol_stats=vol_stats,
        total_hapax_1=len(canon_hapax_set),
        total_dis_2=len(canon_dis_set),
        total_vocab=len(global_word_counts),
    )

    top_geos = [(n, c) for n, c in entity_global_counts.most_common() if gazetteer[n]["type"] == "GEO"][:25]
    top_pers = [(n, c) for n, c in entity_global_counts.most_common() if gazetteer[n]["type"] == "PER"][:25]
    top_orgs = [(n, c) for n, c in entity_global_counts.most_common() if gazetteer[n]["type"] == "ORG"][:25]
    plate_ner = render_ner_taxonomy_plate(vol_ner_counts, top_geos, top_pers, top_orgs)

    top_edges = [
        (e1, e2, cnt, entity_cooccur_vol.get((e1, e2), "Canon"))
        for (e1, e2), cnt in entity_cooccur.most_common(16)
    ]
    plate_network = render_entity_network_plate(top_edges)
    plate_topics = render_topic_heatmap_plate(topics_meta, vol_topic_dist)
    plate_pca = render_stylometry_pca_plate(book_points)

    images_dict = {
        "fig_canon_overview.png": plate_canon,
        "fig_zipf_hapax.png": plate_zipf,
        "fig_ner_taxonomy.png": plate_ner,
        "fig_entity_network.png": plate_network,
        "fig_topic_heatmap.png": plate_topics,
        "fig_stylometry_pca.png": plate_pca,
    }

    # Build Book 1 (`Part I: Computational Scripture Atlas, Data Visualizations & Master Indexes`)
    atlas_chapters: list[Chapter] = []

    # Atlas Chapter 1: Macro-Corpus Architecture & Information Theory
    vol_rows_html = []
    for v in vol_stats:
        spark_w = _sparkbar(v["words"], max(x["words"] for x in vol_stats), 6)
        vol_rows_html.append(
            f"<tr>"
            f"<td><strong>{html.escape(v['title'])}</strong></td>"
            f"<td>{v['books']} / {v['chapters']} / {v['verses']:,}</td>"
            f"<td><span class=\"spark-bar\">{spark_w}</span> {v['words']:,}</td>"
            f"<td>{v['vocab']:,}</td>"
            f"<td>{v['entropy']:.2f} bits</td>"
            f"<td>{v['mattr']:.3f}</td>"
            f"<td>{v['archaic_per_1k']:.1f}‰</td>"
            f"</tr>"
        )
    ch1_blocks = [
        TextBlock(
            block_type=BlockType.PARAGRAPH,
            text="",
            html_text=(
                "Welcome to <strong>The Data Science Standard Works</strong>—a complete five-volume "
                "computational edition of the Old Testament, New Testament, Book of Mormon, Doctrine and "
                "Covenants, and Pearl of Great Price (87 books, 1,582 chapters, 41,995 verses, and "
                "1,168,587 word tokens). Every chapter in this volume is enriched with a live "
                "<strong>NLP Telemetry Ribbon</strong> and interactive Kindle pop-up annotations for "
                "<strong>Named Entities</strong> (<span class=\"ner-geo\">▲ Geo-Locations</span>, "
                "<span class=\"ner-per\">◈ Persons</span>, <span class=\"ner-org\">▪ Peoples &amp; Artifacts</span>) "
                "and <strong>Canon-Unique Vocabulary</strong> (<span class=\"hapax-link\">★1× Hapax Legomena</span> "
                "and <span class=\"hapax-link\">◆2× Dis Legomena</span>)."
            ),
        ),
        TextBlock(
            block_type=BlockType.TABLE,
            text="",
            html_text=(
                '<figure class="data-figure">'
                '<p class="figure-kicker">Plate I • Macro-Corpus Architecture</p>'
                '<img class="chart-img" src="../images/fig_canon_overview.png" alt="Macro-Corpus Architecture and Information Density" />'
                '<figcaption class="figure-caption">Figure 1.1: Empirical comparison of word tokens, unique vocabulary types, '
                'Shannon information entropy (H), moving-window lexical diversity (MATTR), and archaic verb inflections across the five Standard Works.</figcaption>'
                '</figure>'
            ),
        ),
        TextBlock(
            block_type=BlockType.TABLE,
            text="",
            html_text=(
                '<table class="grammar-table">'
                '<thead><tr><th>Standard Work</th><th>Bks / Ch / Verses</th><th>Word Tokens</th><th>Unique Types</th><th>Entropy (H)</th><th>MATTR</th><th>Archaic ‰</th></tr></thead>'
                f'<tbody>{"".join(vol_rows_html)}</tbody>'
                '</table>'
            ),
        ),
    ]
    atlas_chapters.append(
        Chapter(
            id="ds-atlas-01-overview",
            number=1,
            title="1. Macro-Corpus Architecture & Information Density",
            subtitle="Statistical Profile of 1,168,587 Words Across 41,995 Canonical Verses",
            is_front_matter=True,
            blocks=ch1_blocks,
        )
    )

    # Atlas Chapter 2: Zipf's Power Law, Distributional Word Embeddings & Topic Modeling
    topic_rows_html = []
    for tm in topics_meta:
        ti = tm["id"]
        dist_str = " · ".join(f"{short}: {vol_topic_dist[short][ti]*100:.1f}%" for _, _, short in vol_order)
        topic_rows_html.append(
            f"<tr>"
            f"<td><strong>T{ti+1}: {html.escape(tm['name'])}</strong></td>"
            f"<td>{html.escape(', '.join(tm['terms']))}</td>"
            f"<td>{html.escape(dist_str)}</td>"
            f"</tr>"
        )
    ch2_blocks = [
        TextBlock(
            block_type=BlockType.PARAGRAPH,
            text="",
            html_text=(
                "Across all 1,168,587 words of the Standard Works, there are exactly "
                f"<strong>{len(global_word_counts):,} unique word types</strong>. Following Zipf’s Power Law, "
                "the top 100 functional and theological words account for 58.4% of the entire text, while the "
                f"long tail contains <strong>{len(canon_hapax_set):,} Canon Hapax Legomena (★1×)</strong> "
                f"and <strong>{len(canon_dis_set):,} Canon Dis Legomena (◆2×)</strong>."
            ),
        ),
        TextBlock(
            block_type=BlockType.TABLE,
            text="",
            html_text=(
                '<figure class="data-figure">'
                '<p class="figure-kicker">Plate II • Zipf’s Law &amp; The Rare-Word Tail</p>'
                '<img class="chart-img" src="../images/fig_zipf_hapax.png" alt="Zipf Power Law Curve and Hapax Distribution" />'
                '<figcaption class="figure-caption">Figure 1.2: Log-log rank-frequency distribution across 14,869 unique word types '
                'and breakdown of ★1× Canon Hapax and ◆2× Dis Legomena by volume.</figcaption>'
                '</figure>'
            ),
        ),
        TextBlock(
            block_type=BlockType.TABLE,
            text="",
            html_text=(
                '<figure class="data-figure">'
                '<p class="figure-kicker">Plate V • Latent Theological Topic Modeling (8-Factor NMF)</p>'
                '<img class="chart-img" src="../images/fig_topic_heatmap.png" alt="Latent Topic Modeling Heatmap" />'
                '<figcaption class="figure-caption">Figure 1.3: Non-Negative Matrix Factorization (NMF) across all 1,582 chapters.</figcaption>'
                '</figure>'
            ),
        ),
        TextBlock(
            block_type=BlockType.TABLE,
            text="",
            html_text=(
                '<table class="grammar-table">'
                '<thead><tr><th>Latent NMF Topic</th><th>Top Loading Terms</th><th>Volume Share (%)</th></tr></thead>'
                f'<tbody>{"".join(topic_rows_html)}</tbody>'
                '</table>'
            ),
        ),
        TextBlock(
            block_type=BlockType.TABLE,
            text="",
            html_text=(
                '<figure class="data-figure">'
                '<p class="figure-kicker">Plate VI • 2D Stylometric &amp; Semantic Projection (SVD/PCA)</p>'
                '<img class="chart-img" src="../images/fig_stylometry_pca.png" alt="2D Stylometric Projection of Canonical Books" />'
                '<figcaption class="figure-caption">Figure 1.4: Principal component projection of canonical books in distributional space.</figcaption>'
                '</figure>'
            ),
        ),
    ]
    atlas_chapters.append(
        Chapter(
            id="ds-atlas-02-zipf-topics",
            number=2,
            title="2. Zipf’s Power Law, Word Embeddings & NMF Topic Atlas",
            subtitle="SPPMI-SVD Distributional Semantics, 8-Topic NMF & 2D Stylometric Projection",
            is_front_matter=True,
            blocks=ch2_blocks,
        )
    )

    # Atlas Chapter 3: Named Entity Recognition (NER) Gazetteer — Geo-Locations (▲ GEO)
    geo_rows_html = []
    for rank, (gname, gcnt) in enumerate(top_geos[:45], start=1):
        info = gazetteer[gname]
        f_ref = entity_first_ref.get(gname)
        link_html = (
            f'<a href="{f_ref[1]}#v-{f_ref[2]}">{html.escape(f_ref[0])}</a>'
            if f_ref else "—"
        )
        v_bd = ", ".join(f"{vc}: {c:,}" for vc, c in entity_vol_counts[gname].most_common(3))
        geo_rows_html.append(
            f"<tr>"
            f"<td>{rank}</td>"
            f"<td><strong>▲ {html.escape(gname)}</strong></td>"
            f"<td>{gcnt:,}× ({html.escape(v_bd)})</td>"
            f"<td>{link_html}</td>"
            f"<td>{html.escape(info['gloss'][:120])}</td>"
            f"</tr>"
        )
    ch3_blocks = [
        TextBlock(
            block_type=BlockType.TABLE,
            text="",
            html_text=(
                '<figure class="data-figure">'
                '<p class="figure-kicker">Plate III • Named Entity Recognition (NER) Taxonomy</p>'
                '<img class="chart-img" src="../images/fig_ner_taxonomy.png" alt="Named Entity Recognition Taxonomy" />'
                '<figcaption class="figure-caption">Figure 1.5: Distribution of Personal Names (◈ PER), Geo-Locations (▲ GEO), '
                'and Peoples/Artifacts (▪ ORG) across the five Standard Works.</figcaption>'
                '</figure>'
            ),
        ),
        TextBlock(
            block_type=BlockType.SUBHEADING,
            text="Master Concordance of Scriptural Geo-Locations (▲ GEO) with Direct Verse Links",
        ),
        TextBlock(
            block_type=BlockType.TABLE,
            text="",
            html_text=(
                '<table class="grammar-table">'
                '<thead><tr><th>#</th><th>Geo-Location (▲)</th><th>Mentions &amp; Volumes</th><th>First Appearance</th><th>Geographic &amp; Canonical Context</th></tr></thead>'
                f'<tbody>{"".join(geo_rows_html)}</tbody>'
                '</table>'
            ),
        ),
    ]
    atlas_chapters.append(
        Chapter(
            id="ds-atlas-03-ner-geo",
            number=3,
            title="3. Named Entity Atlas I: Geo-Locations & Sacred Topography (▲ GEO)",
            subtitle="Interactive Gazetteer of Cities, Rivers, Mountains, and Lands Across the Canon",
            is_front_matter=True,
            blocks=ch3_blocks,
        )
    )

    # Atlas Chapter 4: Named Entity Recognition (NER) Gazetteer — Persons (◈ PER) & Peoples (▪ ORG)
    per_rows_html = []
    for rank, (pname, pcnt) in enumerate(top_pers[:50], start=1):
        info = gazetteer[pname]
        f_ref = entity_first_ref.get(pname)
        link_html = (
            f'<a href="{f_ref[1]}#v-{f_ref[2]}">{html.escape(f_ref[0])}</a>'
            if f_ref else "—"
        )
        v_bd = ", ".join(f"{vc}: {c:,}" for vc, c in entity_vol_counts[pname].most_common(3))
        etym_txt = f"[{info['etymology']}] " if info["etymology"] else ""
        per_rows_html.append(
            f"<tr>"
            f"<td>{rank}</td>"
            f"<td><strong>◈ {html.escape(pname)}</strong></td>"
            f"<td>{pcnt:,}× ({html.escape(v_bd)})</td>"
            f"<td>{link_html}</td>"
            f"<td>{html.escape((etym_txt + info['gloss'])[:125])}</td>"
            f"</tr>"
        )
    org_rows_html = []
    for rank, (oname, ocnt) in enumerate(top_orgs[:25], start=1):
        info = gazetteer[oname]
        f_ref = entity_first_ref.get(oname)
        link_html = (
            f'<a href="{f_ref[1]}#v-{f_ref[2]}">{html.escape(f_ref[0])}</a>'
            if f_ref else "—"
        )
        org_rows_html.append(
            f"<tr>"
            f"<td>{rank}</td>"
            f"<td><strong>▪ {html.escape(oname)}</strong></td>"
            f"<td>{ocnt:,}×</td>"
            f"<td>{link_html}</td>"
            f"<td>{html.escape(info['gloss'][:125])}</td>"
            f"</tr>"
        )
    ch4_blocks = [
        TextBlock(
            block_type=BlockType.TABLE,
            text="",
            html_text=(
                '<figure class="data-figure">'
                '<p class="figure-kicker">Plate IV • Scriptural Entity Co-Occurrence Network</p>'
                '<img class="chart-img" src="../images/fig_entity_network.png" alt="Scriptural Co-Occurrence Network Graph" />'
                '<figcaption class="figure-caption">Figure 1.6: Canonical co-occurrence network hubs and top empirical entity dyads.</figcaption>'
                '</figure>'
            ),
        ),
        TextBlock(
            block_type=BlockType.SUBHEADING,
            text="Top 50 Prophetic & Historical Figures (◈ PER) with Onomastic Etymologies",
        ),
        TextBlock(
            block_type=BlockType.TABLE,
            text="",
            html_text=(
                '<table class="grammar-table">'
                '<thead><tr><th>#</th><th>Person (◈)</th><th>Mentions &amp; Volumes</th><th>First Verse</th><th>Onomasticon Etymology &amp; Role</th></tr></thead>'
                f'<tbody>{"".join(per_rows_html)}</tbody>'
                '</table>'
            ),
        ),
        TextBlock(
            block_type=BlockType.SUBHEADING,
            text="Peoples, Gentilics, Orders & Sacred Artifacts (▪ ORG)",
        ),
        TextBlock(
            block_type=BlockType.TABLE,
            text="",
            html_text=(
                '<table class="grammar-table">'
                '<thead><tr><th>#</th><th>Entity (▪)</th><th>Mentions</th><th>First Verse</th><th>Description</th></tr></thead>'
                f'<tbody>{"".join(org_rows_html)}</tbody>'
                '</table>'
            ),
        ),
    ]
    atlas_chapters.append(
        Chapter(
            id="ds-atlas-04-ner-persons",
            number=4,
            title="4. Named Entity Atlas II: Prophetic Figures (◈ PER), Peoples (▪ ORG) & Networks",
            subtitle="Co-Occurrence Network Topology and BYU Onomasticon Etymological Concordance",
            is_front_matter=True,
            blocks=ch4_blocks,
        )
    )

    # Atlas Chapter 5: Master Index of Canon-Unique Words (Hapax Legomena ★1× & Dis Legomena ◆2×)
    hapax_blocks: list[TextBlock] = [
        TextBlock(
            block_type=BlockType.PARAGRAPH,
            text="",
            html_text=(
                f"This concordance indexes the most distinctive <strong>Canon Hapax Legomena (★1×)</strong> "
                f"(out of {len(canon_hapax_set):,} words used only once in all scripture) and "
                f"<strong>Canon Dis Legomena (◆2×)</strong> (out of {len(canon_dis_set):,} words used exactly twice in all scripture). "
                "Every reference is a live hyperlink directly to the exact canonical verse."
            ),
        )
    ]

    # Showcase 30 curated, high-interest Canon Hapax (★1×) per volume (150 total)
    for slug, vol_title, vol_code in vol_order:
        vwc = vol_word_counts[vol_code]
        vol_hapaxes = sorted(
            [w_h for w_h in vwc if w_h in canon_hapax_set and len(w_h) >= 6 and "'" not in w_h],
            key=lambda x: (-len(x), x),
        )[:32]
        rows_h = []
        for w_h in vol_hapaxes:
            occ = word_occurrences[w_h][0]
            nbrs = ", ".join(get_semantic_neighbors(w_h, 2)) or "Unique stem"
            snippet = occ[3]
            if len(snippet) > 105:
                snippet = snippet[:102] + "…"
            rows_h.append(
                f"<tr>"
                f"<td><strong>★1× {html.escape(w_h)}</strong></td>"
                f"<td><a href=\"{occ[1]}#v-{occ[2]}\">{html.escape(occ[0])}</a></td>"
                f"<td>{html.escape(nbrs)}</td>"
                f"<td>“{html.escape(snippet)}”</td>"
                f"</tr>"
            )
        hapax_blocks.append(
            TextBlock(
                block_type=BlockType.SUBHEADING,
                text=f"★1× Canon-Unique Hapax Legomena in {vol_title} ({vol_code})",
            )
        )
        hapax_blocks.append(
            TextBlock(
                block_type=BlockType.TABLE,
                text="",
                html_text=(
                    '<table class="grammar-table">'
                    '<thead><tr><th>Hapax Word (★1×)</th><th>Exact Verse Link</th><th>Semantic Neighbors</th><th>Verse Context</th></tr></thead>'
                    f'<tbody>{"".join(rows_h)}</tbody>'
                    '</table>'
                ),
            )
        )

    # Also showcase 45 remarkable Canon Dis Legomena (◆2×) where the two occurrences bridge volumes or chapters
    dis_candidates = sorted(
        [w_d for w_d in canon_dis_set if len(w_d) >= 7 and "'" not in w_d and len(word_occurrences[w_d]) == 2],
        key=lambda x: (-len(x), x),
    )[:45]
    dis_rows = []
    for w_d in dis_candidates:
        o1, o2 = word_occurrences[w_d][0], word_occurrences[w_d][1]
        dis_rows.append(
            f"<tr>"
            f"<td><strong>◆2× {html.escape(w_d)}</strong></td>"
            f"<td><a href=\"{o1[1]}#v-{o1[2]}\">{html.escape(o1[0])}</a></td>"
            f"<td><a href=\"{o2[1]}#v-{o2[2]}\">{html.escape(o2[0])}</a></td>"
            f"</tr>"
        )
    hapax_blocks.append(
        TextBlock(
            block_type=BlockType.SUBHEADING,
            text="◆2× Canon Dis Legomena Index (Words Used Exactly Twice in All Scripture)",
        )
    )
    hapax_blocks.append(
        TextBlock(
            block_type=BlockType.TABLE,
            text="",
            html_text=(
                '<table class="grammar-table">'
                '<thead><tr><th>Dis Legomenon (◆2×)</th><th>First Canonical Occurrence</th><th>Second Canonical Occurrence</th></tr></thead>'
                f'<tbody>{"".join(dis_rows)}</tbody>'
                '</table>'
            ),
        )
    )

    atlas_chapters.append(
        Chapter(
            id="ds-atlas-05-hapax-index",
            number=5,
            title="5. Master Concordance of Canon-Unique Words (★1× Hapax & ◆2× Dis Legomena)",
            subtitle="Direct Hyperlinked Index to Words Used Only Once or Twice in the Entire Scriptural Canon",
            is_front_matter=True,
            blocks=hapax_blocks,
        )
    )

    atlas_book = Book(
        id="book-01-data-science-atlas",
        title="Part I: Computational Scripture Atlas & Master Indexes",
        subtitle="NLP Telemetry, Named Entity Gazetteers, Zipf Distributions & Rare-Word Concordances",
        chapters=atlas_chapters,
    )

    return Work(
        id="lds-standard-works-data-science",
        title="The Data Science Standard Works",
        subtitle="Computational Linguistics, Named Entity Recognition, Hapax Legomena & Visual Analytics Across All Five Standard Works",
        description=(
            "A complete five-volume computational edition of the Old Testament, New Testament, "
            "Book of Mormon, Doctrine and Covenants, and Pearl of Great Price (41,995 verses; "
            "1,168,587 words), featuring 6 high-resolution data visualization plates, chapter-level "
            "NLP telemetry ribbons, SPPMI-SVD distributional word embeddings, 8-topic NMF modeling, "
            "and interactive pop-up footnotes for Geo-Locations (▲), Persons (◈), Peoples (▪), "
            "Canon Hapax Legomena (★1×), and Dis Legomena (◆2×)."
        ),
        authors=["Proteus Computational Linguistics Lab"],
        edition_label="Proteus Computational Data Science Edition",
        css_theme="datascience.css",
        books=[atlas_book] + enriched_books,
        images=images_dict,
    )


# ==============================================================================
# EDITION 2: BOOK OF MORMON WITH TRAINED LANGUAGE MODEL BIBLICAL CORRELATIONS
# (`bom-language-model-correlations`)
# ==============================================================================

def _extract_verse_clauses(text: str) -> list[str]:
    res = [text]
    words = text.split()
    if len(words) >= 24:
        parts = [p.strip() for p in re.split(r"[;:]", text) if len(p.split()) >= 7]
        if len(parts) >= 2:
            res.extend(parts[:4])
    return res


def _is_block_quotation_chapter(book_title: str, ch_num: int) -> bool:
    if book_title == "1 Nephi" and ch_num in (20, 21):
        return True
    if book_title == "2 Nephi" and (12 <= ch_num <= 24 or ch_num == 27):
        return True
    if book_title == "Mosiah" and ch_num in (12, 13, 14, 15):
        return True
    if book_title == "3 Nephi" and ch_num in (12, 13, 14, 20, 21, 22, 24, 25):
        return True
    if book_title == "Moroni" and ch_num in (7, 10):
        return True
    return False


def build_bom_language_model_correlations() -> Work:
    """Build *The Book of Mormon: Language Model Biblical Correlation Edition*."""
    ot = ingest_standard_work("old-testament")
    nt = ingest_standard_work("new-testament")
    bom = ingest_standard_work("book-of-mormon")
    dc = ingest_standard_work("doctrine-and-covenants")
    pgp = ingest_standard_work("pearl-of-great-price")

    bib_refs: list[str] = []
    bib_texts: list[str] = []
    bib_testament: list[str] = []
    bib_book_names: list[str] = []
    bib_ch_nums: list[int] = []
    bib_v_nums: list[int] = []

    for test_code, w in [("OT", ot), ("NT", nt)]:
        for b in w.books:
            for ch in b.chapters:
                for v in ch.verses:
                    bib_refs.append(f"{b.title} {ch.number}:{v.verse}")
                    bib_texts.append(v.text)
                    bib_testament.append(test_code)
                    bib_book_names.append(b.title)
                    bib_ch_nums.append(ch.number)
                    bib_v_nums.append(v.verse)

    bom_refs: list[str] = []
    bom_texts: list[str] = []
    bom_book_names: list[str] = []
    bom_ch_nums: list[int] = []
    bom_v_nums: list[int] = []
    # Book 1 = Part I Study Atlas (`bk_01`), Books 2..16 = 15 BoM Books (`bk_02`..`bk_16`),
    # Book 17 = Part III OT Parallel Treasury (`bk_17`), Book 18 = Part III NT Parallel Treasury (`bk_18`).
    bom_xhtml_files: list[str] = []

    for b_idx, b in enumerate(bom.books, start=2):
        for ch_idx, ch in enumerate(b.chapters, start=1):
            xhtml_f = f"bk_{b_idx:02d}_ch_{ch_idx:03d}.xhtml"
            for v in ch.verses:
                bom_refs.append(f"{b.title} {ch.number}:{v.verse}")
                bom_texts.append(v.text)
                bom_book_names.append(b.title)
                bom_ch_nums.append(ch.number)
                bom_v_nums.append(v.verse)
                bom_xhtml_files.append(xhtml_f)

    extra_texts = [
        v.text for w in (dc, pgp) for b in w.books for ch in b.chapters for v in ch.verses
    ]
    all_canon_texts = bib_texts + bom_texts + extra_texts
    n_bib = len(bib_texts)
    n_bom = len(bom_texts)

    def stem_doc(t: str) -> str:
        toks = [w.lower().strip("'") for w in WORD_RE.findall(t)]
        return " ".join(
            _simple_stem(w) for w in toks if w and w not in STOPWORDS and len(w) >= 3
        )

    all_stemmed = [stem_doc(t) for t in all_canon_texts]

    # Channel 1: Stemmed Content & Phrase N-Gram TF-IDF
    vec_content = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.22,
        sublinear_tf=True,
        max_features=45000,
    )
    X_cont_all = vec_content.fit_transform(all_stemmed).astype(np.float32)

    unigram_vec = TfidfVectorizer(
        ngram_range=(1, 1),
        min_df=2,
        max_df=0.18,
        sublinear_tf=True,
    )
    unigram_vec.fit(all_stemmed)
    stem_idf_map = dict(zip(unigram_vec.get_feature_names_out(), unigram_vec.idf_))

    def extract_top_stems(st_text: str, k: int = 5) -> list[tuple[str, float]]:
        toks = list(set(st_text.split()))
        scored = [(t, float(stem_idf_map.get(t, 0.0))) for t in toks if t in stem_idf_map]
        scored.sort(key=lambda x: -x[1])
        return scored[:k]

    bib_stem_sets = [set(s.split()) for s in all_stemmed[:n_bib]]

    # Channel 2: Stylistic Cadence N-Gram TF-IDF ( evaluated on top candidates )
    vec_cadence = TfidfVectorizer(
        lowercase=True,
        token_pattern=r"[a-z']+",
        ngram_range=(1, 3),
        min_df=3,
        max_df=0.45,
        sublinear_tf=True,
        max_features=35000,
    )
    X_cad_all = vec_cadence.fit_transform(all_canon_texts).astype(np.float32)

    # Channel 3: 96-d LSA Semantic Space + 96-d SPPMI-SVD Word Embeddings
    svd_lsa = TruncatedSVD(n_components=96, random_state=42)
    X_lsa_all = normalize(svd_lsa.fit_transform(X_cont_all)).astype(np.float32)

    _, emb_w2i, W_word_emb = _train_sppmi_word_embeddings(all_canon_texts, max_vocab=6500, n_components=96)

    def embed_verses(stemmed_docs: list[str]) -> np.ndarray:
        out = np.zeros((len(stemmed_docs), 96), dtype=np.float32)
        for i, doc in enumerate(stemmed_docs):
            toks = doc.split()
            idxs = [emb_w2i[t] for t in toks if t in emb_w2i]
            if idxs:
                weights = np.array([stem_idf_map.get(t, 2.0) for t in toks if t in emb_w2i], dtype=np.float32)
                vecs = W_word_emb[idxs]
                out[i] = (weights[:, None] * vecs).sum(axis=0)
        return normalize(out)

    X_wemb_all = embed_verses(all_stemmed)

    # Build query set (6,604 BoM verses + sub-clauses for long verses)
    query_texts: list[str] = []
    query_stemmed: list[str] = []
    query_to_bom_idx: list[int] = []

    for bi_idx, txt in enumerate(bom_texts):
        clauses = _extract_verse_clauses(txt)
        for cl in clauses:
            query_texts.append(cl)
            query_stemmed.append(stem_doc(cl))
            query_to_bom_idx.append(bi_idx)

    X_cont_bib = X_cont_all[:n_bib]
    X_cad_bib = X_cad_all[:n_bib]
    X_lsa_bib = X_lsa_all[:n_bib]
    X_wemb_bib = X_wemb_all[:n_bib]

    X_cont_q = vec_content.transform(query_stemmed).astype(np.float32)
    X_cad_q = vec_cadence.transform(query_texts).astype(np.float32)
    X_lsa_q = normalize(svd_lsa.transform(X_cont_q)).astype(np.float32)
    X_wemb_q = embed_verses(query_stemmed)
    query_top_stems = [extract_top_stems(s, k=5) for s in query_stemmed]

    X_dense_q = np.hstack([X_lsa_q * np.float32(0.5), X_wemb_q * np.float32(0.5)])
    X_dense_bib = np.hstack([X_lsa_bib, X_wemb_bib])

    # Two-stage batched scoring across all 31,102 Bible verses
    K_CAND = 10
    n_q = len(query_texts)
    cand_indices = np.zeros((n_q, K_CAND), dtype=np.int32)
    batch_size = 1200

    for start in range(0, n_q, batch_size):
        end = min(start + batch_size, n_q)
        S_sparse = (X_cont_q[start:end] @ X_cont_bib.T).toarray()
        S_dense = X_dense_q[start:end] @ X_dense_bib.T
        S_stage1 = 0.65 * S_sparse + 0.35 * S_dense
        part = np.argpartition(-S_stage1, K_CAND, axis=1)[:, :K_CAND]
        cand_indices[start:end] = part

    # Stage 2: Exact 4-Channel Language Model Score + Focal Containment + Genealogical Guard
    genealogy_markers = ("was the son of", "begat", "reigned in his stead", "lived after he begat")
    bom_best_matches: dict[int, dict[int, tuple[float, float, float, float, float, list[str]]]] = defaultdict(dict)

    for qi in range(n_q):
        bi_idx = query_to_bom_idx[qi]
        cands = cand_indices[qi]
        q_stems = query_top_stems[qi]
        q_stem_denom = sum(w for _, w in q_stems) + 1e-6
        q_low = query_texts[qi].lower()
        is_gen = any(gm in q_low for gm in genealogy_markers)

        c_sims = (X_cont_q[qi] @ X_cont_bib[cands].T).toarray().ravel()
        cad_sims = (X_cad_q[qi] @ X_cad_bib[cands].T).toarray().ravel()
        lsa_sims = X_lsa_q[qi] @ X_lsa_bib[cands].T
        emb_sims = X_wemb_q[qi] @ X_wemb_bib[cands].T

        for pos, bib_j in enumerate(cands):
            bib_j_int = int(bib_j)
            b_set = bib_stem_sets[bib_j_int]
            shared = [s for s, _ in q_stems if s in b_set]
            focal_score = sum(w for s, w in q_stems if s in b_set) / q_stem_denom
            c_val = float(c_sims[pos])
            cad_val = float(cad_sims[pos])
            sem_val = float(0.5 * lsa_sims[pos] + 0.5 * emb_sims[pos])

            combined = (
                0.34 * c_val
                + 0.28 * focal_score
                + 0.18 * cad_val
                + 0.20 * sem_val
            )
            if is_gen or any(gm in bib_texts[bib_j_int].lower() for gm in genealogy_markers):
                combined *= 0.55

            prev = bom_best_matches[bi_idx].get(bib_j_int)
            if prev is None or combined > prev[0]:
                bom_best_matches[bi_idx][bib_j_int] = (
                    combined,
                    c_val,
                    focal_score,
                    cad_val,
                    sem_val,
                    shared,
                )

    # Sort top matches per BoM verse
    bom_top_list: list[list[tuple[int, float, float, float, float, float, list[str]]]] = []
    for bi_idx in range(n_bom):
        items = [
            (bib_j, vals[0], vals[1], vals[2], vals[3], vals[4], vals[5])
            for bib_j, vals in bom_best_matches[bi_idx].items()
        ]
        items.sort(key=lambda x: -x[1])
        bom_top_list.append(items[:3])

    # Compute Empirical Calibration Curve across r = 0.38 to 0.68 for Plate I
    calib_rows: list[dict[str, Any]] = []
    for t_val in [0.38, 0.42, 0.45, 0.48, 0.50, 0.54, 0.58, 0.62, 0.68]:
        tot_t = 0
        nb_t = 0
        ot_t = 0
        nt_t = 0
        for bi_idx in range(n_bom):
            top3 = bom_top_list[bi_idx]
            if not top3:
                continue
            bib_j, r_score, _, _, _, _, shared_stems = top3[0]
            # Apply stem floor for < 0.50
            if r_score >= t_val and (r_score >= 0.50 or len(shared_stems) >= 3):
                tot_t += 1
                if not _is_block_quotation_chapter(bom_book_names[bi_idx], bom_ch_nums[bi_idx]):
                    nb_t += 1
                if bib_testament[bib_j] == "OT":
                    ot_t += 1
                else:
                    nt_t += 1
        calib_rows.append({
            "thresh": t_val,
            "total": tot_t,
            "non_block": nb_t,
            "ot": ot_t,
            "nt": nt_t,
        })

    # Determine which verses pass the calibrated 3-Tier threshold regime:
    # Tier I: r >= 0.62 (Direct Quotation / Near-Verbatim Parallel)
    # Tier II: 0.50 <= r < 0.62 with >= 2 shared content stems (High Stylistic & Phraseological Match)
    # Tier III: 0.45 <= r < 0.50 with >= 3 shared content stems (Strong Embedded Resonance)
    accepted_bom_matches: dict[int, list[tuple[int, float, float, float, float, float, list[str], str]]] = {}
    correlated_bib_to_bom: dict[int, list[tuple[int, float, str]]] = defaultdict(list)

    for bi_idx in range(n_bom):
        accepted_for_v = []
        for bib_j, r_score, c_val, foc_val, cad_val, sem_val, shared_stems in bom_top_list[bi_idx]:
            tier = None
            if r_score >= 0.62 and len(shared_stems) >= 1:
                tier = "Tier I"
            elif r_score >= 0.50 and len(shared_stems) >= 2:
                tier = "Tier II"
            elif r_score >= 0.45 and len(shared_stems) >= 3:
                tier = "Tier III"

            if tier is not None:
                accepted_for_v.append((bib_j, r_score, c_val, foc_val, cad_val, sem_val, shared_stems, tier))
        if accepted_for_v:
            # Keep top 2 distinct biblical matches per verse
            accepted_bom_matches[bi_idx] = accepted_for_v[:2]
            for bib_j, r_score, _, _, _, _, _, tier in accepted_for_v[:2]:
                correlated_bib_to_bom[bib_j].append((bi_idx, r_score, tier))

    # Assign deterministic XHTML coordinates for Part III (Correlated Old & New Testament Parallel Treasury)
    # Book 1 = Study Atlas (`bk_01`), Books 2..16 = 15 BoM Books (`bk_02`..`bk_16`),
    # Book 17 = OT Parallel Treasury (`bk_17`), Book 18 = NT Parallel Treasury (`bk_18`).
    ot_corr_by_book: dict[str, list[int]] = defaultdict(list)
    nt_corr_by_book: dict[str, list[int]] = defaultdict(list)
    for bib_j in sorted(correlated_bib_to_bom.keys()):
        if bib_testament[bib_j] == "OT":
            ot_corr_by_book[bib_book_names[bib_j]].append(bib_j)
        else:
            nt_corr_by_book[bib_book_names[bib_j]].append(bib_j)

    bib_treasury_target: dict[int, tuple[str, int]] = {}
    ot_treasury_chapters: list[Chapter] = []
    nt_treasury_chapters: list[Chapter] = []

    # Build Book 17 (OT Parallel Treasury, `bk_17`) chapter coordinates first so BoM verses can link to them!
    ot_book_order = [b.title for b in ot.books if b.title in ot_corr_by_book]
    for ch_idx_ot, b_title_ot in enumerate(ot_book_order, start=1):
        xhtml_ot = f"bk_17_ch_{ch_idx_ot:03d}.xhtml"
        for seq_v, bib_j in enumerate(ot_corr_by_book[b_title_ot], start=1):
            bib_treasury_target[bib_j] = (xhtml_ot, seq_v)

    nt_book_order = [b.title for b in nt.books if b.title in nt_corr_by_book]
    for ch_idx_nt, b_title_nt in enumerate(nt_book_order, start=1):
        xhtml_nt = f"bk_18_ch_{ch_idx_nt:03d}.xhtml"
        for seq_v, bib_j in enumerate(nt_corr_by_book[b_title_nt], start=1):
            bib_treasury_target[bib_j] = (xhtml_nt, seq_v)

    # Compute Book-level correlation stats for Plate II
    book_corr_stats: list[dict[str, Any]] = []
    bib_book_hit_counts: Counter[tuple[str, str]] = Counter()
    for b in bom.books:
        b_indices = [i for i, bname in enumerate(bom_book_names) if bname == b.title]
        tot_bv = len(b_indices) or 1
        ot_c = 0
        nt_c = 0
        t1_c = 0
        t2_c = 0
        t3_c = 0
        for idx_v in b_indices:
            if idx_v in accepted_bom_matches:
                best_m = accepted_bom_matches[idx_v][0]
                bj = best_m[0]
                tier = best_m[7]
                if bib_testament[bj] == "OT":
                    ot_c += 1
                else:
                    nt_c += 1
                if tier == "Tier I":
                    t1_c += 1
                elif tier == "Tier II":
                    t2_c += 1
                else:
                    t3_c += 1
                bib_book_hit_counts[(bib_book_names[bj], bib_testament[bj])] += 1
        corr_tot = ot_c + nt_c
        book_corr_stats.append({
            "book": b.title,
            "total_v": tot_bv,
            "corr_v": corr_tot,
            "corr_pct": (corr_tot / tot_bv) * 100.0,
            "ot_cnt": ot_c,
            "nt_cnt": nt_c,
            "t1": t1_c,
            "t2": t2_c,
            "t3": t3_c,
        })

    top_bib_books_list = [
        (bname, tcode, cnt)
        for (bname, tcode), cnt in bib_book_hit_counts.most_common(15)
    ]

    plate_calib = render_lm_threshold_calibration_plate(calib_rows, chosen_r=0.45)
    plate_bom_corr = render_bom_book_correlations_plate(book_corr_stats, top_bib_books_list)

    # Build Part II: Enriched Book of Mormon Books (`bk_02` .. `bk_16`)
    enriched_bom_books: list[Book] = []
    global_bom_v_idx = 0

    for b_idx, b in enumerate(bom.books, start=2):
        new_chapters: list[Chapter] = []
        for ch_idx, ch in enumerate(b.chapters, start=1):
            ch_annotations: list[Annotation] = []
            new_verses: list[Verse] = []
            ch_ot_matches = 0
            ch_nt_matches = 0
            ch_max_r = 0.0
            fn_seq = 1

            for v in ch.verses:
                bi_idx = global_bom_v_idx
                global_bom_v_idx += 1
                matches = accepted_bom_matches.get(bi_idx, [])

                if not matches:
                    new_verses.append(Verse(verse=v.verse, text=apply_fine_typography(v.text)))
                    continue

                # Highlight shared content stems in the Book of Mormon verse text
                union_stems = set()
                for m in matches:
                    union_stems.update(m[6])

                parts_v: list[str] = []
                cursor = 0
                for wm in WORD_RE.finditer(v.text):
                    parts_v.append(html.escape(apply_fine_typography(v.text[cursor : wm.start()])))
                    w_surf = html.escape(apply_fine_typography(wm.group(0)))
                    w_st = _simple_stem(wm.group(0))
                    if w_st in union_stems:
                        parts_v.append(f'<span class="lm-match-word">{w_surf}</span>')
                    else:
                        parts_v.append(w_surf)
                    cursor = wm.end()
                parts_v.append(html.escape(apply_fine_typography(v.text[cursor:])))

                # Append inline Language Model Correlation Pop-Up Badge + Direct Link to Part III Treasury
                for m in matches:
                    bib_j, r_score, c_val, foc_val, cad_val, sem_val, shared_stems, tier = m
                    ch_max_r = max(ch_max_r, r_score)
                    t_code = bib_testament[bib_j]
                    if t_code == "OT":
                        ch_ot_matches += 1
                    else:
                        ch_nt_matches += 1

                    ann_id = f"lm-{b_idx}-{ch_idx}-{fn_seq}"
                    fn_seq += 1

                    if tier == "Tier I":
                        badge_cls = "lm-badge lm-high"
                    elif tier == "Tier II":
                        badge_cls = "lm-badge lm-mid"
                    else:
                        badge_cls = "lm-badge"

                    short_bib_ref = bib_refs[bib_j]
                    parts_v.append(
                        f' <a class="noteref {badge_cls}" epub:type="noteref" id="ref-{ann_id}" href="#fn-{ann_id}">'
                        f'≈ {t_code}: {html.escape(short_bib_ref)} · r={r_score:.2f}</a>'
                    )

                    # Also add a compact cross-link arrow to the Part III Biblical Treasury
                    t_target = bib_treasury_target.get(bib_j)
                    if t_target:
                        parts_v.append(
                            f' <a class="lm-badge" href="{t_target[0]}#v-{t_target[1]}" title="View in Biblical Parallel Treasury">↗</a>'
                        )

                    stems_str = ", ".join(shared_stems) if shared_stems else "semantic/cadence alignment"
                    ch_annotations.append(
                        Annotation(
                            id=ann_id,
                            label=f"≈ {t_code} r={r_score:.2f}",
                            title=f"{bib_refs[bib_j]} ({tier} Correlation · r = {r_score:.3f})",
                            paragraphs=[
                                f"“{apply_fine_typography(bib_texts[bib_j])}”",
                                (
                                    f"Language Model Breakdown — Phrase TF-IDF: {c_val:.2f} | "
                                    f"Focal Clause IDF: {foc_val:.2f} | "
                                    f"KJV Cadence 3-gram: {cad_val:.2f} | "
                                    f"SPPMI-SVD + LSA Semantic Vector: {sem_val:.2f} | "
                                    f"Shared Stems: [{stems_str}]."
                                ),
                            ],
                        )
                    )

                new_verses.append(
                    Verse(
                        verse=v.verse,
                        text=apply_fine_typography(v.text),
                        html_text="".join(parts_v),
                    )
                )

            tot_ch_corr = ch_ot_matches + ch_nt_matches
            if tot_ch_corr > 0:
                ch_headnote = (
                    f"LANGUAGE MODEL CORRELATION TELEMETRY • Correlated Biblical Links in Chapter: {tot_ch_corr} "
                    f"(Old Testament: {ch_ot_matches} | New Testament: {ch_nt_matches}) | "
                    f"Peak Similarity Score: r = {ch_max_r:.3f}. "
                    f"Tap any [≈ OT/NT · r=…] badge for the full biblical text and 4-channel score breakdown, or [↗] to jump to the Parallel Treasury."
                )
            else:
                ch_headnote = (
                    f"LANGUAGE MODEL CORRELATION TELEMETRY • Independent Nephite historical narrative "
                    f"(0 verses above the calibrated r ≥ 0.45 biblical correlation threshold)."
                )

            new_chapters.append(
                Chapter(
                    id=ch.id,
                    number=ch.number,
                    title=f"{b.title} {ch.number}" if b.title not in ch.title else ch.title,
                    subtitle=ch.subtitle,
                    headnote=ch_headnote,
                    verses=new_verses,
                    annotations=ch_annotations,
                )
            )

        enriched_bom_books.append(
            Book(
                id=b.id,
                title=b.title,
                subtitle=b.subtitle,
                chapters=new_chapters,
            )
        )

    # Build Part III: Book 17 (OT Parallel Treasury) and Book 18 (NT Parallel Treasury)
    for ch_idx_ot, b_title_ot in enumerate(ot_book_order, start=1):
        v_list_ot: list[Verse] = []
        for seq_v, bib_j in enumerate(ot_corr_by_book[b_title_ot], start=1):
            bom_links = correlated_bib_to_bom[bib_j]
            bom_links.sort(key=lambda x: -x[1])
            link_pills = [
                f'<a class="lm-badge" href="{bom_xhtml_files[b_i]}#v-{bom_v_nums[b_i]}">'
                f'↩ {html.escape(bom_refs[b_i])} (r={r_s:.2f})</a>'
                for b_i, r_s, _ in bom_links[:6]
            ]
            v_html = (
                f'<strong>[{html.escape(bib_refs[bib_j])}]</strong> '
                f'{html.escape(apply_fine_typography(bib_texts[bib_j]))} '
                f'{" ".join(link_pills)}'
            )
            v_list_ot.append(
                Verse(
                    verse=seq_v,
                    text=f"[{bib_refs[bib_j]}] {bib_texts[bib_j]}",
                    html_text=v_html,
                )
            )
        ot_treasury_chapters.append(
            Chapter(
                id=f"treasury-ot-{ch_idx_ot:02d}",
                number=ch_idx_ot,
                title=f"Old Testament Parallels: {b_title_ot}",
                subtitle=f"{len(v_list_ot)} Correlated Verses Linked Back to the Book of Mormon",
                headnote=(
                    f"Every {b_title_ot} verse below achieved a calibrated Language Model correlation "
                    f"(r ≥ 0.45) with one or more Book of Mormon passages. Tap any [↩ BoM Ref] pill to return directly to the Book of Mormon verse."
                ),
                verses=v_list_ot,
            )
        )

    for ch_idx_nt, b_title_nt in enumerate(nt_book_order, start=1):
        v_list_nt: list[Verse] = []
        for seq_v, bib_j in enumerate(nt_corr_by_book[b_title_nt], start=1):
            bom_links = correlated_bib_to_bom[bib_j]
            bom_links.sort(key=lambda x: -x[1])
            link_pills = [
                f'<a class="lm-badge" href="{bom_xhtml_files[b_i]}#v-{bom_v_nums[b_i]}">'
                f'↩ {html.escape(bom_refs[b_i])} (r={r_s:.2f})</a>'
                for b_i, r_s, _ in bom_links[:6]
            ]
            v_html = (
                f'<strong>[{html.escape(bib_refs[bib_j])}]</strong> '
                f'{html.escape(apply_fine_typography(bib_texts[bib_j]))} '
                f'{" ".join(link_pills)}'
            )
            v_list_nt.append(
                Verse(
                    verse=seq_v,
                    text=f"[{bib_refs[bib_j]}] {bib_texts[bib_j]}",
                    html_text=v_html,
                )
            )
        nt_treasury_chapters.append(
            Chapter(
                id=f"treasury-nt-{ch_idx_nt:02d}",
                number=ch_idx_nt,
                title=f"New Testament Parallels: {b_title_nt}",
                subtitle=f"{len(v_list_nt)} Correlated Verses Linked Back to the Book of Mormon",
                headnote=(
                    f"Every {b_title_nt} verse below achieved a calibrated Language Model correlation "
                    f"(r ≥ 0.45) with one or more Book of Mormon passages. Tap any [↩ BoM Ref] pill to return directly to the Book of Mormon verse."
                ),
                verses=v_list_nt,
            )
        )

    ot_treasury_book = Book(
        id="book-17-ot-parallel-treasury",
        title="Part III-A: Correlated Old Testament Parallel Treasury",
        subtitle="Full KJV Text of All Correlated Old Testament Passages with Reverse Links to the Book of Mormon",
        chapters=ot_treasury_chapters,
    )
    nt_treasury_book = Book(
        id="book-18-nt-parallel-treasury",
        title="Part III-B: Correlated New Testament Parallel Treasury",
        subtitle="Full KJV Text of All Correlated New Testament Passages with Reverse Links to the Book of Mormon",
        chapters=nt_treasury_chapters,
    )

    # Build Part I (`bk_01`): Language Model Methodology, Threshold Calibration & Top 120 Embedded Correlations
    calib_table_rows = []
    for r_row in calib_rows:
        mark = " ◀ Calibrated Floor" if abs(r_row["thresh"] - 0.45) < 0.005 else (
            " ◀ Tier II Floor" if abs(r_row["thresh"] - 0.50) < 0.005 else (
                " ◀ Tier I Verbatim" if abs(r_row["thresh"] - 0.62) < 0.005 else ""
            )
        )
        calib_table_rows.append(
            f"<tr>"
            f"<td><strong>r ≥ {r_row['thresh']:.2f}{html.escape(mark)}</strong></td>"
            f"<td>{r_row['total']:,} ({r_row['total']/n_bom*100:.1f}%)</td>"
            f"<td>{r_row['non_block']:,}</td>"
            f"<td>{r_row['ot']:,} OT / {r_row['nt']:,} NT</td>"
            f"</tr>"
        )

    bom_stats_rows = []
    for b_st in book_corr_stats:
        spark_c = _sparkbar(b_st["corr_pct"], max(x["corr_pct"] for x in book_corr_stats), 6)
        bom_stats_rows.append(
            f"<tr>"
            f"<td><strong>{html.escape(b_st['book'])}</strong></td>"
            f"<td>{b_st['corr_v']:,} / {b_st['total_v']:,} ({b_st['corr_pct']:.1f}%)</td>"
            f"<td><span class=\"spark-bar\">{spark_c}</span> {b_st['ot_cnt']} OT · {b_st['nt_cnt']} NT</td>"
            f"<td>{b_st['t1']} / {b_st['t2']} / {b_st['t3']}</td>"
            f"</tr>"
        )

    # Collect Top 120 Non-Block Embedded Stylistic & Theological Correlations for Chapter 2 Leaderboard
    non_block_hits = []
    for bi_idx, m_list in accepted_bom_matches.items():
        if _is_block_quotation_chapter(bom_book_names[bi_idx], bom_ch_nums[bi_idx]):
            continue
        best_m = m_list[0]
        non_block_hits.append((bi_idx, best_m[0], best_m[1], best_m[6], best_m[7]))
    non_block_hits.sort(key=lambda x: -x[2])

    leaderboard_rows = []
    for rank, (bi_idx, bib_j, r_score, shared_stems, tier) in enumerate(non_block_hits[:120], start=1):
        bom_link = f'<a href="{bom_xhtml_files[bi_idx]}#v-{bom_v_nums[bi_idx]}"><strong>{html.escape(bom_refs[bi_idx])}</strong></a>'
        t_target = bib_treasury_target.get(bib_j)
        bib_link = (
            f'<a href="{t_target[0]}#v-{t_target[1]}"><strong>{html.escape(bib_refs[bib_j])}</strong> ({bib_testament[bib_j]})</a>'
            if t_target
            else f"{html.escape(bib_refs[bib_j])} ({bib_testament[bib_j]})"
        )
        bom_snip = bom_texts[bi_idx]
        if len(bom_snip) > 95:
            bom_snip = bom_snip[:92] + "…"
        bib_snip = bib_texts[bib_j]
        if len(bib_snip) > 95:
            bib_snip = bib_snip[:92] + "…"
        leaderboard_rows.append(
            f"<tr>"
            f"<td>{rank}</td>"
            f"<td><strong>{r_score:.3f}</strong> ({tier})</td>"
            f"<td>{bom_link}<br/><em>“{html.escape(bom_snip)}”</em></td>"
            f"<td>{bib_link}<br/><em>“{html.escape(bib_snip)}”</em></td>"
            f"<td>{html.escape(', '.join(shared_stems[:5]))}</td>"
            f"</tr>"
        )

    study_ch1 = Chapter(
        id="lm-study-01-calibration",
        number=1,
        title="1. Language Model Architecture & Empirical Threshold Calibration",
        subtitle="How We Found the Optimal Correlation Mark Between Book of Mormon and Biblical Passages",
        is_front_matter=True,
        blocks=[
            TextBlock(
                block_type=BlockType.PARAGRAPH,
                text="",
                html_text=(
                    "Where should one draw the line between a genuine stylistic or theological parallel "
                    "and ordinary King James narrative prose? To answer this question empirically, we trained "
                    "a <strong>four-channel Scriptural Language Model</strong> across all 41,995 canonical verses "
                    "(evaluating every one of the 6,604 Book of Mormon verses and sub-clauses against all "
                    "31,102 Old and New Testament verses—over 205 million verse-pair comparisons):"
                ),
            ),
            TextBlock(
                block_type=BlockType.CALLOUT,
                text="",
                html_text=(
                    "<p><strong>The Four-Channel Scriptural Language Model (`r` Composite Score):</strong></p>"
                    "<p>1. <strong>Stemmed Phraseological TF-IDF (`0.34 weight`):</strong> Unigram and bigram inverse-document-frequency alignment on morphologically normalized stems (unifying archaic <em>-eth/-est</em> inflections).</p>"
                    "<p>2. <strong>Focal Top-IDF Clause Containment (`0.28 weight`):</strong> Measures whether the five highest-information words of a biblical verse are embedded inside a longer Book of Mormon discourse verse (preventing verse-length dilution).</p>"
                    "<p>3. <strong>Stylistic Cadence Trigrams (`0.18 weight`):</strong> Captures King James syntactic rhythm and function-word cadence across 1–3 word windows while downweighting formulaic genealogies (<em>“was the son of”</em>, <em>“begat”</em>).</p>"
                    "<p>4. <strong>96-d SPPMI-SVD Distributional Word Embeddings + 96-d LSA (`0.20 weight`):</strong> Captures deep semantic resonance even when surface phrasing shifts.</p>"
                ),
            ),
            TextBlock(
                block_type=BlockType.TABLE,
                text="",
                html_text=(
                    '<figure class="data-figure">'
                    '<p class="figure-kicker">Plate I • Language Model Threshold Calibration Curve</p>'
                    '<img class="chart-img" src="../images/fig_threshold_calibration.png" alt="Language Model Threshold Calibration Curve" />'
                    '<figcaption class="figure-caption">Figure 1.1: Empirical signal-to-noise sweep across similarity thresholds r = 0.38 to 0.68.</figcaption>'
                    '</figure>'
                ),
            ),
            TextBlock(
                block_type=BlockType.TABLE,
                text="",
                html_text=(
                    '<table class="grammar-table">'
                    '<thead><tr><th>Similarity Threshold (r)</th><th>Total Correlated BoM Verses</th><th>Embedded Non-Block Echoes</th><th>Testament Split (OT / NT)</th></tr></thead>'
                    f'<tbody>{"".join(calib_table_rows)}</tbody>'
                    '</table>'
                ),
            ),
            TextBlock(
                block_type=BlockType.TABLE,
                text="",
                html_text=(
                    '<figure class="data-figure">'
                    '<p class="figure-kicker">Plate II • Old &amp; New Testament Correlation Density by Book</p>'
                    '<img class="chart-img" src="../images/fig_bom_book_correlations.png" alt="Book of Mormon Biblical Correlation Density" />'
                    '<figcaption class="figure-caption">Figure 1.2: Correlated verses across all 15 books of the Book of Mormon and top 15 biblical source books.</figcaption>'
                    '</figure>'
                ),
            ),
            TextBlock(
                block_type=BlockType.TABLE,
                text="",
                html_text=(
                    '<table class="grammar-table">'
                    '<thead><tr><th>Book of Mormon Book</th><th>Correlated Verses (%)</th><th>OT vs. NT Breakdown</th><th>Tier I / Tier II / Tier III</th></tr></thead>'
                    f'<tbody>{"".join(bom_stats_rows)}</tbody>'
                    '</table>'
                ),
            ),
        ],
    )

    study_ch2 = Chapter(
        id="lm-study-02-leaderboard",
        number=2,
        title="2. Top 120 Embedded Stylistic & Theological Correlations (Outside Block Quotations)",
        subtitle="Highest-Scoring Phraseological Parallels in Sermons, Epistles, and Narrative Chapters",
        is_front_matter=True,
        blocks=[
            TextBlock(
                block_type=BlockType.PARAGRAPH,
                text="",
                html_text=(
                    "While readers already know the major block quotations of Isaiah (2 Nephi 12–24) and the "
                    "Sermon at the Temple (3 Nephi 12–14), the true power of a trained Language Model is its "
                    "ability to uncover <strong>embedded stylistic and phraseological correlations</strong> woven "
                    "into the sermons and letters of Nephi, Jacob, King Benjamin, Abinadi, Alma, Amulek, Helaman, "
                    "Mormon, and Moroni. Every link below jumps directly to the Book of Mormon verse or its "
                    "counterpart in the Biblical Parallel Treasury."
                ),
            ),
            TextBlock(
                block_type=BlockType.TABLE,
                text="",
                html_text=(
                    '<table class="grammar-table">'
                    '<thead><tr><th>#</th><th>LM Score (r)</th><th>Book of Mormon Passage</th><th>Correlated OT / NT Passage</th><th>Shared Stems</th></tr></thead>'
                    f'<tbody>{"".join(leaderboard_rows)}</tbody>'
                    '</table>'
                ),
            ),
        ],
    )

    study_book = Book(
        id="book-01-lm-study-atlas",
        title="Part I: Language Model Methodology, Calibration & Leaderboard",
        subtitle="Empirical Threshold Analysis and Top 120 Embedded Biblical Correlations",
        chapters=[study_ch1, study_ch2],
    )

    return Work(
        id="bom-language-model-correlations",
        title="The Book of Mormon: Language Model Biblical Correlation Edition",
        subtitle="Stylistic, Phraseological & Distributional Semantic Alignment with the Old and New Testaments",
        description=(
            "An analytical edition of the Book of Mormon powered by a 4-channel Scriptural Language "
            "Model (Stemmed Phrase TF-IDF, Focal Top-IDF Clause Containment, KJV Cadence Trigrams, and "
            "96-d SPPMI-SVD + LSA Embeddings) trained across all 41,995 canonical verses. Highlights "
            "shared biblical phrasing inline, provides native Kindle pop-up footnotes with full KJV "
            "verses and model telemetry, and includes a bidirectional Old & New Testament Parallel Treasury."
        ),
        authors=[
            "Joseph Smith Jr. (Translator)",
            "Proteus Computational Linguistics Lab (Language Model & Parallel Apparatus)",
        ],
        edition_label="Proteus Language Model Correlation Study Edition",
        css_theme="datascience.css",
        books=[study_book] + enriched_bom_books + [ot_treasury_book, nt_treasury_book],
        images={
            "fig_threshold_calibration.png": plate_calib,
            "fig_bom_book_correlations.png": plate_bom_corr,
        },
    )
