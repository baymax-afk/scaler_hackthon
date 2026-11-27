"""Parse and rewrite supported formats without flattening their structure."""
import base64
import binascii
from collections import Counter
import csv
from decimal import Decimal
import io
import json
import re
import unicodedata
import xml.etree.ElementTree as ET

from .detection import FIELDS, NAME, SourceUnit, detect
from .source_context import normalize_label, source_section, structured_label
from .linkage import row_evidence
from .quasi import generalize_row


UUID = re.compile(r"(?:urn:uuid:)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
XHTML = "http://www.w3.org/1999/xhtml"
FHIR_DATE_FIELDS = {"birthDate", "date", "effectiveDateTime", "issued", "timestamp",
                    "start", "end", "recordedDate"}
ET.register_namespace("", XHTML)


class UnsafeInput(Exception):
    pass


def decode(raw):
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16")
    elif raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig")
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1252")
    if not text.strip():
        raise UnsafeInput("empty_file")
    if any(ord(character) < 32 and character not in "\t\r\n" for character in text):
        raise UnsafeInput("invalid_control_character")
    return text


class Rewrite:
    def __init__(self, secret=None):
        self.entities = []
        self.secret = secret
        self.row_evidence = {}
        self.generalized = set()

    def findings(self, text, **context):
        result = detect(SourceUnit(text, **context))
        if result.error:
            raise UnsafeInput(result.error)
        if result.review:
            raise UnsafeInput("ambiguous_identifier")
        self.entities.extend(finding.kind for finding in result.findings)
        return result.findings

    def text(self, value, **context):
        cursor = 0
        parts = []
        for finding in self.findings(value, **context):
            parts.extend((value[cursor:finding.start], "[" + finding.kind + "]"))
            cursor = finding.end
        return "".join((*parts, value[cursor:]))


def table(text, extension, rewrite):
    delimiter = "\t" if extension == ".tsv" else ","
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    header = next(reader, [])
    if len(header) < 2 and any(char in text.partition("\n")[0] for char in ",\t;"):
        raise UnsafeInput("mislabeled_delimiter")
    renamed = [rewrite.text(label, channel="header") for label in header]
    # Two distinct identifying column labels may redact to the same text.
    # Disambiguate only rewritten labels using their position, never raw data.
    reserved = set(renamed)
    collisions = Counter(renamed)
    for index, (original, cleaned) in enumerate(zip(header, renamed)):
        if original != cleaned and collisions[cleaned] > 1:
            candidate = f"{cleaned}__col{index + 1}"
            while candidate in reserved:
                candidate += "_"
            reserved.add(candidate)
            renamed[index] = candidate
    if len(set(renamed)) < len(set(header)):
        raise UnsafeInput("header_collision")
    patient_table = any(normalize_label(label) in FIELDS or
                        normalize_label(label) in PERSON_NAME_FIELDS or
                        normalize_label(label) in PATIENT_FIELDS or
                        normalize_label(label).startswith("patient ") or
                        detect(SourceUnit(label, channel="header")).findings for label in header)
    destination = io.StringIO(newline="")
    writer = csv.writer(destination, delimiter=delimiter, lineterminator="\n")
    writer.writerow(renamed)
    locations = []
    for index, row in enumerate(reader):
        if len(row) != len(header):
            raise UnsafeInput("ragged_table")
        locator = f"row:{index}"
        generalized = generalize_row(header, row) if patient_table else {}
        cleaned = []
        for column, (label, value) in enumerate(zip(header, row)):
            sanitized = rewrite.text(value, label=label)
            cleaned.append(generalized.get(column, sanitized))
        if patient_table:
            locations.append(locator)
            if generalized:
                rewrite.generalized.add(locator)
            if rewrite.secret is not None:
                evidence = row_evidence(header, row, rewrite.secret)
                if evidence is not None and cleaned[evidence.column].strip() in {
                    "[MRN]", "[AADHAAR]", "[ABHA]", "[PHONE]", "[EMAIL]", "[PAN]", "[INSURANCE_ID]"
                }:
                    rewrite.row_evidence[locator] = evidence
        writer.writerow(cleaned)
    return destination.getvalue(), locations


def unique_pairs(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise UnsafeInput("duplicate_json_key")
    return result


def invalid_constant(_value):
    raise UnsafeInput("invalid_json_number")


def encode_json(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return "[" + ",".join(map(encode_json, value)) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(encode_json(key) + ":" + encode_json(item)
                             for key, item in value.items()) + "}"
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def pointer(value):
    return value.replace("~", "~0").replace("/", "~1")


PATIENT_COLLECTIONS = {"patients", "visits", "encounters", "registrations"}
PATIENT_FIELDS = {"patient", "patient name", "patient ref", "patient id", "patient identifier",
                  "uhid", "mrn"}
PERSON_NAME_FIELDS = {"name", "naam", "नाम"}
PERSON_CONTACT_FIELDS = {"phone", "phone number", "mobile", "फोन", "फ़ोन", "email"}
CLINICAL_FIELDS = {"diagnosis", "complaints", "history", "vitals", "rx", "microscopy",
                   "chat", "action plan", "observation", "prescription"}
CONTACT_VALUE = re.compile(r"(?i)[\w.+-]+@[\w.-]+\.[a-z]{2,}|(?<!\d)[6-9]\d{9}(?!\d)")


def patient_evidence(record):
    """Find record roles from structure, independently of detector hits."""
    roles = set()
    pending = [(record, 0)]
    while pending:
        value, depth = pending.pop()
        if depth > 8:
            continue
        if isinstance(value, dict):
            for key, item in value.items():
                label = normalize_label(key)
                if label in PATIENT_FIELDS or label.startswith("patient "):
                    roles.add("patient")
                if label in PERSON_NAME_FIELDS and isinstance(item, str) and item.strip():
                    roles.add("person_name")
                if label in PERSON_CONTACT_FIELDS and isinstance(item, str) and item.strip():
                    roles.add("person_contact")
                if label == "subject" and isinstance(item, dict) and isinstance(item.get("display"), str):
                    roles.add("patient")
                if label in CLINICAL_FIELDS:
                    roles.add("clinical")
                if isinstance(item, str) and CONTACT_VALUE.search(item):
                    roles.add("contact")
                if isinstance(item, (dict, list)):
                    pending.append((item, depth + 1))
        elif isinstance(value, list):
            pending.extend((item, depth + 1) for item in value)
    return ("patient" in roles or {"clinical", "contact"} <= roles
            or {"person_name", "person_contact"} <= roles)


def json_record_locators(document):
    if isinstance(document, list):
        if not document:
            return []
        candidates = [isinstance(item, dict) and patient_evidence(item) for item in document]
        if any(candidates) and not all(candidates):
            raise UnsafeInput("ambiguous_record_collection")
        return [f"/{index}" for index in range(len(document))] if all(candidates) else []
    if not isinstance(document, dict):
        return []
    collections = []
    for key, value in document.items():
        if not isinstance(value, list) or not value:
            continue
        if not all(isinstance(item, dict) for item in value):
            continue
        expected = normalize_label(key) in PATIENT_COLLECTIONS
        evidence = [patient_evidence(item) for item in value]
        if expected or any(evidence):
            if not expected and not all(evidence):
                raise UnsafeInput("ambiguous_record_collection")
            if detect(SourceUnit(key, channel="key")).findings:
                raise UnsafeInput("unsafe_record_locator")
            collections.append((key, len(value)))
    if len(collections) > 1:
        raise UnsafeInput("ambiguous_record_collection")
    if collections:
        key, length = collections[0]
        return [f"/{pointer(key)}/{index}" for index in range(length)]
    return ["doc"] if patient_evidence(document) else []


def json_document(text, rewrite):
    document = json.loads(text, object_pairs_hook=unique_pairs,
                          parse_float=Decimal, parse_constant=invalid_constant)
    fhir = isinstance(document, dict) and document.get("resourceType") == "Bundle"
    if fhir:
        return fhir_document(document, rewrite)
    locations = json_record_locators(document)
    result = walk(document, rewrite)
    return encode_json(result) + "\n", locations


def walk(value, rewrite, path=(), label="", unit="", resource="", siblings=None, name_surfaces=()):
    if len(path) > 80:
        raise UnsafeInput("json_depth_limit")
    if isinstance(value, dict):
        # A link can grant access to the unsanitized document behind it.
        if resource and "url" in value and ("contentType" in value or label == "attachment"):
            raise UnsafeInput("uninspected_attachment_url")
        if resource and "data" in value and "contentType" in value and ({"size", "hash"} & value.keys()):
            raise UnsafeInput("unsupported_attachment_integrity_metadata")
        result = {}
        raw_unit = value.get("unit", "")
        unit = raw_unit if isinstance(raw_unit, str) else ""
        resource_type = value.get("resourceType")
        if resource and isinstance(resource_type, str):
            resource = resource_type
            name_surfaces = human_name_surfaces(value) if resource in {"Patient", "RelatedPerson"} else ()
        for key, item in value.items():
            attachment_field = normalize_label(key) in {"attachment", "data base64", "base64", "b64", "payload base64"}
            typed_attachment = resource and isinstance(item, dict) and "contentType" in item
            if attachment_field and item and not typed_attachment:
                raise UnsafeInput("unsupported_attachment")
            if resource and key == "data" and isinstance(item, str):
                result[key] = attachment(item, value.get("contentType"), rewrite)
                continue
            updated = rewrite.text(key, channel="key")
            if updated in result or (resource and updated != key):
                raise UnsafeInput("json_key_collision_or_fhir_key")
            result[updated] = walk(item, rewrite, (*path, key), key, unit, resource, value, name_surfaces)
        return result
    if isinstance(value, list):
        return [walk(item, rewrite, (*path, index), label, unit, resource, siblings, name_surfaces)
                for index, item in enumerate(value)]
    label = structured_label(path, label, resource, siblings)
    if isinstance(value, str):
        if resource and label == "div" and "text" in path:
            return narrative(value, rewrite, resource, name_surfaces)
        if resource and label in FHIR_DATE_FIELDS:
            if rewrite.findings(value, label=label):
                raise UnsafeInput("unsupported_fhir_date_transform")
            return value
        if resource and label in {"fullUrl", "reference", "id", "system", "url", "resourceType"}:
            reference_id = value.partition("/")[2] if label == "reference" and "/" in value else value
            if not UUID.fullmatch(reference_id.lstrip("#")) and rewrite.findings(value):
                raise UnsafeInput("unsafe_fhir_structure")
            return value
        if resource and label == "source" and "meta" in path:
            return "urn:rakshak:redacted" if rewrite.findings(value, label="source path") else value
        return rewrite.text(value, label=label, section=source_section(label, resource),
                            unit_of_measure=unit)
    if type(value) in {int, Decimal}:
        if rewrite.findings(str(value), label=label, unit_of_measure=unit):
            return 0 if type(value) is int else Decimal(0)
    return value


def attachment(value, content_type, rewrite):
    if not isinstance(content_type, str) or content_type.casefold() not in {
        "text/plain", "text/plain; charset=utf-8",
    }:
        raise UnsafeInput("unsupported_attachment")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise UnsafeInput("invalid_attachment") from None
    cleaned = rewrite.text(decode(decoded))
    return base64.b64encode(cleaned.encode("utf-8")).decode("ascii")


def normalized_name(value):
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def human_name_surfaces(resource):
    names = resource.get("name")
    surfaces = set()
    for name in names if isinstance(names, list) else ():
        if not isinstance(name, dict):
            continue
        if isinstance(name.get("text"), str):
            surfaces.add(normalized_name(name["text"]))
        given, family = name.get("given"), name.get("family")
        if isinstance(given, list) and given and all(isinstance(part, str) for part in given) \
                and isinstance(family, str) and family:
            surfaces.add(normalized_name(" ".join([*given, family])))
    return surfaces - {""}


def narrative(text, rewrite, resource, name_surfaces):
    if "<!" in text or "<?" in text:
        raise UnsafeInput("unsupported_fhir_narrative")
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        raise UnsafeInput("invalid_fhir_narrative") from None
    if root.tag != f"{{{XHTML}}}div":
        raise UnsafeInput("invalid_fhir_narrative")
    for element in root.iter():
        if not element.tag.startswith(f"{{{XHTML}}}") or element.tag.split("}")[-1] in {"script", "iframe", "object"}:
            raise UnsafeInput("unsupported_fhir_narrative")
        if any(key.casefold().startswith("on") or rewrite.findings(value)
               for key, value in element.attrib.items()):
            raise UnsafeInput("unsafe_fhir_narrative_attribute")
    for element in root.iter():
        if name_surfaces and (
            element is root or element.tag.removeprefix(f"{{{XHTML}}}") in {"p", "h1", "h2", "h3"}
        ):
            block = "".join(element.itertext())
            if normalized_name(block) in name_surfaces:
                label = "patient name" if resource == "Patient" else "related person name"
                element.text = rewrite.text(block, label=label, section="fhir")
                for descendant in element.iter():
                    if descendant is not element:
                        descendant.text = descendant.tail = None
        if element.text:
            fragment = element.text
            if resource in {"Patient", "RelatedPerson"} and element is root:
                title = re.match(r"^(" + NAME + r"),[ 	]*[0-9]{1,3}[ 	]*(?:years|yrs)\b", fragment, re.I)
                if title:
                    fragment = rewrite.text(title[1], label="patient name") + fragment[title.end(1):]
            element.text = rewrite.text(fragment)
        if element.tail:
            element.tail = rewrite.text(element.tail)
    return ET.tostring(root, encoding="unicode")


def local_references(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "reference" and isinstance(item, str):
                yield item
            elif key != "contained":
                yield from local_references(item)
    elif isinstance(value, list):
        for item in value:
            yield from local_references(item)


def validate_references(entries):
    urls = [entry["fullUrl"] for entry in entries if isinstance(entry.get("fullUrl"), str)]
    if len(set(urls)) != len(urls):
        raise UnsafeInput("duplicate_fhir_reference_target")
    targets = set(urls)
    for entry in entries:
        resource = entry["resource"]
        if isinstance(resource.get("id"), str):
            targets.add(resource["resourceType"] + "/" + resource["id"])
    for entry in entries:
        resource = entry["resource"]
        children = resource.get("contained", [])
        if not isinstance(children, list):
            raise UnsafeInput("invalid_fhir_contained")
        contained = {"#" + item["id"] for item in children
                     if isinstance(item, dict) and isinstance(item.get("id"), str)}
        references = list(local_references(resource))
        for child in children:
            references.extend(local_references(child))
        for reference in references:
            if reference.startswith("#") and reference not in contained:
                raise UnsafeInput("unresolved_fhir_reference")
            if (reference.startswith(("urn:uuid:", "urn:oid:")) or re.fullmatch(r"[A-Z][A-Za-z]+/[^/]+", reference)):
                if reference not in targets:
                    raise UnsafeInput("unresolved_fhir_reference")


def fhir_document(bundle, rewrite):
    entries = bundle.get("entry", [])
    if not isinstance(entries, list) or not isinstance(bundle.get("type"), str):
        raise UnsafeInput("invalid_fhir_bundle")
    if any(not isinstance(entry, dict) or not isinstance(entry.get("resource"), dict)
           or not isinstance(entry["resource"].get("resourceType"), str) for entry in entries):
        raise UnsafeInput("invalid_fhir_entry")
    patients = sum(entry["resource"]["resourceType"] == "Patient" for entry in entries)
    if patients > 1:
        raise UnsafeInput("multiple_fhir_patients")
    validate_references(entries)
    result = walk(bundle, rewrite, resource="Bundle")
    validate_references(result.get("entry", []))
    return encode_json(result) + "\n", ["doc"] if patients else []


def transform(text, extension, rewrite):
    if extension in {".csv", ".tsv"}:
        return table(text, extension, rewrite)
    if extension == ".json":
        return json_document(text, rewrite)
    if extension == ".txt":
        result = rewrite.text(text)
        return result, ["doc"]
    raise UnsafeInput("unsupported_format")
