# OPS Esports: Mythic Circle, Tournament Results & Announcements

FastAPI + PostgreSQL + React (Vite) + Tailwind. Built as standalone modules because no existing codebase was
available in the workspace. Each piece is structured so it can be merged into your repo (see "Merging").

## Layout
```
backend/   FastAPI app (app/models, services, routers, providers), Alembic migration, pytest suite
frontend/  React pages, components, Tailwind config
```

## Setup
```bash
# 1. Database
createdb ops_esports            # or any Postgres DB; set DATABASE_URL in backend/.env

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # set SECRET_KEY, CALLBACK_SECRET, PUBLIC_BASE_URL, DATABASE_URL
alembic upgrade head
python seed_admins.py           # create staff accounts (create TWO finance_admins)
uvicorn app.main:app --reload   # http://localhost:8000/docs

# 3. Frontend
cd ../frontend
npm install
npm run dev                     # http://localhost:5173 (proxies /api and /uploads)

# 4. Tests
cd ../backend && pytest -q      # 50 tests, SQLite in-memory, no network
```

## Design system
Teal-ink ground with a marigold accent; Bricolage Grotesque (display) and Instrument Sans (body), both self-hosted
through npm (`@fontsource-variable/*`), so no external font requests. Colours are CSS variables in `src/index.css`
(dark by default, light follows the system setting, with a manual toggle in the nav). The Mythic Circle is drawn as a
ring of seats (`components/SeatRing.jsx`) and only ever shows circle-level totals, never individual balances.
To rebrand, change the variables at the top of `index.css` and the font imports in `main.jsx`.

## Roles
| Role | Can |
|---|---|
| `clan_verifier` | Review clan evidence, approve/reject applicants |
| `finance_admin` | Periods, draws, cohorts, refunds, exceptions, payout approvals, Mythic/cohort-targeted notices, CMS |
| `results_admin` | Publish, archive and correct tournament results |
| `content_admin` | Draft results, create/publish announcements (everyone/verified/divisions) |
| `super_admin` | All of the above |

## Routes
Public: `/mythic-circle`, `/results`, `/results/:id`, `/announcements`, `/announcements/:slug`
Member: `/dashboard/mythic-circle`
Admin: `/admin/mythic-circle` (overview, registration periods, content), `/admin/mythic-circle/verification`,
`/cohorts`, `/contributions`, `/payouts`, `/admin/results`, `/admin/announcements`

## How the safety rules are enforced
- **Fixed plans**: `services/plans.py` holds the only two plans as immutable code constants (asserted to total KSh 7,000).
  Cohort creation accepts only size 7 or 10; terms are snapshotted onto the cohort at creation. The CMS endpoint uses a
  key whitelist and rejects any plan-term fields.
- **No fake confirmations**: initiating payment only creates an STK request. A contribution becomes `paid` solely in
  `handle_stk_callback`, which requires a known checkout id, ResultCode 0, an amount that matches, and a unique M-Pesa
  receipt. Mismatches create a reconciliation exception instead of crediting. Callback URLs carry a secret path token.
- **Ledger**: append-only `mythic_ledger`; reversals and refunds are new entries.
- **Payout gate** (`reconciliation()`): all periods paid, exactly KSh 7,000 per member, all reconciled, ledger equals
  contributions, ledger net covers the target, no open exceptions. Checked at request time **and again at execution**.
- **Two-person approval**: batch manifest is hashed and frozen; two *different* admins must approve that hash. Execution
  re-verifies the manifest against current member data, so a changed phone number or amount blocks the payout and
  requires a new batch. Payouts are submitted together; each is tracked independently; the cohort completes only when
  every payout has succeeded or been resolved with a documented settlement note.
- **Refunds**: refund = confirmed contributions actually paid (no penalties). Pre-activation cancellation, cohort
  cancellation and legal refunds cannot be denied through the admin path; other denials need a written reason.
- **Live money is off**: `DARAJA_ENV=sandbox` by default. Production calls are refused unless
  `LIVE_PAYMENTS_ENABLED=true`, `DARAJA_ENV=production` **and** `COMPLIANCE_SIGNOFF_REF` is set.
- **Content safety**: announcement HTML is sanitized server-side with a bleach allow-list; targeted notices to Mythic
  Circle members or cohorts require `finance_admin`; only `results_admin` can publish or correct results; every
  correction to published results is revisioned with a mandatory reason.
- **Fair draw**: random assignment using a recorded seed (stored on the period) so it can be re-verified; overflow goes to
  an ordered waiting list.

## Before real money moves (not done by this code)
1. Legal review: a pooled-savings scheme among members may need registration/licensing in Kenya (e.g. under CBK/SASRA
   or Capital Markets rules depending on structure). Get written advice and record its reference in `COMPLIANCE_SIGNOFF_REF`.
2. Safaricom Daraja production onboarding: Paybill/Till, B2C initiator and security credential, whitelisted callback URLs.
3. Publish the actual terms document and upload it under Policy documents; bump `TERMS_VERSION` when terms change
   (existing cohorts keep their snapshotted version).
4. Data protection: clan screenshots and phone numbers are personal data; register with the ODPC and set retention rules.
5. Run `mark_overdue` / `send_reminders` from a real scheduler if you run more than one API instance (the built-in
   loop in `main.py` is single-instance).
6. Integration-test the STK and B2C flows against the Daraja **sandbox** with your credentials.

## Merging into the existing OPS app
- Delete `routers/auth.py` and point `security.current_user` / `require_roles` at your auth and role system; map the role
  names above to yours. Replace `models/core.User` and the `Team` model with your existing ones (adjust the FKs).
- Mount the routers in your `main.py`, copy `models/` and `services/`, and generate your own Alembic revision from
  your Base (`0001_...` here is for the standalone schema).
- Copy `pages/`, `components/`, add the routes from `main.jsx`, and merge the Tailwind tokens.

## Clan applications and account approval

- Public `/join-clan`: no login required. Applicants submit an updated game name, clan tag,
  player ID, game, email, contact, join message, and a PNG/JPEG/WebP profile screenshot (maximum 5 MB).
- `/admin/clan-requests`: clan verifiers and super admins privately view evidence, filter requests,
  and approve or reject pending applications with an internal note. Contact applicants using their
  supplied contact details; this feature does not automatically send messages or create accounts.
- New public account registrations are pending and receive no login token. Review them at
  `/admin/accounts` to activate or reject access. Clan application approval and account approval
  are separate; neither automatically grants Mythic membership verification.
- On deployment, run `cd backend && alembic upgrade head` before starting the updated backend.
  Migration 0002 adds clan requests; 0003 adds account status and preserves existing accounts as active.
  Deploy the updated frontend alongside the backend.
