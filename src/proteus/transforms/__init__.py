"""Text transformation filters and edition pipelines for Proteus."""

from proteus.transforms.datascience import (
    build_data_science_standard_works,
)
from proteus.transforms.diffs import (
    build_historical_variants_bom,
    build_intertextual_parallels_edition,
)
from proteus.transforms.enrichers import (
    build_enriched_book_of_mormon,
    build_top_1000_cited_verses_anthology,
)
__all__ = [
    "build_data_science_standard_works",
    "build_enriched_book_of_mormon",
    "build_historical_variants_bom",
    "build_intertextual_parallels_edition",
    "build_top_1000_cited_verses_anthology",
]
