# Attestation proposals

This directory is the canonical Git review surface for EPP attestation
proposals. Each `*.json` file must be produced by
`AttestationProposal.to_portable_json()` and pass:

```bash
python -m scripts.validate_proposals
```

Repository-relative evidence is verified byte-for-byte against its declared
SHA-256. HTTPS evidence is never fetched by CI: the reference and digest are
recorded for review, but acquisition remains outside the trusted merge job.

Raw untrusted corpora do not belong here. A pull request is a promotion
boundary, not an ingestion bus.
