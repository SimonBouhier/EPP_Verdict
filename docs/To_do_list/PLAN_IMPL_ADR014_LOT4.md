# PLAN_IMPL_ADR014_LOT4.md
# Plan d'Implémentation ADR-014 Lot 4 — SlitherAdapter + Benchmark

> **Destinataire** : Claude Code
> **Commanditaire** : Sim
> **Validé par** : Claude Opus (Auditeur Adversarial)
> **Baseline de départ** : 766 passed, 14 skipped, 0 failed
> **Pré-requis confirmé** : Slither 0.11.5 installé, solc-select avec 0.4.25 et 0.8.0

---

## CONTEXTE

Le Lot 4 construit l'infrastructure complète pour :
1. Intégrer Slither comme source déterministe (ADR-012 pattern)
2. Benchmarker EPP contre du ground truth professionnel

Le benchmark ne sera pas exécuté par Claude Code (il nécessite Ollama live).
Claude Code construit toute l'infrastructure + un dry-run MockProvider.
Sim lance le run live lui-même plus tard.

---

## STRUCTURE DU LOT

| Étape | Fichier | Action |
|:------|:--------|:-------|
| L4.1 | `services/sources/adapters/slither_adapter.py` | Créer |
| L4.2 | `services/audit/audit_benchmark.py` | Créer |
| L4.3 | `tests/fixtures/benchmark/` | Créer (contrats + ground_truth.json) |
| L4.4 | `tests/test_adr014_slither.py` | Créer |
| L4.5 | `tests/test_adr014_benchmark.py` | Créer |

---

## L4.1 — `services/sources/adapters/slither_adapter.py`

Pattern identique aux autres adapters (ADR-012). Exécution locale de Slither.

```python
"""
SlitherAdapter — Analyse statique via Slither (ADR-014 / ADR-012 pattern).

Exécution locale. Ne nécessite aucune API externe.
Si Slither n'est pas installé, l'adapter signale proprement l'indisponibilité.
"""

import hashlib
import json
import logging
import subprocess
from typing import Any, Dict, Optional

from services.sources.adapters.base import SourceAdapter

logger = logging.getLogger("epp.sources.slither")


class SlitherAdapter(SourceAdapter):
    source_id = "slither_local"

    def __init__(self, slither_path: str = "slither"):
        self._slither_path = slither_path
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """Vérifie si Slither est installé et exécutable."""
        if self._available is not None:
            return self._available
        try:
            result = subprocess.run(
                [self._slither_path, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            self._available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._available = False
        return self._available

    async def fetch(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Exécute Slither sur un contrat Solidity.

        query = {
            "contract_path": "/path/to/Contract.sol",
            "solc_version": "0.4.25"  # optionnel
        }

        Returns: JSON complet de la sortie Slither (detectors + résultats).
        Raises: RuntimeError si Slither n'est pas disponible.
        """
        if not self.is_available():
            raise RuntimeError(
                f"Slither not available at '{self._slither_path}'. "
                "Install with: pip install slither-analyzer"
            )

        contract_path = query["contract_path"]
        solc_version = query.get("solc_version")

        cmd = [self._slither_path, contract_path, "--json", "-"]
        if solc_version:
            cmd.extend(["--solc-solcs-select", solc_version])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 min max par contrat
            )
            # Slither retourne du JSON sur stdout même en cas de findings
            # Le returncode != 0 signifie "findings detected", pas "crash"
            raw = json.loads(result.stdout) if result.stdout.strip() else {}
            if not raw and result.stderr:
                raw = {"error": result.stderr[:2000]}
            return raw
        except json.JSONDecodeError:
            return {"error": f"Slither output not JSON: {result.stdout[:500]}"}
        except subprocess.TimeoutExpired:
            return {"error": "Slither timeout (>120s)"}
        except Exception as exc:
            return {"error": str(exc)}

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalise la sortie Slither en format EPP.

        Returns: {
            "vulnerabilities": [
                {
                    "detector": "reentrancy-eth",
                    "severity": "high",
                    "confidence": "high",
                    "description": "...",
                    "elements": [...]
                }
            ],
            "summary": {
                "total_detectors_run": N,
                "total_findings": M,
                "by_severity": {"high": X, "medium": Y, ...}
            }
        }
        """
        if "error" in raw:
            return {"vulnerabilities": [], "summary": {"error": raw["error"]}}

        results = raw.get("results", {})
        detectors = results.get("detectors", [])

        vulns = []
        by_severity = {"high": 0, "medium": 0, "low": 0, "informational": 0}

        for d in detectors:
            severity = d.get("impact", "informational").lower()
            # Slither uses "High", "Medium", "Low", "Informational"
            if severity not in by_severity:
                severity = "informational"
            by_severity[severity] += 1

            vulns.append({
                "detector": d.get("check", "unknown"),
                "severity": severity,
                "confidence": d.get("confidence", "unknown").lower(),
                "description": d.get("description", "")[:500],
                "elements": [
                    {
                        "name": e.get("name", ""),
                        "source": e.get("source_mapping", {}).get("filename_short", ""),
                        "lines": e.get("source_mapping", {}).get("lines", []),
                    }
                    for e in d.get("elements", [])[:5]  # Cap éléments
                ],
            })

        return {
            "vulnerabilities": vulns,
            "summary": {
                "total_detectors_run": raw.get("number_of_active_detectors", 0),
                "total_findings": len(vulns),
                "by_severity": by_severity,
            },
        }

    def get_source_version(self, raw: Dict[str, Any]) -> str:
        """Version Slither + solc utilisés."""
        slither_v = raw.get("slither_version", "unknown")
        solc_v = raw.get("solc_version", "unknown")
        return f"slither-{slither_v}-solc-{solc_v}"
```

