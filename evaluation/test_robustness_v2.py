from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import robustness_v2 as benchmark
from generate import dump, generate, SEED


class OpenCorpusTest(unittest.TestCase):
    def test_reproducible_counts_and_split_collision(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first", root / "second"
            generate(first, SEED)
            generate(second, SEED)
            result = benchmark.validate(first)["open_splits"]
            self.assertEqual(result["development"]["records"], 1000)
            self.assertEqual(result["validation"]["records"], 400)
            self.assertEqual(result, benchmark.validate(second)["open_splits"])
            validation = second / "validation"
            development = benchmark.read_json(second / "development" / "truth.json")
            manifest, records = benchmark.load_split(validation)
            records[0]["patient_group"] = development[0]["patient_group"]
            dump(validation / "truth.json", records)
            manifest["truth_sha256"] = benchmark.digest(validation / "truth.json")
            dump(validation / "manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "split_collision"):
                benchmark.validate(second)

    def test_source_inventory_is_independent_of_truth_and_includes_background(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "input"
            source.mkdir()
            (source / "one.csv").write_text("Clerk Code,Dose\nnot a patient,5 mg\n")
            before = list(benchmark.source_units(folder))
            dump(folder / "truth.json", [{"file": "one.csv", "units": [{"label": "patient name"}]}])
            self.assertEqual(list(benchmark.source_units(folder)), before)
            self.assertTrue(any(unit["text"] == "5 mg" and unit["label"] == "Dose" for unit in before))
            self.assertTrue(any(unit["text"] == "Clerk Code" and unit["channel"] == "header" for unit in before))

    def test_invalid_file_stays_in_inventory_without_stopping_other_inputs(self):
        from evaluate import predict

        with TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "input"
            source.mkdir()
            (source / "broken.json").write_text("{")
            (source / "unsupported.pdf").write_bytes(b"fixture")
            (source / "valid.txt").write_text("Patient: Mira Sen")
            units = list(benchmark.source_units(folder))
            results = predict(json.dumps(units).encode())["units"]
            failures = {results[unit["id"]]["status"] for unit in units if unit["channel"] == "file"}
            self.assertEqual(failures, {"invalid_input", "unsupported_format"})
            self.assertTrue(any(result["accepted"] == [(9, 17, "NAME")] for result in results.values()))

    def test_release_audit_localizes_identical_surfaces_by_occurrence(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset, release = root / "dataset", root / "release"
            (dataset / "input").mkdir(parents=True)
            (release / "sanitized").mkdir(parents=True)
            original = "Dr. Mira spoke. S/o Mira"
            (dataset / "input" / "note.txt").write_text(original)
            digest = sha256(original.encode()).hexdigest()
            dump(dataset / "manifest.json", {"files": {"note.txt": digest}})
            dump(dataset / "truth.json", [{"file": "note.txt", "loc": "doc", "format": "txt",
                "patient_group": "fixture", "units": [{"location": "doc", "representation": "text",
                    "spans": [{"start": 4, "end": 8, "surface": "Mira", "kind": "PROTECT"},
                              {"start": 20, "end": 24, "surface": "Mira", "kind": "RELATIVE"}]}]}])
            dump(release / "report.json", {"files": [{"input_sha256": digest,
                "output": "sanitized/note.txt", "status": "sanitized"}]})
            (release / "records.jsonl").write_text("")
            note = release / "sanitized" / "note.txt"
            note.write_text("Dr. [NAME] spoke. S/o Mira")
            result = benchmark.audit(dataset, release)["by_format"]["txt"]
            self.assertEqual(result["protected_preserved"], 0)
            self.assertEqual(result["literal_residuals"], 1)
            note.write_text("Dr. Mira spoke. S/o [NAME]")
            result = benchmark.audit(dataset, release)["by_format"]["txt"]
            self.assertEqual(result["protected_preserved"], 1)
            self.assertEqual(result["identifier_transformed"], 1)
            (release / "sanitized" / "unreported.txt").write_text("fixture")
            with self.assertRaisesRegex(ValueError, "unreported_release_artifact"):
                benchmark.audit(dataset, release)

    def test_indistinguishable_duplicates_remain_unresolved(self):
        from evaluation.release_evidence import OccurrenceAlignment
        alignment = OccurrenceAlignment("Mira Mira", "Mira")
        self.assertEqual(alignment.outcome(0, 4), "unresolved")
        self.assertEqual(alignment.outcome(5, 9), "unresolved")

    def test_suppressed_record_cannot_claim_the_surviving_row(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset, release = root / "dataset", root / "release"
            (dataset / "input").mkdir(parents=True)
            (release / "sanitized").mkdir(parents=True)
            original = b"Dose,Reference\n5 mg,first\n5 mg,second\n"
            (dataset / "input" / "visits.csv").write_bytes(original)
            digest = sha256(original).hexdigest()
            dump(dataset / "manifest.json", {"files": {"visits.csv": digest}})
            dump(dataset / "truth.json", [
                {"file": "visits.csv", "loc": f"row:{i}", "format": "csv",
                 "patient_group": f"group-{i}", "units": [
                     {"location": "0", "representation": "text",
                      "spans": [{"start": 0, "end": 4, "surface": "5 mg", "kind": "PROTECT"}]}
                 ]} for i in range(2)
            ])
            output = "sanitized/visits.csv"
            (release / output).write_text("Dose,Reference\n5 mg,PSN-SYNTHETIC\n")
            dump(release / "report.json", {"files": [{"input_sha256": digest,
                 "output": output, "status": "sanitized"}]})
            ledger = release / "records.jsonl"
            rows = [
                {"file": output, "loc": "row:0", "status": "suppressed", "patient": None},
                {"file": output, "loc": "row:1", "out": "row:0", "patient": "PSN-SYNTHETIC"},
            ]
            ledger.write_text("".join(json.dumps(row) + "\n" for row in rows))
            report = benchmark.audit(dataset, release)
            self.assertEqual(report["by_format"]["csv"]["records_locatable"], 1)
            self.assertEqual(report["by_format"]["csv"]["protected_preserved"], 1)
            self.assertEqual(report["by_format"]["csv"]["protected_unexported"], 1)
            self.assertEqual(report["by_format"]["csv"]["records_suppressed"], 1)
            self.assertEqual(report["linkage"]["false_pairs"], 0)

            rows[0]["status"] = "sanitized"
            ledger.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "reused_output_record"):
                benchmark.audit(dataset, release)

    def test_release_check_finds_known_surface_moved_outside_annotated_field(self):
        import base64

        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset, release = root / "dataset", root / "release"
            (dataset / "input").mkdir(parents=True)
            (release / "sanitized").mkdir(parents=True)
            (release / "logs").mkdir()
            surface = "Mira Sen"
            raw = json.dumps({"name": surface, "summary": "asthma"}).encode()
            (dataset / "input" / "case.json").write_bytes(raw)
            digest = sha256(raw).hexdigest()
            dump(dataset / "manifest.json", {"files": {"case.json": digest}})
            dump(dataset / "truth.json", [{"file": "case.json", "loc": "doc", "format": "json",
                "units": [{"location": "/name", "representation": "text", "spans": [
                    {"start": 0, "end": len(surface), "surface": surface, "kind": "NAME"}
                ]}]}])
            path = "sanitized/case.json"
            dump(release / "report.json", {"files": [{"input_sha256": digest,
                "output": path, "status": "sanitized"}]})
            (release / "records.jsonl").write_text("")
            (release / "logs" / "run.txt").write_text(surface)
            dump(release / path, {"name": "[NAME]", "summary": "asthma " + surface,
                "document": {"contentType": "text/plain",
                             "data": base64.b64encode(surface.encode()).decode()},
                "text": {"div": '<div xmlns="http://www.w3.org/1999/xhtml">'
                                '<b>Mira</b> <span>Sen</span></div>'}})
            report = benchmark.audit(dataset, release)
            self.assertEqual(report["by_format"]["json"]["identifier_transformed"], 1)
            self.assertEqual(report["release_surface_scan"]["by_channel"],
                             {"record_content": 1, "attachment": 1, "log": 1, "narrative": 1})
            self.assertEqual(report["release_surface_scan"]["unique_surfaces_seen"], 1)
            self.assertNotIn(surface, json.dumps(report))

    def test_index_uses_longest_locator_without_counting_covering_entry_as_exact(self):
        file = "sanitized/a.json"
        parent = {"file": file, "loc": "/visits/1", "out": "/kept/2", "patient": "SYN"}
        fallback = {"file": file, "loc": "doc", "patient": None}
        index = {(file, parent["loc"]): parent, (file, "doc"): fallback}
        self.assertEqual(benchmark.matching_index_entry(index, file, "/visits/1/0"),
                         (parent, "/kept/2/0"))
        self.assertEqual(benchmark.matching_index_entry(index, file, "/visits/10"),
                         (fallback, "/visits/10"))

    def test_one_broad_prediction_cannot_match_two_occurrences(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "input").mkdir()
            (folder / "input" / "note.txt").write_text("Ab Cd")
            dump(folder / "manifest.json", {})
            dump(folder / "truth.json", [{
                "file": "note.txt", "loc": "doc", "format": "txt",
                "units": [{"location": "doc", "spans": [
                    {"start": 0, "end": 2, "surface": "Ab", "kind": "NAME"},
                    {"start": 3, "end": 5, "surface": "Cd", "kind": "NAME"},
                ]}],
            }])
            units = list(benchmark.source_units(folder))
            raw = json.dumps(units).encode()
            predictions = {"schema": "phase-a-predictions/1", "input_sha256": sha256(raw).hexdigest(),
                           "units": {unit["id"]: {"status": "complete", "review": [],
                                                  "accepted": [[0, 5, "NAME"]] if unit["channel"] == "content" else []}
                                     for unit in units}}
            result = benchmark.score_spans(folder, raw, predictions)["by_category"]["NAME"]
            self.assertEqual(result["exact_hits"], 0)
            self.assertEqual(result["overlap_hits"], 1)

    def test_fhir_role_predictions_use_actor_paths_not_annotation_roles(self):
        from evaluate import predict
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "input").mkdir()
            dump(folder / "input" / "actors.json", {
                "resourceType": "Bundle", "type": "collection", "entry": [
                    {"resource": {"resourceType": "Patient", "name": [{"text": "Mira Sen"}],
                                  "contact": [{"name": {"text": "Mira Sen"}}]}},
                    {"resource": {"resourceType": "RelatedPerson", "name": [{"text": "Mira Sen"}]}},
                    {"resource": {"resourceType": "Practitioner", "name": [{"text": "Mira Sen"}]}},
                ],
            })
            inputs = list(benchmark.source_units(folder))
            snapshot = predict(json.dumps(inputs).encode())["units"]
            actors = {unit["label"]: snapshot[unit["id"]]["accepted_roles"] for unit in inputs
                      if unit["text"] == "Mira Sen"}
            self.assertEqual(actors, {
                "patient name": [(0, 8, "NAME", "patient")],
                "contact name": [(0, 8, "NAME", "contact")],
                "related person name": [(0, 8, "RELATIVE", "related_person")],
                "clinician name": [],
            })

    def test_structured_inventory_and_release_agree_on_clinician_context(self):
        from evaluate import predict
        from rakshak.release import publish_release

        with TemporaryDirectory() as directory:
            dataset, release = Path(directory) / "dataset", Path(directory) / "release"
            (dataset / "input").mkdir(parents=True)
            bundle = {"resourceType": "Bundle", "type": "collection", "entry": [
                {"resource": {"resourceType": "Organization", "name": "Example Care"}},
                {"resource": {"resourceType": "Patient",
                              "telecom": [{"system": "email", "value": "fixture@example.invalid"}]}},
            ]}
            dump(dataset / "input" / "bundle.json", bundle)
            contact = {"display": "Mira Sen", "email": "a@example.invalid"}
            review = {"Clinician": {"name": "Mira Sen"}, "patientName": "Mira Sen",
                      "subject": contact, "assessment": {"subject": contact}}
            dump(dataset / "input" / "review.json", review)
            units = list(benchmark.source_units(dataset))
            snapshot = predict(json.dumps(units).encode())["units"]
            for item in units:
                if item["text"] == "Example Care" or item.get("label") == "clinician name":
                    self.assertEqual(snapshot[item["id"]]["accepted"], [])
                if item["text"] == "fixture@example.invalid":
                    self.assertEqual(snapshot[item["id"]]["accepted"], [(0, 23, "EMAIL")])
            self.assertTrue(any(item.get("label") == "clinician name" for item in units))
            inferred = [snapshot[item["id"]]["accepted_roles"] for item in units
                        if item.get("label") == "patient display"]
            self.assertEqual(inferred, [[(0, 8, "NAME", "patient")]])
            publish_release(dataset / "input", release, b"fixture")
            self.assertEqual(benchmark.read_json(release / "sanitized" / "review.json"),
                             {"Clinician": {"name": "Mira Sen"}, "patientName": "[NAME]",
                              "subject": {"display": "[NAME]", "email": "[EMAIL]"},
                              "assessment": {"subject": {"display": "Mira Sen", "email": "[EMAIL]"}}})
            resources = benchmark.read_json(release / "sanitized" / "bundle.json")["entry"]
            self.assertEqual(resources[0]["resource"]["name"], "Example Care")
            self.assertEqual(resources[1]["resource"]["telecom"][0]["value"], "[EMAIL]")

    def test_release_reconciles_identical_inputs_when_reported_paths_distinguish_them(self):
        from evaluation.release_evidence import reconcile
        with TemporaryDirectory() as directory:
            release = Path(directory)
            (release / "sanitized").mkdir()
            expected = {"one.txt": "same", "two.txt": "same"}
            for path in expected:
                (release / "sanitized" / path).write_text("same")
            rows = [{"input_sha256": "same", "output": "sanitized/" + path,
                     "status": "sanitized"} for path in reversed(expected)]
            dump(release / "report.json", {"files": rows})
            self.assertEqual(reconcile(release, expected)["one.txt"]["output"], "sanitized/one.txt")
            rows[1]["output"] = rows[0]["output"]
            dump(release / "report.json", {"files": rows})
            with self.assertRaisesRegex(ValueError, "reused_release_artifact"):
                reconcile(release, expected)

    def test_incomplete_predictions_are_counted_without_accuracy_or_precision(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "input" / "note.txt"
            source.parent.mkdir()
            source.write_text("Patient: Alira. Pulse: 74.", encoding="utf-8")
            dump(folder / "manifest.json", {})
            dump(folder / "truth.json", [{
                "id": "a", "file": "note.txt", "format": "txt", "loc": "doc",
                "units": [{"location": "doc", "representation": "text", "label": "", "spans": [
                    {"kind": "NAME", "surface": "Alira", "start": 9, "end": 14},
                    {"kind": "PROTECT", "surface": "74", "start": 23, "end": 25},
                ]}],
            }])
            inventory = list(benchmark.source_units(folder))
            units = json.dumps(inventory).encode()
            snapshot = {"schema": "phase-a-predictions/1", "input_sha256": sha256(units).hexdigest(),
                        "units": {unit["id"]: {"status": "input_limit" if unit["text"].startswith("Patient:")
                                              else "complete", "accepted": [], "review": []}
                                  for unit in inventory}}
            result = benchmark.score_spans(folder, units, snapshot)
            self.assertEqual(result["counts"]["incomplete_units"], 1)
            self.assertEqual(result["by_category"]["NAME"]["exact_hits"], 0)
            self.assertEqual(result["by_category"]["NAME"]["incomplete"], 1)
            self.assertNotIn("precision", result)
            with self.assertRaisesRegex(ValueError, "prediction_input_digest"):
                benchmark.score_spans(folder, units + b" ", snapshot)
