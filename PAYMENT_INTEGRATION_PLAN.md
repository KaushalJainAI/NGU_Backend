# Payment Gateway Integration Plan — Razorpay + COD

**Project:** NGU (Nidhi Masala) backend
**Scope:** Razorpay online payments + Cash on Delivery (COD). Stripe stays modeled but unwired.
**Status:** Plan only — no code written yet.
**Author:** Claude
**Date:** 2026-06-19

---

## 1. Where we stand today

Already in place (no work needed):

| Item | Location |
|------|----------|
| `razorpay==2.0.0` + `stripe==13.2.0` pinned | `requirements.txt:24-25` |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` config stubs | `spices_backend/settings.py:372-373` |
| `Payment` model (one-to-one with `Order`, `stripe`/`razorpay`/`cod` gateways, `transaction_details` JSON, `unique` `payment_id`) | `payments/models.py:7` |
| `PaymentMethod` model (saved UPI/card/netbanking/wallet, only last-4 + token stored) | `payments/models.py:34` |
| `Order` model with `payment_method` (`COD`/`ONLINE`/`razorpay`) + `payment_status` | `orders/models.py:8` |
| Order creation w/ cart→order, stock decrement, coupon, atomic txn | `orders/views.py:138` |

**The gap:** `payments/views.py` only does CRUD on saved `PaymentMethod`s. There is:
- ❌ No endpoint to create a Razorpay order
- ❌ No signature verification
- ❌ No webhook handler
- ❌ No link between a placed `Order` and an actual paid transaction

So checkout → paid does not exist yet. The `Payment` row is never created.

---

## 1b. System-fit reconciliation (verified against the codebase — read first)

Four things about *this* codebase change how the plan must be built. These are verified, not assumed.

1. **Order-level `payment_method` is `{'COD','ONLINE'}` only — there is no `'razorpay'` choice.**
   `OrderCreateSerializer.payment_method` (`orders/serializers.py:9`) is `ChoiceField(choices=['COD','ONLINE'])`.
   The model's `PAYMENT_METHOD_CHOICES` (`orders/models.py:20`) *also* lists `stripe`/`razorpay`, but the create API can't set them.
   → **Decision:** keep the gateway distinction on the **`Payment`** model (`payment_gateway='razorpay'`). The **`Order`** stays `payment_method='ONLINE'` for all gateway payments. Every place this plan said "order with `payment_method='razorpay'`" means **`payment_method='ONLINE'` + `Payment.payment_gateway='razorpay'`**. No serializer change needed.

2. **`Order.payment_status` is a free-text `CharField`, default `'pending'`, with no `choices`** (`orders/models.py:37`). Only `'pending'` is currently used; the frontend/assistant reads it (`assistant/tools.py:169`).
   → **Decision:** define and standardise the vocabulary now: **`pending` → `paid` → `failed` → `refunded`**. Recommend adding `choices` + a one-line migration so values can't drift. The plan's `'paid'`/`'failed'` are *new* values this work introduces.

3. **Celery is a dependency but is NOT operationally wired.** `celery==5.5.3` is installed and `settings.py:506-511` has serializer config, but **`CELERY_BROKER_URL`/`RESULT_BACKEND` are commented out**, there is **no `spices_backend/celery.py` app module**, and no worker/beat runs. Redis *is* available (`django_redis`).
   → **Decision:** the L3 reconciliation job (§7) has a **prerequisite**: either (a) stand up Celery — add `celery.py`, uncomment the Redis broker, run a worker + `celery beat`; or (b) ship L3 as a **Django management command** (`python manage.py reconcile_payments`) driven by an external scheduler (Windows Task Scheduler in dev / cron in prod). **(b) is the lower-risk start** and needs no new infra. Pick one before building §7.4/§8 step 8.

4. **A manual UPI collection flow already exists and is live** — `ReceivableAccount` (`admin_panel/models.py:6`) + `PaymentAccountView` (`admin_panel/views.py:58`) return the store's static UPI ID, and `admin_panel/utils.py` builds a `upi://pay?pa=…` QR. Customers currently pay the store's UPI directly and admin reconciles by hand.
   → **Decision:** Razorpay is a **new, parallel** method, not a replacement (yet). `ONLINE` will route to Razorpay; the static-UPI/QR path can remain as a fallback or be retired later. Don't delete `ReceivableAccount` as part of this work. Note the naming overlap: this static flow is unrelated to the `PaymentMethod` model (saved customer methods) and to the new `Payment` gateway rows — keep the three concepts distinct in code review.

