# PLAN_IMPL_ADR014.md
# Plan d'Implémentation ADR-014 — Moteur d'Audit Smart Contracts

> **Destinataire** : Claude Code
> **Commanditaire** : Sim
> **Validé par** : Claude Opus (Auditeur Adversarial)
> **Baseline de départ** : 698 passed, 14 skipped, 0 failed (post-migration Phase B)
> **Deadline** : 6 avril 2026 (Colosseum hackathon)
> **Référence** : ADR-014.md (dans le projet)

---

## ARCHITECTURE DU PLAN

4 lots séquentiels. Chaque lot produit un livrable testable indépendamment.
Chaque lot se termine par un checkpoint : `pytest tests/ -q --tb=no` + rapport
à transmettre à Sim pour validation Opus avant le lot suivant.

| Lot | Contenu | Tests attendus | Risque |
|:----|:--------|:---------------|:-------|
| **L1** | Fondations (taxonomie + slicer + frame) | ≥15 tests | Faible |
| **L2** | Prompts AUDIT + intégration pipeline | ≥10 tests | Moyen |
| **L3** | audit_runner + CLI + DB isolée | ≥10 tests | Moyen |
| **L4** | SlitherAdapter + benchmark | ≥5 tests | Faible (optionnel) |

---

# LOT 1 — FONDATIONS

Zéro dépendance au pipeline existant. Testable en isolation totale.

## L1.1 — `services/audit/swc_taxonomy.py`

**Nouveau fichier.** Mapping des catégories SWC + classes Trail of Bits.

```python
"""
SWC Registry + Trail of Bits vulnerability classification.

Source unique de vérité pour les catégories de vulnérabilités smart contract.
Deux taxonomies supportées : SWC (swcregistry.io) et Trail of Bits (4-level).
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SWCEntry:
    """Entrée du SWC Registry."""
    swc_id: str              # "SWC-107"
    title: str               # "Reentrancy"
    description: str          # Description courte
    severity_default: str     # "high" (tob_4level)
    tob_class: str           # "undefined_behavior"
    relationships: List[str]  # SWC-IDs liés


# Trail of Bits vulnerability classes (cf. audit LooksRare, Origin Protocol)
TOB_CLASSES: List[str] = [
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
TOB_4LEVEL: List[str] = ["high", "medium", "low", "informational"]
SWC_5LEVEL: List[str] = ["critical", "high", "medium", "low", "informational"]

# Mapping SWC → entrées (les 30 plus courantes)
SWC_REGISTRY: Dict[str, SWCEntry] = { ... }
# Claude Code DOIT peupler ce dictionnaire avec au minimum les entrées suivantes :
# SWC-100 (Function Default Visibility)
# SWC-101 (Integer Overflow and Underflow)
# SWC-104 (Unchecked Call Return Value)
# SWC-105 (Unprotected Ether Withdrawal)
# SWC-106 (Unprotected SELFDESTRUCT)
# SWC-107 (Reentrancy)
# SWC-108 (State Variable Default Visibility)
# SWC-110 (Assert Violation)
# SWC-111 (Use of Deprecated Solidity Functions)
# SWC-112 (Delegatecall to Untrusted Callee)
# SWC-113 (DoS with Failed Call)
# SWC-114 (Transaction Order Dependence / Front-Running)
# SWC-115 (Authorization through tx.origin)
# SWC-116 (Block values as a proxy for time)
# SWC-117 (Signature Malleability)
# SWC-118 (Incorrect Constructor Name)
# SWC-119 (Shadowing State Variables)
# SWC-120 (Weak Sources of Randomness)
# SWC-121 (Missing Protection against Signature Replay)
# SWC-123 (Requirement Violation)
# SWC-124 (Write to Arbitrary Storage Location)
# SWC-125 (Incorrect Inheritance Order)
# SWC-126 (Insufficient Gas Griefing)
# SWC-127 (Arbitrary Jump with Function Type Variable)
# SWC-128 (DoS With Block Gas Limit)
# SWC-129 (Typographical Error)
# SWC-130 (Right-To-Left-Override control character)
# SWC-131 (Presence of unused variables)
# SWC-132 (Unexpected Ether balance)
# SWC-133 (Hash Collisions With Multiple Variable Length Arguments)
# SWC-134 (Message call with hardcoded gas amount)
# SWC-135 (Code With No Effects)
# SWC-136 (Unencrypted Private Data On-Chain)

# Helpers
def get_swc(swc_id: str) -> Optional[SWCEntry]: ...
def get_swc_by_tob_class(tob_class: str) -> List[SWCEntry]: ...
def map_severity_5to4(severity: str) -> str:
    """SWC 5-level → ToB 4-level. 'critical' → 'high'."""
    ...
def map_severity_4to5(severity: str) -> str:
    """ToB 4-level → SWC 5-level (inverse). 'high' → 'high' (no critical)."""
    ...
```

