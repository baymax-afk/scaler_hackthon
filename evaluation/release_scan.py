"""Check known Direct Identifier surfaces across the Research Release."""
import base64
from collections import defaultdict
import csv
import io
import json
import re
from xml.etree import ElementTree

from check_dev import norm
from evaluation.source_inventory import MAX_FILE_BYTES, TEXT_ATTACHMENT_TYPES


WORDS = re.compile(r"[^\W_]+")


def structured_text(value, channel):
    if isinstance(value, dict):
        if "contentType" in value and isinstance(value.get("data"), str):
            mime = value["contentType"]
            try:
                if not isinstance(mime, str) or mime.casefold() not in TEXT_ATTACHMENT_TYPES:
                    raise ValueError("unsupported_attachment")
                payload = base64.b64decode(value["data"], validate=True).decode("utf-8-sig")
                yield "attachment", payload
            except ValueError:
                yield "attachment", None
        for key, item in value.items():
            yield channel, key
            if key == "div" and isinstance(item, str) and item.lstrip().startswith("<"):
                try:
                    if "<!" in item or "<?" in item:
                        raise ValueError("unsupported_narrative")
                    yield "narrative", "".join(ElementTree.fromstring(item).itertext())
                except (ValueError, ElementTree.ParseError):
                    yield "narrative", None
            yield from structured_text(item, channel)
    elif isinstance(value, list):
        for item in value:
            yield from structured_text(item, channel)
    elif value is not None:
        yield channel, str(value)


def artifact_text(path, channel):
    with path.open("rb") as file:
        data = file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        yield channel, None
        return
    source = data.decode("utf-8-sig")
    suffix = path.suffix.lower()
    if suffix == ".json":
        yield from structured_text(json.loads(source), channel)
    elif suffix == ".jsonl":
        for line in source.splitlines():
            yield from structured_text(json.loads(line), channel)
    elif suffix in {".csv", ".tsv"}:
        delimiter = "," if suffix == ".csv" else "\t"
        for row in csv.reader(io.StringIO(source, newline=""), delimiter=delimiter, strict=True):
            for cell in row:
                yield channel, cell
    else:
        yield channel, source


def hits(text, by_anchor):
    text = norm(text)
    for word in WORDS.finditer(text):
        for surface, offset in by_anchor.get(word.group(), ()):
            start = word.start() - offset
            end = start + len(surface)
            if (start >= 0 and text.startswith(surface, start)
                    and (not start or not surface[0].isalnum() or not text[start - 1].isalnum())
                    and (end == len(text) or not surface[-1].isalnum() or not text[end].isalnum())):
                yield surface


def scan_known_surfaces(release, surfaces):
    """Report literal hits separately from role-aware occurrence outcomes."""
    by_anchor = defaultdict(list)
    for surface in {norm(value) for value in surfaces}:
        if anchor := WORDS.search(surface):
            by_anchor[anchor.group()].append((surface, anchor.start()))
    found = defaultdict(set)
    incomplete = 0
    for path in sorted(release.rglob("*")):
        relative = path.relative_to(release)
        if relative.parts[0] == "quarantine" or path.is_dir() and not path.is_symlink():
            continue
        if path.is_symlink() or not path.is_file():
            incomplete += 1
            continue
        for component in relative.parts:
            found["path"].update(hits(component.replace("_", " "), by_anchor))
            found["path"].update(hits(component, by_anchor))
        channel = {"sanitized": "record_content", "logs": "log", "report.json": "report",
                   "records.jsonl": "index"}.get(relative.parts[0], "other")
        fully_scanned = True
        try:
            for fragment_channel, text in artifact_text(path, channel):
                if text is None:
                    fully_scanned = False
                else:
                    found[fragment_channel].update(hits(text, by_anchor))
        except (OSError, ValueError, RecursionError, csv.Error):
            fully_scanned = False
        incomplete += not fully_scanned
    return {
        "known_unique_surfaces": sum(map(len, by_anchor.values())),
        "unique_surfaces_seen": len(set().union(*found.values())),
        "by_channel": {channel: len(values) for channel, values in found.items() if values},
        "artifacts_not_fully_scanned": incomplete,
    }
