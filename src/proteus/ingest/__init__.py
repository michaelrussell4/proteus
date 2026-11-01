"""Ingesters for all upstream raw corpora."""

from proteus.ingest.apocrypha import (
    ingest_kjv_apocrypha,
    ingest_patriarchs_and_prophets_apocrypha,
)
from proteus.ingest.apocrypha_compendium import (
    ingest_complete_apocrypha_and_pseudepigrapha_compendium,
)
from proteus.ingest.early_modern_english import (
    build_early_modern_english_scripture_guide,
    ingest_early_modern_english_guide,
)
from proteus.ingest.eme_quick_guide import (
    build_early_modern_english_quick_guide,
    ingest_early_modern_english_quick_guide,
)
from proteus.ingest.lds_literature import (
    ingest_complete_lds_literature_compendium,
    ingest_foundational_lds_classics_anthology,
    ingest_lds_classic_book,
)
from proteus.ingest.standard_works import (
    ingest_bom_historical_edition,
    ingest_standard_work,
)

__all__ = [
    "build_early_modern_english_quick_guide",
    "build_early_modern_english_scripture_guide",
    "ingest_early_modern_english_quick_guide",
    "ingest_bom_historical_edition",
    "ingest_complete_apocrypha_and_pseudepigrapha_compendium",
    "ingest_complete_lds_literature_compendium",
    "ingest_early_modern_english_guide",
    "ingest_foundational_lds_classics_anthology",
    "ingest_kjv_apocrypha",
    "ingest_lds_classic_book",
    "ingest_patriarchs_and_prophets_apocrypha",
    "ingest_standard_work",
]

