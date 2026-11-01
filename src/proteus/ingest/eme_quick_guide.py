"""A Plain-Language Quick Guide to Early Modern English in Scripture (`eme_quick_guide.py`).

A short, lay-reader companion to the longer scholarly reference in `early_modern_english.py`.
It covers only what a new reader of the King James Bible and the Book of Mormon needs:

1. Part 1: The Grammar You Need (you/thou/ye, verb endings, sentence quirks)
2. Part 2: The Words You Need (words we no longer use, and words that changed meaning)
3. Part 3: Practice & Cheat Sheet (two worked passages and a one-page summary)

Verses quoted are from the KJV (public domain) and the Book of Mormon.
"""

from __future__ import annotations

from proteus.core.models import Book, Chapter, Work
from proteus.ingest.early_modern_english import ChapterDraft


def _draft(chapter_id: str, title: str, subtitle: str | None = None, headnote: str | None = None,
           number: int | None = None, front: bool = False) -> ChapterDraft:
    # No pop-up citations are used here, so no corpus lookup is needed (keeps the build fast).
    return ChapterDraft(
        chapter_id=chapter_id,
        title=title,
        subtitle=subtitle,
        headnote=headnote,
        corpus=None,  # type: ignore[arg-type]
        number=number,
        is_front_matter=front,
    )


def _build_intro() -> list[Chapter]:
    d = _draft(
        "eme-quick-intro",
        "Before You Begin",
        "A short guide to the old English of the scriptures",
        "The King James Bible (1611) and the Book of Mormon (1830) are written in Early Modern English. "
        "It is English, but it is not quite the English we speak.",
        front=True,
    )
    d.para(
        "Most of it you can read just fine. A few small things trip people up again and again: words like "
        "<em>thou</em> and <em>ye</em>, verbs that end in <em>-eth</em>, words nobody uses anymore, and a handful "
        "of familiar words that used to mean something different."
    )
    d.para(
        "This guide covers just those things, in plain language. You do not need any grammar training. "
        "It is short on purpose, so read it once straight through, then keep it handy."
    )
    d.callout(
        "What is inside",
        [
            "<strong>Part 1 – Grammar:</strong> you, thou and ye; verb endings; a few odd sentence habits.",
            "<strong>Part 2 – Words:</strong> old words, plus “false friends” that look modern but mean something else.",
            "<strong>Part 3 – Practice:</strong> two passages worked through, and a one-page cheat sheet.",
        ],
    )
    return [d.build()]


