"""ADR-014 Lot 1 — Tests: SWC Taxonomy."""
import pytest

from services.audit.swc_taxonomy import (
    SWCEntry,
    SWC_REGISTRY,
    TOB_CLASSES,
    TOB_4LEVEL,
    SWC_5LEVEL,
    get_swc,
    get_swc_by_tob_class,
    map_severity_5to4,
    map_severity_4to5,
)


def test_all_entries_have_valid_tob_class():
    for entry in SWC_REGISTRY.values():
        assert entry.tob_class in TOB_CLASSES, (
            f"{entry.swc_id} has invalid tob_class: {entry.tob_class!r}"
        )


def test_all_entries_have_valid_severity_default():
    for entry in SWC_REGISTRY.values():
        assert entry.severity_default in TOB_4LEVEL, (
            f"{entry.swc_id} has invalid severity_default: {entry.severity_default!r}"
        )


def test_registry_has_minimum_entries():
    assert len(SWC_REGISTRY) >= 33


def test_get_swc_reentrancy_title():
    entry = get_swc("SWC-107")
    assert entry is not None
    assert entry.title == "Reentrancy"


def test_get_swc_reentrancy_severity():
    entry = get_swc("SWC-107")
    assert entry is not None
    assert entry.severity_default == "high"


def test_get_swc_by_tob_class_contains_reentrancy():
    entries = get_swc_by_tob_class("undefined_behavior")
    ids = [e.swc_id for e in entries]
    assert "SWC-107" in ids


def test_map_severity_5to4_critical_becomes_high():
    assert map_severity_5to4("critical") == "high"


def test_map_severity_5to4_identity_for_others():
    for level in ["high", "medium", "low", "informational"]:
        assert map_severity_5to4(level) == level


def test_map_severity_4to5_no_upgrade_to_critical():
    assert map_severity_4to5("high") == "high"


def test_map_severity_4to5_identity():
    for level in TOB_4LEVEL:
        assert map_severity_4to5(level) == level


def test_swc_entry_is_frozen():
    entry = get_swc("SWC-107")
    assert entry is not None
    with pytest.raises((AttributeError, TypeError)):
        entry.title = "Modified"  # type: ignore[misc]


def test_get_swc_unknown_returns_none():
    assert get_swc("SWC-999") is None
