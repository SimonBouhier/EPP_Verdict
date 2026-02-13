# INSTRUCTIONS — Tests Phase 0.1 : Provider Layer

> Consignes pour Claude Code. Crée les fichiers de test suivants dans `tests/`.

---

## AVANT DE COMMENCER

1. Lis CLAUDE.md
2. Vérifie que pytest et pytest-asyncio sont installés :
   ```
   pip install pytest pytest-asyncio
   ```
3. Vérifie que les imports fonctionnent :
   ```python
   from services.providers.base import ModelProvider, EmbeddingProvider, StructuredQuery, StructuredResponse, ModelMetadata
   from services.providers.registry import ProviderRegistry
   from services.providers.multi_provider_rotator import MultiProviderRotator
   ```
   Si ça échoue, corrige le PYTHONPATH ou les imports AVANT d'écrire les tests.

---

## STRUCTURE À CRÉER

```
tests/
  __init__.py          ← vide
  conftest.py          ← fixtures partagées
  test_providers.py    ← ABC + OllamaProvider + OllamaEmbeddings + Registry
  test_rotator.py      ← MultiProviderRotator
```

4 fichiers, pas plus.

---

## FICHIER 1 — `tests/conftest.py`

Ce fichier contient les fixtures partagées. Crée :

### MockProvider (implémentation concrète de ModelProvider pour les tests)

```python
class MockProvider(ModelProvider):
```

Cette classe :
- Accepte au constructeur : `provider_id: str`, `model_id: str`, `responses: List[str]` (réponses prédéfinies), `should_fail: bool = False`
- `generate()` : retourne la prochaine réponse de la liste (circulaire), ou un StructuredResponse avec `success=False` si `should_fail=True`
- `list_models()` : retourne `[self.model_id]`
- `health_check()` : retourne `{"status": "healthy", "connected": True}`
- `get_metadata()` : retourne un ModelMetadata avec `supports_vram_management=False`
- Possède un compteur `generate_count` incrémenté à chaque appel de `generate()`
- Possède un compteur `unload_count` incrémenté à chaque appel de `unload_model()`

### MockVRAMProvider (comme MockProvider mais avec VRAM)

```python
class MockVRAMProvider(MockProvider):
```

- Hérite de MockProvider
- `get_metadata()` retourne `supports_vram_management=True`
- `preload_model()` et `unload_model()` incrémentent des compteurs `preload_count` et `unload_count`
- Permet de vérifier que le rotator appelle bien preload/unload sur les providers qui le supportent

### MockEmbeddingProvider (implémentation concrète de EmbeddingProvider)

```python
class MockEmbeddingProvider(EmbeddingProvider):
```

- Accepte au constructeur : `dimension: int = 768`, `model_id: str = "mock-embed"`
- `embed()` : retourne une liste de `dimension` floats (valeurs fixes, ex: `[0.1] * dimension`)
- `embed_batch()` : appelle `embed()` pour chaque texte
- `get_dimension()` : retourne `self.dimension`
- `get_model_id()` : retourne `self.model_id`
- `get_provider_id()` : retourne `"mock"`

### Fixture `clean_registry`

Fixture pytest qui appelle `ProviderRegistry.clear_all()` (ou vide les dicts internes) AVANT ET APRÈS chaque test. C'est critique — sans ça, les tests avec ProviderRegistry se polluent entre eux.

```python
@pytest.fixture(autouse=True)
def clean_registry():
    # Setup : vider le registry
    ProviderRegistry._model_providers.clear()
    ProviderRegistry._embedding_providers.clear()
    yield
    # Teardown : vider à nouveau
    ProviderRegistry._model_providers.clear()
    ProviderRegistry._embedding_providers.clear()
```

NOTE : si Phase 2 a ajouté `clear_all()`, utilise-le. Sinon accède aux dicts directement.

---

## FICHIER 2 — `tests/test_providers.py`

Organise les tests en classes. Utilise `@pytest.mark.asyncio` pour les tests async.

### Classe TestABCContracts

Tests qui vérifient que les ABC ne peuvent pas être instanciées directement.

| Test | Vérifie |
|------|---------|
| `test_model_provider_not_instantiable` | `ModelProvider()` lève `TypeError` |
| `test_embedding_provider_not_instantiable` | `EmbeddingProvider()` lève `TypeError` |
| `test_mock_provider_is_valid` | `MockProvider(...)` s'instancie sans erreur, est instance de `ModelProvider` |
| `test_mock_embedding_is_valid` | `MockEmbeddingProvider(...)` s'instancie, est instance de `EmbeddingProvider` |

### Classe TestStructuredDataclasses

