# Ring integration handoff for backend and frontend owners

This document records implementation requirements for the integration owners.
No backend or frontend source files were changed for this work.

## Current contract observed in the repository

- `POST /api/v1/events` accepts `source`, `external_event_id`, `event_type`,
  UTC `occurred_at`, optional `device_id`, and `metadata`. New events return
  `{ "event": ..., "is_duplicate": false }` (201); duplicate
  `(source, external_event_id)` returns the existing record and `true` (200).
- `GET /api/v1/events` filters by source, event type, inclusive start/end time,
  and paginates with `limit`/`offset`. It orders by `received_at DESC, id DESC`.
- `EventResponse` has no summary, rank, processing, or recording fields.
- The current API routes do not establish authenticated user/account ownership.
  The existing frontend event client consumes `EventListResponse`; its event
  types/cards do not render Ring summaries or playback.
- The existing event schema has no stable Ring media reference. Ring's media
  download call is based on device, timestamp, and duration; this code does not
  invent a recording ID or a public media URL.

## Nisha: backend persistence and API proposal

### Ownership and authorization gate

Before exposing a summary, retry, or recording, bind every event and Ring token
to the authenticated AccessAble user and the authorized Ring account/device.
Do not accept a frontend-supplied account ID as proof. The current unauthenticated
event routes are a production blocker for private Ring events, summaries, and
video access. Add auth/ownership to the route/repository/service as a coordinated
backend change before enabling customer records.

### Durable model

Create a durable Ring processing row keyed to the existing event:

```text
ring_event_processing
  id
  event_id                         FK events.id ON DELETE CASCADE
  owner_user_id                    FK authenticated user
  ring_account_id                  opaque Ring account ID; server only
  processing_version
  idempotency_key
  status                           pending | waiting_for_recording | retrieving |
                                   summarizing | completed | unavailable |
                                   failed | skipped
  error_category                   sanitized enum/string, never raw exception
  attempt_count
  next_attempt_at
  lease_owner
  lease_expires_at
  importance_json                  score, rule version, reason codes
  summary_json                     validated final result only
  recording_status                 available | not_ready | not_found |
                                   inaccessible | failed | unknown
  recording_started_at
  recording_duration_ms
  recording_mime_type
  provider_name / model_id
  created_at / updated_at / processed_at
  UNIQUE(event_id, processing_version)
  UNIQUE(idempotency_key)
```

Do not store Ring access/refresh tokens in this row, signed media URLs, raw
video, prompts, model chain-of-thought, or an invented Ring recording ID. Store
Ring tokens in the approved server-side secret/token store keyed to a Ring
account, encrypted at rest and refreshed server-side. Confirm video, frame,
summary, and token deletion/retention durations with product/privacy owners
before production; delete temporary media on success and failure and propagate
user deletion to derived summaries/jobs.

Indexes: `(owner_user_id, event_id)`, unique `(event_id, processing_version)`,
`(status, next_attempt_at, lease_expires_at)`, and `(owner_user_id, processed_at)`.
Keep the existing unique `(source, external_event_id)` event constraint.

### Transaction and worker boundaries

1. Insert/deduplicate the event and enqueue its processing row in the same DB
   transaction. A duplicate event must not create another processing row.
2. Claim eligible jobs atomically with a lease (`FOR UPDATE SKIP LOCKED` where
   supported; SQLite equivalent uses `BEGIN IMMEDIATE`). A worker crash must
   make an expired lease claimable again.
3. Commit `completed` and the validated summary in one transaction. Never mark
   complete before the summary is durable.
4. Persist retry state and `next_attempt_at` for Ring `425` and `429`; respect
   `Retry-After`. Bound other retries with backoff. Permanent authorization,
   unsupported, not-found, and validation failures should not loop indefinitely.
5. Keep webhook response within Ring's deadline. Webhook event persistence and
   durable enqueue happen synchronously; media retrieval and AI work happen in
   the durable worker, after event commit.

