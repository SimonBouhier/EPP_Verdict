---
title: "ADR-015 : Le Grand Découplage — Architecture Tripartite Kernel / Adapters / Domains"
description: "Statut : Différé (post-hackathon Colosseum)"
---
**Date** : 2026-03-09
**Statut** : Différé (post-hackathon Colosseum)
**Auteur** : Sim (architecte) + Opus (gatekeeper)
**Dépendances** : ADR-001 (obsolescence modèles), ADR-012 (sources autoritaires), ADR-014 (pattern audit)

---

## 1. Contexte

EPP a grandi organiquement : pipeline ESMM hérité de Lyra, puis audit smart
contracts (ADR-014), puis sources déterministes (ADR-012), puis géopolitique
(ADR-016). Chaque ajout fonctionne mais la structure physique des répertoires
ne reflète pas la séparation logique qui existe déjà dans le code.

Le risque : présenter une "usine à gaz" au lieu d'un "framework modulaire".

La réalité : le découplage fonctionnel est DÉJÀ en place. Le Kernel
(cycle_manager, consensus_engine, pipeline) ne sait rien de Solidity ni
d'ACLED. L'audit est un consommateur du pipeline (ADR-014 §5.1). ACLED
est un SourceAdapter comme les autres (ADR-012). Ce qui manque, c'est la
matérialisation physique de cette séparation.

---

## 2. Décision

Restructurer les répertoires en trois couches explicites sans modifier
la logique existante. C'est un refactoring de surface (déplacements +
imports), pas une réécriture.

### A. Le Kernel EPP (agnostique au domaine)

Tout ce qui relève de la mécanique du débat. Ne doit contenir AUCUNE
référence à Solidity, ACLED, SWC, ou tout domaine spécifique.

```
services/esmm/                    # Inchangé — c'est déjà le Kernel
    orchestrator.py               # Pilote les runs ESMM
    cycle_manager.py              # Exécution des cycles
    cycle_prompts.py              # Templates EXPLORE + VERIFY (génériques)
    consensus_engine.py           # Vote, normalisation, fingerprinting
    triplet_extractor.py          # Extraction + parsing
    verdict_encoder.py            # Verdict → triplets
    pipeline.py                   # Pont orchestrator → crystallize
    attestation.py                # Cristallisation
    ...
```

**Règle d'or** : si `cycle_manager.py` contient un `if "SWC-107" in claim`,
la modularité est rompue. Le Kernel traite du texte et des probabilités.

### B. La Couche Adapters (traducteurs du monde réel)

Transforme les données externes en formats que le Kernel peut traiter.

```
services/sources/                 # Existe déjà (ex-services/rwa/)
    adapters/
        base.py                   # ABC SourceAdapter
        opensanctions.py          # Sanctions
        ofac.py                   # OFAC
        eu_cfsp.py                # EU
        verra_vcs.py              # Carbone
        acled.py                  # ADR-016 — Conflits armés
        slither_adapter.py        # ADR-014 — Analyse statique Solidity
        __init__.py               # _REGISTRY + get_adapter()
```

Chaque adapter a une seule responsabilité : fetch + normalize + version.
Le Kernel ne sait pas quel adapter est utilisé.

### C. La Couche Domains (plugins de savoir)

Chaque domaine applicatif contient ses taxonomies, prompts spécialisés,
scripts de benchmark, et runners. Un domain est un CONSOMMATEUR du Kernel.

```
domains/
    smartcontracts/               # ADR-014
        swc_taxonomy.py           # 33 SWC + 8 classes ToB
        contract_slicer.py        # Découpe Solidity
        audit_runner.py           # Orchestration slice → pipeline
        audit_prompts.py          # ASSESS_AUDIT / CHALLENGE_AUDIT / ADJUDICATE_AUDIT
        benchmark_config.py       # Ground truth, fixtures
    geopolitics/                  # ADR-016
        jiang_claims.py           # Catalogue de claims
        scenario_jiang.py         # Script dual-path
        geopolitical_prompts.py   # Prompts spécialisés (si nécessaire)
    # Futurs domaines :
    # legal/                      # Diagnostics juridiques
    # medical/                    # Diagnostics médicaux
    # defi/                       # Audit DeFi protocols
```

**Pourquoi** : ajouter un nouveau domaine = créer un répertoire + quelques
fichiers. Zéro modification du Kernel. C'est la scalabilité que Colosseum
veut voir.

---

## 3. Ce qui change (physiquement)

| Actuel | Cible | Type |
|:---|:---|:---|
| `services/audit/` | `domains/smartcontracts/` | git mv |
| `services/audit/swc_taxonomy.py` | `domains/smartcontracts/swc_taxonomy.py` | git mv |
| `services/audit/contract_slicer.py` | `domains/smartcontracts/contract_slicer.py` | git mv |
| `services/audit/audit_runner.py` | `domains/smartcontracts/audit_runner.py` | git mv |
| `demos/scenario_jiang.py` | `domains/geopolitics/scenario_jiang.py` | git mv |
| `cycle_prompts.py` (prompts AUDIT) | Extraits vers `domains/smartcontracts/audit_prompts.py` | Extraction |
| Imports dans CLI, tests, scripts | Mis à jour | grep + sed |