| Test | Vérifie |
|------|---------|
| `test_structured_query_defaults` | `StructuredQuery(messages=[...])` a les bons défauts (temperature=0.7, max_tokens=4096, etc.) |
| `test_structured_query_keep_alive` | `StructuredQuery(messages=[...], keep_alive="5m")` stocke bien la valeur (Phase 2). Si le champ n'existe pas encore, marque le test `@pytest.mark.skip` |
| `test_structured_response_success` | `StructuredResponse(text="hello", ...)` avec `success=True` |
| `test_structured_response_failure` | `StructuredResponse(text="", success=False, error="timeout")` |
| `test_model_metadata` | `ModelMetadata(provider_id="test", model_id="m1", ...)` stocke tous les champs |

### Classe TestOllamaProvider

Tous les tests mockent `httpx.AsyncClient` — AUCUN appel réseau réel.

Stratégie de mock : utilise `unittest.mock.AsyncMock` pour patcher `httpx.AsyncClient.post` et `httpx.AsyncClient.get`. Crée des `httpx.Response` mockées avec le bon `.json()` et `.status_code`.

| Test | Vérifie |
|------|---------|
| `test_generate_success` | Mock POST /api/chat retourne `{"message": {"content": "réponse"}, "eval_count": 10, "prompt_eval_count": 20}`. Vérifie que `StructuredResponse.text == "réponse"`, `success == True`, `tokens["completion"] == 10`, `tokens["prompt"] == 20` |
| `test_generate_empty_response` | Mock retourne `{"message": {"content": ""}}`. Vérifie `success == True` mais `text == ""` |
| `test_generate_http_error` | Mock lève `httpx.HTTPStatusError` (status 500). Vérifie `success == False`, `error` contient "500" |
| `test_generate_network_error` | Mock lève `httpx.ConnectError`. Vérifie `success == False` |
| `test_generate_retry_on_failure` | (Phase 2) Mock échoue 2 fois puis réussit. Vérifie que `generate()` retourne un succès et que le mock a été appelé 3 fois. Si le retry n'existe pas encore, `@pytest.mark.skip` |
| `test_generate_no_retry_on_404` | (Phase 2) Mock lève HTTPStatusError(404). Vérifie qu'il n'y a PAS de retry (mock appelé 1 seule fois) |
| `test_list_models` | Mock GET /api/tags retourne `{"models": [{"name": "mistral:7b"}, {"name": "llama3:8b"}]}`. Vérifie retour `["mistral:7b", "llama3:8b"]` |
| `test_health_check_healthy` | Mock GET /api/tags réussit. Vérifie `{"status": "healthy", "connected": True, ...}` |
| `test_health_check_unhealthy` | Mock GET /api/tags lève exception. Vérifie `{"connected": False, ...}` |
| `test_preload_model` | Mock POST /api/generate réussit. Vérifie retour `True` |
| `test_unload_model` | Mock POST /api/generate réussit. Vérifie retour `True` |
| `test_metadata` | Vérifie `get_metadata()` retourne `provider_id="ollama"`, `supports_vram_management=True` |
| `test_no_model_raises` | `OllamaProvider(model=None)` puis `generate(...)` lève `ValueError` |

### Classe TestOllamaEmbeddingProvider

| Test | Vérifie |
|------|---------|
| `test_embed_success` | Mock POST /api/embeddings retourne `{"embedding": [0.1, 0.2, ..., 0.768]}`. Vérifie la liste retournée |
| `test_embed_auto_dimension` | Premier appel détecte la dimension, `get_dimension()` retourne la bonne valeur ensuite |
| `test_embed_batch` | Mock retourne des embeddings pour 3 textes. Vérifie qu'on obtient 3 vecteurs |
| `test_embed_empty_text` | `embed("")` lève `ValueError` |
| `test_known_dimensions` | `get_dimension()` retourne 768 pour "nomic-embed-text", 1024 pour "mxbai-embed-large" |
| `test_provider_id` | `get_provider_id()` retourne `"ollama"` |

### Classe TestProviderRegistry

RAPPEL : la fixture `clean_registry` vide le registry avant/après chaque test.

| Test | Vérifie |
|------|---------|
| `test_register_and_get_model` | Enregistre un MockProvider, le récupère par ID |
| `test_register_and_get_embedding` | Enregistre un MockEmbeddingProvider, le récupère par ID |
| `test_get_unknown_raises` | `get_model("inexistant")` lève `KeyError` |
| `test_get_unknown_embedding_raises` | `get_embedding("inexistant")` lève `KeyError` |
| `test_list_model_providers` | Enregistre 3 providers, `list_model_providers()` retourne les 3 IDs |
| `test_list_embedding_providers` | Enregistre 2 embedding providers, vérifie le listing |
| `test_overwrite_warning` | Enregistre deux providers avec le même ID, le second remplace le premier |
| `test_unregister_model` | Enregistre puis désenregistre, `get_model()` lève `KeyError` |
| `test_get_stats` | Enregistre 2 model + 1 embedding, vérifie `{"model_providers": 2, "embedding_providers": 1, "total_providers": 3}` |
| `test_close_all` | (async) Enregistre des MockProviders avec une méthode `close()` mockée, appelle `close_all()`, vérifie que `close()` a été appelé sur chaque provider |
| `test_clear_all` | (Phase 2) Si `clear_all()` existe : enregistre des providers, appelle `clear_all()`, vérifie que le registry est vide MAIS que `close()` n'a PAS été appelé |
| `test_convenience_get_provider` | Teste la fonction `get_provider()` du module — cherche d'abord dans model, puis embedding |

