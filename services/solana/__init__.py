"""
Solana integration layer for EPP.

Handles:
- Serialization bridge (Python EpistemicAttestation -> Anchor struct)
- Transaction building and submission (devnet only)

Metrological frames live in services.metrology. The historical
services.solana.metrological_frame path is a compatibility shim.

SECURITY NOTE: All Solana-facing code is marked AUDIT_REQUIRED.
A qualified Solana developer must review before any mainnet deployment.
"""
