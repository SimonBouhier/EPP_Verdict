"""
Solana integration layer for EPP.

Handles:
- Metrological frames (off-chain reference, on-chain hash)
- Serialization bridge (Python EpistemicAttestation -> Anchor struct)
- Transaction building and submission (devnet only)

SECURITY NOTE: All Solana-facing code is marked AUDIT_REQUIRED.
A qualified Solana developer must review before any mainnet deployment.
"""
