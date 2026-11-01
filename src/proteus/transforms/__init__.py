"""Text transformation filters and edition pipelines for Proteus."""

from proteus.transforms.diffs import (
    build_historical_variants_bom,
    build_intertextual_parallels_edition,
    build_poetic_and_chiasmus_bom,
)
from proteus.transforms.enrichers import (
    build_enriched_book_of_mormon,
    build_top_1000_cited_verses_anthology,
)
from proteus.transforms.narrative import (
    combine_works_into_quad,
    transform_to_continuous_narrative,
    transform_to_minimalist,
    transform_to_study_notebook,
)

__all__ = [
    "build_enriched_book_of_mormon",
    "build_historical_variants_bom",
    "build_intertextual_parallels_edition",
    "build_poetic_and_chiasmus_bom",
    "build_top_1000_cited_verses_anthology",
    "combine_works_into_quad",
    "transform_to_continuous_narrative",
    "transform_to_minimalist",
    "transform_to_study_notebook",
]
