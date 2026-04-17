# tests/test_phase03_audit.py
"""
Phase 0.3.1 Tests — Audit and Decoupling of ESMM Pipeline

Verifies:
- No forbidden imports (llm_client, model_rotator, multimodel, app.embeddings)
- No hardcoded URLs (localhost:11434)
- No hardcoded model names outside logs/comments
- All critical ESMM files exist
"""

import re
from pathlib import Path


# Fichiers du pipeline ESMM à auditer
ESMM_FILES = [
    "services/esmm/orchestrator.py",
    "services/esmm/cycle_manager.py",
    "services/esmm/cycle_prompts.py",
    "services/esmm/triplet_extractor.py",
    "services/esmm/triplet_validator.py",
    "services/esmm/consensus_engine.py",
    "services/esmm/cochain_builder.py",
    "services/esmm/gap_detector.py",
    "services/esmm/coverage_analyzer.py",
]

# Patterns interdits (regex)
FORBIDDEN_IMPORTS = [
    r"^\s*(from\s+.*)?import\s+llm_client",
    r"^\s*(from\s+.*)?import\s+model_rotator",
    r"^\s*(from\s+.*)?import\s+multimodel",
    r"^\s*from\s+app\.embeddings\s+import",
]

FORBIDDEN_STRINGS = [
    r"localhost:11434",
    r"httpx\.AsyncClient\(",
    r"requests\.(get|post|put|delete)\(",
]

FORBIDDEN_HARDCODED_MODELS = [
    r"['\"]mistral['\"]",
    r"['\"]llama['\"]",
    r"['\"]deepseek['\"]",
    r"['\"]gpt-oss['\"]",
    r"['\"]gemma['\"]",
    r"['\"]qwen['\"]",
]


class TestESMMDecoupling:
    """Vérifie zéro couplage direct dans le pipeline ESMM."""

    def _get_project_root(self):
        """Find project root (parent of services/)."""
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "services").exists():
                return parent
        return Path.cwd()

    def _read_file_if_exists(self, filepath: str) -> str:
        """Read file content, return empty string if not found."""
        root = self._get_project_root()
        full_path = root / filepath
        if full_path.exists():
            return full_path.read_text(encoding="utf-8")
        return ""

    def test_no_forbidden_imports(self):
        """Aucun fichier ESMM n'importe llm_client, model_rotator, ou multimodel."""
        violations = []
        for filepath in ESMM_FILES:
            content = self._read_file_if_exists(filepath)
            if not content:
                continue
            for line_no, line in enumerate(content.splitlines(), 1):
                for pattern in FORBIDDEN_IMPORTS:
                    if re.search(pattern, line):
                        violations.append(f"{filepath}:{line_no} → {line.strip()}")

        assert not violations, (
            f"Forbidden imports found in ESMM pipeline:\n" +
            "\n".join(violations)
        )

    def test_no_hardcoded_urls(self):
        """Aucun fichier ESMM ne contient d'URL de provider en dur."""
        violations = []
        for filepath in ESMM_FILES:
            content = self._read_file_if_exists(filepath)
            if not content:
                continue
            for line_no, line in enumerate(content.splitlines(), 1):
                # Skip comments and docstrings
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                for pattern in FORBIDDEN_STRINGS:
                    if re.search(pattern, line):
                        violations.append(f"{filepath}:{line_no} → {line.strip()}")

        assert not violations, (
            f"Hardcoded URLs or direct HTTP clients in ESMM pipeline:\n" +
            "\n".join(violations)
        )

    def test_no_hardcoded_model_names(self):
        """Aucun fichier ESMM ne contient de noms de modèles en dur (hors commentaires/logs)."""
        violations = []
        for filepath in ESMM_FILES:
            content = self._read_file_if_exists(filepath)
            if not content:
                continue

            in_multiline_string = False
            for line_no, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()

                # Skip comments
                if stripped.startswith("#"):
                    continue

                # Track multiline docstrings
                if '"""' in stripped or "'''" in stripped:
                    count = stripped.count('"""') + stripped.count("'''")
                    if count == 1:
                        in_multiline_string = not in_multiline_string
                    continue

                if in_multiline_string:
                    continue

                # Allow in f-strings used for logging (logger.info/debug/warning/error)
                if re.match(r"^\s*logger\.(info|debug|warning|error)", stripped):
                    continue

                for pattern in FORBIDDEN_HARDCODED_MODELS:
                    if re.search(pattern, line):
                        violations.append(f"{filepath}:{line_no} → {line.strip()}")

        assert not violations, (
            f"Hardcoded model names in ESMM pipeline:\n" +
            "\n".join(violations)
        )

    def test_esmm_files_exist(self):
        """Au moins les fichiers ESMM principaux existent."""
        root = self._get_project_root()
        critical_files = [
            "services/esmm/orchestrator.py",
            "services/esmm/cycle_manager.py",
            "services/esmm/triplet_extractor.py",
            "services/esmm/consensus_engine.py",
            "services/esmm/cochain_builder.py",
        ]
        missing = [f for f in critical_files if not (root / f).exists()]
        assert not missing, f"Critical ESMM files missing: {missing}"
