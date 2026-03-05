"""
NIST CODATA 2022 adapter — physical constants anchor.
Source: https://physics.nist.gov/cuu/Constants/Table/allascii.txt
File cached locally at: data/nist_codata_2022.txt
No network required at runtime.
"""
import hashlib
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class NISTConstant:
    name: str
    value: float
    uncertainty: Optional[float]
    unit: str
    source_hash: str  # SHA-256 of the raw file line


NIST_FILE = Path("data/nist_codata_2022.txt")

# Canonical name aliases for EPP claims
ALIASES = {
    "speed of light":           "speed of light in vacuum",
    "speed of light in vacuum": "speed of light in vacuum",
    "planck constant":          "Planck constant",
    "boltzmann constant":       "Boltzmann constant",
    "avogadro constant":        "Avogadro constant",
    "elementary charge":        "elementary charge",
    "electron mass":            "electron mass",
    "proton mass":              "proton mass",
}


def _clean_number(raw: str) -> Optional[float]:
    """Strip internal spaces and parse scientific notation."""
    cleaned = raw.strip().replace(" ", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _file_hash() -> str:
    return hashlib.sha256(NIST_FILE.read_bytes()).hexdigest()


def load_constants() -> dict[str, NISTConstant]:
    """Parse nist_codata_2022.txt into a lookup dict."""
    constants = {}
    file_hash = _file_hash()
    
    with open(NIST_FILE, encoding="utf-8") as f:
        for line in f:
            # Skip headers and separators
            if not line.strip() or line.startswith(" ") or "---" in line:
                # But check if it's a data line (starts with lowercase or uppercase letter, not spaces)
                stripped = line.rstrip("\n")
                if not stripped or len(stripped) < 60:
                    continue
                # Data lines: name field is left-aligned, not indented
                if stripped[0] == " ":
                    continue
            else:
                stripped = line.rstrip("\n")
            
            if len(stripped) < 60:
                continue
            if stripped[0] == " " or "---" in stripped or "From:" in stripped:
                continue
            
            name_raw = stripped[:60].strip()
            rest = stripped[60:].split()
            
            if not name_raw or not rest:
                continue
            
            value = _clean_number(rest[0]) if rest else None
            uncertainty = _clean_number(rest[1]) if len(rest) > 1 else None
            unit = rest[2] if len(rest) > 2 else ""
            
            if value is None:
                continue
            
            constants[name_raw.lower()] = NISTConstant(
                name=name_raw,
                value=value,
                uncertainty=uncertainty,
                unit=unit,
                source_hash=file_hash,
            )
    
    return constants


_CACHE: dict[str, NISTConstant] | None = None


def get_constant(name: str) -> Optional[NISTConstant]:
    """
    Lookup a physical constant by name or alias.
    Returns NISTConstant with value, uncertainty, unit, and source_hash.
    """
    global _CACHE
    if _CACHE is None:
        _CACHE = load_constants()
    
    canonical = ALIASES.get(name.lower(), name.lower())
    return _CACHE.get(canonical.lower())


def get_source_anchor(name: str) -> Optional[dict]:
    """
    Returns EPP-compatible source anchor dict for use in pipeline frames.
    """
    const = get_constant(name)
    if const is None:
        return None
    return {
        "source": "NIST_CODATA_2022",
        "constant_name": const.name,
        "value": const.value,
        "uncertainty": const.uncertainty,
        "unit": const.unit,
        "anchor_hash": const.source_hash,
        "url": "https://physics.nist.gov/cuu/Constants/Table/allascii.txt",
        "citation": "Tiesinga et al. (2024), CODATA 2022, NIST Web Version 9.0",
    }