### Small compatible API extension

Keep the existing list response shape. Once the event row is ownership-scoped,
add an optional `summary` object to each event response with `status`,
`importance_score`, `reason_codes`, `text`, `observed_actions`,
`uncertainties`, `evidence_type`, `limitations`, `recording_status`, and
`processed_at`. Add `sort=time|importance` while preserving time sort as the
default. For day navigation, accept a local `day` plus IANA `timezone`, convert
to a half-open UTC interval `[start, end)` on the server, then paginate. Keep
existing `start_time`/`end_time` semantics for existing clients.

Add owner-checked endpoints:

- `GET /api/v1/events/{event_id}/summary`: return one event's processing and
  summary result; 404 when the event does not belong to the caller.
- `POST /api/v1/events/{event_id}/summary/retry`: retry only backend-authorized
  retryable states; deduplicate by the current processing version; return 202
  with the new state.
- `GET /api/v1/events/{event_id}/recording`: authenticate and check ownership,
  then retrieve/proxy the clip server-side with bounded streaming. Never return
  Ring bearer tokens or temporary redirect URLs to the browser. Until this
  endpoint exists, the frontend must not offer playback.

For the first API version, keep HTTP failures structured and safe: 401/403 for
authentication/ownership policy, 404 for absent or inaccessible event, 409 for
non-retryable processing state, 422 for invalid query/body, and 503/429 for a
temporarily unavailable worker/provider. Add contract tests for cross-user
access, duplicate ingestion/job creation, summary state response, retry
authorization, and recording proxy headers/stream limits.

## Ring account-link flow: documented facts and Portal blocker

Official Ring documentation describes two mutually exclusive methods. The
repository and Portal state do not show which AccessAble app method is
configured, so do not build one until Nisha/Rishi confirms the Portal method.

### One-way Ring-driven flow (documented default)

1. The Ring Portal registers public HTTPS **Token Exchange URL**, **Account Link
   URL**, and **Webhook URL**. Ring POSTs form data `code` and `client_id` to
   the Token Exchange URL. The code is single-use and expires after 60 seconds.
2. The backend exchanges it at
   `POST https://oauth.ring.com/oauth/token` as
   `application/x-www-form-urlencoded` with `grant_type=authorization_code`,
   `client_id`, `code`, and `client_secret`. The JSON response has
   `access_token`, `refresh_token`, `scope`, `expires_in`, and `token_type`.
3. It calls `GET https://api.amazonvision.com/v1/users/me` with the access
   token, stores the tokens plus Ring account ID as unclaimed, then returns 200.
   Ring says this callback is not retried after non-2xx, so it must be fast,
   idempotent, and durable.
4. Ring sends the user to the Account Link URL with `time` (epoch ms) and
   `nonce`. After mandatory AccessAble sign-in, match the nonce against the
   unclaimed Ring accounts using
   `HMAC-SHA256(hmac_key, "<time>:<ring_account_id>")`, URL-safe Base64 without
   padding, constant-time compare, and a 600-second freshness window.
5. With the matched user's token, call
   `POST https://api.amazonvision.com/v1/accounts/me/app-integrations` with
   JSON `{ "account_identifier": "<masked signed-in AccessAble identity>",
   "nonce": "<nonce>" }`. The response uses JSON:API envelope
   `data.attributes.status="awaiting"`.
6. Complete the mandatory transition with
   `PATCH https://api.amazonvision.com/v1/accounts/me/app-integrations` and
   JSON `{ "status": "completed" }` (optionally a masked account identifier).

### Partner-initiated OAuth option

