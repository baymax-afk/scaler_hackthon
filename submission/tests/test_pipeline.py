import base64
import csv
from datetime import date
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from rakshak.detection import SourceUnit, detect
from rakshak.formats import Rewrite, UnsafeInput, transform
from rakshak.release import publish_release


class DetectionTest(unittest.TestCase):
    def test_patient_identity_fields_stop_before_demographics_in_both_scripts(self):
        text = "मरीज़ का नाम: काव्या देव    आयु: 47 वर्ष   BP 120/80"
        rendered, _ = transform(text, ".txt", Rewrite())
        self.assertEqual(rendered, "मरीज़ का नाम: [NAME]    आयु: 47 वर्ष   BP 120/80")
        table, _ = transform("Naam\tDawai\nNivara Dev\t5 mg\n", ".tsv", Rewrite())
        self.assertEqual(table, "Naam\tDawai\n[NAME]\t5 mg\n")

    def test_subject_of_measured_vital_preserves_value_and_other_roles(self):
        source = ("Nivara Dev ka BP 120/80 mmHg. Review in 2 weeks.\n"
                  "Dr. Nivara Dev ka BP 120/80 mmHg.\n"
                  "Patient Education ka BP chart was discussed.\n"
                  "left arm ka BP 118/78 mmHg.")
        rendered, _ = transform(source, ".txt", Rewrite())
        self.assertEqual(rendered, source.replace("Nivara Dev", "[NAME]", 1))

    def test_name_boundary_keeps_separate_registration_id_private(self):
        note = "मरीज़ का नाम: Nivara Dev   आयु: 45/F   Reg No: HZ-792   Dose: 5 mg"
        actual, _ = transform(note, ".txt", Rewrite())
        self.assertEqual(actual, "मरीज़ का नाम: [NAME]   आयु: 45/F   Reg No: [MRN]   Dose: 5 mg")

    def test_honorific_and_measured_vital_support_an_abbreviated_patient_mention(self):
        source = "Nivara ji ki blood pressure: 125/80.\nDr sahab ka BP 128/84."
        rendered, _ = transform(source, ".txt", Rewrite())
        self.assertEqual(rendered, "[NAME] ji ki blood pressure: 125/80.\nDr sahab ka BP 128/84.")

    def test_generic_naam_under_medication_and_provider_keeps_its_source_role(self):
        obj = {"medication": {"naam": "Ferrous Sulfate"}, "provider": {"naam": "Nivara Dev"},
               "patient": {"naam": "Nivara Dev"}}
        rendered, _ = transform(json.dumps(obj), ".json", Rewrite())
        obj["patient"]["naam"] = "[NAME]"
        self.assertEqual(json.loads(rendered), obj)

    def test_positions_are_original(self):
        source = "🩺 ९१२३\u200b४५६७८९; 650 mg"
        finding, = detect(SourceUnit(source)).findings
        self.assertEqual(source[finding.start:finding.end], "९१२३\u200b४५६७८९")
        self.assertEqual(finding.kind, "PHONE")

    def test_nonbreaking_label_keeps_original_offsets(self):
        source = "🩺\nPatient Name: ईशा राव\nDose: 5 mg"
        finding, = detect(SourceUnit(source)).findings
        self.assertEqual((finding.start, finding.end, finding.kind),
                         (source.index("ईशा"), source.index("राव") + 3, "NAME"))

    def test_name_candidate_stops_before_dose(self):
        for suffix in (" dose 5 mg", " 500 mg daily", " dose: 5 mg", " 5 mg/kg"):
            source = "Name: Mira Sen" + suffix
            finding, = detect(SourceUnit(source)).findings
            self.assertEqual(source[finding.start:finding.end], "Mira Sen")

    def test_name_boundary_preserves_clinical_tails_in_text_and_cells(self):
        for tail in (" metformin 5 mg", " Medication: exampledrug 5 mg",
                     " follow-up in 7 days", " follow up in 2 weeks"):
            with self.subTest(tail=tail):
                value = "Mira Sen" + tail
                note, _ = transform("Patient Name: " + value, ".txt", Rewrite())
                self.assertEqual(note, "Patient Name: [NAME]" + tail)
                table, _ = transform(f"Patient Name,Dx\n{value},asthma\n", ".csv", Rewrite())
                self.assertEqual(table, f"Patient Name,Dx\n[NAME]{tail},asthma\n")

    def test_tabs_and_equivalent_colon_keep_original_name_offsets(self):
        source = "🩺\nPatient\tName： Mira Sen; Dose: 5 mg"
        finding, = detect(SourceUnit(source)).findings
        self.assertEqual((finding.start, finding.end), (source.index("Mira"), source.index(";")))

    def test_findings_report_only_roles_supported_by_the_source(self):
        cases = (("Patient Name: Mira Sen", "patient"),
                 ("S/o Mira Sen", "relative"),
                 ("Name: Mira Sen", None))
        for note, role in cases:
            with self.subTest(note=note):
                finding, = detect(SourceUnit(note)).findings
                self.assertEqual(finding.role, role)

    def test_name_roles_and_ambiguous_care_of(self):
        source = "Dr. Mira spoke. S/o Mira"
        finding, = detect(SourceUnit(source)).findings
        self.assertEqual(finding.start, source.rindex("Mira"))
        self.assertFalse(detect(SourceUnit("C/O fever")).findings)
        self.assertTrue(detect(SourceUnit("C/O uncertain")).review)

    def test_multilingual_roles_and_hidden_channels(self):
        source = ("मरीज़: काव्या सेन\nरिश्तेदार: मीरा सेन\nफ़ोन: ०००००-०००००\n"
                  "Jaya Sen ji aaye, W/o Mira Sen. Phone +91 00000-00000. C/O chakkar.")
        regions = {source[item.start:item.end]: item.kind for item in detect(SourceUnit(source)).findings}
        self.assertEqual(regions["काव्या सेन"], "NAME")
        self.assertEqual(regions["मीरा सेन"], "RELATIVE")
        self.assertEqual(regions["Jaya Sen"], "NAME")
        self.assertEqual(regions["Mira Sen"], "RELATIVE")
        self.assertEqual(regions["+91 00000-00000"], "PHONE")
        self.assertNotIn("chakkar", regions)
        self.assertTrue(detect(SourceUnit("NovaPerson10101010.txt", channel="filename")).findings)
        self.assertFalse(detect(SourceUnit("note_1234.txt", channel="filename")).findings)

    def test_clinical_patient_heading_is_not_a_name(self):
        source = "Patient - received aspirin 75 mg daily"
        self.assertEqual(transform(source, ".txt", Rewrite())[0], source)

    def test_filename_only_inpatient_id(self):
        self.assertTrue(detect(SourceUnit("nursing_ip-26-00151.txt", channel="filename")).findings)
        self.assertFalse(detect(SourceUnit("nursing_shift_26_00151.txt", channel="filename")).findings)
        self.assertFalse(detect(SourceUnit("IP-26-00151", channel="content")).findings)


