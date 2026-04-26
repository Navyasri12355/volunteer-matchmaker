from __future__ import annotations

import pytest

from backend.nlp.category_config import CATEGORIES, CategoryConfig, CUSTOM_CATEGORY_DEFAULT_WEIGHT


def test_category_config_validates_and_registers_custom_subtype() -> None:
    cfg = CategoryConfig(ngo_id="ngo-1")
    cfg.register_custom_subtype("food", "community_fridge_drive")

    assert cfg.is_subtype_valid("food", "community_fridge_drive") is True
    assert "community_fridge_drive" in cfg.all_subtypes_for("food")


def test_category_config_rejects_builtin_duplicate_custom_subtype() -> None:
    cfg = CategoryConfig(ngo_id="ngo-2")
    builtin = CATEGORIES["food"].subtypes[0]

    with pytest.raises(ValueError, match="already exists as a built-in subtype"):
        cfg.register_custom_subtype("food", builtin)


def test_get_base_weight_for_unknown_category_uses_default() -> None:
    cfg = CategoryConfig(ngo_id="ngo-3")
    assert cfg.get_base_weight("unknown_key") == CUSTOM_CATEGORY_DEFAULT_WEIGHT
