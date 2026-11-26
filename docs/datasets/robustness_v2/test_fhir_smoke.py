"""Narrow structural checks; these do not establish R4 or ABDM conformance."""

from copy import deepcopy
import unittest

from fhir_smoke import check_fhir_bundle


def example():
    composition_url = "urn:uuid:00000000-0000-4000-8000-000000000001"
    patient_url = "urn:uuid:00000000-0000-4000-8000-000000000002"
    practitioner_url = "urn:uuid:00000000-0000-4000-8000-000000000003"
    observation_url = "urn:uuid:00000000-0000-4000-8000-000000000004"
    return {
        "resourceType": "Bundle", "type": "document", "timestamp": "2025-01-02T10:30:00Z",
        "entry": [
            {"fullUrl": composition_url,
             "resource": {"resourceType": "Composition", "id": "composition-1",
                          "date": "2025-01-02T10:30:00Z",
                          "subject": {"reference": patient_url},
                          "author": [{"reference": practitioner_url}],
                          "section": [{"entry": [{"reference": observation_url}]}]}},
            {"fullUrl": patient_url,
             "resource": {"resourceType": "Patient", "id": "patient-1",
                          "birthDate": "1990-05-10"}},
            {"fullUrl": practitioner_url,
             "resource": {"resourceType": "Practitioner", "id": "practitioner-1"}},
            {"fullUrl": observation_url,
             "resource": {"resourceType": "Observation", "id": "observation-1",
                          "subject": {"reference": "Patient/patient-1"},
                          "effectiveDateTime": "2025-01-02T10:30:00+05:30",
                          "valueQuantity": {"value": 120, "unit": "mmHg"},
                          "note": [{"text": "Synthetic clinical note"}],
                          "attachment": {"contentType": "text/plain", "data": "dGVzdA=="}}},
        ],
    }


class FhirSmokeTest(unittest.TestCase):
    def test_accepts_document_with_internal_references_dates_and_attachment(self):
        self.assertEqual(check_fhir_bundle(example()), {"entries": 4})

    def test_unresolved_reference(self):
        bundle = example()
        bundle["entry"][0]["resource"]["subject"]["reference"] = \
            "urn:uuid:00000000-0000-4000-8000-000000000099"
        with self.assertRaisesRegex(ValueError, "^unresolved_fhir_reference$"):
            check_fhir_bundle(bundle)

    def test_duplicate_full_url(self):
        bundle = example()
        bundle["entry"][2]["fullUrl"] = bundle["entry"][1]["fullUrl"]
        with self.assertRaisesRegex(ValueError, "^duplicate_fhir_full_url$"):
            check_fhir_bundle(bundle)

    def test_missing_first_composition(self):
        bundle = example()
        bundle["entry"] = bundle["entry"][1:]
        with self.assertRaisesRegex(ValueError, "^missing_fhir_composition$"):
            check_fhir_bundle(bundle)

    def test_multiple_patients(self):
        bundle = example()
        second = deepcopy(bundle["entry"][1])
        second["fullUrl"] = "urn:uuid:00000000-0000-4000-8000-000000000005"
        second["resource"]["id"] = "patient-2"
        bundle["entry"].append(second)
        with self.assertRaisesRegex(ValueError, "^invalid_fhir_patient_count$"):
            check_fhir_bundle(bundle)

    def test_invalid_base64(self):
        bundle = example()
        bundle["entry"][3]["resource"]["attachment"]["data"] = "not base64?"
        with self.assertRaisesRegex(ValueError, "^invalid_fhir_attachment_data$"):
            check_fhir_bundle(bundle)

    def test_invalid_iso_date_and_invalid_uuid(self):
        bundle = example()
        bundle["entry"][1]["resource"]["birthDate"] = "2025-02-30"
        with self.assertRaisesRegex(ValueError, "^invalid_fhir_date$"):
            check_fhir_bundle(bundle)
        bundle = example()
        bundle["entry"][0]["fullUrl"] = "urn:uuid:not-valid"
        with self.assertRaisesRegex(ValueError, "^invalid_fhir_full_url$"):
            check_fhir_bundle(bundle)


if __name__ == "__main__":
    unittest.main()
