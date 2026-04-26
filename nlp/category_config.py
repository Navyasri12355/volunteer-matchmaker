"""
category_config.py
------------------
Single source of truth for event categories, their base severity weights,
allowed subtypes, and the one custom-subtype slot each NGO may define.

This module is imported by:
  - severity_engine.py  (category weight lookup)
  - event_nlp_extractor.py  (subtype tagging)
  - event_service.py  (validation of category/subtype combinations)
  - ngo_registration.py  (building the NGO's allowed-event allow-list)

Design decisions
~~~~~~~~~~~~~~~~
- Six fixed top-level categories (spec requirement).
- Each category has a curated list of built-in subtypes.
- Each NGO may register ONE custom subtype per category (stored in Firestore
  under their NGO doc).  custom_subtype is validated at event-creation time.
- Base weights reflect domain urgency; they are multiplied by the NLP score
  inside severity_engine.py — a strongly-worded education doc can still
  outscore a weak disaster_relief doc.
- ``allow_custom_subtype`` is True for all categories; set to False here if
  a category should be locked down in future.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EventCategory:
    key: str                          # snake_case identifier used in DB / API
    display_name: str
    base_weight: float                # in [0, 1] — higher = more urgent
    subtypes: List[str]               # built-in subtypes
    allow_custom_subtype: bool = True
    description: str = ""


# The six categories defined in the spec.
# Weights are calibrated against the severity_engine anchor phrases.
CATEGORIES: Dict[str, EventCategory] = {
    "disaster_relief": EventCategory(
        key="disaster_relief",
        display_name="Disaster Relief",
        base_weight=1.00,
        subtypes=[
            "flood",
            "earthquake",
            "cyclone",
            "landslide",
            "fire",
            "industrial_accident",
            "displacement",
            "search_and_rescue",
        ],
        description="Immediate response to natural or man-made disasters.",
    ),
    "water_and_sanitation": EventCategory(
        key="water_and_sanitation",
        display_name="Water & Sanitation",
        base_weight=0.90,
        subtypes=[
            "clean_water_access",
            "waterborne_disease_outbreak",
            "sanitation_infrastructure",
            "hygiene_promotion",
            "drought_response",
            "well_rehabilitation",
        ],
        description="Access to safe water, sanitation, and hygiene (WASH).",
    ),
    "food": EventCategory(
        key="food",
        display_name="Food Security",
        base_weight=0.85,
        subtypes=[
            "acute_malnutrition",
            "food_distribution",
            "community_kitchen",
            "agricultural_support",
            "school_feeding",
            "food_bank",
        ],
        description="Food security, nutrition, and hunger relief.",
    ),
    "education": EventCategory(
        key="education",
        display_name="Education",
        base_weight=0.55,
        subtypes=[
            "school_supplies_drive",
            "remedial_tutoring",
            "digital_literacy",
            "adult_literacy",
            "school_construction",
            "scholarship_support",
            "teacher_training",
        ],
        description="Access to quality education and learning resources.",
    ),
    "environment": EventCategory(
        key="environment",
        display_name="Environment",
        base_weight=0.50,
        subtypes=[
            "reforestation",
            "beach_cleanup",
            "river_cleanup",
            "waste_management",
            "urban_greening",
            "pollution_response",
            "biodiversity_conservation",
        ],
        description="Environmental conservation and restoration.",
    ),
    "animal_welfare": EventCategory(
        key="animal_welfare",
        display_name="Animal Welfare",
        base_weight=0.45,
        subtypes=[
            "rescue_and_rehabilitation",
            "stray_animal_care",
            "anti_poaching",
            "habitat_protection",
            "veterinary_camp",
            "adoption_drive",
        ],
        description="Care, rescue, and protection of animals.",
    ),
}

# Default weight for any NGO-registered custom category key not in CATEGORIES.
CUSTOM_CATEGORY_DEFAULT_WEIGHT: float = 0.60

# Maximum length for a custom subtype label (stored in Firestore).
CUSTOM_SUBTYPE_MAX_LENGTH: int = 64

# ---------------------------------------------------------------------------
# Helper: CategoryConfig  (wraps CATEGORIES + per-NGO custom subtypes)
# ---------------------------------------------------------------------------

@dataclass
class CategoryConfig:
    """
    Holds the full category + subtype configuration for a single NGO.

    Attributes
    ----------
    ngo_id          : Firestore NGO document ID.
    allowed_categories : List of category keys the NGO is permitted to use
                         (set at registration time by the NGO manager).
    custom_subtypes : Mapping of category_key → custom subtype label.
                      Max one entry per category.
    """

    ngo_id: str
    allowed_categories: List[str] = field(default_factory=lambda: list(CATEGORIES.keys()))
    custom_subtypes: Dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def is_category_allowed(self, category_key: str) -> bool:
        return category_key in self.allowed_categories

    def is_subtype_valid(self, category_key: str, subtype: str) -> bool:
        """Return True if the subtype is a built-in or the NGO's custom one."""
        cat = CATEGORIES.get(category_key)
        if cat is None:
            return False
        if subtype in cat.subtypes:
            return True
        custom = self.custom_subtypes.get(category_key)
        return custom is not None and subtype == custom

    def register_custom_subtype(self, category_key: str, label: str) -> None:
        """
        Register (or overwrite) the custom subtype for a category.
        Raises ValueError on invalid input.
        """
        if category_key not in CATEGORIES:
            raise ValueError(f"Unknown category: {category_key!r}")
        cat = CATEGORIES[category_key]
        if not cat.allow_custom_subtype:
            raise ValueError(f"Category {category_key!r} does not allow custom subtypes.")
        label = label.strip()
        if not label:
            raise ValueError("Custom subtype label cannot be empty.")
        if len(label) > CUSTOM_SUBTYPE_MAX_LENGTH:
            raise ValueError(
                f"Custom subtype label too long ({len(label)} > {CUSTOM_SUBTYPE_MAX_LENGTH} chars)."
            )
        if label.lower() in [s.lower() for s in cat.subtypes]:
            raise ValueError(
                f"{label!r} already exists as a built-in subtype for {category_key!r}."
            )
        self.custom_subtypes[category_key] = label

    def all_subtypes_for(self, category_key: str) -> List[str]:
        """Built-in subtypes + custom subtype (if registered)."""
        cat = CATEGORIES.get(category_key)
        if cat is None:
            return []
        subtypes = list(cat.subtypes)
        custom = self.custom_subtypes.get(category_key)
        if custom:
            subtypes.append(custom)
        return subtypes

    def get_base_weight(self, category_key: str) -> float:
        cat = CATEGORIES.get(category_key)
        return cat.base_weight if cat else CUSTOM_CATEGORY_DEFAULT_WEIGHT

    def to_firestore_dict(self) -> dict:
        """Serialise for storage in the NGO's Firestore document."""
        return {
            "ngo_id": self.ngo_id,
            "allowed_categories": self.allowed_categories,
            "custom_subtypes": self.custom_subtypes,
        }

    @classmethod
    def from_firestore_dict(cls, data: dict) -> "CategoryConfig":
        return cls(
            ngo_id=data["ngo_id"],
            allowed_categories=data.get("allowed_categories", list(CATEGORIES.keys())),
            custom_subtypes=data.get("custom_subtypes", {}),
        )