**Enregistrement dans `services/sources/adapters/__init__.py`** :
- Importer `SlitherAdapter`
- Ajouter dans `_REGISTRY` : `"slither_local": SlitherAdapter`
- Ajouter dans les re-exports

**ATTENTION** : le `SlitherAdapter` utilise `subprocess.run` (synchrone) dans
une méthode `async def fetch()`. C'est acceptable pour le hackathon car Slither
est un process externe court (~10-30s). Pour la production, il faudrait
`asyncio.create_subprocess_exec`. Documenter en commentaire `# TODO: asyncify`.

---

## L4.2 — `services/audit/audit_benchmark.py`

Script standalone pour le benchmark. N'est PAS appelé par le pipeline live.

```python
"""
ADR-014 Lot 4 — Benchmark offline : EPP vs ground truth professionnel.

Usage:
    python -m services.audit.audit_benchmark [--dry-run] [--output report.md]

Ce script :
1. Lit le ground_truth.json (vulnérabilités connues par contrat)
2. Pour chaque contrat : run_audit() avec use_cache=False
3. Compare les findings EPP avec le ground truth
4. Calcule precision, recall, F1 par catégorie
5. Produit un rapport markdown
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CategoryMetrics:
    """Métriques par catégorie SWC/ToB."""
    category: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def f1_score(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


@dataclass
class BenchmarkResult:
    """Résultat du benchmark pour un contrat."""
    contract_name: str
    contract_path: str
    ground_truth_source: str
    vulnerabilities_known: int
    vulnerabilities_detected: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    entropy_severity_correlation: float
    per_category: Dict[str, CategoryMetrics]
    slither_concordance_rate: float
    duration_ms: float
    errors: List[str] = field(default_factory=list)


@dataclass
class BenchmarkSuite:
    """Résultat complet du benchmark (tous les contrats)."""
    results: List[BenchmarkResult]
    total_duration_ms: float
    aggregate_precision: float
    aggregate_recall: float
    aggregate_f1: float
    timestamp: float = field(default_factory=time.time)


def load_ground_truth(path: str) -> Dict[str, Any]:
    """Charge le fichier ground_truth.json."""
    with open(path, "r") as f:
        return json.load(f)


def compare_findings(
    epp_findings: List[Dict[str, Any]],
    ground_truth_vulns: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compare les findings EPP avec le ground truth.

    Matching : un finding EPP "matche" un ground truth si :
    - Même catégorie SWC (exact match sur swc_id), OU
    - Même classe ToB (exact match sur tob_class)
    - ET même fonction cible (unit_name) si disponible

    Returns: {
        "true_positives": [...],
        "false_positives": [...],
        "false_negatives": [...],
        "per_category": {category: CategoryMetrics}
    }
    """
    # Claude Code implémente la logique de matching ici.
    # Le matching doit être documenté et déterministe.
    ...


def compute_benchmark_result(
    contract_name: str,
    contract_path: str,
    ground_truth_source: str,
    audit_result: Any,  # AuditResult
    ground_truth_vulns: List[Dict[str, Any]],
    slither_findings: Optional[List[Dict[str, Any]]] = None,
) -> BenchmarkResult:
    """Calcule les métriques pour un contrat."""
    # Claude Code implémente le calcul complet.
    ...


def generate_report(suite: BenchmarkSuite, output_path: str) -> None:
    """
    Génère un rapport markdown dans output_path.

    Format :
    # EPP Audit Benchmark Report
    ## Summary
    - Contracts benchmarked: N
    - Aggregate F1: X.XX
    - Duration: Xs
    ## Results per contract
    ### Contract: XXX
    | Metric | Value |
    | ... | ... |
    ## Per-category metrics
    ## Slither concordance
    """
    ...


async def run_benchmark(
    ground_truth_path: str,
    contracts_dir: str,
    output_path: str = "tests/audits/BENCHMARK_REPORT.md",
    dry_run: bool = False,
    models: Optional[List[str]] = None,
) -> BenchmarkSuite:
    """
    Point d'entrée principal du benchmark.

    Si dry_run=True : utilise MockProvider (pas d'Ollama requis).
    Si dry_run=False : utilise les vrais modèles via Ollama.

    La DB de benchmark est éphémère (tmp dir, jamais epp_audit_devnet.db).
    """
    ...
```

