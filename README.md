# Udyam Digital (Accel Business) — YTL Hackathon 2026, Track A

AI handles acquisition; humans handle exceptions. A mobile-first web app where a small business owner finds the right bundle in their own language, with every eligibility decision made by a deterministic rules engine.

**Status: build Phases 1–6 done.** Phase 6: 15 judge-style advisor scenarios, unit tests for every core module, a mobile end-to-end run, a security pass, and deploy configs.

- **Phase 1:** scaffold, theme, 8 languages, OTP login, rules engine, advisor chat, recommendation card.
- **Phase 2:** pricing rule, quote screen with locks, toggles and steppers, the "compare with what you pay now" line, and accept → order.
- **Phase 3:** consent first, GSTIN and Udyam lookups, OCR on 4 uploaded documents, 13 cross-check rules with readable reasons, and verdicts that move the order and open an escalation on any failure. Results on K01–K12: `docs/kyc_results.md`; rules and thresholds: `docs/KYC_CHECKS.md`.

- **Phase 4:** order tracker with expected and actual dates, automatic install booking, an SLA job that escalates late orders to the least-loaded agent who speaks the customer's language, "Talk to a person", an agent console with full case context, and an order simulator for the demo.

- **Phase 5:** voice in the advisor (hold the mic; replies read back short in the chosen language; Web Speech API first, Sarvam/Bhashini server adapter behind `/voice/*`), WhatsApp updates for opted-in owners (quote accepted, KYC verified/fix/review, install booked, delay/escalation, live, 24 h KYC reminder) through the Twilio sandbox or a mock outbox, the admin leads dashboard (imported + app leads, propensity bucket and reasons, "Advisor could not close" and "High propensity, not contacted", Call with outcome) and a live metrics strip with the 5 pilot metrics.

**Phase 5 demo:** log in as admin (9000000001) → `/admin/leads`. Outbox: `/admin/notifications`. Server speech with Sarvam: in `backend/.env` set `VOICE_PROVIDER=sarvam` and `VOICE_API_KEY=<your key>`. Real WhatsApp: set `NOTIFY_PROVIDER=twilio` plus `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` (and `PUBLIC_API_URL` for delivery callbacks); the owner's phone must have joined your sandbox. Server speech: `VOICE_PROVIDER=sarvam` or `bhashini` with `VOICE_API_KEY` (needs `ffmpeg`). With nothing set, everything runs on the mock outbox and the phone's own speech.

**Phase 5 notes:** the leads table and metrics read only the database; baselines are recomputed from the imported leads (7.4%, 17.6 d, Rs 15,053, 15.2%, 3.0) and the current column from app leads and orders. 6-month churn shows "—" until the first app customer has been live 6 months. An app lead counts as "advisor could not close" when it was handed to a person, or went quiet for `ADVISOR_ABANDON_MINUTES` (30) without an order. Imported leads have no phone number in the app, so their calls are always logged as mock calls. Logging in without the `whatsapp_opt_in` field now keeps the earlier choice (it used to withdraw consent). Fixed: the PII log filter broke uvicorn's access log.

## Demo login

Open the app, pick a language, and log in with **any Indian mobile number**. The demo runs with `OTP_MODE=mock`, so the 6-digit code is shown on screen. Keep "Send me updates on WhatsApp" ticked to see messages land in the outbox.

Staff log in on the same page: admins land on `/admin/leads`, agents on `/admin/escalations`.

| Phone | Who | Speaks | Handles |
|---|---|---|---|
| 9000000001 | Admin: leads dashboard, outbox, order simulator, reassign | | |
| 9000000101 | Priya Sharma | hi, en | kyc, sales |
| 9000000102 | Arjun Iyer | ta, en, te | sales, install |
| 9000000103 | Meera Kulkarni | mr, hi, gu | kyc, install |
| 9000000104 | Sanjay Das | bn, hi, en | install, account manager |
| 9000000105 | Kavya Rao | kn, te, en | account manager, sales, kyc |

A full journey on a phone: advisor → plan → quote → accept → consent → GSTIN `19EOGXH4115Y1ZL` → upload the four `data/kyc_documents/K02_*.png` files → verified and installation booked. Then, as admin, open `/admin/simulator` and move the order to Installed and Live; the tracker and the outbox follow.

## Run it locally

```bash
# backend (Python 3.11+), with tesseract-ocr (KYC OCR) and ffmpeg (server speech only)
cd backend
sudo apt install tesseract-ocr ffmpeg
pip install -r requirements.txt   # or: pip install -e ".[dev]"
cp .env.example .env              # dev defaults work as they are
python -m app.seed                # 4 CSVs from ../data -> udyam.db, scored leads, 5 agents, demo users
uvicorn app.main:app --port 8000  # API docs: http://localhost:8000/api/docs

# frontend (Node 20+)
cd frontend
cp .env.example .env.local
npm install
npm run dev                       # http://localhost:3000
```

