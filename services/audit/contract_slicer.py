"""
Contract Slicer — ADR-014 §2.2.

Découpe un fichier Solidity en unités auditables (ContractUnit) via la stratégie
function_level_v1 : parsing regex sans dépendance compilateur externe.
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path


# Mots-clés Solidity qui ne sont pas des modificateurs
_SOLIDITY_KEYWORDS = frozenset({
    "returns", "public", "external", "internal", "private",
    "view", "pure", "payable", "virtual", "override",
    "memory", "storage", "calldata", "indexed",
    "uint", "uint256", "int", "int256", "address", "bool",
    "bytes", "string", "bytes32",
})

# Modificateurs qui indiquent des droits admin
_ADMIN_MODIFIERS = frozenset({
    "onlyOwner", "onlyAdmin", "onlyRole", "requiresAdmin",
    "onlyGovernance", "onlyTimelock", "adminOnly",
})

# Modificateurs qui indiquent des droits basés sur un rôle (RBAC)
_ROLE_MODIFIERS = frozenset({
    "hasRole", "onlyWithRole", "onlyRole",
})

# Mots-clés Solidity réservés (contrôle de flux + langage) — ne sont pas des noms de fonctions
SOLIDITY_RESERVED_KEYWORDS: frozenset[str] = frozenset({
    # Contrôle de flux
    "if", "else", "for", "while", "do", "break", "continue", "return",
    "throw", "try", "catch", "revert", "require", "assert",
    # Langage
    "new", "delete", "emit", "assembly", "pragma", "import", "using",
    "contract", "interface", "library", "struct", "enum", "event", "error",
    "mapping", "function", "modifier", "constructor", "fallback", "receive",
    "this", "super", "selfdestruct", "type",
})

# Types Solidity de base — exclus de state_writes (déclarations locales)
_LOCAL_DECL_TYPES = re.compile(
    r'\b(uint\d*|int\d*|address|bool|bytes\d*|string|mapping|struct)\s+\w+\s*[+\-]?='
)

# Pattern external calls dans le corps d'une fonction
_EXTERNAL_CALL_RE = re.compile(r'\.call\b|\.delegatecall\b|\.send\b|\.transfer\b')

# Pattern state_writes : assignation à une variable (hors déclarations locales)
_STATE_WRITE_RE = re.compile(r'\b([A-Za-z_]\w*)\s*(?:\[.*?\])?\s*[+\-]?=(?!=)')

# Pattern unités : function / modifier / constructor / fallback / receive
_UNIT_HEADER_RE = re.compile(
    r'\b(function|modifier|constructor|fallback|receive)\s*(\w*)\s*\('
)


@dataclass
class ContractUnit:
    """Unité atomique extraite d'un smart contract."""

    unit_id: str           # sha256(contract_path:unit_name)[:16]
    contract_path: str
    contract_name: str
    unit_type: str         # "function" | "modifier" | "constructor" | "fallback" | "receive"
    unit_name: str
    source_code: str
    visibility: str        # "public" | "external" | "internal" | "private"
    access_level: str      # "public" | "admin" | "role_restricted" | "contract_only"
    modifiers: list[str]
    state_writes: list[str]
    external_calls: list[str]
    line_range: tuple[int, int]
    context_imports: str   # imports + déclaration du contrat (cap ~2000 chars)


@dataclass
class ContractSliceResult:
    """Résultat du découpage d'un contrat."""

    contract_path: str
    contract_hash: str     # SHA-256 hex (64 chars) du fichier source complet
    language: str          # "solidity" | "rust_anchor"
    units: list[ContractUnit]
    total_lines: int
    slice_strategy: str    # "function_level_v1"
    skipped_units: list[str]   # unit_names skippés (view/pure sans external calls)
    slither_assisted: bool = False


