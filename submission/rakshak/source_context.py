"""Interpret field roles from source paths without consulting detector rules."""
import re
import unicodedata


CLINICIAN_FIELDS = {"doctor", "physician", "provider", "clinician", "attending", "practitioner"}
NON_PATIENT_SECTIONS = CLINICIAN_FIELDS | {"diagnosis", "assessment", "specimen", "organization"}
CONTACT_FIELDS = {"email", "email address", "address", "contact email"}
EMAIL_ADDRESS = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


def normalize_label(label):
    label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", label)
    label = re.sub(r"\([^)]*\)", "", label.casefold())
    words = (character if character.isalnum() or unicodedata.category(character).startswith("M")
             else " " for character in label)
    return " ".join("".join(words).split())


def structured_label(path, label, resource, siblings=None):
    siblings = siblings or {}
    if not resource:
        leaf = normalize_label(label)
        if leaf in {"name", "display", "display name"}:
            containers = [normalize_label(part) for part in path[:-1] if isinstance(part, str)]
            if any(part in CLINICIAN_FIELDS for part in containers):
                return "clinician name"
            if containers and not NON_PATIENT_SECTIONS.intersection(containers):
                parent = containers[-1]
                if parent in {"patient", "beneficiary"} or parent == "subject" and any(
                    normalize_label(key) in CONTACT_FIELDS and isinstance(value, str)
                    and EMAIL_ADDRESS.fullmatch(value.strip())
                    for key, value in siblings.items()
                ):
                    return "patient display"
        return label

    if "identifier" in path and label == "value":
        return "patient identifier"
    if "name" in path:
        if resource in {"Patient", "RelatedPerson"} and label in {"text", "given", "family"}:
            if resource == "RelatedPerson":
                return "related person name"
            return "contact name" if "contact" in path else "patient name"
        if resource == "Practitioner":
            return "clinician name"
    if resource in {"Patient", "RelatedPerson"}:
        if "telecom" in path and label == "value":
            return "email" if siblings.get("system") == "email" else "phone"
        if "address" in path and label in {"line", "postalCode", "text", "city"}:
            return "address"
    if "valueQuantity" in path and label == "value":
        return "observation value"
    if label == "name" and isinstance(path[-1], str):
        return ""
    return label


def source_section(label, resource):
    return "fhir" if resource and label in {"contact name", "related person name"} else ""
