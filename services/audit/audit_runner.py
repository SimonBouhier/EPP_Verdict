"""
ADR-014 Lot 3 — Orchestrateur d'audit épistémique de smart contracts.

Découpe un contrat Solidity en unités (ContractUnit) via contract_slicer,
puis lance run_pipeline() en mode VERIFY (assess→challenge→adjudicate)
sur chaque unité. Les résultats sont agrégés dans un AuditResult.

DB isolée : ne jamais utiliser le singleton get_db() ici — la DB d'audit
est gérée par l'appelant (CLI ou tests) via ISpaceDB(path) directement.
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from services.audit.contract_slicer import ContractUnit, ContractSliceResult, slice_contract
from services.audit.swc_taxonomy import TOB_4LEVEL
from services.esmm.cycle_prompts import CYCLE_TEMPLATES, CycleType
from services.esmm.pipeline import PipelineConfig, PipelineResult, run_pipeline

if TYPE_CHECKING:
    from database.engine import ISpaceDB

# Template ASSESS_AUDIT (index 0) — voir cycle_prompts.py
_ASSESS_AUDIT_TEMPLATE = CYCLE_TEMPLATES[CycleType.ASSESS_AUDIT][0]

# Ordre de priorité pour _aggregate_severity
_SEVERITY_ORDER: list[str] = ["high", "medium", "low", "informational"]

# Placeholders attendus dans le template ASSESS_AUDIT
_AUDIT_PLACEHOLDERS = ("contract_context", "function_code", "unit_metadata")


def _safe_format(template: str, **kwargs: str) -> str:
    """
    Substitue uniquement les placeholders connus dans le template, sans
    interpréter les accolades JSON présentes dans le corps du template.

    Remplace {key} par la valeur uniquement pour les clés fournies.
    """
    def _replace(match: "re.Match[str]") -> str:
        key = match.group(1)
        return kwargs.get(key, match.group(0))

    keys_pattern = "|".join(re.escape(k) for k in kwargs)
    return re.sub(rf"\{{({keys_pattern})\}}", _replace, template)


# ---------------------------------------------------------------------------
# Dataclass résultat
# ---------------------------------------------------------------------------


@dataclass
class AuditResult:
    """Résultat complet d'un audit épistémique d'un smart contract."""

    contract_path: str
    contract_hash: str
    contract_name: str
    slice_result: ContractSliceResult
    unit_results: list[dict[str, Any]]   # {unit, pipeline_result, severity} par unité
    aggregate_severity: str              # "high" | "medium" | "low" | "informational"
    aggregate_consensus: float           # min(consensus_score) parmi les unités auditées
    total_vulnerabilities: int           # unités avec severity != "informational"
    total_units_audited: int
    total_units_skipped: int
    duration_ms: float
    db_path: str                         # doit contenir "epp_audit"
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers publics
# ---------------------------------------------------------------------------


def format_unit_for_audit_prompt(unit: ContractUnit) -> dict[str, str]:
    """
    Formate un ContractUnit en placeholders pour le template ASSESS_AUDIT.

    Retourne un dict avec les 3 clés :
      - contract_context : imports + déclaration du contrat
      - function_code    : code source de l'unité
      - unit_metadata    : visibility, access_level, modifiers, state_writes, external_calls
    """
    unit_metadata = (
        f"visibility: {unit.visibility} | access_level: {unit.access_level} "
        f"| modifiers: {unit.modifiers}\n"
        f"state_writes: {unit.state_writes} | external_calls: {unit.external_calls}"
    )
    return {
        "contract_context": unit.context_imports,
        "function_code": unit.source_code,
        "unit_metadata": unit_metadata,
    }


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _sort_units_by_priority(units: list[ContractUnit]) -> list[ContractUnit]:
    """
    Tri déterministe : external_calls non vide → state_writes non vide → reste.
    Préserve l'ordre relatif dans chaque groupe (tri stable).
    """
    def _priority(unit: ContractUnit) -> int:
        if unit.external_calls:
            return 0
        if unit.state_writes:
            return 1
        return 2

    return sorted(units, key=_priority)


def _extract_severity_from_result(result: PipelineResult) -> str:
    """
    Extrait la severity depuis le premier consensus_meta d'un PipelineResult.

    consensus_meta peut être un dict Python (pre-DB round-trip) ou une str
    JSON (post-DB). Les deux cas sont gérés.

    Défaut : "informational" si non trouvé ou parsing échoue.
    """
    if not result.attestations:
        return "informational"

    attestation = result.attestations[0]
    try:
        meta = attestation.consensus_meta
        if isinstance(meta, str):
            meta = json.loads(meta)
        if not isinstance(meta, dict):
            return "informational"
        overall_risk = meta.get("audit_meta", {}).get("overall_risk")
        if overall_risk in TOB_4LEVEL:
            return overall_risk
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    return "informational"


def _aggregate_severity(severities: list[str]) -> str:
    """
    Maillon faible : retourne le niveau le plus sévère parmi les severities.
    Priorité décroissante : high > medium > low > informational.
    """
    for level in _SEVERITY_ORDER:
        if level in severities:
            return level
    return "informational"


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------


async def run_audit(
    contract_path: str,
    db: "ISpaceDB",
    models: Optional[list[str]] = None,
    frame: str = "smartcontract_audit_v1.0",
    use_slither: bool = False,
    use_cache: bool = True,
) -> AuditResult:
    """
    Orchestre l'audit épistémique d'un smart contract.

    Args:
        contract_path : chemin vers le fichier .sol
        db            : instance ISpaceDB isolée (jamais le singleton get_db())
        models        : liste de modèles LLM à consulter (None = config par défaut)
        frame         : frame métrologique à appliquer
        use_slither   : pré-analyse statique via Slither (Lot 4)
        use_cache     : activer le cache épistémique ADR-013

    Returns:
        AuditResult avec résultats par unité et métriques agrégées.
    """
    from services.esmm.orchestrator import ESMMRunConfig
    from services.config_loader import get_section, get_value

    t_start = time.time()
    errors: list[str] = []

    # Lire la stratégie de découpe et autres paramètres depuis config.yaml
    slice_strategy = get_value("audit", "slice_strategy", "function_level_v1")

    # Découper le contrat en unités auditables
    slice_result = slice_contract(contract_path, strategy=slice_strategy)

    # Trier par priorité : external_calls d'abord
    sorted_units = _sort_units_by_priority(slice_result.units)

    # Sélectionner les modèles depuis la config si non fournis
    if models is None:
        models = get_section("esmm", {}).get(
            "models", ["mistral:7b", "llama3.1:8b", "qwen2.5:7b"]
        )

    unit_results: list[dict[str, Any]] = []

    for unit in sorted_units:
        try:
            placeholders = format_unit_for_audit_prompt(unit)
            claim = _safe_format(_ASSESS_AUDIT_TEMPLATE, **placeholders)

            pipeline_config = PipelineConfig(
                use_cache=use_cache,
                metrological_frame=frame,
                default_epistemic_type="security_audit",  # Fix 3 (Lot A)
            )
            esmm_cfg = ESMMRunConfig(
                models=models,
                input_mode="verify",
                original_claim=claim,
                subject_override=f"{unit.contract_name}::{unit.unit_name}",  # Fix 1 (Lot A)
            )

            pipeline_result = await run_pipeline(
                question=claim,
                db=db,
                config=pipeline_config,
                esmm_config=esmm_cfg,
            )

            severity = _extract_severity_from_result(pipeline_result)
            unit_results.append({
                "unit": unit,
                "pipeline_result": pipeline_result,
                "severity": severity,
            })

        except Exception as exc:  # noqa: BLE001
            errors.append(f"Unit {unit.unit_name}: {exc}")

    # Métriques agrégées
    severities = [r["severity"] for r in unit_results]
    aggregate_severity = _aggregate_severity(severities)

    consensus_scores = [
        r["pipeline_result"].attestations[0].consensus_score
        for r in unit_results
        if r["pipeline_result"].attestations
    ]
    aggregate_consensus = min(consensus_scores, default=0.0)

    total_vulnerabilities = sum(
        1 for r in unit_results if r["severity"] != "informational"
    )
    duration_ms = (time.time() - t_start) * 1000

    return AuditResult(
        contract_path=contract_path,
        contract_hash=slice_result.contract_hash,
        contract_name=slice_result.contract_path.replace("\\", "/").split("/")[-1].replace(".sol", ""),
        slice_result=slice_result,
        unit_results=unit_results,
        aggregate_severity=aggregate_severity,
        aggregate_consensus=aggregate_consensus,
        total_vulnerabilities=total_vulnerabilities,
        total_units_audited=len(unit_results),
        total_units_skipped=len(slice_result.skipped_units),
        duration_ms=duration_ms,
        db_path=str(db.db_path),
        errors=errors,
    )
