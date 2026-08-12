"""Governance artifacts for promoting EPP outputs through Git review."""

from .proposal import (
    AttestationProposal,
    EvidenceReference,
    build_attestation_proposal,
)

__all__ = [
    "AttestationProposal",
    "EvidenceReference",
    "build_attestation_proposal",
]
