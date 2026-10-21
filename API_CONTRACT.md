# AccessAble API Contract

This document specifies the current API contract implemented in the AccessAble backend.

**Base URL**: `http://localhost:8000`  
**API Prefix**: `/api/v1`  
**Interactive API Documentation**: `http://localhost:8000/docs`

---

## 1. Global Conventions

### Timestamps
- All timestamps sent to or received from the API are formatted in **ISO 8601** UTC format (e.g. `2026-10-21T12:30:00Z`).
- Naive datetimes sent in request payloads or loaded from SQLite are normalized to UTC at the API boundary.

### Error Response Format
When request validation fails (HTTP 422), FastAPI returns:
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
For general application errors (HTTP 400, HTTP 500):
```json
{
  "detail": "Human-readable error description"
}
```
Internal server errors (HTTP 500) never leak database credentials, connection strings, or stack traces.

---

## 2. Endpoints

### Health Check
- **Method**: `GET`
- **Path**: `/api/v1/health`
- **Description**: Returns backend service health and liveness status.
- **Query Parameters**: None
- **Response (HTTP 200 OK)**:
```json
{
  "status": "ok",
  "service": "accessable-api"
}
```

---

### Ingest Accessibility Event
- **Method**: `POST`
- **Path**: `/api/v1/events`
- **Description**: Ingests an accessibility event. Performs normalization and duplicate detection based on `(source, external_event_id)`.
- **Request Headers**: `Content-Type: application/json`

#### Request Schema
| Field | Type | Required | Description |
|---|---|---|---|
| `source` | string | Yes | Event source (e.g., `"ring"`, `"demo"`). Non-empty string. |
| `external_event_id` | string \| null | No | Source-specific unique event ID. If provided, used for deduplication. |
| `event_type` | string | Yes | Category of event (e.g., `"motion"`, `"doorbell_press"`). Non-empty string. |
| `occurred_at` | string (ISO 8601) | Yes | Timestamp when event occurred. |
| `device_id` | string \| null | No | Source device identifier. |
| `metadata` | object | No | JSON-compatible dictionary for extra attributes. Must not contain credential keys. Default: `{}`. |

#### Request Example
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

#### Response Schemas and Status Codes

- **HTTP 201 Created**: A new event was persisted.
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

- **HTTP 200 OK**: Duplicate event detected (`(source, external_event_id)` was already stored). Returns the existing event without creating a new record.
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

- **HTTP 422 Unprocessable Entity**: Validation failed (e.g., empty source, missing occurred_at, forbidden credential in metadata).
- **HTTP 500 Internal Server Error**: Unexpected failure during persistence.

#### Deduplication & Null External ID Policy
1. **With `external_event_id`**: An exact match on `(source, external_event_id)` returns HTTP 200 with `is_duplicate: true`.
2. **Without `external_event_id` (`null`)**: Treated as **distinct events**. Each request persists a new event with HTTP 201 (`is_duplicate: false`).

---

### List Accessibility Events
- **Method**: `GET`
- **Path**: `/api/v1/events`
- **Description**: Returns paginated events matching filter criteria.

#### Query Parameters
| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `source` | string | No | null | Exact match on event source (e.g., `ring`, `demo`). Case-insensitive. |
| `event_type` | string | No | null | Exact match on event type (e.g., `motion`). Case-insensitive. |
| `start_time` | string (ISO 8601) | No | null | Inclusive lower bound for `occurred_at`. |
| `end_time` | string (ISO 8601) | No | null | Inclusive upper bound for `occurred_at`. |
| `limit` | integer | No | 20 | Page size. Min: 1, Max: 100. |
| `offset` | integer | No | 0 | Pagination offset. Min: 0. |

#### Validation Rules
- If both `start_time` and `end_time` are provided, `start_time` must not be later than `end_time` (otherwise returns **HTTP 400 Bad Request**).
- Invalid `limit` (< 1 or > 100) or negative `offset` returns **HTTP 422 Unprocessable Entity**.

#### Sorting & Pagination
- Events are stably ordered by **`received_at DESC, id DESC`** (newest first).
- `total` represents the total number of matching events across all pages before pagination.

#### Response Example (HTTP 200 OK)
```json
{
  "items": [
    {
      "id": 2,
      "source": "ring",
      "external_event_id": "event-124",
      "event_type": "doorbell_press",
      "occurred_at": "2026-10-21T12:35:00Z",
      "device_id": "device-456",
      "metadata": {},
      "received_at": "2026-10-21T12:35:05Z"
    },
    {
      "id": 1,
      "source": "ring",
      "external_event_id": "event-123",
      "event_type": "motion",
      "occurred_at": "2026-10-21T12:30:00Z",
      "device_id": "device-456",
      "metadata": {},
      "received_at": "2026-10-21T12:31:00Z"
    }
  ],
  "total": 2,
  "limit": 20,
  "offset": 0
}
```

---

## 3. Demo vs. Real Ring Events

- **Demo Events**: Ingested with `"source": "demo"`. Used for mock hardware testing, local frontend development, and manual demos.
- **Ring Events**: Ingested with `"source": "ring"`. Created by the backend Ring integration adapter.