---

## 2. Design decisions

1. **Razorpay-first.** INR, domestic customers. Native UPI/cards/netbanking/wallets. Stripe deferred (kept in model choices, not wired).
2. **Order is created first, then paid.** Reuse the existing `OrderViewSet.create` flow unchanged. After an order exists with `payment_method='ONLINE'` (gateway recorded on the `Payment` row, see §1b.1), the client requests a Razorpay order against it.
3. **Webhook is the source of truth**, not the browser callback. The client callback gives fast UX feedback; the webhook reconciles reality (user may close the tab mid-payment).
4. **Amount is always computed server-side** from `Order.total_amount`. The client never sends an amount. Razorpay works in **paise** → `int(order.total_amount * 100)`.
5. **Idempotency** keyed on `Payment.payment_id` (already `unique=True`). Webhook + callback may both fire; neither double-applies.
6. **COD needs no gateway call.** Order placed as `payment_status='pending'`, a `Payment` row with `payment_gateway='cod'` / `status='pending'`, marked completed on delivery.

---

## 3. Order / payment state machine

```
COD path:
  place order ─► Order.payment_status = 'pending'
              ─► Payment(gateway='cod', status='pending')
              ─► (on delivery) Payment.status='completed', Order.payment_status='paid'

Razorpay path:
  place order ─► Order.payment_status = 'pending'  (no Payment row yet)
  create-order ─► razorpay.Order.create() ─► Payment(gateway='razorpay',
                  payment_id=razorpay_order_id, status='pending')
  user pays in Razorpay Checkout (frontend)
  verify  ─► verify signature ─► Payment.status='completed',
             Order.payment_status='paid', Order.status='confirmed'
  webhook ─► payment.captured  ─► same as verify (idempotent)
          ─► payment.failed    ─► Payment.status='failed'
```

> **Note on `Payment.payment_id`:** during the Razorpay flow this initially holds the
> `razorpay_order_id` (created before payment), then we also persist the
> `razorpay_payment_id` into `transaction_details`. Decide a convention and keep it
> consistent (recommended: `payment_id` = razorpay_order_id, since it exists earliest
> and is unique per order).

---

## 4. New endpoints

All under `payments/`. Register a `PaymentViewSet` (or plain APIViews) in `spices_backend/urls.py`.

### 4.1 `POST /api/payments/create-order/`
- **Auth:** required. **Input:** `{ "order_id": <Order.id> }`
- Loads the user's `Order`, asserts it belongs to them and is unpaid.
- Computes `amount = int(order.total_amount * 100)`.
- Calls `razorpay.Order.create({amount, currency:'INR', receipt:f'order_{order.id}', payment_capture:1})`.
- Creates/updates `Payment(order=order, payment_gateway='razorpay', payment_id=rzp_order['id'], amount=order.total_amount, status='pending')`.
- **Returns:** `{ razorpay_order_id, razorpay_key_id (public), amount, currency, order_id }`.

### 4.2 `POST /api/payments/verify/`
- **Auth:** required. **Input:** `{ razorpay_order_id, razorpay_payment_id, razorpay_signature }`
- Verifies HMAC-SHA256 signature via `client.utility.verify_payment_signature(...)`. **Reject if invalid.**
- On success (idempotent): `Payment.status='completed'`, store `razorpay_payment_id` in `transaction_details`, `Order.payment_status='paid'`, `Order.status='confirmed'`.
- **Returns:** `{ success: true, order_id }`.
- ⚠️ Treat this as UX confirmation only — do not ship product on this alone; webhook reconciles.

