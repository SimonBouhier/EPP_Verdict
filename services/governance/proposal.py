"""Deterministic Git-review envelope for an epistemic attestation.

An ESMM result is not accepted merely because it exists. This module wraps
the result and its evidence into a portable proposal. A pull request can
review that artifact; the merge event, enforced outside this module, records
promotion. Raw or untrusted source content is referenced by digest and is not
embedded as executable instructions.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from services.esmm.attestation import EpistemicAttestation
from services.metrology import PREDEFINED_FRAMES

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_SCHEMA_VERSION = "epp.attestation-proposal/v1"


def _canonical_json(value: Any) -> str:
    """Return the byte-stable JSON representation used for proposal hashes."""
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


class EvidenceReference(BaseModel):
    """Content-addressed reference to evidence reviewed with a proposal."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["source", "run_log", "test_report", "other"]
    location: str = Field(
        min_length=1,
        max_length=2048,
        description="Repository-relative path or public source URL.",
    )
    sha256: str = Field(
        pattern=_SHA256_PATTERN,
        description="SHA-256 of the exact referenced bytes.",
    )
    description: str | None = Field(default=None, max_length=512)

    @field_validator("location")
    @classmethod
    def validate_location(cls, value: str) -> str:
        """Allow HTTPS references or safe repository-relative POSIX paths."""
        parsed = urlparse(value)
        if parsed.scheme:
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError("external evidence location must be an HTTPS URL")
            return value

        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value or ":" in value:
            raise ValueError(
                "local evidence location must be a safe repository-relative POSIX path"
            )
        return value


class AttestationProposal(BaseModel):
    """Canonical proposal submitted to Git review before promotion.

    ``decision`` deliberately stays ``proposed`` in the artifact. Acceptance
    is represented by the protected merge commit rather than by a model field
    that an agent could set itself.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["epp.attestation-proposal/v1"] = _SCHEMA_VERSION
    decision: Literal["proposed"] = "proposed"
    target_ref: str = Field(default="refs/heads/main", min_length=12, max_length=255)
    attestation: EpistemicAttestation
    metrological_frame_hash: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
        description="Hash of the full metrological frame referenced by the attestation.",
    )
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=100)

    @field_validator("target_ref")
    @classmethod
    def validate_target_ref(cls, value: str) -> str:
        """Only ordinary branch refs may be promotion targets."""
        if not value.startswith("refs/heads/"):
            raise ValueError("target_ref must start with 'refs/heads/'")
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("target_ref contains a control character")
        if any(
            token in value
            for token in ("..", "~", "^", ":", "?", "*", "[", "\\", "@{", " ")
        ):
            raise ValueError("target_ref contains a forbidden Git ref token")
        if value.endswith(("/", ".")):
            raise ValueError("target_ref must not end with '/' or '.'")
        branch_components = value.removeprefix("refs/heads/").split("/")
        if any(
            not component
            or component.startswith(".")
            or component.lower().endswith(".lock")
            for component in branch_components
        ):
            raise ValueError("target_ref contains an invalid Git ref component")
        return value

    @field_validator("evidence")
    @classmethod
    def canonicalize_evidence(
        cls, value: list[EvidenceReference]
    ) -> list[EvidenceReference]:
        """Keep the in-memory model and serialized artifact in one order."""
        return sorted(
            value,
            key=lambda item: (
                item.kind,
                item.location,
                item.sha256,
                item.description or "",
            ),
        )

    @model_validator(mode="after")
    def require_frame_hash_for_framed_attestation(self) -> AttestationProposal:
        """A named methodology must be bound to its exact content hash."""
        if self.attestation.metrological_frame and self.metrological_frame_hash is None:
            raise ValueError(
                "metrological_frame_hash is required when the attestation "
                "references a metrological frame"
            )
        return self

    def canonical_payload(self) -> dict[str, Any]:
        """Return the hash payload with evidence order canonicalized."""
        payload = self.model_dump(mode="json")
        payload["evidence"] = sorted(
            payload["evidence"],
            key=lambda item: (
                item["kind"],
                item["location"],
                item["sha256"],
                item.get("description") or "",
            ),
        )
        return payload

    def compute_proposal_hash(self) -> str:
        """Compute SHA-256 over the canonical proposal payload."""
        encoded = _canonical_json(self.canonical_payload()).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_artifact_dict(self) -> dict[str, Any]:
        """Return the complete review artifact, including its integrity hash."""
        return {
            **self.canonical_payload(),
            "proposal_hash": self.compute_proposal_hash(),
        }

    def to_portable_json(self) -> str:
        """Serialize a deterministic, human-reviewable Git artifact."""
        return json.dumps(
            self.to_artifact_dict(),
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ) + "\n"

    @classmethod
    def from_portable_json(cls, raw_json: str) -> AttestationProposal:
        """Parse an artifact and reject any hash mismatch or unknown field."""
        raw = json.loads(raw_json)
        if not isinstance(raw, dict):
            raise TypeError("proposal artifact must be a JSON object")
        claimed_hash = raw.pop("proposal_hash", None)
        if not isinstance(claimed_hash, str):
            raise TypeError("proposal_hash is required")
        proposal = cls.model_validate(raw)
        raw["evidence"] = sorted(
            raw["evidence"],
            key=lambda item: (
                item["kind"],
                item["location"],
                item["sha256"],
                item.get("description") or "",
            ),
        )
        if raw != proposal.canonical_payload():
            raise ValueError(
                "proposal artifact is not canonical or contains unknown nested fields"
            )
        if not hmac.compare_digest(claimed_hash, proposal.compute_proposal_hash()):
            raise ValueError("proposal_hash mismatch")
        return proposal


def build_attestation_proposal(
    attestation: EpistemicAttestation,
    *,
    evidence: Sequence[EvidenceReference] = (),
    metrological_frame_hash: str | None = None,
    target_ref: str = "refs/heads/main",
) -> AttestationProposal:
    """Build a proposal, resolving predefined frame hashes when possible."""
    resolved_frame_hash = metrological_frame_hash
    if attestation.metrological_frame and resolved_frame_hash is None:
        factory = PREDEFINED_FRAMES.get(attestation.metrological_frame)
        if factory is None:
            raise ValueError(
                "custom metrological frame requires an explicit "
                "metrological_frame_hash"
            )
        resolved_frame_hash = factory().compute_frame_hash()

    return AttestationProposal(
        target_ref=target_ref,
        attestation=attestation,
        metrological_frame_hash=resolved_frame_hash,
        evidence=list(evidence),
    )
