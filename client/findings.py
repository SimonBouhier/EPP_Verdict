"""
Frontière d'erreurs du client — journalisation vers docs/audit/SHIM_FINDINGS.md.

Rôle (handoff « shim conversationnel ») :
- Toute exception traversant le shim est attrapée, affichée, et journalisée
  en UNE ligne : horodatage, chemin de code, contexte.
- Les warnings émis par les modules internes pendant une opération sont
  capturés aussi (les `except Exception` avalés en interne ne traversent
  jamais le shim — leurs `logger.warning` sont notre seule visibilité).
- AUCUN pré-durcissement des modules internes : ce module observe, il ne
  corrige rien.

Format d'une ligne de finding :
    | 2026-07-05T14:32:11 | escalate | services.esmm.pipeline:run_pipeline | ValueError: ... |
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
FINDINGS_PATH = REPO_ROOT / "docs" / "audit" / "SHIM_FINDINGS.md"

_HEADER = """# SHIM_FINDINGS — journal de la frontière d'erreurs du client personnel

Alimenté automatiquement par `client/` (shim conversationnel + graph view).
Règle de triage (handoff) : findings **sur le chemin d'appel du shim**
(extraction → pipeline → consensus_engine → crystallization → graphe)
corrigés au fil du besoin réel, RED→GREEN ; findings **hors chemin**
tagués `[deferred]`, sans correction.

Findings pré-connus (audit esmm, session 2026-07-05) :
- `[on-path]` `consensus_engine._get_relation_synonyms` : défaut
  `use_legacy_relation_groups=True` (legacy) alors que le commentaire du
  fallback dit « use new » ; fallback `except Exception: pass` silencieux.
  Sera exercé dès la première escalade.
- `[deferred]` ~90 `except Exception` dans services/esmm hors chemin immédiat
  du shim — voir audit esmm, triage à l'usage.

| horodatage | opération | chemin de code | contexte |
|---|---|---|---|
"""


def _ensure_file() -> None:
    FINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not FINDINGS_PATH.exists():
        FINDINGS_PATH.write_text(_HEADER, encoding="utf-8")


def _sanitize(text: str, limit: int = 300) -> str:
    """Une ligne, pas de pipes, bornée."""
    flat = " ".join(str(text).split()).replace("|", "/")
    return flat[:limit]


def record(operation: str, code_path: str, context: str) -> None:
    """Journalise un finding en une ligne. Ne lève jamais."""
    try:
        _ensure_file()
        ts = datetime.now().isoformat(timespec="seconds")
        line = f"| {ts} | {_sanitize(operation, 40)} | {_sanitize(code_path, 120)} | {_sanitize(context)} |\n"
        with FINDINGS_PATH.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        # La journalisation ne doit jamais casser le shim.
        pass


def record_exception(operation: str, exc: BaseException) -> str:
    """
    Journalise une exception traversant la frontière du shim.
    Retourne un message court affichable à l'utilisateur.
    """
    tb = traceback.extract_tb(exc.__traceback__)
    # Dernier frame dans le repo = chemin de code le plus utile
    code_path = "unknown"
    for frame in reversed(tb):
        if "EPP_Verdict" in frame.filename or "services" in frame.filename or "database" in frame.filename:
            mod = Path(frame.filename).stem
            code_path = f"{mod}:{frame.name}:{frame.lineno}"
            break
    context = f"{type(exc).__name__}: {exc}"
    record(operation, code_path, context)
    return f"{type(exc).__name__}: {exc}  (journalisé → docs/audit/SHIM_FINDINGS.md)"


class WarningCapture(logging.Handler):
    """
    Capture les WARNING+ émis par `services.*`/`database.*` pendant une
    opération du shim. Visibilité sur les exceptions avalées en interne,
    qui ne traversent jamais la frontière.
    """

    def __init__(self, operation: str):
        super().__init__(level=logging.WARNING)
        self.operation = operation

    def emit(self, rec: logging.LogRecord) -> None:
        try:
            if rec.name.startswith(("services", "database", "esmm")):
                record(
                    f"{self.operation} [warning]",
                    f"{rec.name}:{rec.funcName}:{rec.lineno}",
                    rec.getMessage(),
                )
        except Exception:
            pass


class warning_capture:
    """Context manager : installe/retire le WarningCapture sur le root logger."""

    def __init__(self, operation: str):
        self.handler: Optional[WarningCapture] = WarningCapture(operation)

    def __enter__(self):
        logging.getLogger().addHandler(self.handler)
        return self

    def __exit__(self, *exc):
        logging.getLogger().removeHandler(self.handler)
        return False
