# PLAN PHASE 1.2 — Fix désérialiseur on-chain + tests relecture

> **Auteur** : Claude Opus (auditeur adversarial)
> **Exécutant** : Claude Code
> **Date** : 17 février 2026
> **Protocole** : RED-GREEN-FIX obligatoire — ordre d'exécution strict
> **Prérequis** : Baseline `pytest tests/ --tb=short` avant toute modification

---

## RÉSUMÉ DU BUG

Le désérialiseur `_deserialize_attestation_account()` dans `services/solana/client.py`
omet le champ `last_revalidated: i64` (8 bytes) présent dans le struct Rust (`state.rs:70`).

**Conséquence** : Tous les champs après `timestamp` sont décalés de 8 bytes.
`validation_count`, `protocol_version`, `is_challenge`, `challenged_attestation`
lisent des données corrompues sur un vrai compte on-chain.

**Preuve** : `state.rs::EpistemicAttestation::SIZE` = 462 bytes.
Le désérialiseur Python consomme 446 + 8 (discriminator) = 454 ≠ 462. Il manque 8 bytes.

**Note** : `_build_and_send_submit_tx()` ne transmet PAS `last_revalidated` dans
l'instruction — c'est correct, le programme Rust le set lui-même (`lib.rs:85`).
Mais le **compte on-chain** contient bien ce champ. Le désérialiseur lit le compte,
pas l'instruction.

---

## FICHIERS MODIFIÉS

| Fichier | Action |
|---------|--------|
| `services/solana/client.py` | Fix désérialiseur (3 lignes) |
| `tests/test_phase4_solana.py` | Fix 2 tests existants (buffer + calcul taille) |
| `tests/test_solana_deserialize.py` | Nouveau fichier — 5 tests |
| `CHANGELOG.md` | Entrée Phase 1.2 |

---

## ORDRE D'EXÉCUTION (STRICT — NE PAS RÉARRANGER)

### ÉTAPE 0 — Baseline

```bash
pytest tests/ --tb=short
```

Noter le compteur exact (attendu : ~548 passed). C'est la référence.

---

### ÉTAPE 1 — Fix `services/solana/client.py`

Modifier **uniquement** `_deserialize_attestation_account()`.

#### 1A — Ajouter `last_revalidated` entre `timestamp` et `validation_count`

Code actuel (FAUX) :
```python
timestamp = struct.unpack("<q", read(8))[0]
validation_count = struct.unpack("<H", read(2))[0]
```

Code corrigé :
```python
timestamp = struct.unpack("<q", read(8))[0]
last_revalidated = struct.unpack("<q", read(8))[0]  # ← AJOUT
validation_count = struct.unpack("<H", read(2))[0]
```

#### 1B — Ajouter dans le dict de retour

Ajouter `"last_revalidated": last_revalidated` dans le dict retourné,
entre `"timestamp"` et `"validation_count"`.

#### 1C — Ajouter assertion de taille en fin de méthode

À la toute fin de `_deserialize_attestation_account()`, après le `return` dict,
ajouter AVANT le return :

```python
if offset != len(data):
    raise ValueError(
        f"Deserialization offset mismatch: consumed {offset} bytes, "
        f"buffer has {len(data)} bytes"
    )
```

Cette assertion est un **filet permanent** contre tout futur décalage.

#### 1D — Ne PAS modifier

- Les signatures des méthodes publiques
- La logique mock
- `_build_and_send_submit_tx()`
- Les constantes CLAIM_HASH_OFFSET et SUBJECT_OFFSET (elles sont correctes)

---

### ÉTAPE 2 — Prouver le RED sur les tests existants

Après le fix de `client.py` (étape 1), **sans toucher aux tests**, exécuter :

```bash
pytest tests/test_phase4_solana.py::TestPDAValidation::test_deserialize_attestation_layout -v
pytest tests/test_phase4_solana.py::TestInstructionSerialization::test_borsh_layout_matches_account_size -v
```

**Résultat attendu** :

- `test_deserialize_attestation_layout` → **FAIL** (le buffer fait 446 bytes,
  le désérialiseur en attend maintenant 454 → `ValueError` ou `struct.error`)