---

## FICHIER 3 — `tests/test_rotator.py`

Tous les tests utilisent MockProvider et MockVRAMProvider depuis conftest. AUCUN mock httpx ici — on teste le rotator via l'interface abstraite.

### Classe TestMultiProviderRotator

| Test | Vérifie |
|------|---------|
| `test_init` | `MultiProviderRotator(providers={"a": mock_a, "b": mock_b})` s'instancie |
| `test_generate_single_success` | Un provider, une question. Vérifie `ProviderResponse.success == True`, `provider_id` correct, `text` non vide |
| `test_generate_single_unknown_provider` | `generate_single("inexistant", ...)` retourne `success=False`, `error` contient "not found" |
| `test_generate_single_provider_fails` | Provider avec `should_fail=True`. Vérifie `success == False` |
| `test_rotate_and_process` | 3 providers, 1 question. Vérifie `RotationResult` avec 3 réponses, `providers_processed == 3` |
| `test_rotate_and_process_with_failure` | 3 providers, le 2ème échoue. Vérifie `providers_failed == 1`, les 2 autres ont réussi |
| `test_rotate_stop_on_first_success` | 3 providers, `stop_on_first_success=True`. Vérifie que seul le 1er a été appelé (`generate_count == 1` pour le 1er, `== 0` pour les autres) |
| `test_rotate_with_system_prompt` | Vérifie que le system prompt est inclus dans les messages envoyés au provider. Inspecte les `messages` reçus par le MockProvider |
| `test_batch_process` | 1 provider, 3 questions. Vérifie qu'on obtient 3 `ProviderResponse`, chacun avec `success == True` |
| `test_batch_process_unknown_provider` | Provider inexistant, 2 questions. Vérifie 2 réponses avec `success == False` |
| `test_batch_sequential_providers` | 2 providers × 3 questions. Vérifie `BatchProviderResult` avec 2 clés, 3 réponses par clé |
| `test_vram_unload_on_rotation` | 2 MockVRAMProvider. Après `rotate_and_process()`, vérifie que `unload_count > 0` pour chaque provider |
| `test_vram_preload_on_batch` | 1 MockVRAMProvider, 3 questions via `batch_process()`. Vérifie `preload_count == 1` (preload une seule fois avant le batch) |
| `test_no_vram_on_cloud_provider` | 1 MockProvider (pas VRAM). Vérifie que `unload_count == 0` après rotation |
| `test_generate_count_tracking` | 2 providers × 2 questions. Vérifie que chaque `MockProvider.generate_count == 2` |

---

## RÈGLES D'IMPLÉMENTATION

1. **AUCUN appel réseau réel.** Tout est mocké.
2. **Un assert principal par test.** Chaque test vérifie UNE chose (il peut y avoir des asserts auxiliaires, mais le test a un seul objectif).
3. **Noms de test descriptifs.** Le nom dit ce qui est testé ET le résultat attendu.
4. **Pas de tests pour OpenAI/Anthropic providers.** Ils ne sont pas branchés dans le pipeline, on ne les teste pas maintenant.
5. **Pas de tests d'intégration ESMM.** Ça viendra quand le branchement (Phase 3) sera fait.
6. **Ne crée PAS de nouveau fichier .md.** Les résultats de test se lisent dans la sortie pytest.

---

## EXÉCUTION

Après implémentation :

```bash
# Lancer tous les tests
pytest tests/ -v

# Lancer un fichier spécifique
pytest tests/test_providers.py -v
pytest tests/test_rotator.py -v

# Vérifier la couverture (si pytest-cov est installé)
pytest tests/ -v --tb=short
```

---

## CRITÈRE DE VALIDATION

Les tests sont terminés quand :

1. `pytest tests/ -v` affiche VERT pour tous les tests
2. Minimum 35 tests au total (14 ABC/dataclass/ollama/embeddings + 12 registry + 14 rotator ≈ 40)
3. Zéro `@pytest.mark.skip` non justifié (seuls les tests Phase 2 peuvent être skip si le feature n'existe pas encore)
4. Zéro appel réseau (si un test échoue avec `ConnectionRefused`, c'est que le mock est mal fait)
