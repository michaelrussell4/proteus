"""Proteus CLI — Command-Line Interface for Building, Normalizing, and Validating EPUB3 Editions."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable
import typer
from rich.console import Console
from rich.table import Table

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from proteus.core.models import Work
from proteus.ingest import (
    build_early_modern_english_quick_guide,
    build_early_modern_english_scripture_guide,
    ingest_bom_historical_edition,
    ingest_complete_apocrypha_and_pseudepigrapha_compendium,
    ingest_complete_lds_literature_compendium,
    ingest_foundational_lds_classics_anthology,
    ingest_kjv_apocrypha,
    ingest_patriarchs_and_prophets_apocrypha,
    ingest_standard_work,
)
from proteus.renderers.epub import EpubBuilder
from proteus.transforms import (
    build_enriched_book_of_mormon,
    build_historical_variants_bom,
    build_intertextual_parallels_edition,
    build_poetic_and_chiasmus_bom,
    build_top_1000_cited_verses_anthology,
    combine_works_into_quad,
    transform_to_continuous_narrative,
    transform_to_minimalist,
    transform_to_study_notebook,
)
from proteus.validation import validate_epub

app = typer.Typer(
    name="proteus",
    help="Proteus: Computational Text-Transformation & EPUB3 Publishing Pipeline (Kindle KFX / Enhanced Typesetting)",
    add_completion=False,
)
console = Console(legacy_windows=False)


EDITION_BUILDERS: dict[str, tuple[str, Callable[[], Work]]] = {
    # Phase 1 Targets
    "kjv-apocrypha": (
        "[Phase 1] The Complete KJV Apocrypha / Deuterocanon (15 books)",
        lambda: ingest_kjv_apocrypha(),
    ),
    "enoch-jubilees-jasher": (
        "[Phase 1] Enoch (Charles & Laurence), Jubilees & Jasher Omnibus (with pop-up footnotes)",
        lambda: ingest_patriarchs_and_prophets_apocrypha(),
    ),
    "lds-classics-anthology": (
        "[Phase 1] Foundational Classics of the Restoration (9-book doctrinal omnibus with pop-up notes)",
        lambda: ingest_foundational_lds_classics_anthology(),
    ),
    "complete-lds-literature-compendium": (
        "[Phase 1] The Complete Restoration Literature Compendium (All 71 Historical Books, 6.0M words)",
        lambda: ingest_complete_lds_literature_compendium(),
    ),
    "complete-apocrypha-pseudepigrapha-compendium": (
        "[Phase 1] The Complete Apocrypha & Pseudepigrapha Compendium (Deduplicated + Provenance Dossiers)",
        lambda: ingest_complete_apocrypha_and_pseudepigrapha_compendium(),
    ),
    "book-of-mormon-2013": (
        "[Phase 1] The Book of Mormon (2013 Standard Works Edition)",
        lambda: ingest_standard_work("book-of-mormon"),
    ),
    "book-of-mormon-1830": (
        "[Phase 1] The Book of Mormon (1830 Palmyra Historical Edition)",
        lambda: ingest_bom_historical_edition("1830"),
    ),
    "doctrine-and-covenants": (
        "[Phase 1] The Doctrine and Covenants (2013 Standard Works Edition)",
        lambda: ingest_standard_work("doctrine-and-covenants"),
    ),
    "pearl-of-great-price": (
        "[Phase 1] The Pearl of Great Price (2013 Standard Works Edition)",
        lambda: ingest_standard_work("pearl-of-great-price"),
    ),
    # Phase 2 Targets: Canonical Transformations & Structural Formatting
    "book-of-mormon-narrative": (
        "[Phase 2] The Book of Mormon (2013 Continuous Narrative Edition with pop-up verse ranges)",
        lambda: transform_to_continuous_narrative(
            ingest_standard_work("book-of-mormon"),
            edition_id_suffix="narrative",
            include_verse_range_popups=True,
        ),
    ),
    "book-of-mormon-1830-narrative": (
        "[Phase 2] The Book of Mormon (1830 Original Reader's Continuous Narrative Edition)",
        lambda: transform_to_continuous_narrative(
            ingest_bom_historical_edition("1830"),
            edition_id_suffix="narrative",
            include_verse_range_popups=True,
        ),
    ),
    "old-testament-minimalist": (
        "[Phase 2] The Old Testament (Clean chapters & verses, zero footnotes)",
        lambda: transform_to_minimalist(ingest_standard_work("old-testament")),
    ),
    "new-testament-minimalist": (
        "[Phase 2] The New Testament (Clean chapters & verses, zero footnotes)",
        lambda: transform_to_minimalist(ingest_standard_work("new-testament")),
    ),
    "book-of-mormon-minimalist": (
        "[Phase 2] The Book of Mormon (Clean chapters & verses, zero footnotes)",
        lambda: transform_to_minimalist(ingest_standard_work("book-of-mormon")),
    ),
    "doctrine-and-covenants-minimalist": (
        "[Phase 2] The Doctrine and Covenants (Clean sections & verses, zero footnotes)",
        lambda: transform_to_minimalist(ingest_standard_work("doctrine-and-covenants")),
    ),
    "pearl-of-great-price-minimalist": (
        "[Phase 2] The Pearl of Great Price (Clean chapters & verses, zero footnotes)",
        lambda: transform_to_minimalist(ingest_standard_work("pearl-of-great-price")),
    ),
    "lds-standard-works-minimalist": (
        "[Phase 2] The Complete LDS Standard Works Quad (OT + NT + BoM + D&C + PoGP)",
        lambda: combine_works_into_quad(
            [
                transform_to_minimalist(ingest_standard_work("old-testament")),
                transform_to_minimalist(ingest_standard_work("new-testament")),
                transform_to_minimalist(ingest_standard_work("book-of-mormon")),
                transform_to_minimalist(ingest_standard_work("doctrine-and-covenants")),
                transform_to_minimalist(ingest_standard_work("pearl-of-great-price")),
            ]
        ),
    ),
    "new-testament-narrative": (
        "[Phase 2] The New Testament (KJV Continuous Narrative Reader's Edition with pop-up verse ranges)",
        lambda: transform_to_continuous_narrative(
            ingest_standard_work("new-testament"),
            edition_id_suffix="narrative",
            include_verse_range_popups=True,
        ),
    ),
    "book-of-mormon-study-notebook": (
        "[Phase 2] The Book of Mormon (Wide-Margin Study & Annotation Edition)",
        lambda: transform_to_study_notebook(ingest_standard_work("book-of-mormon")),
    ),
    # Phase 3 Targets: Enriched & Relational Compilations
    "top-1000-cited-verses": (
        "[Phase 3] The Top 1,000 Cited Verses of the Restoration (1830–1886 Public-Domain Ranked Anthology)",
        lambda: build_top_1000_cited_verses_anthology(),
    ),
    "book-of-mormon-onomasticon": (
        "[Phase 3] The Book of Mormon Onomasticon Study Reader (◈ Etymology & IPA Pop-ups)",
        lambda: build_enriched_book_of_mormon(
            enable_divine_speech=False,
            enable_onomasticon=True,
            enable_citations=False,
            custom_id="book-of-mormon-onomasticon",
            custom_title="The Book of Mormon (Onomasticon Lexical Study Edition)",
            custom_subtitle="With Interactive BYU Onomasticon Etymologies, IPA Pronunciations & Ancient Reconstructions",
            custom_edition_label="Proteus Onomasticon Study Reader",
        ),
    ),
    "book-of-mormon-master-study": (
        "[Phase 3] The Master Study Book of Mormon (◈ Onomasticon + [★] Historical Citations)",
        lambda: build_enriched_book_of_mormon(
            enable_divine_speech=False,
            enable_onomasticon=True,
            enable_citations=True,
            custom_id="book-of-mormon-master-study",
            custom_title="The Book of Mormon (Master Relational Study Edition)",
            custom_subtitle="Uniting BYU Onomasticon Etymologies (◈) and 19th-Century Discourse Citations ([★])",
            custom_edition_label="Proteus Relational Master Study Edition",
        ),
    ),
    # Phase 4 Targets: Advanced NLP, Historical Variants, Intertextual Parallels & Poetics
    "book-of-mormon-historical-variants": (
        "[Phase 4] The Historical Textual Variants Book of Mormon (1830–2013 8-Edition Collation)",
        lambda: build_historical_variants_bom(),
    ),
    "bom-intertextual-parallels": (
        "[Phase 4] Book of Mormon Intertextual Parallels (BoM Isaiah vs KJV & 3 Nephi vs Matthew)",
        lambda: build_intertextual_parallels_edition(),
    ),
    "bom-poetic-and-chiasmus": (
        "[Phase 4] The Book of Mormon: Poetic & Chiasmus Study Edition (Alma 36, Psalms & Parallelisms)",
        lambda: build_poetic_and_chiasmus_bom(),
    ),
    "early-modern-english-scripture-guide": (
        "[Phase 4] An Early Modern English Guide to Reading the Scriptures (KJV & Book of Mormon Companion)",
        lambda: build_early_modern_english_scripture_guide(),
    ),
    "early-modern-english-quick-guide": (
        "[Phase 4] Reading Old English Scripture: A Plain-Language Quick Guide (thou/ye, -eth, old words)",
        lambda: build_early_modern_english_quick_guide(),
    ),
}

PHASE1_TARGETS = [
    "kjv-apocrypha",
    "enoch-jubilees-jasher",
    "lds-classics-anthology",
    "complete-lds-literature-compendium",
    "complete-apocrypha-pseudepigrapha-compendium",
]
PHASE2_TARGETS = [
    "book-of-mormon-narrative",
    "book-of-mormon-1830-narrative",
    "old-testament-minimalist",
    "new-testament-minimalist",
    "book-of-mormon-minimalist",
    "doctrine-and-covenants-minimalist",
    "pearl-of-great-price-minimalist",
    "lds-standard-works-minimalist",
    "new-testament-narrative",
    "book-of-mormon-study-notebook",
]
PHASE3_TARGETS = [
    "top-1000-cited-verses",
    "book-of-mormon-onomasticon",
    "book-of-mormon-master-study",
]
PHASE4_TARGETS = [
    "book-of-mormon-historical-variants",
    "bom-intertextual-parallels",
    "bom-poetic-and-chiasmus",
    "early-modern-english-scripture-guide",
    "early-modern-english-quick-guide",
]


@app.command("list")
def list_editions() -> None:
    """List all registered EPUB3 editions available to build."""
    table = Table(title="Proteus Registered EPUB3 Build Targets")
    table.add_column("Target ID", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    for tid, (desc, _) in EDITION_BUILDERS.items():
        table.add_row(tid, desc)
    console.print(table)


@app.command("build")
def build_editions(
    target: str = typer.Argument(
        "phase4",
        help="Target ID to build ('phase1', 'phase2', 'phase3', 'phase4', 'all', or a specific ID)",
    ),
    out_dir: Path = typer.Option(Path("dist/epubs"), "--out-dir", "-o", help="Output directory for compiled EPUBs"),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="Run lxml & W3C epubcheck validation"),
) -> None:
    """Compile one or more normalized works into Kindle Paperwhite-ready EPUB3 volumes."""
    if target == "phase1":
        targets = PHASE1_TARGETS
    elif target == "phase2":
        targets = PHASE2_TARGETS
    elif target == "phase3":
        targets = PHASE3_TARGETS
    elif target == "phase4":
        targets = PHASE4_TARGETS
    elif target == "all":
        targets = list(EDITION_BUILDERS.keys())
    elif target in EDITION_BUILDERS:
        targets = [target]
    else:
        console.print(f"[red]Unknown target '{target}'. Run 'proteus list' to see valid targets.[/red]")
        raise typer.Exit(code=1)

    builder = EpubBuilder()
    summary_table = Table(title="Proteus EPUB3 Build & Validation Report")
    summary_table.add_column("Edition ID", style="cyan")
    summary_table.add_column("Books", justify="right")
    summary_table.add_column("Chapters", justify="right")
    summary_table.add_column("Words", justify="right")
    summary_table.add_column("Pop-up Notes", justify="right")
    summary_table.add_column("EPUB Size", justify="right")
    summary_table.add_column("Validation", style="bold")

    any_failed = False

    for tid in targets:
        desc, loader = EDITION_BUILDERS[tid]
        console.print(f"\n[bold blue]-> Ingesting & Transforming:[/bold blue] {tid} ({desc})")
        work = loader()
        epub_path = out_dir / f"{work.id}.epub"

        console.print(f"[bold blue]-> Packaging EPUB3:[/bold blue] {epub_path}")
        builder.build(work, epub_path)
        size_kb = epub_path.stat().st_size / 1024.0

        status_str = "SKIPPED"
        popup_cnt = sum(
            len(c.annotations)
            for b in work.books
            for c in (b.front_matter + b.chapters)
        )

        if validate:
            console.print(f"[bold blue]-> Validating with lxml + W3C epubcheck:[/bold blue] {epub_path.name}")
            vres = validate_epub(epub_path, run_official_epubcheck=True)
            popup_cnt = vres.popup_footnotes_verified
            if vres.passed:
                ec_tag = " + epubcheck 5.3" if vres.epubcheck_ran else ""
                status_str = f"[green]PASSED ({vres.xhtml_files_checked} XHTML{ec_tag})[/green]"
            else:
                any_failed = True
                status_str = f"[red]FAILED ({len(vres.errors)} errors)[/red]"
                for err in vres.errors[:15]:
                    console.print(f"  [red]* {err}[/red]")

        summary_table.add_row(
            work.id,
            str(len(work.books)),
            f"{work.total_chapters:,}",
            f"{work.total_words:,}",
            f"{popup_cnt:,}",
            f"{size_kb:,.1f} KB",
            status_str,
        )

    console.print("\n")
    console.print(summary_table)
    if any_failed:
        raise typer.Exit(code=1)


@app.command("validate")
def validate_command(
    epub_path: Path = typer.Argument(..., help="Path to an .epub file or directory of .epub files"),
) -> None:
    """Validate an existing EPUB3 file or directory using native lxml checks and W3C epubcheck."""
    paths = sorted(epub_path.glob("*.epub")) if epub_path.is_dir() else [epub_path]
    any_failed = False
    for p in paths:
        res = validate_epub(p, run_official_epubcheck=True)
        if res.passed:
            console.print(
                f"[green][PASS] {p.name}[/green] "
                f"({res.xhtml_files_checked} XHTML files, {res.popup_footnotes_verified} pop-up footnotes, "
                f"epubcheck={res.epubcheck_ran})"
            )
        else:
            any_failed = True
            console.print(f"[red][FAIL] {p.name} ({len(res.errors)} errors)[/red]")
            for err in res.errors:
                console.print(f"  [red]- {err}[/red]")
    if any_failed:
        raise typer.Exit(code=1)