class FormatTest(unittest.TestCase):
    def test_record_census_is_independent_of_identifier_detection(self):
        table_output, table_locators = transform("Patient Name,Dose\n,75 mg\n,80 mg\n", ".csv", Rewrite())
        self.assertEqual(table_locators, ["row:0", "row:1"])
        self.assertIn(",75 mg", table_output)
        self.assertEqual(transform("Drug,Dose\naspirin,75 mg\n", ".csv", Rewrite())[1], [])
        self.assertEqual(transform("BP 120/80", ".txt", Rewrite())[1], ["doc"])
        self.assertEqual(transform('{"patient_name":"Mira Sen","observation":"stable"}',
                                   ".json", Rewrite())[1], ["doc"])
        self.assertEqual(transform('{"visits":[{"status":"stable"}]}', ".json", Rewrite())[1],
                         ["/visits/0"])

    def test_json_record_locators_follow_patient_records(self):
        cases = [
            ('{"patient":{"name":"Mira Sen"},"panels":[{"result":"normal"}]}', ["doc"]),
            ('{"clinic/queue":[{"subject":{"display":"Mira Sen"}}]}', ["/clinic~1queue/0"]),
            ('{"round~two":[{"subject":{"display":"Mira Sen"}}]}', ["/round~0two/0"]),
            ('[{"patient_name":"Mira Sen"},{"patient_name":"Asha Rao"}]', ["/0", "/1"]),
            ('{"metadata":[{"source":"clinic"}]}', []),
            ('{"wards":[{"beds":12}]}', []),
            ('{"registrations":[{"name":"Mira Sen","phone":"9123456789"}]}',
             ["/registrations/0"]),
            ('{"registrations":[{"नाम":"मीरा सेन","फोन":"९१२३४५६७८९"}]}',
             ["/registrations/0"]),
        ]
        for source, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(transform(source, ".json", Rewrite())[1], expected)
    def test_keeps_reordered_name_initials_inside_the_identifier_span(self):
        note = "Patient: Velan, K. R.; dose 5 mg\nDr. Velan, K. R. verified."
        rendered, _ = transform(note, ".txt", Rewrite())
        self.assertEqual(rendered, "Patient: [NAME]; dose 5 mg\nDr. Velan, K. R. verified.")

    def test_uses_patient_role_and_chart_context_in_structured_fields(self):
        data = {
            "referral": {"subject": {"display": "நிலா வேலன்", "email": "patient@example.invalid",
                                     "medicalRecordReference": "WEST-39A-0021"}},
            "assessment": {"subject": {"display": "Diabetes Mellitus"}},
            "attending": {"subject": {"display": "நிலா வேலன்", "email": "provider@example.invalid"}},
            "diagnosis": {"code": "E11.9"}, "specimen": {"number": "WEST-39A-0021"},
        }
        rendered, _ = transform(json.dumps(data), ".json", Rewrite())
        result = json.loads(rendered)
        self.assertEqual(result["referral"]["subject"],
                         {"display": "[NAME]", "email": "[EMAIL]", "medicalRecordReference": "[MRN]"})
        self.assertEqual(result["attending"]["subject"]["display"], "நிலா வேலன்")
        for key in ("assessment", "diagnosis", "specimen"):
            self.assertEqual(result[key], data[key])

    def test_recognizes_explicit_referral_role_in_tables(self):
        rendered, _ = transform(
            'Referred Subject,Clinical subject,Sample reference\n"Patel, J.",Pulse Pressure,WD-072B\n',
            ".csv", Rewrite(),
        )
        self.assertEqual(rendered,
                         "Referred Subject,Clinical subject,Sample reference\n[NAME],Pulse Pressure,WD-072B\n")

    def test_uses_chart_number_cue_without_treating_all_codes_as_mrns(self):
        note = "Chart # NOR-872B/04\nSpecimen # NOR-872B/04\nDiagnosis: E11.9"
        rendered, _ = transform(note, ".txt", Rewrite())
        self.assertEqual(rendered, "Chart # [MRN]\nSpecimen # NOR-872B/04\nDiagnosis: E11.9")

    def test_localized_name_cues_and_relationship_lines_preserve_their_neighbors(self):
        note = ("Mareez ka naam / Nivara Dast\n"
                "ರೋಗಿಯ ಹೆಸರು: ಕಾವ್ಯ ಸೇನ್\n"
                "நோயாளியின் பெயர்: நிலா வேலன்\n"
                "W/o நிலா வேலன் 5 mg\n"
                "S/o Ahira M. D. Velam\n"
                "BP: 120/80 mmHg")
        rendered, _ = transform(note, ".txt", Rewrite())
        self.assertEqual(rendered, "Mareez ka naam / [NAME]\nರೋಗಿಯ ಹೆಸರು: [NAME]\n"
                         "நோயாளியின் பெயர்: [NAME]\nW/o [RELATIVE] 5 mg\n"
                         "S/o [RELATIVE]\nBP: 120/80 mmHg")

    def test_delimiter_and_original_label_roles(self):
        output, locations = transform('नाम\tDose\n"ईशा राव"\t650 mg\n', ".tsv", Rewrite())
        self.assertEqual(list(csv.reader(io.StringIO(output), delimiter="\t")),
                         [["नाम", "Dose"], ["[NAME]", "650 mg"]])
        self.assertEqual(locations, ["row:0"])

    def test_transliterated_birth_date_field(self):
        output, _ = transform("Janm Tithi\tBP\tDose\n1991-02-03\t120/80\t650 mg\n",
                              ".tsv", Rewrite())
        self.assertEqual(list(csv.reader(io.StringIO(output), delimiter="\t")),
                         [["Janm Tithi", "BP", "Dose"], ["[DOB]", "120/80", "650 mg"]])

    def test_patient_export_aliases_preserve_clinical_values(self):
        output, _ = transform("Naam\tGaon\tPata\tDose\nMira Sen\tRampur\tMain Road\t650 mg\n",
                              ".tsv", Rewrite())
        self.assertEqual(list(csv.reader(io.StringIO(output), delimiter="\t"))[1],
                         ["[NAME]", "[ADDRESS]", "[ADDRESS]", "650 mg"])
        output, _ = transform('{"patient_ref":"MRN123456","hospital_uhid":"UHID123456",'
                              '"pmjay_id":"PMJAY123456","dose":"650 mg"}', ".json", Rewrite())
        released = json.loads(output)
        self.assertEqual([released[key] for key in ("patient_ref", "hospital_uhid", "pmjay_id")],
                         ["[MRN]", "[MRN]", "[INSURANCE_ID]"])
        self.assertEqual(released["dose"], "650 mg")

    def test_json_types_precision_and_duplicate_key(self):
        output, _ = transform('{"mobile":9123456789,"measurement":2.00,"flag":true}', ".json", Rewrite())
        self.assertEqual(json.loads(output), {"mobile": 0, "measurement": 2.0, "flag": True})
        self.assertIn('"measurement":2.00', output)
        with self.assertRaisesRegex(UnsafeInput, "duplicate_json_key"):
            transform('{"key":"x","key":"y"}', ".json", Rewrite())

    def test_fhir_references_narrative_and_attachment(self):
        anchor = "urn:uuid:91234567-1234-1234-1234-912345678912"
        attachment = base64.b64encode(b"Phone: 9123456789").decode("ascii")
        bundle = {
            "resourceType": "Bundle", "type": "collection", "entry": [
                {"fullUrl": anchor, "resource": {"resourceType": "Patient", "name": [
                    {"given": ["Mira"], "family": "Sen"}], "text": {"status": "generated",
                    "div": '<div xmlns="http://www.w3.org/1999/xhtml">Mira Sen, 27 yrs</div>'}}},
                {"resource": {"resourceType": "Observation", "subject": {"reference": anchor},
                              "valueQuantity": {"value": 9123456789, "unit": "mg/dL"}}},
                {"resource": {"resourceType": "DocumentReference",
                              "content": [{"attachment": {"contentType": "text/plain", "data": attachment}}]}},
            ],
        }
        result, locators = transform(json.dumps(bundle), ".json", Rewrite())
        self.assertNotIn("Mira", result)
        self.assertEqual(locators, ["doc"])
        entries = json.loads(result)["entry"]
        self.assertEqual(entries[0]["fullUrl"], entries[1]["resource"]["subject"]["reference"])
        self.assertEqual(entries[1]["resource"]["valueQuantity"]["value"], 9123456789)
        value = entries[2]["resource"]["content"][0]["attachment"]["data"]
        self.assertNotIn(b"9123456789", base64.b64decode(value))
        bundle["entry"][0].pop("fullUrl")
        with self.assertRaisesRegex(UnsafeInput, "unresolved_fhir_reference"):
            transform(json.dumps(bundle), ".json", Rewrite())

    def test_fhir_name_roles_use_source_paths_for_identical_surfaces(self):
        patient_url = "urn:uuid:17ba0c07-910b-4395-a3d1-dd81ad44670b"
        entries = [
            {"fullUrl": patient_url,
             "resource": {"resourceType": "Patient", "name": [{"text": "Mira Sen"}],
                          "contact": [{"name": {"text": "Mira Sen"}}]}},
            {"fullUrl": "urn:uuid:17ba0c07-910b-4395-a3d1-dd81ad44670c",
             "resource": {"resourceType": "RelatedPerson", "name": [{"text": "Mira Sen"}],
                          "patient": {"reference": patient_url}}},
            {"fullUrl": "urn:uuid:17ba0c07-910b-4395-a3d1-dd81ad44670d",
             "resource": {"resourceType": "Practitioner", "name": [{"text": "Mira Sen"}]}},
        ]
        rendered, _ = transform(json.dumps({"resourceType": "Bundle", "type": "collection",
                                            "entry": entries}), ".json", Rewrite())
        patient, relative, clinician = (entry["resource"] for entry in json.loads(rendered)["entry"])
        self.assertEqual(patient["name"][0]["text"], "[NAME]")
        self.assertEqual(patient["contact"][0]["name"]["text"], "[NAME]")
        self.assertEqual(relative["name"][0]["text"], "[RELATIVE]")
        self.assertEqual(clinician["name"][0]["text"], "Mira Sen")

    def test_fhir_narrative_corroborates_names_across_xhtml_nodes(self):
        div = ('<div xmlns="http://www.w3.org/1999/xhtml"><p><b>நிலா</b> <em>வேலன்</em></p>'
               '<p>Dr. நிலா வேலன் documented 5 mg.</p></div>')
        bundle = {"resourceType": "Bundle", "type": "collection", "entry": [
            {"resource": {"resourceType": "Patient", "name": [{"given": ["நிலா"], "family": "வேலன்"}],
                          "text": {"status": "generated", "div": div}}}
        ]}
        rendered, _ = transform(json.dumps(bundle), ".json", Rewrite())
        patient = json.loads(rendered)["entry"][0]["resource"]
        content = patient["text"]["div"]
        self.assertEqual(patient["name"], [{"given": ["[NAME]"], "family": "[NAME]"}])
        self.assertNotIn("<b>நிலா</b>", content)
        self.assertNotIn("<em>வேலன்</em>", content)
        self.assertIn("[NAME]", content)
        self.assertIn("Dr. நிலா வேலன் documented 5 mg.", content)

    def test_fhir_birth_date_never_becomes_an_invalid_placeholder(self):
        bundle = {"resourceType": "Bundle", "type": "document", "entry": [
            {"fullUrl": "urn:uuid:22222222-2222-4222-8222-222222222222",
             "resource": {"resourceType": "Patient", "id": "22222222-2222-4222-8222-222222222222",
                          "birthDate": "1991-02-03"}}]}
        try:
            output, _ = transform(json.dumps(bundle), ".json", Rewrite())
        except UnsafeInput as exc:
            self.assertEqual(exc.args[0], "unsupported_fhir_date_transform")
        else:
            released = json.loads(output)["entry"][0]["resource"]["birthDate"]
            date.fromisoformat(released)
            self.assertNotEqual(released, "[DOB]")


