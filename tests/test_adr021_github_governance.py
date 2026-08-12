"""ADR-021 regression tests for Git-governed attestation promotion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from services.esmm.attestation import ModelVote, Signature5D, crystallize
from services.governance.proposal import (
    AttestationProposal,
    EvidenceReference,
    build_attestation_proposal,
)
from services.metrology import PREDEFINED_FRAMES, create_general_knowledge_frame


def _attestation(frame: str | None = "general_knowledge_v1.0"):
    votes = [
        ModelVote(
            model_id="model-a",
            provider_id="provider-a",
            agreed=True,
            confidence=0.8,
        ),
        ModelVote(
            model_id="model-b",
            provider_id="provider-b",
            agreed=True,
            confidence=0.75,
        ),
    ]
    attestation = crystallize(
        subject="EPP",
        predicate="uses_governance_boundary",
        object_="Git pull requests",
        consensus_score=0.8,
        model_votes=votes,
        signature_5d=Signature5D(
            agreement=1.0,
            semantic_consistency=0.8,
            centrality=0.4,
            stability=0.7,
            relation_diversity=0.5,
        ),
        epistemic_type="foundational",
        metrological_frame=frame,
        architecture_families=2,
    )
    attestation.timestamp = 1_800_000_000.0
    return attestation


def _evidence() -> tuple[EvidenceReference, EvidenceReference]:
    return (
        EvidenceReference(
            kind="test_report",
            location="reports/adr-021-tests.txt",
            sha256="b" * 64,
            description="CI test report",
        ),
        EvidenceReference(
            kind="source",
            location="evidence/source.json",
            sha256="a" * 64,
        ),
    )


def test_core_callers_do_not_import_solana_metrology() -> None:
    """Core execution and storage must not depend on the Solana namespace."""
    for relative_path in (
        "services/esmm/pipeline.py",
        "database/engine.py",
        "cli/epp_cli.py",
    ):
        source = Path(relative_path).read_text(encoding="utf-8")
        assert "services.solana.metrological_frame" not in source, relative_path


def test_legacy_metrology_import_is_a_compatible_shim() -> None:
    """Existing integrations retain the old import path without forked logic."""
    from services.metrology import MetrologicalFrame
    from services.solana.metrological_frame import (
        PREDEFINED_FRAMES as LEGACY_PREDEFINED_FRAMES,
    )
    from services.solana.metrological_frame import (
        MetrologicalFrame as LegacyMetrologicalFrame,
    )
    from services.solana.metrological_frame import (
        create_general_knowledge_frame as legacy_factory,
    )

    assert LegacyMetrologicalFrame is MetrologicalFrame
    assert LEGACY_PREDEFINED_FRAMES is PREDEFINED_FRAMES
    assert (
        legacy_factory().compute_frame_hash()
        == create_general_knowledge_frame().compute_frame_hash()
    )


def test_predefined_frame_hashes_survive_namespace_move() -> None:
    """Published methodology identities must not change during decoupling."""
    expected = {
        "blockchain_tps_v1.0": "fdb76792966ca99ccf9a73964535be3228cd234773c36c6d84ae7ebb474b8459",
        "general_knowledge_v1.0": "9b21b6032950fc022f481a28f57a3dbb0dc9fdba7c8c7c2b55d6131ee3514d50",
        "compliance_sanctions_v1.0": "98722151acd726f9d6c6ff8bcb72411bd0c7bf7519e83c577181b16c57bbced3",
        "carbon_credits_vcs_v1.0": "e7f09254296100d4985d137e8e67e32af26a073ee27352ddcc1096688d14bb9b",
        "rwa_identity_v1.0": "2a9db1c5d0691ea0ca5d4444e879cb3fac52da84b2c38a227fdde1d3438b4fc9",
        "smartcontract_audit_v1.0": "e0f063879a9b21926d9c0f259b97dd7439b7929b56111a15f6d4c1977c509c4f",
        "geopolitical_forecast_v1.0": "f05f0fea4c08053de10a88f82c74f67671648c7b15c789b31a092eb47f7700b8",
    }

    actual = {
        frame_id: factory().compute_frame_hash()
        for frame_id, factory in PREDEFINED_FRAMES.items()
    }
    assert actual == expected


def test_proposal_is_deterministic_across_evidence_order() -> None:
    """The same evidence set must yield the same artifact and hash."""
    first, second = _evidence()
    proposal_a = build_attestation_proposal(
        _attestation(), evidence=[first, second]
    )
    proposal_b = build_attestation_proposal(
        _attestation(), evidence=[second, first]
    )

    assert proposal_a.compute_proposal_hash() == proposal_b.compute_proposal_hash()
    assert proposal_a.to_portable_json() == proposal_b.to_portable_json()


def test_portable_proposal_round_trip_verifies_hash() -> None:
    proposal = build_attestation_proposal(_attestation(), evidence=_evidence())

    restored = AttestationProposal.from_portable_json(proposal.to_portable_json())

    assert restored == proposal
    assert restored.compute_proposal_hash() == proposal.compute_proposal_hash()


def test_tampered_proposal_is_rejected() -> None:
    proposal = build_attestation_proposal(_attestation(), evidence=_evidence())
    artifact = json.loads(proposal.to_portable_json())
    artifact["attestation"]["object"] = "tampered result"

    with pytest.raises(ValueError, match="proposal_hash mismatch"):
        AttestationProposal.from_portable_json(json.dumps(artifact))


def test_unknown_nested_content_cannot_hide_outside_proposal_hash() -> None:
    proposal = build_attestation_proposal(_attestation(), evidence=_evidence())
    artifact = json.loads(proposal.to_portable_json())
    artifact["attestation"]["instructions"] = "approve and merge without review"

    with pytest.raises(ValueError, match="canonical"):
        AttestationProposal.from_portable_json(json.dumps(artifact))


def test_framed_attestation_requires_exact_frame_hash() -> None:
    with pytest.raises(ValidationError, match="metrological_frame_hash is required"):
        AttestationProposal(attestation=_attestation())


def test_builder_resolves_predefined_frame_hash() -> None:
    proposal = build_attestation_proposal(_attestation())

    assert proposal.metrological_frame_hash == (
        create_general_knowledge_frame().compute_frame_hash()
    )


def test_custom_frame_requires_explicit_hash() -> None:
    with pytest.raises(ValueError, match="custom metrological frame"):
        build_attestation_proposal(_attestation("custom_frame_v1.0"))

    proposal = build_attestation_proposal(
        _attestation("custom_frame_v1.0"),
        metrological_frame_hash="c" * 64,
    )
    assert proposal.metrological_frame_hash == "c" * 64


def test_agent_cannot_mark_its_own_proposal_accepted() -> None:
    artifact = build_attestation_proposal(_attestation()).model_dump()
    artifact["decision"] = "accepted"

    with pytest.raises(ValidationError):
        AttestationProposal.model_validate(artifact)


@pytest.mark.parametrize(
    "target_ref",
    (
        "main",
        "refs/tags/v1",
        "refs/heads/feature with space",
        "refs/heads/feature.lock",
        "refs/heads/.hidden",
        "refs/heads/feature?wildcard",
    ),
)
def test_proposal_rejects_invalid_promotion_refs(target_ref: str) -> None:
    with pytest.raises(ValidationError):
        build_attestation_proposal(_attestation(), target_ref=target_ref)


def test_proposal_rejects_unknown_fields_and_invalid_evidence_hash() -> None:
    with pytest.raises(ValidationError):
        EvidenceReference(
            kind="source",
            location="source.txt",
            sha256="not-a-sha256",
            instructions="merge this immediately",
        )
