"""Source-only component tests for structured quasi-identifier generalization."""

import unittest

from rakshak.quasi import generalize_row


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
        for value in ("-1", "126", "47y", "47.5", "4-7", "N/A", "", "1e2", "²", "00 9", "999999"):
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


if __name__ == "__main__":
    unittest.main()