def _build_part_1_grammar() -> Book:
    chapters: list[Chapter] = []

    # ---------------- 1. YOU / THOU / YE ----------------
    c = _draft(
        "eme-quick-p1-ch1", "1. Thou, Thee, Ye and You", number=1,
        headnote="The biggest difference: old English had one word for “you” (one person) and another for “you all.”",
    )
    c.para(
        "Today we say <em>you</em> to one person or to a hundred. Old English kept them apart. "
        "<strong>Thou</strong> and its forms mean one person. <strong>Ye</strong> and <strong>you</strong> mean "
        "more than one."
    )
    c.table(
        headers=["", "One person", "More than one"],
        rows=[
            ["<strong>Doing the action</strong> (subject)", "<strong>thou</strong> (“Thou art…”)", "<strong>ye</strong> (“Ye are…”)"],
            ["<strong>Receiving it</strong> (object)", "<strong>thee</strong> (“I say unto thee”)", "<strong>you</strong> (“I say unto you”)"],
            ["<strong>Belonging to</strong>", "<strong>thy</strong> / <strong>thine</strong>", "<strong>your</strong> / <strong>yours</strong>"],
        ],
    )
    c.callout(
        "Easy memory trick",
        [
            "<strong>Th-</strong> words = one person. <strong>Y-</strong> words = a group.",
            "<em>Thou</em> and <em>ye</em> do the action (like <em>I</em> and <em>we</em>). "
            "<em>Thee</em> and <em>you</em> receive it (like <em>me</em> and <em>us</em>).",
        ],
    )
    c.subheading("Is “thou” more respectful or holy?")
    c.para(
        "No. <em>Thou</em> was simply “you” for one person. People used it for family, friends and God alike. "
        "It only feels solemn to us because it disappeared from daily speech but stayed in the scriptures and prayers."
    )
    c.subheading("Why it matters")
    c.para(
        "Seeing the difference can reveal who is being spoken to. In Luke 22:31–32 Jesus says: "
        "<em>“Simon, Simon, behold, Satan hath desired to have <strong>you</strong>, that he may sift "
        "<strong>you</strong> as wheat: But I have prayed for <strong>thee</strong>, that <strong>thy</strong> "
        "faith fail not.”</em> The first “you” is all the apostles; the “thee” is Peter alone. "
        "Modern English hides that."
    )
    c.para(
        "Likewise John 3:7: <em>“Marvel not that I said unto <strong>thee</strong> [Nicodemus], "
        "<strong>Ye</strong> [all of you] must be born again.”</em>"
    )
    chapters.append(c.build())

    # ---------------- 2. MY/MINE ----------------
    c = _draft(
        "eme-quick-p1-ch2", "2. Thy or Thine? My or Mine?", number=2,
        headnote="It works just like “a” and “an.”",
    )
    c.para(
        "You say <em>a</em> pear but <em>an</em> apple. Old English did the same with <em>my/mine</em> and "
        "<em>thy/thine</em>: the short form goes before a consonant sound, the long form before a vowel sound."
    )
    c.table(
        headers=["Before…", "Use", "Examples"],
        rows=[
            ["a consonant sound", "<strong>my, thy</strong>", "<em>my servant</em>, <em>thy faith</em>, <em>thy whole body</em>"],
            ["a vowel sound (or a soft <em>h</em>)", "<strong>mine, thine</strong>",
             "<em>mine enemies</em>, <em>thine eye</em>, <em>thine heart</em>, <em>mine own</em>"],
            ["nothing (it stands alone)", "<strong>mine, thine</strong>", "<em>“For <strong>thine</strong> is the kingdom.”</em>"],
        ],
    )
    c.para(
        "Both appear in one verse: <em>“Thou preparest a table before me in the presence of "
        "<strong>mine</strong> enemies: thou anointest <strong>my</strong> head with oil”</em> (Psalm 23:5). "
        "Same meaning either way: it is just “my” and “your.”"
    )
    chapters.append(c.build())

    # ---------------- 3. VERB ENDINGS ----------------
    c = _draft(
        "eme-quick-p1-ch3", "3. Verb Endings: -est and -eth", number=3,
        headnote="Verbs changed their endings depending on who was doing the action. Just look past the ending.",
    )
    c.para("Two endings do most of the work:")
    c.table(
        headers=["Ending", "Goes with", "Example", "Means"],
        rows=[
            ["<strong>-est</strong> (or <strong>-st</strong>)", "<em>thou</em> (one person you’re talking to)",
             "<em>Thou knowest</em> · <em>thou art</em> · <em>thou hast</em>", "you know · you are · you have"],
            ["<strong>-eth</strong> (or <strong>-th</strong>)", "<em>he, she, it</em>, or a single thing",
             "<em>He loveth</em> · <em>it maketh</em> · <em>he saith</em>", "he loves · it makes · he says"],
        ],
    )
    c.para(
        "Paul’s famous line uses <em>-eth</em> over and over: <em>“Charity <strong>suffereth</strong> long, and is kind; "
        "charity <strong>envieth</strong> not; charity <strong>vaunteth</strong> not itself”</em> "
        "(1 Corinthians 13:4). Read: “Love is patient and kind; love does not envy or boast.”"
    )
    c.subheading("Common little verbs")
    c.table(
        headers=["Old form", "Modern form"],
        rows=[
            ["art / wast / wert", "are / were"],
            ["hast / hath", "have / has"],
            ["dost / doth", "do / does"],
            ["wilt / shalt", "will / shall (“Thou shalt not steal” = you must not steal)"],
            ["canst / couldest / wouldest", "can / could / would"],
            ["saith / said", "says / said"],
            ["cometh / goeth / giveth", "comes / goes / gives"],
        ],
    )
    c.callout(
        "Two quick tips",
        [
            "<strong>Past tense with thou</strong> adds <em>-st</em> too: <em>thou wentest</em> = you went; "
            "<em>thou girdedst thyself</em> = you dressed yourself.",
            "<strong>Plural subjects</strong> usually have no ending: <em>“the wicked flee,”</em> but "
            "<em>“the wicked man fleeth.”</em>",
        ],
    )
    chapters.append(c.build())

    # ---------------- 4. SENTENCE HABITS ----------------
    c = _draft(
        "eme-quick-p1-ch4", "4. Odd Sentence Habits", number=4,
        headnote="Six patterns that look strange today but follow simple rules.",
    )
    c.subheading("1. No “do” needed for questions and “not”")
    c.para(
        "We say “What do you think?” and “Do not fear.” They said it directly: "
        "<em>“What <strong>think ye</strong>?”</em> (Matthew 22:42) and <em>“<strong>Fear not</strong>”</em> "
        "(Luke 2:10). Just add “do” in your head."
    )
    c.subheading("2. Verb before the subject")
    c.para(
        "<em>“Whom <strong>say ye</strong> that I am?”</em> (Matthew 16:15) means “Who do you say that I am?” "
        "<em>“Knowest thou not?”</em> means “Don’t you know?”"
    )
    c.subheading("3. “Is come” and “are fallen”: being, not having")
    c.para(
        "With verbs of coming, going and rising, old English said <em>is/are</em> where we say <em>has/have</em>. "
        "<em>“We <strong>are come</strong> to worship him”</em> (Matthew 2:2) means “We have come.” "
        "<em>“He <strong>is risen</strong>”</em> means “He has risen.”"
    )
    c.subheading("4. “Which” for people")
    c.para(
        "<em>“Our Father <strong>which</strong> art in heaven”</em> (Matthew 6:9) means “who is in heaven.” "
        "<em>Which</em> and <em>that</em> were both fine for people."
    )
    c.subheading("5. “If he be…”: a leftover mood")
    c.para(
        "After <em>if</em>, <em>though</em> or <em>lest</em>, the verb often skips its ending. "
        "<em>“If thine eye <strong>be</strong> single”</em> (Matthew 6:22) means “If your eye is focused.” "
        "It is not an error, just an old way of saying “if it’s possible/uncertain.”"
    )
    c.subheading("6. “His” can mean “its,” and “of” can mean “by”")
    c.para(
        "<em>“If the salt have lost <strong>his</strong> savour”</em> (Matthew 5:13) = “its flavor.” "
        "<em>“Led up <strong>of</strong> the Spirit”</em> (Matthew 4:1) = “led by the Spirit.”"
    )
    c.callout(
        "A note on “And it came to pass”",
        [
            "This phrase, very common in the Book of Mormon, is a storytelling marker, like “and then” or "
            "“next.” It mirrors the style of the Hebrew Bible. It simply means “and it happened.”",
        ],
    )
    chapters.append(c.build())

    return Book(
        id="eme-quick-part-1",
        title="Part 1: The Grammar You Need",
        full_title="Part 1: The Grammar You Need",
        subtitle="Thou, ye, -est, -eth, and a few sentence habits",
        chapters=chapters,
    )