class ReleaseTest(unittest.TestCase):
    def test_safe_paths_stay_put_and_identifying_filenames_are_keyed(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            (source / "ward").mkdir(parents=True)
            (source / "ward" / "observations.txt").write_text("BP: 120/80")
            (source / "ward" / "9123456789.txt").write_text("BP: 120/80")
            first, second = root / "first", root / "second"
            publish_release(source, first, b"key-a")
            publish_release(source, second, b"key-b")
            self.assertTrue((first / "sanitized" / "ward" / "observations.txt").exists())
            self.assertTrue((second / "sanitized" / "ward" / "observations.txt").exists())
            paths = [next((out / "sanitized" / "ward").glob("file_*.txt"))
                     .relative_to(out / "sanitized")
                     for out in (first, second)]
            self.assertNotEqual(paths[0], paths[1])
            self.assertEqual(paths[0].parent, Path("ward"))
            self.assertEqual((first / "sanitized" / paths[0]).read_text(), "BP: 120/80")

    def test_identifying_directory_is_quarantined(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            (source / "9123456789").mkdir(parents=True)
            (source / "9123456789" / "observations.txt").write_text("BP: 120/80")
            output = root / "output"
            publish_release(source, output, b"key-a")
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["counts"]["files_quarantined"], 1)
            self.assertEqual(report["files"][0]["reason"], "unsafe_directory_name")
            self.assertFalse(list((output / "sanitized").rglob("*.txt")))
    def test_cli_preserves_clinical_neighbors_of_unicode_name_label(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "input"
            incoming.mkdir()
            (incoming / "note.txt").write_text(
                "Patient Name: Mira Sen dose 0,5 mg\n"
                "Patient Name: Mira Sen (dose 5 mg)\nDr. Mira Sen reviewed."
            )
            outgoing = root / "output"
            cli = Path(__file__).resolve().parents[1] / "main.py"
            subprocess.run([sys.executable, "-B", str(cli), "--input", str(incoming),
                            "--output", str(outgoing)], check=True, capture_output=True,
                           env={**os.environ, "RAKSHA_SECRET": "boundary-fixture"})
            self.assertEqual((outgoing / "sanitized/note.txt").read_text(),
                             "Patient Name: [NAME] dose 0,5 mg\n"
                             "Patient Name: [NAME] (dose 5 mg)\nDr. Mira Sen reviewed.")

    def test_masked_phone_cannot_escape_in_content_or_release_paths(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "input"
            incoming.mkdir()
            masked = "98XXXXXX10"
            (incoming / (masked + ".txt")).write_text(
                "Callback requested at " + masked + ". Dose 10 mg. Lot AB98XXXXXX10Z.")
            output = root / "release"
            publish_release(incoming, output, b"fixture")
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["counts"]["files_sanitized"], 1)
            path = report["files"][0]["output"]
            self.assertNotIn(masked, path)
            self.assertEqual((output / path).read_text(),
                             "Callback requested at [PHONE]. Dose 10 mg. Lot AB98XXXXXX10Z.")
            self.assertNotIn(masked, (output / "records.jsonl").read_text())

    def test_uninspected_attachment_link_is_withheld_from_entire_release(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            source.mkdir()
            marker = "synthetic-download-token"
            attachment = {"url": "https://files.example.invalid/" + marker,
                          "contentType": "application/pdf"}
            bundle = {"resourceType": "Bundle", "type": "collection", "entry": [
                {"resource": {"resourceType": "DocumentReference",
                              "content": [{"attachment": attachment}]}}]}
            (source / "ref.json").write_text(json.dumps(bundle))
            (source / "safe.txt").write_text("Dose 5 mg.")
            out = root / "release"
            counts = publish_release(source, out, b"fixture")
            self.assertEqual((counts["files_sanitized"], counts["files_quarantined"]), (1, 1))
            self.assertFalse((out / "sanitized/ref.json").exists())
            self.assertEqual((out / "sanitized/safe.txt").read_text(), "Dose 5 mg.")
            for artifact in (out / "report.json", out / "records.jsonl"):
                self.assertNotIn(marker, artifact.read_text())

    def test_repeatable_and_quarantine_does_not_publish_raw(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "input"
            source.mkdir()
            sample = b"Name: Mira Sen"
            (source / "9123456789.txt").write_bytes(sample)
            (source / "duplicate.txt").write_bytes(sample)
            (source / "unreadable.pdf").write_bytes(b"raw synthetic marker")
            (source / "review.txt").write_text("C/O uncertain")
            out, repeat, rotated = (directory / label for label in ("a", "b", "c"))
            for path, key in ((out, b"key-a"), (repeat, b"key-a"), (rotated, b"key-b")):
                publish_release(source, path, key)
            def artifacts(path):
                return {file.relative_to(path): file.read_bytes() for file in path.rglob("*")
                        if file.is_file() and file.name != "report.json"}
            self.assertEqual(artifacts(out), artifacts(repeat))
            self.assertNotEqual(artifacts(out), artifacts(rotated))
            self.assertNotIn(b"Mira", b"".join(artifacts(out).values()))
            report = json.loads((out / "report.json").read_text())
            self.assertEqual(report["counts"]["files_sanitized"], 2)
            self.assertEqual(report["counts"]["files_quarantined"], 2)
            self.assertEqual(report["files"][0]["input_sha256"], report["files"][1]["input_sha256"])
            self.assertEqual((source / "9123456789.txt").read_bytes(), sample)


if __name__ == "__main__":
    unittest.main()
