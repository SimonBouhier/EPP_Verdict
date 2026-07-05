"""
Shim conversationnel EPP — write path (Lot A).

Converser avec un modèle local (couche Ollama existante), escalader à tout
moment une affirmation du fil dans un cycle ESMM. L'attestation s'écrit au
graphe par le chemin habituel (`run_pipeline` → crystallization inchangée).

Lancement :
    python -m client.shim

Commandes :
    /models              modèles Ollama disponibles
    /model <nom>         changer de modèle de conversation
    /params              paramètres de cycle exposés
    /set <clé> <valeur>  modifier un paramètre exposé
    /escalate [texte]    escalader une affirmation (défaut : dernière réponse)
    /history             fil de la session
    /quit                sortir

Contraintes respectées (handoff) :
- ADR-003 : un seul run ESMM à la fois — escalade bloquante, progression
  affichée via les logs INFO du pipeline.
- Pas de nouveau moteur : MultiProviderRotator + OllamaProvider existants.
- Aucun chemin d'ancrage on-chain (attestations en SQLite locale,
  `submission_status` inchangé).
- Frontière d'erreurs : voir client/findings.py.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from client.findings import record_exception, warning_capture

logger = logging.getLogger("client.shim")

SYSTEM_PROMPT = (
    "You are a local assistant running on the operator's personal EPP node. "
    "Answer directly and factually. Keep answers compact."
)


# --------------------------------------------------------------------------
# Paramètres exposés à runtime — UNIQUEMENT ceux que le shim touche.
# Chaque paramètre figé rencontré en chemin : dégelé si bloquant, sinon
# journalisé (SHIM_FINDINGS.md). Pas de dégel généralisé.
# --------------------------------------------------------------------------
@dataclass
class ShimParams:
    chat_model: str = ""                 # rempli au démarrage depuis config/Ollama
    escalade_models: List[str] = field(default_factory=list)  # modèles du run ESMM
    temperature: float = 0.7
    max_tokens: int = 1024
    max_questions_per_cycle: int = 10    # ESMMRunConfig — exposé car coût direct
    frame: str = "general_knowledge_v1.0"

    EXPOSED = {
        "chat_model": str,
        "temperature": float,
        "max_tokens": int,
        "max_questions_per_cycle": int,
        "frame": str,
    }

    def show(self) -> str:
        lines = [f"  chat_model              = {self.chat_model}"]
        lines.append(f"  escalade_models         = {', '.join(self.escalade_models)} (via /model, ordre config.yaml)")
        lines.append(f"  temperature             = {self.temperature}")
        lines.append(f"  max_tokens              = {self.max_tokens}")
        lines.append(f"  max_questions_per_cycle = {self.max_questions_per_cycle}")
        lines.append(f"  frame                   = {self.frame}")
        return "\n".join(lines)

    def set(self, key: str, value: str) -> str:
        if key not in self.EXPOSED:
            return f"Paramètre non exposé : {key} (exposés : {', '.join(self.EXPOSED)})"
        try:
            setattr(self, key, self.EXPOSED[key](value))
            return f"{key} = {getattr(self, key)}"
        except ValueError as e:
            return f"Valeur invalide pour {key} : {e}"


class Shim:
    def __init__(self):
        self.params = ShimParams()
        self.history: List[Dict[str, str]] = []   # [{"role","content"}]
        self.rotator = None                        # MultiProviderRotator
        self._escalating = False                   # garde ADR-003 (ceinture)

    # ---------------------------------------------------------------- setup
    async def setup(self) -> None:
        from services.providers.ollama import OllamaProvider
        from services.esmm.multi_provider_rotator import MultiProviderRotator
        from services.config_loader import get_section

        esmm_cfg = get_section("esmm", {}) or {}
        models = esmm_cfg.get("models", ["mistral:latest"])
        self.params.escalade_models = models[: esmm_cfg.get("default_models", 3)]
        self.params.chat_model = models[0]

        provider = OllamaProvider(model=self.params.chat_model)
        self.rotator = MultiProviderRotator(providers={"ollama": provider})

        health = await provider.health_check()
        if not health.get("connected", False):
            print("⚠ Ollama ne répond pas sur localhost:11434 — la conversation")
            print("  et l'escalade échoueront tant que le serveur n'est pas lancé.")
        elif not health.get("default_model_available", True):
            avail = ", ".join(health.get("models", [])[:6]) or "(aucun)"
            print(f"⚠ Modèle « {self.params.chat_model} » absent d'Ollama. Disponibles : {avail}")
            print("  → /model <nom> pour en choisir un.")

    # ----------------------------------------------------------------- chat
    async def chat_turn(self, user_text: str) -> None:
        self.history.append({"role": "user", "content": user_text})
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.history[-12:]

        provider = self.rotator.providers["ollama"]
        provider.model = self.params.chat_model  # sélection runtime

        resp = await self.rotator.generate_single(
            provider_id="ollama",
            messages=messages,
            temperature=self.params.temperature,
            max_tokens=self.params.max_tokens,
            unload_after=False,  # conversation : on garde le modèle chaud
        )
        if not resp.success:
            self.history.pop()
            raise RuntimeError(f"génération échouée : {resp.error}")

        self.history.append({"role": "assistant", "content": resp.text.strip()})
        print(f"\n[{resp.model} · {resp.latency_ms:.0f}ms]")
        print(resp.text.strip())

    # ------------------------------------------------------------- escalade
    def _default_claim(self) -> Optional[str]:
        for msg in reversed(self.history):
            if msg["role"] == "assistant":
                return msg["content"]
        return None

    async def escalate(self, claim: Optional[str]) -> None:
        """
        Escalade bloquante (ADR-003 : un seul run à la fois).
        Chemin habituel : run_pipeline (mode verify) → crystallization → graphe.
        Aucun ancrage on-chain.
        """
        if self._escalating:
            print("Un run ESMM est déjà en cours (ADR-003) — attendre sa fin.")
            return

        claim = (claim or self._default_claim() or "").strip()
        if not claim:
            print("Rien à escalader : pas d'affirmation désignée ni de réponse dans le fil.")
            return
        if len(claim) > 4900:
            claim = claim[:4900]  # MAX_QUESTION_LENGTH=5000 côté pipeline

        from database.engine import get_db
        from services.esmm.pipeline import run_pipeline, PipelineConfig
        from services.esmm.orchestrator import ESMMRunConfig

        print(f"\n⇪ Escalade ESMM (bloquante) : « {claim[:100]}{'…' if len(claim) > 100 else ''} »")
        print(f"  modèles : {', '.join(self.params.escalade_models)}")
        print("  progression via logs pipeline ↓\n")

        # Progression : les logs INFO du pipeline sont l'indicateur.
        pipeline_level = logging.getLogger("services").level
        logging.getLogger("services").setLevel(logging.INFO)
        logging.getLogger("esmm").setLevel(logging.INFO)

        self._escalating = True
        try:
            with warning_capture("escalate"):
                db = await get_db()
                esmm_config = ESMMRunConfig(
                    models=list(self.params.escalade_models),
                    input_mode="verify",
                    original_claim=claim,
                    max_questions_per_cycle=self.params.max_questions_per_cycle,
                )
                result = await run_pipeline(
                    question=claim,
                    db=db,
                    config=PipelineConfig(metrological_frame=self.params.frame),
                    esmm_config=esmm_config,
                )
        finally:
            self._escalating = False
            logging.getLogger("services").setLevel(pipeline_level)

        print(f"\n── Run terminé ({result.duration_ms:.0f} ms) ──")
        print(f"  {result.triplets_extracted} extraits → {result.triplets_attested} attestés → {result.triplets_injected} injectés au graphe")
        for att in result.attestations:
            print(f"  [{att.confidence_tier.upper():11s}] {att.subject} —{att.predicate}→ {att.object}")
            print(f"               consensus {att.consensus_score:.2%} · {att.models_agreeing}/{att.models_consulted} modèles · hash {att.claim_hash[:12]}…")
        if result.errors:
            print(f"  erreurs pipeline : {result.errors}")
        print("  (local/SQLite uniquement — pas d'ancrage on-chain, submission_status inchangé)")

    # --------------------------------------------------------------- REPL
    async def run(self) -> None:
        print("EPP — shim conversationnel (nœud personnel, local). /help pour l'aide.")
        await self.setup()
        print(f"Modèle de conversation : {self.params.chat_model}\n")

        while True:
            try:
                line = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nbye.")
                return
            if not line:
                continue

            try:
                if line in ("/quit", "/exit", "/q"):
                    print("bye.")
                    return
                elif line == "/help":
                    print(__doc__.split("Commandes :")[1].split("Contraintes")[0])
                elif line == "/models":
                    models = await self.rotator.providers["ollama"].list_models()
                    print("\n".join(f"  {m}" for m in models) or "  (aucun)")
                elif line.startswith("/model "):
                    self.params.chat_model = line.split(None, 1)[1].strip()
                    print(f"chat_model = {self.params.chat_model}")
                elif line == "/params":
                    print(self.params.show())
                elif line.startswith("/set "):
                    parts = line.split(None, 2)
                    print(self.params.set(parts[1], parts[2]) if len(parts) == 3 else "usage : /set <clé> <valeur>")
                elif line == "/history":
                    for i, m in enumerate(self.history):
                        print(f"  [{i}] {m['role']:9s} {m['content'][:90]}")
                elif line.startswith("/escalate"):
                    arg = line[len("/escalate"):].strip() or None
                    await self.escalate(arg)
                elif line.startswith("/"):
                    print(f"commande inconnue : {line.split()[0]} — /help")
                else:
                    with warning_capture("chat"):
                        await self.chat_turn(line)
            except Exception as exc:
                # Frontière d'erreurs : attraper, afficher, journaliser. Point.
                print(f"\n✗ {record_exception(line.split()[0] if line.startswith('/') else 'chat', exc)}")


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        asyncio.run(Shim().run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
