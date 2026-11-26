"""Offline structural smoke check for synthetic FHIR R4 document Bundles.

This is not a full R4 validator and makes no ABDM profile conformance claim.
It checks only a narrow, local subset needed by the open development fixture.
"""

import base64
import binascii
from datetime import date, datetime
import re
import uuid


RESOURCE_ID = re.compile(r"[A-Za-z0-9.-]{1,64}\Z")
RESOURCE_TYPE = re.compile(r"[A-Z][A-Za-z0-9]*\Z")
UUID_URL = re.compile(r"urn:uuid:([0-9a-fA-F-]{36})\Z")
RELATIVE_REFERENCE = re.compile(r"([A-Z][A-Za-z0-9]*)/([A-Za-z0-9.-]{1,64})\Z")
PARTIAL_DATE = re.compile(r"([0-9]{4})(?:-([0-9]{2})(?:-([0-9]{2}))?)?\Z")
TIME_VALUE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
                        r"(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})\Z")
DATE_KEYS = {"date", "birthDate", "timestamp", "issued", "effectiveDateTime",
             "creation", "start", "end", "recordedDate"}


def _check_date(value):
    if not isinstance(value, str):
        raise ValueError("invalid_fhir_date")
    match = PARTIAL_DATE.fullmatch(value)
    if match:
        try:
            year, month, day = match.groups()
            if day is not None:
                date(int(year), int(month), int(day))
            elif month is not None:
                date(int(year), int(month), 1)
            else:
                date(int(year), 1, 1)
            return
        except ValueError as exc:
            raise ValueError("invalid_fhir_date") from exc
    if TIME_VALUE.fullmatch(value):
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return
        except ValueError as exc:
            raise ValueError("invalid_fhir_date") from exc
    raise ValueError("invalid_fhir_date")


def _walk(value, full_urls, identities):
    if isinstance(value, list):
        for item in value:
            _walk(item, full_urls, identities)
        return
    if not isinstance(value, dict):
        return
    reference = value.get("reference")
    if reference is not None:
        if not isinstance(reference, str) or not reference:
            raise ValueError("invalid_fhir_reference")
        if reference.startswith("urn:uuid:"):
            if reference not in full_urls:
                raise ValueError("unresolved_fhir_reference")
        elif RELATIVE_REFERENCE.fullmatch(reference):
            if reference not in identities:
                raise ValueError("unresolved_fhir_reference")
        elif not (reference.startswith("http://") or reference.startswith("https://")):
            raise ValueError("invalid_fhir_reference")
    # Attachment is a complex data type and has no resourceType member. Any
    # inline data in this document subset must be well-formed base64Binary.
    if "data" in value:
        _check_attachment_data(value["data"])
    for key, child in value.items():
        if key in DATE_KEYS:
            _check_date(child)
        _walk(child, full_urls, identities)


def _check_attachment_data(value):
    if not isinstance(value, str):
        raise ValueError("invalid_fhir_attachment_data")
    try:
        base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid_fhir_attachment_data") from exc


def check_fhir_bundle(bundle):
    """Return aggregate entry count or raise a stable, data-free ValueError code."""
    if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle" or \
            bundle.get("type") != "document":
        raise ValueError("invalid_fhir_bundle")
    entries = bundle.get("entry")
    if not isinstance(entries, list) or not entries:
        raise ValueError("invalid_fhir_entries")
    if not isinstance(entries[0], dict) or \
            not isinstance(entries[0].get("resource"), dict) or \
            entries[0]["resource"].get("resourceType") != "Composition":
        raise ValueError("missing_fhir_composition")

    full_urls = set()
    canonical_urls = set()
    identities = set()
    patient_count = 0
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("resource"), dict):
            raise ValueError("invalid_fhir_entry")
        full_url = entry.get("fullUrl")
        match = UUID_URL.fullmatch(full_url) if isinstance(full_url, str) else None
        if match is None:
            raise ValueError("invalid_fhir_full_url")
        try:
            if str(uuid.UUID(match.group(1))) != match.group(1).lower():
                raise ValueError("invalid_fhir_full_url")
        except ValueError as exc:
            raise ValueError("invalid_fhir_full_url") from exc
        if full_url.lower() in canonical_urls:
            raise ValueError("duplicate_fhir_full_url")
        full_urls.add(full_url)
        canonical_urls.add(full_url.lower())
        resource = entry["resource"]
        kind, identifier = resource.get("resourceType"), resource.get("id")
        if not isinstance(kind, str) or not RESOURCE_TYPE.fullmatch(kind) or \
                not isinstance(identifier, str) or not RESOURCE_ID.fullmatch(identifier):
            raise ValueError("invalid_fhir_resource_id")
        identity = f"{kind}/{identifier}"
        if identity in identities:
            raise ValueError("duplicate_fhir_resource_id")
        identities.add(identity)
        patient_count += kind == "Patient"
    if patient_count != 1:
        raise ValueError("invalid_fhir_patient_count")
    _walk(bundle, full_urls, identities)
    return {"entries": len(entries)}
