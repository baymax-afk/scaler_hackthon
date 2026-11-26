"""Replay V1 practice visibility labels and report the earliest observable failure.

Run from repository root with the pinned V1 implementation. Output is counts only.
"""
from collections import Counter, defaultdict
import json
from inspect import currentframe
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path.cwd()
sys.path[:0] = [str(ROOT), str(ROOT / "submission")]
from check_dev import norm, read_text
from evaluation.evaluate import practice_audit
from rakshak.detection import detect, FIELDS, normalize_label
from rakshak.formats import Rewrite, decode, pointer, transform
from rakshak.release import output_location, publish_release


class TracedRewrite(Rewrite):
    def __init__(self):
        super().__init__()
        self.calls = []

    def findings(self, text, **context):
        frame = currentframe().f_back
        while frame and frame.f_code.co_name not in {
            "table", "walk", "output_location", "transform"
        }:
            frame = frame.f_back
        loc = "doc"
        if frame and frame.f_code.co_name == "table":
            index = frame.f_locals.get("index")
            loc = "@header" if index is None else f"row:{index}"
        elif frame and frame.f_code.co_name == "walk":
            parts = frame.f_locals["path"]
            loc = "/" + "/".join(pointer(str(part)) for part in parts)
        elif frame and frame.f_code.co_name == "output_location":
            loc = "@filename"

        # Capture the detector's pre-selection candidate lists in memory. An early typed-field return has only the public findings.
        candidates = []

        def trace(detector_frame, event, _arg):
            if detector_frame.f_code is detect.__code__:
                if event == "return":
                    for collection in ("accepted", "review"):
                        candidates.extend(detector_frame.f_locals.get(collection, ()))
                return trace
            return None

        sys.settrace(trace)
        try:
            findings = super().findings(text, **context)
        finally:
            sys.settrace(None)

        self.calls.append((loc, context, text, findings, candidates))
        return findings


def redact(text, findings):
    for finding in reversed(findings):
        text = text[:finding.start] + "[" + finding.kind + "]" + text[finding.end:]
    return text


def scoped(call, loc, channel):
    found, context, *_ = call
    if channel == "filename":
        return found == "@filename"
    if found == "@filename":
        return False
    if channel == "header":
        return found == "@header"
    if channel == "key":
        return context.get("channel") == "key"
    if found == "@header" or context.get("channel") == "key":
        return False
    return (
        loc in {"doc", "@file"} or loc == found or found.startswith(loc + "/")
    )


def cause(calls, loc, entity):
    phrase = norm(entity["surface"])
    matches = [call for call in calls if phrase in norm(call[2])]
    in_scope = [call for call in matches if scoped(call, loc, entity["channel"])]
    if not in_scope:
        if matches:
            return "visibility only outside intended scope"
        return "no literal in detector input"
    residual = []
    for call in in_scope:
        _, _, source, findings, _ = call
        if phrase in (norm(source) if loc == "@filename" and not findings
                      else "" if loc == "@filename" else norm(redact(source, findings))):
            residual.append(call)
    if not residual:
        return "accepted edit removed all traced local matches"
    if any(any(f not in findings and phrase in norm(source[f.start:f.end]) for f in pre)
           for _, _, source, findings, pre in residual):
        return "covering candidate discarded by overlap selection"
    if any(context.get("label") and normalize_label(context["label"]) not in FIELDS
           for _, context, _, _, _ in residual):
        return "present in structured field without covering candidate"
    return "present in text or path without covering candidate"


def main():
    truth = json.loads((ROOT / "dev/truth/truth.json").read_text())
    secret = b"practice"
    counts = Counter()
    by_axis = defaultdict(Counter)
    misses_by_file = Counter()
    cause_by_type = defaultdict(Counter)
    with TemporaryDirectory(prefix="secret-wards-v1-audit-") as temp:
        output = Path(temp) / "release"
        publish_release(ROOT / "dev/input", output, secret)
        totals = practice_audit(output, truth)
        ledger = defaultdict(list)
        for entry in json.loads((output / "report.json").read_text())["files"]:
            ledger[entry["input_sha256"]].append(entry["output"])

        for path, info in sorted(truth["files"].items()):
            result = ledger[info["sha256"]].pop(0)
            if not result:
                continue
            relative = Path(path)
            raw = (ROOT / "dev/input" / relative).read_bytes()
            rendered = (output / result).read_bytes()
            haystack = norm(read_text(output / result))
            trace = TracedRewrite()
            written = output_location(relative, secret, trace)
            replayed, _ = transform(decode(raw), relative.suffix.lower(), trace)
            if "sanitized/" + written.as_posix() != result or replayed.encode("utf-8") != rendered:
                raise ValueError("release_replay_mismatch")
            for loc, unit in info["units"].items():
                for entity in unit["entities"]:
                    if entity["type"] == "CANARY":
                        continue
                    target = norm(result) if entity["channel"] == "filename" else haystack
                    phrase = norm(entity["surface"])
                    if not phrase or phrase not in target:
                        continue
                    category = cause(trace.calls, loc, entity)
                    counts[category] += 1
                    cause_by_type[category][entity["type"]] += 1
                    misses_by_file[path] += 1
                    for axis, value in {
                        "format": ("FHIR" if path.startswith("fhir/") else relative.suffix),
                        "channel": entity["channel"],
                        "script": entity["script"],
                        "type": entity["type"],
                    }.items():
                        by_axis[axis][value] += 1
    if sum(counts.values()) != totals["counts"]["visible_mentions"]:
        raise ValueError("visible_count_mismatch")
    print(json.dumps({"baseline": totals, "failure_locations": counts,
                      "breakdown": by_axis, "cause_by_type": cause_by_type,
                      "affected_files": len(misses_by_file)},
                     ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
