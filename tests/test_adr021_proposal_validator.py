"""Tests for the no-network proposal validation gate introduced by ADR-021."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.validate_proposals import (
    ProposalValidationError,
    validate_proposal_directory,
)
from services.governance.proposal import EvidenceReference, build_attestation_proposal
from tests.test_adr021_github_governance import _attestation


def _proposal_directory(repository_root: Path) -> Path:
    directory = repository_root / "governance" / "proposals"
    directory.mkdir(parents=True)
    return directory


def test_empty_canonical_directory_is_valid(tmp_path: Path) -> None:
    _proposal_directory(tmp_path)

    report = validate_proposal_directory(tmp_path)

    assert report.proposals_validated == 0
    assert report.local_evidence_verified == 0


def test_local_evidence_is_verified_byte_for_byte(tmp_path: Path) -> None:
    proposal_directory = _proposal_directory(tmp_path)
    evidence_path = tmp_path / "evidence" / "report.txt"
    evidence_path.parent.mkdir()
    evidence_bytes = b"observable test result\n"
    evidence_path.write_bytes(evidence_bytes)
    proposal = build_attestation_proposal(
        _attestation(),
        evidence=[
            EvidenceReference(
                kind="test_report",
                location="evidence/report.txt",
                sha256=hashlib.sha256(evidence_bytes).hexdigest(),
            )
        ],
    )
    (proposal_directory / "valid.json").write_text(
        proposal.to_portable_json(), encoding="utf-8"
    )

    report = validate_proposal_directory(tmp_path)

    assert report.proposals_validated == 1
    assert report.local_evidence_verified == 1


def test_local_evidence_hash_mismatch_fails_gate(tmp_path: Path) -> None:
    proposal_directory = _proposal_directory(tmp_path)
    evidence_path = tmp_path / "evidence.txt"
    evidence_path.write_bytes(b"actual bytes")
    proposal = build_attestation_proposal(
        _attestation(),
        evidence=[
            EvidenceReference(
                kind="source",
                location="evidence.txt",
                sha256=hashlib.sha256(b"different bytes").hexdigest(),
            )
        ],
    )
    (proposal_directory / "mismatch.json").write_text(
        proposal.to_portable_json(), encoding="utf-8"
    )

    with pytest.raises(ProposalValidationError, match="hash mismatch"):
        validate_proposal_directory(tmp_path)


def test_https_evidence_is_declared_but_never_fetched(tmp_path: Path) -> None:
    proposal_directory = _proposal_directory(tmp_path)
    proposal = build_attestation_proposal(
        _attestation(),
        evidence=[
            EvidenceReference(
                kind="source",
                location="https://example.org/source.json",
                sha256="a" * 64,
            )
        ],
    )
    (proposal_directory / "external.json").write_text(
        proposal.to_portable_json(), encoding="utf-8"
    )

    report = validate_proposal_directory(tmp_path)

    assert report.external_evidence_declared == 1
    assert report.local_evidence_verified == 0


@pytest.mark.parametrize(
    "location",
    (
        "../outside.txt",
        "/absolute/path.txt",
        "C:\\outside.txt",
        "file:///tmp/source.txt",
        "http://example.org/source.txt",
    ),
)
def test_unsafe_evidence_locations_are_rejected(location: str) -> None:
    with pytest.raises(ValidationError):
        EvidenceReference(kind="source", location=location, sha256="a" * 64)


def test_proposal_directory_cannot_escape_repository(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-proposals"
    outside.mkdir(exist_ok=True)

    with pytest.raises(ProposalValidationError, match="inside the repository"):
        validate_proposal_directory(tmp_path, outside)