# word, meaning, example "quote (reference)"
_WORDS_LITTLE = [
    ("wherefore", "therefore, for this reason (in a question, “why”)", "“Wherefore, by their fruits ye shall know them.” (3 Nephi 14:20)"),
    ("unto", "to", "“Behold, verily, verily, I say unto you…” (3 Nephi 11:31)"),
    ("whither", "to where", "“Whither shall I go from thy spirit?” (Psalms 139:7)"),
    ("hither", "to here", "“Bring them hither to me.” (Matthew 14:18)"),
    ("thither", "to there", "“…went thither to hear his words.” (Mosiah 18:6)"),
    ("whence", "from where", "“…from whence cometh my help.” (Psalms 121:1)"),
    ("hence", "from here", "“…before I go hence, and be no more.” (Psalms 39:13)"),
    ("thence", "from there", "“And he laid his hands on them, and departed thence.” (Matthew 19:15)"),
    ("yea", "yes (or “indeed”)", "“Yea, cry unto him for mercy…” (Alma 34:18)"),
    ("nay", "no", "“And he answered, Nay.” (Alma 30:38)"),
    ("verily", "truly, certainly", "“Verily I say unto you, I know you not.” (Matthew 25:12)"),
    ("behold", "look! pay attention", "“Behold how he loved him!” (John 11:36)"),
    ("hearken", "listen closely", "“Hearken, O ye house of Israel, and hear the words of me, a prophet of the Lord.” (Jacob 5:2)"),
    ("lest", "so that … not; for fear that", "“Not of works, lest any man should boast.” (Ephesians 2:9)"),
    ("ere", "before", "“Sir, come down ere my child die.” (John 4:49)"),
    ("save", "except", "“…save it be those which are forbidden.” (3 Nephi 27:23)"),
    ("nigh", "near", "“And the passover, a feast of the Jews, was nigh.” (John 6:4)"),
    ("yonder", "over there", "“…while I go and pray yonder.” (Matthew 26:36)"),
    ("naught", "nothing", "“…it shall come to naught…” (2 Nephi 18:10)"),
    ("aught", "anything", "“…thy brother hath aught against thee…” (3 Nephi 12:23)"),
    ("twain", "two", "“…go with him twain.” (Matthew 5:41)"),
    ("betwixt", "between", "“Now there must needs be a space betwixt the time of death and the time of the resurrection.” (Alma 40:6)"),
    ("peradventure", "perhaps", "“Peradventure the woman will not follow me.” (Genesis 24:39)"),
    ("whosoever / whatsoever", "whoever / whatever", "“And whosoever shall compel thee to go a mile, go with him twain.” (3 Nephi 12:41)"),
    ("divers", "various, several", "“…count it all joy when ye fall into divers temptations.” (James 1:2)"),
    ("sundry", "various, several", "“God, who at sundry times and in divers manners spake in time past…” (Hebrews 1:1)"),
    ("withal", "with it; besides", "“…the manifestation of the Spirit is given to every man to profit withal.” (1 Corinthians 12:7)"),
]

