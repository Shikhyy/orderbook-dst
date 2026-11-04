"""graders/import_policy.py
Enforce AST allowlist on candidate code submissions.
Allowed: stdlib, exchange_core.types, .state, .intmath, .config, .book, .ledger, .engine,
exchange_core.handlers.new_limit and exchange_core.handlers.settle.
Forbidden: All other exchange_core modules (including exchange_core.rules.*),
dynamic import calls (importlib, __import__, eval, exec), and relative imports
targeting forbidden modules.
"""
import ast
from pathlib import Path
from typing import Optional

ALLOWED_MODULES = {
    "exchange_core.types",
    "exchange_core.state",
    "exchange_core.intmath",
    "exchange_core.config",
    "exchange_core.book",
    "exchange_core.ledger",
    "exchange_core.engine",
    "exchange_core.handlers.new_limit",
    "exchange_core.handlers.settle",
}

ALLOWED_TOP_NAMES = {"types", "state", "intmath", "config", "book", "ledger", "engine"}


def check_candidate_ast(code: str, file_path: str = "") -> tuple[bool, Optional[str]]:
    """Check code string for forbidden imports using AST.
    Returns (True, None) if all imports are allowed, or (False, error_reason).
    """
    try:
        tree = ast.parse(code)
    except Exception as e:
        return False, f"FORBIDDEN_IMPORT: Syntax error parsing code: {e}"

    pkg_parts = (
        list(Path(file_path).parent.parts) if file_path else ["exchange_core", "handlers"]
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "importlib" or name.startswith("importlib."):
                    return False, f"FORBIDDEN_IMPORT: import of '{name}' is forbidden"
                if name == "exchange_core":
                    return False, "FORBIDDEN_IMPORT: bare 'import exchange_core' is forbidden"
                if name.startswith("exchange_core."):
                    is_sub = any(m.startswith(name + ".") for m in ALLOWED_MODULES)
                    if name not in ALLOWED_MODULES and not is_sub:
                        return False, f"FORBIDDEN_IMPORT: import of '{name}' is forbidden"

        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level > 0:
                # Relative import
                if node.level > len(pkg_parts):
                    return False, (
                        f"FORBIDDEN_IMPORT: relative import outside root package ({node.level})"
                    )
                base = pkg_parts[:-node.level + 1] if (node.level - 1) > 0 else pkg_parts
                full_mod = ".".join(base + mod.split(".")) if mod else ".".join(base)
                if full_mod.startswith("exchange_core"):
                    if full_mod == "exchange_core":
                        for alias in node.names:
                            if alias.name not in ALLOWED_TOP_NAMES:
                                return False, (
                                    f"FORBIDDEN_IMPORT: relative import of '{alias.name}' forbidden"
                                )
                    elif full_mod == "exchange_core.handlers":
                        for alias in node.names:
                            if f"exchange_core.handlers.{alias.name}" not in ALLOWED_MODULES:
                                return False, (
                                    f"FORBIDDEN_IMPORT: relative import of '{alias.name}' forbidden"
                                )
                    elif full_mod not in ALLOWED_MODULES:
                        return False, (
                            f"FORBIDDEN_IMPORT: relative import of '{full_mod}' is forbidden"
                        )
            else:
                # Absolute import
                if mod == "importlib" or mod.startswith("importlib."):
                    return False, f"FORBIDDEN_IMPORT: import from '{mod}' is forbidden"
                if mod == "exchange_core":
                    for alias in node.names:
                        if alias.name not in ALLOWED_TOP_NAMES:
                            return False, (
                                f"FORBIDDEN_IMPORT: 'from exchange_core import {alias.name}' "
                                "is forbidden"
                            )
                elif mod == "exchange_core.handlers":
                    for alias in node.names:
                        if f"exchange_core.handlers.{alias.name}" not in ALLOWED_MODULES:
                            return False, (
                                f"FORBIDDEN_IMPORT: 'from exchange_core.handlers "
                                f"import {alias.name}' is forbidden"
                            )
                elif mod.startswith("exchange_core."):
                    if mod not in ALLOWED_MODULES:
                        return False, f"FORBIDDEN_IMPORT: import from '{mod}' is forbidden"

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {"exec", "eval", "__import__"}:
                return False, f"FORBIDDEN_IMPORT: call to '{node.func.id}' is forbidden"
            if isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
                return False, "FORBIDDEN_IMPORT: call to 'import_module' is forbidden"

    return True, None


def check_candidate_target_files(target_files: dict[str, str]) -> tuple[bool, Optional[str]]:
    """Check all files in target_files for import violations."""
    for rel_path, content in target_files.items():
        ok, err = check_candidate_ast(content, file_path=rel_path)
        if not ok:
            return False, err
    return True, None