---

## L4.3 — Fixtures benchmark : `tests/fixtures/benchmark/`

### Structure

```
tests/fixtures/benchmark/
├── ground_truth.json           # Vulnérabilités connues (source professionnelle)
├── not_so_smart/               # Fichiers .sol de crytic/not-so-smart-contracts
│   ├── reentrancy.sol          # Depuis reentrancy/
│   ├── integer_overflow.sol    # Depuis integer_overflow/
│   ├── unprotected_function.sol # Depuis unprotected_function/
│   └── unchecked_call.sol      # Depuis unchecked_external_call/
└── README.md                   # Sources et licences
```

### `ground_truth.json`

Format :

```json
{
  "metadata": {
    "version": "1.0",
    "created": "2026-03-05",
    "sources": [
      "crytic/not-so-smart-contracts (Apache-2.0, archived 2023-02)",
      "crytic/building-secure-contracts (AGPLv3, active)"
    ]
  },
  "contracts": {
    "reentrancy.sol": {
      "source": "crytic/not-so-smart-contracts/reentrancy",
      "license": "Apache-2.0",
      "solc_version": "0.4.25",
      "vulnerabilities": [
        {
          "swc_id": "SWC-107",
          "tob_class": "undefined_behavior",
          "severity": "high",
          "title": "Reentrancy in withdrawBalance",
          "function": "withdrawBalance",
          "description": "External call via .call.value() before state update"
        }
      ]
    },
    "integer_overflow.sol": {
      "source": "crytic/not-so-smart-contracts/integer_overflow",
      "license": "Apache-2.0",
      "solc_version": "0.4.25",
      "vulnerabilities": [
        {
          "swc_id": "SWC-101",
          "tob_class": "undefined_behavior",
          "severity": "high",
          "title": "Integer overflow in transfer",
          "function": "transfer",
          "description": "Unchecked arithmetic allows balance manipulation"
        }
      ]
    },
    "unprotected_function.sol": {
      "source": "crytic/not-so-smart-contracts/unprotected_function",
      "license": "Apache-2.0",
      "solc_version": "0.4.25",
      "vulnerabilities": [
        {
          "swc_id": "SWC-105",
          "tob_class": "access_controls",
          "severity": "high",
          "title": "Unprotected changeOwner",
          "function": "changeOwner",
          "description": "Anyone can call changeOwner and take control"
        }
      ]
    },
    "unchecked_call.sol": {
      "source": "crytic/not-so-smart-contracts/unchecked_external_call",
      "license": "Apache-2.0",
      "solc_version": "0.4.25",
      "vulnerabilities": [
        {
          "swc_id": "SWC-104",
          "tob_class": "data_validation",
          "severity": "medium",
          "title": "Unchecked call return value",
          "function": "callchecked / callnotchecked",
          "description": "Return value of .call() not checked"
        }
      ]
    }
  }
}
```

### Fichiers `.sol`

Claude Code DOIT copier les fichiers `.sol` depuis le repo GitHub
`crytic/not-so-smart-contracts` (les fichiers sources réels, pas des
réécritures). Chaque fichier doit conserver son header de licence Apache-2.0.

Pour chaque catégorie, prendre le fichier `.sol` principal du dossier :
- `reentrancy/` → le fichier contenant `withdrawBalance`
- `integer_overflow/` → le fichier contenant `transfer` avec overflow
- `unprotected_function/` → le fichier contenant `changeOwner` sans restriction
- `unchecked_external_call/` → le fichier contenant les patterns checked/unchecked

Si les fichiers ne compilent pas avec solc 0.4.25 (pragma mismatch), noter
le pragma exact dans `ground_truth.json` sous `solc_version`.

### `README.md` dans le dossier benchmark

