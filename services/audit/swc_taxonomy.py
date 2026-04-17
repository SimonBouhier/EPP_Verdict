"""
SWC Registry + Trail of Bits vulnerability classification.

Source unique de vérité pour les catégories de vulnérabilités smart contract.
Deux taxonomies supportées : SWC (swcregistry.io) et Trail of Bits (4-level).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SWCEntry:
    """Entrée du SWC Registry."""

    swc_id: str            # "SWC-107"
    title: str             # "Reentrancy"
    description: str       # Description courte (une ligne)
    severity_default: str  # "high" (tob_4level)
    tob_class: str         # Classe Trail of Bits
    relationships: list[str]  # SWC-IDs liés


# Trail of Bits vulnerability classes (cf. audit LooksRare, Origin Protocol)
TOB_CLASSES: list[str] = [
    "access_controls",
    "timing",
    "undefined_behavior",
    "patching",
    "data_validation",
    "auditing_logging",
    "configuration",
    "cryptography",
]

# Severity levels — deux taxonomies
TOB_4LEVEL: list[str] = ["high", "medium", "low", "informational"]
SWC_5LEVEL: list[str] = ["critical", "high", "medium", "low", "informational"]

# Mapping SWC → entrées (33 entrées couvrant SWC-100 à SWC-136)
SWC_REGISTRY: dict[str, SWCEntry] = {
    "SWC-100": SWCEntry(
        swc_id="SWC-100",
        title="Function Default Visibility",
        description="Functions that do not have a function visibility type specified are public by default.",
        severity_default="medium",
        tob_class="access_controls",
        relationships=[],
    ),
    "SWC-101": SWCEntry(
        swc_id="SWC-101",
        title="Integer Overflow and Underflow",
        description="An overflow/underflow happens when an arithmetic operation reaches the maximum or minimum size.",
        severity_default="high",
        tob_class="undefined_behavior",
        relationships=[],
    ),
    "SWC-104": SWCEntry(
        swc_id="SWC-104",
        title="Unchecked Call Return Value",
        description="The return value of a message call is not checked, silently swallowing failures.",
        severity_default="medium",
        tob_class="data_validation",
        relationships=["SWC-107"],
    ),
    "SWC-105": SWCEntry(
        swc_id="SWC-105",
        title="Unprotected Ether Withdrawal",
        description="Any party can withdraw ETH from the contract without restriction.",
        severity_default="high",
        tob_class="access_controls",
        relationships=["SWC-106"],
    ),
    "SWC-106": SWCEntry(
        swc_id="SWC-106",
        title="Unprotected SELFDESTRUCT",
        description="Any party can destroy the contract and transfer ETH to an arbitrary address.",
        severity_default="high",
        tob_class="access_controls",
        relationships=["SWC-105"],
    ),
    "SWC-107": SWCEntry(
        swc_id="SWC-107",
        title="Reentrancy",
        description="External contract calls allow attackers to re-enter the calling function before completion.",
        severity_default="high",
        tob_class="undefined_behavior",
        relationships=["SWC-104"],
    ),
    "SWC-108": SWCEntry(
        swc_id="SWC-108",
        title="State Variable Default Visibility",
        description="State variables that do not have a visibility type specified are internal by default.",
        severity_default="medium",
        tob_class="access_controls",
        relationships=["SWC-100"],
    ),
    "SWC-110": SWCEntry(
        swc_id="SWC-110",
        title="Assert Violation",
        description="Directly calling assert() with a false condition halts execution and wastes remaining gas.",
        severity_default="medium",
        tob_class="undefined_behavior",
        relationships=["SWC-123"],
    ),
    "SWC-111": SWCEntry(
        swc_id="SWC-111",
        title="Use of Deprecated Solidity Functions",
        description="Several functions and operators in Solidity are deprecated and should not be used.",
        severity_default="low",
        tob_class="patching",
        relationships=["SWC-118"],
    ),
    "SWC-112": SWCEntry(
        swc_id="SWC-112",
        title="Delegatecall to Untrusted Callee",
        description="Calling an untrusted external contract with delegatecall allows it to take over the caller's storage.",
        severity_default="high",
        tob_class="undefined_behavior",
        relationships=["SWC-107"],
    ),
    "SWC-113": SWCEntry(
        swc_id="SWC-113",
        title="DoS with Failed Call",
        description="External calls that fail can cause denial of service if the failure is not handled properly.",
        severity_default="medium",
        tob_class="timing",
        relationships=["SWC-128"],
    ),
    "SWC-114": SWCEntry(
        swc_id="SWC-114",
        title="Transaction Order Dependence",
        description="Race conditions caused by transaction ordering (front-running) can lead to unexpected outcomes.",
        severity_default="medium",
        tob_class="timing",
        relationships=["SWC-116"],
    ),
    "SWC-115": SWCEntry(
        swc_id="SWC-115",
        title="Authorization through tx.origin",
        description="Using tx.origin for authorization makes contracts vulnerable to phishing attacks.",
        severity_default="high",
        tob_class="access_controls",
        relationships=["SWC-105"],
    ),
    "SWC-116": SWCEntry(
        swc_id="SWC-116",
        title="Block values as a proxy for time",
        description="Block timestamp can be manipulated by miners within certain bounds.",
        severity_default="low",
        tob_class="timing",
        relationships=["SWC-114"],
    ),
    "SWC-117": SWCEntry(
        swc_id="SWC-117",
        title="Signature Malleability",
        description="ECDSA signatures can be manipulated without knowledge of the private key.",
        severity_default="medium",
        tob_class="cryptography",
        relationships=["SWC-121"],
    ),
    "SWC-118": SWCEntry(
        swc_id="SWC-118",
        title="Incorrect Constructor Name",
        description=(
            "Legacy pattern (Solidity < 0.4.22): using the contract name as constructor "
            "instead of the constructor keyword. If renamed, the function becomes public. "
            "Obsolete since Solidity 0.4.22 introduced the constructor keyword."
        ),
        severity_default="high",
        tob_class="access_controls",
        relationships=["SWC-100"],
    ),
    "SWC-119": SWCEntry(
        swc_id="SWC-119",
        title="Shadowing State Variables",
        description="State variables in derived contracts can shadow variables in base contracts.",
        severity_default="medium",
        tob_class="undefined_behavior",
        relationships=["SWC-125"],
    ),
    "SWC-120": SWCEntry(
        swc_id="SWC-120",
        title="Weak Sources of Randomness",
        description="On-chain randomness sources (block.timestamp, blockhash) are predictable by miners.",
        severity_default="high",
        tob_class="cryptography",
        relationships=["SWC-116"],
    ),
    "SWC-121": SWCEntry(
        swc_id="SWC-121",
        title="Missing Protection against Signature Replay",
        description="Signatures can be replayed across transactions or chains without a nonce/chainId.",
        severity_default="high",
        tob_class="cryptography",
        relationships=["SWC-117"],
    ),
    "SWC-123": SWCEntry(
        swc_id="SWC-123",
        title="Requirement Violation",
        description="A requirement is violated, indicating an unexpected contract state or caller error.",
        severity_default="medium",
        tob_class="data_validation",
        relationships=["SWC-110"],
    ),
    "SWC-124": SWCEntry(
        swc_id="SWC-124",
        title="Write to Arbitrary Storage Location",
        description="An attacker can write to arbitrary storage slots, corrupting contract state.",
        severity_default="high",
        tob_class="undefined_behavior",
        relationships=["SWC-101"],
    ),
    "SWC-125": SWCEntry(
        swc_id="SWC-125",
        title="Incorrect Inheritance Order",
        description="Multiple inheritance can lead to unexpected behavior due to C3 linearization.",
        severity_default="medium",
        tob_class="configuration",
        relationships=["SWC-119"],
    ),
    "SWC-126": SWCEntry(
        swc_id="SWC-126",
        title="Insufficient Gas Griefing",
        description="A caller can provide insufficient gas to subvert the behavior of a forwarding call.",
        severity_default="medium",
        tob_class="timing",
        relationships=["SWC-113"],
    ),
    "SWC-127": SWCEntry(
        swc_id="SWC-127",
        title="Arbitrary Jump with Function Type Variable",
        description="Use of function type variables can allow jumps to arbitrary code locations.",
        severity_default="high",
        tob_class="undefined_behavior",
        relationships=["SWC-112"],
    ),
    "SWC-128": SWCEntry(
        swc_id="SWC-128",
        title="DoS With Block Gas Limit",
        description="Unbounded loops or operations can exceed the block gas limit, bricking the contract.",
        severity_default="medium",
        tob_class="timing",
        relationships=["SWC-113"],
    ),
    "SWC-129": SWCEntry(
        swc_id="SWC-129",
        title="Typographical Error",
        description="A typo in an operator (e.g., =+ instead of +=) changes the intended behavior.",
        severity_default="low",
        tob_class="patching",
        relationships=[],
    ),
    "SWC-130": SWCEntry(
        swc_id="SWC-130",
        title="Right-To-Left-Override control character",
        description="RTL Unicode control characters can make malicious code appear benign in editors.",
        severity_default="informational",
        tob_class="auditing_logging",
        relationships=[],
    ),
    "SWC-131": SWCEntry(
        swc_id="SWC-131",
        title="Presence of unused variables",
        description="Unused variables increase gas cost and may indicate dead or unreachable code.",
        severity_default="informational",
        tob_class="patching",
        relationships=["SWC-135"],
    ),
    "SWC-132": SWCEntry(
        swc_id="SWC-132",
        title="Unexpected Ether balance",
        description="Contracts that assume a specific Ether balance can be broken via selfdestruct or coinbase.",
        severity_default="medium",
        tob_class="undefined_behavior",
        relationships=["SWC-106"],
    ),
    "SWC-133": SWCEntry(
        swc_id="SWC-133",
        title="Hash Collisions With Multiple Variable Length Arguments",
        description="Using abi.encodePacked with dynamic types can cause hash collisions.",
        severity_default="high",
        tob_class="cryptography",
        relationships=["SWC-117"],
    ),
    "SWC-134": SWCEntry(
        swc_id="SWC-134",
        title="Message call with hardcoded gas amount",
        description="Hardcoded gas amounts in calls may break with future EVM gas repricing.",
        severity_default="low",
        tob_class="patching",
        relationships=["SWC-113"],
    ),
    "SWC-135": SWCEntry(
        swc_id="SWC-135",
        title="Code With No Effects",
        description="Code that has no side effects but appears to do something may indicate a bug.",
        severity_default="informational",
        tob_class="patching",
        relationships=["SWC-131"],
    ),
    "SWC-136": SWCEntry(
        swc_id="SWC-136",
        title="Unencrypted Private Data On-Chain",
        description="Private state variables are visible to anyone who can read blockchain state.",
        severity_default="high",
        tob_class="data_validation",
        relationships=[],
    ),
}


def get_swc(swc_id: str) -> Optional[SWCEntry]:
    """Retourne l'entrée SWC correspondant à swc_id, ou None si inconnu."""
    return SWC_REGISTRY.get(swc_id)


def get_swc_by_tob_class(tob_class: str) -> list[SWCEntry]:
    """Retourne toutes les entrées SWC correspondant à une classe Trail of Bits."""
    return [entry for entry in SWC_REGISTRY.values() if entry.tob_class == tob_class]


def map_severity_5to4(severity: str) -> str:
    """SWC 5-level → ToB 4-level. 'critical' → 'high', reste identity."""
    return "high" if severity == "critical" else severity


def map_severity_4to5(severity: str) -> str:
    """ToB 4-level → SWC 5-level (inverse). Pas d'upgrade en 'critical'."""
    return severity
