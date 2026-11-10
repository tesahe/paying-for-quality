"""AC-DC-2: Core imports nothing outside the standard library and its own package."""

import ast
import sys
from pathlib import Path

import paying_for_quality.core as core

CORE_DIR = Path(core.__file__).parent


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_core_uses_only_the_standard_library():
    offenders = {}
    for path in CORE_DIR.glob("*.py"):
        outside = {m for m in imported_modules(path) if m not in sys.stdlib_module_names and m != "__future__"}
        if outside:
            offenders[path.name] = sorted(outside)
    assert offenders == {}


def test_core_does_not_import_outer_layers():
    for path in CORE_DIR.glob("*.py"):
        text = path.read_text()
        for layer in ("paying_for_quality.app", "paying_for_quality.adapters", "paying_for_quality.cli"):
            assert layer not in text, f"{path.name} imports {layer}"
