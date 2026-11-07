# KYC checks (build Phase 3)

Code: `backend/app/kyc/` (`ocr.py`, `checks.py`, `gstin.py`, `names.py`, `service.py`). Results on the sample applicants: [`kyc_results.md`](kyc_results.md), regenerated with `python3 scripts/kyc_batch.py`.

## Order of events

1. **Consent first.** `POST /consent` stores purpose `kyc_verification`, notice version `kyc-v1.0`, language, timestamp and a hash of the client. Only then does a KYC case exist, and `kyc_cases.consent_id` is NOT NULL, so there is nowhere to upload to before consent. `POST /kyc/upload` also re-checks the consent on every call and returns `403 CONSENT_REQUIRED` once it is withdrawn. Withdrawing (`DELETE /consent/{id}`) deletes the files at once, closes the case and cancels the order.
2. **Upload.** Each photo is OCR'd on arrival (about 1.5 s a page). Problems the customer can fix straight away (blur, a stale bill, an unreadable GSTIN) come back in `instant_checks`.
3. **Submit.** The order moves to `KYC_SUBMITTED` and every rule below runs in a background task.
4. **Result.** Verified → `KYC_VERIFIED`. Any failed rule → `KYC_FLAGGED` plus a `kyc_flag` escalation to the least-loaded KYC agent who speaks the customer's language. If the verdict is Human review, the order then moves on to `HUMAN_REVIEW`.

## OCR

| Step | Setting |
|---|---|
| Watermark removal | pixels with `R−G > 25` and `R−B > 15` (the pink "SYNTHETIC SPECIMEN" text) are set to white |
| Binarise | grey < 150 → black |
| Sharpness | variance of the Laplacian; **below 50 = unreadable**. The blurry K04 certificate scores 1.0; clean scans score 900–1,900 |
| OCR confidence | Tesseract mean word confidence; **below 55% = unreadable** |
| Deskew | angle search −12° to +12° on row-projection variance (2° coarse, 0.5° fine); K02 is straightened by 7° |
| GSTIN line | find the word "GSTIN", crop to its right, re-read with 5 threshold/scale settings and 2 page modes, letters and digits only |

## GSTIN reading

The checksum is the official GST mod-36 check digit and accepts `X` as the 4th PAN character. An OCR read becomes a GSTIN only if, after swapping up to 3 look-alike characters (0/O/D, 1/I/L, 5/S, 8/B, 2/Z, 6/G, 3/9, 7/1, U/V), it passes the checksum **and** exists in the registry. If no read works, the registry is searched by the trade name on the certificate. A difference that is not a look-alike (K06: 8 where the registry has 5) means the number printed on the certificate is not that business's GSTIN, and it goes to a person.

## Name matching

`names.match(a, b)`: lower-case, drop punctuation and "LLP", "Pvt Ltd", "Private Limited", then

- same number of words: every word pair equal, or for words over 3 letters a difflib ratio of **at least 0.80**. That forgives one OCR slip per word ("Bental" vs "Dental" = 0.83) but not a different word ("Shri" vs "Neelgiri" = 0.33);
- different number of words: whole strings at least **0.95** similar.

For proprietorships the registry legal name is "Owner (Prop. Trade name)". Both parts are compared: the trade name inside the brackets with the registry trade name, and the owner with the registry owner.

## The rules

Each rule writes one row to `kyc_checks` with `check_code`, `result`, `severity`, a customer message in their language (`app/i18n/kyc_messages.json`, 8 languages) and an internal reason. Every identifier in the reason is masked.

| Code | Rule | Fails when | Severity |
|---|---|---|---|
| `DOCUMENT_PRESENT` | Missing document detected (one row per document) | GST certificate, Udyam certificate, signatory ID or address proof not uploaded | missing_document |
| `DOCUMENT_READABLE` | Photo is good enough to read | sharpness < 50 or OCR confidence < 55% | unreadable |
| `GSTIN_FORMAT` | GSTIN valid format + checksum | no read passes pattern and checksum | needs_review |
| `GSTIN_MATCHES_CERTIFICATE` | The number on the certificate is this business's GSTIN | the only registry match differs by a non-look-alike character, or the GSTIN typed in step 1 differs from the certificate | mismatch |
| `GSTIN_EXISTS` | GSTIN exists in the registry | not in `gstin_registry` | mismatch |
| `GSTIN_ACTIVE` | GSTIN status Active | Cancelled or Suspended | **blocking** |
| `GSTIN_STATE_CODE` | State code in GSTIN matches registry state | first two digits map to another state | mismatch |
| `UDYAM_EXISTS` | Udyam exists | number blank on the certificate, bad format, or not in `udyam_registry` (district `00` accepted) | mismatch |
| `UDYAM_NAME_MATCH` | Udyam name matches | certificate name vs Udyam registry name fails `names.match` | mismatch |
| `NAMES_MATCH` | Names match across GST cert, Udyam cert and registry | any of: certificate trade name, business inside "(Prop. …)", proprietor, Udyam certificate name differs from the registry | mismatch |
| `SIGNATORY_FOR_BUSINESS` | Signatory ID is for this business | "For business" on the ID matches neither registry name | mismatch |
| `ADDRESS_MATCH` | Address on proof matches registry city/state | the bill address doesn't contain the registry city and state (spaces ignored, so OCR's "Ludhi ana" still matches) | mismatch |
| `ADDRESS_PROOF_DATE` | Address proof ≤ 90 days before 2026-07-15 | bill date older than 90 days or in the future | stale |

A rule that needs an earlier result (for example a registry lookup without a readable certificate) is skipped, not failed. The earlier failure already explains it.

## Verdict

| Failed severities | Verdict | Order | Escalation | What the customer sees |
|---|---|---|---|---|
| none | Verified | KYC_VERIFIED | none | green "Verified" |
| includes blocking | Blocked | KYC_FLAGGED | P1, 4 h | "Choose a plan without GST-only items"; GST-only items listed |
| includes missing, unreadable or stale | Re-upload needed | KYC_FLAGGED | P3, 24 h (an agent nudges if not fixed) | list of fixes, each with a re-upload button |
| mismatch or needs_review only | Human review | KYC_FLAGGED → HUMAN_REVIEW | P1, 4 h | "A specialist will call you by …" |

Re-uploading and submitting again closes the old escalation and runs every rule again on the latest version of each document.

## Data protection

- Files are Fernet-encrypted on disk under `backend/storage/<case>/`. The DB keeps only the encrypted path and a sha256.
- OCR text is stored encrypted. GSTIN and Udyam numbers are stored encrypted with a separate masked copy (`27•••••••••1Z5`, `UDYAM-DL-00-•••4567`). API responses carry only the masked forms, and the signatory ID number is shown as its last 4 characters.
- Retention: 30 days after consent if the customer never finishes, 90 days after verification, immediately on withdrawal.
- The logging filter masks GSTIN, Udyam, PAN and phone patterns in every log line.
