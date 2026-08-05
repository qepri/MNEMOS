"""The SPA's Document['status'] union must match the backend's status_enum.

These two drifted silently for a long time: the backend emitted 'error' while
the SPA declared and branched on 'failed', so the error badge never rendered
once. TypeScript cannot catch it - the union is an unchecked assertion over
JSON - and neither suite tests the other, so the mismatch needs a test that
reads both sides.

Lives in Python because this side can read the enum from the model directly;
the TypeScript side is a literal union that has to be parsed either way.
"""
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.api

_MODEL_TS = (
    Path(__file__).resolve().parents[2]
    / "frontend_spa" / "src" / "app" / "core" / "models" / "document.model.ts"
)


def _spa_status_values() -> set[str]:
    source = _MODEL_TS.read_text(encoding="utf-8")
    match = re.search(r"^\s*status:\s*([^;]+);", source, re.MULTILINE)
    assert match, f"Could not find a `status:` union in {_MODEL_TS}"
    return set(re.findall(r"'([^']+)'", match.group(1)))


def test_spa_status_union_matches_backend_enum(app):
    from app.models.document import Document

    backend_values = set(Document.__table__.c.status.type.enums)

    assert _spa_status_values() == backend_values, (
        "frontend_spa document.model.ts and app/models/document.py disagree on "
        "document status values. A value the backend never emits is dead code in "
        "the SPA; a value it emits but the SPA lacks renders as an unstyled "
        "fallback."
    )


def test_backend_still_emits_error_not_failed(app):
    """Guards the specific historical mismatch, so a revert is loud."""
    from app.models.document import Document

    enums = set(Document.__table__.c.status.type.enums)
    assert "error" in enums
    assert "failed" not in enums
