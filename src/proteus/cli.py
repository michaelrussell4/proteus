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
    build_early_modern_english_scripture_guide,
    ingest_bom_historical_edition,
    ingest_complete_apocrypha_and_pseudepigrapha_compendium,
    ingest_complete_lds_literature_compendium,
    ingest_foundational_lds_classics_anthology,
    ingest_kjv_apocrypha,
    ingest_patriarchs_and_prophets_apocrypha,
    ingest_pseudepigrapha,
    ingest_standard_work,
)
from proteus.renderers.epub import EpubBuilder
from proteus.transforms import (
    build_data_science_standard_works,
    build_enriched_book_of_mormon,
    build_historical_variants_bom,
    build_intertextual_parallels_edition,
    build_master_study_book_of_mormon,
    build_master_study_doctrine_and_covenants,
    build_master_study_new_testament,
    build_master_study_old_testament,
    build_master_study_pearl_of_great_price,
    build_master_study_standard_works,
    build_narrative_book_of_mormon,
    build_narrative_doctrine_and_covenants,
    build_narrative_new_testament,
    build_narrative_old_testament,
    build_narrative_pearl_of_great_price,
    build_narrative_standard_works,
    build_top_1000_cited_verses_anthology,
)
from proteus.validation import validate_epub

app = typer.Typer(
    name="proteus",
    help="Proteus: Computational Text-Transformation & EPUB3 Publishing Pipeline (Kindle KFX / Enhanced Typesetting)",
    add_completion=False,
)
console = Console(legacy_windows=False)


