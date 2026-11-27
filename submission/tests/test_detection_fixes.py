"""Regression and negative controls for role-aware narrative privacy."""
import unittest

from rakshak.detection import SourceUnit, detect


def rewrite(text, **context):
    result = detect(SourceUnit(text, **context))
    if result.error or result.review:
        raise AssertionError("detector returned an unresolved finding")
    parts = []
    cursor = 0
    for finding in result.findings:
        parts.extend((text[cursor:finding.start], "[" + finding.kind + "]"))
        cursor = finding.end
    return "".join((*parts, text[cursor:]))


class NarrativeDetectionRegression(unittest.TestCase):
    def test_timestamped_patient_vitals_and_case_history(self):
        source = ("2026-11-02 22:00 - Nivara didi ka BP 170/92, pulse 64.\n"
                  "14:00 - Nivara Dev - K/C/O asthma. Attendant (S/o Kavi Dev) informed.\n"
                  "Dr. Nivara Dev ka BP 128/80.\nLeft Arm ka BP 118/76.")
        self.assertEqual(rewrite(source), (
            "2026-11-02 22:00 - [NAME] didi ka BP 170/92, pulse 64.\n"
            "14:00 - [NAME] - K/C/O asthma. Attendant (S/o [RELATIVE]) informed.\n"
            "Dr. Nivara Dev ka BP 128/80.\nLeft Arm ka BP 118/76."))

    def test_sample_attendant_and_report_subject(self):
        self.assertEqual(rewrite("Report of Nivara Dev 48 Y / F\nHaemoglobin 14.0 g/dL"),
                         "Report of [NAME] 48 Y / F\nHaemoglobin 14.0 g/dL")
        self.assertEqual(rewrite("Sample received from Nivara's attendant (W/o Kavi Dev)."),
                         "Sample received from [NAME]'s attendant (W/o [RELATIVE]).")
        self.assertEqual(rewrite("Report of Blood Glucose 15 mg/dL"), "Report of Blood Glucose 15 mg/dL")

    def test_hindi_repeated_explicit_patient_and_unrelated_symptom(self):
        text = ("नाम: काव्या देव   आयु: 47 वर्ष\n"
                "काव्या देव को 2 दिन से बुखार है।\n"
                "दाहिने पैर को 5 दिन से दर्द है।")
        self.assertEqual(rewrite(text),
                         "नाम: [NAME]   आयु: 47 वर्ष\n[NAME] को 2 दिन से बुखार है।\n"
                         "दाहिने पैर को 5 दिन से दर्द है।")

    def test_discharge_person_separated_from_diagnosis(self):
        self.assertEqual(rewrite("Nivara Dev, W/o Kavi Dev, discharged in stable condition."),
                         "[NAME], W/o [RELATIVE], discharged in stable condition.")
        self.assertEqual(rewrite("Treated conservatively. Nivara Dev ki condition ab stable hai."),
                         "Treated conservatively. [NAME] ki condition ab stable hai.")

    def test_lowercase_transliterated_surname(self):
        self.assertEqual(rewrite("Nivara dev amma ka BP 120/80"),
                         "[NAME] amma ka BP 120/80")
        self.assertEqual(rewrite("Report of Nivara dev 48 Y / F"),
                         "Report of [NAME] 48 Y / F")
        self.assertEqual(rewrite("Treated conservatively. Nivara dev ki condition ab stable hai."),
                         "Treated conservatively. [NAME] ki condition ab stable hai.")
        self.assertEqual(rewrite('{"patient":"Nivara Dev", "dose":"5 mg"}'),
                         '{"patient":"[NAME]", "dose":"5 mg"}')
        self.assertEqual(rewrite("Report of Nivara ji 48 Y / F"), "Report of [NAME] ji 48 Y / F")
        self.assertEqual(rewrite("Treated conservatively. Nivara behenji ki condition ab stable hai."),
                         "Treated conservatively. [NAME] behenji ki condition ab stable hai.")

    def test_mrn_header_name_and_measurement_controls(self):
        self.assertEqual(rewrite("UHID-123456 Nivara", channel="header"), "[MRN] [NAME]")
        self.assertEqual(rewrite("UHID-123456 BP", channel="header"), "[MRN] BP")
        self.assertEqual(rewrite("UHID-123456 Glucose", channel="header"), "[MRN] Glucose")
        self.assertEqual(rewrite("UHID-123456 Nivara"), "[MRN] Nivara")

    def test_semantic_role_alias_with_unicode_name_and_negative_controls(self):
        for label in ("Sample recipient", "Transfer for", "Ward chart", "OnBehalfOf", "Caller"):
            with self.subTest(label=label):
                self.assertEqual(rewrite("ನಿವರಾ ದೇವ್", label=label), "[NAME]")
                self.assertEqual(rewrite("Nivara, K. R.", label=label), "[NAME]")
                self.assertEqual(rewrite("Blood Pressure", label=label), "Blood Pressure")
                self.assertEqual(rewrite("14 mg", label=label), "14 mg")
        self.assertEqual(rewrite("Nivara Dev", label="Clinician"), "Nivara Dev")
        self.assertEqual(rewrite("Nivara Dev", label="Specimen"), "Nivara Dev")

    def test_scoped_opaque_administrative_aliases(self):
        for label in ("ChartAnchor", "Claim member", "Local file", "Handover label", "Settlement", "AccessionOwner"):
            with self.subTest(label=label):
                self.assertEqual(rewrite("WEST-7W209X", label=label), "[MRN]")
                self.assertEqual(rewrite("E11.9", label=label), "E11.9")
                self.assertEqual(rewrite("650 mg", label=label), "650 mg")
        self.assertEqual(rewrite("WEST-7W209X", label="Benefit code"), "WEST-7W209X")
        self.assertEqual(rewrite("WEST-7W209X", label="Specimen"), "WEST-7W209X")
        self.assertEqual(rewrite("Chart: SNJ/26/123456; follow-up 26/11/2026; E11.9"),
                         "Chart: [MRN]; follow-up 26/11/2026; E11.9")

    def test_explicit_dialogue_roles_not_clinician(self):
        source = ("Family: I am काव्या देव. I came with நிலா வேலன்.\n"
                  "Clinician: I am काव्या देव. I came with நிலா வேலன்.\n"
                  "Dr. काव्या देव confirmed 120/80.")
        expected = ("Family: I am [RELATIVE]. I came with [NAME].\n"
                    "Clinician: I am काव्या देव. I came with நிலா வேலன்.\n"
                    "Dr. काव्या देव confirmed 120/80.")
        self.assertEqual(rewrite(source), expected)

    def test_review_subject_requires_role_and_contact_context(self):
        source = "Prescription review\nSubject = Nivara, R.\nContinue 14 mg\nReply-to person@example.invalid"
        self.assertEqual(rewrite(source),
                         "Prescription review\nSubject = [NAME]\nContinue 14 mg\nReply-to [EMAIL]")
        self.assertEqual(rewrite("Subject = Blood Pressure\nReview 14 mg"), "Subject = Blood Pressure\nReview 14 mg")
        self.assertEqual(rewrite("Subject = Nivara Dev"), "Subject = Nivara Dev")

    def test_localized_relative_and_registration_clues(self):
        text = "पति का नाम: रवि देव\nपंजीकरण सं.: RK/26/00012    आईपीडी सं.: IP/26/00012"
        self.assertEqual(rewrite(text),
                         "पति का नाम: [RELATIVE]\nपंजीकरण सं.: [MRN]    आईपीडी सं.: [MRN]")
        self.assertEqual(rewrite("NURSING NOTES - Ward 4, Bed 5 - IP/26/00012\nDose 5 mg"),
                         "NURSING NOTES - Ward 4, Bed 5 - [MRN]\nDose 5 mg")

    def test_postal_address_preserves_district_and_clinical_neighbours(self):
        source = ("Address: Sunset Road, Ward 4, Mohalla Market, Durga Nagar, "
                  "Tehsil Velam, Distt. Neela - 123456\nBP 120/80\n"
                  "District hospital, Dose 12 mg")
        self.assertEqual(rewrite(source), (
            "Address: [ADDRESS], [ADDRESS], [ADDRESS], [ADDRESS], "
            "Tehsil Velam, Distt. Neela - [PIN]\nBP 120/80\n"
            "District hospital, Dose 12 mg"))
        self.assertEqual(rewrite("Address: Sunset Road, District Neela, dose 5 mg"),
                         "Address: [ADDRESS], District Neela, dose 5 mg")
        self.assertEqual(rewrite("Address (attendant): C/O Kavi Dev, Market Road\nOPD: C/O fever"),
                         "Address (attendant): C/O [RELATIVE], [ADDRESS]\nOPD: C/O fever")

    def test_attachment_chat_sender_but_not_general_clinician_chat(self):
        text = ("[23/06/26, 8:11 pm] Nivara Dev: <attachment: report.pdf>\n"
                "Forwarded\nReport of Kavi Dev 48 Y / F\n"
                "[23/06/26, 8:11 pm] Doctor Nivara: BP 120/80")
        self.assertEqual(rewrite(text), (
            "[23/06/26, 8:11 pm] [RELATIVE]: <attachment: report.pdf>\n"
            "Forwarded\nReport of [NAME] 48 Y / F\n"
            "[23/06/26, 8:11 pm] Doctor Nivara: BP 120/80"))


if __name__ == "__main__":
    unittest.main()
