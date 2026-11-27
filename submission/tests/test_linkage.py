"""Synthetic unit tests for conservative table-only linkage."""
import unittest

from rakshak.linkage import row_evidence, resolve_linkage, json_evidence, text_evidence, text_target


SECRET = b"synthetic-linkage-test-a"
A = "2435 1234 5678"
B = "9856 4321 9876"
ABHA = "12-3456-7890-1234"
NAME = "Mira Sen"


class TestLinkage(unittest.TestCase):
    def row(self, **values):
        return row_evidence(list(values), list(values.values()), SECRET)

    def resolve(self, *rows, secret=SECRET):
        return resolve_linkage({i: row for i, row in enumerate(rows) if row is not None}, secret)

    def linked(self, *rows):
        links = self.resolve(*rows)
        self.assertEqual(len(rows), len(links))
        self.assertEqual(1, len(set(links.values())))
        self.assertRegex(links[0], r"^PSN-[0-9A-F]{24}$")
        return links[0]

    def test_global_aadhaar_and_abha_typed(self):
        self.linked(self.row(Aadhaar=A, PatientName=NAME), self.row(Aadhar="२४३५-१२३४-५६७८", PatientName="  MIRA SEN "))
        self.linked(self.row(ABHA=ABHA, PatientName=NAME), self.row(ABHA="12345678901234", PatientName=NAME))
        self.assertEqual({}, self.resolve(self.row(Aadhaar=A), self.row(Aadhaar=A)))
        self.linked(self.row(Aadhaar=A, ABHA=ABHA), self.row(Aadhaar=A, ABHA=ABHA))

    def test_mrn_scope_and_shape(self):
        a = self.row(UHID="CLN/26/00123", PatientName=NAME)
        b = self.row(UHID="cln/२६/००१२३", PatientName=NAME)
        self.assertEqual(0, a.column)
        self.linked(a, b)
        self.assertEqual({}, self.resolve(a, self.row(UHID="CLN-26-00123", PatientName=NAME)))
        self.assertEqual({}, self.resolve(a, self.row(UHID="CLN/26/00123", PatientName="Other Person")))
        self.assertIsNone(self.row(UHID="00001234", PatientName=NAME))
        self.assertIsNone(self.row(UHID="dose 50 mg", PatientName=NAME))

    def test_generic_mrn_requires_second_clue(self):
        a = self.row(UHID="UHID-00123", PatientName=NAME)
        self.assertEqual({}, self.resolve(a, a))
        a = self.row(UHID="UHID-00123", PatientName=NAME, Age="47", Sex="F")
        b = self.row(UHID="UHID-00123", PatientName=NAME, AgeSex="४७/F")
        self.linked(a, b)
        self.assertEqual({}, self.resolve(a, self.row(UHID="UHID-00123", PatientName=NAME, AgeSex="48/F")))
        self.assertEqual({}, self.resolve(a, self.row(UHID="UHID-00123", PatientName=NAME, Age="47")))

    def test_explicit_issuer_scope(self):
        a = self.row(UHID="MRN-00123", PatientName=NAME, Issuer="Clinic A")
        self.linked(a, a)
        self.assertEqual({}, self.resolve(a, self.row(UHID="MRN-00123", PatientName=NAME, Issuer="Clinic B")))
        self.assertEqual({}, self.resolve(a, self.row(UHID="MRN-00123", PatientName=NAME)))

    def test_contact_requires_name_and_independent_clue(self):
        a = self.row(Phone="+91 60000 12345", PatientName=NAME)
        b = self.row(Mobile="06000012345", PatientName=NAME)
        self.assertEqual({}, self.resolve(a, b))
        self.linked(self.row(Phone="+91 60000 12345", PatientName=NAME, DOB="1979-01-15"),
                    self.row(Mobile="06000012345", PatientName=NAME, DOB="15/01/1979"))
        self.linked(self.row(Email="synthetic@example.invalid", PatientName=NAME, Guardian="Arun Sen"),
                    self.row(Email="synthetic@EXAMPLE.INVALID", PatientName=NAME, RelativeName="Arun Sen"))
        self.assertEqual({}, self.resolve(self.row(Phone="+91 60000 12345", PatientName=NAME, DOB="1979-01-15"),
                                          self.row(Mobile="06000012345", PatientName="Other Person", DOB="1979-01-15")))

    def test_consistent_split_name_and_corroboration(self):
        first = self.row(PatientID="MRN-012345", FirstName="Mira", LastName="Sen", DOB="1979-11-23")
        second = self.row(UHID="MRN-012345", PatientName=NAME, DOB="23/11/1979")
        self.linked(first, second)

    def test_conflicting_age_name_village_relative_ids(self):
        first = self.row(Aadhaar=A, PatientName=NAME, Age="47", Village="Synthetic Nagar", Guardian="Arun Sen")
        for other in (
            self.row(Aadhaar=A, PatientName="Other Person"),
            self.row(Aadhaar=A, PatientName=NAME, Age="48"),
            self.row(Aadhaar=A, PatientName=NAME, Village="Different Nagar"),
            self.row(Aadhaar=A, PatientName=NAME, Guardian="Akash Sen"),
        ):
            self.assertEqual({}, self.resolve(first, other))
        self.assertEqual({}, self.resolve(self.row(UHID="CLN-00123", Aadhaar=A, PatientName=NAME),
                                          self.row(UHID="CLN-00123", Aadhaar=B, PatientName=NAME)))
        self.assertEqual({}, self.resolve(self.row(UHID="CLN-00123", Aadhaar=A, PatientName=NAME),
                                          self.row(UHID="CLN-00456", Aadhaar=A, PatientName=NAME)))
        self.linked(self.row(UHID="ABC-00123", Aadhaar=A, PatientName=NAME), self.row(UHID="DEF-00456", Aadhaar=A, PatientName=NAME))

    def test_transitive_chain_is_not_a_patient_cluster(self):
        a = self.row(UHID="CLN-00123", PatientName=NAME)
        b = self.row(UHID="CLN-00123", Aadhaar=A, PatientName=NAME)
        c = self.row(Aadhaar=A, PatientName=NAME)
        self.assertEqual({}, self.resolve(a, b, c))

    def test_same_identifier_with_conflicting_bucket_abstains(self):
        a = self.row(Aadhaar=A, PatientName=NAME)
        c = self.row(Aadhaar=A, PatientName="Other Person")
        self.assertEqual({}, self.resolve(a, a, c))

    def test_malformed_unrelated_cells_and_ambiguous_roles(self):
        self.assertIsNone(self.row(DoctorName=NAME, SampleID="CLN-123456", Result="243512345678"))
        self.assertIsNone(self.row(Aadhaar="XXXX XXXX 5678", PatientName=NAME))
        self.assertIsNone(self.row(ABHA="user@abdm", PatientName=NAME))
        self.assertIsNone(self.row(Phone="1-0-1", PatientName=NAME))
        self.assertIsNone(self.row(Aadhaar=A, AadhaarNo=B, PatientName=NAME))
        self.assertIsNone(self.row(Aadhaar=A, PatientName=NAME, Name="Other Person"))
        self.assertEqual({}, self.resolve(self.row(Aadhaar=A, PatientName="Mira"), self.row(Aadhaar=A, PatientName="Mira")))
        self.assertIsNone(row_evidence(["UHID"], [], SECRET))

    def test_determinism_and_keyed_evidence(self):
        header = ["Age", "Aadhaar", "PatientName", "UHID"]
        values = ["47", A, NAME, "CLN-123456"]
        a = row_evidence(header, values, SECRET)
        b = row_evidence(header, values, SECRET)
        self.assertEqual(3, a.column)
        first = resolve_linkage({"a": a, "b": b}, SECRET)
        self.assertEqual(first, resolve_linkage({"b": b, "a": a}, SECRET))
        secret2 = b"synthetic-linkage-test-b"
        a2 = row_evidence(header, values, secret2)
        self.assertNotEqual(first, resolve_linkage({"a": a2, "b": a2}, secret2))
        self.assertNotEqual(a, a2)
        self.assertEqual("<RowEvidence>", repr(a))
        self.assertNotIn(NAME, repr(vars(a)))
        self.assertNotIn(A, repr(vars(a)))
        self.assertNotIn(SECRET.decode(), repr(vars(a)))
        self.assertEqual({}, self.resolve(a))

    def test_unambiguous_dob_parse_only(self):
        a = row_evidence(["UHID", "PatientName", "DOB (MM/DD/YYYY)"], ["MRN-00123", NAME, "01/12/1979"], SECRET)
        b = row_evidence(["UHID", "PatientName", "DOB (DD/MM/YYYY)"], ["MRN-00123", NAME, "12/01/1979"], SECRET)
        self.linked(a, b)
        c = self.row(UHID="MRN-00123", PatientName=NAME, DOB="01/12/1979")
        self.assertEqual({}, self.resolve(a, c))
        self.assertIsNone(row_evidence(["UHID", "PatientName", "DOB (DD/MM/YYYY)"], ["MRN-00123", NAME, "01/13/1979"], SECRET).dob)


    def test_json_patient_fields_cross_format(self):
        doc = {'visits': [{'patient_ref': 'CLN-12345', 'patient': {'name': NAME, 'age_sex': '47/F'},
                           'doctor': {'name': 'Other Person'}, 'vitals': {'value': 123}}]}
        evidence, path = json_evidence(doc, '/visits/0', SECRET)
        self.assertEqual(('visits', 0, 'patient_ref'), path)
        table = self.row(UHID='CLN-12345', PatientName=NAME, AgeSex='47/F')
        self.linked(evidence, table)

    def test_json_whole_structured_record_and_string_only(self):
        doc = {'patient': {'name': NAME, 'age': 47, 'sex': 'F', 'hospital_uhid': 'MRN-00123'}}
        evidence, path = json_evidence(doc, 'doc', SECRET)
        self.assertEqual(('patient', 'hospital_uhid'), path)
        self.linked(evidence, self.row(UHID='MRN-00123', PatientName=NAME, AgeSex='47/F'))
        self.assertIsNone(json_evidence({'patient': {'aadhaar': 123456789012, 'name': NAME}}, 'doc', SECRET))
        self.assertIsNone(json_evidence({'metadata': {'name': NAME, 'uhid': 'CLN-12345'}}, 'doc', SECRET))
        self.assertIsNone(json_evidence({'secret-name': [{'name': NAME, 'uhid': 'CLN-12345'}]}, '/secret-name/0', SECRET))
        self.assertIsNone(json_evidence({'resourceType': 'Bundle', 'uhid': 'CLN-12345'}, 'doc', SECRET))

    def test_json_nested_ids_and_relative(self):
        doc = {'patients': [{'name': NAME, 'ids': {'aadhaar': A},
                             'guardian': {'name': 'Arun Sen', 'uhid': 'CLN-12345'}}]}
        evidence, path = json_evidence(doc, '/patients/0', SECRET)
        self.assertEqual(('patients', 0, 'ids', 'aadhaar'), path)
        self.linked(evidence, self.row(Aadhaar=A, PatientName=NAME, RelativeName='Arun Sen'))
        self.assertIsNone(json_evidence(doc, '/patients/9', SECRET))
        self.assertIsNone(json_evidence(doc, '/patients/00', SECRET))

    def test_text_label_line_and_validated_target(self):
        raw = 'Patient Name: ' + NAME + '\r\nUHID: CLN-12345\r\nDose: 10 mg'
        evidence, line, kind = text_evidence(raw, SECRET)
        self.assertEqual((1, 'MRN'), (line, kind))
        self.linked(evidence, self.row(UHID='CLN-12345', PatientName=NAME))
        clean = 'Patient Name: [NAME]\r\nUHID: [MRN]  \r\nDose: 10 mg'
        start, end = text_target(clean, line, kind)
        self.assertEqual('[MRN]', clean[start:end])
        self.assertIsNone(text_target('Patient Name: [NAME]\nUHID: [MRN] extra', line, kind))
        self.assertIsNone(text_target('Patient Name: [NAME]\nDoctor: [MRN]', line, kind))
        self.assertIsNone(text_evidence(raw + '\r\nUHID: CLN-12345', SECRET))
        self.assertIsNone(text_evidence('Dose: CLN-12345\nName: ' + NAME, SECRET))
        self.assertIsNone(text_evidence('Patient Name: ' + NAME + '\nUHID: CLN-12345; Dose 10mg', SECRET))


    def test_fhir_unique_typed_patient_identifier(self):
        patient = {'resourceType': 'Patient', 'id': 'unchanged-reference-id',
                   'identifier': [{'system': 'https://clinic.invalid/uhid', 'type': {'coding': [
                       {'system': 'http://terminology.hl7.org/CodeSystem/v2-0203', 'code': 'MR'}]},
                                   'value': 'CLN-12345'}],
                   'name': [{'text': NAME, 'given': ['Mira'], 'family': 'Sen'}]}
        bundle = {'resourceType': 'Bundle', 'entry': [{'resource': patient}, {'resource': {'resourceType':'Observation',
                  'subject': {'reference': 'Patient/unchanged-reference-id'}, 'value': 42}}]}
        evidence, path = json_evidence(bundle, 'doc', SECRET)
        self.assertEqual(('entry', 0, 'resource', 'identifier', 0, 'value'), path)
        self.linked(evidence, self.row(UHID='CLN-12345', PatientName=NAME))
        self.assertIsNone(json_evidence({'resourceType':'Bundle', 'entry':[{'resource':patient}, {'resource':patient}]}, 'doc', SECRET))
        bundle['entry'][1]['resource']['subject']['identifier'] = {'value': 'CLN-12345'}
        self.assertIsNone(json_evidence(bundle, 'doc', SECRET))
        del patient['identifier'][0]['type']
        self.assertIsNone(json_evidence({'resourceType':'Bundle','entry':[{'resource':patient}]}, 'doc', SECRET))


if __name__ == "__main__":
    unittest.main()
