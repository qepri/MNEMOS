#!/usr/bin/env python3
"""Coverage ratchet gate for the two highest-risk pipelines (FR-012/SC-007).

Reads a Cobertura coverage.xml (from `pytest --cov-report=xml`), computes
line coverage for the RAG pipeline and document-processing pipeline path
groups, and fails if either drops below the percentage recorded in
coverage-baseline.json. Coverage for the rest of the backend is not gated.

The baseline is a deliberate, reviewable value in the repo - it never
updates itself. Raise it by hand in the same commit that improves coverage.
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Paths as they appear in coverage.xml: relative to .coveragerc's
# [run] source = app, not the repo root.
GROUPS = {
    "rag_pipeline": [
        "services/rag.py",
        "services/rag_context.py",
    ],
    "processing_pipeline": [
        "tasks/pipeline.py",
        "tasks/processing.py",
        "services/chunker.py",
    ],
}


def _normalize(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def group_coverage(coverage_xml: Path) -> dict[str, float]:
    tree = ET.parse(coverage_xml)
    lines_by_file: dict[str, tuple[int, int]] = {}

    for cls in tree.getroot().iter("class"):
        filename = _normalize(cls.get("filename", ""))
        lines = cls.find("lines")
        if lines is None:
            continue
        valid = hit = 0
        for line in lines.findall("line"):
            valid += 1
            if int(line.get("hits", "0")) > 0:
                hit += 1
        prev_hit, prev_valid = lines_by_file.get(filename, (0, 0))
        lines_by_file[filename] = (prev_hit + hit, prev_valid + valid)

    result = {}
    for group, files in GROUPS.items():
        hit = valid = 0
        for f in files:
            h, v = lines_by_file.get(f, (0, 0))
            hit += h
            valid += v
        result[group] = (100.0 * hit / valid) if valid else 0.0
    return result


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_coverage_baseline.py <coverage.xml>", file=sys.stderr)
        return 2

    coverage_xml = Path(sys.argv[1])
    baseline_path = Path(__file__).resolve().parent.parent / "coverage-baseline.json"
    baseline = json.loads(baseline_path.read_text())
    measured = group_coverage(coverage_xml)

    failed = False
    for group, baseline_pct in baseline.items():
        if group == "recorded_at":
            continue
        measured_pct = measured.get(group, 0.0)
        status = "OK"
        if measured_pct < baseline_pct - 0.01:
            status = "FAIL (regression)"
            failed = True
        print(f"{group}: {measured_pct:.1f}% (baseline {baseline_pct:.1f}%) - {status}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
