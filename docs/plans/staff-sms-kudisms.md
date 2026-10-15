# Plan: management sends SMS to staff (KudiSMS)

**Status: planned, NOT started.** Build only when the owner says so.

## Decisions already made
- **Direct to KudiSMS.** The school portal calls KudiSMS itself with the school's sender ID. It does **not** go through the Reachly bulk SMS platform (`bulk-backend` / `bulk-frontend`).
- **Audience for now: staff only.** Parents and students come later (see Phase 2).
- The school pays KudiSMS directly (tops up its KudiSMS balance there). No wallet or pricing inside the portal.
- **Sender ID: `Laazeere`** (8 characters, under the 11-character limit).
- **Route: DND** (KudiSMS gateway 2), so staff on Nigeria's do-not-disturb list still receive messages.
- **Account:** the owner's own KudiSMS account, which holds the sender ID. Its API key goes in the server's environment.
- **Who can send: management only** (management and admin roles). Teachers, students and parents get no access to the page or the API.
- The KudiSMS API key lives only in the server's environment, never in the frontend, the same way the Flutterwave keys do.

## Still to decide before building
1. **How many staff have a phone number saved.** The page will list those without one, so this can be fixed.

Confirm on the KudiSMS dashboard that `Laazeere` is approved and works on the DND route. The first test send checks this too.

## How it will look
Management sidebar → **Send SMS**:
1. **Who:** all staff, one or more designations (e.g. Teacher, Cashier), or hand-picked people.
2. **Message:** a box with a live counter: characters, SMS parts (160 characters each, or 70 if the message has certain special characters), recipients and total SMS units.
3. **Preview:** shows how many will get it and lists anyone without a valid number.
4. **Send** → a confirm box (count and the start of the message) → a result: sent / failed.
5. **History:** date, sent by, message, sent / failed; click one to see each person's status.
6. A **KudiSMS balance** chip at the top, with a low-balance warning.

## Backend (raddai-backend, cPanel + MySQL)
- **Settings (env on cPanel):** `KUDISMS_API_KEY`, `KUDISMS_BASE_URL` (default `https://my.kudisms.net`), `KUDISMS_SENDER_ID` (`Laazeere`), `KUDISMS_ROUTE` (`dnd`), and `KUDISMS_DRY_RUN=1` for local development so nothing real is sent.
- **Client** (`core/kudisms.py`), ported from `bulk-backend/integrations/kudisms.py`:
  - Requests must be sent as multipart/form-data (form-urlencoded returns "missing parameters").
  - 100 numbers per call (KudiSMS error 108); 30 second timeout.
  - `send_sms`, `get_balance`, clear errors.
- **Phone cleaning:** spaces and dashes removed; `+234…`, `234…` and `0…` accepted; one standard form; duplicates removed; invalid numbers reported, never silently skipped. The exact format KudiSMS wants is confirmed with one real test send on day one.
- **Models** (additive migration only):
  - `SMSBatch`: sent_by, message, sender_id, route, parts, recipient_count, sent_count, failed_count, status (sent / partial / failed), provider_error, request_id (unique, to stop a double click sending twice), created_at.
  - `SMSRecipient`: batch, staff (nullable), name at the time, phone, status, provider message id.
- **API** (management and admin only, same permission as the other management endpoints):
  - `GET  /api/sms/balance/`
  - `POST /api/sms/preview/` → recipients, people without a number, parts, units
  - `POST /api/sms/send/` → creates the batch and sends in chunks of 100. A staff list is small, so it finishes inside one request; each chunk is protected separately, so one failure does not lose the rest.
  - `GET  /api/sms/history/` and `GET /api/sms/history/<id>/`
- **Guard rails:** message length cap, a send limit per user per hour, a send log kept for every message (who, what, when, to whom), and a warning on code-style wording ("verification code"), because KudiSMS blocks that on the normal route.
- **Tests** (KudiSMS is always mocked, no real sends): number cleaning, audience choosing, chunking at 100 and 101, a partly failed send, a double click, and permissions (staff, student and parent get 403).

## Frontend (raddai-lms)
- New page `/management/sms`, linked in the sidebar under Management, in the same style as the Staff page.
- `smsApi` in `lib/api.ts`, plus the types.
- Browser check on desktop and phone before it goes live.

## Going live
1. Add the `KUDISMS_*` variables on cPanel.
2. `git pull origin master`, `python manage.py migrate`, Restart (the same steps as the backend deploys).
3. The frontend deploys itself on Vercel.
4. First test: one real SMS to the owner's own number. Check it on the KudiSMS dashboard before sending to staff.

The school's cPanel server already makes outgoing calls (the Flutterwave check), so reaching KudiSMS should work. Confirm with the test send.

## Phase 2 (later, not part of the first build)
- Parents and students as recipients, by class. About 1,100 numbers, so sends run in the background in batches.
- Message templates (fee reminder, closing date).
- Scheduled sends.
- Delivery reports from KudiSMS (a callback that marks delivered / undelivered).
- Automatic alerts, such as absence messages once fingerprint attendance exists.
