import unittest
from xml.sax.saxutils import escape

from proteus.core.scripture_linker import (
    ALIAS_TO_CANONICAL,
    BOOK_ALIASES,
    SCRIPTURE_REF_PATTERN,
    linkify_scripture_references,
    linkify_xref_list,
)


class TestScriptureLinker(unittest.TestCase):
    def test_canonical_mapping_completeness(self):
        """Every canonical book alias must map to one of the 87 canonical books."""
        self.assertEqual(len(BOOK_ALIASES), 87)

    def test_linkify_intra_volume(self):
        """Intra-volume references must resolve to internal relative XHTML links."""
        resolver = {
            ("Genesis", 1): ("bk_01_ch_001.xhtml", {1, 2, 7, 9}),
            ("Jonah", 1): ("bk_32_ch_001.xhtml", {9}),
        }
        text = "See Jonah 1:9 and Gen 1:7."
        result = linkify_scripture_references(text, resolver)
        self.assertIn('<a href="bk_32_ch_001.xhtml#v-9" class="scripture-link">Jonah 1:9</a>', result)
        self.assertIn('<a href="bk_01_ch_001.xhtml#v-7" class="scripture-link">Gen 1:7</a>', result)

    def test_cross_volume_retained_as_plain_text(self):
        """Cross-volume references missing from the local resolver must remain unlinked clean text."""
        resolver = {
            ("Genesis", 1): ("bk_01_ch_001.xhtml", {7, 9}),
        }
        text = "2 Pet 3:5; Matt 8:27; Gen 1:9"
        result = linkify_scripture_references(text, resolver)
        # 2 Pet 3:5 and Matt 8:27 are not packaged in this EPUB; retain plain text
        self.assertIn("2 Pet 3:5", result)
        self.assertNotIn("https://", result)
        self.assertNotIn('href="bk_', result.split(";")[0])  # 2 Pet 3:5 should not have href
        # Gen 1:9 is in the resolver; must have relative href
        self.assertIn('<a href="bk_01_ch_001.xhtml#v-9" class="scripture-link">Gen 1:9</a>', result)

    def test_linkify_comma_separated_verses(self):
        """Comma-separated verses and ranges should each be properly hyperlinked."""
        resolver = {
            ("1 Nephi", 2): ("bk_01_ch_002.xhtml", {1, 2, 19, 20}),
        }
        text = "1 Ne. 2:1-2, 19-20"
        result = linkify_scripture_references(text, resolver)
        self.assertIn('<a href="bk_01_ch_002.xhtml#v-1" class="scripture-link">1 Ne. 2:1-2</a>', result)
        self.assertIn('<a href="bk_01_ch_002.xhtml#v-19" class="scripture-link">19-20</a>', result)

    def test_linkify_xref_list(self):
        """Cross-reference lists must be formatted with semicolons and intra-volume items linkified."""
        resolver = {
            ("Psalms", 95): ("bk_19_ch_095.xhtml", {5}),
        }
        xrefs = ["2 Pet 3:5", "Ps 95:5"]
        result = linkify_xref_list(xrefs, resolver)
        self.assertIn('<a href="bk_19_ch_095.xhtml#v-5" class="scripture-link">Ps 95:5</a>', result)
        self.assertIn("2 Pet 3:5", result)
        self.assertNotIn("https://", result)
        self.assertIn("; ", result)


if __name__ == "__main__":
    unittest.main()
