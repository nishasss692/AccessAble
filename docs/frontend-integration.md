# AccessAble Frontend API Integration Guide

This guide provides practical, framework-neutral documentation for developers integrating a frontend application with the AccessAble backend API.

The backend exposes a REST API built with FastAPI and SQLite. It provides real-time accessible event ingestion, status tracking, acknowledgement history, and user accessibility preference management.

---

## 1. Connection Setup

### 1.1 Backend Prerequisites and Startup

From the repository root or `backend/` directory:

```powershell
# 1. Navigate to backend directory
cd backend

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1    # Windows PowerShell
# source .venv/bin/activate     # macOS / Linux

# 3. Ensure database is initialized (idempotent)
python init_db.py

# 4. Start the development server
uvicorn app.main:app --reload --port 8000
```

### 1.2 URLs and Endpoints

| Resource | URL | Description |
|---|---|---|
| **API Base URL** | `http://localhost:8000` | Base URL for all HTTP requests |
| **API Prefix** | `/api/v1` | All domain endpoints are prefixed with `/api/v1` |
| **Interactive Docs (Swagger UI)** | `http://localhost:8000/docs` | Test endpoints directly in browser |
| **OpenAPI Schema (JSON)** | `http://localhost:8000/openapi.json` | OpenAPI 3.1.0 machine-readable schema |
| **Health Check** | `http://localhost:8000/api/v1/health` | Backend liveness and availability check |

### 1.3 CORS Configuration

The backend is configured with FastAPI CORS middleware.

- **Default Allowed Origin**: `http://localhost:5173` (standard Vite development server).
- **Configuring Frontend Origins**: If your frontend dev server runs on another port (e.g. `http://localhost:3000` for Create-React-App/Next.js) or a custom domain, configure `CORS_ORIGINS` in `backend/.env`:

```ini
# backend/.env
CORS_ORIGINS="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
```

- **Allowed Methods**: `GET`, `POST`, `PUT`, `OPTIONS`, `HEAD`.
- **Allowed Headers**: Standard headers including `Content-Type`, `Accept`, `Origin`, `Authorization`.
- **Credentials**: The API is stateless and does not require session cookies or basic auth. `CORS_ALLOW_CREDENTIALS` defaults to `false`.

### 1.4 Verifying Backend Availability

Before initializing frontend state, verify that the backend is up:

```javascript
async function checkBackendHealth(baseUrl = "http://localhost:8000") {
  try {
    const res = await fetch(`${baseUrl}/api/v1/health`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.status === "ok"; // Returns true when ready
  } catch (err) {
    console.error("AccessAble backend is unreachable:", err);
    return false;
  }
}
```

---

## 2. Endpoint Integration Examples

All examples below use the standard browser `fetch` API.

### 2.1 Fetching Accessibility Preferences

Retrieves the user's active accessibility preferences. If none exist in the database, the backend creates and returns the default profile automatically.

```javascript
async function getPreferences() {
  const response = await fetch("http://localhost:8000/api/v1/preferences");
  if (!response.ok) throw new Error(`Failed to load preferences: ${response.status}`);
  return await response.json();
}
```

**Expected Response (HTTP 200 OK):**
```json
{
  "visual_alerts_enabled": true,
  "audio_alerts_enabled": true,
  "high_contrast_enabled": false,
  "text_scale": "medium",
  "updated_at": "2026-10-21T18:00:00Z"
}
```

---

### 2.2 Updating Accessibility Preferences

Updates accessibility settings. Updates are applied in place to avoid duplicate profile records.

```javascript
async function updatePreferences(prefs) {
  const response = await fetch("http://localhost:8000/api/v1/preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      visual_alerts_enabled: prefs.visualAlerts,
      audio_alerts_enabled: prefs.audioAlerts,
      high_contrast_enabled: prefs.highContrast,
      text_scale: prefs.textScale // "small" | "medium" | "large"
    }),
  });
  if (!response.ok) {
    const errorBody = await response.json();
    throw new Error(errorBody.detail || "Validation error updating preferences");
  }
  return await response.json();
}
```

**Expected Response (HTTP 200 OK):**
```json
{
  "visual_alerts_enabled": true,
  "audio_alerts_enabled": false,
  "high_contrast_enabled": true,
  "text_scale": "large",
  "updated_at": "2026-10-21T18:05:00Z"
}
```

---

### 2.3 Fetching Events (Alert Feed)