### 4.3 `POST /api/payments/webhook/`
- **Auth:** none (Razorpay calls it) — but **verify the webhook signature** using `RAZORPAY_WEBHOOK_SECRET` against the raw request body. `csrf_exempt`.
- Handle events: `payment.captured` → mark paid (idempotent); `payment.failed` → mark failed.
- Always return `200` quickly once verified; do heavy work async (Celery already available) if needed.
- Idempotent on `payment_id` / event id — a re-delivered webhook must not double-apply.

### 4.4 COD (extend existing order flow)
- When an order is placed with `payment_method='COD'`, create a `Payment(gateway='cod', status='pending')` alongside it.
- Add `POST /api/payments/{id}/mark-cod-paid/` (staff-only) or hook into the order "delivered" transition to flip `Payment.status='completed'` + `Order.payment_status='paid'`.

---

## 5. Files to add / change

| File | Change |
|------|--------|
| `payments/gateway.py` *(new)* | Thin Razorpay client factory: `get_razorpay_client()` reading keys from settings. Keeps SDK calls in one place. |
| `payments/views.py` | Add `create-order`, `verify`, `webhook`, COD-mark views. Keep existing `PaymentMethodViewSet`. |
| `payments/serializers.py` | Add `CreateOrderSerializer`, `VerifyPaymentSerializer` (input validation). |
| `payments/urls.py` *(new, optional)* | Route the new endpoints; include from main `urls.py`. |
| `spices_backend/urls.py` | Register payment routes (`create-order`, `verify`, `webhook`). |
| `spices_backend/settings.py` | Add `RAZORPAY_WEBHOOK_SECRET = config('RAZORPAY_WEBHOOK_SECRET', default='')`. |
| `payments/tests.py` | Tests: signature verify (valid/invalid), idempotent webhook, COD path, amount-from-server. |
| `.env` / deployment secrets | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` (test keys first). |

No model migration strictly required (Payment/Order already support this). Optional: add a `razorpay_payment_id` field to `Payment` instead of stuffing it in `transaction_details` — cleaner querying, costs one migration.

---

## 6. Frontend touchpoints (nidhi-brand-forge)

1. On checkout with online payment: `POST /api/payments/create-order/` → receive `razorpay_order_id` + `razorpay_key_id`.
2. Load Razorpay Checkout script, open with that order id + key.
3. On Checkout success callback → `POST /api/payments/verify/` with the three returned fields.
4. Show success on verify `200`; show pending/failed otherwise.
5. COD: just place the order; show "Pay on delivery" confirmation.

(Frontend work is out of scope for this backend plan but listed so the contract is clear.)

---

## 7. Resilience — the core of a robust integration

> **Governing principle:** the money moves between the customer's browser and
> Razorpay. **Our server is never in the money path.** Our database is a *cache* of
> Razorpay's truth, not the source of it. Downtime, crashes and races can only make us
> temporarily **stale** — never **wrong** — provided every state transition is
> idempotent and reconcilable. Everything below follows from that one idea.

Razorpay's webhook contract (from official docs) that drives this design:
- **At-least-once delivery** — the same event can arrive multiple times.
- **No ordering guarantee** — `payment.failed` can arrive *before* `payment.captured`.
- **5-second ACK window** — you must return `2xx` within 5s or it's treated as failed.
- **Retries with exponential backoff for 24h**, then the webhook is auto-disabled and an alert email is sent.
- Each delivery carries a unique **`x-razorpay-event-id`** header — the idempotency key.

### 7.1 The three-layer reconciliation model (defence in depth)

No single mechanism is trusted. State converges through three independent layers:

| Layer | Trigger | Catches | Mechanism |
|-------|---------|---------|-----------|
| **L1 — Client callback** | Browser returns from Checkout → `POST /verify/` | Happy path, instant UX | Signature verify → mark paid |
| **L2 — Webhook** | Razorpay server → `POST /webhook/` (retried 24h) | Tab closed, callback lost, L1 server blip | Signature + event-id idempotency → mark paid |
| **L3 — Active reconciliation** | Celery beat job, every ~15 min + nightly sweep | Webhook lost to >24h outage, missed events, abandoned orders | Poll `client.order.fetch`/`payment.fetch` for stuck `pending` |

L3 is the backstop that makes the whole thing robust: even if L1 **and** L2 both fail, the system self-heals on the next poll. Build all three.

### 7.2 Concurrency & idempotency (races)

Multiple actors can touch one payment simultaneously: L1 callback + L2 webhook, webhook redelivery, double-clicks. The rule: **every transition is guarded by a row lock + a status check + a recorded event id.**

```python
# verify and webhook BOTH funnel through one idempotent function
def mark_payment_captured(razorpay_order_id, razorpay_payment_id, event_id=None):
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(payment_id=razorpay_order_id)

        # Idempotency guard — second caller (race or redelivery) is a no-op
        if payment.status in ('completed', 'refunded'):
            return payment
        if event_id and ProcessedWebhookEvent.objects.filter(event_id=event_id).exists():
            return payment

        payment.status = 'completed'
        payment.transaction_details = {**(payment.transaction_details or {}),
                                       'razorpay_payment_id': razorpay_payment_id}
        payment.save(update_fields=['status', 'transaction_details', 'updated_at'])

        order = payment.order            # already locked via FK? lock explicitly if needed
        order.payment_status = 'paid'
        order.status = 'confirmed'
        order.save(update_fields=['payment_status', 'status', 'updated_at'])

        if event_id:
            ProcessedWebhookEvent.objects.create(event_id=event_id)

        # side-effects exactly once, inside the lock
        transaction.on_commit(lambda: send_order_confirmation(order.id))