Ring documents the authorization URL
`https://account.ring.com/account/integrations/partner-link/authorize`,
authorization-code flow, PKCE S256, CSRF `state`, HTTPS exact-match redirect
URI. The docs conflict on `scope`: the parameter table says `ava.v1:read`, while
its example URL says `ava`; use only the scope shown as approved in the Ring
Portal and get Ring clarification if the Portal does not resolve it. The
callback exchanges the code
through `POST https://oauth.ring.com/oauth/token` as form data:
`grant_type=authorization_code`, `code`, stored `code_verifier`, `client_id`,
and `client_secret`. Its JSON token response has `access_token`,
`refresh_token`, `scope`, `expires_in`, and `token_type`. Then call
`PATCH https://api.amazonvision.com/v1/accounts/me/app-integrations` with JSON
`{ "status": "completed", "account_identifier": "<masked signed-in identity>" }`;
this mode does not use the one-way nonce POST. Ring says this method is
invitation-only; the Portal must show that AccessAble is allowlisted. The
callback must validate PKCE S256 and CSRF `state`. Do not assume this is enabled.

For both modes, device access depends on the app's approved scopes and the
user's selected eligible Ring device/subscription. Portal app configuration,
staging testers, HTTPS callback/webhook URLs, and certification/review cannot
be verified from this repository. Ring's current API docs also require
`User-Agent: AppName/version` and a per-user/device UUID `Hardware_Id` on Ring
API requests; a cloud deployment may need a Ring-approved static egress IP to
avoid 406. These are implementation and operations prerequisites.

For media downloads, the worker passes through a single webhook
`component_ids` entry. Events naming multiple components are currently marked
unsupported by this local worker because the product needs an agreed policy for
fetching and combining one clip per camera module; it must not silently choose
one view.

## Nithish: frontend contract and UI

Continue using `GET /api/v1/events`; consume the additive per-event `summary`
object after backend support is deployed. Render a local-day timeline with
time/importance sorting, date navigation, device name, local time, type, score
and reason, AI-generated label, summary status, neutral observations and
uncertainty/limitations. Show playback only if `recording_status="available"`
and an authenticated same-origin recording endpoint is supplied by the backend.
Never render provider URLs. Show `pending`, `waiting_for_recording`,
`unavailable`, `failed`, and `skipped` honestly; show retry only when the
backend contract marks the current state retryable. Keyboard-accessible cards,
visible focus, readable contrast, responsive layout, loading and empty states
are required. Demo fixtures must visibly say synthetic.

Example additive event shape (illustrative contract proposal, not current API):

```json
{
  "id": 123,
  "source": "ring",
  "external_event_id": "request-id",
  "event_type": "motion",
  "occurred_at": "2026-10-22T10:00:00.123Z",
  "device_id": "ring-device-id",
  "metadata": {},
  "received_at": "2026-10-22T10:00:01Z",
  "summary": {
    "status": "completed",
    "importance_score": 20,
    "reason_codes": ["event_type:motion"],
    "text": "...",
    "observed_actions": [],
    "uncertainties": [],
    "evidence_type": "video",
    "limitations": [],
    "recording_status": "available",
    "processed_at": "2026-10-22T10:00:10Z"
  }
}
```

This example is a target contract only; no such API response currently exists.

## Verification gates before staging

- Nisha supplies authenticated owner-scoped storage, a durable worker, Ring
  account/token lifecycle, the agreed API, and the authorized playback path.
- Nithish adds compatible API types, event cards, date navigation, summary
  statuses, and accessible playback gating.
- Rishi confirms the Ring Portal account-link method, exact callback URLs,
  configured scopes, staging status, eligible test account/device and media
  approval; confirm whether Ring Partner-Initiated OAuth allowlisting applies.
- Configure approved server secrets only in the deployment secret manager.
  Provide a public HTTPS staging backend, required API headers, and approved
  static egress IP if Ring requires it.
- Keep AI disabled until the data-processing/privacy approval and retention
  decision are recorded. Exercise only a synthetic fixture until then.
- Verify one real signed staging webhook persisted once, a recording request
  succeeded for an eligible device, and an authorized user sees the resulting
  summary/playback state through the final API/UI. None of those real checks
  have happened yet.