_WORDS_EVERYDAY = [
    ("brethren", "brothers (and often “fellow believers”)", "“Brethren, pray for us.” (1 Thessalonians 5:25)"),
    ("begat", "was the father of", "“And Boaz begat Obed, and Obed begat Jesse.” (1 Chronicles 2:12)"),
    ("raiment", "clothing", "“And having food and raiment let us be therewith content.” (1 Timothy 6:8)"),
    ("victuals", "food supplies", "“And the men took of their victuals…” (Joshua 9:14)"),
    ("tarry", "wait, stay", "“But I will tarry at Ephesus until Pentecost.” (1 Corinthians 16:8)"),
    ("abide", "stay, remain; endure", "“But who may abide the day of his coming…?” (3 Nephi 24:2)"),
    ("girded", "tied on or around (clothing, armor, weapons)", "“Let your loins be girded about, and your lights burning.” (Luke 12:35)"),
    ("slay / slew", "kill / killed", "“…they were determined to slay them.” (Alma 46:2)"),
    ("smite / smote", "strike / struck", "“And the men that held Jesus mocked him, and smote him.” (Luke 22:63)"),
    ("rend / rent", "tear / torn", "“And the veil of the temple was rent in twain from the top to the bottom.” (Mark 15:38)"),
    ("wax / waxed", "grow / grew", "“…the love of many shall wax cold.” (Matthew 24:12)"),
    ("wroth", "very angry", "“…they were exceedingly wroth…” (Alma 46:2)"),
    ("durst", "dared", "“…for I durst not speak further as yet…” (1 Nephi 22:29)"),
    ("wont", "in the habit of", "“…and went, as he was wont, to the mount of Olives…” (Luke 22:39)"),
    ("fain", "gladly, willingly", "“And he would fain have filled his belly with the husks that the swine did eat…” (Luke 15:16)"),
    ("wist / wot", "knew / know", "“…wist ye not that I must be about my Father’s business?” (Luke 2:49)"),
    ("meet", "fitting, proper", "“Bring forth therefore fruits meet for repentance.” (Matthew 3:8)"),
    ("froward", "stubborn, willfully contrary", "“A naughty person, a wicked man, walketh with a froward mouth.” (Proverbs 6:12)"),
    ("sore", "greatly, painfully", "“…for he wist not what to say; for they were sore afraid.” (Mark 9:6)"),
    ("firmament", "the sky, the dome of heaven", "“The heavens declare the glory of God; and the firmament sheweth his handywork.” (Psalms 19:1)"),
    ("publican", "tax collector", "“Two men went up into the temple to pray; the one a Pharisee, and the other a publican.” (Luke 18:10)"),
    ("usury", "interest on a loan", "“…I should have received mine own with usury.” (Matthew 25:27)"),
]