**Tests** (`tests/test_adr014_swc_taxonomy.py`) — ≥5 tests :
- Toutes les 30+ entrées SWC ont un `tob_class` valide (dans `TOB_CLASSES`)
- `get_swc("SWC-107")` retourne reentrancy
- `get_swc_by_tob_class("undefined_behavior")` contient SWC-107
- `map_severity_5to4("critical")` → `"high"`
- `map_severity_4to5("high")` → `"high"` (pas d'upgrade en critical)
- Toutes les entrées ont `severity_default` dans `TOB_4LEVEL`

## L1.2 — `services/audit/__init__.py`

Fichier vide ou commentaire ADR-014 uniquement. Pas de re-exports à ce stade.

## L1.3 — `services/audit/contract_slicer.py`

**Nouveau fichier.** Le slicer Solidity `function_level_v1`.

Dataclasses `ContractUnit` et `ContractSliceResult` exactement comme dans ADR-014 §2.2.

Fonction principale :

```python
def slice_contract(
    contract_path: str,
    strategy: str = "function_level_v1",
) -> ContractSliceResult:
    """
    Découpe un fichier Solidity en unités auditables.
    
    Args:
        contract_path: Chemin vers le fichier .sol
        strategy: Stratégie de découpe (seule "function_level_v1" implémentée)
    
    Returns:
        ContractSliceResult avec les ContractUnit extraites
    """
```

**Implémentation `function_level_v1`** :

1. Lire le fichier, calculer `contract_hash` (SHA-256)
2. Extraire le nom du contrat (regex : `contract\s+(\w+)`)
3. Extraire les imports et héritages (lignes `import` + `is` dans la déclaration)
4. Pour chaque fonction/modifier/constructor/fallback/receive :
   - Regex robuste : `function\s+(\w+)\s*\(` avec gestion des accolades imbriquées
     pour capturer le corps complet
   - Extraire `visibility` (public/external/internal/private — défaut : public si absent pour Solidity < 0.5)
   - Classer `access_level` :
     - `"admin"` si modifiers contient onlyOwner, onlyAdmin, onlyRole, etc.
     - `"role_restricted"` si AccessControl, hasRole, etc.
     - `"contract_only"` si internal/private sans modifier public
     - `"public"` sinon
   - Extraire `modifiers` (entre `)` et `{`)
   - Extraire `state_writes` : grep pour `=` sur variables d'état (hors locales)
   - Extraire `external_calls` : patterns `.call(`, `.delegatecall(`, `.send(`, `.transfer(`, interfaces
   - Calculer `line_range`
   - Construire `context_imports` (cap 500 tokens ≈ ~2000 chars)
5. Filtrage : marquer `pure`/`view` sans external_calls comme skipped
6. Retourner `ContractSliceResult`

**Point critique** : le slicer doit être testé sur du vrai code Solidity.
Claude Code DOIT créer un répertoire `tests/fixtures/contracts/` avec au minimum
3 fichiers `.sol` de test :

```
tests/fixtures/contracts/
├── reentrancy_vulnerable.sol    # Contrat avec SWC-107 (classique withdraw)
├── access_control_simple.sol    # Contrat avec onlyOwner + fonctions publiques
└── safe_token.sol               # Contrat propre (OpenZeppelin pattern)
```

Ces fixtures sont des fichiers Solidity minimalistes (20-50 lignes chacun),
PAS des contrats copiés depuis un projet externe. Ils sont écrits par Claude Code
spécifiquement pour tester le slicer.

**Tests** (`tests/test_adr014_contract_slicer.py`) — ≥7 tests :
- `slice_contract("reentrancy_vulnerable.sol")` → ≥1 unit avec `external_calls` non vide
- `slice_contract("access_control_simple.sol")` → ≥1 unit avec `access_level="admin"`
- `slice_contract("safe_token.sol")` → toutes les units ont `visibility` peuplé
- `contract_hash` est un SHA-256 hex de 64 chars
- `slice_strategy` est `"function_level_v1"`
- Les fonctions `view`/`pure` sans external calls sont dans `skipped_units`
- `context_imports` contient les lignes `import` du fichier
- `line_range` est un tuple (start, end) avec start < end

## L1.4 — Frame `smartcontract_audit_v1.0`

Dans `services/solana/metrological_frame.py` :

Ajouter `create_smartcontract_audit_frame()` exactement comme dans ADR-014 §2.5.
Enregistrer dans `PREDEFINED_FRAMES`.

**Tests** (`tests/test_adr014_frame.py`) — ≥3 tests :
- `"smartcontract_audit_v1.0"` dans `PREDEFINED_FRAMES`
- `frame.domain == "smart_contract_security"`
- `frame.parameters["severity_taxonomy"] == "tob_4level"`
- Hash déterministe (2 appels → même hash)

## L1.5 — Checkpoint Lot 1

```bash
pytest tests/test_adr014_*.py -v --tb=short
# → ≥15 passed, 0 failed

pytest tests/ -q --tb=no 2>&1 | tail -3
# → ≥698 + 15 = ≥713 passed, ≤14 skipped, 0 failed
```

**Livrable** : rapport à transmettre à Sim avec les deux sorties pytest.

---

# LOT 2 — PROMPTS + INTÉGRATION PIPELINE

Dépend du Lot 1. Branche les prompts d'audit dans le pipeline ESMM existant.

## L2.1 — Templates AUDIT dans `cycle_prompts.py`

Ajouter 3 nouveaux CycleType dans l'enum :

```python
ASSESS_AUDIT = "assess_audit"
CHALLENGE_AUDIT = "challenge_audit"
ADJUDICATE_AUDIT = "adjudicate_audit"
```

Ajouter les templates et system prompts correspondants.
Le SYSTEM_PROMPT de ASSESS_AUDIT doit inclure le format JSON de sortie
tel que défini dans ADR-014 §2.4 (avec `swc_id`, `tob_class`, `severity`,
`verdict`, `confidence`, `evidence`, `affected_lines`).

**Attention** : les templates AUDIT utilisent des placeholders différents
des templates VERIFY. ASSESS_AUDIT utilise `{contract_context}`,
`{function_code}`, `{unit_metadata}` — pas `{claim}`.

Mettre à jour `CYCLE_TEMPLATES` et `SYSTEM_PROMPTS` avec les 3 nouveaux types.

## L2.2 — `CLAIM_TYPE_PENALTIES` dans `pipeline.py`

Ajouter une seule ligne :

```python
CLAIM_TYPE_PENALTIES = {
    "empirical": 1.0,
    "definitional": 0.90,
    "normative": 0.70,
    "speculative": 0.75,
    "security_audit": 1.0,  # ADR-014 — pas de pénalité (claim empirique)
}
```

## L2.3 — Tests Lot 2

`tests/test_adr014_prompts.py` — ≥5 tests :
- `CycleType.ASSESS_AUDIT` existe dans l'enum
- `get_system_prompt(CycleType.ASSESS_AUDIT)` contient "SWC" et "vulnerability"
- `get_template(CycleType.ASSESS_AUDIT)` contient `{function_code}`
- Les 3 nouveaux types sont dans `CYCLE_TEMPLATES` et `SYSTEM_PROMPTS`
- `CLAIM_TYPE_PENALTIES["security_audit"]` == 1.0

`tests/test_adr014_prompts.py` — ≥5 tests supplémentaires :
- Le prompt ASSESS_AUDIT formaté avec un vrai `ContractUnit` produit un string
  contenant `<FUNCTION_UNDER_AUDIT>` et `<UNIT_METADATA>`
- Le prompt CHALLENGE_AUDIT contient `{peer_verdict}`
- Le prompt ADJUDICATE_AUDIT contient `{all_verdicts}`
- Les 3 system prompts exigent la sortie en JSON
- Les 3 system prompts contiennent "MUST be in English"

## L2.4 — Checkpoint Lot 2

```bash
pytest tests/test_adr014_*.py -v --tb=short
# → ≥25 passed, 0 failed

pytest tests/ -q --tb=no 2>&1 | tail -3
# → baseline + ≥25 nouveaux, 0 failed
```

---

# LOT 3 — AUDIT RUNNER + CLI + DB

Le cœur de l'orchestration. Relie le slicer au pipeline VERIFY.

## L3.1 — `services/audit/audit_runner.py`

**Nouveau fichier.** Orchestration complète d'un audit.

```python
@dataclass
class AuditResult:
    """Résultat complet d'un audit de smart contract."""
    contract_path: str
    contract_hash: str
    contract_name: str
    slice_result: ContractSliceResult
    unit_results: List[Dict[str, Any]]   # PipelineResult par unit
    aggregate_severity: str               # Maillon faible (pré-indexation)
    aggregate_consensus: float            # Min consensus_score
    total_vulnerabilities: int
    total_units_audited: int
    total_units_skipped: int
    duration_ms: float
    db_path: str                          # "data/epp_audit_devnet.db"
    errors: List[str]


async def run_audit(
    contract_path: str,
    db: "ISpaceDB",
    models: Optional[List[str]] = None,
    frame: str = "smartcontract_audit_v1.0",
    use_slither: bool = False,
    use_cache: bool = True,
) -> AuditResult:
    """
    Orchestre un audit complet :
    1. slice_contract() → N units
    2. Pour chaque unit (priorité : external_calls > state_writes > reste) :
       a. Formater la claim AUDIT depuis la ContractUnit
       b. Appeler run_pipeline() en mode VERIFY avec les prompts AUDIT
       c. Collecter le PipelineResult
    3. Agréger les résultats (pré-indexation : maillon faible)
    4. Retourner AuditResult
    """
```

**Points critiques** :
- Le `db` passé est une instance pointant vers `data/epp_audit_devnet.db`, jamais `data/epp_devnet.db`
- Chaque appel à `run_pipeline()` passe `metrological_frame="smartcontract_audit_v1.0"`
- Le `ESMMRunConfig` doit avoir `input_mode="verify"` et `original_claim` = le prompt AUDIT formaté
- L'ordre d'audit des units est déterministe : fonctions avec `external_calls` d'abord, puis `state_writes`, puis le reste

## L3.2 — Commande CLI `epp audit`

Dans `cli/epp_cli.py`, ajouter :

```python
@cli.command("audit")
@click.argument("contract_path", type=click.Path(exists=True))
@click.option("--frame", "-f", default="smartcontract_audit_v1.0")
@click.option("--models", "-m", default=3, help="Number of models")
@click.option("--slither/--no-slither", default=False)
@click.option("--output", "-o", type=click.Choice(["json", "text"]), default="text")
def audit(contract_path, frame, models, slither, output):
    """Run epistemic audit on a smart contract.
    
    Example:
        epp audit contracts/TokenVault.sol --models 3
    """
```

La commande :
1. Ouvre/crée `data/epp_audit_devnet.db` (pas la DB principale)
2. Appelle `run_audit()`
3. Affiche le résultat (index structuré : chaque unit, verdict, entropy, severity)
4. En mode JSON : dump complet de `AuditResult`

## L3.3 — Initialisation `data/epp_audit_devnet.db`

Le schéma est identique à `data/epp_devnet.db` (`schema.sql`). L'initialisation
se fait via le même `ISpaceDB.initialize()`. Seul le path change.

Dans `config.yaml`, ajouter :

```yaml
audit:
  enabled: true
  db_path: "data/epp_audit_devnet.db"
  slice_strategy: "function_level_v1"
  severity_taxonomy: "tob_4level"
  slither_path: "slither"  # ou chemin absolu
```

## L3.4 — Tests Lot 3

`tests/test_adr014_audit_runner.py` — ≥10 tests :
- `run_audit()` sur `reentrancy_vulnerable.sol` avec MockProvider retourne un `AuditResult`
- `AuditResult.contract_hash` est un SHA-256 de 64 chars
- `AuditResult.total_units_audited` > 0
- `AuditResult.aggregate_severity` est dans `TOB_4LEVEL`
- `AuditResult.db_path` contient "epp_audit_devnet"
- `AuditResult.errors` est une liste (peut être vide)
- L'audit utilise le frame `smartcontract_audit_v1.0`
- Les units avec `external_calls` sont auditées avant les autres
- Les attestations sont stockées dans `epp_audit_devnet.db`, pas dans `epp_devnet.db`
- Le cache fonctionne : 2 runs sur le même contrat → le 2ème est plus rapide (ADR-013)

**Important** : tous les tests utilisent `MockProvider` — pas d'Ollama requis.
Les tests doivent mocker la réponse LLM pour retourner un JSON d'audit valide
(avec `swc_id`, `severity`, `verdict`, etc.).

## L3.5 — Checkpoint Lot 3

```bash
pytest tests/test_adr014_*.py -v --tb=short
# → ≥35 passed, 0 failed

pytest tests/ -q --tb=no 2>&1 | tail -3
# → baseline + ≥35 nouveaux, 0 failed
```

---

# LOT 4 — SLITHER + BENCHMARK (parallélisable, optionnel)

Ce lot est important pour la qualité du pitch mais pas bloquant pour la démo.
Si le temps manque, le Lot 3 suffit pour une démo fonctionnelle.

## L4.1 — `services/sources/adapters/slither_adapter.py`

Pattern identique aux autres adapters (ADR-012). Exécution locale de Slither.

Si Slither n'est pas installé, l'adapter retourne une erreur propre (pas de crash).
L'`audit_runner` vérifie `use_slither` et l'installe optionnellement.

## L4.2 — `services/audit/audit_benchmark.py`

Script standalone. Dataclass `BenchmarkResult` comme dans ADR-014 §2.8.

Dataset minimal : 3-5 contrats de `crytic/not-so-smart-contracts` copiés dans
`tests/fixtures/contracts/benchmark/` avec un fichier `ground_truth.json` qui
liste les vulnérabilités connues par contrat.

Le benchmark :
1. Pour chaque contrat : `run_audit()` avec `use_cache=False`
2. Compare avec `ground_truth.json`
3. Calcule precision, recall, F1 par catégorie
4. Produit un rapport markdown dans `tests/audits/BENCHMARK_REPORT.md`

## L4.3 — Tests Lot 4

≥5 tests sur le benchmark (structure du rapport, calcul F1, etc.).

## L4.4 — Checkpoint Lot 4

```bash
pytest tests/test_adr014_*.py -v --tb=short
# → ≥40 passed, 0 failed
```

---

## RÈGLES TRANSVERSALES

### Structure de fichiers attendue en fin d'implémentation

```
services/audit/
├── __init__.py
├── swc_taxonomy.py          # L1.1
├── contract_slicer.py       # L1.3
├── audit_runner.py           # L3.1
└── audit_benchmark.py        # L4.2

services/sources/adapters/
├── slither_adapter.py        # L4.1 (nouveau)
├── ... (existants inchangés)

services/solana/
├── metrological_frame.py     # L1.4 (modifié : +1 frame)

services/esmm/
├── cycle_prompts.py          # L2.1 (modifié : +3 cycle types)
├── pipeline.py               # L2.2 (modifié : +1 ligne CLAIM_TYPE_PENALTIES)

cli/
├── epp_cli.py                # L3.2 (modifié : +commande audit)

config.yaml                   # L3.3 (modifié : +section audit)

tests/
├── fixtures/contracts/
│   ├── reentrancy_vulnerable.sol
│   ├── access_control_simple.sol
│   └── safe_token.sol
├── test_adr014_swc_taxonomy.py
├── test_adr014_contract_slicer.py
├── test_adr014_frame.py
├── test_adr014_prompts.py
├── test_adr014_audit_runner.py
└── test_adr014_benchmark.py   # L4

data/
├── epp_audit_devnet.db        # Créé par le CLI ou les tests
```

### Conventions de nommage

- Tous les tests ADR-014 : `test_adr014_*.py`
- Tous les nouveaux modules : dans `services/audit/` (sauf adapter et frame)
- Les fixtures Solidity : dans `tests/fixtures/contracts/`

### Protocole RED-GREEN-FIX

Pour chaque test :
1. Le test DOIT être écrit AVANT le code qu'il teste
2. Le test DOIT échouer sur le code existant (RED)
3. La correction minimale fait passer le test (GREEN)
4. `pytest tests/` complet confirme la non-régression (FIX)

En pratique pour ce plan : Claude Code peut écrire les tests et le code
dans le même lot, mais chaque test doit avoir au moins une assertion
sur une VALEUR (pas juste `is not None` — contrôle C6).

### Ce qui est interdit

- ❌ Modifier la logique de `run_pipeline()` (l'audit est un consommateur)
- ❌ Modifier `orchestrator.py` ou `cycle_manager.py`
- ❌ Écrire dans `data/epp_devnet.db` depuis le code d'audit
- ❌ Importer `services/audit/` depuis un module existant (sauf `epp_cli.py`)
- ❌ Ajouter des dépendances Python sans les documenter dans requirements.txt
- ❌ Copier du code Solidity sous copyright sans vérifier la licence

---

*PLAN_IMPL_ADR014.md — v1.0*
*Rédigé par Claude Opus (Auditeur Adversarial)*
*Validé par Sim*
*Date : 2026-03-05*
