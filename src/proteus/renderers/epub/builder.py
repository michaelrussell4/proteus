"""Deterministic EPUB3 Packaging Engine for Kindle Paperwhite (KFX / Enhanced Typesetting).

Generates commercial-grade EPUB3 files adhering strictly to:
- Uncompressed `mimetype` first entry (`ZIP_STORED`)
- `META-INF/container.xml`
- `OEBPS/content.opf` (EPUB 3.0 package document with `<guide>` and `toc="ncx"` fallback)
- `OEBPS/nav.xhtml` (EPUB3 semantic `<nav epub:type="toc">` and `<nav epub:type="landmarks">`)
- `OEBPS/toc.ncx` (EPUB2 NCX hierarchical navigation)
- `OEBPS/styles/<theme>.css`
- `OEBPS/text/*.xhtml` (Strict semantic XHTML5 with Kindle pop-up footnote `<aside epub:type="footnote">` pairs)
"""

from __future__ import annotations

import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

from proteus.core.models import Work
from proteus.renderers.epub.covers import generate_cover_png_bytes


COVER_CSS_SUPPLEMENT = """
/* Proteus Cover Page Layout (Kindle Enhanced Typesetting) */
.cover-page {
  text-align: center;
  margin: 0;
  padding: 0;
  page-break-after: always;
  break-after: page;
}
.cover-image {
  max-width: 100%;
  max-height: 98vh;
  height: auto;
  display: block;
  margin: 0 auto;
}
"""


CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


@dataclass
class ManifestSpineItem:
    id: str
    filename: str
    title: str


@dataclass
class BookNavItem:
    index: int
    title: str
    intro_filename: str
    chapters: list[ManifestSpineItem] = field(default_factory=list)