# word, old meaning, example verse, common mistake
_FALSE_FRIENDS = [
    ("prevent", "go ahead of, come before", "“we which are alive… shall not prevent them which are asleep” (1 Thessalonians 4:15)",
     "Not “stop”: the living will not go before the dead."),
    ("suffer", "allow, let", "“Suffer the little children to come unto me” (Mark 10:14)", "Not “feel pain”: Jesus says “let them come.”"),
    ("conversation", "way of life, behavior", "“let your conversation be as it becometh the gospel” (Philippians 1:27)", "Not “talk.”"),
    ("charity", "love (especially unselfish love)", "“But charity is the pure love of Christ…” (Moroni 7:47)", "Not just giving money."),
    ("meat", "food in general", "“I have meat to eat that ye know not of” (John 4:32)", "Not only animal flesh."),
    ("let", "hinder, stop (rare); usually “allow”", "“was let hitherto” (Romans 1:13)", "Here it means “was blocked.”"),
    ("take no thought", "do not worry", "“Take no thought for your life” (Matthew 6:25)", "Not “don’t think.”"),
    ("careful", "full of worry", "“Be careful for nothing” (Philippians 4:6)", "Means “Don’t be anxious.”"),
    ("pitiful", "full of pity, compassionate", "“be pitiful, be courteous” (1 Peter 3:8)", "A compliment, not an insult."),
    ("quick", "alive, living", "“the word of God is quick, and powerful” (Hebrews 4:12)", "The “quick and the dead” = living and dead."),
    ("peculiar", "special, one’s very own", "“a peculiar people” (1 Peter 2:9)", "Not “weird.”"),
    ("vile", "lowly, humble", "“our vile body” (Philippians 3:21)", "Not “disgusting.”"),
    ("halt", "lame", "“better… to enter into life halt or maimed” (Matthew 18:8)", "Not “stop.”"),
    ("bowels", "deep feelings, compassion", "“bowels of mercies” (Colossians 3:12)", "Think “heart,” not stomach."),
    ("corn", "grain in general (wheat, barley)", "“ears of corn” (Matthew 12:1)", "Not American maize."),
    ("fowl", "birds in general", "“fowl that may fly above the earth” (Genesis 1:20)", "Not just chickens."),
    ("by and by / presently / anon", "right away, immediately", "“by and by he is offended” (Matthew 13:21)",
     "Not “later.” Also “straightway” = immediately."),
    ("want", "lack, need", "“The Lord is my shepherd; I shall not want” (Psalms 23:1)", "Not “desire.”"),
    ("condescension", "kind stooping down to help", "“Knowest thou the condescension of God?” (1 Nephi 11:16)", "It is a good thing: no snobbery."),
]