EDITION_BUILDERS: dict[str, tuple[str, Callable[[], Work]]] = {
    # Phase 1: Canonical Editions & Historical Printings
    "old-testament": (
        "[Phase 1] The Old Testament (2013 KJV Standard Works Edition)",
        lambda: ingest_standard_work("old-testament"),
    ),
    "new-testament": (
        "[Phase 1] The New Testament (2013 KJV Standard Works Edition)",
        lambda: ingest_standard_work("new-testament"),
    ),
    "book-of-mormon": (
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
    # Phase 2: Apocrypha, Ancient Texts & Restoration Literature
    "kjv-apocrypha": (
        "[Phase 2] The Complete KJV Apocrypha / Deuterocanon (15 books)",
        lambda: ingest_kjv_apocrypha(),
    ),
    "pseudepigrapha": (
        "[Phase 2] The Complete Pseudepigrapha (30 OT Pseudepigrapha, Enochic, Patriarchal & Second Temple Works)",
        lambda: ingest_pseudepigrapha(),
    ),
    "enoch-jubilees-jasher": (
        "[Phase 2] Enoch (Charles & Laurence), Jubilees & Jasher Omnibus (with pop-up footnotes)",
        lambda: ingest_patriarchs_and_prophets_apocrypha(),
    ),
    "complete-apocrypha-pseudepigrapha-compendium": (
        "[Phase 2] The Complete Apocrypha & Pseudepigrapha Compendium (Deduplicated + Provenance Dossiers)",
        lambda: ingest_complete_apocrypha_and_pseudepigrapha_compendium(),
    ),
    "foundational-lds-classics-anthology": (
        "[Phase 2] Foundational Classics of the Restoration (9-book doctrinal omnibus with pop-up notes)",
        lambda: ingest_foundational_lds_classics_anthology(),
    ),
    "complete-lds-literature-compendium": (
        "[Phase 2] The Complete Restoration Literature Compendium (All 71 Historical Books, 6.0M words)",
        lambda: ingest_complete_lds_literature_compendium(),
    ),
    # Phase 3: Relational, Historical Variants & Citations
    "old-testament-master-study": (
        "[Master Study] The Old Testament (BSB • ASV • BBE Parallel Translations + Citations)",
        lambda: build_master_study_old_testament(),
    ),
    "new-testament-master-study": (
        "[Master Study] The New Testament (BSB • ASV • BBE Parallel Translations + Citations)",
        lambda: build_master_study_new_testament(),
    ),
    "book-of-mormon-master-study": (
        "[Master Study] The Book of Mormon (◈ Onomasticon + [★] Historical Citations)",
        lambda: build_master_study_book_of_mormon(),
    ),
    "doctrine-and-covenants-master-study": (
        "[Master Study] The Doctrine and Covenants (◈ Onomasticon + [★] Historical Citations)",
        lambda: build_master_study_doctrine_and_covenants(),
    ),
    "pearl-of-great-price-master-study": (
        "[Master Study] The Pearl of Great Price (◈ Onomasticon [Kolob, Egyptus] + [★] Citations)",
        lambda: build_master_study_pearl_of_great_price(),
    ),
    "lds-standard-works-master-study": (
        "[Master Study] The Complete Standard Works (Parallel Bible, Onomasticon & Citations)",
        lambda: build_master_study_standard_works(),
    ),
    "top-1000-cited-verses": (
        "[Phase 3] The Top 1,000 Cited Verses of the Restoration (1830–1886 Public-Domain Ranked Anthology)",
        lambda: build_top_1000_cited_verses_anthology(),
    ),
    "book-of-mormon-historical-variants": (
        "[Phase 3] The Historical Textual Variants Book of Mormon (1830–2013 8-Edition Collation)",
        lambda: build_historical_variants_bom(),
    ),
    "bom-intertextual-parallels": (
        "[Phase 3] Book of Mormon Intertextual Parallels (BoM Isaiah vs KJV & 3 Nephi vs Matthew)",
        lambda: build_intertextual_parallels_edition(),
    ),
    # Phase 4: Philology & Data Science
    "early-modern-english-scripture-guide": (
        "[Phase 4] An Early Modern English Guide to Reading the Scriptures (KJV & Book of Mormon Companion)",
        lambda: build_early_modern_english_scripture_guide(),
    ),
    "lds-standard-works-data-science": (
        "[Phase 4] The Data Science Standard Works (NLP, NER Geo/Names, ★1× Hapax Legomena, Charts & Indexes)",
        lambda: build_data_science_standard_works(),
    ),
    # Narrative Editions
    "old-testament-narrative": (
        "[Narrative] The Old Testament (Narrative Edition — Flowing Paragraph Prose)",
        lambda: build_narrative_old_testament(),
    ),
    "new-testament-narrative": (
        "[Narrative] The New Testament (Narrative Edition — Flowing Paragraph Prose)",
        lambda: build_narrative_new_testament(),
    ),
    "book-of-mormon-narrative": (
        "[Narrative] The Book of Mormon (Narrative Edition — Flowing Paragraph Prose)",
        lambda: build_narrative_book_of_mormon(),
    ),
    "doctrine-and-covenants-narrative": (
        "[Narrative] The Doctrine and Covenants (Narrative Edition — Flowing Paragraph Prose)",
        lambda: build_narrative_doctrine_and_covenants(),
    ),
    "pearl-of-great-price-narrative": (
        "[Narrative] The Pearl of Great Price (Narrative Edition — Flowing Paragraph Prose)",
        lambda: build_narrative_pearl_of_great_price(),
    ),
    "lds-standard-works-narrative": (
        "[Narrative] The Standard Works (Narrative Edition — All 5 Canonical Volumes)",
        lambda: build_narrative_standard_works(),
    ),
}

PHASE1_TARGETS = [
    "old-testament",
    "new-testament",
    "book-of-mormon",
    "book-of-mormon-1830",
    "doctrine-and-covenants",
    "pearl-of-great-price",
]
PHASE2_TARGETS = [
    "kjv-apocrypha",
    "pseudepigrapha",
    "enoch-jubilees-jasher",
    "complete-apocrypha-pseudepigrapha-compendium",
    "foundational-lds-classics-anthology",
    "complete-lds-literature-compendium",
]
PHASE3_TARGETS = [
    "book-of-mormon-master-study",
    "top-1000-cited-verses",
    "book-of-mormon-historical-variants",
    "bom-intertextual-parallels",
]
MASTER_STUDY_TARGETS = [
    "old-testament-master-study",
    "new-testament-master-study",
    "book-of-mormon-master-study",
    "doctrine-and-covenants-master-study",
    "pearl-of-great-price-master-study",
    "lds-standard-works-master-study",
]
PHASE4_TARGETS = [
    "early-modern-english-scripture-guide",
    "lds-standard-works-data-science",
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
        help="Target ID to build ('phase1', 'phase2', 'phase3', 'phase4', 'master-study', 'all', or a specific ID)",
    ),
    out_dir: Path = typer.Option(Path("dist/epubs"), "--out-dir", "-o", help="Output directory for compiled EPUBs"),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="Run lxml & W3C epubcheck validation"),
) -> None:
    """Compile one or more normalized works into Kindle Paperwhite-ready EPUB3 volumes."""
    if target == "lds-classics-anthology":
        target = "foundational-lds-classics-anthology"
    if target == "phase1":
        targets = PHASE1_TARGETS
    elif target == "phase2":
        targets = PHASE2_TARGETS
    elif target == "phase3":
        targets = PHASE3_TARGETS
    elif target in ("master-study", "master_study", "masterstudy"):
        targets = MASTER_STUDY_TARGETS
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