### Ce qui ne change PAS

- `services/esmm/` — le Kernel reste en place
- `services/sources/` — les adapters restent en place
- `services/solana/` — la couche transport reste en place
- `services/providers/` — les providers LLM restent en place
- `database/` — le storage reste en place
- `programs/epp/` — le programme Rust reste en place

---

## 4. Étapes de migration

### Étape 1 — Normaliser l'interface d'entrée

Vérifier que le Kernel ne contient aucune référence directe aux domains :

```bash
grep -rn "SWC\|swc_taxonomy\|contract_slicer\|audit_runner\|ACLED\|acled\|jiang" \
    services/esmm/ --include="*.py"
```

Si des références existent dans cycle_prompts.py (templates AUDIT),
les extraire vers le domain concerné avec un mécanisme d'injection :

```python
# Kernel (cycle_prompts.py) :
# Les templates de base EXPLORE + VERIFY restent ici.
# Les templates de domain sont injectés par le domain au runtime.

def register_domain_templates(templates: Dict[CycleType, List[str]]) -> None:
    """Permet à un domain d'enregistrer ses templates spécialisés."""
    for cycle_type, tmpl_list in templates.items():
        CYCLE_TEMPLATES[cycle_type].extend(tmpl_list)
```

### Étape 2 — Créer la structure domains/

```bash
mkdir -p domains/smartcontracts domains/geopolitics
```

### Étape 3 — Déplacer les fichiers

Migration atomique avec audit C1 complet :

```bash
# 1. Diagnostic pré-migration
grep -rn "services/audit\|services.audit\|from.*audit" --include="*.py" .

# 2. Déplacement
git mv services/audit/ domains/smartcontracts/

# 3. Mise à jour imports
# Script Python dédié (comme la migration rwa → sources)

# 4. Audit C1 post-migration
grep -rn "services/audit" --include="*.py" .
# Doit retourner 0 résultats

# 5. Non-régression
pytest tests/ -q
```

### Étape 4 — Externaliser les prompts AUDIT

Extraire de `cycle_prompts.py` les templates ASSESS_AUDIT, CHALLENGE_AUDIT,
ADJUDICATE_AUDIT vers `domains/smartcontracts/audit_prompts.py`.

Le domain s'enregistre au démarrage :

```python
# domains/smartcontracts/__init__.py
from services.esmm.cycle_prompts import register_domain_templates
from .audit_prompts import AUDIT_TEMPLATES

register_domain_templates(AUDIT_TEMPLATES)
```

### Étape 5 — Le Bridge Solana en mode "Fire and Forget" (optionnel)

Actuellement le pipeline attend la réponse Solana. Découpler :

```python
# services/solana/anchor_daemon.py
class AnchorDaemon:
    """
    Surveille les nouvelles attestations en DB et les soumet on-chain.
    File d'attente async. Le pipeline ne bloque pas.
    """
    async def watch_and_submit(self):
        while True:
            pending = await db.get_pending_attestations()
            for att in pending:
                try:
                    tx = await client.submit_attestation(att)
                    await db.update_attestation_solana_tx(att, tx)
                except Exception:
                    await db.mark_submission_failed(att)
            await asyncio.sleep(10)
```

Ceci évite qu'un benchmark de 30 minutes plante à cause d'un timeout RPC.

---

## 5. Risques

| Risque | Probabilité | Mitigation |
|:---|:---|:---|
| Imports cassés post-migration | Haute | Script diagnostic + C1 + baseline pytest |
| Tests référençant les anciens chemins | Haute | grep exhaustif + mise à jour |
| cycle_prompts.py trop couplé aux domains | Moyenne | Mécanisme register_domain_templates |
| Regression sur le chemin déterministe | Faible | source_anchor_builder.py déjà découplé |

---

## 6. Bénéfices pour Colosseum

- **Maintenabilité** : survie à l'évolution des modèles (ADR-001)
- **Scalabilité** : 10 nouveaux langages = 10 domains, 0 modif Kernel
- **Professionnalisme** : architecte système, pas codeur brouillon
- **Pitch visuel** : un slide avec 3 boîtes (Kernel / Adapters / Domains)
  vaut plus que 100 lignes de code

---

## 7. Timing

**Différé à post-hackathon.** Les raisons :

1. Le découplage fonctionnel existe déjà — le Kernel ne sait rien des domains
2. Un refactoring physique risque de casser la baseline (791 tests)
3. Les 5 fixes du Lot A + ADR-016 sont plus impactants pour la demo
4. Le pitch peut décrire l'architecture tripartite sans qu'elle soit
   physiquement matérialisée dans les répertoires

Le Grand Découplage sera le premier chantier post-Colosseum.
