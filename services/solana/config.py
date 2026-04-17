"""
Solana configuration -- cluster, keypair, guards.

# AUDIT_REQUIRED: This entire module manages blockchain connectivity.
# Review devnet guard, keypair handling, and cluster validation
# before ANY mainnet consideration.
"""

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


# AUDIT[A10-018] 🟢 ACCEPTED: MAINNET intentionnellement absent — devnet guard by design.
class SolanaCluster(Enum):
    """Clusters Solana supportes."""
    LOCALNET = "http://127.0.0.1:8899"
    DEVNET = "https://api.devnet.solana.com"
    # MAINNET est intentionnellement ABSENT.
    # AUDIT_REQUIRED: N'ajoutez mainnet qu'apres audit de securite complet.


# === PROGRAM ID ===
DEFAULT_PROGRAM_ID = "9QtybfyZQFhra1D6S3NtD6jD4z2Z3wcYmf4YXETq8bSD"


# === DEVNET GUARD ===
# AUDIT_REQUIRED: Remove this guard ONLY after full security audit.
_ALLOWED_CLUSTERS = {SolanaCluster.LOCALNET, SolanaCluster.DEVNET}


def validate_cluster(cluster: SolanaCluster) -> None:
    """
    Refuse categoriquement tout cluster non autorise.

    Raises:
        RuntimeError: Si le cluster n'est pas localnet ou devnet.
    """
    if cluster not in _ALLOWED_CLUSTERS:
        raise RuntimeError(
            f"SECURITY: Cluster {cluster} is NOT allowed. "
            f"EPP MVP is restricted to devnet/localnet. "
            f"Mainnet requires security audit. See AUDIT_REQUIRED markers."
        )


@dataclass
class SolanaConfig:
    """Configuration Solana pour EPP."""
    cluster: SolanaCluster = SolanaCluster.DEVNET
    keypair_path: Optional[str] = None  # None = ~/.config/solana/id.json
    program_id: Optional[str] = DEFAULT_PROGRAM_ID
    commitment: str = "confirmed"
    timeout_seconds: int = 30

    def __post_init__(self):
        # Guard systematique
        validate_cluster(self.cluster)

        # Keypair path par defaut
        if self.keypair_path is None:
            default = Path.home() / ".config" / "solana" / "id.json"
            if default.exists():
                self.keypair_path = str(default)

    @property
    def rpc_url(self) -> str:
        return self.cluster.value

    @property
    def is_localnet(self) -> bool:
        return self.cluster == SolanaCluster.LOCALNET
