# AccessAble Canonical API Contract

This document serves as the **single canonical API specification** for the AccessAble backend.

- **Base URL**: `http://localhost:8000`
- **API Version Prefix**: `/api/v1`
- **Interactive Swagger UI**: `http://localhost:8000/docs`
- **OpenAPI Schema (JSON)**: `http://localhost:8000/openapi.json`

---

## 1. Global Conventions

### Timestamps
- All request and response timestamps must use **ISO 8601** UTC format (e.g. `2026-10-21T12:30:00Z`).
- SQLite returns naive timestamps, which are strictly normalized to timezone-aware UTC at the API response boundary.

### Error Response Format
Validation errors (`HTTP 422 Unprocessable Entity`) return FastAPI's structured error detail:
```json
{
  "detail": [
    {
      "type": "string",
      "loc": ["body", "source"],
      "msg": "Field must not be empty or whitespace only",
      "input": ""
    }
  ]
}
```
Client/application errors (`HTTP 400 Bad Request`, `HTTP 404 Not Found`, `HTTP 409 Conflict`):
```json
{
  "detail": "Human-readable error explanation"
}
```
Internal server errors (`HTTP 500 Internal Server Error`):
```json
{
  "detail": "An unexpected error occurred while processing the request."
}
```
*Note: Internal database connection strings, credentials, and full stack traces are never leaked in API responses.*

---

## 2. API Endpoints

### 2.1 Health Check

#### Check Service Health
- **Method**: `GET`
- **Path**: `/api/v1/health`
- **Description**: Returns backend liveness status and service identifier.
- **Query Parameters**: None
- **Response (HTTP 200 OK)**:
```json
{
  "status": "ok",
  "service": "accessable-api"
}
```

---

### 2.2 Accessibility Events

#### Ingest Event
- **Method**: `POST`
- **Path**: `/api/v1/events`
- **Description**: Ingests an event. Checks for duplicate events using `(source, external_event_id)` when an external ID is provided.
- **Request Headers**: `Content-Type: application/json`

##### Request Schema (`EventCreate`)
| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `source` | string | Yes | - | Event source (e.g., `"ring"`, `"demo"`). Non-empty string. |
| `external_event_id` | string \| null | No | `null` | Source-specific unique event ID. Used for deduplication. |
| `event_type` | string | Yes | - | Event category (e.g., `"motion"`, `"doorbell_press"`). Non-empty string. |
| `occurred_at` | string (ISO 8601) | Yes | - | UTC timestamp when event occurred. |
| `device_id` | string \| null | No | `null` | Device identifier from source. |
| `metadata` | object | No | `{}` | JSON-compatible extra payload. Must not contain credential keys (`token`, `secret`, `password`, `api_key`). |

##### Request Example
```json
{
  "source": "ring",
  "external_event_id": "event-123",
  "event_type": "motion",
  "occurred_at": "2026-10-21T12:30:00Z",
  "device_id": "device-456",
  "metadata": {
    "battery_level": 92
  }
}
```

##### Responses
- **HTTP 201 Created**: A new event was persisted (`is_duplicate: false`).
```json
{
  "event": {
    "id": 1,
    "source": "ring",
    "external_event_id": "event-123",
    "event_type": "motion",
    "occurred_at": "2026-10-21T12:30:00Z",
    "device_id": "device-456",
    "metadata": {
      "battery_level": 92
    },
    "received_at": "2026-10-21T12:31:00Z"
  },
  "is_duplicate": false
}
```
- **HTTP 200 OK**: Duplicate event detected (`is_duplicate: true`). Returns the existing event record without creating another row.
```json
{
  "event": {
    "id": 1,
    "source": "ring",
    "external_event_id": "event-123",
    "event_type": "motion",
    "occurred_at": "2026-10-21T12:30:00Z",
    "device_id": "device-456",
    "metadata": {
      "battery_level": 92
    },
    "received_at": "2026-10-21T12:31:00Z"
  },
  "is_duplicate": true
}
```
- **HTTP 422 Unprocessable Entity**: Validation failure (empty source/event_type, forbidden metadata credentials, invalid timestamps).

