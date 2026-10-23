# AccessAble Ring integration

## Current scope

This package contains the Ring event adapter plus an **explicit, opt-in** video
retrieval and summary foundation. The webhook path does not download video,
call a summary provider, or start a worker. The package does not yet provide
Ring account linking/token storage, durable summary persistence, or a frontend.

- `app/normalizer.py` maps Ring v1.1 webhook event envelopes to the existing
  AccessAble event contract.
- `app/event_sender.py` is a local synthetic event sender for
  `/api/v1/events`; it is not the production webhook path.
- `app/ring_client.py` implements Ring's documented timestamp/duration MP4
  request with typed/sanitized failures, bounded timeouts/retries, byte limits,
  and opt-in redirect handling.
- `app/summaries.py` defines a provider interface, validated summary shape,
  video-evidence and metadata-only paths.
- `app/ranking.py` provides explainable event-type and repeat-window scoring.
- `app/sqlite_pipeline.py` and `app/pipeline_worker.py` provide a local-only,
  durable SQLite queue with atomic event/job deduplication, worker leases,
  restart recovery, bounded retries, and day/timezone/importance timeline output.
- `app/vision_provider.py` provides a disabled-by-default OpenAI Responses API
  adapter. It sends bounded, temporally sampled JPEG frames; it does not send
  MP4 directly. `app/synthetic_fixture.py` creates and decodes local test video.
- `app/summary_demo.py` runs that generated video through a mock retriever and
  fixture inspector, persists a summary in SQLite, restarts the store, and reads
  the local timeline. It does not contact Ring, OpenAI, the backend, or frontend.
- `fixtures/sample_events.json` is a synthetic event fixture. Tests generate a
  three-frame color-card MP4 and inspect decoded frames; it contains no real
  camera footage.

Ring v1.1 mappings are `motion_detected` → `motion`, `button_press` →
`doorbell_press`, and device lifecycle events to their canonical names. The
Ring delivery key is `meta.request_id`; Ring event ID is retained as metadata.
This matches the backend's existing event shape (`source`,
`external_event_id`, `event_type`, `occurred_at`, `device_id`, `metadata`).
The backend schema has no recording or summary fields; no fields were added to
it here.

## Official Ring API findings

Verified against Ring's official API docs on 2026-10-23:

- [Event History](https://developer.amazon.com/docs/ring/api-documentation.html)
  is metadata-only. It returns event IDs/times/device relationships, not a media
  identifier. It is not required before requesting a clip.
- [Media Clips](https://developer.amazon.com/docs/ring/api-documentation.html)
  documents `POST https://api.amazonvision.com/v1/devices/{device_id}/media/video/download`.
  The JSON body requires `timestamp` (epoch milliseconds) and `duration`
  (milliseconds, at most 900,000); a multi-camera request takes one
  `{ "component_id": "..." }` object in `components`.
- Successful responses are binary `video/mp4` with `X-Media-Timestamp`; a
  partial response can include `X-Media-Length`. `416 MEDIA_NOT_FOUND` and
  `425 RECORDING_NOT_READY` are distinct; Ring recommends retrying an unchanged
  recent request for a bounded period. The endpoint retrieves existing footage;
  it does not create a recording.
- Ring documents motion and button-press webhook events as recording-producing
  events. The media request uses device ID, event timestamp, and caller-chosen
  duration, **not** the webhook event ID. `component_ids` from a webhook should
  be used when applicable.
- Ring says a `301` redirect may occur and clients must follow it. The docs do
  not give a stable redirect-host allowlist. This client rejects redirects by
  default; configure exact HTTPS hostnames in `allowed_redirect_hosts` only
  after independently verifying Ring's destination policy. The GET to that
  configured signed URL contains no Ring bearer credential, and the URL is not
  returned or logged.
- The current Ring API reference also requires `User-Agent` in
  `AppName/version` form and `Hardware_Id` as a UUID unique to each user/device
  pair on API requests. The client requires the caller to supply this UUID; it
  cannot safely infer the user's device identity. Ring documents `429` with a
  `Retry-After` seconds header; short waits are honored inline and longer waits
  are returned as a typed error for durable scheduling. Ring warns that cloud
  egress may receive `406` until the partner's static egress IP is approved.
- Ring's current reference distinguishes `404 DEVICE_NOT_FOUND`, `416
  MEDIA_NOT_FOUND`, `422 CORRUPT_RECORDING`, and `425 RECORDING_NOT_READY`.
  A recent `416`/`425` is retryable only within Ring's two-minute readiness
  window; the durable worker schedules a bounded retry. `429` honors
  `Retry-After`; longer waits are returned to the durable queue instead of
  holding a request open.

These docs establish API operation shapes, not that this AccessAble Ring app is
approved for media access. A real customer authorization, approved app scopes,
eligible device/subscription, and server-side access token are still required.
This repository has no verified real Ring authorization or media retrieval.

## Retrieval and privacy behavior

`RingVideoClient.download_event_video(event, duration_ms=..., component_id=...)`
must be invoked explicitly by a future backend worker or approved orchestrator.
The client also requires a caller-supplied Ring bearer token, a per-user/device
UUID `hardware_id`, and uses an application/version user agent.
It accepts only normalized Ring motion/doorbell events, checks that the
requested time range ended at least five seconds earlier, limits duration to 15 minutes and response
bytes to 25 MiB by default, uses connect/read timeouts, never follows redirects
automatically, and retries are capped at five attempts. The caller must wait
for the recording range to end and respect Ring's readiness window; no retry
is done by webhook ingestion.

The returned `RecordingMetadata` carries the event delivery ID, device ID,
time/duration, availability, MIME type, retrieval time, and media bytes for
immediate processing. A single webhook `component_ids` value is passed through
as the documented `components` request entry. Events naming multiple camera
components are safely marked unsupported until the product/backend chooses
per-component processing and summary semantics. Ring does not document a recording ID for this operation,
so `recording_id` remains `None`; no permanent playback reference is fabricated.
The result object is in-memory and must not be persisted with video bytes.
`404` is reported as inaccessible, `416` as not found, `425` as not ready,
`401/403` as authorization failure, and unapproved redirects as unsafe. The
current Ring media docs do not define a distinct expired-recording response or
retention period; the abstraction reserves an `expired` state, but the client
does not guess that `416` means expired.

The actual provider adapter is OpenAI's Responses API with the `gpt-6-luna`
image-capable model. It samples four evenly spaced frames using local FFmpeg and
sends only those JPEGs; video support is not claimed. External processing is
disabled unless `RING_AI_ENABLED=true`, `RING_AI_PROVIDER=openai`, and
`OPENAI_API_KEY` are configured. The call uses `store:false`, but the standard
OpenAI API data controls still apply; account eligibility for modified
monitoring or zero data retention is not established here. The account owner
must approve sending Ring-derived frames to OpenAI and decide retention before
enabling it. No real provider call was made. [Model](https://developers.openai.com/api/docs/models/gpt-6-luna),
[image inputs](https://developers.openai.com/api/docs/guides/images-vision?api-mode=responses),
[data controls](https://developers.openai.com/api/docs/guides/your-data).
At the current standard tier, text tokens are listed at $0.10 per million input
and $0.50 per million output; image input is billed as tokens, so actual
per-clip cost depends on the sampled frames and output length. This is a
documented current rate, not a cost guarantee. The model supports image input
but no video input; the account's region and data-retention options must be
confirmed before enabling it. [Current model pricing](https://developers.openai.com/api/docs/pricing?tab=suite).

The interface is provider-independent. Video summaries are marked
`evidence_type="video"` only after non-empty video bytes were passed to an
explicit provider. Without bytes, the pipeline can describe only normalized
event metadata. Without a provider, video is marked available but the summary
status is unavailable; provider failures are marked failed without leaking
exception details. No real footage is sent to an external service.

The opt-in adapter reads these variable names (values are never committed):
`RING_AI_ENABLED`, `RING_AI_PROVIDER`, `OPENAI_API_KEY`, `RING_AI_MODEL`,
`RING_FFMPEG_PATH`, and `RING_FRAME_SAMPLE_COUNT`. The synthetic demo and tests
need no secret variables. `ACCESSABLE_API_URL` is used only by the separate
synthetic event sender. The Ring media client takes its authorized access token
and per-user/device `hardware_id` as constructor inputs from the backend owner;
it does not add a token to this package's local environment files.

Importance is a numeric score derived from event-type points and same-device,
same-type events in a configurable time window. Repeated events add bounded
points. The output includes the base, repeat count, bonus, rules, and a separate
metadata-based confidence label. It does not estimate danger or trigger actions.

## Local setup, tests, and demo

From the repository root:

```powershell
python -m pip install -r integrations/ring/requirements.txt
python -m pytest -p no:cacheprovider integrations/ring/tests
python -m integrations.ring.app.summary_demo
```

The demo makes a valid three-frame synthetic MP4 locally, decodes and verifies
the red/blue/green cards with a mock fixture inspector, then shows duplicate
delivery handling, worker restart recovery, persisted summary, local SQLite
timeline output, and retrieval/provider failures that stop after two attempts.
The output is labeled synthetic. It does not exercise the AccessAble API or
frontend. No network is used. `av` and `Pillow` are included in the Ring
integration requirements for fixture generation and inspection.

The durable local tables use `UNIQUE(source, external_event_id)` and
`UNIQUE(event_id, processing_version)`. Atomic `BEGIN IMMEDIATE` transactions
serialize enqueue/claim/final-result writes; expired worker leases can be
reclaimed after restart. Video bytes remain in bounded worker memory for
immediate processing and are not stored in SQLite. This is a local integration
implementation, not production ownership-aware backend persistence.

To send the separate synthetic ingestion fixture to a local backend, start the
backend from its documented local setup, then:

```powershell
$env:ACCESSABLE_API_URL = "http://127.0.0.1:8000"
python -m integrations.ring.app.demo_runner
```

The demo sender blocks non-local hosts unless `--allow-remote` is supplied.
Never use it with a production backend. The sender targets `/api/v1/events`;
actual Ring notifications should go directly to the backend's signed webhook
route.

## Dependencies before an end-to-end feature

**Backend owner (Nisha):** see [OWNER_HANDOFF.md](OWNER_HANDOFF.md) for the
implementation-ready schema/API/transaction proposal, Ring's two documented
account-linking choices and endpoint shapes, and the current authentication
gap. The existing event schema cannot store summary/processing state. Never
store signed URLs or raw footage as durable event fields.

**Frontend owner (Nithish):** display event timeline, summary and processing
status, evidence/limitations, recording availability, and a user-authorized
playback action. Include clear metadata-only, unavailable, not-ready, and
expired states. An integration-local result is not a shipped product feature
until backend persistence/API and frontend rendering exist.

**Ring app/operator:** confirm Portal media/device scopes, account-linking
configuration, public HTTPS callback/webhook URLs, staging eligibility, and
redirect destination policy. Ring's development guide says staging testing
requires configured app information and OAuth endpoints, deployed HTTPS
endpoints, and an eligible Ring account/device. This repo cannot confirm the
Portal state or whether this app has the required media approval.

**AI provider/customer approval:** the OpenAI frame adapter is implemented but
disabled; approve the provider/data handling and define retention before any
real footage is sent. No provider request was made.

## Remaining verification

- No real Ring account authorization, Ring API request, webhook, recording, or
  AI video analysis has been performed.
- No real-world record is created by the synthetic demo. Mocked tests establish
  local behavior only.
- Backend API/storage/scheduling and frontend presentation remain unimplemented
  by design; deployment and Ring Portal configuration remain unverified.
- Confirm public HTTPS, account authorization, approved scopes, test device
  eligibility, signed webhook persistence, and a real event's media availability
  before calling the end-to-end path verified.
