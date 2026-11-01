"""Keep branching in named, independently understandable units."""

from pathlib import Path

import pytest
from radon.complexity import cc_visit

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.unit


def functions(blocks, seen=None):
    seen = set() if seen is None else seen
    for block in blocks:
        if hasattr(block, "methods"):
            yield from functions(block.methods, seen)
        elif (block.lineno, block.name) not in seen:
            seen.add((block.lineno, block.name))
            yield block
            yield from functions(block.closures, seen)


@pytest.mark.parametrize("folder", ["src", "scripts"])
def test_functions_remain_within_complexity_budget(folder):
    violations = set()
    for path in (ROOT / folder).rglob("*.py"):
        for function in functions(cc_visit(path.read_text(encoding="utf-8"))):
            if function.complexity > 10:
                violations.add(
                    (
                        str(path.relative_to(ROOT)),
                        function.lineno,
                        function.name,
                        function.complexity,
                    )
                )
    assert not violations, sorted(violations)
