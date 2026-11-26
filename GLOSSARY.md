# Secret Wards

Secret Wards prepares synthetic hospital records for research while protecting patient identities and preserving clinical information.

## Language

**Patient**:
An individual who received care and may be represented by several **Patient Records**, possibly at different hospitals.

**Patient Record**:
A row, structured entry, or document about a **Patient**. One patient can have many records across registrations, visits, prescriptions, and other exports.
_Avoid_: Patient, file

**Direct Identifier**:
Information that directly identifies a **Patient** or associated person, such as a full name, phone number, or government-assigned identifier.

**Quasi-Identifier**:
An attribute such as an age, locality, or encounter date that can help identify a **Patient** when combined with other information.

**Patient Pseudonym**:
A substitute identifier shared by the released records assigned to one **Patient** within a **Research Release**.
_Avoid_: Patient name, anonymous ID

**False Merge**:
The assignment of **Patient Records** from different patients to the same **Patient Pseudonym**.

**Missed Link**:
A failure to group **Patient Records** that available evidence identifies as belonging to the same **Patient**.

**Clinical Utility**:
The value of a **Research Release** for analysis, including intact clinical observations, accurate time intervals, and representative coverage of the input.

**Research Release**:
The collection of processed hospital records and accompanying information made available for research.
_Avoid_: Anonymous dataset

**Quarantined File**:
An input file excluded from the **Research Release** because it could not be processed safely.

**Canary**:
A synthetic identity deliberately placed in the inputs to verify whether identifying information escapes during processing or in a **Research Release**.
