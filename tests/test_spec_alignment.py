"""Contract alignment: ENUM values in app.contracts.enums must match the
table in Docs/ENGINE_SPEC.md §2 ("상태값 단일 기준").

Parsing is intentionally naive (line-based); a malformed table fails the test
so drift between code and contract cannot pass silently.
"""

from __future__ import annotations

import re

from app.contracts import enums

SPEC_PATH = "Docs/ENGINE_SPEC.md"
SECTION_2 = "## 2. 상태값 단일 기준"
SECTION_3 = "## 3."

_ENDPOINT_RE = re.compile(r"^\|\s*`(\w+)`\s*\|\s*(.+?)\s*\|\s*$")


def _spec_enum_values() -> dict[str, set[str]]:
    with open(SPEC_PATH, encoding="utf-8") as handle:
        text = handle.read()
    section = text.split(SECTION_2, 1)[1].split(SECTION_3, 1)[0]
    values: dict[str, set[str]] = {}
    for line in section.splitlines():
        match = _ENDPOINT_RE.match(line)
        if match:
            values[match.group(1)] = {cell.strip() for cell in match.group(2).split(",")}
    return values


def test_enum_values_match_engine_spec() -> None:
    spec = _spec_enum_values()
    assert spec, f"no enum table rows parsed from {SPEC_PATH} {SECTION_2!r}"

    code_enums = {
        name: member
        for name, member in vars(enums).items()
        if isinstance(member, type) and issubclass(member, str) and member.__module__ == enums.__name__
    }

    missing = sorted(set(spec) - set(code_enums))
    assert not missing, f"spec enums without code contract: {missing}"

    for name, expected in sorted(spec.items()):
        actual = {member.value for member in code_enums[name]}
        assert actual == expected, f"{name}: code={sorted(actual)} spec={sorted(expected)}"
