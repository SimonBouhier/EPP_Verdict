"""Validate all Git-governed EPP proposal artifacts without network access."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from services.governance.proposal import AttestationProposal

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ProposalValidationError(ValueError):
    """Raised when a proposal or its local evidence fails validation."""


@dataclass(frozen=True)
class ValidationReport:
    proposals_validated: int = 0
    local_evidence_verified: int = 0
    external_evidence_declared: int = 0


def _verify_local_evidence(
    repository_root: Path,
    location: str,
    expected_sha256: str,
) -> None:
    repository_root = repository_root.resolve()
    evidence_path = repository_root.joinpath(*PurePosixPath(location).parts).resolve()
    try:
        evidence_path.relative_to(repository_root)
    except ValueError as exc:
        raise ProposalValidationError(
            f"local evidence escapes repository root: {location}"
        ) from exc
    if not evidence_path.is_file():
        raise ProposalValidationError(f"local evidence file is missing: {location}")
    with evidence_path.open("rb") as evidence_file:
        actual_sha256 = hashlib.file_digest(evidence_file, "sha256").hexdigest()
    if not hmac.compare_digest(actual_sha256, expected_sha256):
        raise ProposalValidationError(
            f"local evidence hash mismatch: {location} "
            f"(expected {expected_sha256}, got {actual_sha256})"
        )

def validate_proposal_file(
    proposal_path: Path,
    repository_root: Path,
) -> ValidationReport:
    try:
        proposal = AttestationProposal.from_portable_json(
            proposal_path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise ProposalValidationError(
            f"invalid proposal artifact {proposal_path}: {exc}"
        ) from exc

    local_count = 0
    external_count = 0
    for evidence in proposal.evidence:
        if evidence.location.startswith("https://"):
            external_count += 1
            continue
        _verify_local_evidence(repository_root, evidence.location, evidence.sha256)
        local_count += 1

    return ValidationReport(
        proposals_validated=1,
        local_evidence_verified=local_count,
        external_evidence_declared=external_count,
    )


def validate_proposal_directory(
    repository_root: Path,
    proposal_directory: Path | None = None,
) -> ValidationReport:
    repository_root = repository_root.resolve()
    proposal_directory = (
        proposal_directory or repository_root / "governance" / "proposals"
    ).resolve()
    try:
        proposal_directory.relative_to(repository_root)
    except ValueError as exc:
        raise ProposalValidationError(
            "proposal directory must stay inside the repository"
        ) from exc

    if not proposal_directory.is_dir():
        raise ProposalValidationError(
            f"proposal directory is missing: {proposal_directory}"
        )

    report = ValidationReport()
    for proposal_path in sorted(proposal_directory.rglob("*.json")):
        current = validate_proposal_file(proposal_path, repository_root)
        report = ValidationReport(
            proposals_validated=(
                report.proposals_validated + current.proposals_validated
            ),
            local_evidence_verified=(
                report.local_evidence_verified + current.local_evidence_verified
            ),
            external_evidence_declared=(
                report.external_evidence_declared
                + current.external_evidence_declared
            ),
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=PROJECT_ROOT,
    )
    parser.add_argument("--proposal-directory", type=Path, default=None)
    args = parser.parse_args()

    try:
        report = validate_proposal_directory(
            args.repository_root,
            args.proposal_directory,
        )
    except ProposalValidationError as exc:
        print(f"PROPOSAL VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1

    print(
        "Proposal validation passed: "
        f"{report.proposals_validated} proposal(s), "
        f"{report.local_evidence_verified} local evidence file(s) verified, "
        f"{report.external_evidence_declared} external reference(s) declared "
        "without network access."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
