# PLAN — Phase 1.2 : Fix & Validate client.py (Relecture on-chain)

> **Auteur** : Claude Opus (auditeur)
> **Exécutant** : Claude Code
> **Prérequis** : Baseline tests à vérifier (`pytest tests/ --tb=short`)
> **Protocole** : RED-GREEN-FIX obligatoire

---

## CONTEXTE

Le fichier `services/solana/client.py` a été étendu avec :
- `_deserialize_attestation_account()` — parseur Borsh des comptes on-chain
- `check_pda_exists()` — vérification d'existence PDA
- `get_attestation()` — lecture d'une attestation par PDA
- `query_attestations_by_claim()` — query memcmp sur claim_hash
- `query_attestations_by_subject()` — query memcmp sur subject
- `_build_and_send_submit_tx()` — construction tx manuelle sans anchorpy

Un bug critique a été identifié dans le désérialiseur. Ce plan corrige le bug et ajoute les tests de validation.

---

## BUG CRITIQUE : OFFSET SHIFT DANS `_deserialize_attestation_account()`

### Le problème

Le layout on-chain (`state.rs`) contient le champ `last_revalidated: i64` (8 bytes) entre `timestamp` et `validation_count`. Le désérialiseur Python **saute ce champ**, ce qui décale tous les champs suivants de 8 bytes.

### Layout Rust (state.rs L67-72) — ordre exact :
```
timestamp: i64             // 8 bytes
last_revalidated: i64      // 8 bytes  ← MANQUANT DANS LE PARSEUR
validation_count: u16      // 2 bytes
protocol_version: u16      // 2 bytes
is_challenge: bool         // 1 byte
challenged_attestation: Pubkey  // 32 bytes
```

### Code actuel (client.py L423-427) — FAUX :
```python
timestamp = struct.unpack("<q", read(8))[0]        # ✅ lit timestamp
validation_count = struct.unpack("<H", read(2))[0]  # ❌ lit les 2 premiers bytes de last_revalidated
protocol_version = struct.unpack("<H", read(2))[0]  # ❌ lit bytes 3-4 de last_revalidated
is_challenge = struct.unpack("<B", read(1))[0]      # ❌ lit byte 5 de last_revalidated
challenged_attestation = read(32)                    # ❌ décalé de 8 bytes, lit hors limites
```

### Correction requise :
```python
timestamp = struct.unpack("<q", read(8))[0]
last_revalidated = struct.unpack("<q", read(8))[0]   # ← AJOUTER
validation_count = struct.unpack("<H", read(2))[0]
protocol_version = struct.unpack("<H", read(2))[0]
is_challenge = struct.unpack("<B", read(1))[0] != 0
challenged_attestation = read(32)
```

Et dans le dict de retour, ajouter `"last_revalidated": last_revalidated` .

---

## ÉTAPE 1 — FIX : Corriger le désérialiseur

### 1.1 — `_deserialize_attestation_account()` dans `client.py`

- Ajouter `last_revalidated = struct.unpack("<q", read(8))[0]` entre `timestamp` et `validation_count`
- Ajouter `"last_revalidated": last_revalidated` dans le dict de retour

### 1.2 — Vérification de la taille totale

Après le fix, le désérialiseur doit consommer exactement **454 bytes** (462 - 8 bytes de discriminator). Ajouter une assertion à la fin de la méthode :

```python
assert offset == len(data), f"Deserialization offset mismatch: read {offset}, expected {len(data)}"
```

Cette assertion sert de **filet de sécurité permanent** contre tout futur décalage.

### 1.3 — Ne PAS modifier

- Les signatures des méthodes publiques (`get_attestation`, `query_attestations_by_*`)
- La logique mock
- Le code de `_build_and_send_submit_tx` (l'instruction ne contient pas `last_revalidated`, c'est normal — le programme Rust le set dans `lib.rs:85`)

---

## ÉTAPE 2 — TESTS RED-GREEN-FIX

### Fichier : `tests/test_solana_deserialize.py` (nouveau fichier)

Tous les tests ci-dessous doivent **échouer AVANT le fix** (RED) puis **passer APRÈS** (GREEN).

### TEST 1 — Roundtrip sérialisation/désérialisation

```
Nom : test_roundtrip_serialize_deserialize
But : Vérifier que les données survivent au roundtrip Python → bytes → Python
Méthode :
  1. Construire un EpistemicAttestation avec des valeurs connues
  2. Appeler attestation_to_anchor_args() pour obtenir les bytes sérialisés
  3. Construire manuellement le blob de 454 bytes (hors discriminator) en reproduisant
     le layout Borsh de state.rs, y compris last_revalidated = timestamp
  4. Appeler _deserialize_attestation_account(blob)
  5. Vérifier les valeurs : consensus_score, subject, sig_agreement, timestamp,
     last_revalidated, validation_count, protocol_version, is_challenge

Assertions obligatoires (pas de "is not None") :
  - assert result["consensus_score"] == pytest.approx(0.85, abs=0.0001)
  - assert result["subject"] == "solana"
  - assert result["signature_5d"]["agreement"] == pytest.approx(0.75, abs=0.0001)
  - assert result["timestamp"] == 1700000000
  - assert result["last_revalidated"] == 1700000000
  - assert result["validation_count"] == 1
  - assert result["protocol_version"] == 100  (ou la valeur u16 correspondante)
  - assert result["is_challenge"] == False
```