def _build_part_2_words() -> Book:
    chapters: list[Chapter] = []

    c = _draft(
        "eme-quick-p2-ch1", "5. Little Words You Will Keep Meeting", number=5,
        headnote="Old connecting words, directions and exclamations. Learn these and a lot of verses open up.",
    )
    c.table(
        headers=["Word", "Means", "Example"],
        rows=[[f"<strong>{w}</strong>", m, f"<em>{e}</em>" if e else ""] for w, m, e in _WORDS_LITTLE],
    )
    c.callout(
        "Where / whither / whence",
        [
            "A tidy pattern: <strong>where</strong> = at what place, <strong>whither</strong> = to what place, "
            "<strong>whence</strong> = from what place. The same trio works for here (here / hither / hence) and "
            "there (there / thither / thence).",
        ],
    )
    chapters.append(c.build())

    c = _draft(
        "eme-quick-p2-ch2", "6. Everyday Old Words", number=6,
        headnote="Words that are plainly old. You will not be fooled by these, but it helps to have the meanings.",
    )
    c.table(
        headers=["Word", "Means", "Example"],
        rows=[[f"<strong>{w}</strong>", m, f"<em>{e}</em>" if e else ""] for w, m, e in _WORDS_EVERYDAY],
    )
    chapters.append(c.build())

    c = _draft(
        "eme-quick-p2-ch3", "7. False Friends: Words That Look Modern but Aren’t", number=7,
        headnote="These are the sneaky ones. They look familiar, so we read in our own meaning, and miss the point.",
    )
    c.para("Check this list whenever a verse sounds odd, harsh, or just doesn’t make sense.")
    c.table(
        headers=["Word", "Old meaning", "In scripture", "Watch out"],
        rows=[[f"<strong>{w}</strong>", m, f"<em>{e}</em>", n] for w, m, e, n in _FALSE_FRIENDS],
    )
    c.callout(
        "Why “prevent” is the best example",
        [
            "In 1 Thessalonians 4:15 it looks like Paul is saying the living will not <em>stop</em> the dead from rising. "
            "He means the living will not get ahead of them: <em>all</em> will be gathered together. "
            "The whole verse flips from confusing to comforting once you know the old meaning.",
        ],
    )
    chapters.append(c.build())

    return Book(
        id="eme-quick-part-2",
        title="Part 2: The Words You Need",
        full_title="Part 2: The Words You Need",
        subtitle="Old words and false friends",
        chapters=chapters,
    )


