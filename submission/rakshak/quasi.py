"""Conservative, source-only quasi-identifier transforms for patient CSV/TSV rows.

Only independently recognizable patient tables and explicitly named fields are
eligible. The caller retains responsibility for direct identifier detection, file
quarantine, and reporting whether a generalized row was actually released.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence


_AGE = frozenset({
    "age", "age years", "age yrs", "age y", "age in years", "age in yrs",
    "patient age", "patient age years", "patient age yrs", "patient age in years",
    "ageyears", "patientage", "ageyrs", "umar", "umr", "umar years", "umar yrs",
    "age saal", "उम्र", "आयु", "उम्र वर्ष", "आयु वर्ष",
    "मरीज की उम्र", "मरीज़ की उम्र", "रोगी की आयु", "रोगी की उम्र",
})
_PIN = frozenset({
    "pin", "pin code", "pincode", "zip", "zip code", "postal code", "postalcode",
    "patient pin", "address pin", "patient pin code", "postal pin",
    "पिन", "पिन कोड", "पिनकोड", "डाक कोड",
})
_LOCATION = frozenset({
    "village", "village name", "patient village", "patient locality",
    "locality", "locality name", "mohalla", "gram", "gaon", "village mohalla",
    "गांव", "गाँव", "ग्राम", "मोहल्ला", "मुहल्ला", "ग्राम मोहल्ला", "बस्ती",
})
_DISTRICT = frozenset({
    "district", "district name", "patient district", "address district",
    "jila", "zilla", "जिला", "ज़िला", "ज़िला",
})
_PATIENT = frozenset({
    "patient", "patient name", "patient full name", "patient id", "patientid",
    "patient identifier", "patient ref", "patient display", "patientname",
    "mrn", "uhid", "hospital uhid", "medical record no", "medical record number",
    "medical record id", "patient chart id", "patient chart", "beneficiary name",
    "रोगी का नाम", "मरीज का नाम", "मरीज़ का नाम", "mareez ka naam",
})
_NAME = frozenset({"name", "full name", "naam", "नाम", "first name", "last name"})
_REG = frozenset({
    "reg no", "reg number", "registration no", "registration number", "ipd no",
    "opd no", "admission no", "admission id", "hospital id",
})
_GOV = frozenset({
    "aadhaar", "aadhaar no", "aadhaar number", "aadhar", "aadhar no",
    "abha", "abha no", "abha number", "abha address", "आधार",
})
_CONTACT = frozenset({
    "phone", "phone no", "phone number", "mobile", "mobile no", "mobile number",
    "contact no", "contact number", "email", "email address", "फोन", "मोबाइल",
})
_NON_PATIENT = frozenset({
    "employee", "employee name", "employee id", "staff", "staff name", "staff id",
    "doctor id", "clinician id", "provider id", "specimen id", "sample id",
    "drug code", "product code",
})
_MISSING = frozenset({
    "", "-", "--", "na", "n/a", "none", "null", "unknown", "not known",
    "not available", "not applicable", "redacted", "withheld", "[redacted]",
    "[address]", "[locality]", "[village]", "अज्ञात", "उपलब्ध नहीं", "पता नहीं",
})


def _role(label: str) -> str:
    # Unlike general label normalization, keep words in parentheses. A field
    # called "Age (days)" must never be interpreted as age in years.
    if not isinstance(label, str):
        return ""
    label = unicodedata.normalize("NFKC", label)
    label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", label).casefold()
    words = (character if character.isalnum() or unicodedata.category(character).startswith("M")
             else " " for character in label)
    return " ".join("".join(words).split())


def _present(value: str) -> bool:
    return isinstance(value, str) and value.strip().casefold() not in _MISSING


def _decimal_digits(value: str) -> str | None:
    source = value.strip()
    if not source or len(source) > 6:
        return None
    try:
        return "".join(str(unicodedata.decimal(ch)) for ch in source)
    except ValueError:
        return None


def _location(value: str) -> str | None:
    if not _present(value):
        return None
    cleaned = value.strip()
    if len(cleaned) > 128 or not any(ch.isalpha() for ch in cleaned):
        return None
    if any(unicodedata.category(ch).startswith("C") for ch in cleaned):
        return None
    return cleaned


def _district(value: str) -> str | None:
    cleaned = _location(value)
    # The field must be a single, plain district name, not a free-form address.
    # Some genuine district labels have digits; conservatively abstain from
    # duplicating their names instead of guessing how to parse them.
    if cleaned and all(unicodedata.category(ch)[0] in "LM" or ch in " .-'’"
                       for ch in cleaned):
        return cleaned
    return None


def _patient_row(roles: list[str], row: Sequence[str]) -> bool:
    present = {role for role, value in zip(roles, row) if _present(value)}
    if _PATIENT & present:
        return True
    # Localized registration schemas may use only generic names and numbered
    # registration fields. Require all three independent identity-role groups.
    return not (_NON_PATIENT & present) and bool(
        _NAME & present and _REG & present and _GOV & present and _CONTACT & present
    )


def generalize_row(header: Sequence[str], row: Sequence[str]) -> dict[int, str]:
    """Return only changed existing-cell index/value pairs, without mutating input.

    Age is generalized to an inclusive, truthful five-year band only when the
    source is an exact age of 0..125 years. PINs become a truthful three-digit
    prefix plus "***". A locality may use the explicitly supplied district from
    the same row only when exactly one plausible district field exists.

    CSV/TSV cell strings remain strings. Do not apply this adapter to JSON, FHIR,
    free-text notes, or unproven field roles. A district role is source-structural
    evidence, not independently validated geographic truth.
    """
    if isinstance(header, str) or isinstance(row, str) or len(header) != len(row):
        return {}
    if not all(isinstance(value, str) for value in row):
        return {}
    roles = [_role(label) for label in header]
    if not _patient_row(roles, row):
        return {}

    district_indices = [i for i, role in enumerate(roles) if role in _DISTRICT]
    district = _district(row[district_indices[0]]) if len(district_indices) == 1 else None
    # Do not duplicate a same-row personal name disguised as a district.
    if district and any(role in (_PATIENT | _NAME) and district.casefold() == value.strip().casefold()
                        for role, value in zip(roles, row)):
        district = None

    changes = {}
    for i, (role, value) in enumerate(zip(roles, row)):
        if role in _AGE:
            digits = _decimal_digits(value)
            if digits is not None and len(digits) <= 3:
                age = int(digits)
                if 0 <= age <= 125:
                    low = age // 5 * 5
                    changes[i] = f"{low}-{low + 4}"
        elif role in _PIN:
            digits = _decimal_digits(value)
            if digits is not None and len(digits) == 6 and digits[0] != "0":
                changes[i] = digits[:3] + "***"
        elif role in _LOCATION and district is not None and _location(value) is not None:
            if value != district:
                changes[i] = district
    return changes
