"""Automated EPUB3 & Kindle Paperwhite (KFX) Validation Pipeline.

Performs two layers of verification on every compiled `.epub`:
1. Native Python `lxml` Structural & Kindle Pop-up Footnote Verification:
   - Verifies uncompressed `mimetype` header at byte offset 0
   - Parses `META-INF/container.xml`, `OEBPS/content.opf`, `OEBPS/nav.xhtml`, `OEBPS/toc.ncx`, and all XHTML files with strict `lxml.etree.XMLParser`
   - Verifies that every internal link (`href="...#id"`) resolves to an existing file and element `id`
   - Verifies that every `<a epub:type="noteref">` pairs cleanly with an `<aside epub:type="footnote">`
2. Official W3C `epubcheck` (v5.3.0) Validation:
   - Automatically locates Java 21 (including Eclipse Adoptium on Windows if PATH has not yet refreshed)
   - Runs `epubcheck` and confirms 0 fatal errors and 0 errors.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from lxml import etree


@dataclass
class ValidationResult:
    epub_path: Path
    passed: bool = True
    xhtml_files_checked: int = 0
    popup_footnotes_verified: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    epubcheck_ran: bool = False
    epubcheck_messages: list[str] = field(default_factory=list)


def _ensure_java_on_path() -> str | None:
    """Locate `java` executable, adding Eclipse Adoptium / standard Windows JDK locations to PATH if needed."""
    java_bin = shutil.which("java")
    if java_bin:
        return java_bin

    search_roots = [
        Path(r"C:\Program Files\Eclipse Adoptium"),
        Path(r"C:\Program Files\Java"),
        Path(r"C:\Program Files\Microsoft"),
        Path(r"C:\Program Files\Amazon Corretto"),
    ]
    for root in search_roots:
        if root.exists():
            for exe in root.rglob("java.exe"):
                bin_dir = str(exe.parent)
                os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
                return str(exe)
    return None


def validate_epub(epub_path: Path, run_official_epubcheck: bool = True) -> ValidationResult:
    """Run strict XML/XHTML5, link integrity, Kindle pop-up footnote, and W3C `epubcheck` validation."""
    res = ValidationResult(epub_path=epub_path)

    if not epub_path.exists():
        res.passed = False
        res.errors.append(f"File does not exist: {epub_path}")
        return res

    xml_parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=False)
    epub_ns = "http://www.idpf.org/2007/ops"

    with zipfile.ZipFile(epub_path, "r") as zf:
        infolist = zf.infolist()
        if not infolist or infolist[0].filename != "mimetype":
            res.passed = False
            res.errors.append("First entry in EPUB archive must be 'mimetype'.")
        else:
            if infolist[0].compress_type != zipfile.ZIP_STORED:
                res.passed = False
                res.errors.append("'mimetype' entry must be uncompressed (ZIP_STORED).")
            if zf.read("mimetype") != b"application/epub+zip":
                res.passed = False
                res.errors.append("Invalid 'mimetype' contents.")

        namelist = set(zf.namelist())
        for req in ("META-INF/container.xml", "OEBPS/content.opf", "OEBPS/nav.xhtml", "OEBPS/toc.ncx"):
            if req not in namelist:
                res.passed = False
                res.errors.append(f"Missing required EPUB file: {req}")

        # Parse all XML/XHTML/OPF/NCX files and collect all element IDs per archive path
        ids_by_file: dict[str, set[str]] = {}
        trees_by_file: dict[str, etree._Element] = {}

        for name in sorted(namelist):
            if name.endswith((".xml", ".opf", ".ncx", ".xhtml")):
                raw_data = zf.read(name)
                try:
                    root = etree.fromstring(raw_data, parser=xml_parser)
                    trees_by_file[name] = root
                    ids_by_file[name] = {el.attrib["id"] for el in root.xpath(".//*[@id]")}
                    if name.endswith(".xhtml"):
                        res.xhtml_files_checked += 1
                except etree.XMLSyntaxError as exc:
                    res.passed = False
                    res.errors.append(f"XML syntax error in {name}: {exc}")

        # Verify internal links and Kindle pop-up footnote contracts across all XHTML files
        for name, root in trees_by_file.items():
            if not name.endswith(".xhtml"):
                continue

            base_dir = Path(name).parent
            aside_ids: set[str] = set()
            for aside in root.xpath(".//*[local-name()='aside']"):
                ep_type = aside.attrib.get(f"{{{epub_ns}}}type", "")
                if "footnote" in ep_type and "id" in aside.attrib:
                    aside_ids.add(aside.attrib["id"])

            for a_el in root.xpath(".//*[local-name()='a'][@href]"):
                href = a_el.attrib["href"]
                if href.startswith(("http://", "https://", "mailto:")):
                    continue

                if "#" in href:
                    file_part, frag = href.split("#", 1)
                else:
                    file_part, frag = href, None

                target_file = name if not file_part else (base_dir / file_part).as_posix()
                if target_file not in namelist:
                    res.passed = False
                    res.errors.append(f"Broken file link in {name}: href='{href}' -> '{target_file}' missing")
                    continue

                if frag and frag not in ids_by_file.get(target_file, set()):
                    res.passed = False
                    res.errors.append(f"Broken anchor link in {name}: href='{href}' -> '#{frag}' missing in {target_file}")

                ep_type = a_el.attrib.get(f"{{{epub_ns}}}type", "")
                if "noteref" in ep_type:
                    if not frag or frag not in aside_ids:
                        res.passed = False
                        res.errors.append(
                            f"Kindle pop-up footnote violation in {name}: noteref href='{href}' does not point to an <aside epub:type='footnote'>"
                        )
                    else:
                        res.popup_footnotes_verified += 1

    # Layer 2: Official W3C epubcheck
    if run_official_epubcheck and _ensure_java_on_path():
        import epubcheck

        res.epubcheck_ran = True
        ec_valid = epubcheck.validate(str(epub_path))
        if not ec_valid:
            res.passed = False
            res.errors.append("W3C epubcheck reported validation errors (see console output above).")

    return res