class EpubBuilder:
    """Deterministic EPUB3 compiler powered by Jinja2."""

    def __init__(self) -> None:
        self.base_dir = Path(__file__).parent
        self.templates_dir = self.base_dir / "templates"
        self.styles_dir = self.base_dir / "styles"
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["xhtml", "xml", "j2"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def build(self, work: Work, output_path: Path) -> Path:
        """Compile a `Work` into a valid, deterministic EPUB3 archive at `output_path`."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Deterministic UUID v5 based on work.id
        uid = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_DNS, f'proteus.press.{work.id}')}"
        modified_timestamp = f"{work.publication_date}T00:00:00Z"

        cover_tpl = self.env.get_template("cover.xhtml.j2")
        titlepage_tpl = self.env.get_template("titlepage.xhtml.j2")
        book_intro_tpl = self.env.get_template("book_intro.xhtml.j2")
        chapter_tpl = self.env.get_template("chapter.xhtml.j2")
        nav_tpl = self.env.get_template("nav.xhtml.j2")
        ncx_tpl = self.env.get_template("toc.ncx.j2")
        opf_tpl = self.env.get_template("content.opf.j2")

        xhtml_files: dict[str, str] = {}
        manifest_items: list[ManifestSpineItem] = []
        front_matter_items: list[ManifestSpineItem] = []
        book_nav_items: list[BookNavItem] = []

        # 0. Cover Page & High-Resolution Cover PNG
        cover_png_bytes = generate_cover_png_bytes(work)
        cover_item = ManifestSpineItem(id="cover", filename="cover.xhtml", title="Cover")
        manifest_items.append(cover_item)
        xhtml_files[cover_item.filename] = cover_tpl.render(
            title=work.title,
            language=work.language,
            css_theme=work.css_theme,
        )

        # 1. Title Page
        tp_item = ManifestSpineItem(id="titlepage", filename="titlepage.xhtml", title="Title Page")
        manifest_items.append(tp_item)
        xhtml_files[tp_item.filename] = titlepage_tpl.render(
            title=work.title,
            subtitle=work.subtitle,
            edition_label=work.edition_label,
            authors=work.authors,
            description=work.description,
            publisher=work.publisher,
            publication_date=work.publication_date,
            language=work.language,
            css_theme=work.css_theme,
        )

        # 2. Volume-level Front Matter
        for fm_idx, fm_ch in enumerate(work.front_matter, start=1):
            fm_filename = f"fm_{fm_idx:02d}_{fm_ch.id}.xhtml"
            fm_item = ManifestSpineItem(
                id=f"fm-{fm_idx:02d}",
                filename=fm_filename,
                title=fm_ch.title,
            )
            manifest_items.append(fm_item)
            front_matter_items.append(fm_item)
            xhtml_files[fm_filename] = chapter_tpl.render(
                book_title=work.title,
                chapter=fm_ch,
                language=work.language,
                css_theme=work.css_theme,
            )

        # 3. Books & Chapters
        start_reading_href: str | None = None
        multi_book = len(work.books) > 1

        for bk_idx, book in enumerate(work.books, start=1):
            bk_chapters_nav: list[ManifestSpineItem] = []
            intro_filename: str | None = None

            if multi_book or book.heading or book.subtitle:
                intro_filename = f"bk_{bk_idx:02d}_intro.xhtml"
                intro_item = ManifestSpineItem(
                    id=f"bk-{bk_idx:02d}-intro",
                    filename=intro_filename,
                    title=book.title,
                )
                manifest_items.append(intro_item)
                if start_reading_href is None:
                    start_reading_href = intro_filename
                xhtml_files[intro_filename] = book_intro_tpl.render(
                    volume_title=work.title,
                    book=book,
                    language=work.language,
                    css_theme=work.css_theme,
                )

            # Book-specific front matter (e.g., Prefaces in an anthology book)
            for bfm_idx, bfm_ch in enumerate(book.front_matter, start=1):
                bfm_filename = f"bk_{bk_idx:02d}_fm_{bfm_idx:02d}.xhtml"
                bfm_item = ManifestSpineItem(
                    id=f"bk-{bk_idx:02d}-fm-{bfm_idx:02d}",
                    filename=bfm_filename,
                    title=bfm_ch.title,
                )
                manifest_items.append(bfm_item)
                bk_chapters_nav.append(bfm_item)
                if start_reading_href is None:
                    start_reading_href = bfm_filename
                xhtml_files[bfm_filename] = chapter_tpl.render(
                    book_title=book.title,
                    chapter=bfm_ch,
                    language=work.language,
                    css_theme=work.css_theme,
                )

            # Book body chapters
            for ch_idx, ch in enumerate(book.chapters, start=1):
                ch_filename = f"bk_{bk_idx:02d}_ch_{ch_idx:03d}.xhtml"
                ch_item = ManifestSpineItem(
                    id=f"bk-{bk_idx:02d}-ch-{ch_idx:03d}",
                    filename=ch_filename,
                    title=ch.title,
                )
                manifest_items.append(ch_item)
                bk_chapters_nav.append(ch_item)
                if start_reading_href is None:
                    start_reading_href = ch_filename
                xhtml_files[ch_filename] = chapter_tpl.render(
                    book_title=book.title,
                    chapter=ch,
                    language=work.language,
                    css_theme=work.css_theme,
                )

            if intro_filename is None and bk_chapters_nav:
                intro_filename = bk_chapters_nav[0].filename
                # Avoid duplicate child link if the book only has 1 chapter and no intro divider
                if len(bk_chapters_nav) == 1:
                    bk_chapters_nav = []

            if intro_filename:
                book_nav_items.append(
                    BookNavItem(
                        index=bk_idx,
                        title=book.title,
                        intro_filename=intro_filename,
                        chapters=bk_chapters_nav,
                    )
                )

        # 4. Render nav.xhtml, toc.ncx, and content.opf
        nav_xhtml = nav_tpl.render(
            title=work.title,
            language=work.language,
            css_theme=work.css_theme,
            front_matter_items=front_matter_items,
            book_nav_items=book_nav_items,
            start_reading_href=start_reading_href,
        )
        toc_ncx = ncx_tpl.render(
            uid=uid,
            title=work.title,
            front_matter_items=front_matter_items,
            book_nav_items=book_nav_items,
        )
        extra_image_entries: list[tuple[str, str]] = []
        for idx_img, img_fname in enumerate(sorted(work.images.keys()), start=1):
            extra_image_entries.append((f"fig-img-{idx_img:02d}", img_fname))

        content_opf = opf_tpl.render(
            uid=uid,
            title=work.title,
            subtitle=work.subtitle,
            language=work.language,
            authors=work.authors,
            publisher=work.publisher,
            publication_date=work.publication_date,
            rights=work.rights,
            description=work.description,
            subjects=work.subjects,
            modified_timestamp=modified_timestamp,
            css_theme=work.css_theme,
            extra_images=extra_image_entries,
            manifest_items=manifest_items,
            spine_items=manifest_items,
            start_reading_href=start_reading_href,
        )

        # 5. Read CSS stylesheet
        css_path = self.styles_dir / work.css_theme
        css_content = css_path.read_text(encoding="utf-8")
        if ".cover-page" not in css_content:
            css_content = css_content.rstrip() + "\n" + COVER_CSS_SUPPLEMENT

        # 6. Write deterministic EPUB3 ZIP archive
        with zipfile.ZipFile(output_path, "w") as zf:
            # Rule 1: `mimetype` MUST be the very first entry, uncompressed (`ZIP_STORED`), with no extra fields
            mimetype_info = zipfile.ZipInfo("mimetype", date_time=(2026, 10, 31, 0, 0, 0))
            mimetype_info.compress_type = zipfile.ZIP_STORED
            zf.writestr(mimetype_info, b"application/epub+zip")

            def _write_deflated(arcname: str, text_data: str) -> None:
                zinfo = zipfile.ZipInfo(arcname, date_time=(2026, 10, 31, 0, 0, 0))
                zinfo.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(zinfo, text_data.encode("utf-8"))

            def _write_binary(arcname: str, binary_data: bytes) -> None:
                zinfo = zipfile.ZipInfo(arcname, date_time=(2026, 10, 31, 0, 0, 0))
                zinfo.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(zinfo, binary_data)

            _write_deflated("META-INF/container.xml", CONTAINER_XML)
            _write_deflated("OEBPS/content.opf", content_opf)
            _write_deflated("OEBPS/nav.xhtml", nav_xhtml)
            _write_deflated("OEBPS/toc.ncx", toc_ncx)
            _write_deflated(f"OEBPS/styles/{work.css_theme}", css_content)
            _write_binary("OEBPS/images/cover.png", cover_png_bytes)
            for img_fname in sorted(work.images.keys()):
                _write_binary(f"OEBPS/images/{img_fname}", work.images[img_fname])

            for fname, xhtml_str in xhtml_files.items():
                _write_deflated(f"OEBPS/text/{fname}", xhtml_str)

        return output_path

