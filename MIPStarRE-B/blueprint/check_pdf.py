#!/usr/bin/env python3
"""Reject clipped blueprint text and verify planned Lean identifiers survive PDF extraction."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMMAND_TIMEOUT_SECONDS = 30
BOUNDARY_TOLERANCE_POINTS = Decimal("0.01")
OVERLAP_TOLERANCE_POINTS = Decimal("0.1")


def validate_bbox(xml_text: str) -> tuple[int, list[str]]:
    root = ET.fromstring(xml_text)
    pages = root.findall(".//{*}page")
    errors: list[str] = []
    if not pages:
        errors.append("document contains no pages")
    for page_number, page in enumerate(pages, start=1):
        try:
            width = Decimal(page.attrib["width"])
            height = Decimal(page.attrib["height"])
        except (KeyError, InvalidOperation):
            errors.append(f"page {page_number}: malformed page geometry")
            continue
        if not all(value.is_finite() and value > 0 for value in (width, height)):
            errors.append(f"page {page_number}: invalid page dimensions")
            continue
        word_boxes: list[tuple[Decimal, Decimal, Decimal, Decimal, str]] = []
        for word in page.findall(".//{*}word"):
            text = "".join(word.itertext())
            try:
                x_min = Decimal(word.attrib["xMin"])
                x_max = Decimal(word.attrib["xMax"])
                y_min = Decimal(word.attrib["yMin"])
                y_max = Decimal(word.attrib["yMax"])
            except (KeyError, InvalidOperation):
                errors.append(f"page {page_number}: malformed word box: {text}")
                continue
            coordinates = (x_min, x_max, y_min, y_max)
            if not all(value.is_finite() for value in coordinates):
                errors.append(f"page {page_number}: non-finite word box: {text}")
                continue
            if x_min > x_max or y_min > y_max:
                errors.append(f"page {page_number}: inverted word box: {text}")
                continue
            if x_min == x_max or y_min == y_max:
                errors.append(f"page {page_number}: zero-area word box: {text}")
                continue
            word_boxes.append((x_min, x_max, y_min, y_max, text))
            edge_violations = (
                ("left", x_min < -BOUNDARY_TOLERANCE_POINTS, x_min, Decimal(0)),
                ("right", x_max > width + BOUNDARY_TOLERANCE_POINTS, x_max, width),
                ("bottom", y_min < -BOUNDARY_TOLERANCE_POINTS, y_min, Decimal(0)),
                ("top", y_max > height + BOUNDARY_TOLERANCE_POINTS, y_max, height),
            )
            for edge, violated, coordinate, boundary in edge_violations:
                if not violated:
                    continue
                errors.append(
                    f"page {page_number}: text crosses {edge} page boundary "
                    f"({coordinate:.3f} outside 0..{boundary:.3f}): {text}"
                )
        by_left_edge = sorted(word_boxes)
        for index, first in enumerate(by_left_edge):
            first_x_min, first_x_max, first_y_min, first_y_max, first_text = first
            for second in by_left_edge[index + 1:]:
                second_x_min, second_x_max, second_y_min, second_y_max, second_text = second
                x_overlap = min(first_x_max, second_x_max) - max(first_x_min, second_x_min)
                if x_overlap <= OVERLAP_TOLERANCE_POINTS:
                    if second_x_min >= first_x_max - OVERLAP_TOLERANCE_POINTS:
                        break
                    continue
                y_overlap = min(first_y_max, second_y_max) - max(first_y_min, second_y_min)
                if y_overlap <= OVERLAP_TOLERANCE_POINTS:
                    continue
                errors.append(
                    f"page {page_number}: text boxes overlap "
                    f"({x_overlap:.3f} x {y_overlap:.3f} points): "
                    f"{first_text!r} and {second_text!r}"
                )
    return len(pages), errors


def planned_identifiers(metadata_path: Path) -> list[str]:
    document = json.loads(metadata_path.read_text(encoding="utf-8"))
    return sorted({
        identifier
        for node in document["nodes"]
        for identifier in [node["lean"]["module"], *node["lean"]["names"]]
    })


def extracted_identifier_errors(text: str, identifiers: list[str]) -> list[str]:
    compact = "".join(text.split())
    return [f"planned Lean identifier is not extractable: {identifier}"
            for identifier in identifiers if identifier not in compact]


def run_pdftotext(pdf: Path, mode: str) -> str:
    process = subprocess.run(
        ["pdftotext", mode, str(pdf), "-"],
        check=False,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
    )
    if process.returncode != 0:
        raise RuntimeError(f"pdftotext {mode} failed with exit {process.returncode}")
    return process.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--metadata", type=Path, default=ROOT / "metadata/nodes.json")
    args = parser.parse_args()
    try:
        bbox = run_pdftotext(args.pdf, "-bbox-layout")
        text = run_pdftotext(args.pdf, "-layout")
        page_count, errors = validate_bbox(bbox)
        identifiers = planned_identifiers(args.metadata)
        errors.extend(extracted_identifier_errors(text, identifiers))
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ET.ParseError, ValueError) as error:
        print(f"ERROR: PDF validation failed: {error}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {page_count} PDF pages; {len(identifiers)} planned Lean identifiers extractable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