def _build_part_3_practice() -> Book:
    chapters: list[Chapter] = []

    c = _draft(
        "eme-quick-p3-ch1", "8. Let’s Read Two Passages", number=8,
        headnote="Putting it all together, one from the Bible and one from the Book of Mormon.",
    )
    c.subheading("The Lord’s Prayer (Matthew 6:9–10)")
    c.table(
        headers=["As written", "What it says"],
        rows=[
            ["<em>Our Father <strong>which</strong> art in heaven,</em>", "Our Father <strong>who</strong> <strong>is</strong> in heaven,"],
            ["<em>Hallowed be <strong>thy</strong> name.</em>", "May your name be treated as holy."],
            ["<em><strong>Thy</strong> kingdom come, <strong>thy</strong> will be done in earth, as it is in heaven.</em>",
             "May your kingdom come and your will be done on earth as in heaven."],
        ],
    )
    c.para("Here <em>which</em> means “who,” <em>art</em> means “are,” <em>thy</em> is “your” (one person), and “be done” is the old if/wish form.")

    c.subheading("Nephi’s Answer (1 Nephi 11:16–17)")
    c.table(
        headers=["As written", "What it says"],
        rows=[
            ["<em>And he said unto me: <strong>Knowest thou</strong> the condescension of God?</em> (v. 16)",
             "And he said to me: Do you know the loving stooping-down of God?"],
            ["<em>And I said unto him: I <strong>know</strong> that he <strong>loveth</strong> his children;</em>",
             "And I said: I know that he loves his children;"],
            ["<em>nevertheless, I <strong>do not know</strong> the meaning of all things.</em>",
             "still, I don’t know the meaning of everything."],
        ],
    )
    c.para("<em>Knowest thou</em> is the question-flip plus the <em>-est</em> ending. <em>Loveth</em> is <em>-eth</em> for “he.” <em>Condescension</em> is a false friend that carries no snobbery.")
    chapters.append(c.build())

    c = _draft(
        "eme-quick-p3-ch2", "9. One-Page Cheat Sheet", number=9,
        headnote="Keep this page handy.",
    )
    c.table(
        headers=["When you see…", "Think…"],
        rows=[
            ["<strong>thou, thee, thy, thine</strong>", "you / your: <strong>one</strong> person"],
            ["<strong>ye, you, your</strong>", "you / your: <strong>several</strong> people"],
            ["<strong>-est</strong> (<em>knowest</em>)", "“you [one person] know”"],
            ["<strong>-eth</strong> (<em>loveth</em>)", "“he/she/it loves”"],
            ["<strong>hath / doth / saith</strong>", "has / does / says"],
            ["<strong>art / wast / wilt / shalt</strong>", "are / were / will / shall (must)"],
            ["<strong>is come, are fallen</strong>", "has come, have fallen"],
            ["<strong>mine / thine</strong> before a noun", "my / your (before a vowel, like “an”)"],
            ["<strong>“Fear ye not” / “Think ye?”</strong>", "Don’t fear / Do you think?"],
            ["<strong>wherefore</strong>", "therefore (or “why” in a question)"],
            ["<strong>unto, yea, nay, behold, verily</strong>", "to, yes, no, look, truly"],
            ["<strong>prevent, suffer, conversation, charity, meat</strong>", "go before, allow, behavior, love, food"],
        ],
    )
    c.callout(
        "If a verse still sounds odd…",
        [
            "1. Look for <em>th-</em> or <em>y-</em> words and decide: one person or many?",
            "2. Strip the verb ending (<em>-est</em>, <em>-eth</em>) and read the plain verb.",
            "3. Check the false-friends list for a word that looks familiar.",
            "4. Read it aloud: the rhythm often carries the meaning.",
        ],
    )
    chapters.append(c.build())

    return Book(
        id="eme-quick-part-3",
        title="Part 3: Practice & Cheat Sheet",
        full_title="Part 3: Practice & Cheat Sheet",
        subtitle="Two passages and a one-page summary",
        chapters=chapters,
    )


def ingest_early_modern_english_quick_guide() -> Work:
    """Compile the short plain-language Early Modern English quick guide into a normalized `Work`."""
    return Work(
        id="early-modern-english-quick-guide",
        title="Reading Old English Scripture: A Quick Guide",
        subtitle="Easy help with thou, ye, -eth, and the old words of the King James Bible and Book of Mormon",
        authors=["Proteus Scriptorium"],
        edition_label="Plain-Language Quick Guide",
        description=(
            "A short, plain-language guide for everyday readers of the King James Bible and the Book of Mormon. "
            "Covers the basic grammar (thou/ye, -est/-eth, odd sentence patterns), a glossary of old words, "
            "and common 'false friends' whose meanings have changed, with a one-page cheat sheet."
        ),
        subjects=[
            "English language — Early modern, 1500-1700 — Grammar",
            "Bible. English — Authorized — Language, style",
            "Book of Mormon — Language, style",
        ],
        front_matter=_build_intro(),
        books=[_build_part_1_grammar(), _build_part_2_words(), _build_part_3_practice()],
        css_theme="classic.css",
    )


build_early_modern_english_quick_guide = ingest_early_modern_english_quick_guide