```

Key points:
- `select_for_update()` serialises the L1/L2 race; the loser sees `completed` and no-ops. The `unique=True` on `payment_id` prevents duplicate *rows* but does **not** prevent a lost update — the lock does.
- **Out-of-order safety:** never downgrade a terminal state. `payment.failed` arriving after `payment.captured` must not flip a paid order back to failed. Only apply `failed` if status is still `pending`.
- **Side-effects via `transaction.on_commit`** so a rolled-back txn never emails a customer about a payment that didn't persist.

### 7.3 Server crash / downtime matrix

| When the server dies | What happens to the money | Recovery |
|----------------------|---------------------------|----------|
| During `create-order`, before Razorpay order made | Nothing charged | Client retries; `get_or_create` returns existing pending Payment |
| After Razorpay order made, before `Payment` row commits | Nothing charged; orphan RZP order expires | `transaction.atomic()` rolls back cleanly — no partial row |
| **While user pays in Checkout** | **Captured by Razorpay regardless** | L1 callback fails (cosmetic) → **L2 webhook reconciles on retry** |
| During `/verify/` processing | Captured | Webhook + L3 reconcile; atomic txn means no half-update |
| During webhook processing, before ACK | Captured | **Must not 200 early** → Razorpay redelivers → idempotent no-op |
| Down > 24h (webhook disabled) | Captured | **L3 polling job** fetches truth from Razorpay API |

**The ACK-ordering rule (critical):** return `200` to the webhook **only after** the DB transaction commits. ACK-before-commit + crash = silently lost event with no retry. It is always safer to crash and be redelivered than to ACK early.

**The 5-second rule:** signature-verify and persist a minimal record fast, then ACK; push slow side-effects (email, analytics, invoice PDF) to a background worker (Celery once wired — §1b.3; until then keep the handler's work minimal so even a synchronous path stays well under 5s, and let L3 backfill anything skipped). Never do blocking I/O before the ACK.

### 7.4 The abandoned-order stock leak (silent inventory bug)

Stock is decremented at order creation (`orders/views.py:293-301`), **before** payment. An online order abandoned at Checkout therefore holds stock at `payment_status='pending'` forever. The L3 Celery job fixes this and does double duty:

```
for each Order where payment_method='ONLINE' and payment_status='pending'
                     and created_at < now() - TTL (e.g. 30 min):
                     # (gateway is on the Payment row; Order.payment_method is 'ONLINE', see §1b.1)
    truth = razorpay.order.fetch(payment.payment_id)   # ask the source of truth
    if truth shows a captured payment:  mark paid (a webhook was missed)  → L3 saves L2
    else:                               cancel order + restore stock (reuse Order.cancel logic)