- `test_borsh_layout_matches_account_size` → **PASS** (ce test ne fait que de
  l'arithmétique, il n'appelle pas le désérialiseur — mais son assert `== 446`
  est FAUX par rapport à la réalité. C'est un test tautologique qui ment.)

**⚠️ Copier/coller le log de cette étape dans le récap de livraison.**
C'est la preuve RED.

---

### ÉTAPE 3 — Fix des 2 tests existants dans `tests/test_phase4_solana.py`

#### 3A — Fix `test_deserialize_attestation_layout` (L195-238)

Insérer entre la ligne `timestamp` et la ligne `validation_count` du buffer :

```python
data += struct.pack("<q", 1700000000)  # last_revalidated
```

Ajouter dans les assertions :

```python
assert result["last_revalidated"] == 1700000000
```

#### 3B — Fix `test_borsh_layout_matches_account_size` (L139-152)

Remplacer **tout le corps** du test par :

```python
def test_borsh_layout_matches_account_size(self):
    """La taille sérialisée correspond à l'account size Anchor (462 bytes)."""
    # Account layout from state.rs — CHAQUE champ listé :
    # bump(1) + submitter(32) + claim_hash(32) + subject(64) + predicate(64) +
    # object(128) + consensus_score(2) + models_consulted(1) + models_agreeing(1) +
    # sig_5d(5×2=10) + epistemic_type(1) + confidence_tier(1) + frame_hash(32) +
    # source_anchor(32) + timestamp(8) + last_revalidated(8) + validation_count(2) +
    # protocol_version(2) + is_challenge(1) + challenged_attestation(32)
    expected_data_size = (
        1 + 32 + 32 + 64 + 64 + 128 + 2 + 1 + 1 + 10 + 1 + 1
        + 32 + 32 + 8 + 8 + 2 + 2 + 1 + 32
    )
    assert expected_data_size == 454  # Data sans discriminator
    assert expected_data_size + ACCOUNT_DISCRIMINATOR_SIZE == 462  # == state.rs::SIZE
```

**Supprimer** le commentaire `# Full account with discriminator = 454 (not 462 — the Rust SIZE may include padding)`.
Il est faux : la différence de 8 bytes N'EST PAS du padding, c'est le champ `last_revalidated` qui était omis.

---

### ÉTAPE 4 — Prouver le GREEN sur les tests corrigés

```bash
pytest tests/test_phase4_solana.py::TestPDAValidation::test_deserialize_attestation_layout -v
pytest tests/test_phase4_solana.py::TestInstructionSerialization::test_borsh_layout_matches_account_size -v
```

**Résultat attendu** : Les 2 passent. **Copier le log dans le récap.**

---

### ÉTAPE 5 — Créer `tests/test_solana_deserialize.py`

Nouveau fichier avec 5 tests. Les tests NE nécessitent PAS de connexion Solana —
on construit les bytes manuellement.

Pour instancier `EppSolanaClient` : `SolanaConfig(cluster=SolanaCluster.DEVNET)`.

#### Helper : construire un blob de 454 bytes

Écrire une fonction helper `_build_test_blob()` qui construit un buffer complet
de 454 bytes (sans discriminator) avec des valeurs connues et vérifiables.
Ce helper est réutilisé par plusieurs tests.

Valeurs de référence :
- subject = "solana", predicate = "has_tps", object = "exceeds_3000"
- consensus_score = 8500 (u16, soit 0.85)
- models_consulted = 3, models_agreeing = 2
- sig_agreement = 7500 (0.75), sig_semantic_consistency = 9000 (0.90),
  sig_centrality = 7000 (0.70), sig_stability = 8000 (0.80),
  sig_relation_diversity = 6000 (0.60)
- epistemic_type = 0 (foundational), confidence_tier = 2 (validated)
- timestamp = 1700000000, last_revalidated = 1700000000
- validation_count = 1, protocol_version = 100
- is_challenge = False

#### TEST 1 — `test_roundtrip_serialize_deserialize`

```
But : Vérifier que les données survivent au roundtrip bytes → Python
Méthode :
  1. Construire le blob de 454 bytes via le helper
  2. Appeler _deserialize_attestation_account(blob)
  3. Vérifier les valeurs EXACTES (pas de "is not None")

Assertions obligatoires :
  - assert result["subject"] == "solana"
  - assert result["predicate"] == "has_tps"
  - assert result["object"] == "exceeds_3000"
  - assert result["consensus_score"] == pytest.approx(0.85, abs=0.0001)
  - assert result["signature_5d"]["agreement"] == pytest.approx(0.75, abs=0.0001)
  - assert result["signature_5d"]["semantic_consistency"] == pytest.approx(0.90, abs=0.0001)
  - assert result["timestamp"] == 1700000000
  - assert result["last_revalidated"] == 1700000000
  - assert result["validation_count"] == 1
  - assert result["protocol_version"] == 100
  - assert result["is_challenge"] is False
  - assert result["epistemic_type"] == "foundational"
  - assert result["confidence_tier"] == "validated"
```

#### TEST 2 — `test_deserialize_invalid_size`

```
But : Rejeter les données de taille incorrecte
Méthode :
  - Appeler _deserialize_attestation_account(b"\x00" * 100)
  - Attendre ValueError (levée par l'assertion de taille ajoutée en étape 1C)
  - Tester aussi avec un buffer trop long (500 bytes)
```

#### TEST 3 — `test_claim_hash_offset_matches_layout`

```
But : Vérifier que CLAIM_HASH_OFFSET (41) est correct
Méthode :
  1. Construire le blob de 454 bytes avec claim_hash = b"\xAA" * 32
  2. Désérialiser
  3. Vérifier result["claim_hash"] == "aa" * 32
  4. Vérifier l'arithmétique : ACCOUNT_DISCRIMINATOR_SIZE + 1 + 32 == 41
```

#### TEST 4 — `test_subject_offset_matches_layout`

```
But : Vérifier que SUBJECT_OFFSET (73) est correct
Méthode :
  1. Construire le blob avec subject = "test_subject"
  2. Désérialiser
  3. Vérifier result["subject"] == "test_subject"
  4. Vérifier l'arithmétique : ACCOUNT_DISCRIMINATOR_SIZE + 1 + 32 + 32 == 73
```

#### TEST 5 — `test_roundtrip_float_through_bytes` (hypothesis)

```
But : Roundtrip float → u16 → LE bytes → u16 → float sans perte
Méthode :
  from hypothesis import given, strategies as st
  from services.solana.bridge import float_to_u16, u16_to_float

  @given(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
  def test_roundtrip_float_through_bytes(self, f):
      u16_val = float_to_u16(f)
      packed = struct.pack("<H", u16_val)
      unpacked = struct.unpack("<H", packed)[0]
      restored = u16_to_float(unpacked)
      assert abs(restored - f) <= 0.0001
```

---

### ÉTAPE 6 — Validation complète

```bash
pytest tests/ --tb=short
```

**Attendu** : baseline + 5 nouveaux tests, 0 failed.

Puis vérifications C1 :

```bash
grep -rn "_deserialize_attestation_account\|get_attestation\|query_attestations" \
  --include="*.py" services/ tests/
```

Aucune signature publique ne doit avoir changé.

---

### ÉTAPE 7 — CHANGELOG.md

Ajouter en tête du fichier :

```markdown
## [2026-02-17] Phase 1.2 — Fix désérialiseur on-chain + tests relecture

- client.py: fix _deserialize_attestation_account() — ajout champ last_revalidated
  (i64, 8 bytes) manquant entre timestamp et validation_count. Tous les champs après
  timestamp étaient décalés de 8 bytes (bug critique C4).
- client.py: assertion taille en fin de désérialisation (filet anti-décalage permanent)
- test_phase4_solana.py: fix test_deserialize_attestation_layout (buffer +8 bytes)
- test_phase4_solana.py: fix test_borsh_layout_matches_account_size (446→454, +assert ==462)
- 5 tests RED→GREEN dans test_solana_deserialize.py (roundtrip, taille invalide,
  offsets claim_hash/subject, hypothesis float)
- Baseline: N → N+5 passed, 0 failed
```

---

## RÉCAP DE LIVRAISON ATTENDU

Claude Code doit fournir dans sa réponse finale :

1. **Log baseline** (étape 0) — compteur avant
2. **Log RED** (étape 2) — les 2 tests existants qui cassent après fix client.py
3. **Log GREEN** (étape 4) — les 2 tests corrigés qui passent
4. **Log pytest complet** (étape 6) — baseline + 5, 0 failed
5. **Log grep C1** (étape 6) — aucun appelant cassé
6. **Diff résumé** — lignes ajoutées/modifiées par fichier

Sans ces 6 preuves, le livrable est rejeté.

---

## CE QUI N'EST PAS DANS CE PLAN

- Modification du programme Rust (lib.rs, state.rs, constants.rs)
- Modification de bridge.py
- Test E2E avec validator Solana réel
- Implémentation de challenge_attestation côté Rust
- Modification des signatures des méthodes publiques du client

---

*PLAN_PHASE_1_2_CLIENT_COMPLET.md — EPP_Verdict*
*Rédigé par Claude Opus — 17 février 2026*
*Intègre le plan initial + 2 corrections Opus (test taille 446→454, ordre RED)*
