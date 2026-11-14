import re
import unittest

from proteus.core.models import BlockType
from proteus.core.typography import capitalize_verse_start
from proteus.ingest import (
    ingest_kjv_apocrypha,
    ingest_pseudepigrapha,
    ingest_standard_work,
)
from proteus.transforms.narrative import (
    build_narrative_book_of_mormon,
    build_narrative_doctrine_and_covenants,
    build_narrative_new_testament,
    build_narrative_old_testament,
    build_narrative_pearl_of_great_price,
    build_narrative_standard_works,
)


class TestVerseCapitalization(unittest.TestCase):
    def test_capitalize_verse_start_basic(self):
        self.assertEqual(capitalize_verse_start("that these plates"), "That these plates")
        self.assertEqual(capitalize_verse_start("“and it came to pass"), "“And it came to pass")
        self.assertEqual(capitalize_verse_start("  (for behold"), "  (For behold")
        self.assertEqual(capitalize_verse_start("Already capitalized."), "Already capitalized.")
        self.assertEqual(capitalize_verse_start(""), "")

    def test_ingested_verses_always_start_capitalized(self):
        for fn in (
            lambda: ingest_standard_work("book-of-mormon"),
            lambda: ingest_standard_work("doctrine-and-covenants"),
            lambda: ingest_standard_work("pearl-of-great-price"),
            ingest_kjv_apocrypha,
        ):
            work = fn()
            for book in work.books:
                for ch in book.chapters:
                    for v in ch.verses:
                        m = re.match(r'^[\s“‘"\'(\[]*([A-Za-z])', v.text)
                        if m:
                            self.assertTrue(
                                m.group(1).isupper(),
                                f"{v.citation_label} starts with lowercase: {v.text[:40]!r}",
                            )


class TestPseudepigraphaEdition(unittest.TestCase):
    def test_standalone_pseudepigrapha_structure(self):
        work = ingest_pseudepigrapha()
        self.assertEqual(work.id, "pseudepigrapha")
        self.assertEqual(len(work.books), 30)
        book_ids = {b.id for b in work.books}
        self.assertIn("1-enoch-charles", book_ids)
        self.assertIn("enoch-laurence", book_ids)
        self.assertIn("book-of-jubilees", book_ids)
        self.assertIn("book-of-jasher", book_ids)
        self.assertIn("testaments-of-the-twelve-patriarchs", book_ids)
        # Should exclude KJV Deuterocanon and NT Apocrypha / Apostolic Fathers
        self.assertNotIn("1-esdras", book_ids)
        self.assertNotIn("the-didache", book_ids)
        self.assertTrue(work.books[0].title.startswith("[I. "))


class TestNarrativeEditions(unittest.TestCase):
    def test_individual_and_combined_narrative_editions(self):
        ot = build_narrative_old_testament()
        nt = build_narrative_new_testament()
        bom = build_narrative_book_of_mormon()
        dc = build_narrative_doctrine_and_covenants()
        pgp = build_narrative_pearl_of_great_price()
        combined = build_narrative_standard_works()

        self.assertEqual(ot.id, "old-testament-narrative")
        self.assertEqual(nt.id, "new-testament-narrative")
        self.assertEqual(bom.id, "book-of-mormon-narrative")
        self.assertEqual(dc.id, "doctrine-and-covenants-narrative")
        self.assertEqual(pgp.id, "pearl-of-great-price-narrative")
        self.assertEqual(combined.id, "lds-standard-works-narrative")

        # Combined should contain all 87 canonical books + BoM front matter book
        self.assertEqual(len(combined.books), 88)

        # Narrative chapters use paragraph blocks instead of verse-per-line
        gen1 = ot.books[0].chapters[0]
        self.assertEqual(gen1.verses, [])
        self.assertTrue(len(gen1.blocks) > 1)
        self.assertTrue(all(b.block_type == BlockType.PARAGRAPH for b in gen1.blocks))
        self.assertIn('<span class="verse-num" id="v-1">1</span>', gen1.blocks[0].html_text or "")

        # D&C 1:9-10 em-dash continuation should flow seamlessly in the same paragraph
        dc1 = dc.books[0].chapters[0]
        joined_dc1 = "\n".join(b.text for b in dc1.blocks)
        self.assertIn("without measure— unto the day", joined_dc1)