Fetches paginated accessibility events with optional filters. Results are deterministically ordered newest first (`received_at DESC, id DESC`).

```javascript
async function fetchEvents({ source, eventType, limit = 20, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (source) params.append("source", source);
  if (eventType) params.append("event_type", eventType);
  params.append("limit", limit.toString());
  params.append("offset", offset.toString());

  const response = await fetch(`http://localhost:8000/api/v1/events?${params}`);
  if (!response.ok) throw new Error(`Failed to fetch events: ${response.status}`);
  return await response.json();
}
```

**Expected Response (HTTP 200 OK):**
```json
{
  "items": [
    {
      "id": 1,
      "source": "demo",
      "external_event_id": "demo-001",
      "event_type": "motion",
      "occurred_at": "2026-10-21T18:00:00Z",
      "device_id": "front-door-cam",
      "metadata": { "battery": 92 },
      "received_at": "2026-10-21T18:00:05Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

---

### 2.4 Submitting a Demo Event (Simulating Alerts)

The frontend can trigger simulated alerts during testing without Ring hardware by posting an event with `"source": "demo"`.

```javascript
async function submitDemoEvent({ eventType = "motion", deviceId = "front-cam", metadata = {} } = {}) {
  const response = await fetch("http://localhost:8000/api/v1/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source: "demo",
      external_event_id: `demo-${Date.now()}`,
      event_type: eventType,
      occurred_at: new Date().toISOString(),
      device_id: deviceId,
      metadata: metadata,
    }),
  });

  if (!response.ok) throw new Error(`Event submission failed: ${response.status}`);
  return await response.json(); // { event: {...}, is_duplicate: boolean }
}
```

- Returns **HTTP 201 Created** (`is_duplicate: false`) for new events.
- Returns **HTTP 200 OK** (`is_duplicate: true`) if an event with identical `(source, external_event_id)` was already processed.

---

### 2.5 Acknowledging an Event

Records an acknowledgement action on an event.

```javascript
async function acknowledgeEvent(eventId, note = "Resident saw alert") {
  const response = await fetch("http://localhost:8000/api/v1/acknowledgements", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event_id: eventId,
      action: "acknowledged",
      note: note,
    }),
  });

  if (response.status === 404) {
    throw new Error("Event does not exist");
  }
  if (response.status === 409) {
    throw new Error("Event is already acknowledged");
  }
  if (!response.ok) {
    throw new Error(`Failed to acknowledge event: ${response.status}`);
  }
  return await response.json(); // Returns recorded acknowledgement
}
```

**Expected Response (HTTP 201 Created):**
```json
{
  "id": 1,
  "event_id": 1,
  "action": "acknowledged",
  "note": "Resident saw alert",
  "acknowledged_at": "2026-10-21T18:02:00Z",
  "event": {
    "id": 1,
    "source": "demo",
    "external_event_id": "demo-001",
    "event_type": "motion",
    "occurred_at": "2026-10-21T18:00:00Z",
    "device_id": "front-door-cam",
    "metadata": { "battery": 92 },
    "received_at": "2026-10-21T18:00:05Z"
  }
}
```

---

### 2.6 Dismissing an Event

Dismissing an event transitions its state and records an entry in the history log.

```javascript
async function dismissEvent(eventId, note = "Dismissed by resident") {
  const response = await fetch("http://localhost:8000/api/v1/acknowledgements", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event_id: eventId,
      action: "dismissed",
      note: note,
    }),
  });

  if (response.status === 404) throw new Error("Event not found");
  if (response.status === 409) throw new Error("Event is already dismissed");
  if (!response.ok) throw new Error(`Failed to dismiss event: ${response.status}`);
  return await response.json();
}
```

---

### 2.7 Loading Acknowledgement History

Retrieves audit history for user actions. Can be filtered by `event_id` or `action`. Results are sorted with newest actions first (`acknowledged_at DESC, id DESC`).

```javascript
async function fetchAcknowledgementHistory({ eventId, action, limit = 20, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (eventId) params.append("event_id", eventId.toString());
  if (action) params.append("action", action);
  params.append("limit", limit.toString());
  params.append("offset", offset.toString());

  const response = await fetch(`http://localhost:8000/api/v1/acknowledgements?${params}`);
  if (!response.ok) throw new Error(`Failed to fetch history: ${response.status}`);
  return await response.json();
}
```

**Expected Response (HTTP 200 OK):**
```json
{
  "items": [
    {
      "id": 2,
      "event_id": 1,
      "action": "dismissed",
      "note": "Dismissed after checking camera",
      "acknowledged_at": "2026-10-21T18:04:00Z",
      "event": { "id": 1, "source": "demo", "event_type": "motion" }
    },
    {
      "id": 1,
      "event_id": 1,
      "action": "acknowledged",
      "note": "Resident saw alert",
      "acknowledged_at": "2026-10-21T18:02:00Z",
      "event": { "id": 1, "source": "demo", "event_type": "motion" }
    }
  ],
  "total": 2,
  "limit": 20,
  "offset": 0
}
```

---

### 2.8 Checking Ring Integration Status

Checks whether the backend has a live connection to Ring hardware.

```javascript
async function getRingStatus() {
  const response = await fetch("http://localhost:8000/api/v1/integrations/ring/status");
  if (!response.ok) throw new Error(`Failed to check Ring status: ${response.status}`);
  return await response.json();
}
```

**Expected Response (HTTP 200 OK):**
```json
{
  "source": "ring",
  "status": "unknown",
  "is_connected": false,
  "last_checked_at": "2026-10-21T18:00:00Z",
  "last_successful_sync_at": null,
  "error_message": null,
  "details": {
    "mode": "unconfigured",
    "note": "Live Ring credentials not configured. Integration mechanism pending hardware verification by Rishi.",
    "demo_events_supported": true
  }
}
```

---

## 3. Frontend State and Error Handling

The frontend should handle these standard HTTP statuses returned by the backend:

| HTTP Status | Meaning | Frontend Handling Recommendation |
|---|---|---|
| **200 OK** | Successful read, preference update, or duplicate event detection | Use response payload to update UI state. |
| **201 Created** | New resource created (new event persisted, acknowledgement recorded) | Append to feed or refresh active alerts. |
| **400 Bad Request** | Query parameter error (e.g. `start_time` after `end_time`) | Show user date filter error; do not send malformed date ranges. |
| **404 Not Found** | Target resource does not exist (e.g. event ID not found during acknowledgement) | Remove the event from active UI queue or inform user that the event was deleted. |
| **409 Conflict** | Target event is already in the requested state (e.g. acknowledging an already acknowledged event) | Update button state to disabled/selected; alert user that the action was already taken. |
| **422 Unprocessable Entity** | Schema validation failure (missing required field, invalid text scale) | Inspect `detail` array for field errors; fix form input bindings. |
| **500 Server Error** | Unexpected backend exception | Display fallback error banner with retry button. Safe error messages avoid leaking backend traces. |
| **Network Error** | Backend is stopped, offline, or blocked by network/CORS | Display persistent offline banner and retry polling every 5–10 seconds. |

### Interpreting Ring Integration States

The `status` field in `GET /api/v1/integrations/ring/status` has four supported values:

1. `"unknown"` (Default): Live Ring credentials have not been configured. The backend is operating in development mode with full support for demo events (`details.demo_events_supported: true`). The frontend should show a neutral status indicator (e.g. "Simulated Mode / Not Connected") without treating this as a crash.
2. `"connected"`: Live Ring stream verified and actively receiving events (`is_connected: true`). The frontend can display a green "Ring Online" indicator.
3. `"disconnected"`: Live credentials are configured but the stream is currently disconnected. Display a warning indicator (e.g. amber "Ring Reconnecting").
4. `"error"`: Upstream Ring API authentication failure or network outage. The frontend should display the safe `error_message` from the response.

---

## 4. Accessibility Behavior Implementation

> **Important**: Storing accessibility preferences in the backend does **not** automatically render accessible styles in the browser. The frontend application is responsible for consuming these preferences and applying them to the DOM.

### 4.1 Accessibility Preference Schema

| Preference | Type | Default | Expected Frontend Implementation |
|---|---|---|---|
| `visual_alerts_enabled` | `boolean` | `true` | When `true`, new alerts trigger high-visibility screen banners, flashing badges, or visual pulse animations. When `false`, suppress flashing lights for photosensitive users. |
| `audio_alerts_enabled` | `boolean` | `true` | When `true`, play an audible chime on incoming alerts. When `false`, keep audio completely silent. |
| `high_contrast_enabled` | `boolean` | `false` | When `true`, apply a high-contrast CSS class (e.g. `document.body.classList.add('high-contrast')`), setting dark backgrounds (`#000000`), vivid text (`#FFFFFF`, `#FFFF00`), and bold borders (`>= 2px solid`). |
| `text_scale` | `"small" \| "medium" \| "large"` | `"medium"` | Apply a root typography multiplier (e.g. `data-text-scale="large"` on `<html>`). |

### 4.2 Recommended CSS / DOM Mapping

```css
/* Text scaling mappings */
html[data-text-scale="small"]  { font-size: 14px; }
html[data-text-scale="medium"] { font-size: 16px; } /* Default */
html[data-text-scale="large"]  { font-size: 20px; }

/* High contrast mode mappings */
body.high-contrast {
  background-color: #000000 !important;
  color: #ffffff !important;
}

body.high-contrast .alert-card {
  border: 3px solid #ffff00 !important;
  background-color: #1a1a1a !important;
}

body.high-contrast button {
  border: 2px solid #ffffff !important;
}
```

---

## 5. Event Lifecycle and Workflow

1. **Ingestion**:
   - Live events or demo events enter via `POST /api/v1/events`.
   - Events with `external_event_id` are deduplicated (`is_duplicate: true` on repeat).
   - Events without `external_event_id` create new records each time.
2. **Display**:
   - Frontend polls or fetches `GET /api/v1/events`.
   - Newest events appear first (`received_at DESC, id DESC`).
3. **Action**:
   - User clicks "Acknowledge" -> `POST /api/v1/acknowledgements` with `action="acknowledged"`.
   - User clicks "Dismiss" -> `POST /api/v1/acknowledgements` with `action="dismissed"`.
   - Submitting the same action again on an already acknowledged/dismissed event returns `HTTP 409 Conflict`.
   - Transitioning from "acknowledged" to "dismissed" succeeds (`HTTP 201 Created`) and adds a second history record.
4. **Audit History**:
   - `GET /api/v1/acknowledgements?event_id={id}` returns complete action log in descending order of time.

---

## 6. Repeatable Demo Testing Workflow

Frontend developers can run this self-contained workflow to verify their integration locally without hardware:

```powershell
# 1. Check backend health
curl.exe http://localhost:8000/api/v1/health

# 2. Ingest a demo motion event
curl.exe -X POST http://localhost:8000/api/v1/events `
  -H "Content-Type: application/json" `
  -d '{"source": "demo", "external_event_id": "demo-001", "event_type": "motion", "occurred_at": "2026-10-21T18:00:00Z", "device_id": "front-cam"}'

# 3. Retrieve active events
curl.exe "http://localhost:8000/api/v1/events?source=demo"

# 4. Acknowledge the event
curl.exe -X POST http://localhost:8000/api/v1/acknowledgements `
  -H "Content-Type: application/json" `
  -d '{"event_id": 1, "action": "acknowledged", "note": "Checked door"}'

# 5. Dismiss the event (transition)
curl.exe -X POST http://localhost:8000/api/v1/acknowledgements `
  -H "Content-Type: application/json" `
  -d '{"event_id": 1, "action": "dismissed", "note": "All clear"}'

# 6. Retrieve acknowledgement history for the event
curl.exe "http://localhost:8000/api/v1/acknowledgements?event_id=1"

# 7. Update accessibility preferences
curl.exe -X PUT http://localhost:8000/api/v1/preferences `
  -H "Content-Type: application/json" `
  -d '{"visual_alerts_enabled": true, "audio_alerts_enabled": false, "high_contrast_enabled": true, "text_scale": "large"}'

# 8. Check Ring integration status
curl.exe http://localhost:8000/api/v1/integrations/ring/status
```

---

## 7. Frontend Developer Handoff Checklist

Before completing your frontend connection:

- [ ] Verify backend is running on `http://localhost:8000`.
- [ ] If your dev server port is not `5173`, add your origin to `backend/.env` under `CORS_ORIGINS`.
- [ ] Call `GET /api/v1/health` on initial page load to verify connection status.
- [ ] Load accessibility preferences on startup (`GET /api/v1/preferences`) and apply theme/font classes to DOM.
- [ ] Implement UI for updating preferences (`PUT /api/v1/preferences`) with text scale options (`small`, `medium`, `large`).
- [ ] Implement event feed (`GET /api/v1/events`) with pagination controls (`limit`, `offset`).
- [ ] Handle `HTTP 409 Conflict` gracefully when acknowledging/dismissing events that have already been acted on.
- [ ] Display safe status indicators for Ring integration (`GET /api/v1/integrations/ring/status`).