##### Deduplication Policy for Events Without `external_event_id`
Events where `external_event_id` is `null` are treated as **distinct events**. Each request persists a new record with `HTTP 201 Created` (`is_duplicate: false`).

---

#### List Events
- **Method**: `GET`
- **Path**: `/api/v1/events`
- **Description**: Returns paginated events matching filter criteria.

##### Query Parameters
| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `source` | string | No | null | Exact match on source (`"ring"`, `"demo"`). Case-insensitive. |
| `event_type` | string | No | null | Exact match on event type (`"motion"`). Case-insensitive. |
| `start_time` | string (ISO 8601) | No | null | Inclusive lower bound for `occurred_at`. |
| `end_time` | string (ISO 8601) | No | null | Inclusive upper bound for `occurred_at`. |
| `limit` | integer | No | 20 | Page size. Min: 1, Max: 100. |
| `offset` | integer | No | 0 | Page offset. Min: 0. |

##### Validation & Ordering
- `start_time` must not be later than `end_time` (returns **HTTP 400 Bad Request**).
- Invalid `limit` (< 1 or > 100) or negative `offset` returns **HTTP 422**.
- Results are deterministically ordered by **`received_at DESC, id DESC`** (newest first).
- `total` represents total matching items across all pages before pagination.

##### Response Example (HTTP 200 OK)
```json
{
  "items": [
    {
      "id": 1,
      "source": "ring",
      "external_event_id": "event-123",
      "event_type": "motion",
      "occurred_at": "2026-10-21T12:30:00Z",
      "device_id": "device-456",
      "metadata": {
        "battery_level": 92
      },
      "received_at": "2026-10-21T12:31:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

---

### 2.3 Accessibility Preferences

#### Retrieve Preferences
- **Method**: `GET`
- **Path**: `/api/v1/preferences`
- **Description**: Retrieves current active accessibility preferences. If none exist yet, documented defaults are automatically persisted and returned.
- **Response (HTTP 200 OK)**:
```json
{
  "visual_alerts_enabled": true,
  "audio_alerts_enabled": true,
  "high_contrast_enabled": false,
  "text_scale": "medium",
  "updated_at": "2026-10-21T15:41:44.100541Z"
}
```

#### Update Preferences
- **Method**: `PUT`
- **Path**: `/api/v1/preferences`
- **Description**: Updates accessibility preferences in place for the profile.
- **Request Headers**: `Content-Type: application/json`

##### Request Schema (`PreferencesUpdate`)
| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `visual_alerts_enabled` | boolean | No | `true` | Enable visual flashing/banners. |
| `audio_alerts_enabled` | boolean | No | `true` | Enable audio alert chimes. |
| `high_contrast_enabled` | boolean | No | `false` | Enable high contrast theme for low-vision users. |
| `text_scale` | string | No | `"medium"` | Text scale option. Allowed values: `"small"`, `"medium"`, `"large"`. |

##### Request Example
```json
{
  "visual_alerts_enabled": false,
  "audio_alerts_enabled": true,
  "high_contrast_enabled": true,
  "text_scale": "large"
}
```

##### Response Example (HTTP 200 OK)
```json
{
  "visual_alerts_enabled": false,
  "audio_alerts_enabled": true,
  "high_contrast_enabled": true,
  "text_scale": "large",
  "updated_at": "2026-10-21T15:41:45.031854Z"
}
```

##### Validation Errors (HTTP 422 Unprocessable Entity)
- Passing unsupported `text_scale` values (e.g. `"huge"`).
- Passing non-boolean values for alert toggles.

---

### 2.4 Event Acknowledgements and History

#### Record Acknowledgement
- **Method**: `POST`
- **Path**: `/api/v1/acknowledgements`
- **Description**: Records an action taken on an event. Validates that the event exists and prevents duplicate operations when the event is already in the requested state.
- **Request Headers**: `Content-Type: application/json`

##### Request Schema (`AcknowledgementCreate`)
| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `event_id` | integer | Yes | - | Internal ID of the event to acknowledge. Must be > 0. |
| `action` | string | No | `"acknowledged"` | Action taken: `"acknowledged"` or `"dismissed"`. |
| `note` | string \| null | No | `null` | Optional comment (max 500 characters). |

##### Request Example
```json
{
  "event_id": 1,
  "action": "acknowledged",
  "note": "Resident checked front door camera"
}
```

##### Responses
- **HTTP 201 Created**: Acknowledgement successfully recorded.
```json
{
  "id": 1,
  "event_id": 1,
  "action": "acknowledged",
  "note": "Resident checked front door camera",
  "acknowledged_at": "2026-10-21T15:51:23.839198Z",
  "event": {
    "id": 1,
    "source": "ring",
    "external_event_id": "event-123",
    "event_type": "motion",
    "occurred_at": "2026-10-21T12:30:00Z",
    "device_id": "device-456",
    "metadata": {},
    "received_at": "2026-10-21T12:31:00Z"
  }
}
```
- **HTTP 404 Not Found**: If referenced `event_id` does not exist (`{"detail": "Event with id 999 does not exist."}`).
- **HTTP 409 Conflict**: If the event is already in the requested state (`{"detail": "Event 1 has already been acknowledged."}`).
- **HTTP 422 Unprocessable Entity**: Invalid action value or invalid `event_id`.

---

#### List Acknowledgement History
- **Method**: `GET`
- **Path**: `/api/v1/acknowledgements`
- **Description**: Retrieves paginated acknowledgement audit history.

##### Query Parameters
| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `event_id` | integer | No | null | Filter by specific event ID. |
| `action` | string | No | null | Filter by action (`"acknowledged"` or `"dismissed"`). |
| `limit` | integer | No | 20 | Page size (1-100). |
| `offset` | integer | No | 0 | Page offset (>= 0). |

##### Sorting
- Stably ordered by **`acknowledged_at DESC, id DESC`** (newest actions first).

##### Response Example (HTTP 200 OK)
```json
{
  "items": [
    {
      "id": 1,
      "event_id": 1,
      "action": "acknowledged",
      "note": "Resident checked front door camera",
      "acknowledged_at": "2026-10-21T15:51:23.839198Z",
      "event": {
        "id": 1,
        "source": "ring",
        "external_event_id": "event-123",
        "event_type": "motion",
        "occurred_at": "2026-10-21T12:30:00Z",
        "device_id": "device-456",
        "metadata": {},
        "received_at": "2026-10-21T12:31:00Z"
      }
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

---

### 2.5 External Integrations (Ring)

#### Retrieve Ring Integration Status
- **Method**: `GET`
- **Path**: `/api/v1/integrations/ring/status`
- **Description**: Returns the verified connection state of the Ring integration.
- **Query Parameters**: None

##### Possible Status Values
- `"connected"`: Live connection verified with authenticated event stream.
- `"disconnected"`: Live connection explicitly offline or disconnected.
- `"error"`: Upstream integration or network error detected.
- `"unknown"`: Integration not yet verified or live credentials unconfigured (default state during development).

##### Response Example (HTTP 200 OK)
```json
{
  "source": "ring",
  "status": "unknown",
  "is_connected": false,
  "last_checked_at": "2026-10-21T16:01:46.759362Z",
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

## 3. Demo vs. Real Ring Events

- **Demo Events**: Ingested with `"source": "demo"`. Used for mock hardware testing, local frontend development, and manual demos.
- **Ring Events**: Ingested with `"source": "ring"`. Created by the backend Ring integration adapter once hardware credentials are verified.