**Demo a delay:** start the API with `SLA_SCAN_INTERVAL_SEC=5`, open `/admin/simulator`, pick an order in INSTALL_BOOKED, "Make it late by 30 hours". Within a few seconds the customer's tracker shows the delay and names the agent who will call. From a terminal: `python scripts/simulate.py UD-2611-0004 --late 30 --scan`.

## Environment variables

Backend (`backend/.env` locally, the host's environment settings when deployed). Everything has a dev default; the ones marked **required** must be set when `APP_ENV` is `demo` or `prod`, or the API refuses to start.

| Variable | Default | What it does |
|---|---|---|
| `APP_ENV` | `dev` | `dev` / `demo` / `prod`. Outside `dev`, real secrets are enforced |
| `JWT_SECRET` | dev value | **required**, 32+ chars. Signs login tokens |
| `APP_ENCRYPTION_KEY` | derived in dev | **required**, 32+ chars (a Fernet key or any long random string). Encrypts PII columns and document files |
| `PII_HASH_KEY` | dev value | **required**, 32+ chars. HMAC for phone lookups |
| `DATABASE_URL` | `sqlite:///backend/udyam.db` | SQLite path |
| `UPLOAD_DIR` | `backend/storage` | Encrypted KYC files; never served over HTTP |
| `DATA_DIR` | `../data` | The CSVs the seed loads |
| `CORS_ORIGINS` | localhost:3000 | Comma-separated frontend URLs (your Vercel URL) |
| `CORS_ORIGIN_REGEX` | empty | Optional, e.g. `https://udyam[a-z0-9-]*\.vercel\.app` for preview deployments |
| `OTP_MODE` | `mock` | `mock` shows the code on screen (demo) |
| `PUBLIC_APP_URL` | localhost:3000 | Frontend URL used in WhatsApp links |
| `PUBLIC_API_URL` | empty | Public API URL, needed only for Twilio delivery callbacks |
| `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` | `template` | Advisor wording; `template` needs no key |
| `NOTIFY_PROVIDER` | `mock` | `twilio` sends real WhatsApp via the sandbox (with `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`); falls back to the mock outbox without credentials |
| `TWILIO_VOICE_FROM` | empty | Caller ID for click-to-call from the leads dashboard |
| `VOICE_PROVIDER` | `browser` | `sarvam` or `bhashini` for server speech when the phone has none |
| `VOICE_API_KEY` | empty | **Your Sarvam (or Bhashini) key goes here.** Never commit it |
| `SLA_SCAN_INTERVAL_SEC` | `300` | How often the late-order job runs (5 for a live demo) |
| `ADVISOR_ABANDON_MINUTES` | `30` | Quiet time before an app lead counts as "advisor could not close" |
| `LOOKUP_RATE_LIMIT`, `OTP_IP_RATE_LIMIT` | `20`, `20` | Per user per 10 min (GSTIN/Udyam lookups); OTP requests per IP per 10 min (plus 3 per phone) |
| `DOC_RETENTION_DAYS`, `DOC_RETENTION_ABANDONED_DAYS` | `90`, `30` | When KYC files are deleted |
| `KYC_TODAY` | `2026-07-15` | Fixed "today" for the dataset's bill-date check |

Frontend (`frontend/.env.local`, or Vercel project settings): `NEXT_PUBLIC_API_BASE_URL` (the backend URL + `/api/v1`), `NEXT_PUBLIC_DEMO_MODE=true` (shows the mock OTP), `NEXT_PUBLIC_DEFAULT_LANG=hi`, `NEXT_PUBLIC_SUPPORTED_LANGS=hi,en,mr,ta,bn,kn,gu,te`.

## Deploy

Push the repo to GitHub first.

**Backend on Render** (Docker, seeded SQLite):

1. Render → New → Blueprint → pick the repo. `render.yaml` creates `udyam-api` from `backend/Dockerfile`, generates `JWT_SECRET`, `APP_ENCRYPTION_KEY` and `PII_HASH_KEY`, and installs Tesseract and ffmpeg.
2. On first start, `backend/start.sh` seeds SQLite with the deployment's own keys (25 products, both registries, 5,000 scored leads, agents, demo logins). The free plan's disk is ephemeral, so every restart returns to clean demo data. Add a Render disk at `/srv/db` and `/srv/storage` to keep data.
3. Wait for `https://<name>.onrender.com/api/v1/health` to show `"status":"ok"`.
4. Railway works the same way: new project from the repo, Dockerfile path `backend/Dockerfile`, and set the same variables by hand (generate the three secrets with `openssl rand -hex 32`).

**Frontend on Vercel:**

1. Vercel → Add New Project → the repo → **Root Directory `frontend`** (Next.js is detected).
2. Environment variables: `NEXT_PUBLIC_API_BASE_URL=https://<name>.onrender.com/api/v1`, `NEXT_PUBLIC_DEMO_MODE=true`, `NEXT_PUBLIC_DEFAULT_LANG=hi`, `NEXT_PUBLIC_SUPPORTED_LANGS=hi,en,mr,ta,bn,kn,gu,te`. Deploy.
3. Back on Render, set `CORS_ORIGINS` and `PUBLIC_APP_URL` to the Vercel URL and redeploy.

**Check the live link on a phone viewport:** `E2E_WEB=https://<app>.vercel.app E2E_API=https://<name>.onrender.com/api/v1 python scripts/e2e_happy_path.py out/` runs the whole journey (language to live) in a Pixel 5 browser and saves a screenshot per step. Free Render instances sleep after 15 minutes idle; the first request takes about a minute to wake them, and the script waits.

## How to run the KYC test

The 12 sample applicants (K01–K12) in `data/kyc_documents/` each carry one planted problem (or none). Three ways to run them:

```bash
# 1. Batch: all 47 images through the app's own OCR and 13 checks; writes docs/kyc_results.md and docs/kyc_results.json
python scripts/kyc_batch.py
# expect: "All 12 verdicts match the planted problems: yes"

# 2. Automated tests: every applicant's expected verdict plus consent, GSTIN/Udyam APIs and log masking
cd backend && pytest -q tests/test_kyc.py

```

3. **One applicant by hand, in the app:** run the demo journey above but upload a different applicant's four files at the KYC step, for example `K11_*` (stale bill: re-upload asked, with the exact fix) or `K06_*` (wrong GSTIN on the certificate: sent to a KYC specialist, who appears in `/admin/escalations` for agent Priya, 9000000101).

| Applicant | Expected verdict | Planted problem |
|---|---|---|
| K02, K03, K08, K09, K10, K12 | Verified | none |
| K01 | Blocked | GSTIN cancelled |
| K04 | Re-upload needed | blurry GST certificate |
| K05 | Re-upload needed | Udyam certificate missing |
| K06 | Human review | GSTIN on certificate isn't this business's |
| K07 | Human review | legal name on the certificate names another business |
| K11 | Re-upload needed | bill older than 90 days |

Rules and thresholds: `docs/KYC_CHECKS.md`. Latest results: `docs/kyc_results.md`.

## Tests

```bash
cd backend && pytest -q        # 192 tests, about 2 minutes
```

| File | Covers |
|---|---|
| `test_rules.py` | 22 bundle checks, 9 must-refuse cases, every catalogue rule |
| `test_pricing.py` | pricing rule for every product and segment, totals, setup, contract, install days |
| `test_gstin.py` | checksum (with `X` as the 4th PAN character), format |
| `test_kyc.py` | K01–K12 verdicts, consent before upload, lookups, masked logs |
| `test_state_machine.py` | every allowed and refused transition, events, SLA deadlines |
| `test_escalations.py` | skill filter, language match, least-loaded, full and inactive agents |
| `test_advisor.py`, `test_advisor_scenarios.py` | 10 profiles plus 15 judge-style scenarios (results in `docs/advisor_scenarios.md`) and spoken number words |
| `test_quotes.py`, `test_tracker.py` | quotes, locks, orders, tracker, SLA job, agent console |
| `test_notifications.py`, `test_voice.py`, `test_admin_leads.py`, `test_metrics.py` | Phase 5 |
| `test_privacy.py` | security pass: log scrubbing, encrypted uploads outside the web root, retention purge, rate limits, required secrets, no secrets in the repo |

Browser runs (both servers up, Chrome installed):

```bash
python scripts/e2e_happy_path.py docs/screenshots/happy_path            # the whole journey on a Pixel 5 viewport
python scripts/e2e_phase5.py docs/screenshots/phase5 backend/udyam.db   # voice chat in Hindi, WhatsApp outbox, calling a High lead
python scripts/e2e_phase4.py docs/screenshots/phase4 backend/udyam.db   # late order -> auto-escalated -> agent rebooks (SLA_SCAN_INTERVAL_SEC=5)
python scripts/e2e_phase3.py docs/screenshots/phase3 backend/udyam.db   # consent, GSTIN, uploads: verified / re-upload / review
python scripts/check_design.py docs/DESIGN.md                           # design traceability
```

## Security

- **Logs:** every log record, from any logger including uvicorn's access log, has GSTIN, Udyam, PAN and phone numbers masked when it's created (`security/log_filter.py`). Lookup URLs log as `/kyc/gstin/19•••••••••1ZL`.
- **Documents:** encrypted per file with `APP_ENCRYPTION_KEY`, random file names, stored in `UPLOAD_DIR` outside anything served over HTTP. An hourly job (`python -m app.kyc.retention` by hand) deletes the files and OCR text 90 days after verification, or 30 days after an abandoned or withdrawn case. Cases still in review are never purged.
- **Rate limits:** OTP requests 3 per phone and 20 per IP per 10 minutes, 5 wrong codes per request; GSTIN/Udyam lookups 20 per user per 10 minutes. The limiter is in memory, which suits the single demo instance.
- **Secrets:** read from the environment only. With `APP_ENV` set to `demo` or `prod`, the API won't start on missing or built-in secrets. `.env` files are git-ignored; a test scans the code for leaked keys.
- **Demo caveat:** `OTP_MODE=mock` shows the code on screen so judges can log in. Use a real SMS provider and `OTP_MODE=sms` for anything beyond the demo.

## What's where

| Path | What |
|---|---|
| `backend/app/rules/engine.py` | Rules engine: `eligible_products`, `validate_bundle`, `build_bundle`. Re-exported as `app/advisor/rules.py` |
| `backend/app/advisor/service.py` | Advisor: 6 questions, profile JSON, rules engine, LLM guardrails, recommendation |
| `backend/app/advisor/llm/` | Provider interface. `template` (default, no key needed) and `openai_compatible` (`LLM_PROVIDER`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`) |
| `backend/app/pricing/` | `service.py` (pricing rule, see `docs/PRICING.md`) and `quote.py` (quotes, locks, accept → order) |
| `backend/app/orders/state_machine.py` | Order states and transitions, with an event written for every change |
| `backend/app/kyc/` | `ocr.py` (watermark, blur, deskew, Tesseract), `checks.py` (the 13 rules + verdict), `gstin.py`, `names.py`, `service.py` (consent, uploads, submit, results), `storage.py` (encrypted files) |
| `backend/app/escalations/` | `service.py` (create, least-loaded language-matched assignment, callback times), `sla.py` (the SLA scan and its background loop), `cases.py` (talk to a person, agent queue, full case context, resolutions) |
| `backend/app/orders/` | `state_machine.py`, `fulfilment.py` (auto-booking, expected dates), `tracker.py`, `simulator.py` |
| `frontend/src/app/order/[id]/` | Tracker (C9), consent (C6), KYC (C7) |
| `frontend/src/app/admin/` | Staff console: escalation queue (A4), case view (A5), order simulator (A7) |
| `backend/app/advisor/guards.py` | Rejects LLM output with product codes, unlisted products, wrong amounts, wrong language, or more than 3 sentences |
| `backend/app/i18n/` | Advisor questions, chips, product descriptions, KYC messages and the consent notice, in 8 languages |
| `backend/app/notifications/` | Templates in 8 languages, `service.py` (render, opt-in, send, dispatcher), `providers/` (twilio, mock) |
| `backend/app/voice/` | `providers.py` (browser, Sarvam, Bhashini), `brevity.py` (short spoken replies), `audio.py` (ffmpeg, in memory) |
| `backend/app/admin/` | `leads.py` (table, calls, notes), `metrics.py` (the 5 pilot metrics), `lead_sync.py` (app leads follow the advisor and order) |
| `frontend/src/app/admin/leads`, `/notifications` | Leads dashboard with metrics strip (A2), lead detail (A3), outbox (A6) |
| `frontend/messages/` | UI strings in 8 languages: hi, en, mr, ta, bn, kn, gu, te |
| `docs/` | Phase 1 report (PDF), `DESIGN.md`, 10-profile results, screenshots, `demo_script.md` (3-minute script), `privacy_security_note.md`/`.pdf` (1-page note) |
| `docs/architecture/` | Architecture diagram: PNG, SVG, draw.io, Mermaid, and `build_arch.py` that generates them |
| `showcase/site/` | The showcase website, ready to host: drag this folder onto app.netlify.com/drop or run `npx vercel --prod` inside it. Add `demo.mp4` here for the video |
| `showcase/build/` | Source for the showcase: edit `template.html` or `demo.py`, then `python showcase/build/build.py` writes `showcase/site/index.html` |
| `analysis/` | Phase 1 data analysis scripts and outputs |

**Change from `DESIGN.md`:** Bengali was added at the Phase 1 brief's request, so the app ships 8 languages: the design's 7 plus `bn`.
