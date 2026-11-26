"""Build evaluator source units from the raw input tree alone."""
import base64
import csv
from decimal import Decimal
from hashlib import sha256
import io
import json

from submission.rakshak.source_context import source_section, structured_label


MAX_FILE_BYTES = 16 * 1024 * 1024
TEXT_ATTACHMENT_TYPES = {"text/plain", "text/plain; charset=utf-8"}


def pointer_segment(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def source_id(relative, channel, locator):
    payload = json.dumps((relative, channel, locator), ensure_ascii=True)
    return sha256(payload.encode()).hexdigest()[:32]


def unit(relative, channel, locator, text, **context):
    return {"id": source_id(relative, channel, locator), "text": text, "channel": channel,
            **context}


def decode_text(raw):
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16")
    elif raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig")
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1252")
    if not text.strip() or any(ord(char) < 32 and char not in "\t\r\n" for char in text):
        raise ValueError("source_inventory_invalid_text")
    return text


def table_units(relative, raw, delimiter):
    reader = csv.reader(io.StringIO(decode_text(raw), newline=""), delimiter=delimiter,
                        strict=True)
    header = next(reader, [])
    for index, value in enumerate(header):
        yield unit(relative, "header", str(index), value)
    for index, row in enumerate(reader):
        if len(row) != len(header):
            raise ValueError("source_inventory_ragged_table")
        for column, (label, value) in enumerate(zip(header, row)):
            yield unit(relative, "content", f"row:{index}/{column}", value, label=label)


def json_units(relative, value, path="", fields=(), resource="", label="", siblings=None,
               unit_of_measure="", depth=0):
    if depth > 80:
        raise ValueError("source_inventory_depth_limit")
    if isinstance(value, dict):
        declared_resource = value.get("resourceType")
        if resource and isinstance(declared_resource, str):
            resource = declared_resource
        measure = value.get("unit", "")
        for key, item in value.items():
            child = path + "/" + pointer_segment(key)
            yield unit(relative, "key", child, key)
            mime = value.get("contentType")
            if (resource and key == "data" and isinstance(item, str)
                    and isinstance(mime, str) and mime.casefold() in TEXT_ATTACHMENT_TYPES):
                text = decode_text(base64.b64decode(item, validate=True))
                yield unit(relative, "content", child, text)
            else:
                yield from json_units(relative, item, child, (*fields, key), resource, key,
                                      value, measure if isinstance(measure, str) else "",
                                      depth + 1)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from json_units(relative, item, path + "/" + str(index), (*fields, index), resource,
                                  label, siblings, unit_of_measure, depth + 1)
    elif isinstance(value, str) or type(value) in {int, Decimal}:
        source_label = structured_label(fields, label, resource, siblings)
        yield unit(relative, "content", path or "doc", str(value), label=source_label,
                   section=source_section(source_label, resource),
                   unit_of_measure=unit_of_measure)


def unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("source_inventory_duplicate_key")
    return result


def invalid_number(_value):
    raise ValueError("source_inventory_invalid_number")


def content_units(relative, suffix, raw):
    if suffix in {".csv", ".tsv"}:
        yield from table_units(relative, raw, "," if suffix == ".csv" else "\t")
    elif suffix == ".txt":
        yield unit(relative, "content", "doc", decode_text(raw))
    else:
        document = json.loads(decode_text(raw), object_pairs_hook=unique_object,
                              parse_float=Decimal, parse_constant=invalid_number)
        fhir = isinstance(document, dict) and document.get("resourceType") == "Bundle"
        yield from json_units(relative, document, resource="Bundle" if fhir else "")


def source_inventory(incoming):
    if not incoming.is_dir():
        raise ValueError("source_inventory_missing_input")
    for path in sorted(incoming.rglob("*")):
        if path.is_symlink():
            raise ValueError("source_inventory_symlink")
        if not path.is_file():
            continue
        relative = path.relative_to(incoming).as_posix()
        suffix = path.suffix.lower()
        if suffix not in {".csv", ".tsv", ".txt", ".json"}:
            yield unit(relative, "file", "doc", "", parse_error="unsupported_format")
            continue
        try:
            with path.open("rb") as source:
                raw = source.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES:
                yield unit(relative, "file", "doc", "", parse_error="file_limit")
                continue
            contents = list(content_units(relative, suffix, raw))
        except (ValueError, RecursionError, csv.Error):
            yield unit(relative, "file", "doc", "", parse_error="invalid_input")
            continue
        except OSError:
            yield unit(relative, "file", "doc", "", parse_error="unreadable_input")
            continue
        yield unit(relative, "filename", "doc", path.name)
        yield from contents


def annotated_source_id(record, annotation):
    locator = record["loc"]
    location = annotation["location"]
    if location != "doc":
        locator = location if locator == "doc" else (
            locator + "/" + location if record["format"] in {"csv", "tsv"} else locator + location)
    return source_id(record["file"], annotation.get("channel", "content"), locator)