### TEST 2 — Taille invalide

```
Nom : test_deserialize_invalid_size
But : Vérifier le rejet des données de taille incorrecte
Méthode :
  - Appeler _deserialize_attestation_account(b"too_short")
  - Attendre une exception (ValueError ou struct.error ou AssertionError)
```

### TEST 3 — Offset cohérence claim_hash

```
Nom : test_claim_hash_offset_matches_layout
But : Vérifier que CLAIM_HASH_OFFSET (41) dans query_attestations_by_claim
      correspond au layout réel
Méthode :
  - Construire un blob de 454 bytes avec un claim_hash connu aux positions [32:64]
    (après bump=1 + submitter=32)
  - Désérialiser et vérifier que claim_hash correspond
  - Vérifier que ACCOUNT_DISCRIMINATOR_SIZE + 1 + 32 == 41
```

### TEST 4 — Offset cohérence subject

```
Nom : test_subject_offset_matches_layout
But : Vérifier que SUBJECT_OFFSET (73) correspond au layout réel
Méthode :
  - Construire un blob avec un subject connu aux positions [64:128] (après bump + submitter + claim_hash)
  - Désérialiser et vérifier que subject correspond
  - Vérifier que ACCOUNT_DISCRIMINATOR_SIZE + 1 + 32 + 32 == 73
```

### TEST 5 (hypothesis) — Roundtrip float/u16/bytes/u16/float

```
Nom : test_roundtrip_float_through_bytes
But : Vérifier que le roundtrip float → u16 → LE bytes → u16 → float est sans perte
Méthode :
  - @given(st.floats(min_value=0.0, max_value=1.0))
  - float_to_u16(f) → struct.pack("<H", val) → struct.unpack("<H") → u16_to_float()
  - Vérifier abs(result - original) <= 0.0001
```

### Important pour les tests

- Les tests ne nécessitent PAS de connexion Solana — on construit les bytes manuellement
- Les tests appellent `_deserialize_attestation_account()` directement (c'est une méthode de la classe, pas besoin de mock RPC)
- Pour instancier `EppSolanaClient` dans les tests, utiliser un config mock (SolanaConfig avec cluster=LOCALNET)

---

## ÉTAPE 3 — VALIDATION

### 3.1 — pytest complet
```bash
pytest tests/ --tb=short
```
Attendu : baseline + 5 nouveaux tests, 0 failed.

### 3.2 — grep C1 (signatures)
Aucune signature publique ne change dans ce plan. Vérification :
```bash
grep -rn "_deserialize_attestation_account\|get_attestation\|query_attestations" --include="*.py" services/ tests/
```

### 3.3 — Vérification layout byte-par-byte

Après le fix, exécuter ce script de vérification :
```python
# Vérifier que le désérialiseur consomme exactement 454 bytes
import struct
# Construire 454 bytes de données de test
data = b'\x00' * 454
client = EppSolanaClient(mock_config)
try:
    result = client._deserialize_attestation_account(data)
    print("OK: 454 bytes consumed without error")
except AssertionError as e:
    print(f"FAIL: {e}")
```

### 3.4 — CHANGELOG
Ajouter une entrée :
```
## [DATE] Phase 1.2 — Fix désérialiseur on-chain + tests relecture

- client.py: fix _deserialize_attestation_account() — ajout champ last_revalidated (i64, 8 bytes)
  manquant entre timestamp et validation_count. Tous les champs après timestamp
  étaient décalés de 8 bytes (bug critique C4).
- client.py: assertion taille en fin de désérialisation (filet anti-décalage)
- 5 tests RED→GREEN (roundtrip, taille invalide, offsets claim_hash/subject, hypothesis float)
- Baseline: N → N+5 passed, 0 failed
```

---

## CE QUI N'EST PAS DANS CE PLAN

- Modification du programme Rust (`lib.rs`, `state.rs`, `constants.rs`) — pas touché
- Modification de `bridge.py` — pas touché (les fonctions d'encodage/décodage sont correctes)
- Test end-to-end avec un validator Solana réel — hors scope (pas de validator dans l'env CI)
- Implémentation de `challenge_attestation` côté Rust — hors scope (Phase 1.1, pas 1.2)

---

## CONTRÔLES POST-LIVRAISON (Claude Opus vérifiera)

| # | Contrôle | Vérification |
|---|----------|-------------|
| C1 | Signatures | grep — aucune signature publique modifiée |
| C3 | Silence | Aucun nouveau `except: pass` |
| C4 | Layout | Comparer les offsets du parseur Python vs state.rs, byte par byte |
| C5 | API | Vérifier `MemcmpOpts` signature vs doc solana-py |
| C6 | Tautologie | Chaque test vérifie des VALEURS, pas juste `is not None` |
| C7 | Pollution | Le nouveau fichier test ne touche aucun singleton |
| C8 | Mocks | Le test roundtrip construit de vrais bytes, pas de mock du parseur |
| C9 | Doc | CHANGELOG mis à jour |
| P7 | Float/u16 | Test hypothesis roundtrip inclus |

---

*PLAN_PHASE_1_2_CLIENT.md — EPP_Verdict*
*Rédigé par Claude Opus — 17 février 2026*
*Bug identifié par audit croisé state.rs ↔ _deserialize_attestation_account()*
