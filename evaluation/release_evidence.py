"""Independent release reconciliation and conservative occurrence alignment."""
from collections import Counter
from difflib import SequenceMatcher
import json
from pathlib import PurePosixPath
import re


MAX_ALIGNMENT_PRODUCT = 2_000_000
REDACTION_MARKER = re.compile(
    r"\[(?:NAME|RELATIVE|PHONE|EMAIL|AADHAAR|ABHA|MRN|ADDRESS|PIN|DOB|PAN|"
    r"INSURANCE_ID|PATH|IDENTIFIER|REDACTED)\]"
)


def reconcile(release, expected):
    report = json.loads((release / "report.json").read_bytes())
    entries = report["files"]
    if len({row["input_sha256"] for row in entries}) != len(entries):
        raise ValueError("duplicate_report_entry")
    if len(set(expected.values())) != len(expected):
        raise ValueError("ambiguous_input_digest")
    by_hash = {row["input_sha256"]: row for row in entries}
    if by_hash.keys() != set(expected.values()):
        raise ValueError("unmatched_report_file")
    sanitized = release / "sanitized"
    if not sanitized.is_dir() or sanitized.is_symlink():
        raise ValueError("invalid_release_root")
    root = sanitized.resolve()
    outputs = set()
    for entry in entries:
        status, reported = entry["status"], entry["output"]
        if status in {"quarantined", "suppressed"} and reported is None:
            continue
        if status != "sanitized" or not isinstance(reported, str):
            raise ValueError("inconsistent_report_status")
        relative = PurePosixPath(reported)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe_report_path")
        output = (release / relative).resolve()
        if not output.is_relative_to(root) or not output.is_file():
            raise ValueError("unsafe_report_path")
        if output in outputs:
            raise ValueError("reused_release_artifact")
        outputs.add(output)
    actual = set()
    for path in sanitized.rglob("*"):
        if path.is_symlink():
            raise ValueError("release_symlink")
        if path.is_file():
            actual.add(path.resolve())
    if actual != outputs:
        raise ValueError("unreported_release_artifact")
    counts = report.get("counts", {})
    statuses = Counter(entry["status"] for entry in entries)
    for key, observed in (("files_total", len(entries)), ("files_sanitized", statuses["sanitized"]),
                          ("files_quarantined", statuses["quarantined"])):
        if key in counts and counts[key] != observed:
            raise ValueError("incorrect_report_total")
    return {relative: by_hash[digest] for relative, digest in expected.items()}


def alignment(original, rendered, *, reverse=False):
    if reverse:
        left, right = original[::-1], rendered[::-1]
    else:
        left, right = original, rendered
    points = {}
    for i, j, length in SequenceMatcher(None, left, right, autojunk=False).get_matching_blocks():
        for delta in range(length):
            a, b = i + delta, j + delta
            if reverse:
                a, b = len(original) - 1 - a, len(rendered) - 1 - b
            points[a] = b
    return points


class OccurrenceAlignment:
    """Locate attributable original characters without consulting detector edits."""

    def __init__(self, original, rendered):
        self.original = original
        self.rendered = rendered
        self.mappings = None
        if rendered is not None and original != rendered:
            if len(original) * len(rendered) <= MAX_ALIGNMENT_PRODUCT:
                comparison = REDACTION_MARKER.sub(
                    lambda match: match[0] if match[0] in original else "\0" * len(match[0]),
                    rendered,
                )
                self.mappings = (alignment(original, comparison),
                                 alignment(original, comparison, reverse=True))

    def outcome(self, start, end):
        if not 0 <= start < end <= len(self.original):
            raise ValueError("invalid_alignment_target")
        if self.rendered is None:
            return "unresolved"
        if self.original == self.rendered:
            return "visible"
        if self.mappings is None:
            return "unresolved"
        span = range(start, end)
        left, right = self.mappings
        left_points = tuple(left.get(index) for index in span)
        if left_points != tuple(right.get(index) for index in span):
            return "unresolved"
        surface = self.original[start:end]
        if None not in left_points and left_points == tuple(range(left_points[0], left_points[0] + len(span))):
            return "visible"
        if (surface and self.original.count(surface) == 1 and
                surface.casefold() in self.rendered.casefold()):
            return "unresolved"
        if any(self.original[i].isalnum() and left.get(i) is not None for i in span):
            return "partial"
        return "transformed"