```

COD orders are exempt (no online payment expected). Choose TTL ≥ Razorpay order validity.

### 7.5 Money-specific correctness

- **Amount integrity:** always `int(order.total_amount * 100)` (paise) computed server-side. Never accept an amount from the client. Verify the webhook's `amount` matches the stored `Payment.amount`; mismatch → flag, don't auto-fulfil.
- **Currency** pinned to `INR`.
- **Double-payment:** if a `Payment` is already `completed`, reject/refund a second capture for the same order rather than fulfilling twice.
- **Refunds:** `status='refunded'` already modeled. Handle `refund.processed` webhook; restore stock per business rule. (Phase 2 — see open questions.)
- **Reconciliation report:** nightly job diffs our `completed` payments against Razorpay settlement/transactions for the day; alert on any mismatch. This is the human-visible safety net.

### 7.6 Transparency — making every issue visible (customer + admin)

> Correctness that nobody can see is not assurance. **Every payment must have a truthful,
> queryable state and an immutable history; every anomaly must raise a durable record AND a
> notification — never just a log line.** Three mechanisms deliver this.

#### (a) The audit trail — `PaymentEvent` (single source of "what happened")

Add an append-only `PaymentEvent(payment FK, event_type, source, from_status, to_status, message, raw_payload JSON, created_at)`. **Every** transition writes one row, inside the same `transaction.atomic()` as the state change (so the history can never disagree with the state):

| `source` | Examples of `event_type` |
|----------|--------------------------|
| `client` | `order_created`, `verify_succeeded`, `verify_signature_failed` |
| `webhook` | `captured`, `failed`, `signature_invalid`, `duplicate_ignored`, `out_of_order_ignored` |
| `reconcile` | `recovered_paid`, `auto_cancelled`, `amount_mismatch`, `stuck_flagged` |
| `admin` | `manual_marked_paid`, `manual_refund`, `note_added` |

This is what makes an issue *explainable* after the fact: anyone can read the full lifecycle of a single payment — including the raw Razorpay payloads — in one place. It is also the evidence trail for disputes/chargebacks.

#### (b) Customer-facing transparency

- **Payment state is always surfaced on the order page**, mapped from `Order.payment_status`:
  `pending` → "Payment pending", `processing`* → "Confirming your payment…", `paid` → "Payment received", `failed` → "Payment failed — retry".
  *(\*optional intermediate `processing` state for the "paid at Razorpay but our `/verify/` hasn't confirmed yet" window — see §1b.2 vocabulary.)*
- **Never show a false failure.** The "paid but verify callback failed" case shows **"Confirming your payment…"**, not "failed". A short frontend poll on `GET /api/payments/status/?order_id=` (or order detail) flips it to "Payment received" once the webhook lands. This single rule prevents the worst customer experience: being told to pay again for an order you already paid.
- **Proactive notifications** on every terminal transition, reusing the existing email infra (you already send password-reset email): payment received, payment failed (+ retry link), refund processed. Optionally SMS for failures.
- **A reference the customer can quote** — show `razorpay_payment_id` / order number on the confirmation and in emails, so a support conversation starts with an ID, not "my payment didn't work."

#### (c) Admin-facing transparency + active alerting

- **Exceptions queue** — the highest-value piece. A filtered admin view (extend `payments/admin.py` and/or `DashboardViewSet`) listing payments **needing human attention**, never buried in normal traffic:
  - stuck `pending` past TTL, `amount_mismatch`, `signature_invalid` (possible fraud/misconfig), `recovered_paid` (a webhook was missed — worth knowing), Razorpay webhook **auto-disabled** (the 24h-failure email condition), nightly settlement diff mismatches.
- **Push alerts, don't wait for someone to look.** The reconciliation job and webhook handler **email the admin** (and/or post to a Slack/webhook URL) the moment any exception is recorded — same email backend you already use. Silence = healthy; an alert = a named payment + reason + link.
- **Rich Django admin** on `Payment` + inline `PaymentEvent` history: status, gateway, amount, `razorpay_payment_id`, `failure_reason`, full timeline. Filters by status/gateway/date already partly exist for orders (`orders/admin.py:28`).
- **Admin actions, audited:** "mark COD paid", "mark as manually reconciled", "initiate refund" — each writes a `PaymentEvent(source='admin')` so manual interventions are as traceable as automated ones.
- **A daily digest** (even when nothing is wrong): "N payments, ₹X captured, M reconciled by job, K exceptions open." Turns "is the payment system OK?" into a glance.

**Net effect:** for any troubled transaction, the customer sees an honest, non-alarming status and a way forward; the admin gets pushed an alert with the exact payment, the reason, and the full event history to act on. Nothing fails silently.

---

## 8. Security checklist (must-haves)

- [ ] Amount derived from `Order.total_amount` server-side — never from request body.
- [ ] Signature verified on **both** `/verify/` and `/webhook/` before marking paid.
- [ ] Webhook signature computed over the **raw request body bytes** (not re-serialised JSON) using HMAC-SHA256 with `RAZORPAY_WEBHOOK_SECRET`.
- [ ] Idempotency on **`x-razorpay-event-id`** (recorded in a `ProcessedWebhookEvent` table) **and** a status guard — webhook + callback + redelivery all safe.
- [ ] Never downgrade a terminal payment state (out-of-order event safety).
- [ ] `/webhook/` returns `2xx` within **5 seconds**; heavy work deferred to Celery.
- [ ] ACK the webhook **only after** DB commit (`transaction.on_commit` for side-effects).
- [ ] Keys via `python-decouple`, never committed. Test keys until go-live.
- [ ] `/webhook/` is `csrf_exempt` but signature-gated; reject unverified with `400`.
- [ ] TLS 1.2+ on the webhook endpoint; optionally allowlist Razorpay's webhook source IPs.
- [ ] Order ownership enforced (`order.user == request.user`) on create-order/verify.
- [ ] No raw card data ever touches the backend (Razorpay Checkout handles PCI scope).
- [ ] Verify webhook `amount`/`currency` match the stored `Payment` before fulfilling.

---

## 9. New model needs (for the resilience layer)

| Addition | Purpose |
|----------|---------|
| `ProcessedWebhookEvent(event_id unique, event_type, received_at)` *(new model)* | Idempotency ledger keyed on `x-razorpay-event-id`. One migration. |
| `Payment.razorpay_payment_id` *(optional field)* | First-class column instead of digging in `transaction_details` JSON — easier reconciliation queries. One migration. |
| `Payment.failure_reason` / `failure_code` *(optional)* | Store `payment.failed` error code for support + retry-UX. |
| `Order.payment_status` add `choices=['pending','paid','failed','refunded']` (+ optional `processing`) | Lock the vocabulary this work introduces (currently free text, see §1b.2). One migration; no data change. |
| `PaymentEvent(payment FK, event_type, source, from_status, to_status, message, raw_payload, created_at)` *(new model)* | Append-only audit trail powering all of §7.6 (admin history, exceptions, dispute evidence). One migration. |

---

## 10. Suggested build order

0. **Decide the §1b prerequisites:** Celery-vs-management-command for L3 (recommend management command first), and add `Order.payment_status` choices migration.
1. Add `RAZORPAY_WEBHOOK_SECRET` to settings; put test keys in `.env`.
2. `payments/gateway.py` — client factory.
3. Add `ProcessedWebhookEvent` + `PaymentEvent` models + `payment_status` choices migration. Write a `PaymentEvent` row inside every state transition from the start (§7.6a).
4. `create-order` endpoint + serializer (with `get_or_create` guard) → test in Razorpay test mode. Order is `payment_method='ONLINE'`; gateway lives on `Payment`.
5. `verify` endpoint → routes through the shared `mark_payment_captured()` idempotent function.
6. `webhook` endpoint → signature + event-id idempotency, fast ACK, deferred side-effects.
7. COD path wiring into order/delivery flow (`payment_method='COD'` → `Payment(gateway='cod')`).
8. **L3 reconciliation** — as a `manage.py reconcile_payments` command (or Celery beat task if §1b.3 chose Celery): stuck-order reconciliation + stock restoration + nightly settlement diff. Wire to scheduler.
9. **Transparency layer (§7.6):** customer `GET /payments/status/` endpoint; admin exceptions queue + rich `Payment`/`PaymentEvent` admin; alert email on exceptions; customer notification emails (reuse existing email backend); optional daily digest.
10. Tests (`payments/tests.py`) — see §11.
11. Wire frontend Checkout (handle the "paid but verify failed → show *processing*, not *failed*" UX). Keep the existing `ReceivableAccount` UPI/QR path until Razorpay is proven.
12. Switch to live keys + register production webhook URL & subscribe events in Razorpay dashboard.

**Events to subscribe in dashboard:** `payment.captured`, `payment.failed`, `order.paid`, and (phase 2) `refund.processed`.

---

## 11. Test matrix (what "robust" must prove)

- [ ] Valid signature accepted; tampered/invalid signature rejected (verify + webhook).
- [ ] Duplicate webhook (same `event_id`) → second is a no-op, no double email.
- [ ] L1 callback and L2 webhook racing → exactly one set of side-effects.
- [ ] Out-of-order: `payment.failed` after `payment.captured` does not un-pay the order.
- [ ] Amount tampering in request body is ignored (server uses `Order.total_amount`).
- [ ] Webhook handler returns 2xx in <5s with side-effects deferred.
- [ ] Crash simulated between commit and ACK → redelivery reconciles, no dup.
- [ ] L3 job marks a paid-but-webhook-missed order as paid.
- [ ] L3 job cancels a truly-abandoned order and restores stock.
- [ ] COD order: Payment row created `pending`, flips on delivery.
- [ ] Every state transition writes exactly one `PaymentEvent` in the same transaction (history never disagrees with state).
- [ ] "Paid but verify failed" surfaces as *processing*/*confirming*, never *failed*, then flips to *paid* on webhook.
- [ ] Each exception type (`amount_mismatch`, `signature_invalid`, `stuck_flagged`, `recovered_paid`) lands in the admin exceptions queue **and** triggers an alert email.
- [ ] Customer notification email sent on paid / failed / refunded.

---

## 12. Open questions before coding

- **`payment_id` convention:** store `razorpay_order_id` as the canonical `payment_id` (recommended — exists earliest, unique per order) vs `razorpay_payment_id`. Affects idempotency keys.
- **COD "paid" trigger:** flip on the order `delivered` status transition, or a separate staff action?
- **Refund flow:** in scope now or phase 2? (`status='refunded'` already modeled.)
- **Stuck-order TTL:** 30 min default — confirm against Razorpay order validity and your fulfilment SLA.
- **`razorpay_payment_id` as a column** vs reuse `transaction_details` JSON.

---

## 13. Sources / references

- [Razorpay — Webhooks Best Practices](https://razorpay.com/docs/webhooks/best-practices/) — 5s ACK, at-least-once, `x-razorpay-event-id`, 24h backoff, TLS/IP.
- [Razorpay — Validate & Test Webhooks](https://razorpay.com/docs/webhooks/validate-test/) — HMAC-SHA256 over raw body, signature verification.
- [Razorpay — About Webhooks](https://razorpay.com/docs/webhooks/) and [Webhook FAQs](https://razorpay.com/docs/webhooks/faqs/) — retry/disable behaviour, ordering.
- [Razorpay — Payment Gateway API Integration Guide](https://razorpay.com/blog/payment-gateway-api-integration-guide/) — failure handling, reconciliation.
- [Payment Webhook Best Practices (apidog)](https://apidog.com/blog/payment-webhook-best-practices/) — idempotency & reconciliation patterns.
- [Unresponsive Payments: Retry & Fallback (Medium)](https://medium.com/@akshayp344/unresponsive-payments-handling-on-razorpay-platform-with-retry-and-fallback-mechanism-3f74e0f3b54d) — polling fallback design.