```markdown
# Benchmark Contracts — ADR-014

## Sources
- `not_so_smart/` : contrats de crytic/not-so-smart-contracts (Apache-2.0)
  Repo archivé en 2023, migré vers crytic/building-secure-contracts.
  Utilisés ici uniquement comme fixtures de benchmark avec ground truth connu.

## Ground Truth
`ground_truth.json` documente les vulnérabilités connues par contrat.
Chaque entrée cite sa source professionnelle.

## Licence
Les fichiers .sol conservent leur licence Apache-2.0 d'origine.
Le ground_truth.json est un travail dérivé documentaire (fair use).
```

---

## L4.4 — Tests SlitherAdapter

`tests/test_adr014_slither.py` — ≥5 tests :

```python
# Structure
def test_slither_adapter_has_source_id():
    # source_id == "slither_local"

def test_slither_adapter_is_available_returns_bool():
    # is_available() retourne True ou False sans crash

def test_slither_adapter_normalize_empty_results():
    # normalize({"results": {"detectors": []}})
    # → {"vulnerabilities": [], "summary": {...}}

def test_slither_adapter_normalize_with_findings():
    # normalize() avec un raw JSON simulant 2 findings
    # → 2 vulns, severity correcte, by_severity cohérent

def test_slither_adapter_get_source_version():
    # get_source_version({"slither_version": "0.11.5", "solc_version": "0.4.25"})
    # → "slither-0.11.5-solc-0.4.25"

def test_slither_adapter_in_registry():
    # "slither_local" dans _REGISTRY ou SlitherAdapter importable
    from services.sources.adapters import SlitherAdapter

def test_slither_adapter_fetch_missing_contract_raises():
    # fetch({"contract_path": "nonexistent.sol"}) → raw contient "error"
```

**NOTE** : ne PAS tester `fetch()` sur un vrai contrat dans les tests unitaires.
Le test d'intégration Slither live est réservé au run benchmark par Sim.
Tester uniquement `normalize()`, `get_source_version()`, et `is_available()`.

---

## L4.5 — Tests Benchmark

`tests/test_adr014_benchmark.py` — ≥5 tests :

```python
def test_ground_truth_json_is_valid():
    # Charger ground_truth.json, vérifier la structure

def test_ground_truth_all_contracts_have_vulnerabilities():
    # Chaque contrat dans ground_truth a ≥1 vulnérabilité

def test_ground_truth_vulnerabilities_have_swc_id():
    # Chaque vuln a un swc_id qui existe dans SWC_REGISTRY

def test_category_metrics_precision_recall_f1():
    # CategoryMetrics avec des valeurs connues → vérifier P/R/F1

def test_category_metrics_zero_division():
    # CategoryMetrics(tp=0, fp=0, fn=0) → precision=0, recall=0, f1=0

def test_compare_findings_exact_match():
    # 1 finding EPP qui matche 1 ground truth → tp=1, fp=0, fn=0

def test_compare_findings_false_positive():
    # 1 finding EPP sans ground truth correspondant → tp=0, fp=1, fn=0

def test_compare_findings_false_negative():
    # 0 finding EPP mais 1 ground truth → tp=0, fp=0, fn=1
```

---

## CHECKPOINT L4

```bash
pytest tests/test_adr014_*.py -v --tb=short
# → ≥72 passed (52 L1-L2 + 16 L3 + ≥10 L4), 0 failed

pytest tests/ -q --tb=no 2>&1 | tail -3
# → ≥776 passed, ≤14 skipped, 0 failed
```

---

## RÈGLES SPÉCIFIQUES LOT 4

- ❌ Ne PAS exécuter `run_benchmark(dry_run=False)` — Sim le fait lui-même
- ❌ Ne PAS faire de `subprocess.run(["slither", ...])` dans les tests unitaires
- ✅ Tester `normalize()` et `get_source_version()` avec des données simulées
- ✅ Le `ground_truth.json` doit citer ses sources (repo, licence, date)
- ✅ Les fichiers `.sol` du benchmark doivent conserver leur licence d'origine
- ✅ La DB de benchmark est éphémère (`tmp_path`), jamais `epp_audit_devnet.db`
- ✅ `audit_benchmark.py` doit être exécutable en mode `--dry-run` avec MockProvider

---

## LIVRABLES À TRANSMETTRE À SIM

1. Sortie `pytest tests/test_adr014_*.py -v --tb=short`
2. Sortie `pytest tests/ -q --tb=no`
3. `git diff --stat` montrant tous les fichiers créés/modifiés
4. Contenu de `ground_truth.json` (pour validation Opus)

---

*PLAN_IMPL_ADR014_LOT4.md — v1.0*
*Rédigé par Claude Opus (Auditeur Adversarial)*
*Validé par Sim*
*Date : 2026-03-05*
