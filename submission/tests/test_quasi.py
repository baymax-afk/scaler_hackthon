"""Source-only component tests for structured quasi-identifier generalization."""

import unittest
from datetime import datetime

from rakshak.quasi import (generalize_json_record, generalize_row,
                             patient_day_shift, shift_patient_date)


class StructuredQuasiTests(unittest.TestCase):
    def test_truthful_age_bands(self):
        for age in (0, 1, 4, 5, 44, 45, 47, 49, 50, 99, 100, 125):
            with self.subTest(age=age):
                result = generalize_row(["Patient ID", "Age"], ["MRN-1234", str(age)])
                lower, upper = map(int, result[1].split("-"))
                self.assertLessEqual(lower, age)
                self.assertLessEqual(age, upper)
                self.assertEqual(upper - lower, 4)

    def test_unicode_digits_and_localized_headers(self):
        self.assertEqual(
            generalize_row(
                ["रोगी का नाम", "आयु", "पिन कोड", "गाँव", "ज़िला"],
                ["Synthetic Patient", "४७", "५६०१००", "काल्पनिक गाँव", "नमूना ज़िला"],
            ),
            {1: "45-49", 2: "560***", 3: "नमूना ज़िला"},
        )
        self.assertEqual(generalize_row(["UHID", "postalCode"], ["MRN-1234", "５６０１００"]), {1: "560***"})

    def test_practice_role_layout_without_memorizing_values(self):
        header = ["Reg No", "Naam", "Ling", "Umar", "Gaon", "Jila", "Pin Code", "Mobile No", "Aadhar"]
        row = ["REG-42", "Synthetic Patient", "F", "59", "Synthetic Village",
               "Sample District", "560100", "9000000000", "000000000000"]
        self.assertEqual(generalize_row(header, row), {3: "55-59", 4: "Sample District", 6: "560***"})
        self.assertEqual(
            generalize_row(["PatientID", "AgeYears", "Village/Mohalla", "District", "Zip"],
                           ["MRN-42", "42", "Synthetic Village", "Sample District", "560100"]),
            {1: "40-44", 2: "Sample District", 4: "560***"},
        )

    def test_district_requires_explicit_trustworthy_field(self):
        self.assertEqual(generalize_row(["UHID", "Village"], ["MRN-1234", "Synthetic Village"]), {})
        for district in ("", "unknown", "-", "123", "Sample\nDistrict", "District, Address", "[ADDRESS]",
                         "9988776655", "Synthetic Patient"):
            with self.subTest(district=district):
                self.assertEqual(
                    generalize_row(["Patient Name", "Village", "District"],
                                   ["Synthetic Patient", "Synthetic Village", district]),
                    {},
                )
        self.assertEqual(
            generalize_row(["UHID", "Village", "District", "Jila"],
                           ["MRN-1234", "Synthetic Village", "Sample District", "Other District"]),
            {},
        )

    def test_reference_and_staff_tables_are_unchanged(self):
        for header, row in (
            (["Age", "Dose"], ["47", "50 mg"]),
            (["Name", "Age", "PIN"], ["Synthetic Person", "47", "560100"]),
            (["Specimen ID", "Age", "PIN"], ["LAB-100", "47", "560100"]),
            (["Doctor ID", "Age", "PIN"], ["DOC-100", "47", "560100"]),
            (["Name", "Employee ID", "Reg No", "Aadhar", "Mobile", "Age"],
             ["Synthetic Person", "EMP-1", "REG-1", "000000000000", "9000000000", "47"]),
        ):
            with self.subTest(header=header):
                self.assertEqual(generalize_row(header, row), {})

    def test_clinical_controls_even_in_patient_table(self):
        header = ["MRN", "Age (days)", "Age (months)", "Dosage", "Years on treatment", "Lab code",
                  "Length of stay", "BP", "Patient age (years)", "Physician age", "Age of specimen",
                  "Medications", "Postal code of laboratory", "Phone"]
        row = ["MRN-1234", "47", "47", "47", "47", "560100", "47", "150/90", "47", "47", "47",
               "Metformin 500 mg", "560100", "9000000000"]
        self.assertEqual(generalize_row(header, row), {8: "45-49"})

    def test_only_valid_exact_ages_are_changed(self):
        for value in ("-1", "126", "47mg", "47.5", "4-7", "N/A", "", "1e2", "²", "00 9", "999999"):
            with self.subTest(value=value):
                self.assertEqual(generalize_row(["MRN", "Age"], ["MRN-42", value]), {})

    def test_only_valid_exact_pins_are_changed(self):
        for value in ("56010", "5601000", "+560100", "560***", "560 100", "unknown", "012345"):
            with self.subTest(value=value):
                self.assertEqual(generalize_row(["MRN", "PIN"], ["MRN-42", value]), {})

    def test_idempotent_and_input_unchanged(self):
        header = ["MRN", "Age", "PIN", "Village", "District"]
        row = ["MRN-42", "47", "560100", "Synthetic Village", "Sample District"]
        original_header, original_row = header[:], row[:]
        updated = [generalize_row(header, row).get(i, v) for i, v in enumerate(row)]
        self.assertEqual(generalize_row(header, updated), {})
        self.assertEqual(header, original_header)
        self.assertEqual(row, original_row)

    def test_unsupported_inputs_are_unchanged(self):
        self.assertEqual(generalize_row(["MRN", "Age"], ["MRN-42"]), {})
        self.assertEqual(generalize_row(["MRN", "Age"], ["MRN-42", 47]), {})
        self.assertEqual(generalize_row(["MRN", "Age"], ["MRN-42", True]), {})
        self.assertEqual(generalize_row(["MRN", "Age"], ["", "47"]), {})


    def test_combined_age_sex_and_year_units(self):
        for label, value, expected in (
            ("AgeSex", "52/M", "50-54/M"), ("Age/Gender", "52 Y / F", "50-54 Y / F"),
            ("Age", "52 y", "50-54 y"), ("Age", "52yrs", "50-54yrs"),
            ("Age", "52y", "50-54y"), ("आयु", "५२ वर्ष", "50-54 वर्ष"),
            ("उम्र", "५२ साल/महिला", "50-54 साल/महिला"),
        ):
            with self.subTest(label=label, value=value):
                self.assertEqual(generalize_row(["MRN", label], ["MRN-42", value]), {1: expected})
                self.assertEqual(generalize_row(["MRN", label], ["MRN-42", expected]), {})
        for v in ("52 days", "52 months", "52/MIN", "52/100", "52 mg", "52/M/F", "52 y dose"):
            self.assertEqual(generalize_row(["MRN", "Age"], ["MRN-42", v]), {})

    def test_json_explicit_nested_patient_string_fields(self):
        record = {
            "patient": {
                "name": "Synthetic Patient", "ageSex": "52/M",
                "address": {"village": "Synthetic Village", "district": "Sample District", "PIN": "560100"},
                "demographics": {"age": "52 yrs"},
                "other": {"age": "52"},
            },
            "specimen": {"age": "52", "pin": "560100"},
            "doctor": {"age": "52", "PIN": "560100"},
        }
        self.assertEqual(generalize_json_record(record), {
            ("patient", "ageSex"): "50-54/M",
            ("patient", "address", "village"): "Sample District",
            ("patient", "address", "PIN"): "560***",
            ("patient", "demographics", "age"): "50-54 yrs",
        })

    def test_json_explicit_patient_root_and_typed_values(self):
        record = {"patientId": 17, "age": 52, "PIN": 560100, "patient age": "52Y",
                  "village": "Synthetic Village", "district": "Sample District",
                  "dose": "50 mg", "length of stay": 7, "date": "2026-10-01", "age (days)": "52"}
        self.assertEqual(generalize_json_record(record), {
            ("patient age",): "50-54Y", ("village",): "Sample District"
        })
        self.assertEqual(record["age"], 52)
        self.assertEqual(record["PIN"], 560100)

    def test_json_ambiguous_and_non_patient_paths_are_unchanged(self):
        for record in (
            {"age": "52", "PIN": "560100", "name": "Synthetic Person"},
            {"resourceType": "Patient", "id": "identifier", "age": "52", "PIN": "560100"},
            {"patients": [{"patientID": "MRN-1", "age": "52"}]},
            {"patient": {"age": "52"}, "beneficiary": {"age": "52"}},
            {"MRN": "MRN-42", "village": "Synthetic Village", "district": "Sample District",
             "address": {"district": "Other District"}},
            {"patient": {"age": "52", "resourceType": "Patient"}},
        ):
            with self.subTest(record=record):
                self.assertEqual(generalize_json_record(record), {})

    def test_json_address_list_relative_paths(self):
        record = {"MRN": "MRN-42", "addresses": [
            {"village": "Synthetic Village", "district": "Sample District", "pin": "560100"}
        ]}
        self.assertEqual(generalize_json_record(record), {
            ("addresses", 0, "village"): "Sample District",
            ("addresses", 0, "pin"): "560***",
        })


    def test_patient_date_shift_preserves_intervals_and_is_keyed(self):
        offset = patient_day_shift("practice-test", "PSN-SYNTHETIC")
        self.assertTrue(0 < abs(offset) <= 365)
        self.assertEqual(offset, patient_day_shift(b"practice-test", b"PSN-SYNTHETIC"))
        self.assertNotEqual(offset, patient_day_shift("another-test", "PSN-SYNTHETIC"))
        distinct = {patient_day_shift("practice-test", f"PSN-SYNTHETIC-{i}") for i in range(10)}
        self.assertGreater(len(distinct), 1)
        for fmt, dates in (
            ("%Y-%m-%d", ("2024-02-27", "2024-03-01")),
            ("%d/%m/%Y", ("27/02/2024", "01/03/2024")),
        ):
            shifted = [shift_patient_date(value, offset, date_format=fmt) for value in dates]
            original_gap = datetime.strptime(dates[1], fmt) - datetime.strptime(dates[0], fmt)
            shifted_gap = datetime.strptime(shifted[1], fmt) - datetime.strptime(shifted[0], fmt)
            self.assertEqual(original_gap, shifted_gap)

    def test_date_shift_abstains_without_exact_format_or_key(self):
        for date, fmt in (
            ("2024-02-30", "%Y-%m-%d"), ("2024-02", "%Y-%m"), ("2024-2-1", "%Y-%m-%d"),
            ("01/02/2024", "%Y-%m-%d"), ("2024-01-01T12:00:00Z", "%Y-%m-%d"),
        ):
            self.assertIsNone(shift_patient_date(date, 21, date_format=fmt))
        self.assertIsNone(shift_patient_date("2024-01-01", 366, date_format="%Y-%m-%d"))
        self.assertIsNone(shift_patient_date("2024-01-01", True, date_format="%Y-%m-%d"))
        with self.assertRaises(ValueError):
            patient_day_shift("", "PSN-SYNTHETIC")
        with self.assertRaises(ValueError):
            patient_day_shift("practice-test", "")


if __name__ == "__main__":
    unittest.main()
