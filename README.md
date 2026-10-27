# payment-webhook-false-failure

A reconstruction of a production bug I fixed in a WhatsApp sales agent: after paying through a
payment link, some customers got "❌ We could not process your payment" and, about a minute later,
"✅ Payment received". The payment itself was fine.

The original code is confidential, so this repo is written from scratch with the same stack
(FastAPI, SQLModel, Postgres) and a mock of the gateway that replays the callbacks we saw in
production. No code, names or data come from the original system. The git history follows the
real sequence of fixes, one commit per step, including the tests that were written red.

## Run it

```bash
make up          # api on :8000, gateway mock on :8001, Postgres
open http://localhost:8000
```

On the left is what the customer sees on WhatsApp; on the right, each callback the gateway sent
and what the webhook answered, the payment status and the emails. Write "I want to pay", open the
link, and choose how the gateway answers: `in review then approved`, `approved`, `expired` or
`declined`. The agent's messages carry a trace id; the webhook's do not.

To see the bug, run the same flow on the commit before the fix:

```bash
git checkout step-3 && make up     # in review then approved: ❌, then ✅ 5 s later
git checkout main && make up       # only ✅
```

Tests: `make test` (local, after `pip install -r api/requirements.txt`) or `make test-docker`.

## What happened

The gateway documents three outcomes (success, failure, pending), but in production it sends
numeric `status` / `status_detail` codes, and we never got the full table. For some payments it
sends two callbacks: `0/36` while its anti-fraud check runs, and `1/3` (approved) about 49 seconds
later. The handler treated anything that was not an approval as a failure.

| Tag | Commit | What it shows |
|---|---|---|
| `step-1` | feat | Original logic: not approved means failed. Tests check the database only. |
| `step-2` | fix | The payment stayed `failed` when the approval came later, so no receipt email. A later approval now wins. The test starts from `failed` and never looks at what the customer saw. |
| `step-3` | test (red) | Replays `0/36` then `1/3` and asserts the customer gets only ✅. Fails: the database ends `paid`, so every earlier test was green while the customer got ❌ first. |
| `step-4` | fix | In review changes nothing and sends nothing. |
| `step-5` | chore | A log line at every exit of the webhook, with the raw callback. A malformed callback answers 400 with its body in the log instead of failing silently. |
| `step-6` | test (red) | Those logs showed a second false ❌: an expired link arrives as `5/14`. |
| `step-7` | fix | Allowlist instead of blocklist. Only an explicit failure marks the payment failed and sends ❌; an expired link closes without a message; any other code is ignored and logged raw. |

How the first one was found: it showed up on a real test payment in production. In the LLM traces
the two messages did not exist, so they were not coming from the agent; the webhook logs had the
in-review callback.

Why the allowlist: fixing one code at a time does not end when you do not know all the codes.
A missing ❌ makes the customer ask; a false ❌ makes them think something went wrong with their
money. The cost is accepted on purpose: a decline that arrives under an unknown code reaches the
logs, not the customer (`test_unknown_code_is_ignored_and_logged_raw`).

## What this does not cover

- No end-to-end test from the callback to a message delivered on a real channel. The outbox table
  stands in for WhatsApp and email.
- Callbacks are not authenticated. A real gateway signs them, and the handler should verify that
  before anything else.
- No deduplication by transaction id: a callback the gateway retries is handled again. The status
  checks make that harmless for these flows, but it is not tested.
- Tests run on SQLite; the compose runs Postgres.
- The agent is a deterministic stand-in so the demo runs without API keys. In the original it was
  an LLM graph traced in Langfuse; here each agent turn writes a row to a `trace` table instead.

## Layout

```
api/app/webhook.py       the handler this repo is about
api/app/agent.py         agent stand-in: replies and payment links, one trace per turn
api/app/notifier.py      messages to the customer (outbox)
api/tests/               test_webhook.py has one test per step above
gateway-mock/app.py      the gateway: links, a pay page, and the callback scenarios
```
