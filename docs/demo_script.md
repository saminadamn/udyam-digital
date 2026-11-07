# Udyam Digital: 3-minute demo script

Total running time 3:00. Voiceover about 280 words. Phone screens on the left of the frame, labels on the right.

| Time | Scene | On screen | Voiceover |
|---|---|---|---|
| 0:00–0:15 | **The problem** | Showcase site: cover, then the Problem slide. Cut to the phone. | Accel Business converts 7 in 100 small-business leads. Buying takes a visit, a slow quote, paper KYC and 17.6 days. Udyam Digital does it on a phone, in one sitting. |
| 0:15–0:27 | **Language and login** | Phone: pick हिन्दी, enter a mobile number, the mock OTP fills in, "Send me updates on WhatsApp" stays ticked. | The owner picks a language, logs in with an OTP and opts in to WhatsApp updates. Eight languages, voice included. |
| 0:27–0:57 | **Advisor, by voice** | Tap the mic and answer in Hindi: dental clinic, 6 people, Kolkata. Type GSTIN 19EOGXH4115Y1ZL at question 3 (green tick). The recommendation card appears: a reason per item, one refused item with its unlock. | No salesperson. The advisor asks at most six questions, here by voice in Hindi, and checks the GSTIN as it's typed. The rules engine picks the bundle; the AI only explains why, in plain words. Anything the business isn't eligible for is refused, with what would unlock it. |
| 0:57–1:15 | **One monthly price** | Quote: toggle an add-on, step a quantity, point at the locked item ("Needed by Static IP") and the "compared with what you pay now" line. Tap Accept. | One monthly price. Add-ons toggle and the total updates instantly. Items that others depend on stay locked, with the reason, and it compares with what they pay today. |
| 1:15–1:50 | **Smart KYC** | Consent screen (what, why, how long, withdraw): accept. GSTIN lookup pre-fills the legal name and address. Upload the four K02 files: each gets a tick. Cut-in, 3 s: a different applicant's stale bill gets the exact fix. Back to K02: Verified, installation booked. | Before any document, a DPDP consent screen: what we collect, why, for how long, and how to withdraw. Registry lookups pre-fill the details. Documents are read and cross-checked as they upload, so a stale bill is caught now, not days later. Verified, and installation books itself. |
| 1:50–2:12 | **Tracker and escalation** | Tracker with expected dates and the technician visit. Admin, Order simulator: "Make it late by 30 hours". Back on the phone: the delay banner names the agent. Admin outbox: the Hindi WhatsApp message. | The owner sees dates instead of chasing. If a step runs late, the system escalates on its own to the least-loaded agent who speaks their language, and the owner gets a WhatsApp update. |
| 2:12–2:38 | **Humans and sales** | Agent console: chat, quote, KYC and timeline in one view. Leads dashboard: filter "High propensity, not contacted", tap Call, log the outcome. Hold on the live metrics strip. | People handle the exceptions, with full context. For sales, every lead gets a propensity score and its reasons. One filter shows high-propensity leads nobody has called, and the five pilot metrics are computed live from the database. |
| 2:38–2:50 | **Privacy by design** | Showcase site: Architecture, then the Privacy pipeline. Zoom on a masked GSTIN (27•••••••••1Z5). | IDs are masked on screen and in logs, encrypted at rest, and documents delete themselves after 90 days. |
| 2:50–3:00 | **Close** | Impact slide: baseline to target for the five metrics. End card with the link. | Fifteen judge scenarios and 192 tests pass. A plan in minutes, and a target of eight days to go live, not 17.6. |

## Before recording

- Record the phone at 390×844 (browser device mode or a real phone) and the admin screens at 1440×900.
- Start the API with SLA_SCAN_INTERVAL_SEC=5 so the delay escalation shows within seconds.
- Have data/kyc_documents/K02_* ready to upload, and a 3-second clip of K11's stale-bill message for the cut-in.
- Log in as admin with 9000000001 in a second window (simulator, outbox, leads) and as agent Priya with 9000000101.
- Read the voiceover at a calm pace: about 280 words in 3 minutes leaves room for the on-screen actions.

_Voiceover: 282 words._
