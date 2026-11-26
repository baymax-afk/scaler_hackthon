"""Build evaluator source units from the raw input tree alone."""
import base64
import csv
from decimal import Decimal
from hashlib import sha256
import io
import json


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
        return raw.decode("utf-16")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


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


def structured_label(label, fields, resource, contact_system):
    if resource in {"Patient", "RelatedPerson"}:
        if "name" in fields and label in {"text", "given", "family"}:
            return "relative name" if resource == "RelatedPerson" or "contact" in fields else "patient name"
        if "telecom" in fields and label == "value":
            return {"phone": "phone", "email": "email"}.get(contact_system, label)
        if "identifier" in fields and label == "value":
            return "patient identifier"
        if "address" in fields and label in {"line", "postalCode", "text", "city"}:
            return "address"
    if resource == "Practitioner" and "name" in fields:
        return "clinician name"
    if "valueQuantity" in fields and label == "value":
        return "observation value"
    return label


def json_units(relative, value, path="", fields=(), resource="", label="", contact_system="",
               unit_of_measure="", depth=0):
    if depth > 80:
        raise ValueError("source_inventory_depth_limit")
    if isinstance(value, dict):
        declared_resource = value.get("resourceType")
        if resource and isinstance(declared_resource, str):
            resource = declared_resource
        declared_system = value.get("system")
        system = declared_system if isinstance(declared_system, str) else contact_system
        measure = value.get("unit", "")
        for key, item in value.items():
            child = path + "/" + pointer_segment(key)
            yield unit(relative, "key", child, key)
            mime = value.get("contentType")
            if (resource and key == "data" and isinstance(item, str)
                    and isinstance(mime, str) and mime.casefold() in TEXT_ATTACHMENT_TYPES):
                text = base64.b64decode(item, validate=True).decode("utf-8")
                yield unit(relative, "content", child, text)
            else:
                yield from json_units(relative, item, child, (*fields, key), resource, key,
                                      system, measure if isinstance(measure, str) else "",
                                      depth + 1)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from json_units(relative, item, path + "/" + str(index), fields, resource,
                                  label, contact_system, unit_of_measure, depth + 1)
    elif isinstance(value, str) or type(value) in {int, Decimal}:
        yield unit(relative, "content", path or "doc", str(value),
                   label=structured_label(label, fields, resource, contact_system),
                   unit_of_measure=unit_of_measure)


def unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("source_inventory_duplicate_key")
    return result


def source_inventory(incoming):
    if not incoming.is_dir():
        raise ValueError("source_inventory_missing_input")
    for path in sorted(incoming.rglob("*")):
        if path.is_symlink():
            raise ValueError("source_inventory_symlink")
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in {".csv", ".tsv", ".txt", ".json"}:
            raise ValueError("source_inventory_unsupported_type")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("source_inventory_file_limit")
        relative = path.relative_to(incoming).as_posix()
        raw = path.read_bytes()
        yield unit(relative, "filename", "doc", path.name)
        if suffix in {".csv", ".tsv"}:
            yield from table_units(relative, raw, "," if suffix == ".csv" else "\t")
        elif suffix == ".txt":
            yield unit(relative, "content", "doc", decode_text(raw))
        else:
            document = json.loads(decode_text(raw), object_pairs_hook=unique_object,
                                  parse_float=Decimal)
            fhir = isinstance(document, dict) and document.get("resourceType") == "Bundle"
            yield from json_units(relative, document, resource="Bundle" if fhir else "")


def annotated_source_id(record, annotation):
    locator = record["loc"]
    location = annotation["location"]
    if location != "doc":
        locator = location if locator == "doc" else (
            locator + "/" + location if record["format"] in {"csv", "tsv"} else locator + location)
    return source_id(record["file"], annotation.get("channel", "content"), locator)