def _find_body_end(source: str, brace_start: int) -> int:
    """
    Retourne l'index de l'accolade fermante correspondant à l'ouvrante à brace_start.
    Gère les accolades imbriquées.
    """
    depth = 0
    i = brace_start
    while i < len(source):
        if source[i] == '{':
            depth += 1
        elif source[i] == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(source) - 1


def _extract_visibility(signature: str) -> str:
    """Extrait la visibilité dans la signature. Défaut : 'public'."""
    for vis in ("external", "internal", "private", "public"):
        if re.search(rf'\b{vis}\b', signature):
            return vis
    return "public"


def _extract_modifiers(between: str) -> list[str]:
    """
    Extrait les modificateurs entre ')' et '{'.
    Ignore les mots-clés Solidity et les types de retour.
    """
    # Supprimer la clause returns(...)
    between = re.sub(r'\breturns\s*\([^)]*\)', '', between)
    tokens = re.findall(r'\b([A-Za-z_]\w*)\b', between)
    return [t for t in tokens if t not in _SOLIDITY_KEYWORDS]


def _classify_access(visibility: str, modifiers: list[str], inheritance_line: str) -> str:
    """Classifie le niveau d'accès selon la taxonomie Trail of Bits."""
    mod_set = set(modifiers)

    if mod_set & _ADMIN_MODIFIERS:
        return "admin"

    if mod_set & _ROLE_MODIFIERS:
        return "role_restricted"

    if "AccessControl" in inheritance_line and mod_set:
        return "role_restricted"

    if visibility in ("internal", "private"):
        return "contract_only"

    return "public"


def _extract_state_writes(body: str) -> list[str]:
    """
    Extrait les noms de variables d'état modifiées dans le corps.
    Filtre les déclarations locales (uint x = ..., address y = ...).
    """
    # Supprimer les lignes de déclaration locale
    lines = body.splitlines()
    filtered_lines = []
    for line in lines:
        stripped = line.strip()
        if _LOCAL_DECL_TYPES.match(stripped):
            continue
        filtered_lines.append(line)
    filtered = "\n".join(filtered_lines)

    writes = []
    for match in _STATE_WRITE_RE.finditer(filtered):
        name = match.group(1)
        if name not in _SOLIDITY_KEYWORDS and name not in {"require", "emit", "revert", "assert"}:
            if name not in writes:
                writes.append(name)
    return writes


def _extract_external_calls(body: str) -> list[str]:
    """Extrait les patterns d'appels externes dans le corps."""
    matches = _EXTERNAL_CALL_RE.findall(body)
    # Dédupliquer en préservant l'ordre
    seen: set[str] = set()
    result = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def _build_unit_id(contract_path: str, unit_name: str) -> str:
    """Calcule unit_id = sha256(contract_path:unit_name)[:16]."""
    raw = f"{contract_path}:{unit_name}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _extract_context_imports(source: str, cap: int = 2000) -> str:
    """
    Extrait les imports et la déclaration du contrat (héritage).
    Cap à ~2000 chars.
    """
    lines = source.splitlines()
    selected = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("import\""):
            selected.append(line)
        elif re.match(r'^\s*contract\s+\w+', line):
            selected.append(line)
    result = "\n".join(selected)
    return result[:cap]


def _detect_language(contract_path: str) -> str:
    """Détecte le langage depuis l'extension du fichier."""
    if contract_path.endswith(".rs"):
        return "rust_anchor"
    return "solidity"


def slice_contract(
    contract_path: str,
    strategy: str = "function_level_v1",
) -> ContractSliceResult:
    """
    Découpe un fichier Solidity en unités auditables.

    Args:
        contract_path: Chemin vers le fichier .sol (ou .rs)
        strategy: Stratégie de découpe. Seule "function_level_v1" est implémentée.

    Returns:
        ContractSliceResult avec les ContractUnit extraites.

    Raises:
        ValueError: Si la stratégie n'est pas reconnue.
        FileNotFoundError: Si le fichier n'existe pas.
    """
    if strategy != "function_level_v1":
        raise ValueError(f"Unknown slice strategy: {strategy!r}. Only 'function_level_v1' is supported.")

    path = Path(contract_path)
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    total_lines = len(lines)
    language = _detect_language(contract_path)
    contract_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()

    # Nom du contrat
    contract_name_match = re.search(r'\bcontract\s+(\w+)\s*(?:is\b|\{)', source)
    contract_name = contract_name_match.group(1) if contract_name_match else path.stem

    # Ligne de déclaration du contrat (pour AccessControl detection)
    contract_decl_line = ""
    if contract_name_match:
        decl_start = source.rfind("\n", 0, contract_name_match.start()) + 1
        decl_end = source.find("\n", contract_name_match.end())
        contract_decl_line = source[decl_start:decl_end] if decl_end != -1 else source[decl_start:]

    context_imports = _extract_context_imports(source)

    units: list[ContractUnit] = []
    skipped_units: list[str] = []

    for header_match in _UNIT_HEADER_RE.finditer(source):
        unit_type = header_match.group(1)
        raw_name = header_match.group(2)

        # Nom de l'unité
        if unit_type == "constructor":
            unit_name = "constructor"
        elif unit_type in ("fallback", "receive"):
            unit_name = unit_type
        else:
            unit_name = raw_name if raw_name else unit_type

        # Trouver la signature : du début du header jusqu'au '{' ou ';'
        sig_start = header_match.start()
        brace_pos = source.find("{", header_match.end())
        semicolon_pos = source.find(";", header_match.end())

        # Interfaces / abstract functions : pas de corps
        if semicolon_pos != -1 and (brace_pos == -1 or semicolon_pos < brace_pos):
            continue

        if brace_pos == -1:
            continue

        body_end = _find_body_end(source, brace_pos)
        full_source = source[sig_start: body_end + 1]

        # Signature = tout ce qui précède le '{'
        signature = source[sig_start:brace_pos]
        # Corps = entre '{' et '}'
        body = source[brace_pos + 1:body_end]

        # Entre ')' et '{' : modifiers + visibility + returns
        paren_close = signature.rfind(")")
        between = signature[paren_close + 1:] if paren_close != -1 else signature

        visibility = _extract_visibility(signature)
        modifiers = _extract_modifiers(between)
        access_level = _classify_access(visibility, modifiers, contract_decl_line)
        state_writes = _extract_state_writes(body)
        external_calls = _extract_external_calls(body)

        # line_range : position dans le fichier
        sig_line = source[:sig_start].count("\n") + 1
        end_line = source[:body_end].count("\n") + 1

        # Filtrage view/pure sans external calls → skipped
        if re.search(r'\b(view|pure)\b', signature) and not external_calls:
            skipped_units.append(unit_name)
            continue

        unit_id = _build_unit_id(contract_path, unit_name)

        units.append(ContractUnit(
            unit_id=unit_id,
            contract_path=contract_path,
            contract_name=contract_name,
            unit_type=unit_type,
            unit_name=unit_name,
            source_code=full_source.strip(),
            visibility=visibility,
            access_level=access_level,
            modifiers=modifiers,
            state_writes=state_writes,
            external_calls=external_calls,
            line_range=(sig_line, end_line),
            context_imports=context_imports,
        ))

    # Fix 2 (Lot A) : filtrer les unités dont le nom est un mot-clé Solidity réservé
    filtered_units = []
    for u in units:
        if u.unit_name.lower() in SOLIDITY_RESERVED_KEYWORDS:
            skipped_units.append(f"{u.unit_name} (reserved keyword)")
        else:
            filtered_units.append(u)
    units = filtered_units

    return ContractSliceResult(
        contract_path=contract_path,
        contract_hash=contract_hash,
        language=language,
        units=units,
        total_lines=total_lines,
        slice_strategy=strategy,
        skipped_units=skipped_units,
        slither_assisted=False,
    )
